"""Shared future-cost proposals; preview is independent of the recorded plan."""

from services.calculations import budget
from services.decision_basis import record_basis, retained_basis
from services.evidence import escalation_benchmark, stats
from services.workflow import apply_change

GENERAL_COHORT = {
    "id": "general-fm-office-awarded-v1",
    "scope": "Office FM",
    "status": "awarded",
    "roles": (
        "Facilities Manager",
        "Assistant Facilities Manager",
        "Admin Executive",
        "Technician",
        "BMS Engineer",
        "Property Officer",
        "Environmental Engineer",
        "Customer Service Officer",
    ),
}


def general_reference(plan, records, role_ids):
    # Fixed reference cohort: deployment titles never expand or narrow the sample.
    eligible = [
        r
        for r in records
        if r.get("scope") == GENERAL_COHORT["scope"]
        and r.get("standard_role") in GENERAL_COHORT["roles"]
        and r.get("validation_status") == "validated"
        and r.get("award_status") == GENERAL_COHORT["status"]
        and r.get("currency") == "SGD"
        and r.get("rate_basis") == "inclusive monthly per head"
        and "manpower" in r.get("inclusions", "").casefold()
        and not any(
            term in (r.get("scope", "") + " " + r.get("inclusions", "")).casefold()
            for term in ("full trade", "full service", "trade/service")
        )
    ]
    schedules, pairs, issues = {}, [], []
    for title in GENERAL_COHORT["roles"]:
        bm = escalation_benchmark(eligible, title, GENERAL_COHORT["status"], GENERAL_COHORT["scope"])
        for row in bm["schedules"]:
            schedules[row["schedule_id"]] = row
        pairs.extend(bm["changes"])
        issues.extend(bm["issues"])
    record_ids = sorted({rid for pair in pairs for rid in pair["record_ids"]})
    return {
        **stats([s["median_yoy"] for s in schedules.values()]),
        "gaps": [],
        "cohort": GENERAL_COHORT,
        "schedules": list(schedules.values()),
        "issues": issues,
        "record_ids": record_ids,
        "records": [r for r in eligible if r["record_id"] in record_ids],
        "method": "Fixed general FM cohort v1: validated, awarded Office FM schedules in SGD, inclusive monthly per head, for the listed general FM roles. One median consecutive-year unit-rate change per distinct manpower-only schedule; arithmetic average of those medians with equal schedule weights. Minimum and maximum use the same medians. At least three distinct schedules are required overall. Duplicate contract years and nonconsecutive or changed-basis pairs are excluded. Deployment titles do not determine sample membership or add weight.",
        "limitations": "Synthetic demonstration tender manpower charges, not market rates, employee wage increments or realised inflation. Office FM is the declared reference scope; other scopes, submitted bids and full trade/service prices are excluded. A general budgeting reference does not establish role-specific forecasts or PWM eligibility.",
    }


def general_proposal(
    plan, records, role_ids, percent, reason, source, reference_selected, officer, yearly_percent=None
):
    if not role_ids:
        return plan.model_copy(deep=True)
    if plan.profile.years == 1:
        percent, reason, source, reference_selected = (
            0.0,
            "Single contract year: retain confirmed starting monthly charges; no annual anniversary increase applies.",
            "Confirmed contract period",
            False,
        )
    if percent is None and yearly_percent is not None:
        percent = 0.0  # The explicit yearly table supplies the profile independently.
    if percent is None or not -50 <= percent <= 100:
        raise ValueError("Enter an annual increase from -50% to 100%, including explicit zero.")
    percent = round(percent, 2)
    profile = [0.0] + [percent / 100] * (plan.profile.years - 1)
    if yearly_percent is not None:
        if (
            len(yearly_percent) != plan.profile.years
            or yearly_percent[0] != 0
            or any(not -50 <= x <= 100 for x in yearly_percent)
        ):
            raise ValueError(
                "Enter one percentage per contract year, starting with zero; each must be from -50% to 100%."
            )
        profile = [round(x, 2) / 100 for x in yearly_percent]
        reference_selected = False
    optional_note = reason.strip()
    selected = [r for r in plan.roles if r.included and r.id in role_ids]
    if len(selected) != len(set(role_ids)) or any(r.pwm for r in selected):
        raise ValueError("General increase cannot include a role with active PWM salary progression.")
    bm = general_reference(plan, records, role_ids)
    if reference_selected:
        if (
            not bm["available"]
            or not round(bm["minimum"] * 100, 2) - 1e-10 <= percent <= round(bm["maximum"] * 100, 2) + 1e-10
        ):
            raise ValueError("A supported selection must be within the observed reference range.")
        reason = "Comparable manpower-only schedule reference: " + bm["method"]
        source = ", ".join(bm["record_ids"])
    else:
        reason = (
            "Officer-entered yearly manpower cost assumptions"
            if yearly_percent is not None
            else f"Officer-entered annual manpower cost assumption: {percent:.2f}% compounded from Year 2"
        ) + ". Supporting note/document is optional; no independent verification is implied."
        if optional_note:
            reason += " Officer note: " + optional_note
    candidate = plan.model_copy(deep=True)
    changed = []
    for role in selected:
        prior = retained_basis(plan, role, "escalation")
        if (
            role.escalation == profile
            and role.escalation_mode == "assumption"
            and prior
            and prior.explanation == reason
            and prior.source == source
        ):
            continue
        payload = role.model_dump(mode="json")
        payload.update(
            escalation=profile, escalation_mode="assumption", schedule_id=None, escalation_reason=reason
        )
        apply_change(
            candidate,
            "role",
            payload,
            "Shared annual increase selected; starting allowance retained",
            officer,
        )
        changed.append(role.id)
    if changed:
        record_basis(
            candidate,
            "escalation",
            changed,
            "Comparable database reference" if reference_selected else "Custom annual increase",
            reason,
            source,
            "sourced evidence" if reference_selected else "officer assumption",
            officer,
        )
        basis = candidate.decision_bases[-1]
        for detail in basis.snapshots.values():
            detail["selected_percent"] = percent if yearly_percent is None else None
            detail["yearly_percent"] = [round(x * 100, 2) for x in profile]
            detail["optional_note"] = optional_note
            detail["applicable_years"] = list(range(2, plan.profile.years + 1))
            detail["reference_data"] = bm if reference_selected else {"optional_reference": source}
    candidate.basis_drafts.pop("common_future", None)
    return candidate


def impact(plan, records):
    result = budget(plan, records)
    baseline = sum(r["flat_baseline"] for r in result["rows"])
    return {
        "Contract": result["contract_total"],
        "Base": result["base_total"],
        "Option": result["option_total"],
        "Change from flat starting charges": round(result["contract_total"] - baseline, 2),
    }
