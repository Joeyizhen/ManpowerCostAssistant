"""Deterministic quantities and prices. No LLM arithmetic or inferred wage breakdown."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import ceil

from services.evidence import quoted_schedule
from services.models import Coverage, Plan
from services.pwm import salary_months, validate_pwm


def D(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Required numeric input must be finite")
    return result


def cents(value):
    return float(D(value).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))


def monthly_role_cost(role):
    if not role.included:
        return 0.0
    if role.quantity is None or role.quantity <= 0 or role.rate is None:
        return None
    if role.quantity_unit == "posts":
        raise ValueError("Convert posts to headcount or FTE before costing")
    return cents(D(role.quantity) * D(role.rate))


def coverage_quantity(c: Coverage):
    if c.capacity_basis == "net" and c.relief_factor != 1:
        raise ValueError("Net productive hours already include absence: relief factor must be 1")
    weekly = c.hours_per_day * c.days_per_week * c.simultaneous_posts
    baseline = weekly / c.capacity_hours
    fte = baseline * c.relief_factor
    return {
        "weekly_coverage_hours": weekly,
        "employee_capacity_hours": c.capacity_hours,
        "capacity_basis": c.capacity_basis,
        "baseline_fte": baseline,
        "relief_factor": c.relief_factor,
        "fte": fte,
        "personnel": ceil(fte),
        "suggested_quantity": ceil(fte) if c.round_to_personnel else fte,
        "method": "coverage hours / employee capacity × relief factor; whole personnel only if explicitly selected",
        "limitation": "Indicative quantity, not proof of feasible shifts/roster. Hours and relief are officer assumptions.",
    }


def anniversary(start: date, offset: int):
    try:
        return start.replace(year=start.year + offset)
    except ValueError:
        return start.replace(year=start.year + offset, day=28)


def budget(plan: Plan, records: list[dict], scenario_delta=0):
    p = plan.profile
    if p.costing_start is None or p.base_years is None or p.option_years is None or not 1 <= p.years <= 20:
        raise ValueError("Confirm start date, base years and option years (maximum total 20)")
    if not any(r.included for r in plan.roles):
        raise ValueError("Include at least one role")
    rows = []
    for role in plan.roles:
        if not role.included:
            continue
        from services.cost_routing import route_errors

        if errors := route_errors(role):
            raise ValueError("; ".join(errors))
        if role.quantity is None or role.quantity <= 0 or role.rate is None:
            raise ValueError(f"{role.label}: positive quantity and rate are required")
        if role.quantity_unit == "posts":
            raise ValueError(f"{role.label}: convert posts to explicit headcount or FTE before costing")
        if role.quantity_unit == "headcount" and any(
            not float(q).is_integer() for q in [role.quantity, *role.yearly_quantities]
        ):
            raise ValueError(f"{role.label}: fractional quantities require an explicit FTE basis")
        if role.yearly_quantities and len(role.yearly_quantities) != p.years:
            raise ValueError(f"{role.label}: every contract year needs a quantity")
        if len(role.escalation) != p.years or role.escalation[0] != 0:
            raise ValueError(f"{role.label}: escalation profile must cover all years, starting at zero")
        policy_keys = [
            (x.effective_date, x.affected_component.casefold(), x.source.casefold()) for x in role.policies
        ]
        if len(policy_keys) != len(set(policy_keys)):
            raise ValueError(
                f"{role.label}: duplicate component adjustment would double count the same source/effective date"
            )
        quotes = None
        if role.policies and p.start is None:
            raise ValueError("An exact contract start date is required for effective-date policy adjustments")
        if role.escalation_mode == "quoted schedule":
            if p.start is None or p.start.month != 1 or p.start.day != 1:
                raise ValueError(
                    "Calendar-year quotes require a 1 January contract start; otherwise use disclosed assumptions"
                )
            if not role.schedule_id or not role.mapped_role:
                raise ValueError("Select a mapped role and quoted schedule")
            quotes = quoted_schedule(
                records, role.schedule_id, role.mapped_role, list(range(p.start.year, p.start.year + p.years))
            )
            if cents(role.rate) != cents(quotes[0]["unit_rate_monthly"]):
                raise ValueError(
                    f"{role.label}: selected base rate must equal the retrieved target-year quote"
                )
            if any(role.escalation):
                raise ValueError(
                    "Quoted prices already price each target year; extra escalation is prohibited"
                )
        if role.pwm:
            validate_pwm(role, p)
        previous_rate = D(role.rate)
        for year in range(1, p.years + 1):
            start = anniversary(p.costing_start, year - 1)
            end = anniversary(p.costing_start, year)
            quantity = D(role.yearly_quantities[year - 1] if role.yearly_quantities else role.quantity)
            change = role.escalation[year - 1] + (
                scenario_delta if year > 1 and quotes is None and not role.pwm else 0
            )
            if not -0.5 <= change <= 1:
                raise ValueError("Scenario escalation exceeds permitted numeric bounds")
            monthly = (
                D(quotes[year - 1]["unit_rate_monthly"])
                if quotes
                else (previous_rate * (1 + D(change))).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            )
            policy_annual = D(0)
            for policy in role.policies:
                if not policy.basis_confirmed or not policy.overlap_reviewed:
                    raise ValueError(
                        f"{role.label}: confirm policy component basis and overlap review before inclusion"
                    )
                if quotes:
                    raise ValueError(
                        "Policy adjustments cannot be added to quoted future prices without separate component evidence"
                    )
                effective = max(start, policy.effective_date)
                proportion = D(max(0, (end - effective).days)) / D((end - start).days)
                policy_annual += D(policy.annual_monthly_increment) * 12 * proportion
            before_policy = cents(quantity * monthly * 12)
            policy_cost = cents(quantity * policy_annual)
            pwm_months = salary_months(role, p, year) if role.pwm else []
            pwm_salary = cents(sum((D(m["salary_change"]) for m in pwm_months), D(0)))
            pwm_oncost = cents(sum((D(m["employer_oncost_change"]) for m in pwm_months), D(0)))
            pwm_cost = cents(D(pwm_salary) + D(pwm_oncost))
            annual = cents(D(before_policy) + D(policy_cost) + D(pwm_cost))
            flat = cents(quantity * D(role.rate) * 12)
            rows.append(
                {
                    "role_id": role.id,
                    "role": role.label,
                    "year": year,
                    "period_start": start.isoformat(),
                    "period_end": (end - timedelta(days=1)).isoformat(),
                    "optional": year > p.base_years,
                    "quantity": float(quantity),
                    "base_rate": role.rate,
                    "escalation": change,
                    "factor": 1 + change,
                    "monthly_unit_rate": float(monthly),
                    "annual_before_policy": before_policy,
                    "policy_annual_per_head": float(policy_annual),
                    "policy_cost": policy_cost,
                    "annual_cost": annual,
                    "pwm_salary_cost": pwm_salary,
                    "pwm_oncost_cost": pwm_oncost,
                    "pwm_cost": pwm_cost,
                    "pwm_months": pwm_months,
                    "flat_baseline": flat,
                    "excess_over_baseline": cents(D(annual) - D(flat)),
                    "source_record": quotes[year - 1]["record_id"]
                    if quotes
                    else (
                        "Official schedule salary-ratio budgeting method; see PWM monthly trace"
                        if role.pwm
                        else "Officer-confirmed escalation assumption"
                    ),
                }
            )
            previous_rate = monthly
    annuals = [cents(sum(D(r["annual_cost"]) for r in rows if r["year"] == y)) for y in range(1, p.years + 1)]
    total = cents(sum(map(D, annuals)))
    baseline = cents(sum(D(r["flat_baseline"]) for r in rows))
    additions = [
        cents(sum(D(r["excess_over_baseline"]) for r in rows if r["year"] == y))
        for y in range(1, p.years + 1)
    ]
    if cents(D(baseline) + sum(map(D, additions))) != total:
        raise ArithmeticError("Waterfall does not reconcile")
    return {
        "rows": rows,
        "annual_totals": annuals,
        "contract_total": total,
        "base_total": cents(sum(map(D, annuals[: p.base_years]))),
        "option_total": cents(sum(map(D, annuals[p.base_years :]))),
        "waterfall": {
            "baseline": baseline,
            "additions": additions,
            "total": total,
            "method": "Sum confirmed yearly quantities × Year 1 rate × 12; add each year's excess. Includes policy amounts.",
        },
        "rounding": "Monthly unit rate and PWM salary per worker rounded to cents; annual salary/on-cost and role/year policy aggregates rounded separately, then summed. Payroll statutory rounding is not inferred.",
        "period_basis": p.period_basis,
    }


def preliminary(plan: Plan):
    rows = []
    for r in plan.roles:
        if r.included:
            if r.quantity is None or r.quantity <= 0 or r.rate is None:
                raise ValueError("Each included role needs a quantity and rate")
            if r.quantity_unit == "posts":
                raise ValueError(f"{r.label}: convert posts to headcount or FTE before costing")
            if r.quantity_unit == "headcount" and not float(r.quantity).is_integer():
                raise ValueError(f"{r.label}: fractional quantities require an explicit FTE basis")
            rows.append(
                {
                    "role": r.label,
                    "quantity": r.quantity,
                    "rate": r.rate,
                    "monthly": cents(D(r.quantity) * D(r.rate)),
                    "year_1": cents(D(r.quantity) * D(r.rate) * 12),
                }
            )
    return {
        "rows": rows,
        "monthly": cents(sum(D(r["monthly"]) for r in rows)),
        "year_1": cents(sum(D(r["year_1"]) for r in rows)),
        "label": "Preliminary base-year budget — contract escalation and policy adjustments pending",
    }


def sensitivity(plan, records):
    result = []
    for name, delta in [("Lower", -0.01), ("Central", 0), ("Higher", 0.01)]:
        try:
            output = budget(plan, records, delta)
        except ValueError as e:
            result.append(
                {
                    "scenario": name,
                    "annual_change_delta": delta,
                    "annual_totals": [],
                    "contract_total": None,
                    "method": f"Scenario unavailable: {e}; no clamping applied.",
                }
            )
            continue
        result.append(
            {
                "scenario": name,
                "annual_change_delta": delta,
                "annual_totals": output["annual_totals"],
                "contract_total": output["contract_total"],
                "method": "Shift each assumed Year 2+ rate change by ±1 percentage point. Quantities, quoted prices, PWM salary paths and additive nominal policies unchanged. Not confidence intervals.",
            }
        )
    return result
