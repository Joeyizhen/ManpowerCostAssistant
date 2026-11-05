"""Alternative proposal entry into shared budgeting decisions; originals stay immutable."""

from services.cost_routing import recorded_route
from services.decision_basis import meaningful, record_basis, retained_basis
from services.future_groups import general_proposal, general_reference
from services.models import GATES
from services.workflow import confirm, missing_for_gate


def next_decision(p):
    for step, gate in [(1, "plan"), (3, "base"), (4, "escalation")]:
        if gate not in p.plan.confirmations:
            return step
    return 5


def seed_supplied_pwm_details(p):
    import re

    for role in p.plan.roles:
        if (
            role.pwm
            or recorded_route(role)["route"] != "pwm"
            or p.drafts.get("pwm_source_seeded", {}).get(role.id)
        ):
            continue
        notes = role.duties_notes
        salary = re.search(r"supplied salary component:\s*SGD\s*([\d,]+(?:\.\d+)?)", notes, re.I)
        workers = re.search(r"covered workers:\s*(\d+)", notes, re.I)
        if salary and workers:
            source = next(
                (r.get("Source location") for r in p.original_rows if r["id"] == role.id),
                "Supplied proposal remarks",
            )
            p.plan.basis_drafts.setdefault("pwm_" + role.id, {}).update(
                starting_salary=float(salary[1].replace(",", "")),
                covered_quantity=int(workers[1]),
                salary_source=source + "; explicitly supplied salary component",
                applicability_basis=notes,
            )
            p.drafts.setdefault("pwm_source_seeded", {})[role.id] = True


def supplied_method(p, role):
    row = next((r for r in p.original_rows if r["id"] == role.id), {})
    return row.get("Proposed method") or (
        "Supplied yearly prices"
        if row.get("Yearly rates")
        else "General annual increase"
        if row.get("Annual increase (%)") is not None
        else "Unanswered"
    )


def material_checks(p, records):
    from services.manpower_checks import quantity_discrepancy

    findings = []
    for doc in p.original_documents:
        for index, item in enumerate(doc.get("unmatched_assumptions", [])):
            key = doc["sha256"][:12] + "-" + str(index)
            if key not in p.drafts.get("group_resolutions", {}):
                findings.append(
                    {
                        "Role": "Proposal group: " + item["target"],
                        "Issue": "The supplied group could not be assigned safely to deployment rows.",
                        "Next action": "Select the intended roles; no assumption was applied by default.",
                        "kind": "scope",
                        "role_id": key,
                        "assumption": item,
                    }
                )
    decisions = p.drafts.get("method_decisions", {})
    for role in p.plan.roles:
        if not role.included:
            continue
        row = next((r for r in p.original_rows if r["id"] == role.id), {})
        route, supplied = (
            recorded_route(role),
            p.drafts.get("input_resolutions", {}).get(role.id, {}).get("method", supplied_method(p, role)),
        )
        resolved = decisions.get(role.id)
        if (
            route["route"] == "pwm"
            and supplied.casefold() in ("pwm", "pwm salary progression")
            and (row.get("Annual increase (%)") not in (None, 0) or row.get("Yearly rates"))
            and role.id not in p.drafts.get("input_resolutions", {})
        ):
            findings.append(
                {
                    "Role": role.label,
                    "Issue": "PWM and a full-unit future increase or price profile are supplied for the same role.",
                    "Next action": "Confirm salary-only PWM treatment at Annual changes; do not add the general increase to that salary component.",
                    "kind": "pwm_overlap",
                    "role_id": role.id,
                }
            )
        if row.get("Assumption conflict") and role.id not in p.drafts.get("input_resolutions", {}):
            findings.append(
                {
                    "Role": role.label,
                    "Issue": "Shared and individual future assumptions conflict.",
                    "Next action": "Choose the intended supplied assumption; neither is selected automatically.",
                    "kind": "conflict",
                    "role_id": role.id,
                }
            )
        if (
            supplied.casefold() in ("pwm", "pwm salary progression")
            and route["route"] == "general"
            and not (resolved and resolved.get("accepted") == "General annual increase")
        ):
            ref = general_reference(p.plan, records, [role.id])
            action = (
                f"Review a general annual increase of {ref['average']:.2%} from the shared reference, then accept or choose another value."
                if ref["available"]
                else "Enter an explicit general annual assumption; no supported reference percentage is available."
            )
            findings.append(
                {
                    "Role": role.label,
                    "Issue": "The proposal requests PWM; this role is marked PWM applies? = No in Standard Roles.",
                    "Next action": action,
                    "kind": "wrong_method",
                    "role_id": role.id,
                }
            )
        if (
            supplied.casefold()
            not in (
                "pwm",
                "pwm salary progression",
                "general annual increase",
                "supplied yearly prices",
                "unanswered",
            )
            and not resolved
        ):
            findings.append(
                {
                    "Role": role.label,
                    "Issue": "The supplied escalation method needs interpretation: " + supplied,
                    "Next action": "Choose the intended method; the original wording stays preserved.",
                    "kind": "method",
                    "role_id": role.id,
                }
            )
        if route["route"] == "unresolved":
            findings.append(
                {
                    "Role": role.label,
                    "Issue": "Standard Role/PWM classification is unresolved.",
                    "Next action": "Resolve classification at Annual changes; the starting-rate mapping remains separate.",
                    "kind": "mapping",
                    "role_id": role.id,
                }
            )
        if row.get("Yearly rates") and row.get("Annual increase (%)") not in (None, 0) and not resolved:
            findings.append(
                {
                    "Role": role.label,
                    "Issue": "Quoted yearly prices and an additional general increase cover the same charge.",
                    "Next action": "Choose which supplied treatment to retain; do not stack them.",
                    "kind": "overlap",
                    "role_id": role.id,
                }
            )
        if issue := quantity_discrepancy(role, role.current_quantity is not None):
            findings.append(
                {
                    "Role": role.label,
                    "Issue": issue,
                    "Next action": "Correct the number or the operational remarks in Deployment.",
                    "kind": "deployment",
                    "role_id": role.id,
                }
            )
    return findings


