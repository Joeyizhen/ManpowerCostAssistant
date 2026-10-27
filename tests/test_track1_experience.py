"""Synthetic checks for officer-facing refinements; no provider calls."""

from datetime import date
from io import BytesIO

import openpyxl
import pytest

from hybrid_inputs import confirmation_errors
from journey_inputs import parse_start, role_options, validate_manpower
from services.calculations import budget
from services.demo import demo_plan
from services.evidence import load_records
from services.export import export_excel
from services.hybrid import comparison_rows, save_input_table
from services.journey import accept_review, prepare_review, working_draft
from services.models import Plan, PolicyAdjustment, Profile


@pytest.mark.parametrize(
    "text, expected",
    [("Sep 2028", (2028, 9)), (" jan 2028 ", (2028, 1)), ("2028", (2028, None)), ("", (None, None))],
)
def test_anticipated_month_parsing_preserves_precision(text, expected):
    assert parse_start(text) == expected


@pytest.mark.parametrize("text", ["September 2028", "13 2028", "Jan 28", "Jan 2201", "foo"])
def test_bad_anticipated_start_has_actionable_error(text):
    with pytest.raises(ValueError, match="MMM YYYY|1900"):
        parse_start(text)


def test_month_only_costing_and_export_never_claim_an_exact_date():
    p = demo_plan()
    p.profile.start, p.profile.start_year, p.profile.start_month = None, 2024, 9
    result = budget(p, load_records())
    assert p.profile.costing_start == date(2024, 9, 1) and p.profile.start is None
    assert result["rows"][0]["period_start"] == "2024-09-01"
    assert "illustrative" in result["period_basis"] and "exact" in result["period_basis"]
    old = Profile.model_validate({"start_year": 2024, "base_years": 4, "option_years": 2})
    assert old.start_month is None and old.costing_start == date(2024, 1, 1)
    workbook = openpyxl.load_workbook(BytesIO(export_excel(p, load_records())), data_only=True)
    assert any(
        "2024-09 (anticipated month" in str(cell.value) for row in workbook["Budget summary"] for cell in row
    )
    p.roles[0].policies = [
        PolicyAdjustment(
            name="Synthetic component",
            effective_date=date(2025, 1, 1),
            annual_monthly_increment=10,
            affected_component="Synthetic component only",
            source="Synthetic source",
            basis_confirmed=True,
            overlap_reviewed=True,
        )
    ]
    with pytest.raises(ValueError, match="exact contract start"):
        budget(p, load_records())
    p.roles[0].policies = []
    p.roles[0].escalation_mode = "quoted schedule"
    with pytest.raises(ValueError, match="1 January contract start"):
        budget(p, load_records())


def test_role_picker_filters_added_titles_and_supported_aliases_without_merging_seniority():
    p = Plan()
    choices = role_options(p, "Browse all roles")
    assert "Facility Manager" not in choices and "Facilities Manager" not in choices
    assert "Technician" not in choices
    assert "Senior Facilities Manager" in choices
    assert any("cum" in x.casefold() for x in choices)
    assert len({x.casefold() for x in choices}) == len(choices)


def test_changed_current_quantity_needs_a_reason_and_fractional_basis_is_explicit():
    p = Plan(contract_kind="existing contract", current_deployment_status="known")
    rows = comparison_rows(p)
    for r in rows:
        r.update({"Proposed quantity / FTE": 0, "Quantity basis": "headcount"})
    rows[0].update({"Current quantity / FTE": 2, "Proposed quantity / FTE": 1})
    save_input_table(p, "Synthetic office description", 2028, 3, 3, rows)
    validate_manpower(p)  # Missing change remarks are advisory, not invalid arithmetic.
    from services.workflow import findings

    assert any(f.code == "change_reason" and not f.blocking for f in findings(working_draft(p), []))
    rows[0]["Duties / deployment notes"] = "Synthetic shared supervision reduces this role"
    rows[0]["Proposed quantity / FTE"] = 0.5
    save_input_table(p, "Synthetic office description", 2028, 3, 3, rows)
    with pytest.raises(ValueError, match="fractional allocation"):
        validate_manpower(p)
    rows[0]["Quantity basis"] = "FTE"
    save_input_table(p, "Synthetic office description", 2028, 3, 3, rows)
    validate_manpower(p)
    assert working_draft(p).roles[0].quantity_unit == "FTE"


