"""Opt-in complete synthetic conversation, real model, explicit scripted officer actions."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from services.agent import AgentError, converse, create_client
from services.calculations import budget
from services.config import settings
from services.evidence import load_records
from services.export import export_excel
from services.journey import accept_review, working_draft
from services.models import STAGES, Plan, now
from services.workflow import confirm, findings, unlocked_stage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--resume", type=Path, help="Continue this synthetic check from its retained trace")
    args = parser.parse_args()
    if not args.allow_live:
        print(
            "Dry run: one blank synthetic journey with a revision; maximum 18 conversational turns / 108 Responses requests. Zero API calls."
        )
        return
    cfg = settings()
    if not cfg.api_key or not cfg.model:
        parser.error("Configure the key/model privately")
    records, plan = load_records(), Plan()
    directory = Path("outputs/evaluation")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("conversation-" + now().replace(":", "-") + ".jsonl")
    counts = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "turns": 0}
    if args.resume:
        target = args.resume
        entries = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
        if any(e["kind"] == "completed" for e in entries):
            parser.error(
                "This conversation is complete; use its saved trace for local review, not new API calls"
            )
        if any(e["model"] != cfg.model for e in entries):
            parser.error("Resume with the same configured model")
        snapshots = [e["plan_snapshot"] for e in entries if "plan_snapshot" in e]
        if snapshots:
            plan = Plan.model_validate(snapshots[-1])
            if "final" in plan.confirmations:
                parser.error("The saved budget is already finally confirmed; do not resume live calls")
        else:
            # Compatibility with the initial three-turn trace, before snapshot instrumentation.
            for e in entries:
                if e["kind"] == "live_turn":
                    plan.chat.extend(
                        [
                            {"role": "user", "content": e["input"]},
                            {"role": "assistant", "content": e["answer"]},
                        ]
                    )
                    plan.tool_audit.extend(e["tools"])
                    plan.working_notes, plan.pending = e["working_notes"], e["pending"]
                    plan.review_checkpoint = e["checkpoint"]
        usage_entries = [e["counts"] for e in entries if "counts" in e]
        if not usage_entries:
            parser.error("Cannot resume without persisted usage; refusing to reset the request ceiling")
        prior = usage_entries[-1]
        if any(type(prior.get(k)) is not int or prior[k] < 0 for k in counts):
            parser.error("Persisted usage counters are invalid")
        recorded_turns = sum(e["kind"] == "live_turn" for e in entries)
        if prior["turns"] < recorded_turns or prior["requests"] < recorded_turns:
            parser.error("Persisted usage is inconsistent with recorded turns")
        counts.update(prior)
        if counts["requests"] >= 108 or counts["turns"] >= 18:
            parser.error("The original live-check ceiling has already been reached")
        print(
            f"Resuming with {counts['requests']} requests / {counts['turns']} turns already used; original ceilings remain 108 / 18.",
            flush=True,
        )

    sdk = create_client(cfg.api_key)

    class Responses:
        def create(self, **kwargs):
            if counts["requests"] >= 108:
                raise AgentError("Live smoke-test request ceiling reached")
            counts["requests"] += 1
            # Persist before dispatch so a process interruption cannot reset consumed request capacity.
            write({"kind": "request_reserved", "counts": dict(counts)})
            response = sdk.responses.create(**kwargs)
            usage = getattr(response, "usage", None)
            counts["input_tokens"] += getattr(usage, "input_tokens", 0)
            counts["output_tokens"] += getattr(usage, "output_tokens", 0)
            return response

    client = SimpleNamespace(responses=Responses())

    def write(entry):
        with target.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "time": now(),
                        "model": cfg.model,
                        "plan_snapshot": plan.model_dump(mode="json"),
                        **entry,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def turn(text):
        if counts["turns"] >= 18:
            raise AgentError("Live conversation turn ceiling reached")
        counts["turns"] += 1
        write({"kind": "turn_started", "input": text, "counts": dict(counts)})
        previous = len(plan.tool_audit)
        stage = STAGES[unlocked_stage(plan)]
        answer = converse(plan, records, text, client, cfg.model, stage)
        write(
            {
                "kind": "live_turn",
                "stage": stage,
                "input": text,
                "answer": answer,
                "tools": plan.tool_audit[previous:],
                "working_notes": plan.working_notes,
                "checkpoint": plan.review_checkpoint,
                "pending": plan.pending,
            }
        )
        print(f"Turn {counts['turns']}: {stage}; ready={plan.review_checkpoint or 'gathering'}", flush=True)
        return answer

    def accept(checkpoint):
        if plan.review_checkpoint != checkpoint:
            raise AgentError(
                f"Conversation did not prepare {checkpoint}; inspect trace instead of bypassing readiness"
            )
        stage = accept_review(plan, "Synthetic development officer", records)
        write(
            {
                "kind": "scripted_officer_confirmation",
                "checkpoint": checkpoint,
                "next_step": STAGES[stage],
                "confirmations": plan.confirmations,
                "profile": plan.profile.model_dump(mode="json"),
                "roles": [r.model_dump(mode="json") for r in plan.roles],
            }
        )

    try:
        if "responsibilities" not in plan.confirmations:
            if not args.resume:
                turn(
                    "This is a SYNTHETIC development project from a blank session. I need an FM manpower budget for a public civic venue with two buildings. Start 1 Jan 2024, four base years and two option years. Public opening is daily 08:00–22:00, with one shared technical response post on site 24/7. I have no manpower plan or role list. Help me work out what you need."
                )
                if plan.pending:
                    raise AgentError("Premature proposal after incomplete opening description")
                turn(
                    "The FM team handles contract/vendor oversight, technical response and routine contract reporting. Security, cleaning and visitor enquiries are covered by existing internal teams; event delivery is outside scope. The technical post must be physically present continuously with a 15-minute response. BMS is present, chiller absent and critical-power details unknown. Technical contractors handle specialist maintenance, not the response post. GST, cleaning, security, specialist maintenance and event delivery costs are excluded."
                )
                turn(
                    "Correction to my earlier answer: public opening is 08:00–20:00 daily, not 22:00. The technical post is still 24/7 and the contract remains four base years plus two options. Please retain the other answers and show the requirements summary only if you have enough information."
                )
            draft = working_draft(plan)
            if (
                draft.profile.base_years != 4
                or draft.profile.option_years != 2
                or "20:00" not in (draft.profile.operating_hours or "")
            ):
                raise AgentError("Revision or retained contract facts missing from working notes")
            if plan.review_checkpoint != "requirements" and "responsibilities" not in plan.confirmations:
                turn(
                    "The two buildings share one site; either is reachable on foot within five minutes with no known access barrier. One shared technical responder is my planning requirement, not two simultaneous response positions. The 15-minute requirement is attendance, assessment of BMS alarms, making equipment safe within competence and escalation to specialist contractors, not specialist repairs. Specialist contractors provide their own call-out cover. Retain critical-power details as unknown. Please review the requirements if these material gaps are now answered."
                )
            accept("requirements")
        if "plan" not in plan.confirmations:
            if not args.resume or not any(
                e.get("stage") == "Quantities" and e["kind"] == "live_turn" for e in entries
            ):
                turn(
                    "Officer action: I confirmed the requirements in the interface. Lead me to the next decision. I do not have roles in mind; what operational information is still needed before suggesting them?"
                )
            turn(
                "Use 44 gross weekly hours and 1.15 relief as my explicit illustrative assumptions, with whole dedicated technical personnel. For oversight and routine reporting, I choose one daytime FM manager as an officer scenario; no validated workload rule is claimed. FM manager: five years experience, FM qualification requirements unknown for now. Technician: technical diploma and three years experience. Use the confirmed duties, calculate technical coverage with Python, check missing or duplicated coverage, and prepare the manpower decision when ready. No costs yet."
            )
            if plan.review_checkpoint != "manpower":
                turn(
                    "Retain those supplied assumptions and requirements. Are there material gaps still preventing the manpower review? If none, prepare that decision for confirmation; do not invent new requirements."
                )
            accept("manpower")
        if "base" not in plan.confirmations:
            if args.resume and any(r.mapped_role is None for r in plan.roles):
                turn(
                    "Before prices, please prepare an updated manpower mapping review. I propose comparing my original FM Manager title to Facilities Manager for the same confirmed oversight/reporting scope; retain the original title and disclose qualification/comparability limits. Technician is an exact supported title. Use the validated evidence catalog, retain the quantities and all other operational answers, and let me confirm these mappings before pricing."
                )
                accept("manpower")
            turn(
                "Officer action: I confirmed the manpower plan in the interface. Guide rate selection now. For each included role retrieve comparable SYNTHETIC awarded public-venue rates priced in 2024. Recommend the median inclusive monthly rate, show source IDs, filters, sample count and limitations. These are development reference prices, not market reality; I will review the complete rates decision."
            )
            if plan.review_checkpoint != "rates":
                turn(
                    "Use the retrieved comparable medians for all included roles as synthetic benchmark selections. Retain the qualifications and limitations and prepare the complete rate/base-year review if ready."
                )
            accept("rates")
        if "escalation" not in plan.confirmations:
            turn(
                "Officer action: I confirmed the rates and preliminary base-year overview. Retrieve SYNTHETIC awarded public-venue multiyear schedules for each included role. Recommend their median implied yearly unit-price change as a constant officer planning assumption, first contract year zero, covering all six years. No separate policy increment or target-year quote. Explain sample counts, priced years, method and limitations; this is not realised inflation."
            )
            if plan.review_checkpoint != "escalation":
                turn(
                    "Use the retrieved schedule median for each role, repeated over later contract years, and prepare the six-year future-price review. Keep causes unverified and policy additions zero."
                )
            accept("escalation")
        if "validation" not in plan.confirmations:
            turn(
                "Officer action: I confirmed the future cost profile. Calculate the full contract budget with Python and show the current validation findings. Ask what you need from me before recording any decisions."
            )
            current = findings(plan, records)
            turn(
                "For this SYNTHETIC development review only, propose each of the following as a data limitation with this justification: I reviewed the disclosed synthetic sources, unknown asset/qualification details, officer scenario and indicative roster calculation. Real evidence, workload rules, missing facts and roster feasibility require verification before procurement; this remains a qualified development budget, not verified market evidence. Excluded services remain excluded. Do not approve the final budget. Finding IDs: "
                + ", ".join(f.id for f in current)
            )
            accept("validation")
        turn(
            "Officer action: I confirmed the finding decisions. Present the full six-year contract value, separate base and optional totals, annual costs and remaining qualifications using Python tools. Do not approve it on my behalf."
        )
        if "final" in plan.confirmations:
            raise AgentError("The model approved the budget without an officer action")
        totals = budget(plan, records)
        confirm(plan, "final", "Synthetic development officer", records)
        workbook = directory / (target.stem + ".xlsx")
        workbook.write_bytes(export_excel(plan, records))
        write(
            {
                "kind": "completed",
                "counts": counts,
                "budget": totals,
                "officer_final_confirmation": True,
                "workbook": str(workbook),
            }
        )
        print(
            "Complete synthetic conversation, scripted final officer approval and workbook export recorded.",
            flush=True,
        )
    except (AgentError, ValueError) as e:
        write({"kind": "failure", "error": str(e), "counts": counts})
        print("Conversation check stopped: " + str(e), flush=True)
    print(str(target), flush=True)


if __name__ == "__main__":
    main()
