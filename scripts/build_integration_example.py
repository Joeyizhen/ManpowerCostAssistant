"""Regenerate only the synthetic handoff example and JSON schemas. No API/database access."""

import json
from pathlib import Path

from services.calculations import budget
from services.demo import demo_plan
from services.evidence import load_records, rate_benchmark
from services.integration_contracts import BudgetDocument, TenderSubmission

ROOT = Path(__file__).resolve().parents[1]


def synthetic_budget():
    plan, records = demo_plan(), load_records()
    for role in plan.roles:
        role.quantity_unit = "headcount"  # Explicit fixture assumption; never inferred from an officer plan.
    result = budget(plan, records)
    roles, assumptions, evidence = [], [], []
    for role in plan.roles:
        if not role.included:
            continue
        reference = rate_benchmark(
            records, role.mapped_role, role.benchmark_year, role.benchmark_status, role.benchmark_scope
        )
        eid, qid, fid = "rate-" + role.id, "deployment-" + role.id, "future-" + role.id
        evidence.append(
            dict(
                evidence_id=eid,
                kind="synthetic fixture" if reference["available"] else "officer assumption",
                label="SYNTHETIC inclusive monthly rate; no market validation",
                record_ids=[r["record_id"] for r in reference["records"]],
                limitations=[
                    reference["limitations"],
                    "Synthetic example only; unsupported roles use invented officer allowances.",
                ],
            )
        )
        assumptions += [
            dict(assumption_id=qid, description="SYNTHETIC: " + role.quantity_reason),
            dict(assumption_id=fid, description="SYNTHETIC: " + role.escalation_reason),
        ]
        roles.append(
            dict(
                role_id=role.id,
                original_title=role.label,
                mapped_benchmark_role=role.mapped_role,
                responsibility_ids=role.responsibility_ids,
                duties="; ".join(
                    d.description for d in plan.responsibilities if d.id in role.responsibility_ids
                ),
                quantity=role.quantity,
                quantity_unit="headcount",
                quantity_basis=role.quantity_reason,
                monthly_rate=role.rate,
                rate_unit="inclusive monthly per head",
                source_rate_basis="Inclusive monthly tender charge per full-time person; not employee salary",
                rate_pricing_year=role.benchmark_year or 2024,
                evidence_refs=[eid],
                assumption_refs=[qid, fid],
                years=[
                    dict(
                        contract_year=row["year"],
                        pricing_year=plan.profile.start.year + row["year"] - 1,
                        period_start=row["period_start"],
                        period_end=row["period_end"],
                        optional=row["optional"],
                        quantity=row["quantity"],
                        monthly_unit_rate=row["monthly_unit_rate"],
                        annual_adjustment=row["policy_cost"],
                        annual_cost=row["annual_cost"],
                    )
                    for row in result["rows"]
                    if row["role_id"] == role.id
                ],
            )
        )
    return BudgetDocument.model_validate(
        dict(
            budget_id="SYNTHETIC-BUDGET-001",
            source_plan_id="SYNTHETIC-PLAN-001",
            source_plan_version=1,
            revision=1,
            status="approved",
            synthetic=True,
            label="SYNTHETIC APPROVED-BUDGET EXAMPLE — NOT A REAL APPROVAL OR TENDER",
            approval=dict(
                actor="SYNTHETIC TEST OFFICER",
                approved_at="2026-10-17T00:00:00Z",
                approval_reference="SYNTHETIC-APPROVAL-001",
                synthetic_approval=True,
            ),
            contract=dict(
                start_year=2024,
                start_date="2024-01-01",
                base_years=4,
                option_years=2,
                period_basis="exact date",
                currency="SGD",
            ),
            roles=roles,
            assumptions=assumptions,
            evidence=evidence,
            limitations=[
                "Entirely invented development fixture; not a real approved budget.",
                "Full-time headcount quantities and future-price assumptions are synthetic officer selections.",
                "No market validity, legal working-hours standard, roster feasibility or inflation attribution is established.",
                "This interface fixture does not approve or mutate any saved app project.",
            ],
            annual_totals=[
                dict(contract_year=i, amount=value) for i, value in enumerate(result["annual_totals"], 1)
            ],
            base_total=result["base_total"],
            option_total=result["option_total"],
            contract_total=result["contract_total"],
        )
    )


def main():
    example = ROOT / "data/sample/integration/approved_budget.synthetic.json"
    example.parent.mkdir(parents=True, exist_ok=True)
    example.write_text(synthetic_budget().model_dump_json(indent=2) + "\n", encoding="utf-8")
    folder = ROOT / "contracts"
    folder.mkdir(exist_ok=True)
    for name, model in [("approved-budget", BudgetDocument), ("tender-submission", TenderSubmission)]:
        (folder / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
        )
    print(
        "Synthetic integration fixture and two schemas generated. No API, real approval, or database write."
    )


if __name__ == "__main__":
    main()
