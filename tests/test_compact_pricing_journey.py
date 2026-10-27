"""Compact deployment/pricing and final handover checks. All inputs are synthetic."""

from io import BytesIO

import openpyxl
from test_grouped_future_journey import ready_plan
from test_ui import blank, button, fill_table

from services.calculations import preliminary
from services.decision_basis import retained_basis
from services.evidence import load_records, rate_benchmark
from services.export import export_excel
from services.pricing import pricing_proposal, starting_overview


def test_monthly_annual_overview_discloses_fte_rounding_without_changing_calculation():
    p = ready_plan()
    p.roles = [p.roles[0]]
    p.roles[0].quantity = 2.5
    p.roles[0].quantity_unit = "FTE"
    p.roles[0].rate = 4060.21
    original = preliminary(p)
    shown = starting_overview(p)
    assert shown["monthly"] == 10150.53
    assert shown["display_annual"] == 121806.36
    assert shown["year_1"] == original["year_1"] == 121806.30
    assert shown["annual_rounding_difference"] == -0.06


def prices(monkeypatch, tmp_path):
    at = fill_table(blank(monkeypatch, tmp_path), ["Facility Manager", "Technician"], [1, 0.5])
    at.button(key="use_manpower_plan").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 3
    return at


def controls(at, title="Technician"):
    p = at.session_state["plan"]
    role = next(r for r in p.roles if r.label == title)
    return p, role, f"rate_{p.id}_{role.id}_{role.benchmark_year}"


