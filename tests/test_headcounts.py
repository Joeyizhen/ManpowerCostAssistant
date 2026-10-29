import json

import pytest
from test_grouped_future_journey import ready_plan
from test_ui import blank

from services.headcounts import comparison


def row(current, proposed, unit="headcount"):
    return {"Quantity basis": unit, "Current quantity / FTE": current, "Proposed quantity / FTE": proposed}


def test_current_proposed_and_change_include_explicit_exclusions():
    r = comparison([row(3, 5), row(2, 4), row(1, 0)], True)
    assert (r["current"], r["proposed"], r["change"]) == (6, 9, 3)


def test_missing_and_non_whole_people_do_not_become_zero_or_complete_totals():
    r = comparison([row(None, 3), row(2, None), row(0.5, 1)], True)
    assert (r["current"], r["proposed"]) == (2, 4)
    assert (r["current_missing"], r["proposed_missing"], r["change"]) == (2, 1, None)


def test_unknown_context_does_not_assume_a_zero_current_team():
    r = comparison([row(None, 4)], None)
    assert r["current_missing"] == 1 and r["change"] is None


def test_old_deployment_panel_is_reloaded_without_replacing_financial_models():
    from types import SimpleNamespace

    import services.models as models
    from services.runtime_compat import recover_stale_imports

    modules = {"journey_inputs": SimpleNamespace(), "services.models": models}
    assert recover_stale_imports(modules)
    assert "journey_inputs" not in modules
    assert modules["services.models"] is models


def test_saved_fte_is_not_silently_added_as_people():
    r = comparison([row(2, 4), row(0.5, 1.5, "FTE")], True)
    assert (r["current"], r["proposed"], r["legacy_rows"], r["change"]) == (2, 4, 1, None)


def test_new_deployment_has_zero_current_and_no_assumed_missing_proposal():
    assert comparison([row(None, 4)], False)["change"] == 4
    assert comparison([row(None, None)], False)["change"] is None


def test_assistant_cannot_introduce_fte_or_round_it_into_headcount():
    from services.deployment_review import accept_suggestions
    from services.models import Plan, Role
    from services.workflow import proposal

    p = Plan()
    proposal(
        p,
        "role",
        Role(id="new", label="FM", quantity=0.5, quantity_unit="FTE").model_dump(mode="json"),
        "Suggested shared cover",
    )
    before = p.model_dump_json()
    with pytest.raises(ValueError, match="actual whole-person headcount"):
        accept_suggestions(p, "Test officer")
    assert p.model_dump_json() == before


def test_headcount_ui_hides_unit_choice_and_updates_comparison(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan()
    p.contract_kind, p.current_deployment_status, p.ui_step = "existing contract", "known", 1
    p.roles[0].current_quantity, p.roles[0].quantity = 2, 5
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Current headcount"] == "2"
    assert metrics["Proposed headcount"] == "5"
    assert metrics["Headcount change"] == "+3"
    table = next(d for d in at.dataframe if "Quantity basis" in d.value.columns)
    assert json.loads(table.proto.columns)["Quantity basis"]["hidden"]
    assert "Proposed FTE" not in metrics


def test_legacy_unit_requires_explicit_headcounts_and_keeps_saved_values(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan()
    p.ui_step = 1
    p.roles[0].quantity_unit, p.roles[0].quantity = "FTE", 0.5
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert at.session_state["plan"].roles[0].quantity == 0.5
    next(n for n in at.number_input if n.label == "Proposed number of people").set_value(2).run()
    next(b for b in at.button if b.label == "Use these headcounts").click().run()
    assert not at.exception
    from services.journey import working_draft

    updated = working_draft(at.session_state["plan"]).roles[0]
    assert (updated.quantity_unit, updated.quantity) == ("headcount", 2)
