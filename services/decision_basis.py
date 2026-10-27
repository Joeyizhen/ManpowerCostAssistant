"""Material decisions retain evidence classification and value-specific bases."""

import hashlib
import json
import re

from services.models import DecisionBasis


def meaningful(text):
    cleaned = re.sub(r"[^a-z0-9 ]", " ", text.casefold())
    words = cleaned.split()
    vague = {
        "need",
        "needs",
        "more",
        "less",
        "manpower",
        "staff",
        "staffing",
        "people",
        "pax",
        "required",
        "increase",
        "decrease",
        "because",
        "budget",
        "officer",
        "assumption",
        "selected",
        "rate",
        "change",
        "annual",
        "scenario",
        "constant",
        "confirmed",
        "by",
        "of",
        "the",
        "a",
        "and",
        "for",
        "to",
        "is",
        "we",
        "there",
        "much",
        "higher",
        "at",
        "it",
        "our",
        "looks",
        "quite",
        "good",
        "okay",
        "ok",
        "fine",
        "suitable",
        "appropriate",
        "enough",
        "adequate",
        "reasonable",
        "works",
        "best",
        "normal",
        "standard",
        "usual",
    }
    numbers = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "zero"}
    concrete = {w for w in words if w not in vague and w not in numbers and not w.isdigit()}
    # Judge a concrete cause or source, rather than requiring a writing length.
    # Spelled-out quantities and digits carry the same weight.
    return len(concrete) >= 2 or (bool(concrete) and any(w.isdigit() or w in numbers for w in words))


def snapshot(plan, role, kind):
    context = {"start": str(plan.profile.costing_start), "years": plan.profile.years}
    fields = {
        "quantity": [
            "label",
            "included",
            "quantity",
            "current_quantity",
            "quantity_unit",
            "yearly_quantities",
        ],
        "rate": [
            "quantity_unit",
            "rate_basis",
            "rate",
            "rate_origin",
            "benchmark_year",
            "mapped_role",
            "benchmark_scope",
            "benchmark_status",
        ],
        "escalation": [
            "rate",
            "quantity",
            "quantity_unit",
            "escalation",
            "escalation_mode",
            "schedule_id",
            "pwm",
        ],
        "policy": ["quantity", "rate", "policies", "pwm"],
    }[kind]
    data = role.model_dump(mode="json")
    if kind == "quantity":
        context["operating_context"] = plan.profile.description
        context["contract_kind"] = plan.contract_kind
        context["current_status"] = plan.current_deployment_status
    return {**context, **{key: data[key] for key in fields}}


def signature(plan, role, kind):
    return hashlib.sha256(json.dumps(snapshot(plan, role, kind), sort_keys=True).encode()).hexdigest()


def retained_basis(plan, role, kind):
    return next(
        (
            b
            for b in reversed(plan.decision_bases)
            if b.kind == kind and b.signatures.get(role.id) == signature(plan, role, kind)
        ),
        None,
    )


def record_basis(plan, kind, role_ids, category, explanation, source, classification, officer):
    from services.journey import working_draft
    from services.workflow import invalidate

    if not meaningful(explanation):
        raise ValueError(
            "Give a concrete operational cause, financial assumption or supporting quotation for this decision."
        )
    if classification == "sourced evidence" and not source.strip():
        raise ValueError(
            "Identify the quotation, record or official source; otherwise label this an officer assumption."
        )
    draft = working_draft(plan)
    roles = [r for r in draft.roles if r.id in role_ids]
    if not roles or len(roles) != len(set(role_ids)):
        raise ValueError("Select the affected roles.")
    basis = DecisionBasis(
        kind=kind,
        role_ids=role_ids,
        category=category,
        explanation=explanation.strip(),
        source=source.strip(),
        classification=classification,
        snapshots={r.id: snapshot(draft, r, kind) for r in roles},
        signatures={r.id: signature(draft, r, kind) for r in roles},
        periods=f"Contract years 1–{draft.profile.years}; start {draft.profile.costing_start}",
    )
    from services.evidence import load_records, rate_benchmark

    for role in roles:
        detail = basis.snapshots[role.id]
        if kind == "rate":
            bm = rate_benchmark(
                load_records(),
                role.mapped_role,
                role.benchmark_year,
                role.benchmark_status,
                role.benchmark_scope,
            )
            detail["reference_average"] = bm["average"]
            detail["reference_year"] = role.benchmark_year
        prior_change = next(
            (
                h.get("before")
                for h in reversed(plan.history)
                if h.get("kind") == "role" and h.get("before", {}) and h["before"].get("id") == role.id
            ),
            None,
        )
        detail["previous_recorded_values"] = prior_change
    prior = plan.version
    gate = {"quantity": "quantities", "rate": "rates", "escalation": "escalation", "policy": "escalation"}[
        kind
    ]
    invalidate(plan, gate, f"Recorded {kind} basis for {', '.join(r.label for r in roles)}", officer)
    if plan.working_notes.get("base_version") == prior:
        plan.working_notes["base_version"] = plan.version
    for item in plan.pending:
        if item["base_version"] == prior:
            item["base_version"] = plan.version
    plan.decision_bases.append(basis)