def resolve_conflict(p, rid, assumption, records, officer):
    candidate = p.model_copy(deep=True)
    _resolve_conflict(candidate, rid, assumption, records, officer)
    p.__dict__.update(candidate.__dict__)


def _resolve_conflict(p, rid, assumption, records, officer):
    from services.proposals import apply_yearly
    from services.workflow import apply_change

    role = next(r for r in p.plan.roles if r.id == rid)
    selected = dict(assumption)
    payload = role.model_dump(mode="json")
    payload.update(
        pwm=None,
        escalation=[],
        escalation_mode="assumption",
        schedule_id=None,
        escalation_reason="Officer selected the supplied assumption at " + selected["source"],
    )
    apply_change(p.plan, "role", payload, "Officer resolved conflicting supplied future assumptions", officer)
    if selected["method"] == "General annual increase" and selected.get("percent") is not None:
        preview = correction_preview(p, rid, records, selected["percent"])
        accept_correction(p, preview, records, officer)
    elif selected["method"] == "Supplied yearly prices":
        apply_yearly(p, rid, [], selected.get("yearly_rates") or [], selected["source"], officer)
    p.drafts.setdefault("input_resolutions", {})[rid] = selected
    p.drafts.setdefault("method_decisions", {})[rid] = {
        "accepted": selected["method"],
        "reason": "Officer selected the supplied assumption at " + selected["source"],
    }


