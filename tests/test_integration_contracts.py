"""Synthetic handoff contracts: strict status, units, references and reconciled money."""

import json
from pathlib import Path

import pytest

from scripts.audit_shareable import issues_for
from scripts.build_integration_example import synthetic_budget
from services.calculations import budget
from services.demo import demo_plan
from services.evidence import load_records
from services.integration_contracts import BudgetDocument, TenderSubmission

ROOT = Path(__file__).resolve().parents[1]


def payload():
    return json.loads(
        (ROOT / "data/sample/integration/approved_budget.synthetic.json").read_text(encoding="utf-8")
    )


def test_example_and_schemas_are_current_and_match_python_budget():
    example = BudgetDocument.model_validate(payload())
    assert example == synthetic_budget()
    result = budget(demo_plan(), load_records())
    assert example.contract_total == result["contract_total"]
    assert example.base_total == result["base_total"] and example.option_total == result["option_total"]
    assert example.synthetic and example.approval.synthetic_approval and example.status == "approved"
    for name, model in [("approved-budget", BudgetDocument), ("tender-submission", TenderSubmission)]:
        saved = json.loads((ROOT / f"contracts/{name}.schema.json").read_text())
        assert saved == model.model_json_schema()


@pytest.mark.parametrize(
    "change", ["total", "annual", "currency", "unit", "approval", "reference", "period", "duplicate"]
)
def test_inconsistent_transfer_documents_are_rejected(change):
    data = payload()
    if change == "total":
        data["contract_total"] += 1
    elif change == "annual":
        data["roles"][0]["years"][0]["annual_cost"] += 1
    elif change == "currency":
        data["contract"]["currency"] = "USD"
    elif change == "unit":
        data["roles"][0]["quantity_unit"] = "posts"
    elif change == "approval":
        data["approval"] = None
    elif change == "reference":
        data["roles"][0]["evidence_refs"] = ["unavailable"]
    elif change == "period":
        data["roles"][0]["years"][0]["period_start"] = "2024-02-01"
    else:
        data["roles"][1]["role_id"] = data["roles"][0]["role_id"]
    with pytest.raises(ValueError):
        BudgetDocument.model_validate(data)


def test_draft_budget_and_submitted_tender_are_not_approved_budgets():
    data = payload()
    data.update(status="draft", approval=None)
    assert BudgetDocument.model_validate(data).approval is None
    for key in ["document_type", "budget_id", "source_plan_id", "source_plan_version", "approval"]:
        data.pop(key)
    data.update(
        document_type="tender_submission",
        submission_id="SYNTHETIC-SUB-001",
        tender_id="SYNTHETIC-TENDER-001",
        tenderer_id="SYNTHETIC-TENDERER-A",
        budget_id="SYNTHETIC-BUDGET-001",
        budget_revision=1,
        status="submitted",
        submitted_at="2026-10-17T01:00:00Z",
    )
    tender = TenderSubmission.model_validate(data)
    assert tender.document_type == "tender_submission" and tender.status == "submitted"
    with pytest.raises(ValueError):
        BudgetDocument.model_validate(data)
    data["status"] = "approved"
    with pytest.raises(ValueError):
        TenderSubmission.model_validate(data)


def test_shareable_audit_detects_risks_without_echoing_contents():
    credential = ("sk-" + "z" * 48).encode()
    assert "credential-shaped value" in issues_for("services/example.py", credential)
    assert "outside reviewed shareable file categories" in issues_for(".env", credential)
    assert "private identifier or local path" in issues_for(
        "docs/example.md", b"C:" + b"/" + b"Users/" + b"Example/private"
    )
    assert "dataset lacks explicit synthetic provenance" in issues_for(
        "data/sample/unreviewed.json", b'{"synthetic":false}'
    )
    assert not issues_for(".env.example", b"OPENAI_API_KEY=\nOPENAI_MODEL=\n")
