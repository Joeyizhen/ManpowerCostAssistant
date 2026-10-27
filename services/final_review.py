"""Read-only final-review views built from the existing calculation and workflow rules."""

from services.calculations import D, budget, cents, sensitivity
from services.decision_basis import basis_errors, meaningful, retained_basis
from services.models import GATES, Finding
from services.workflow import confirm, findings, missing_for_gate, requires_decision

GATE_STEPS = {
    "profile": 0,
    "responsibilities": 2,
    "quantities": 1,
    "plan": 2,
    "rates": 3,
    "base": 3,
    "escalation": 4,
}
STEP_NAMES = {
    0: "Contract context",
    1: "Deployment inputs",
    2: "Deployment review",
    3: "Starting rates",
    4: "Future cost changes",
    5: "Your manpower budget",
}
BASIS_STEPS = {"quantity": 1, "rate": 3, "escalation": 4, "policy": 4}


def reviewed(finding):
    return bool(
        finding.officer.strip()
        and finding.justification.strip()
        and finding.justification != "Officer justification was not provided."
    )


def finding_step(finding):
    if finding.code == "rate_range" or finding.code in ("mapping", "thin_evidence", "unmatched"):
        return 3
    if finding.code.startswith(("pwm_", "policy_")) or finding.code == "unusual_escalation":
        return 4
    return 1


def error_step(message):
    text = message.casefold()
    if "edited finding" in text:
        return 5
    if any(
        x in text
        for x in (
            "pwm",
            "salary",
            "escalation",
            "annual change",
            "annual allowance",
            "yearly",
            "future",
            "policy",
            "schedule",
        )
    ):
        return 4
    if any(x in text for x in ("monthly", "rate", "allowance", "quotation", "pricing")):
        return 3
    if any(x in text for x in ("quantity", "quantities", "headcount", "fte", "posts", "role")):
        return 1
    return 0


def rationale_for(plan, finding):
    if reviewed(finding):
        return finding.justification
    role = next((r for r in plan.roles if r.id == finding.role_id), None)
    if role is None:
        return ""
    kind = (
        "rate"
        if finding.code == "rate_range"
        else "escalation"
        if finding.code == "unusual_escalation"
        else None
    )
    if kind is None:
        return ""
    prior = retained_basis(plan, role, kind)
    reason = (
        prior.snapshots[role.id].get("pricing_rationale", prior.explanation)
        if prior
        else getattr(role, kind + "_reason", "")
    )
    if meaningful(reason) and not reason.startswith(
        ("Officer budgeting allowance:", "Officer selected constant annual change")
    ):
        return reason
    return ""


