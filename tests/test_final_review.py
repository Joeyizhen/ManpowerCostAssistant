"""Final-review clarity and workflow checks; private saved project is read-only when available."""

from pathlib import Path

import pytest
from test_grouped_future_journey import ready_plan
from test_ui import blank, button

from services.calculations import budget, sensitivity
from services.evidence import load_records
from services.final_review import (
    annual_breakdown,
    deployment_rows,
    rationale_for,
    review_state,
    reviewed,
    sensitivity_rows,
)
from services.journey import accept_review, prepare_review
from services.models import Plan
from services.workflow import apply_change, confirm, findings, record_decision


def final_fixture(mixed=False):
    p = ready_plan(mixed)
    confirm(p, "escalation", "Synthetic officer", load_records())
    p.ui_step = 5
    return p


def test_readiness_and_scenarios_are_read_only_and_match_existing_sensitivity():
    p = final_fixture(True)
    before = p.model_dump_json()
    state = review_state(p, load_records())
    assert state["status"] == "Ready for confirmation" and not state["actions"]
    rows, profiles = sensitivity_rows(p, load_records())
    old = sensitivity(p, load_records())
    assert [r["Full contract budget"] for r in rows] == [r["contract_total"] for r in old]
    assert rows[1]["Difference from selected (SGD)"] == 0
    assert rows[0]["Difference from selected (SGD)"] < 0 < rows[2]["Difference from selected (SGD)"]
    assert len(profiles) == 3 and p.model_dump_json() == before


def test_missing_rate_is_specific_actionable_and_not_false_zero(monkeypatch, tmp_path):
    p = final_fixture()
    p.roles[0].rate = None
    state = review_state(p, load_records())
    assert state["result"] is None and state["status"] == "Needs attention"
    assert any(a["step"] == 3 and any("rate" in m.lower() for m in a["messages"]) for a in state["actions"])
    messages = [m for a in state["actions"] for m in a["messages"]]
    assert len(messages) == len(set(messages))
    at = blank(monkeypatch, tmp_path)
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert not any("Excel evidence workbook" in x.label for x in at.get("download_button"))
    assert button(at, "Confirm full contract budget").disabled
    assert any("Edit rates" == x.label for x in at.button)


def test_accepted_rate_flag_reuses_rationale_and_reopens_only_for_relevant_change():
    p = ready_plan()
    role = p.roles[0]
    payload = role.model_dump(mode="json")
    payload.update(rate=1000, rate_reason="Contractor quotation Q1 covers the stated inclusive scope")
    apply_change(p, "role", payload, "Synthetic price choice", "Synthetic officer")
    assert prepare_review(p, "rates", load_records())["ready"]
    accept_review(p, "Synthetic officer", load_records())
    confirm(p, "escalation", "Synthetic officer", load_records())
    flag = next(f for f in findings(p, load_records()) if f.code == "rate_range")
    assert "quotation Q1" in rationale_for(p, flag)
    record_decision(p, flag, "accepted exception", rationale_for(p, flag), "Synthetic officer")
    state = review_state(p, load_records())
    assert not any(flag.id in a["findings"] for a in state["actions"])
    assert any(f.id == flag.id and reviewed(f) for f in state["findings"])
    payload = p.roles[0].model_dump(mode="json")
    payload["duties_notes"] = "Same pricing; revised operational narrative"
    apply_change(p, "role", payload, "Unrelated narrative", "Synthetic officer")
    assert reviewed(next(f for f in findings(p, load_records()) if f.id == flag.id))
    payload = p.roles[0].model_dump(mode="json")
    payload["rate"] = 1001
    apply_change(p, "role", payload, "Changed price", "Synthetic officer")
    assert not reviewed(next(f for f in findings(p, load_records()) if f.id == flag.id))


def test_annual_components_previous_year_change_and_deployment_contribution_reconcile():
    p = final_fixture(True)
    fm = next(r for r in p.roles if not r.pwm)
    fm.yearly_quantities = [1, 2]
    result = budget(p, load_records())
    rows, changes = annual_breakdown(p, result)
    assert rows[0]["Change from previous year (SGD)"] is None
    assert rows[0]["Change from previous year (%)"] is None
    assert changes[0]["Deployment change at starting rates"] == 96000
    assert rows[1]["Change from previous year (SGD)"] == pytest.approx(
        result["annual_totals"][1] - result["annual_totals"][0]
    )
    for row in rows:
        assert row["Starting-rate manpower cost"] + row["Compounded annual manpower increase"] + row[
            "PWM increase"
        ] + row["Other adjustments"] == pytest.approx(row["Total annual manpower cost"])
    assert sum(row["Total annual manpower cost"] for row in rows) == pytest.approx(result["contract_total"])


def test_variable_scenarios_and_all_pwm_explanation_do_not_touch_fixed_costs():
    p = final_fixture(True)
    p.profile.option_years = 2
    fm = next(r for r in p.roles if not r.pwm)
    fm.escalation = [0, 0.02, 0.04]
    p.roles = [fm]
    before = p.model_dump_json()
    rows, profiles = sensitivity_rows(p, [])
    assert "Y3: 3.00%" in rows[0]["Annual increase / yearly profile"]
    assert "Y3: 5.00%" in rows[2]["Annual increase / yearly profile"]
    assert p.model_dump_json() == before
    p = final_fixture(True)
    p.roles = [r for r in p.roles if r.pwm]
    assert sensitivity_rows(p, load_records()) == ([], [])


