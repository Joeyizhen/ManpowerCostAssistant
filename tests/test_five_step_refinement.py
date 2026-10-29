"""Five visible screens, immutable legacy locations and honest reference controls."""

from test_compact_pricing_journey import controls, prices
from test_grouped_future_journey import open_future
from test_prepared_references import prepared  # noqa: F401 -- register isolated prepared fixture
from test_ui import blank, button

from selection_controls import bar_domain
from services.evidence import load_records
from services.hybrid import canonical_step, step_number
from services.models import Plan, Role
from services.role_catalogue import available_roles, catalogue


def test_taxonomy_flags_are_the_only_typical_list_and_additional_is_disjoint(monkeypatch):
    source = {
        "dataset_id": "invented-v1",
        "standard_roles": [
            {"Role Title": "Senior FM", "Typical manpower?": "Yes"},
            {"Role Title": "FM cum FSM", "Typical manpower?": "No"},
        ],
        "mappings": [],
    }
    monkeypatch.setattr("services.role_catalogue.active_snapshot", lambda: source)
    monkeypatch.setattr("services.role_catalogue.title_mapping", lambda t: None)
    assert catalogue()["typical"] == ["Senior FM"]
    assert catalogue()["additional"] == ["FM cum FSM"]
    p = Plan(roles=[Role(id="r", label="Senior FM", quantity=1)])
    assert available_roles(p)["typical"] == []
    source["standard_roles"][1]["Typical manpower?"] = "Yes"
    assert catalogue()["typical"] == ["Senior FM", "FM cum FSM"]


def test_alias_deduplication_preserves_seniority_and_combined_arrangements(monkeypatch):
    from services.role_catalogue import identity

    monkeypatch.setattr("services.role_catalogue.title_mapping", lambda t: "Facilities Manager")
    assert identity("Facilities Manager (FM)") == identity("Facilities Manager")
    assert identity("Senior FM") != identity("Facilities Manager")
    assert identity("FM cum FSM") != identity("Facilities Manager")


