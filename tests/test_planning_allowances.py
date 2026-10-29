"""Demo pricing controls are explicit assumptions, not invented observed evidence."""

from test_grouped_future_journey import ready_plan
from test_ui import blank

from services.evidence import load_records
from services.models import Plan, Role
from services.planning_allowances import planning_range, seed_missing_allowances
from services.xtown_example import EXAMPLE_NAME, xtown_plan


def test_illustrative_defaults_preserve_values_clears_titles_and_confirmations():
    p = Plan(
        roles=[
            Role(id="new", label="Account Director", quantity=1, quantity_unit="headcount"),
            Role(id="kept", label="Facilities Manager", quantity=2, quantity_unit="headcount", rate=8765),
            Role(id="clear", label="Technician", quantity=1, quantity_unit="headcount"),
            Role(id="combined", label="Senior FM cum FSM", quantity=1, quantity_unit="headcount"),
        ]
    )
    p.basis_drafts["rate_unanswered"] = {"clear": True}
    seed_missing_allowances(p, [], "Test officer")
    assert [r.rate for r in p.roles] == [12000, 8765, None, 5000]
    assert p.roles[-1].label == "Senior FM cum FSM" and planning_range(p.roles[-1])["generic"]
    assert p.roles[0].rate_origin == "Officer assumption"
    assert "illustrative" in p.roles[0].rate_reason and "no market-rate evidence" in p.roles[0].rate_reason
    assert not p.confirmations


def test_slider_exact_sync_and_no_per_role_reference_expanders(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan()
    p.roles = [p.roles[0]]
    p.roles[0].label = "Account Director"
    p.roles[0].mapped_role = None
    p.roles[0].rate = None
    p.roles[0].rate_reason = ""
    p.ui_step = 3
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    p = at.session_state["plan"]
    role = p.roles[0]
    prefix = f"rate_{p.id}_{role.id}_{role.benchmark_year}"
    assert role.rate == 12000
    assert at.slider(key=prefix + "_bar").value == 12000
    assert not any(e.label.startswith("View reference details") for e in at.expander)
    at.number_input(key=prefix + "_number").set_value(13500).run()
    assert at.slider(key=prefix + "_bar").value == 13500
    at.slider(key=prefix + "_bar").set_value(12500).run()
    assert at.number_input(key=prefix + "_number").value == 12500
    at.number_input(key=prefix + "_number").set_value(None).run()
    at.run()
    assert at.session_state["plan"].roles[0].rate is None
    assert "rates" not in at.session_state["plan"].confirmations


def test_xtown_is_complete_resumable_and_not_finally_approved(tmp_path):
    from services.calculations import budget
    from services.storage import Store

    records = load_records()
    p = xtown_plan(records)
    assert p.profile.name == EXAMPLE_NAME and (p.profile.base_years, p.profile.option_years) == (3, 3)
    assert p.ui_step == 5 and "final" not in p.confirmations
    assert sum(r.current_quantity for r in p.roles) == 13
    assert sum(r.quantity for r in p.roles) == 17
    assert len([r for r in p.roles if r.pwm]) == 2
    assert all(r.quantity_unit == "headcount" for r in p.roles)
    result = budget(p, records)
    assert len(result["annual_totals"]) == 6
    assert round(result["base_total"] + result["option_total"], 2) == result["contract_total"]
    store = Store(f"sqlite:///{tmp_path / 'example.db'}")
    store.save(p, "test", 0)
    loaded, _ = store.load(p.id, "test")
    assert budget(loaded, records)["contract_total"] == result["contract_total"]
    assert "final" not in loaded.confirmations


def test_xtown_button_opens_final_budget_without_auto_approval(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    at.button(key="load_xtown_example").click().run()
    assert not at.exception
    p = at.session_state["plan"]
    assert p.profile.name == EXAMPLE_NAME and p.ui_step == 5
    assert "final" not in p.confirmations
    assert any(m.label == "Full contract manpower budget (SGD)" for m in at.metric)


def test_xtown_navigation_keeps_confirmed_inputs(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    monkeypatch.delenv("MANPOWER_REFERENCE_SOURCE", raising=False)
    at.button(key="load_xtown_example").click().run()
    before = at.session_state["plan"].model_copy(deep=True)
    at.button(key="step_nav_3").click().run()
    p = at.session_state["plan"]
    assert not at.exception
    assert "plan" in p.confirmations, p.history[-4:]
    assert [r.rate for r in p.roles] == [r.rate for r in before.roles]
    assert len(at.slider) == 5


def test_saved_xtown_resume_navigation(monkeypatch, tmp_path):
    from services.storage import Store

    at = blank(monkeypatch, tmp_path)
    monkeypatch.delenv("MANPOWER_REFERENCE_SOURCE", raising=False)
    saved = xtown_plan(load_records())
    Store(f"sqlite:///{tmp_path / 'ui.db'}").save(saved, "local-review", 0)
    at.run()
    next(b for b in at.button if b.label == "Resume selected project").click().run()
    at.button(key="step_nav_3").click().run()
    p = at.session_state["plan"]
    assert "plan" in p.confirmations, p.history[-4:]