def review_state(plan, records, pending_errors=()):
    try:
        current = findings(plan, records)
    except ValueError as error:
        current = [
            Finding(
                id="invalid_saved_input",
                code="arithmetic",
                message=str(error),
                impact="Correct the invalid saved calculation input.",
                blocking=True,
            )
        ]
    actions = {}

    def add(step, kind, message, why):
        key = (step, kind)
        item = actions.setdefault(
            key,
            {
                "step": step,
                "kind": kind,
                "title": STEP_NAMES[step],
                "why": why,
                "messages": [],
                "findings": [],
            },
        )
        if message not in item["messages"]:
            item["messages"].append(message)
        return item

    bases = {kind: basis_errors(plan, kind, records) for kind in BASIS_STEPS}
    basis_messages = {e for messages in bases.values() for e in messages}
    seen_inputs = set()
    for gate in GATES[:7]:
        for message in missing_for_gate(plan, gate, records):
            if message not in basis_messages and message not in seen_inputs:
                seen_inputs.add(message)
                add(
                    GATE_STEPS[gate],
                    "inputs",
                    message,
                    "These inputs are needed to calculate or confirm the budget correctly.",
                )
    for kind, messages in bases.items():
        for message in messages:
            add(
                BASIS_STEPS[kind],
                "judgement",
                message,
                "The figures can be retained, but their financial or operational basis must be recorded beside the original decision.",
            )
    for message in pending_errors:
        pending_finding = next(
            (f for f in current if "edited finding decision:" in message and message.endswith(f.message)),
            None,
        )
        if pending_finding is not None:
            actions[(5, pending_finding.id)] = {
                "step": finding_step(pending_finding),
                "kind": "finding",
                "title": pending_finding.message,
                "why": "An edited response has not been recorded. Record it or revert to the previously saved decision.",
                "messages": [],
                "findings": [pending_finding.id],
            }
            continue
        add(
            error_step(message),
            "inputs",
            message,
            "Unrecorded edits must be applied or reverted before the displayed version can be confirmed.",
        )
    result, calculation_error = None, None
    try:
        result = budget(plan, records)
    except ValueError as error:
        calculation_error = str(error)
        existing = {m for a in actions.values() for m in a["messages"]}
        if calculation_error not in existing:
            add(
                error_step(calculation_error),
                "inputs",
                calculation_error,
                "A valid numeric budget is not yet available. Correct this input; an exception cannot bypass it.",
            )
    for f in current:
        if f.blocking:
            if not any(f.message in a["messages"] for a in actions.values()):
                add(error_step(f.message), "inputs", f.message, f.impact)
            continue
        if not requires_decision(f) or reviewed(f):
            continue
        step = finding_step(f)
        role = next((r for r in plan.roles if r.id == f.role_id), None)
        related_basis = bool(
            role
            and any(
                m.startswith(role.label + ":")
                for m in bases["rate" if step == 3 else "escalation" if step == 4 else "quantity"]
            )
        )
        if related_basis:
            item = add(step, "judgement", f.message, f.impact)
            if f.impact not in item["why"]:
                item["why"] += " " + f.impact
            item["findings"].append(f.id)
        else:
            actions[(5, f.id)] = {
                "step": step,
                "kind": "finding",
                "title": f.message,
                "why": f.impact,
                "messages": [],
                "findings": [f.id],
            }
    for gate, step in GATE_STEPS.items():
        if gate not in plan.confirmations and not any(
            a["step"] == step and a["kind"] != "finding" for a in actions.values()
        ):
            add(
                step,
                "confirmation",
                "Review and confirm the retained inputs in this step.",
                "The current budget needs the existing officer confirmation before final approval.",
            )
    candidate = plan.model_copy(deep=True)
    final_errors = list(pending_errors)
    try:
        if "validation" not in candidate.confirmations:
            confirm(candidate, "validation", "Final review check", records)
        confirm(candidate, "final", "Final review check", records)
    except ValueError as error:
        final_errors += str(error).splitlines()
    # Preserve any workflow safeguard not already explained by the actionable groups.
    if final_errors and not actions:
        for message in dict.fromkeys(final_errors):
            add(
                error_step(message),
                "inputs",
                message,
                "Resolve this validation requirement before confirming the budget.",
            )
    confirmed = "final" in plan.confirmations and not final_errors and not actions
    status = (
        "Confirmed"
        if confirmed
        else "Needs attention"
        if any(a["kind"] != "confirmation" for a in actions.values())
        else "Draft"
        if actions
        else "Ready for confirmation"
    )
    return {
        "result": result,
        "calculation_error": calculation_error,
        "actions": list(actions.values()),
        "findings": current,
        "final_errors": list(dict.fromkeys(final_errors)),
        "status": status,
        "confirmed": confirmed,
    }


def annual_breakdown(plan, result):
    from review_inputs import cost_components

    original, totals = cost_components(plan, result)
    rows, movements = [], []
    previous = None
    for src in original:
        other = cents(D(src["Other component adjustments"]) + D(src["Quoted future-price changes"]))
        row = {
            "Contract year": src["Contract year"],
            "Starting-rate manpower cost": src["Starting charges"],
            "Compounded annual manpower increase": src["Annual manpower increases"],
            "PWM increase": src["PWM salary progression"],
            "Other adjustments": other,
            "Total annual manpower cost": src["Total"],
            "Change from previous year (SGD)": None,
            "Change from previous year (%)": None,
        }
        if previous is not None:
            delta = cents(D(src["Total"]) - D(previous["Total"]))
            row["Change from previous year (SGD)"] = delta
            row["Change from previous year (%)"] = (
                float(D(delta) / D(previous["Total"]) * 100) if previous["Total"] else None
            )
            change = {
                "Contract year": src["Contract year"],
                "Deployment change at starting rates": cents(
                    D(src["Starting charges"]) - D(previous["Starting charges"])
                ),
                "Change in accumulated annual increase": cents(
                    D(src["Annual manpower increases"]) - D(previous["Annual manpower increases"])
                ),
                "Change in PWM increase": cents(
                    D(src["PWM salary progression"]) - D(previous["PWM salary progression"])
                ),
                "Change in other adjustments": cents(
                    D(other)
                    - D(previous["Other component adjustments"])
                    - D(previous["Quoted future-price changes"])
                ),
                "Total annual change": delta,
            }
            if (
                cents(
                    sum(
                        (
                            D(v)
                            for k, v in change.items()
                            if k not in ("Contract year", "Total annual change")
                        ),
                        D(0),
                    )
                )
                != delta
            ):
                raise ArithmeticError("Year-on-year change breakdown does not reconcile")
            movements.append(change)
        rows.append(row)
        previous = src
    return rows, movements


