"""Read-only headcount-first attribution reconciles to the existing budget."""

import json

import pytest
from test_ui import blank

from services.calculations import budget, cents
from services.evidence import load_records
from services.final_review import headcount_comparison
from services.xtown_example import xtown_plan


def test_xtown_attribution_reconciles_each_year_and_average():
    p = xtown_plan(load_records())
    before = p.model_dump_json()
    result = budget(p, load_records())
    view = headcount_comparison(p, result)
    assert view["available"] and view["baseline"] == 650400
    assert view["average"] == cents(result["contract_total"] / 6)
    for row in view["rows"]:
        assert row["Headcount change"] == 177600
        assert (
            cents(
                sum(
                    row[k]
                    for k in (
                        "Current headcount at starting rates",
                        "Headcount change",
                        "General annual increase",
                        "PWM increase",
                        "Other adjustments",
                    )
                )
            )
            == row["Annual total"]
        )
    assert sum(i["Share of increase (%)"] for i in view["impacts"]) == pytest.approx(100)
    assert p.model_dump_json() == before


def test_unknown_is_not_zero_and_zero_baseline_has_no_percentage():
    p = xtown_plan(load_records())
    p.roles[0].current_quantity = None
    view = headcount_comparison(p, budget(p, load_records()))
    assert not view["available"] and "Facilities Manager" in view["reason"]
    for r in p.roles:
        r.current_quantity = 0
    view = headcount_comparison(p, budget(p, load_records()))
    assert view["available"] and view["baseline"] == 0 and view["increase_percent"] is None
    p.roles[0].quantity_unit = "FTE"
    assert not headcount_comparison(p, budget(p, load_records()))["available"]


def test_reductions_removed_roles_and_yearly_staffing_stay_signed():
    p = xtown_plan(load_records())
    p.roles[0].current_quantity = 20
    p.roles[1].included = False
    p.roles[2].yearly_quantities = [5, 6, 7, 6, 5, 4]
    result = budget(p, load_records())
    view = headcount_comparison(p, result)
    assert view["available"]
    assert all(r["Headcount change"] < 0 for r in view["rows"])
    assert view["rows"][1]["Headcount change"] - view["rows"][0]["Headcount change"] == 50400
    assert all(i["Share of increase (%)"] is None for i in view["impacts"])


def test_budget_ui_has_year_zero_headcount_segment_and_insights(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    at.button(key="load_xtown_example").click().run()
    assert not at.exception
    spec = json.loads(at.get("plotly_chart")[0].proto.spec)
    assert "Headcount change" in [trace["name"] for trace in spec["data"]]
    assert spec["data"][0]["x"][0] == "Year 0 (current)"
    assert any(m.label == "Average budget (SGD/year)" for m in at.metric)
    assert any("Share of increase (%)" in d.value.columns for d in at.dataframe)
    assert "final" not in at.session_state["plan"].confirmations