def confirm_deployment(p, records, officer):
    candidate = p.plan.model_copy(deep=True)
    errors = [error for gate in GATES[:4] for error in missing_for_gate(candidate, gate, records)]
    # A supplied operational brief can support related workload allowances once,
    # rather than asking for the same rationale for every proposal row.
    for role in candidate.roles:
        if role.quantity_unit not in ("headcount", "FTE"):
            errors.append(f"{role.label}: confirm headcount or FTE.")
        if role.included and not retained_basis(candidate, role, "quantity"):
            explanation = (
                role.duties_notes if meaningful(role.duties_notes) else candidate.profile.description
            )
            if meaningful(explanation):
                record_basis(
                    candidate,
                    "quantity",
                    [role.id],
                    "Supplied proposal deployment",
                    explanation,
                    "Officer-confirmed proposal interpretation and deployment review",
                    "officer assumption",
                    officer,
                )
    # Re-evaluate after reusing the already supplied basis.
    errors = [error for gate in GATES[:4] for error in missing_for_gate(candidate, gate, records)] + [
        f"{r.label}: confirm headcount or FTE."
        for r in candidate.roles
        if r.included and r.quantity_unit not in ("headcount", "FTE")
    ]
    errors += [
        f"{r.label}: headcount must be a whole number of people."
        for r in candidate.roles
        if r.included
        and r.quantity_unit == "headcount"
        and r.quantity is not None
        and not float(r.quantity).is_integer()
    ]
    if errors:
        raise ValueError("\n".join(dict.fromkeys(errors)))
    for gate in GATES[:4]:
        confirm(candidate, gate, officer, records)
    candidate.ui_step = 3
    p.plan = candidate


def correction_preview(p, rid, records, percent=None):
    role = next(r for r in p.plan.roles if r.id == rid)
    if recorded_route(role)["route"] != "general":
        raise ValueError(
            "This correction is available only for a role explicitly routed to general annual increase."
        )
    ref = general_reference(p.plan, records, [rid])
    if percent is None:
        if not ref["available"]:
            raise ValueError(
                "No supported general annual reference is available. Enter an officer assumption explicitly."
            )
        percent = round(ref["average"] * 100, 2)
    percent = round(float(percent), 2)
    from services.calculations import budget

    estimate = p.plan.model_copy(deep=True)
    proposed = role.model_copy(deep=True)
    proposed.pwm = None
    proposed.escalation_mode, proposed.schedule_id = "assumption", None
    proposed.escalation = [0] + [percent / 100] * (p.plan.profile.years - 1)
    estimate.roles = [proposed]
    try:
        proposed_cost = budget(estimate, records)["contract_total"]
    except ValueError:
        proposed_cost = None
    original_row = next((r for r in p.original_rows if r["id"] == rid), {})
    return {
        "role_id": rid,
        "Role": role.label,
        "Original method": supplied_method(p, role),
        "Proposed method": "General annual increase",
        "Selected annual increase (%)": percent,
        "Original annual increase (%)": original_row.get("Annual increase (%)"),
        "Proposed role contract cost (SGD)": proposed_cost,
        "Reason": "Standard Roles marks PWM applies? = No; general tender manpower changes apply to this project route.",
        "reference_available": ref["available"],
        "reference": {
            k: ref.get(k)
            for k in ("available", "average", "minimum", "maximum", "dataset_id", "method", "sample_count")
        },
        "plan_version": p.plan.version,
    }


def accept_correction(p, preview, records, officer):
    role = next(r for r in p.plan.roles if r.id == preview["role_id"])
    fresh = correction_preview(p, role.id, records, preview["Selected annual increase (%)"])
    if preview.get("plan_version", p.plan.version) != p.plan.version or preview["reference"].get(
        "dataset_id"
    ) != fresh["reference"].get("dataset_id"):
        raise ValueError(
            "The plan or reference source changed. Preview this correction again before accepting it."
        )
    candidate = p.plan.model_copy(deep=True)
    revised = next(r for r in candidate.roles if r.id == role.id)
    revised.pwm = None
    ref = fresh["reference"]
    percent = fresh["Selected annual increase (%)"]
    backed = ref["available"] and round(ref["minimum"] * 100, 2) <= percent <= round(ref["maximum"] * 100, 2)
    candidate = general_proposal(candidate, records, [role.id], percent, fresh["Reason"], "", backed, officer)
    p.plan = candidate
    p.drafts.setdefault("method_decisions", {})[role.id] = {
        "original": fresh["Original method"],
        "accepted": "General annual increase",
        "percent": percent,
        "reason": fresh["Reason"],
    }
    p.history.append(
        {
            "action": "Officer accepted future-method correction",
            "role_id": role.id,
            "original": fresh["Original method"],
            "accepted": "General annual increase",
            "percent": percent,
            "reason": fresh["Reason"],
            "version": p.plan.version,
        }
    )