def sensitivity_rows(plan, records):
    affected = (
        [r for r in plan.roles if r.included and not r.pwm and r.escalation_mode == "assumption"]
        if plan.profile.years > 1
        else []
    )
    if not affected:
        return [], []
    cases = sensitivity(plan, records)
    selected = next(x["contract_total"] for x in cases if x["scenario"] == "Central")
    rows, profiles = [], []
    for case, title in zip(
        cases, ["Lower annual increase", "Selected annual increase", "Higher annual increase"], strict=True
    ):
        profile_groups = {}
        for role in affected:
            profile = tuple(
                round((x + (case["annual_change_delta"] if i else 0)) * 100, 2)
                for i, x in enumerate(role.escalation)
            )
            profile_groups.setdefault(profile, []).append(role.label)
        descriptions = []
        for values, labels in profile_groups.items():
            text = (
                f"{values[1]:.2f}% from Year 2"
                if len(set(values[1:])) == 1
                else "; ".join(f"Y{i + 1}: {v:.2f}%" for i, v in enumerate(values))
            )
            descriptions.append(text)
            profiles.append(
                {"Scenario": title, "Applicable manpower": "; ".join(labels), "Yearly increase": text}
            )
        total = case["contract_total"]
        difference = cents(D(total) - D(selected)) if total is not None else None
        rows.append(
            {
                "Scenario": title,
                "Annual increase / yearly profile": descriptions[0]
                if len(descriptions) == 1
                else "Varies by role; see profiles below",
                "Full contract budget": total,
                "Difference from selected (SGD)": difference,
                "Difference from selected (%)": float(D(difference) / D(selected) * 100)
                if difference is not None and selected
                else None,
                "Availability": "Available" if total is not None else case["method"],
            }
        )
    return rows, profiles


def deployment_rows(plan):
    return [
        {
            "Role": r.label,
            "Quantity": r.quantity,
            "Unit": r.quantity_unit,
            "Yearly quantities": list(r.yearly_quantities),
        }
        for r in plan.roles
        if r.included
    ]


def flat_cost_explanation(plan, result):
    totals = result["annual_totals"]
    if len(totals) < 2 or len(set(totals)) != 1:
        return ""
    roles = [r for r in plan.roles if r.included]
    unchanged = all(not r.yearly_quantities or len(set(r.yearly_quantities)) == 1 for r in roles)
    general = [r for r in roles if not r.pwm and r.escalation_mode == "assumption"]
    zero = bool(general) and all(
        len(r.escalation) == plan.profile.years and all(v == 0 for v in r.escalation[1:]) for r in general
    )
    added = any(
        r["pwm_cost"] or r["policy_cost"] or r["annual_before_policy"] != r["flat_baseline"]
        for r in result["rows"]
    )
    if unchanged and zero and not added:
        return "Costs remain constant because the selected annual increase is 0% and deployment is unchanged."
    if unchanged:
        return "Annual totals are unchanged under the recorded price, PWM and adjustment profiles. Compare the components below; offsetting changes may still be present."
    return "Annual totals remain flat because the recorded deployment and price changes offset each other. The deployment contribution is shown separately below."


def action_presentation(plan, action):
    details = {}
    for message in action["messages"]:
        role = next(
            (
                r
                for r in sorted(plan.roles, key=lambda r: len(r.label), reverse=True)
                if message.startswith(r.label + ":")
            ),
            None,
        )
        name = role.label if role else "Budget review"
        item = details.setdefault(
            name,
            {
                "Role": name,
                "What to check": [],
                "Selected monthly rate": role.rate if role and action["step"] == 3 else None,
            },
        )
        text = message.split(":", 1)[1].strip() if role else message
        if "financial basis" in text or "quotation or" in text:
            text = "Explain where this allowance comes from - for example, a supplier quotation or your budgeting judgement. The amount can be kept."
        elif "comparable typical range" in text:
            text += " This is a comparison flag, not proof that the price is wrong."
        item["What to check"].append(text)
    rows = [{**r, "What to check": " ".join(dict.fromkeys(r["What to check"]))} for r in details.values()]
    if action["step"] == 3 and action["kind"] == "judgement":
        summary = (
            f"{len(rows)} roles need a pricing basis. One quotation or explanation may cover several roles."
        )
        why = "A clear source or budgeting reason makes the EPV easier to explain. Comparison flags do not require you to change valid figures."
    else:
        summary = (
            "; ".join(action["messages"])
            if len(action["messages"]) <= 2
            else f"{len(rows)} inputs need attention in {action['title']}."
        )
        why = action["why"]
    return summary, why, rows


