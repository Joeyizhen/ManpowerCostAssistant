"""Officer-facing six-step decisions; all data invented, model calls forbidden/mocked."""

from datetime import date

import pytest
from test_ui import blank, seed_retained_role

from services.calculations import budget
from services.deployment_review import accept_suggestions, officer_draft, retain_assistant_proposals
from services.evidence import load_records
from services.final_review import annual_breakdown, review_state, sensitivity_rows
from services.journey import update_notes, working_draft
from services.models import Plan, Profile, Role
from services.scenario_selection import adopt_scenario


def by_label(elements, label):
    return next(x for x in elements if x.label == label)


def populate(at):
    by_label(at.text_input, "Project name").set_value("Synthetic officer journey").run()
    by_label(
        at.text_area, "Describe the properties and operating conditions the FM team will manage"
    ).set_value("Two office buildings require weekday reception and equipment response").run()
    for label, value in [
        ("Anticipated start month", "Jan 2028"),
        ("Base term (years)", "2"),
        ("Option term (years)", "1"),
    ]:
        by_label(at.text_input, label).set_value(value).run()
    at.button(key="six_continue").click().run()
    by_label(at.radio, "Deployment context").set_value("New site / service").run()
    assert not at.dataframe
    for title in ["Facility Manager", "Technician"]:
        picker = by_label(at.selectbox, "Add another role")
        if title in picker.options:
            picker.set_value(title).run()
            at.button(key="add_selected_roles").click().run()
        else:
            seed_retained_role(at, title)
    key = at.session_state["six_editor_key"]
    at.session_state[key] = {
        "edited_rows": {
            i: {
                "Proposed quantity / FTE": i + 1,
                "Duties / deployment notes": "Dedicated weekday response team for two office buildings",
            }
            for i in range(2)
        },
        "added_rows": [],
        "deleted_rows": [],
    }
    at.run()
    at.run()  # manual editor metadata needs a rendered callback-equivalent pass
    assert not at.exception and at.session_state["plan"].ui_step == 1
    return at


