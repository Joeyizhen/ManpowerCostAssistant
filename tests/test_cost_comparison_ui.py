"""Officer-facing cost attribution reconciles to the unchanged budget engine."""

import json
from datetime import date
from io import BytesIO

import openpyxl
import pytest
from test_grouped_future_journey import ready_plan
from test_ui import blank, button

from review_inputs import COMPONENTS, cost_components
from services.calculations import budget
from services.demo import demo_plan
from services.evidence import load_records
from services.export import export_excel
from services.models import PolicyAdjustment
from services.workflow import confirm


def test_mixed_pwm_and_general_costs_reconcile_without_changing_the_plan():
    p = ready_plan(True)
    before = p.model_dump_json()
    result = budget(p, load_records())
    yearly, total = cost_components(p, result)
    assert total["Annual manpower increases"] == 1920.0
    assert total["PWM salary progression"] == sum(r["pwm_cost"] for r in result["rows"])
    assert total["Total"] == result["contract_total"]
    for row in yearly:
        assert sum(row[k] for k in ["Starting charges", *COMPONENTS]) == pytest.approx(row["Total"])
    assert p.model_dump_json() == before


def test_quoted_prices_other_adjustments_and_changed_quantities_are_not_pwm_or_inflation():
    p = demo_plan()
    p.profile.start = date(2025, 1, 1)
    role = p.roles[1]
    role.escalation_mode = "quoted schedule"
    role.schedule_id = "SYN-T01-R05-awarded"
    records = load_records()
    quote = next(r for r in records if r["schedule_id"] == role.schedule_id and r["pricing_year"] == 2025)
    role.rate, role.escalation = quote["unit_rate_monthly"], [0] * 6
    p.roles[0].yearly_quantities = [1, 2, 3, 2, 1, 1]
    p.roles[0].policies = [
        PolicyAdjustment(
            name="Synthetic allowance",
            effective_date=date(2025, 1, 1),
            annual_monthly_increment=20,
            affected_component="Synthetic component",
            source="Synthetic quotation",
            basis_confirmed=True,
            overlap_reviewed=True,
        )
    ]
    result = budget(p, records)
    yearly, total = cost_components(p, result)
    quote_rows = [r for r in result["rows"] if r["role_id"] == role.id]
    assert total["Quoted future-price changes"] == round(
        sum(r["annual_before_policy"] - r["flat_baseline"] for r in quote_rows), 2
    )
    assert total["Quoted future-price changes"] > 0 and total["Other component adjustments"] > 0
    assert total["PWM salary progression"] == 0
    assert total["Starting charges"] == result["waterfall"]["baseline"]
    assert total["Total"] == result["contract_total"]


def test_reductions_and_zero_changes_are_honest():
    p = ready_plan()
    p.roles[0].escalation = [0, -0.02]
    yearly, total = cost_components(p, budget(p, []))
    assert total["Annual manpower increases"] == -1920
    assert yearly[1]["Total"] == 94080
    p.roles[0].escalation = [0, 0]
    _, flat = cost_components(p, budget(p, []))
    assert all(flat[k] == 0 for k in COMPONENTS)
    assert flat["Starting charges"] == flat["Total"]


def test_final_screen_uses_simple_comparison_and_one_final_confirmation(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan(True)
    confirm(p, "escalation", "Synthetic officer", load_records())
    p.ui_step = 5
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    removed = {
        "Trace material budget decisions",
        "Resolved findings and previous decisions",
        "Optional separate finding-review checkpoint",
    }
    assert not removed.intersection(x.label for x in at.expander)
    assert not any(b.key == "confirm_validation" for b in at.button)
    specs = [json.loads(chart.proto.spec) for chart in at.get("plotly_chart")]
    assert len(specs) >= 2
    assert all(trace["type"] == "bar" for spec in specs for trace in spec["data"])
    assert "PWM increase" in [trace.get("name") for trace in specs[0]["data"]]
    button(at, "Confirm full contract budget").click().run()
    assert not at.exception
    saved = at.session_state["plan"]
    assert "validation" in saved.confirmations and "final" in saved.confirmations
    workbook = openpyxl.load_workbook(BytesIO(export_excel(saved, load_records())), data_only=True)
    assert "Findings and decisions" in workbook.sheetnames