def test_all_five_steps_are_clickable_without_confirming_or_showing_false_totals(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    original = p.model_dump(mode="json", exclude={"ui_step", "input_steps_completed"})
    for route in [5, 4, 3, 1, 0]:
        at.button(key=f"step_nav_{route}").click().run()
        assert not at.exception
        assert at.session_state["plan"].ui_step == route
        assert not at.session_state["plan"].confirmations
        if route >= 3:
            assert not any(m.label == "Full contract manpower budget (SGD)" for m in at.metric)
    assert (
        at.session_state["plan"].model_dump(mode="json", exclude={"ui_step", "input_steps_completed"})
        == original
    )


def test_legacy_six_screen_locations_route_without_repricing_or_reconfirming(monkeypatch, tmp_path):
    from test_grouped_future_journey import ready_plan

    at = blank(monkeypatch, tmp_path)
    for old in range(6):
        p = ready_plan()
        p.ui_step = old
        before = p.model_dump(mode="json", exclude={"ui_step", "input_steps_completed"})
        at.session_state["plan"] = p
        at.run()
        assert not at.exception
        assert at.session_state["plan"].ui_step == canonical_step(old)
        assert step_number(old) == [1, 2, 2, 3, 4, 5][old]
        assert (
            at.session_state["plan"].model_dump(mode="json", exclude={"ui_step", "input_steps_completed"})
            == before
        )


def test_rate_bar_and_exact_input_sync_both_ways_and_allow_outside_range(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    p, role, key = controls(at)
    value = round(at.slider(key=key + "_bar").value + 10, 2)
    at.slider(key=key + "_bar").set_value(value).run()
    assert at.number_input(key=key + "_number").value == value
    at.number_input(key=key + "_number").set_value(99999.0).run()
    assert at.slider(key=key + "_bar").value == 99999.0
    assert next(r for r in at.session_state["plan"].roles if r.id == role.id).rate == 99999.0
    assert next(r for r in at.session_state["plan"].roles if r.id == role.id).quantity == 0.5
    assert bar_domain(10, 20, 30) == (10, 30)
    assert "rates" not in at.session_state["plan"].confirmations


def test_rate_controls_rehydrate_after_direct_navigation_without_changing_facts(monkeypatch, tmp_path):
    at = prices(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    before = p.model_dump(mode="json", exclude={"ui_step", "input_steps_completed"})
    for route in [0, 1, 5, 3]:
        at.button(key=f"step_nav_{route}").click().run()
        assert not at.exception
    for role in at.session_state["plan"].roles:
        if role.included:
            key = f"rate_{p.id}_{role.id}_{role.benchmark_year}_number"
            assert at.number_input(key=key).value == role.rate
    assert (
        at.session_state["plan"].model_dump(mode="json", exclude={"ui_step", "input_steps_completed"})
        == before
    )


def test_annual_bar_and_input_sync_without_confirming_saved_choice(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    prefix = f"common_future_{p.id}"
    original = [r.escalation[:] for r in p.roles]
    at.slider(key=prefix + "_bar").set_value(2.75).run()
    assert at.number_input(key=prefix + "_percent").value == 2.75
    at.number_input(key=prefix + "_percent").set_value(9.5).run()
    assert at.slider(key=prefix + "_bar").value == 9.5
    assert [r.escalation for r in at.session_state["plan"].roles] == original
    assert "escalation" not in at.session_state["plan"].confirmations


def test_unfinished_unlisted_title_survives_navigation_save_and_reopen(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    at.button(key="step_nav_1").click().run()
    at.session_state["plan"].basis_drafts["role_entry"] = {"title": "Senior digital FM coordinator"}
    at.run()
    at.button(key="step_nav_5").click().run()
    button(at, "Save draft").click().run()
    button(at, "Resume selected project").click().run()
    at.button(key="step_nav_1").click().run()
    assert at.session_state["plan"].basis_drafts["role_entry"]["title"] == "Senior digital FM coordinator"
    assert not at.session_state["plan"].roles
    assert not any(t.label == "Unlisted role title" for t in at.text_input)
    assert not any(e.label == "Add an unlisted role" for e in at.expander)


def test_invalid_project_text_survives_navigation_and_saved_reopening(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    next(t for t in at.text_input if t.label == "Base term (years)").set_value("awaiting decision").run()
    at.button(key="step_nav_5").click().run()
    button(at, "Save draft").click().run()
    button(at, "Resume selected project").click().run()
    at.button(key="step_nav_0").click().run()
    assert next(t for t in at.text_input if t.label == "Base term (years)").value == "awaiting decision"
    assert not at.session_state["plan"].confirmations
    assert at.session_state["plan"].profile.base_years is None


def test_no_price_recommendation_is_invented_from_unqualified_prepared_quotes(prepared):  # noqa: F811 -- pytest fixture registration
    from services.pricing import reference
    from services.reference_data import rate_reference

    # This regression also enforces that a broad source range is not the bar's
    # verified per-person evidence. Detailed observations may remain secondary.
    assert not rate_reference([], "Facilities Manager")["available"]
    p = Plan(roles=[Role(id="r", label="Facilities Manager", mapped_role="Facility Manager", quantity=1)])
    assert not reference(p, p.roles[0], load_records())["recommendation_supported"]


def test_explicitly_cleared_rate_stays_unanswered_instead_of_being_reseeded(monkeypatch):
    from test_grouped_future_journey import ready_plan

    import pricing_inputs
    from services.hybrid import initialise_rates

    p = ready_plan()

    class State(dict):
        __getattr__ = dict.__getitem__

    monkeypatch.setattr(
        pricing_inputs.st, "session_state", State(plan=p, officer="Test officer", entered=None)
    )
    pricing_inputs.rate_changed("fm", "rate", "entered")
    initialise_rates(p, load_records(), 2028)
    assert p.roles[0].rate is None
    assert "rates" not in p.confirmations
    restored = Plan.model_validate_json(p.model_dump_json())
    initialise_rates(restored, load_records(), 2028)
    assert restored.roles[0].rate is None
