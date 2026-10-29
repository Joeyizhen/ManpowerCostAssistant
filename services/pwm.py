"""Owner's salary-ratio budgeting method. Official wage facts are not inclusive prices."""

import hashlib
import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


def catalog():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "data/reference/pwm-2026-10-19.json").read_text(
            encoding="utf-8"
        )
    )


def get_schedule(schedule_id):
    match = next((s for s in catalog()["schedules"] if s["id"] == schedule_id), None)
    if not match:
        raise ValueError("Select a verified official monthly PWM schedule")
    match["digest"] = hashlib.sha256(json.dumps(match, sort_keys=True).encode()).hexdigest()
    return match


def wage_at(schedule, when):
    points = [p for p in schedule["points"] if date.fromisoformat(p["effective"]) <= when]
    if not points:
        raise ValueError(
            "The contract starts before the retained published schedule; obtain the correct source"
        )
    return Decimal(str(points[-1]["wage"]))


def validate_pwm(role, profile):
    c = role.pwm
    if not c:
        return
    from services.cost_routing import route_errors

    if errors := route_errors(role):
        raise ValueError("; ".join(errors))
    from services.decision_basis import meaningful

    s = get_schedule(c.schedule_id)
    if c.schedule_digest != s["digest"]:
        raise ValueError(
            "The official schedule snapshot changed or was not confirmed; review its source and dates again"
        )
    if profile.start is None or profile.start.day != 1:
        raise ValueError(
            f"{role.label}: confirm an exact first-of-month start for calendar-month PWM budgeting; partial-month treatment is unresolved"
        )
    if role.quantity_unit != "headcount":
        raise ValueError(
            "This published monthly full-time schedule needs explicit headcount; do not infer a part-time/FTE conversion"
        )
    if not role.quantity or c.covered_quantity > min([role.quantity, *role.yearly_quantities]):
        raise ValueError("PWM covered workers cannot exceed the included quantity in any year")
    if role.rate is None or c.starting_salary > role.rate:
        raise ValueError(
            "Identify a starting salary component within the inclusive per-head charge; never infer a salary split"
        )
    if role.escalation_mode != "assumption" or any(role.escalation) or role.policies:
        raise ValueError(
            "PWM salary progression cannot be stacked with full-unit escalation, quoted future prices or generic component adjustments; provide a separately reviewed non-overlapping model"
        )
    if (
        not c.applicability_confirmed
        or not c.remainder_flat_confirmed
        or not c.salary_source.strip()
        or not meaningful(c.applicability_basis)
        or not meaningful(c.rationale)
    ):
        raise ValueError(
            "Confirm category/job eligibility, salary source, operational rationale and the flat non-salary remainder"
        )
    if c.oncost_rate and not c.oncost_source.strip():
        raise ValueError("Employer on-cost changes need a separate evidenced rate and source")
    end = profile.start.replace(year=profile.start.year + profile.years)
    if end > date.fromisoformat(s["valid_until"]) + timedelta(days=1) and c.beyond_published == "unselected":
        raise ValueError("Choose and explain the officer assumption beyond the published PWM period")
    if end > date.fromisoformat(s["valid_until"]) + timedelta(days=1) and not meaningful(c.beyond_reason):
        raise ValueError(
            "Explain how unpublished future salary movements are budgeted; they are assumptions, not policy"
        )
    wage_at(s, profile.start)


def salary_months(role, profile, contract_year):
    validate_pwm(role, profile)
    c = role.pwm
    s = get_schedule(c.schedule_id)
    baseline = wage_at(s, profile.start)
    salary = Decimal(str(c.starting_salary))

    def assumed_factor(when):
        end = date.fromisoformat(s["valid_until"])
        if when <= end or c.beyond_published != "officer annual assumption":
            return Decimal(1)
        elapsed = (when.year - end.year) * 12 + when.month - end.month
        return (1 + Decimal(str(c.beyond_rate))) ** (1 + (elapsed - 1) // 12)

    result = []
    for month in range(12):
        offset = (contract_year - 1) * 12 + month
        month_index = profile.start.year * 12 + profile.start.month - 1 + offset
        when = date(month_index // 12, month_index % 12 + 1, 1)
        wage = wage_at(s, when)
        assumption = when > date.fromisoformat(s["valid_until"])
        factor = wage / baseline
        factor *= assumed_factor(when) / assumed_factor(profile.start)
        adjusted = (salary * factor).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        delta = adjusted - salary
        salary_cost = delta * c.covered_quantity
        oncost = salary_cost * Decimal(str(c.oncost_rate))
        result.append(
            {
                "month": when.isoformat(),
                "workers": c.covered_quantity,
                "starting_salary": float(salary),
                "reference_wage_at_contract_start": float(baseline),
                "published_reference_wage": float(wage),
                "salary_factor": float(factor),
                "published_valid_until": s["valid_until"],
                "adjusted_salary": float(adjusted),
                "salary_change": float(salary_cost),
                "employer_oncost_change": float(oncost),
                "basis": "Officer assumption beyond published period"
                if assumption
                else "Published schedule ratio applied by owner budgeting method",
                "source": s["source"],
                "schedule_id": s["id"],
                "verified_on": s["verified_on"],
            }
        )
    return result