def basis_errors(plan, kind, records):
    from services.evidence import rate_benchmark

    errors = []
    for r in plan.roles:
        if not r.included and kind != "quantity":
            continue
        if retained_basis(plan, r, kind):
            continue
        if any(b.kind == kind and r.id in b.role_ids for b in plan.decision_bases):
            errors.append(
                f"{r.label}: the recorded {kind} basis predates changed values or context; review and record whether it still applies."
            )
            continue
        if kind == "quantity":
            if r.quantity is None:
                continue
            changed = (r.current_quantity is not None and r.quantity != r.current_quantity) or any(
                q != r.quantity for q in r.yearly_quantities
            )
            new = r.included and (plan.contract_kind == "new site / service" or r.current_quantity is None)
            if (changed or new) and not meaningful(r.duties_notes):
                # Existing meaningful explicit reasoning remains compatible, not generated table boilerplate.
                generated = r.quantity_reason.startswith("Officer-provided quantity in manpower table")
                if generated or not meaningful(r.quantity_reason):
                    errors.append(
                        f"{r.label}: explain {'the staffing change' if changed else 'the new-site quantity'} (a shared basis can cover related roles)."
                    )
        elif kind == "rate" and r.rate is not None:
            if (
                r.benchmark_year
                and plan.profile.costing_start
                and r.benchmark_year != plan.profile.costing_start.year
                and not meaningful(r.rate_notes)
            ):
                errors.append(
                    f"{r.label}: record whether and why the reference-year allowance is adjusted or retained for the contract start."
                )
            bm = rate_benchmark(
                records, r.mapped_role, r.benchmark_year, r.benchmark_status, r.benchmark_scope
            )
            if r.rate_origin == "Officer assumption" or not bm["available"]:
                generated = r.rate_reason.startswith("Officer budgeting allowance:")
                if generated or not meaningful(r.rate_reason):
                    errors.append(f"{r.label}: record the quotation or financial basis for this allowance.")
            elif abs(r.rate - round(bm["average"], 2)) > 0.005 and not meaningful(r.rate_reason):
                errors.append(f"{r.label}: explain the selected allowance against the reference average.")
        elif kind == "escalation" and not r.pwm:
            generated = r.escalation_reason.startswith("Officer selected constant annual change")
            if generated or not meaningful(r.escalation_reason):
                errors.append(f"{r.label}: explain the annual changes or selected yearly profile.")
        elif kind == "policy" and r.policies:
            errors.append(
                f"{r.label}: record the policy adjustment rationale and its non-overlapping component basis."
            )
    return errors