def source_summary(plan, records):
    """Readable officer evidence, without source-record dumps or internal identifiers."""
    from services.evidence import rate_benchmark

    rows, sources, active = [], [], []
    for role in plan.roles:
        if not role.included:
            continue
        bm = rate_benchmark(
            records, role.mapped_role, role.benchmark_year, role.benchmark_status, role.benchmark_scope
        )
        active.extend(bm["records"])
        basis = retained_basis(plan, role, "rate")
        reason = basis.explanation if basis else role.rate_reason
        reference = basis.source if basis else ""
        if reference and not all(
            x.strip() in {r["record_id"] for r in records} for x in reference.split(",")
        ):
            sources.append(reference)
        sources.extend(r["source"] for r in bm["records"] if r.get("source"))
        rows.append(
            {
                "Role": role.label,
                "Monthly rate (SGD)": f"{role.rate:,.2f}" if role.rate is not None else "Unanswered",
                "Basis": reason
                or (
                    "Comparable reference selection"
                    if role.rate_origin == "Synthetic benchmark selection"
                    else "Officer allowance; pricing explanation not recorded"
                ),
                "Reference year": str(role.benchmark_year or "Not recorded"),
                "Sample support": f"{bm['sample_count']} comparable schedules"
                if bm["sample_count"]
                else "No comparable rate reference",
            }
        )
    # Annual-increase selections may use a general cohort even when no role has a rate match.
    for basis in plan.decision_bases:
        if basis.kind == "escalation":
            if basis.source and not all(
                x.strip() in {r["record_id"] for r in records} for x in basis.source.split(",")
            ):
                sources.append(basis.source)
            for snapshot in basis.snapshots.values():
                ids = snapshot.get("reference_data", {}).get(
                    "record_ids", snapshot.get("reference_record_ids", snapshot.get("record_ids", []))
                )
                active.extend(r for r in records if r["record_id"] in ids)
                sources.extend(r["source"] for r in records if r["record_id"] in ids and r.get("source"))
    demo = any("synthetic" in r.get("data_origin", "").casefold() for r in active)
    return rows, list(dict.fromkeys(x for x in sources if x)), demo


def qualification_summary(plan, current):
    """Keep substantive qualifications and distinguish internal tagging from operational gaps."""
    texts, tagging, grouped = [], [], {}
    routine_labels = {
        "scenario": "Quantities are officer scenarios; no validated workload staffing rule is established",
        "mapping": "Benchmark mapping remains unverified",
        "unmatched": "No comparable starting-rate references are available",
        "thin_evidence": "Limited comparable rate samples",
        "quantity_reason": "A separate operational quantity explanation is not recorded",
        "change_reason": "Deployment changed without separate remarks",
    }
    unmatched = {f.role_id for f in current if f.code == "unmatched"}
    for finding in current:
        if finding.blocking or (
            requires_decision(finding) and finding.code != "proposal_capability" and not reviewed(finding)
        ):
            continue  # Already actionable above the tabs.
        if finding.code.startswith("basis_missing_"):
            continue
        if not reviewed(finding) and finding.code in routine_labels:
            if finding.code == "thin_evidence" and finding.role_id in unmatched:
                continue
            role = next((r for r in plan.roles if r.id == finding.role_id), None)
            grouped.setdefault(routine_labels[finding.code], []).append(
                role.label if role else "Recorded manpower"
            )
            continue
        if not reviewed(finding) and finding.code in {"requirements", "exclusions", "pwm_budget_method"}:
            continue  # Covered by the grouped deployment, exclusions and PWM summaries.
        if finding.code == "role_scope":
            role = next((r for r in plan.roles if r.id == finding.role_id), None)
            tagging.append(role.label if role else "Recorded roles")
            if reviewed(finding):
                texts.append(finding.justification)
            continue
        if "synthetic" in (finding.message + finding.impact).casefold():
            continue  # The active-data disclosure appears once above the tabs.
        text = finding.message
        if reviewed(finding):
            text += " Recorded decision: " + finding.justification
        elif finding.impact:
            text += " " + finding.impact
        texts.append(text)
    for concern, labels in grouped.items():
        texts.append(concern + ": " + "; ".join(dict.fromkeys(labels)) + ".")
    if tagging:
        texts.append(
            "Internal duty tagging is incomplete for: "
            + "; ".join(dict.fromkeys(tagging))
            + ". This alone does not establish that deployment is inadequate."
        )
    return list(dict.fromkeys(texts)) or ["No additional accepted qualifications are recorded."]
