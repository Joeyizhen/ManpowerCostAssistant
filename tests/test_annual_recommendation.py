"""Recommendation-first future cost controls; synthetic fixtures only."""

import pytest
from test_grouped_future_journey import open_future, ready_plan
from test_ui import blank

from services.calculations import budget
from services.decision_basis import retained_basis
from services.evidence import load_records
from services.future_groups import GENERAL_COHORT, general_proposal, general_reference


def fresh(monkeypatch, tmp_path, records=None):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan()
    p.id = "annual-recommendation-fixture"
    p.roles[0].escalation = []
    p.roles[0].escalation_reason = ""
    at.session_state["plan"] = p
    if records is not None:
        monkeypatch.setattr("services.evidence.load_records", lambda: records)
    at.run()
    assert not at.exception
    return at


def test_general_cohort_is_fixed_and_independent_of_deployment_titles():
    p = ready_plan()
    bm = general_reference(p, load_records(), ["fm"])
    p.roles[0].mapped_role = None
    p.roles[0].benchmark_scope = "unmatched site"
    again = general_reference(p, load_records(), ["fm"])
    assert bm == again and bm["available"]
    assert all(
        r["scope"] == GENERAL_COHORT["scope"]
        and r["award_status"] == "awarded"
        and r["validation_status"] == "validated"
        for r in bm["records"]
    )
    assert bm["average"] == pytest.approx(sum(x["median_yoy"] for x in bm["schedules"]) / bm["sample_count"])
    for field, value in [
        ("validation_status", "unvalidated"),
        ("currency", "USD"),
        ("scope", "Public venue FM"),
        ("award_status", "submitted"),
        ("inclusions", "Full trade/service manpower price"),
        ("rate_basis", "salary per month"),
    ]:
        contaminated = [{**r, field: value} for r in load_records()]
        assert not general_reference(p, contaminated, ["fm"])["available"]
    only_two = {s["schedule_id"] for s in bm["schedules"][:2]}
    assert not general_reference(p, [r for r in load_records() if r["schedule_id"] in only_two], ["fm"])[
        "available"
    ]


def test_custom_without_note_remains_assumption_and_preserves_earlier_decisions():
    p = ready_plan(True)
    before = p.model_dump_json()
    q = general_proposal(p, [], ["fm"], 3.25, "", "", False, "Synthetic officer")
    fm = next(r for r in q.roles if r.id == "fm")
    basis = retained_basis(q, fm, "escalation")
    assert basis.classification == "officer assumption" and not basis.source
    assert basis.snapshots["fm"]["optional_note"] == ""
    assert q.roles[0].pwm == p.roles[0].pwm
    assert q.confirmations == p.confirmations
    assert p.model_dump_json() == before


def test_compounding_from_second_year_and_explicit_advanced_profile():
    p = ready_plan()
    p.profile.option_years = 2
    q = general_proposal(p, [], ["fm"], 3, "", "", False, "Test")
    rows = budget(q, [])["rows"]
    assert [r["annual_cost"] for r in rows] == [96000, 98880, 101846.4]
    q = general_proposal(p, [], ["fm"], 3, "", "", False, "Test", yearly_percent=[0, 1, 4])
    assert q.roles[0].escalation == [0, 0.01, 0.04]
    assert q.decision_bases[-1].snapshots["fm"]["yearly_percent"] == [0, 1, 4]
    with pytest.raises(ValueError, match="one percentage"):
        general_proposal(p, [], ["fm"], 3, "", "", False, "Test", yearly_percent=[0, 4])


