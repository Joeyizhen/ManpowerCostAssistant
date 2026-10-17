"""Opt-in live evaluation runner. Every case is isolated; no model self-grading or fake scores."""

import argparse
import json
from pathlib import Path

from services.agent import AgentError, converse, create_client
from services.config import settings
from services.demo import demo_plan
from services.evidence import load_records
from services.models import GATES, Plan, now
from services.workflow import confirm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["development", "held-out"], default="development")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--allow-live", action="store_true", help="Explicitly enable billable calls")
    args = parser.parse_args()
    if not 1 <= args.limit <= 30:
        parser.error("Use a limit between 1 and 30")
    cases = json.loads(Path("evaluation/cases.json").read_text(encoding="utf-8"))
    cases = [c for c in cases if c["split"] == args.split][: args.limit]
    if not args.allow_live:
        print(
            json.dumps(
                {
                    "mode": "dry run; zero API calls",
                    "split": args.split,
                    "case_ids": [c["id"] for c in cases],
                    "maximum_responses_if_enabled": len(cases) * 6,
                }
            )
        )
        return
    cfg = settings()
    if not cfg.api_key or not cfg.model:
        parser.error(
            "Privately configure OPENAI_API_KEY and OPENAI_MODEL; never provide them on the command line"
        )
    print(
        f"Live evaluation: {len(cases)} synthetic-only cases; maximum {len(cases) * 6} Responses requests, 3,500 output tokens per request. Model: {cfg.model}"
    )
    print(
        "The output contains prompts, public tool results and replies, not API keys or internal reasoning. Review costs in your provider account."
    )
    records = load_records()
    path = Path("outputs/evaluation")
    path.mkdir(parents=True, exist_ok=True)
    outfile = path / (args.split + "-" + now().replace(":", "-") + ".jsonl")
    client = create_client(cfg.api_key)
    for case in cases:
        plan = Plan() if case["stage"] == "Profile" else demo_plan()
        target = {
            "Responsibilities": 1,
            "Quantities": 2,
            "Manpower plan": 3,
            "Rates": 4,
            "Escalation": 6,
            "Contract budget": 8,
        }.get(case["stage"], 0)
        for gate in GATES[:target]:
            confirm(plan, gate, "Evaluation setup", records)
        try:
            answer = converse(plan, records, case["prompt"], client, cfg.model, case["stage"])
            entry = {
                "case": case,
                "model": cfg.model,
                "time": now(),
                "answer": answer,
                "tools": plan.tool_audit,
                "proposals": plan.pending,
                "human_behaviour_score": None,
                "human_faithfulness_score": None,
                "failure_analysis": None,
                "live": True,
            }
        except AgentError as e:
            entry = {"case": case, "model": cfg.model, "time": now(), "error": str(e), "live": True}
        with outfile.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(case["id"] + ": recorded; awaiting human scoring")
    print(str(outfile))


if __name__ == "__main__":
    main()
