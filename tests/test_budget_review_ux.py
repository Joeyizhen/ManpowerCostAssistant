"""Saved zero assumptions and officer-facing summaries remain safe to explore."""

import json

from test_grouped_future_journey import ready_plan
from test_ui import blank

from services.calculations import budget
from services.evidence import load_records
from services.future_groups import general_proposal, general_reference
from services.workflow import confirm


def saved_zero(monkeypatch, tmp_path, step=4):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan()
    p = general_proposal(p, load_records(), [p.roles[0].id], 0, "", "", False, "Test")
    confirm(p, "escalation", "Test", load_records())
    p.ui_step = step
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    return at


def test_saved_zero_recommendation_previews_without_mutation_then_confirms(monkeypatch, tmp_path):
    at = saved_zero(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    before = p.model_dump_json()
    total = budget(p, load_records())["contract_total"]
    prefix = f"common_future_{p.id}"
    expected = round(general_reference(p, load_records(), [])["average"] * 100, 2)
    at.button(key=prefix + "_use_average").click().run()
    assert not at.exception
    assert at.number_input(key=prefix + "_percent").value == expected
    # The choice edits a persisted preview, not the recorded assumptions or approval.
    p = at.session_state["plan"]
    assert p.roles[0].escalation == [0, 0]
    assert budget(p, load_records())["contract_total"] == total
    assert p.confirmations["escalation"] == json.loads(before)["confirmations"]["escalation"]
    at.button(key="confirm_escalation").click().run()
    assert not at.exception
    p = at.session_state["plan"]
    assert p.ui_step == 5 and p.roles[0].escalation == [0, expected / 100]
    assert budget(p, load_records())["contract_total"] > total
    assert not at.button(key="confirm_final_budget").disabled


def test_keep_zero_reverses_only_the_preview(monkeypatch, tmp_path):
    at = saved_zero(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    prefix = f"common_future_{p.id}"
    at.button(key=prefix + "_use_average").click().run()
    at.button(key=prefix + "_keep_zero").click().run()
    assert not at.exception
    assert at.number_input(key=prefix + "_percent").value == 0
    assert at.session_state["plan"].roles[0].escalation == [0, 0]
    assert not at.button(key="confirm_escalation").disabled


def test_compact_review_hides_inapplicable_pwm_and_keeps_details_available(monkeypatch, tmp_path):
    at = saved_zero(monkeypatch, tmp_path, step=5)
    p = at.session_state["plan"]
    assert not any("Demo reference data" in x.value for x in at.caption)
    assert not any("Material limitation:" in x.value for x in at.caption)
    summary = next(d.value for d in at.dataframe if "Annual total" in d.value.columns)
    assert {
        "Contract year",
        "Annual total",
        "Change from prior year (SGD)",
        "Change from prior year (%)",
    } <= set(summary.columns)
    assert (
        sum(float(str(v).replace(",", "")) for v in summary["Annual total"])
        == budget(p, load_records())["contract_total"]
    )
    chart = json.loads(at.get("plotly_chart")[0].proto.spec)
    assert "PWM increase" not in [t.get("name") for t in chart["data"]]
    assert at.session_state["plan"].roles[0].escalation == [0, 0]
    assert at.button(key="confirm_final_budget").label == "Confirm final budget"
    assert not at.exception
    assert any("Current headcount at starting rates" in d.value.columns for d in at.dataframe)
    at.button(key=f"final_sensitivity_edit_{p.id}").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 4


def test_source_notice_does_not_label_real_reference_rows_as_synthetic(monkeypatch, tmp_path):
    at = saved_zero(monkeypatch, tmp_path, step=5)
    records = [{**r, "data_origin": "source-extracted"} for r in load_records()]
    monkeypatch.setattr("services.evidence.load_records", lambda: records)
    at.run()
    assert not at.exception
    assert not any("Demo reference data" in x.value for x in at.caption)
    assert any(x.label == "Assumptions & sources" for x in at.tabs)