def test_readiness_is_read_only_and_lists_officer_and_affected_role():
    p, records = demo_plan(), load_records()
    assert prepare_review(p, "manpower", records)["ready"]
    accept_review(p, "Synthetic officer", records)
    p.roles[-1].rate = None
    before = p.model_dump_json()
    errors = confirmation_errors(p, "", records, checkpoint="rates")
    assert not any("officer" in e for e in errors)
    assert any("Events Manager" in e for e in errors)
    assert p.model_dump_json() == before


def test_advisory_scope_review_retains_valid_draft_and_survives_confirmation():
    from services.journey import record_draft_decision, update_notes
    from services.workflow import findings

    p = demo_plan()
    records = load_records()
    update_notes(p, roles=[{**p.roles[0].model_dump(), "responsibility_ids": []}])
    original = working_draft(p).roles[0].quantity
    advice = next(f for f in findings(working_draft(p), records) if f.code == "role_scope")
    record_draft_decision(
        p,
        advice.id,
        "unresolved risk",
        "Synthetic officer retains the quantity; duty allocation remains uncertain",
        "Synthetic officer",
        records,
    )
    assert not p.confirmations and working_draft(p).roles[0].quantity == original
    assert prepare_review(p, "manpower", records)["ready"]
    accept_review(p, "Synthetic officer", records)
    reviewed = next(f for f in findings(p, records) if f.id == advice.id)
    assert reviewed.officer == "Synthetic officer" and reviewed.status == "unresolved risk"
    assert p.roles[0].quantity == original


def test_acknowledged_uncertainty_allows_qualified_final_without_changing_figures():
    from services.models import GATES
    from services.workflow import confirm, findings, record_decision

    p, records = demo_plan(), load_records()
    quantities = [r.quantity for r in p.roles]
    for gate in GATES:
        if gate == "validation":
            for f in findings(p, records):
                assert not f.blocking
                record_decision(
                    p,
                    f,
                    "unresolved risk",
                    "Synthetic officer acknowledges this uncertainty and retains the plan",
                    "Synthetic officer",
                )
        confirm(p, gate, "Synthetic officer", records)
    confirm(p, "final", "Synthetic officer", records)
    assert [r.quantity for r in p.roles] == quantities
    wb = openpyxl.load_workbook(BytesIO(export_excel(p, records)), data_only=True)
    assert any(
        "acknowledges this uncertainty" in str(cell.value) for sheet in wb for row in sheet for cell in row
    )


@pytest.mark.parametrize(
    "current, proposed, remarks, flagged",
    [
        (2, 2, "additional 4 pax for support", True),
        (2, 6, "additional 4 pax for support", False),
        (2, 2, "", False),
        (None, 6, "additional 4 pax", False),
        (2, 2, "could add 4 pax", False),
        (2, 2, "not adding 4 pax", False),
        (4, 2, "reduce by 2 staff", False),
        (4, 2, "reduce by 1 staff", True),
        (None, 2, "proposed 4 pax", True),
    ],
)
def test_narrow_quantity_claims_only(current, proposed, remarks, flagged):
    from services.manpower_checks import quantity_discrepancy
    from services.models import Role

    role = Role(
        id="synthetic", label="Technician", current_quantity=current, quantity=proposed, duties_notes=remarks
    )
    assert bool(quantity_discrepancy(role)) == flagged


def test_rate_chart_frames_evidence_and_preserves_override():
    from services.evidence import rate_benchmark
    from services.manpower_checks import rate_display_bounds

    bm = rate_benchmark(load_records(), demo_plan().roles[0].mapped_role, 2024)
    bounds = rate_display_bounds(bm["average"], bm)
    assert bounds[0] > 0 and bounds[0] < bm["minimum"] < bm["maximum"] < bounds[1]
    assert rate_display_bounds(25000, bm)[1] > 25000
    assert rate_display_bounds(None, {"available": False}) is None


def test_routine_scope_qualifications_do_not_require_individual_acknowledgement():
    from services.models import GATES
    from services.workflow import confirm, findings, requires_decision

    p, records = demo_plan(), load_records()
    for r in p.roles:
        r.responsibility_ids = []
    fs = findings(p, records)
    assert any(f.code == "role_scope" for f in fs)
    assert all(not requires_decision(f) for f in fs if f.code in {"role_scope", "scenario", "thin_evidence"})
    # Arithmetic stays validated independently; routine qualifications remain visible in export.
    for gate in GATES:
        confirm(p, gate, "Local plan user (name not collected)", records)
    material = [f for f in findings(p, records) if requires_decision(f)]
    if not material:
        confirm(p, "final", "Local plan user (name not collected)", records)
    assert any(f.code == "role_scope" for f in findings(p, records))