def test_deployment_keeps_units_and_duplicate_titles_and_live_quantities():
    p = final_fixture()
    p.roles.append(
        p.roles[0].model_copy(update={"id": "different-row", "quantity": 0.5, "quantity_unit": "FTE"})
    )
    rows = deployment_rows(p)
    assert [r["Unit"] for r in rows] == ["headcount", "FTE"]
    assert rows[0]["Role"] == rows[1]["Role"]
    p.roles[1].quantity = 0.75
    assert deployment_rows(p)[1]["Quantity"] == 0.75


def test_final_page_order_and_single_confirmation_keeps_evidence(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = final_fixture(True)
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert not any(x.value == "### What needs your attention" for x in at.markdown)
    assert any(x.value == "Budget status: Ready for confirmation" for x in at.info)
    assert [x.label for x in at.tabs] == ["Budget", "Scenarios", "Manpower", "Assumptions & sources"]
    assert not at.get("json")
    assert not any("Outstanding decisions" in x.value for x in at.markdown)
    assert any(x.label == "Download budget" for x in at.get("download_button"))
    button(at, "Confirm full contract budget").click().run()
    saved = at.session_state["plan"]
    assert not at.exception and "final" in saved.confirmations and "validation" in saved.confirmations
    assert any("Confirmed budget" == x.value for x in at.caption)


def test_existing_saved_project_is_inspected_as_an_isolated_copy(monkeypatch, tmp_path):
    path = Path("outputs/evaluation/existing-step6-review.json")
    if not path.exists():
        pytest.skip("Local officer snapshot is intentionally excluded from the shareable repository")
    original = path.read_bytes()
    p = Plan.model_validate_json(original)
    before = p.model_dump_json()
    state = review_state(p, load_records())
    assert state["result"] is not None and state["status"] == "Needs attention"
    assert len(state["actions"]) == 1 and state["actions"][0]["step"] == 3
    assert p.model_dump_json() == before
    at = blank(monkeypatch, tmp_path)
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert any(x.label == "Download budget" for x in at.get("download_button"))
    assert button(at, "Confirm full contract budget").disabled
    assert any("Complete pricing basis" == x.label for x in at.button)
    after = at.session_state["plan"].model_dump(mode="json")
    original_fields = Plan.model_validate_json(before).model_dump(mode="json")
    changed = [key for key in after if after[key] != original_fields[key]]
    assert set(changed) <= {"input_steps_completed"}, changed
    assert path.read_bytes() == original


def test_pending_edits_to_an_accepted_decision_have_a_review_control():
    p = final_fixture()
    p.roles[0].rate = 1000
    flag = next(f for f in findings(p, load_records()) if f.code == "rate_range")
    record_decision(
        p,
        flag,
        "accepted exception",
        "Contractor quotation Q1 covers the retained inclusive scope",
        "Synthetic officer",
    )
    state = review_state(p, load_records(), ["Record or revert the edited finding decision: " + flag.message])
    matches = [a for a in state["actions"] if flag.id in a["findings"]]
    assert len(matches) == 1 and matches[0]["kind"] == "finding"
    assert state["final_errors"]


def test_sensitivity_boundaries_remain_unavailable_without_clamping():
    p = final_fixture()
    p.roles[0].escalation = [0, 1.0]
    before = p.model_dump_json()
    rows, _ = sensitivity_rows(p, [])
    assert rows[2]["Full contract budget"] is None
    assert "unavailable" in rows[2]["Availability"].lower()
    assert p.model_dump_json() == before


def test_officer_can_keep_valid_rate_using_the_existing_rationale(monkeypatch, tmp_path):
    p = ready_plan()
    payload = p.roles[0].model_dump(mode="json")
    payload.update(rate=1000, rate_reason="Contractor quotation Q1 covers the stated inclusive scope")
    apply_change(p, "role", payload, "Synthetic price review", "Synthetic officer")
    assert prepare_review(p, "rates", load_records())["ready"]
    accept_review(p, "Synthetic officer", load_records())
    confirm(p, "escalation", "Synthetic officer", load_records())
    p.ui_step = 5
    at = blank(monkeypatch, tmp_path)
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    flag = next(f for f in findings(p, load_records()) if f.code == "rate_range")
    assert not any((x.key or "").startswith(f"finding_{p.id}_{flag.id}") for x in at.text_area)
    assert at.session_state["plan"].roles[0].rate_reason == payload["rate_reason"]
    assert not at.button(key="confirm_final_budget").disabled


def test_different_profiles_remain_visible_for_repeated_role_titles(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = final_fixture()
    p.roles.append(p.roles[0].model_copy(update={"id": "second-position", "escalation": [0, 0.04]}))
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert any(x.label == "Scenario profiles by manpower group" for x in at.expander)
    assert any("Applicable manpower" in x.value.columns for x in at.dataframe)
