"""Bounded, opt-in synthetic live check of the revised manpower conversation."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from services.agent import AgentError, converse, create_client
from services.config import settings
from services.evidence import load_records
from services.journey import accept_review, working_draft
from services.models import Plan, now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if not args.allow_live:
        print(
            "Dry run: 3 synthetic turns, 18 requests maximum, 3500 output tokens per response, no automatic retries or budget approval."
        )
        return
    cfg = settings()
    if not cfg.api_key or not cfg.model:
        parser.error("Configure key and model privately")
    p, records = Plan(), load_records()
    target = Path("outputs/evaluation") / ("manpower-refinement-" + now().replace(":", "-") + ".jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)
    counts = dict(turns=0, requests=0, input_tokens=0, output_tokens=0)

    def write(kind, **entry):
        with target.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    dict(
                        time=now(),
                        kind=kind,
                        model=cfg.model,
                        counts=dict(counts),
                        plan_snapshot=p.model_dump(mode="json"),
                        **entry,
                    ),
                    ensure_ascii=False,
                )
                + "\n"
            )

    sdk = create_client(cfg.api_key)

    class Responses:
        def create(self, **kwargs):
            if counts["requests"] >= 18:
                raise AgentError("Original 18-request ceiling reached")
            counts["requests"] += 1
            write("request_reserved")
            response = sdk.responses.create(**kwargs)
            usage = getattr(response, "usage", None)
            counts["input_tokens"] += getattr(usage, "input_tokens", 0)
            counts["output_tokens"] += getattr(usage, "output_tokens", 0)
            write("request_usage")
            return response

    messages = [
        "Synthetic development case only. Build an FM manpower budget for an invented weekday office, starting in 2028 with 2 base years and 2 option years; the exact date is not decided. My known roles are Senior Property Executive cum FSM: 1, for overall accountability, contractor supervision and fire-safety coordination; Technician: 3, for routine facilities fault attendance. Both quantities are my workload planning scenarios, not continuous coverage calculations. I also need an Admin Executive to handle maintenance records, contractor reports and tenant feedback, but have not supplied its quantity yet. Existing owner-appointed specialist contractors perform all specialist servicing; a separate cleaning contractor and security contractor cover cleaning and guarding. This FM team supervises those contracts rather than replacing them. Normal weekday office attendance only; no 24/7 post or event requirement. Qualifications and experience are not specified. Please retain all this and ask about material missing information before presenting the complete proposal.",
        "Use 1 Admin Executive. The brief basis is one dedicated weekday administrator for the stated records, reports and tenant feedback. All three roles cover weekday daytime duties only. Keep the Senior Property Executive cum FSM combined title and its quantity of 1; do not split it. The technicians' quantity remains 3. There are no additional in-scope duties beyond those supplied; specialist works, cleaning and guarding remain externally covered. Compile one manpower review when ready, without rates or escalation yet.",
        "Correction to my earlier answer: use 4 Technicians instead of 3. This is my revised weekday workload scenario. Keep all other roles, quantities, duties, external support and contract terms unchanged. Refresh the single manpower proposal for my review; do not approve it for me.",
    ]
    write(
        "started",
        limits=dict(turns=3, requests=18, output_tokens_per_response=3500),
        synthetic=True,
        earlier_traces_unchanged=True,
    )
    try:
        for message in messages:
            counts["turns"] += 1
            write("turn_started", input=message)
            before = len(p.tool_audit)
            answer = converse(
                p, records, message, SimpleNamespace(responses=Responses()), cfg.model, "Profile"
            )
            write("live_turn", input=message, answer=answer, tools=p.tool_audit[before:])
            print(
                f"Turn {counts['turns']}: checkpoint={p.review_checkpoint or 'gathering'}, requests={counts['requests']}/18",
                flush=True,
            )
            if counts["turns"] == 1 and p.review_checkpoint:
                raise ValueError("Premature proposal: admin quantity was missing")
        draft = working_draft(p)
        assert p.review_checkpoint == "manpower", "Complete brief did not reach manpower review"
        assert not p.confirmations, "Model approved a decision"
        quantities = {r.label: r.quantity for r in draft.roles if r.included}
        assert quantities == {
            "Senior Property Executive cum FSM": 1,
            "Technician": 4,
            "Admin Executive": 1,
        }, quantities
        assert draft.profile.start is None and draft.profile.start_year == 2028
        assert draft.profile.base_years == 2 and draft.profile.option_years == 2
        next_stage = accept_review(p, "Scripted synthetic development officer", records)
        assert next_stage == 4 and "rates" not in p.confirmations and "final" not in p.confirmations
        write(
            "completed",
            next_stage=next_stage,
            scripted_manpower_confirmation=True,
            budget_approval=False,
            human_behaviour_score=None,
        )
        print(
            "Passed retained facts, missing-quantity guard, revision and one confirmation to rates.",
            flush=True,
        )
    except Exception as error:
        write(
            "failure",
            error=str(error)
            if isinstance(error, (AgentError, AssertionError, ValueError))
            else "Unexpected runner error; inspect locally",
        )
        print("Stopped; safe failure recorded for review.", flush=True)
    finally:
        sdk.close()
        print(f"Trace: {target}; usage: {counts}", flush=True)


if __name__ == "__main__":
    main()
