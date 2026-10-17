"""Two bounded real-model checks on isolated copies of saved synthetic working state."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from services.agent import AgentError, converse, create_client
from services.config import settings
from services.evidence import load_records
from services.models import Plan, now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if not args.allow_live:
        print(
            "Dry run: two synthetic saved-state follow-ups, at most 2 turns / 12 Responses requests, 3500 output tokens per response; no retries. Zero API calls."
        )
        return
    entries = [json.loads(line) for line in args.trace.read_text(encoding="utf-8").splitlines()]
    turns = [e for e in entries if e["kind"] == "live_turn"]
    requirement = next(e for e in turns if e["checkpoint"] == "requirements")
    cfg, records = settings(), load_records()
    if not cfg.api_key or not cfg.model:
        parser.error("Configure key/model privately")
    cases = [
        (
            "requirements-confirmation",
            "Profile",
            requirement["plan_snapshot"],
            "Please summarise the requirements I already supplied for correction and the next meaningful confirmation. Retain my revised opening hours and unknown assets. Keep roles and costs until the relevant later decision.",
        ),
        (
            "final-calculation-explanation",
            "Contract budget",
            turns[-1]["plan_snapshot"],
            "Please verify and present the full contract budget, annual totals, base versus option totals and the method behind them. Retain the disclosed limitations and leave final approval to me.",
        ),
    ]
    counts = {"requests": 0, "turns": 0, "input_tokens": 0, "output_tokens": 0}
    target = args.trace.parent / ("followups-" + now().replace(":", "-") + ".jsonl")
    sdk = create_client(cfg.api_key)
    plan, case_id = None, ""

    def write(entry):
        with target.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "time": now(),
                        "model": cfg.model,
                        "source_trace": str(args.trace),
                        "case": case_id,
                        "counts": dict(counts),
                        **entry,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    class Responses:
        def create(self, **kwargs):
            if counts["requests"] >= 12:
                raise AgentError("Two-case follow-up request ceiling reached")
            counts["requests"] += 1
            write({"kind": "request_reserved"})
            response = sdk.responses.create(**kwargs)
            counts["input_tokens"] += getattr(response.usage, "input_tokens", 0)
            counts["output_tokens"] += getattr(response.usage, "output_tokens", 0)
            write({"kind": "request_usage"})
            return response

    write(
        {
            "kind": "started",
            "limits": {"turns": 2, "requests": 12, "output_tokens_per_response": 3500},
            "original_trace_unchanged": True,
        }
    )
    for case_id, stage, snapshot, message in cases:
        plan = Plan.model_validate(snapshot)
        if "final" in plan.confirmations:
            parser.error("Use pre-final working state; never modify a completed approval")
        plan.pending, plan.review_checkpoint = [], ""
        counts["turns"] += 1
        write(
            {
                "kind": "turn_started",
                "stage": stage,
                "input": message,
                "plan_snapshot": plan.model_dump(mode="json"),
            }
        )
        before = len(plan.tool_audit)
        try:
            answer = converse(
                plan, records, message, SimpleNamespace(responses=Responses()), cfg.model, stage
            )
        except AgentError as error:
            write({"kind": "failure", "error": str(error)})
            print(f"Stopped {case_id}: {error}")
            break
        write(
            {
                "kind": "live_turn",
                "answer": answer,
                "tools": plan.tool_audit[before:],
                "checkpoint": plan.review_checkpoint,
                "plan_snapshot": plan.model_dump(mode="json"),
                "human_behaviour_score": None,
                "human_faithfulness_score": None,
            }
        )
        print(f"Completed {case_id}; requests used {counts['requests']}/12", flush=True)
    write({"kind": "finished"})
    print(f"Trace: {target}", flush=True)


if __name__ == "__main__":
    main()