def test_ui_range_and_exact_input_sync_and_custom_no_document(monkeypatch, tmp_path):
    at = fresh(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    prefix = f"common_future_{p.id}"
    bm = general_reference(p, load_records(), ["fm"])
    assert at.slider(key=prefix + "_percent").value == round(bm["average"] * 100, 2)
    assert not at.text_area
    at.number_input(key=prefix + "_exact").set_value(round(bm["minimum"] * 100, 2)).run()
    assert not at.exception
    assert at.slider(key=prefix + "_percent").value == at.number_input(key=prefix + "_exact").value
    at.slider(key=prefix + "_percent").set_value(round(bm["maximum"] * 100, 2)).run()
    assert at.number_input(key=prefix + "_exact").value == round(bm["maximum"] * 100, 2)
    at.checkbox(key=prefix + "_custom").check().run()
    at.number_input(key=prefix + "_percent").set_value(8.5).run()
    at.text_area(key=prefix + "_reason").set_value("").run()
    assert not at.button(key="confirm_escalation").disabled
    at.button(key="confirm_escalation").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 5
    role = at.session_state["plan"].roles[0]
    assert role.escalation == [0, 0.085]
    assert retained_basis(at.session_state["plan"], role, "escalation").classification == "officer assumption"


def test_section_order_and_no_routine_justification_or_group_correction(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path, True)
    headings = [m.value for m in at.markdown if m.value.startswith("### ")]
    assert headings == [
        "### Annual manpower cost increase",
        "### PWM salary progression",
        "### Contract cost impact",
    ]
    assert not any(
        x.label == "Correct the grouping or retain an existing special arrangement" for x in at.expander
    )
    assert not any("What supports" in x.label for x in at.text_area)
    assert not any("Incomplete draft" in x.value for x in at.caption)
    assert {x.label for x in at.metric} >= {
        "Recommended database average",
        "Lower allowance",
        "Higher allowance",
    }


def test_saved_yearly_profiles_require_explicit_replacement(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan()
    p.profile.option_years = 2
    p.roles[0].escalation = [0, 0.01, 0.04]
    at.session_state["plan"] = p
    at.run()
    prefix = f"common_future_{p.id}"
    assert at.checkbox(key=prefix + "_retain").value
    assert p.roles[0].escalation == [0, 0.01, 0.04]
    at.checkbox(key=prefix + "_retain").uncheck().run()
    assert not at.exception and p.roles[0].escalation == [0, 0.01, 0.04]
    assert any(x.key == prefix + "_percent" for x in at.slider)
    at.checkbox(key=prefix + "_yearly_enabled").check().run()
    at.session_state[prefix + "_yearly_table_3"] = {
        "edited_rows": {0: {"Increase (%)": 2.0}, 1: {"Increase (%)": 5.0}},
        "added_rows": [],
        "deleted_rows": [],
    }
    at.run()
    assert not at.exception
    assert any("0, 2, 5" in x.value for x in at.markdown)


def test_insufficient_reference_ui_allows_custom_without_document(monkeypatch, tmp_path):
    import services.future_groups as groups

    original = groups.general_reference
    monkeypatch.setattr(groups, "general_reference", lambda plan, records, ids: original(plan, [], ids))
    at = fresh(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    prefix = f"common_future_{p.id}"
    assert not at.slider
    assert any("evidence is unavailable" in x.value for x in at.info)
    assert not any(x.label == "Recommended database average" for x in at.metric)
    assert at.button(key="confirm_escalation").disabled
    at.number_input(key=prefix + "_percent").set_value(0.0).run()
    assert not at.exception and not at.button(key="confirm_escalation").disabled
    at.text_area(key=prefix + "_reason").set_value("").run()
    at.button(key="confirm_escalation").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 5


def test_yearly_table_keeps_legacy_entries_and_saves_blank_as_unanswered(monkeypatch, tmp_path):
    from test_ui import button

    from services.storage import Store

    at = fresh(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    p.basis_drafts["common_future"] = {"yearly_enabled": True, "yearly_text": "0, 4.25"}
    at.session_state["plan"] = p
    at.run()
    prefix = f"common_future_{p.id}"
    at.checkbox(key=prefix + "_yearly_enabled").check().run()
    table = next(d.value for d in at.dataframe if "Increase (%)" in d.value.columns)
    assert list(table["Contract year"]) == [2]
    assert list(table["Increase (%)"]) == [4.25]
    assert not any(x.key == prefix + "_yearly_text" for x in at.text_input)
    at.session_state[prefix + "_yearly_table_2"] = {
        "edited_rows": {0: {"Increase (%)": None}},
        "added_rows": [],
        "deleted_rows": [],
    }
    at.run()
    assert not at.exception and at.button(key="confirm_escalation").disabled
    assert any("Year 2: enter an increase" in x.value for x in at.info)
    button(at, "Save project").click().run()
    stored, _ = Store(f"sqlite:///{tmp_path / 'ui.db'}").load(p.id, "local-review")
    assert stored.basis_drafts["common_future"]["yearly_values"] == [0, None]
    assert stored.roles[0].escalation == []


def test_pwm_section_is_visible_without_assigning_ordinary_fm_roles(monkeypatch, tmp_path):
    at = fresh(monkeypatch, tmp_path)
    assert any(x.value == "### PWM salary progression" for x in at.markdown)
    assert any("No relevant trade workers" in x.value for x in at.caption)
    assert any(x.value == "**Applicable manpower**" for x in at.markdown)
    assert not any(x.label in ("Affected manpower", "Review grouping") for x in at.expander)
    assert not any("Workers to check" in x.label for x in at.multiselect)
    p = at.session_state["plan"]
    before = [r.model_dump() for r in p.roles]
    at.button(key=f"future_edit_pwm_deployment_{p.id}").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 1
    assert [r.model_dump() for r in at.session_state["plan"].roles] == before


def test_yearly_table_needs_no_separate_constant_percentage():
    p = ready_plan()
    q = general_proposal(p, [], ["fm"], None, "", "", False, "Test", yearly_percent=[0, 4.25])
    assert q.roles[0].escalation == [0, .0425]