def test_recommended_rates_are_unconfirmed_and_sources_attach_automatically(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    p, role, key = controls(at)
    bm = rate_benchmark(load_records(), role.mapped_role, 2028)
    assert role.rate == round(bm["average"], 2)
    assert not any((x.key or "").startswith("basis_") and "_record" in x.key for x in at.button)
    assert "rates" not in p.confirmations
    assert not at.button(key="confirm_rates").disabled
    at.button(key="confirm_rates").click().run()
    p = at.session_state["plan"]
    assert not at.exception and p.ui_step == 4
    for role in p.roles:
        if role.included:
            basis = retained_basis(p, role, "rate")
            assert basis and basis.snapshots[role.id]["reference_records"]
            assert basis.classification == "sourced evidence"


def test_range_exact_input_and_fte_totals_update_together(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    p, role, key = controls(at)
    bm = rate_benchmark(load_records(), role.mapped_role, 2028)
    selected = round(bm["minimum"] + 100, 2)
    at.slider(key=key + "_slider").set_value(selected).run()
    p, role, key = controls(at)
    assert role.rate == selected and at.number_input(key=key + "_number").value == selected
    assert role.quantity == 0.5 and role.quantity_unit == "FTE"
    assert "Monthly rate per FTE" in at.number_input(key=key + "_number").label
    assert not at.button(key="confirm_rates").disabled
    assert not any(x.key == key + "_rationale" for x in at.text_area)
    result = preliminary(at.session_state["plan"])
    assert next(r for r in result["rows"] if r["role"] == "Technician")["monthly"] == round(selected * 0.5, 2)
    assert not at.button(key="confirm_rates").disabled
    second = round(selected + 50, 2)
    at.number_input(key=key + "_number").set_value(second).run()
    assert at.slider(key=key + "_slider").value == second
    assert not any(x.key == key + "_rationale" for x in at.text_area)


def test_outside_rate_is_explicit_and_reason_survives_save_resume(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    p, role, key = controls(at, "Facility Manager")
    bm = rate_benchmark(load_records(), role.mapped_role, 2028)
    at.checkbox(key=key + "_custom").check().run()
    at.number_input(key=key + "_number").set_value(round(bm["maximum"] + 100, 2)).run()
    at.text_area(key=key + "_rationale").set_value("Contractor mobilisation quotation").run()
    at.text_input(key=key + "_source").set_value("Synthetic quote Q1").run()
    button(at, "Save project").click().run()
    button(at, "Resume selected project").click().run()
    assert not at.exception and not at.error
    assert at.text_area(key=key + "_rationale").value == "Contractor mobilisation quotation"
    assert at.text_input(key=key + "_source").value == "Synthetic quote Q1"
    at.button(key="confirm_rates").click().run()
    p = at.session_state["plan"]
    role = next(r for r in p.roles if r.label == "Facility Manager")
    assert retained_basis(p, role, "rate").snapshots[role.id]["quotation_reference"] == "Synthetic quote Q1"


def test_reference_year_treatment_is_shared_once_and_retained(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    next(x for x in at.selectbox if x.label == "Reference pricing year").set_value(2024).run()
    p = at.session_state["plan"]
    assert len([x for x in at.text_area if x.label == "Reference-year treatment"]) == 1
    at.text_area(key=f"pricing_year_{p.id}_text").set_value(
        "Retain reference-year charges as a disclosed budget assumption"
    ).run()
    assert not at.button(key="confirm_rates").disabled
    at.button(key="confirm_rates").click().run()
    p = at.session_state["plan"]
    assert p.ui_step == 4 and not at.exception
    for role in p.roles:
        if role.included:
            assert (
                retained_basis(p, role, "rate")
                .snapshots[role.id]["year_treatment"]
                .startswith("Retain reference-year")
            )


def test_edit_deployment_keeps_rates_until_actual_change_then_invalidates(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    p, role, key = controls(at)
    rate = role.rate
    at.button(key="pricing_edit_deployment").click().run()
    assert at.session_state["plan"].ui_step == 1
    assert next(r for r in at.session_state["plan"].roles if r.id == role.id).rate == rate
    assert any(x.label == "Proposed headcount" for x in at.metric)
    assert any(x.label == "Proposed FTE" for x in at.metric)


def test_pricing_proposal_unknown_and_meaningful_custom_without_reference():
    p = ready_plan()
    role = p.roles[0]
    role.mapped_role = None
    role.rate_reason = "higher rate"
    p.decision_bases = []
    q, errors = pricing_proposal(p, [], "Synthetic officer")
    assert errors and "briefly explain where this allowance comes from" in errors[0]
    role.rate_reason = "Contractor renewal quotation"
    q, errors = pricing_proposal(p, [], "Synthetic officer")
    assert not errors
    basis = retained_basis(q, q.roles[0], "rate")
    assert basis.classification == "officer assumption" and not basis.snapshots[role.id]["reference_records"]


def test_confirmed_and_draft_exports_keep_repeated_titles_and_fte():
    p = ready_plan()
    p.roles.append(p.roles[0].model_copy(update={"id": "annex-fm", "quantity": 0.5, "quantity_unit": "FTE"}))
    q, errors = pricing_proposal(p, load_records(), "Synthetic officer")
    assert not errors
    workbook = openpyxl.load_workbook(BytesIO(export_excel(q, load_records())), data_only=True)
    assert any("annex-fm" in row for row in workbook["Budget summary"].values)
    assert preliminary(q)["monthly"] == 12000


def test_unchanged_draft_rationale_is_recorded_once_and_unknown_current_stays_unknown():
    from journey_inputs import commit_rows
    from services.hybrid import comparison_rows
    from services.journey import working_draft
    from services.models import Plan, Profile

    p = Plan(
        contract_kind="existing contract",
        current_deployment_status="known",
        profile=Profile(start_year=2028, base_years=2, option_years=0),
    )
    rows = comparison_rows(p)
    for i, row in enumerate(rows):
        row.update(
            {
                "Proposed quantity / FTE": 2 if i == 0 else 0,
                "Current quantity / FTE": None,
                "Quantity basis": "headcount",
                "Duties / deployment notes": "Two buildings require dedicated supervision" if i == 0 else "",
            }
        )
    commit_rows(p, rows)
    version, count = p.version, len(p.decision_bases)
    commit_rows(p, comparison_rows(p))
    assert p.version == version and len(p.decision_bases) == count == 1
    assert working_draft(p).roles[0].current_quantity is None