def trace_rows(plan, records):
    from services.calculations import budget

    try:
        costs = budget(plan, records)["rows"]
    except ValueError:
        costs = []
    rows = []
    for b in plan.decision_bases:
        for rid in b.role_ids:
            role = next((r for r in plan.roles if r.id == rid), None)
            current = bool(role and b.signatures.get(rid) == signature(plan, role, b.kind))
            detail = b.snapshots[rid]
            role_costs = [r for r in costs if r["role_id"] == rid]
            impact = None
            if role_costs and current:
                if b.kind == "quantity" and detail.get("current_quantity") is not None and role.quantity:
                    impact = round(
                        sum(
                            (r["annual_before_policy"] + r["policy_cost"])
                            * (r["quantity"] - detail["current_quantity"])
                            / r["quantity"]
                            for r in role_costs
                            if r["quantity"]
                        ),
                        2,
                    )
                elif b.kind == "policy":
                    impact = round(sum(r["policy_cost"] for r in role_costs), 2)
                elif b.kind == "escalation":
                    impact = round(sum(r["excess_over_baseline"] - r["policy_cost"] for r in role_costs), 2)
                elif b.kind == "rate" and detail.get("reference_average") is not None and role.rate:
                    impact = round(
                        sum(r["annual_before_policy"] for r in role_costs)
                        * (role.rate - detail["reference_average"])
                        / role.rate,
                        2,
                    )
            rows.append(
                {
                    "Decision": b.kind,
                    "Role ID": rid,
                    "Role": role.label if role else rid,
                    "Original / reference": detail.get("current_quantity")
                    if b.kind == "quantity"
                    else detail.get("reference_average")
                    if b.kind == "rate"
                    else detail.get("previous_recorded_values"),
                    "Recorded values": detail,
                    "Basis": b.explanation,
                    "Category": b.category,
                    "Classification": b.classification,
                    "Source": b.source,
                    "Period": b.periods,
                    "Cost effect (SGD)": impact,
                    "Effect basis": "Quantity change at selected unit charges (PWM worker allocation separate)"
                    if b.kind == "quantity"
                    else "Allowance difference versus reference average at selected quantities/general profile; component costs separate"
                    if b.kind == "rate"
                    else "Separate additive component cost"
                    if b.kind == "policy"
                    else "Future cost versus flat starting-rate baseline, excluding separate legacy policy additions",
                    "State": "Current" if current else "Superseded; retained history",
                    "Recorded": b.recorded_at,
                }
            )
    from services.evidence import escalation_benchmark, rate_benchmark

    for role in plan.roles:
        if not role.included:
            continue
        role_costs = [r for r in costs if r["role_id"] == role.id]
        for kind, explanation in (
            ("quantity", role.duties_notes or role.quantity_reason),
            ("rate", role.rate_reason),
            ("escalation", role.pwm.rationale if role.pwm else role.escalation_reason),
        ):
            if retained_basis(plan, role, kind):
                continue
            if (
                kind == "quantity"
                and plan.contract_kind == "existing contract"
                and role.current_quantity == role.quantity
            ):
                explanation = "Status quo: unchanged existing deployment. " + explanation
            source = "Officer-entered operating basis; not independently verified"
            original = (
                role.current_quantity if kind == "quantity" else role.rate if kind == "escalation" else None
            )
            proposed = (
                role.quantity
                if kind == "quantity"
                else role.escalation
                if kind == "escalation"
                else role.rate
            )
            if kind == "rate":
                bm = rate_benchmark(
                    records,
                    role.mapped_role,
                    role.benchmark_year,
                    role.benchmark_status,
                    role.benchmark_scope,
                )
                original = bm["average"]
                source = (
                    role.rate_notes
                    or ", ".join(r["record_id"] for r in bm["records"])
                    or "Unsupported allowance: officer assumption"
                )
            elif kind == "escalation":
                if role.pwm:
                    from services.pwm import get_schedule

                    source = (
                        get_schedule(role.pwm.schedule_id)["source"]
                        + "; salary component: "
                        + role.pwm.salary_source
                    )
                else:
                    eb = escalation_benchmark(
                        records, role.mapped_role, role.benchmark_status, role.benchmark_scope
                    )
                    source = eb["method"] + "; " + ", ".join(r["schedule_id"] for r in eb["schedules"])
            impact = (
                round(sum(r["excess_over_baseline"] - r["policy_cost"] for r in role_costs), 2)
                if kind == "escalation" and role_costs
                else None
            )
            rows.append(
                {
                    "Decision": kind,
                    "Role ID": role.id,
                    "Role": role.label,
                    "Original / reference": original,
                    "Recorded values": {
                        "proposed": proposed,
                        "unit": role.quantity_unit,
                        "quantity": role.quantity,
                        "reference_year": role.benchmark_year,
                    },
                    "Basis": explanation or "Basis not yet recorded",
                    "Category": "Retained role inputs",
                    "Classification": "officer assumption",
                    "Source": source,
                    "Period": f"Contract years 1–{plan.profile.years}",
                    "Cost effect (SGD)": impact,
                    "Effect basis": "Future cost above flat starting-rate baseline"
                    if kind == "escalation"
                    else "See annual role calculations; no unsupported counterfactual cost inferred",
                    "State": "Current retained inputs; not evidence verification",
                    "Recorded": "Retained project / revision history",
                }
            )
    if any(key != "_ui_controls" or value.get("values") for key, value in plan.basis_drafts.items()):
        rows.append(
            {
                "Decision": "Unapplied input drafts",
                "Role ID": "Project",
                "Role": "Project",
                "Original / reference": "Recorded plan remains the calculation basis",
                "Recorded values": plan.basis_drafts,
                "Basis": "Saved for continuation; these edits have not been applied or confirmed",
                "Category": "Draft",
                "Classification": "acknowledged uncertainty",
                "Source": "Officer input draft",
                "Period": "Not applied",
                "Cost effect (SGD)": None,
                "Effect basis": "No draft values included in totals",
                "State": "Unapplied; complete or revert before decision confirmation",
                "Recorded": "Saved project metadata",
            }
        )
    return rows
