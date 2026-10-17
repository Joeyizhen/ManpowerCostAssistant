"""Opt-in bounded development conversation starting with an officer-entered table."""

import argparse
import json
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import openpyxl

from services.agent import AgentError, converse, create_client
from services.calculations import budget, sensitivity
from services.config import settings
from services.evidence import load_records
from services.export import export_excel
from services.hybrid import initialise_rates, parse_manpower_list, save_input_table
from services.journey import accept_review, prepare_review, working_draft
from services.models import Plan, now
from services.workflow import apply_change


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if not args.allow_live:
        print(
            "Dry run: 3 synthetic turns; 18 requests maximum; 3500 output tokens/response; no automatic retries or budget approval."
        )
        return
    cfg = settings()
    if not cfg.api_key or not cfg.model:
        parser.error("Configure the key and model privately")
    p, records = Plan(), load_records()
    brief = "SYNTHETIC weekday office FM contract. Team supervises separate cleaning, security and specialist maintenance contracts and attends routine facilities faults. Quantities are officer workload allowances, not continuous coverage predictions."
    rows = parse_manpower_list(
        "Senior Property Executive cum FSM, 0.5, contract supervision and fire coordination\nTechnician, 3, routine weekday facilities fault attendance\nAdmin Executive, 1, records and reports plus tenant enquiries"
    )
    rows[0]["Deployment"] = "shared / fractional"
    save_input_table(
        p,
        brief,
        2028,
        2,
        2,
        rows,
        "Cleaning/security/specialist works are external. An internal tenant desk already handles all tenant enquiries. The senior officer is shared across two sites; confirm whether 0.5 is this contract allocation.",
    )
    p.manpower_review_requested = True
    target = Path("outputs/evaluation") / ("hybrid-" + now().replace(":", "-") + ".jsonl")
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
        "Review my manpower plan from the supplied brief, contract inputs and table. Check material duplication/shared allocations/external support. Ask targeted clarification only where it could change the plan. Preserve my titles and quantities; no prices or approval.",
        "Yes, remove tenant enquiries from the Admin Executive duties: the internal desk retains them. Our Admin Executive handles only maintenance records and contractor reports. The senior officer allocation is 0.5 FTE for THIS contract, shared with the other site; do not add another full person. The 3 Technicians are my weekday workload allowance, with specialist servicing externally delivered. All stated in-plan duties are covered by these roles; no 24/7, standby, events or other duties are in scope. Keep the start year 2028, 2 base years and 2 option years; no exact date yet. Compile one manpower review when ready.",
        "Revision: change Technician from 3 to 4 for my revised weekday workload allowance. Keep the 0.5 Senior Property Executive cum FSM and 1 Admin Executive, all confirmed duty boundaries, external support and contract terms unchanged. Refresh the one manpower review, without approving it.",
    ]
    write(
        "started",
        synthetic=True,
        earlier_traces_unchanged=True,
        limits=dict(turns=3, requests=18, output_tokens_per_response=3500),
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
                f"Turn {counts['turns']}: {p.review_checkpoint or 'targeted clarification'}, {counts['requests']}/18 requests",
                flush=True,
            )
            if counts["turns"] == 1:
                assert not p.review_checkpoint, (
                    "Unresolved duplicated duties/shared allocation led to premature review"
                )
                assert "?" in answer, "No relevant clarification asked"
        draft = working_draft(p)
        assert p.review_checkpoint == "manpower", (
            "Complete table and clarification did not reach manpower review"
        )
        assert {r.label: r.quantity for r in draft.roles if r.included} == {
            "Senior Property Executive cum FSM": 0.5,
            "Technician": 4,
            "Admin Executive": 1,
        }
        assert draft.profile.start is None and draft.profile.start_year == 2028
        assert (draft.profile.base_years, draft.profile.option_years) == (2, 2)
        assert not p.confirmations and all(r.rate is None for r in draft.roles)
        assert accept_review(p, "Scripted synthetic development officer", records) == 4
        write("conversation_completed", scripted_manpower_confirmation=True, budget_approval=False)
        # Explicit synthetic officer selections exercise the downstream Python journey. No more LLM calls.
        initialise_rates(p, records, 2028)
        for r in list(p.roles):
            if r.included and r.rate is None:
                apply_change(
                    p,
                    "role",
                    {
                        **r.model_dump(mode="json"),
                        "rate": 6500,
                        "rate_origin": "Officer assumption",
                        "rate_reason": "Explicit SYNTHETIC officer allowance for unsupported combined senior title",
                        "rate_notes": "0.5 FTE allocation; inclusive monthly full-FTE unit rate, not salary",
                    },
                    "Synthetic officer input",
                    "Synthetic officer",
                )
        assert prepare_review(p, "rates", records)["ready"]
        assert accept_review(p, "Scripted synthetic development officer", records) == 6
        for r in list(p.roles):
            if r.included:
                apply_change(
                    p,
                    "role",
                    {
                        **r.model_dump(mode="json"),
                        "escalation": [0, 0.02, 0.02, 0.02],
                        "escalation_reason": "Explicit SYNTHETIC officer 2% future-price allowance, not observed inflation",
                    },
                    "Synthetic officer input",
                    "Synthetic officer",
                )
        assert prepare_review(p, "escalation", records)["ready"]
        assert accept_review(p, "Scripted synthetic development officer", records) == 7
        result = budget(p, records)
        assert round(sum(result["annual_totals"]), 2) == result["contract_total"]
        assert round(result["base_total"] + result["option_total"], 2) == result["contract_total"]
        assert (
            round(result["waterfall"]["baseline"] + sum(result["waterfall"]["additions"]), 2)
            == result["contract_total"]
        )
        for r in (r for r in p.roles if r.included):
            unit = Decimal(str(r.rate))
            for i, line in enumerate(row for row in result["rows"] if row["role_id"] == r.id):
                unit = (unit * (1 + Decimal(str(r.escalation[i])))).quantize(Decimal(".01"), ROUND_HALF_UP)
                assert (
                    float((unit * Decimal(str(r.quantity)) * 12).quantize(Decimal(".01"), ROUND_HALF_UP))
                    == line["annual_cost"]
                )
        scenarios = sensitivity(p, records)
        assert (
            scenarios[0]["contract_total"]
            < scenarios[1]["contract_total"]
            == result["contract_total"]
            < scenarios[2]["contract_total"]
        )
        workbook = export_excel(p, records)
        target.with_suffix(".xlsx").write_bytes(workbook)
        wb = openpyxl.load_workbook(BytesIO(workbook))
        assert len(wb.sheetnames) == 9 and sum(len(ws._charts) for ws in wb) == 2
        assert "final" not in p.confirmations
        write(
            "completed",
            budget=result,
            calculation_checks="Decimal role/year, totals, waterfall, sensitivity, nine sheets and two charts passed",
            budget_approval=False,
            human_behaviour_score=None,
        )
        print(
            "Passed table-led clarification, retained answers, revision, manpower confirmation and downstream calculations/export.",
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
        raise SystemExit(1) from None
    finally:
        sdk.close()
        print(f"Trace: {target}; usage: {counts}", flush=True)


if __name__ == "__main__":
    main()
