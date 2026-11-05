"""Resume checkpoints retain earlier drafts and explicit current deployment."""

import io

import openpyxl
import pytest
from test_proposals import sample

from services.demo import demo_plan
from services.evidence import load_records
from services.headcounts import comparison
from services.hybrid import comparison_rows
from services.proposal_export import comparison_rows as proposal_changes
from services.proposal_intake import load_example, preplanned_sample_bytes, template_bytes
from services.proposal_legacy import pending, prepare, rate_entries, resolve
from services.proposals import capture_original, extract_document, original_signature


def test_existing_example_has_complete_current_and_proposed_headcounts():
    plan = demo_plan()
    totals = comparison(comparison_rows(plan, common=False), existing=True)
    assert plan.contract_kind == "existing contract" and plan.current_deployment_status == "known"
    assert (totals["current"], totals["proposed"], totals["change"]) == (6, 7, 1)
    assert not totals["current_missing"] and not totals["proposed_missing"]
    assert not plan.confirmations and not plan.pending
    p = load_example()
    capture_original(p, p.input_profile, p.input_rows, True)
    assert p.plan.current_deployment_status == "known"
    assert sum(r.current_quantity for r in p.plan.roles) == 6
    assert not p.plan.confirmations


def test_normal_preplanned_budget_sample_uploads_and_defers_future_assumptions():
    from services.proposals import Proposal

    doc = extract_document("preplanned-sample.xlsx", preplanned_sample_bytes())
    p = Proposal()
    capture_original(p, doc["profile"], doc["rows"], True)
    assert p.plan.contract_kind == "existing contract"
    assert sum(r.current_quantity for r in p.plan.roles) == 7
    assert sum(r.quantity for r in p.plan.roles) == 8
    assert sum(r.quantity * r.rate for r in p.plan.roles) == 35500
    assert {tuple(r.escalation) for r in p.plan.roles} == {()}
    assert not doc["assumptions"]
    assert {r.label for r in p.plan.roles} == {
        "Facilities Manager",
        "Admin Executive",
        "Technician",
        "Cleaner",
    }
    assert not p.plan.confirmations and not p.plan.pending and not p.plan.decisions


@pytest.mark.parametrize("accept", [True, False])
def test_saved_rate_and_annual_edits_remain_pending_until_explicit_choice(accept):
    p = sample()
    original = original_signature(p)
    role = p.plan.roles[0]
    key = f"proposal_rate_{p.id}_{role.id}_2_exact"
    p.drafts["controls"] = {
        key: 8500,
        key.removesuffix("_exact") + "_reason": "Retained officer quotation assumption",
        "proposal_shared_percent_" + p.id: 3,
        "proposal_shared_note_" + p.id: "Retained renewal allowance",
    }
    prepare(p)
    assert pending(p) and rate_entries(p)[0]["Saved pending rate"] == 8500
    assert role.rate == 8000 and role.escalation == [0, 0]
    resolve(p, load_records(), "Test officer", apply=accept)
    assert not pending(p)
    assert p.plan.roles[0].rate == (8500 if accept else 8000)
    assert p.plan.roles[0].escalation == ([0, 0.03] if accept else [0, 0])
    assert original_signature(p) == original
    assert not p.plan.confirmations
    changes = proposal_changes(p, load_records())[0]
    assert changes["Original yearly increases (%)"] == "0, 0"
    assert changes["Reviewed yearly increases (%)"] == ("0, 3" if accept else "0, 0")


def test_generic_xlsx_keeps_real_row_location_and_template_requires_headers():
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Staff"
    sheet.append(["Existing-site quotation"])
    sheet.append([])
    sheet.append(["Role", "Proposed quantity", "Unit", "Monthly unit rate (SGD)", "Current quantity"])
    sheet.append(["Technician", 5, "headcount", 4000, 4])
    data = io.BytesIO()
    book.save(data)
    doc = extract_document("other-layout.xlsx", data.getvalue())
    assert doc["rows"][0]["Quantity"] == 5
    assert doc["rows"][0]["Current quantity"] == 4
    assert "4" in doc["rows"][0]["Source location"]
    book = openpyxl.load_workbook(io.BytesIO(template_bytes(True)))
    book["Proposed manpower"]["D4"] = "Salary"
    data = io.BytesIO()
    book.save(data)
    with pytest.raises(ValueError, match="missing columns.*Monthly unit rate"):
        extract_document("broken-template.xlsx", data.getvalue())
