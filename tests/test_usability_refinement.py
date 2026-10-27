"""Targeted usability refinements retain the existing budgeting and confirmation rules."""

from pathlib import Path

import pytest
from test_compact_pricing_journey import controls, prices
from test_final_review import final_fixture
from test_grouped_future_journey import open_future, ready_plan
from test_ui import blank, button

from services.calculations import budget
from services.decision_basis import retained_basis
from services.evidence import load_records
from services.final_review import action_presentation, flat_cost_explanation, review_state
from services.models import Plan
from services.pricing import apply_shared_pricing, pricing_proposal, shared_pricing_applies
from services.workflow import apply_change


def test_shared_quote_applies_once_preserves_rates_and_invalidates_only_affected_gates():
    p = ready_plan()
    p.roles.append(p.roles[0].model_copy(update={"id": "separate-position", "rate": 7500}))
    rates = {r.id: r.rate for r in p.roles}
    quantities = {r.id: r.quantity for r in p.roles}
    ids = list(rates)
    apply_shared_pricing(
        p,
        ids,
        "Supplier quotation Q1 covers inclusive charges for these positions",
        "Synthetic Q1",
        "Synthetic officer",
    )
    q, errors = pricing_proposal(p, load_records(), "Synthetic officer")
    assert not errors
    assert {r.id: r.rate for r in q.roles} == rates and {r.id: r.quantity for r in q.roles} == quantities
    assert "plan" in p.confirmations and "rates" not in p.confirmations
    for role in q.roles:
        basis = retained_basis(q, role, "rate")
        assert "Supplier quotation Q1" in basis.explanation
        assert basis.snapshots[role.id]["quotation_reference"] == "Synthetic Q1"
        assert set(basis.snapshots[role.id]["shared_pricing_roles"]) == set(ids)
    changed = p.roles[0].model_dump(mode="json")
    changed.update(rate=p.roles[0].rate + 1, rate_reason="")
    apply_change(p, "role", changed, "Price changed", "Synthetic officer")
    assert not shared_pricing_applies(p, next(r for r in p.roles if r.id == changed["id"]))
    assert any(shared_pricing_applies(p, r) for r in p.roles)


def test_shared_pricing_ui_avoids_repeated_explanation_and_keeps_draft(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    p, role, _ = controls(at)
    for r in p.roles:
        if r.included:
            r.rate = 15000
            r.rate_reason = ""
    at.session_state["plan"] = p
    at.run()
    prefix = f"pricing_shared_{p.id}"
    selected = [r.id for r in p.roles if r.included]
    at.multiselect(key=prefix + "_roles").set_value(selected).run()
    at.text_area(key=prefix + "_reason").set_value(
        "Supplier quotation Q1 covers these inclusive manpower allowances"
    ).run()
    at.text_input(key=prefix + "_source").set_value("Synthetic quotation Q1").run()
    at.button(key=prefix + "_apply").click().run()
    assert not at.exception
    assert not any((x.key or "").endswith("_rationale") for x in at.text_area)
    assert not at.button(key="confirm_rates").disabled
    button(at, "Save project").click().run()
    at.button(key="confirm_rates").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 4
    assert all(r.rate == 15000 for r in at.session_state["plan"].roles if r.included)


def test_saved_project_actions_are_short_with_expandable_details():
    path = Path("outputs/evaluation/usability-saved-project.json")
    if not path.exists():
        pytest.skip("Local officer snapshot is intentionally private")
    p = Plan.model_validate_json(path.read_text(encoding="utf-8"))
    before = p.model_dump_json()
    state = review_state(p, load_records())
    summary, why, details = action_presentation(p, state["actions"][0])
    assert "6 role" in summary and "One quotation or explanation may cover several roles" in summary
    assert len(details) == 6
    assert all("financial basis" not in row["What to check"] for row in details)
    assert "do not require you to change" in why
    assert p.model_dump_json() == before


def test_confirmation_follows_annual_breakdown_and_selected_scenario_is_visible(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = final_fixture(True)
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    elements = list(at.main)
    tabs_index = next(i for i, x in enumerate(elements) if x.type == "tab_container")
    final_index = next(i for i, x in enumerate(elements) if getattr(x, "key", "") == "confirm_final_budget")
    assert tabs_index < final_index
    metrics = [x for x in at.metric if "annual increase (SGD)" in x.label]
    assert len(metrics) == 3
    assert (
        next(x.value for x in metrics if x.label.startswith("Selected"))
        == f"{budget(p, load_records())['contract_total']:,.2f}"
    )


def test_zero_and_missing_are_distinct_and_flat_cost_reason_is_accurate(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    prefix = f"common_future_{p.id}"
    at.number_input(key=prefix + "_percent").set_value(0.0).run()
    assert any("0% selected" in x.value for x in at.info)
    assert not at.button(key="confirm_escalation").disabled
    p = ready_plan()
    p.roles[0].escalation = [0, 0]
    assert "0% and deployment is unchanged" in flat_cost_explanation(p, budget(p, []))
    p.roles[0].yearly_quantities = [1, 2]
    assert not flat_cost_explanation(p, budget(p, []))


def test_review_choices_are_distinct_and_corrections_are_recorded(monkeypatch, tmp_path):
    from services.journey import accept_review, prepare_review
    from services.workflow import confirm, findings

    p = ready_plan()
    item = p.roles[0].model_dump(mode="json")
    item.update(rate=1000, rate_reason="Supplier quote Q1 covers the retained inclusive scope")
    apply_change(p, "role", item, "Synthetic quote", "Synthetic officer")
    assert prepare_review(p, "rates", load_records())["ready"]
    accept_review(p, "Synthetic officer", load_records())
    confirm(p, "escalation", "Synthetic officer", load_records())
    p.ui_step = 5
    at = blank(monkeypatch, tmp_path)
    at.session_state["plan"] = p
    at.run()
    flag = next(f for f in findings(p, load_records()) if f.code == "rate_range")
    prefix = f"finding_{p.id}_{flag.id}_{flag.fingerprint}"
    assert at.radio(key=prefix + "_choice").options == [
        "Keep my figures",
        "Correct the interpretation",
        "Revise figures",
    ]
    at.text_area(key=prefix + "_reason").set_value(
        "Supplier quote Q1 reflects the narrower stated scope"
    ).run()
    at.radio(key=prefix + "_choice").set_value("Revise figures").run()
    assert not any(x.key == prefix + "_record" for x in at.button)
    assert any("Revise figures in Step 4" == x.label for x in at.button)
    at.radio(key=prefix + "_choice").set_value("Correct the interpretation").run()
    assert (
        at.text_area(key=prefix + "_reason").value == "Supplier quote Q1 reflects the narrower stated scope"
    )
    at.button(key=prefix + "_record").click().run()
    assert not at.exception
    saved = at.session_state["plan"]
    assert saved.roles[0].rate == 1000
    assert any(h.get("choice") == "Correct the interpretation" for h in saved.history)
    assert any(x.value == "Budget status: Ready for confirmation" for x in at.info)
