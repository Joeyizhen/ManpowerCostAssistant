"""Synthetic regression checks for the compiled manpower decision; no paid calls."""

from datetime import date
from io import BytesIO

import openpyxl
import pytest

from services.calculations import budget
from services.demo import demo_plan
from services.evidence import load_records, map_role, rate_benchmark
from services.export import export_excel
from services.journey import accept_review, prepare_review, update_notes, working_draft
from services.models import Plan, PolicyAdjustment
from services.workflow import apply_change, findings


def supplied_brief():
    example = demo_plan()
    p = Plan()
    profile = example.profile.model_dump(mode="json")
    profile.update(start=None, start_year=2024, operating_hours=None, assets=None, locations=None)
    roles = [r.model_dump(mode="json") for r in example.roles]
    for r in roles:
        r.update(experience="", qualifications="")
    update_notes(
        p, profile=profile, responsibilities=[d.model_dump() for d in example.responsibilities], roles=roles
    )
    return p


def test_one_manpower_decision_from_full_brief_without_optional_fields():
    p, records = supplied_brief(), load_records()
    assert not p.roles and not p.confirmations and not p.pending
    result = prepare_review(p, "manpower", records)
    assert result["ready"]
    assert not any(f["code"] == "requirements" for f in result["findings"])
    assert accept_review(p, "Synthetic officer", records) == 4
    assert set(p.confirmations) == {"profile", "responsibilities", "quantities", "plan"}
    assert p.roles and p.profile.start is None and p.profile.start_year == 2024
    assert "rates" not in p.confirmations and "final" not in p.confirmations


def test_requirements_only_review_preserves_roles_and_revision():
    p, records = supplied_brief(), load_records()
    original = {r.id: r.quantity for r in working_draft(p).roles}
    assert prepare_review(p, "requirements", records)["ready"]
    accept_review(p, "Synthetic officer", records)
    assert {r.id: r.quantity for r in working_draft(p).roles} == original
    role = working_draft(p).roles[0].model_dump(mode="json")
    update_notes(
        p,
        roles=[
            {
                **role,
                "quantity": 2,
                "quantity_reason": "Two officers cover separate occupied buildings during the overlapping daytime shift",
            }
        ],
    )
    assert len(working_draft(p).roles) == len(original)
    assert next(r.quantity for r in working_draft(p).roles if r.id == role["id"]) == 2
    assert prepare_review(p, "manpower", records)["ready"]
    accept_review(p, "Synthetic officer", records)
    assert next(r.quantity for r in p.roles if r.id == role["id"]) == 2


def test_manual_profile_edit_keeps_other_conversational_drafts():
    p = supplied_brief()
    original = working_draft(p)
    apply_change(
        p,
        "profile",
        {**original.profile.model_dump(mode="json"), "description": "Officer corrected description"},
        "Correction",
        "Synthetic officer",
    )
    assert working_draft(p).roles == original.roles
    assert working_draft(p).responsibilities == original.responsibilities
    assert working_draft(p).profile.description == "Officer corrected description"


def test_missing_quantity_is_precise_and_never_a_qualification_gate():
    p = supplied_brief()
    r = working_draft(p).roles[0].model_dump(mode="json")
    update_notes(p, roles=[{**r, "quantity": None}])
    result = prepare_review(p, "manpower", load_records())
    assert not result["ready"] and not p.pending
    assert any(r["label"] in x and "quantity" in x for x in result["missing_inputs"])
    assert not any("experience" in x or "qualification" in x for x in result["missing_inputs"])


def test_seniority_and_combined_title_preserved_without_invented_rate():
    p = supplied_brief()
    r = working_draft(p).roles[0].model_dump(mode="json")
    title = "Senior Property Executive cum FSM"
    assert map_role(title) is None
    update_notes(
        p,
        roles=[
            {
                **r,
                "label": title,
                "mapped_role": None,
                "mapping_reason": "",
                "rate_origin": "Officer assumption",
                "rate_reason": "Synthetic contractor quotation covers the combined senior supervisory duties for this allowance",
            }
        ],
    )
    records = load_records()
    assert not rate_benchmark(records, None)["available"]
    assert prepare_review(p, "manpower", records)["ready"]
    accept_review(p, "Synthetic officer", records)
    assert any(r.label == title and r.mapped_role is None for r in p.roles)
    assert prepare_review(p, "rates", records)["ready"]
    accept_review(p, "Synthetic officer", records)
    assert prepare_review(p, "escalation", records)["ready"]
    accept_review(p, "Synthetic officer", records)
    result = budget(p, records)
    assert result["base_total"] + result["option_total"] == result["contract_total"]
    workbook = openpyxl.load_workbook(BytesIO(export_excel(p, records)))
    assert any(title in str(c.value) for row in workbook["Manpower plan"] for c in row)
    assert not any(f.code == "requirements" for f in findings(p, records))


def test_start_year_only_costing_discloses_boundary_and_keeps_exact_date_unknown():
    p, records = demo_plan(), load_records()
    expected = budget(p, records)
    p.profile.start_year = p.profile.start.year
    p.profile.start = None
    actual = budget(p, records)
    assert actual["annual_totals"] == expected["annual_totals"]
    assert p.profile.start is None
    assert "illustrative" in actual["period_basis"]
    p.roles[0].policies = [
        PolicyAdjustment(
            name="Synthetic policy",
            effective_date=date(2025, 1, 1),
            annual_monthly_increment=50,
            affected_component="component",
            source="Synthetic",
            overlap_reviewed=True,
            basis_confirmed=True,
        )
    ]
    with pytest.raises(ValueError, match="exact contract start"):
        budget(p, records)
    p.roles[0].policies = []
    p.roles[0].escalation_mode = "quoted schedule"
    with pytest.raises(ValueError, match="1 January"):
        budget(p, records)


def test_unavailable_rates_cannot_be_confirmed_as_synthetic_benchmarks():
    from services.workflow import missing_for_gate

    p = demo_plan()
    p.roles[0].mapped_role = None
    assert any("explicit officer assumption" in x for x in missing_for_gate(p, "rates", load_records()))
    p.roles[0].rate_origin = "Officer assumption"
    assert not missing_for_gate(p, "rates", load_records())