def test_attempted_validation_and_two_action_checkpoint(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    assert not any("To continue:" in x.value for x in at.info)
    assert not at.button(key="six_continue").disabled
    at.button(key="six_continue").click().run()
    assert at.session_state["plan"].ui_step == 0
    assert any("To continue:" in x.value for x in at.info)
    assert not at.date_input
    populate(at)
    labels = {x.label for x in at.button}
    assert {
        "Confirm and continue",
        "Discuss deployment with AI",
    } <= labels
    assert not {"Review plan", "Discuss changes", "Use this plan", "Edit deployment"} & labels
    assert len(working_draft(at.session_state["plan"]).roles) == 2
    assert not any(x.label == "Discuss changes or ask the assistant" for x in at.expander)
    assert not at.chat_input
    at.button(key="revise_manpower_plan").click().run()
    assert at.chat_input and not at.exception
    assert at.session_state["plan"].ui_step == 1 and not at.session_state["plan"].confirmations


def test_non_pwm_full_journey_direct_rates_compounding_and_reopen(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    at.default_timeout = 90
    populate(at)
    at.button(key="use_manpower_plan").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 3
    assert not any(x.label in ("Use another rate", "Use another percentage") for x in at.checkbox)
    assert not any(x.label == "Edit basis / custom rate" for x in at.expander)
    p = at.session_state["plan"]
    role = p.roles[0]
    key = f"rate_{p.id}_{role.id}_{role.benchmark_year}_number"
    at.number_input(key=key).set_value(12345.67).run()
    reason = next(x for x in at.text_area if x.label.startswith("Short pricing reason"))
    reason.set_value("Synthetic supplier quotation Q7 for the inclusive deployment charge").run()
    # Retain any legacy reference-year alignment explicitly.
    note = next((x for x in at.text_area if x.label == "Reference-year treatment"), None)
    if note:
        note.set_value("Retain the quoted starting allowances without automatic inflation").run()
    at.button(key="confirm_rates").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 4
    p = at.session_state["plan"]
    percent_key = f"common_future_{p.id}_percent"
    assert at.number_input(key=percent_key).value is not None
    at.number_input(key=percent_key).set_value(2.5).run()
    assert not any(x.label == "Use another percentage" for x in at.checkbox)
    at.button(key="confirm_escalation").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 5
    p = at.session_state["plan"]
    result = budget(p, load_records())
    rows, changes = annual_breakdown(p, result)
    assert sum(r["Total annual manpower cost"] for r in rows) == pytest.approx(result["contract_total"])
    assert all(r.escalation == [0, 0.025, 0.025] for r in p.roles if r.included)
    assert {x.label for x in at.tabs} == {"Budget", "Scenarios", "Manpower", "Assumptions & sources"}
    original = p.model_dump(mode="json")
    sensitivity_rows(p, load_records())
    assert p.model_dump(mode="json") == original
    by_label(at.button, "Save draft").click().run()
    saved = p.model_copy(deep=True)
    at.session_state["plan"] = Plan.model_validate_json(saved.model_dump_json())
    at.run()
    assert not at.exception
    assert budget(at.session_state["plan"], load_records())["contract_total"] == result["contract_total"]


def test_assistant_changes_only_after_acceptance_and_stays_at_checkpoint():
    p = Plan(
        profile=Profile(description="Office", start=date(2028, 1, 1), base_years=2, option_years=0), ui_step=2
    )
    update_notes(
        p,
        roles=[
            Role(id="fm", label="Facility Manager", quantity=1, quantity_unit="headcount").model_dump(
                mode="json"
            )
        ],
    )
    before = p.model_copy(deep=True)
    suggested = (
        officer_draft(p)
        .roles[0]
        .model_copy(update={"quantity": 3, "quantity_reason": "Dedicated response cover for two buildings"})
    )
    update_notes(p, roles=[suggested.model_dump(mode="json")])
    retain_assistant_proposals(p, before)
    assert officer_draft(p).roles[0].quantity == 1 and working_draft(p).roles[0].quantity == 3
    assert p.pending[0]["reason"] == "Dedicated response cover for two buildings"
    accept_suggestions(p, "Test officer")
    assert p.roles[0].quantity == 3 and p.ui_step == 1 and not p.confirmations


def test_pwm_baseline_reconciles_and_scenarios_do_not_change_salary_component():
    from test_budget_basis_pwm import pwm_plan

    p = pwm_plan()
    result = budget(p, load_records())
    rows, changes = annual_breakdown(p, result)
    for row in rows:
        assert sum(
            row[k]
            for k in [
                "Starting-rate manpower cost",
                "Compounded annual manpower increase",
                "PWM increase",
                "Other adjustments",
            ]
        ) == pytest.approx(row["Total annual manpower cost"])
    original_pwm = p.roles[0].pwm.model_dump(mode="json")
    p.working_notes = {}
    adopt_scenario(p, 0.01, "Test officer", load_records())
    assert p.roles[0].pwm.model_dump(mode="json") == original_pwm
    assert "escalation" not in p.confirmations and "final" not in p.confirmations


def test_plain_benchmark_difference_not_an_outstanding_decision():
    from test_grouped_future_journey import ready_plan

    p = ready_plan()
    p.roles[0].rate = 99999
    p.roles[0].rate_reason = "Supplier quotation Q100 for dedicated response cover"
    state = review_state(p, load_records())
    ordinary = {f.id for f in state["findings"] if f.code == "rate_range"}
    assert not any(set(a["findings"]) & ordinary for a in state["actions"])


def test_shared_reason_draft_survives_save_and_reopen_without_confirmation(monkeypatch, tmp_path):
    at = populate(blank(monkeypatch, tmp_path))
    p = at.session_state["plan"]
    p.basis_drafts["deployment_reason"] = {
        "roles": [r.id for r in working_draft(p).roles if r.included],
        "reason": "Rotating response cover for two office buildings",
    }
    at.run()
    by_label(at.button, "Save draft").click().run()
    by_label(at.button, "Resume selected project").click().run()
    assert not at.exception
    assert (
        at.session_state["plan"].basis_drafts["deployment_reason"]["reason"]
        == "Rotating response cover for two office buildings"
    )
    assert not at.session_state["plan"].confirmations
    assert not any(e.label == "One operational reason covers related roles" for e in at.expander)
    assert not any(t.label == "Shared operational reason" for t in at.text_area)
    assert not at.button(key="use_manpower_plan").disabled


def test_mixed_headcount_and_fte_are_not_summed_for_shared_numerical_claims():
    from services.decision_basis import record_basis
    from services.manpower_checks import shared_basis_mismatches

    p = Plan(
        contract_kind="new site / service",
        roles=[
            Role(id="a", label="Response officer", quantity=1, quantity_unit="headcount"),
            Role(id="b", label="Shared administrator", quantity=0.5, quantity_unit="FTE"),
        ],
    )
    record_basis(
        p,
        "quantity",
        ["a", "b"],
        "Operational reason",
        "Two additional buildings require two officers each",
        "Officer input",
        "officer assumption",
        "Test officer",
    )
    assert not shared_basis_mismatches(p)


def test_editing_a_recorded_pricing_reason_preserves_amount_and_updates_basis(monkeypatch):
    from test_grouped_future_journey import ready_plan

    import pricing_inputs
    from services.decision_basis import retained_basis
    from services.pricing import pricing_proposal

    p, errors = pricing_proposal(ready_plan(), load_records(), "Test officer")
    assert not errors
    role = p.roles[0]
    original_amount = role.rate
    assert retained_basis(p, role, "rate")

    class State(dict):
        __getattr__ = dict.__getitem__

    updated = "Supplier quotation Q9 confirms the retained monthly allowance for dedicated response cover"
    monkeypatch.setattr(
        pricing_inputs.st, "session_state", State(plan=p, officer="Test officer", revised_reason=updated)
    )
    pricing_inputs.rate_changed(role.id, "rate_reason", "revised_reason")
    revised, errors = pricing_proposal(p, load_records(), "Test officer")
    assert not errors
    assert revised.roles[0].rate == original_amount
    assert retained_basis(revised, revised.roles[0], "rate").explanation == updated
    assert "rates" not in p.confirmations


def test_reconfirming_unchanged_deployment_retains_valid_later_confirmations():
    from test_grouped_future_journey import ready_plan

    from services.journey import accept_review, prepare_review
    from services.workflow import confirm

    p = ready_plan()
    for gate in ["escalation", "validation", "final"]:
        confirm(p, gate, "Test officer", load_records())
    before = p.confirmations.copy()
    amounts = budget(p, load_records())
    assert prepare_review(p, "manpower", load_records())["ready"]
    accept_review(p, "Test officer", load_records())
    assert p.confirmations == before
    assert budget(p, load_records()) == amounts


def test_unchanged_future_selection_keeps_recorded_reason_and_source():
    from test_grouped_future_journey import ready_plan

    from services.future_groups import general_proposal

    p = general_proposal(
        ready_plan(), load_records(), ["fm"], 2.5, "Supplier renewal forecast Q9", "Q9", False, "Test officer"
    )
    before = p.model_dump(mode="json")
    # Even if this number lies in a newly displayed reference band, it remains
    # the officer's recorded assumption until they change values or context.
    same = general_proposal(p, load_records(), ["fm"], 2.5, "", "", True, "Test officer")
    assert same.model_dump(mode="json") == before


def test_distinct_saved_constant_increases_require_explicit_replacement(monkeypatch, tmp_path):
    from test_grouped_future_journey import ready_plan
    from test_ui import blank

    p = ready_plan()
    original = p.roles[0]
    original.escalation = [0] + [0.02] * (p.profile.years - 1)
    p.roles.append(
        original.model_copy(
            update={"id": "annex", "label": "Annex FM", "escalation": [0] + [0.03] * (p.profile.years - 1)}
        )
    )
    before = [r.escalation[:] for r in p.roles]
    at = blank(monkeypatch, tmp_path)
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert by_label(at.checkbox, "Keep saved yearly profiles and special arrangements").value
    assert not any(x.label == "Selected annual manpower cost increase (%)" for x in at.number_input)
    assert [r.escalation for r in at.session_state["plan"].roles] == before
