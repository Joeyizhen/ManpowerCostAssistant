"""Officer-facing results, with read-only views and existing approval safeguards."""

import json
from pathlib import Path

import pytest
from test_final_review import final_fixture
from test_ui import blank

from services.calculations import budget
from services.evidence import load_records
from services.final_review import qualification_summary, review_state, source_summary
from services.models import Plan


def test_results_tabs_and_components_are_formatted_without_inapplicable_pwm(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = final_fixture()
    p.roles[0].escalation = [0, 0]
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Budget", "Scenarios", "Manpower", "Assumptions & sources"]
    assert not any(x.value == "### What needs your attention" for x in at.markdown)
    assert not any("PWM:" in x.value for x in at.markdown)
    annual = json.loads(at.get("plotly_chart")[0].proto.spec)
    assert [t["name"] for t in annual["data"]] == ["Starting-rate cost"]
    totals = at.dataframe[0].value
    assert totals.iloc[0]["Annual cost (SGD)"] == "96,000.00"
    assert totals.iloc[1]["Change (%)"] == "0.00%"
    at.radio(key=f"final_budget_view_{p.id}").set_value("Cost components").run()
    assert not at.exception
    detail = at.dataframe[0].value
    assert "Starting-rate manpower cost" in detail and "PWM increase" not in detail
    assert at.session_state["plan"].roles[0].escalation == [0, 0]
    assert not at.get("json")
    assert not any("technical records" in x.label for x in at.expander)
    assert not at.button(key="confirm_final_budget").disabled


def test_saved_project_uses_direct_action_and_compact_optional_details(monkeypatch, tmp_path):
    path = Path("outputs/evaluation/results-page-original.json")
    if not path.exists():
        pytest.skip("Private snapshot is intentionally local only")
    original = path.read_bytes()
    p = Plan.model_validate_json(original)
    before = p.model_dump(mode="json")
    at = blank(monkeypatch, tmp_path)
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert at.button(key=f"final_action_{p.id}_0").label == "Complete pricing basis"
    assert not any("final_group_intent" in (x.key or "") for x in at.radio)
    assert sum("roles need a pricing basis" in x.value for x in at.markdown) == 1
    assert at.button(key="confirm_final_budget").disabled
    at.toggle(key=f"final_action_details_{p.id}_0").set_value(True).run()
    assert len(at.dataframe[0].value) == 6
    after = at.session_state["plan"].model_dump(mode="json")
    assert {k for k in before if before[k] != after[k]} <= {"input_steps_completed"}
    assert path.read_bytes() == original


def test_active_demo_disclosure_and_consolidated_tagging_preserve_evidence():
    p = final_fixture()
    records = load_records()
    _, _, demo = source_summary(p, records)
    assert demo
    assert not source_summary(p, [dict(r, data_origin="validated tender") for r in records])[2]
    assert not source_summary(p, [])[2]
    state = review_state(p, records)
    text = qualification_summary(p, state["findings"])
    assert not any("duty coverage has not been linked" in x for x in text)
    assert sum("Internal duty tagging" in x for x in text) <= 1


def test_mixed_budget_components_and_scenario_views_reconcile(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = final_fixture(True)
    before = p.model_dump(mode="json")
    at.session_state["plan"] = p
    at.run()
    at.radio(key=f"final_budget_view_{p.id}").set_value("Cost components").run()
    assert not at.exception
    result = budget(p, load_records())
    frame = at.dataframe[0].value
    assert not any("Unpublished periods: unselected" in x.value for x in at.caption)
    assert "PWM increase" in frame
    assert sum(float(v.replace(",", "")) for v in frame["Annual cost (SGD)"]) == pytest.approx(
        result["contract_total"]
    )
    assert any(x.label == "Change annual increase in Step 5" for x in at.button)
    assert any("+0.00" in x.value and "vs selected" in x.value for x in at.caption)
    after = at.session_state["plan"].model_dump(mode="json")
    assert {k for k in before if before[k] != after[k]} <= {"input_steps_completed"}
    assert not after["confirmations"].get("final")
