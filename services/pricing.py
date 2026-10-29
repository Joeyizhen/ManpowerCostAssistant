"""Starting-rate decisions reuse deployment inputs and retain value-specific evidence."""

from services.decision_basis import meaningful, record_basis, retained_basis, signature
from services.evidence import rate_benchmark


def starting_overview(plan):
    from services.calculations import D, cents, preliminary

    result = preliminary(plan)
    annual = cents(D(result["monthly"]) * 12)
    return {
        **result,
        "display_annual": annual,
        "annual_rounding_difference": cents(D(result["year_1"]) - D(annual)),
    }


def reference(plan, role, records):
    result = rate_benchmark(
        records,
        role.mapped_role,
        role.benchmark_year,
        role.benchmark_status,
        role.benchmark_scope,
        quantity_unit=role.quantity_unit,
    )
    if result.get("reference_kind") == "prepared quotation":
        # The selection certifies title equivalence, not hours, allocation or an
        # inclusive headcount/FTE denominator. Do not infer these from quantity.
        result = {
            **result,
            "recommendation_supported": False,
            "typical_supported": False,
            "comparability_rule": "pricing-comparability-v1: a recommendation requires a verified matching pricing denominator, deployment basis and inclusions. The prepared selection does not establish these fields.",
            "comparability_note": "Source units, shared deployment and inclusions are unresolved. The quoted average is context, not a recommended rate per person or FTE.",
        }
    else:
        result = {
            **result,
            "recommendation_supported": result["available"],
            "typical_supported": result["available"],
        }
    return result


def custom_rate(role, benchmark):
    return (
        not benchmark.get("recommendation_supported", benchmark["available"])
        or role.rate is None
        or abs(role.rate - round(benchmark["average"], 2)) > 0.005
    )


def needs_pricing_basis(role, benchmark):
    return not benchmark.get("recommendation_supported", benchmark["available"]) or (
        role.rate is not None
        and not round(benchmark["minimum"], 2) <= role.rate <= round(benchmark["maximum"], 2)
    )


def shared_pricing_applies(plan, role):
    shared = plan.basis_drafts.get("rate", {})
    return role.id in shared.get("_roles", []) and (
        "_signatures" not in shared or shared["_signatures"].get(role.id) == signature(plan, role, "rate")
    )


def apply_shared_pricing(plan, role_ids, explanation, source, officer):
    from services.workflow import invalidate

    explanation, source = explanation or "", source or ""
    roles = [r for r in plan.roles if r.included and r.id in role_ids]
    if not roles or len(roles) != len(set(role_ids)):
        raise ValueError("Select the roles covered by this quotation or explanation.")
    if not meaningful(explanation):
        raise ValueError(
            "Briefly explain where these allowances come from, for example a supplier quotation covering these roles."
        )
    plan.basis_drafts["rate"] = {
        "_roles": [r.id for r in roles],
        "_explanation": explanation.strip(),
        "_source": source.strip(),
        "_shared": True,
        "_signatures": {r.id: signature(plan, r, "rate") for r in roles},
    }
    invalidate(
        plan, "rates", "Officer applied one pricing basis to selected allowances; figures unchanged", officer
    )


def pricing_proposal(plan, records, officer):
    candidate = plan.model_copy(deep=True)
    errors = []
    if plan.pending:
        errors.append(
            "Review or dismiss the assistant's proposed changes before confirming the displayed starting rates."
        )
    year_draft = plan.basis_drafts.get("pricing_year", {})
    sources = plan.basis_drafts.get("pricing_sources", {})
    legacy = plan.basis_drafts.get("rate", {})
    for role in candidate.roles:
        if not role.included:
            continue
        if role.rate is None or role.rate <= 0:
            errors.append(f"{role.label}: enter a positive monthly rate per {role.quantity_unit}.")
            continue
        old = retained_basis(plan, role, "rate")
        year_changed = role.id in year_draft.get("roles", [])
        legacy_applies = shared_pricing_applies(plan, role)
        shared_override = legacy_applies and legacy.get("_shared", False)
        if old and not year_changed and role.id not in sources and not shared_override:
            continue
        bm = reference(candidate, role, records)
        custom = custom_rate(role, bm)
        reason = role.rate_reason
        if old and (not meaningful(reason) or reason.startswith("Officer budgeting allowance:")):
            reason = old.snapshots[role.id].get("pricing_rationale", old.explanation)
        if legacy_applies and (
            shared_override or not meaningful(reason) or reason.startswith("Officer budgeting allowance:")
        ):
            reason = legacy.get("_explanation", "")
        if custom and (not meaningful(reason) or reason.startswith("Officer budgeting allowance:")):
            if needs_pricing_basis(role, bm):
                errors.append(
                    f"{role.label}: briefly explain where this allowance comes from, such as a supplier quotation or your budgeting judgement."
                )
                continue
            reason = f"Officer-selected allowance of SGD {role.rate:,.2f} within the observed comparable range SGD {bm['minimum']:,.2f}-{bm['maximum']:,.2f}; historical reference records retained automatically. This is a budgeting choice, not a verified supplier quotation."
        if not custom:
            reason = (
                f"Conditional contract-year 1 quote reference across {bm['sample_count']} distinct submissions; equal submission weighting. Actual calendar pricing year, source count/allocation basis and inclusions remain unverified. Officer-selected starting allowance; no time normalisation."
                if bm.get("reference_kind") == "prepared quotation"
                else f"Comparable database arithmetic average from {bm['sample_count']} distinct inclusive manpower schedules, priced in {role.benchmark_year}; selected for the starting allowance."
            )
        pricing_reason = reason
        mismatch = (
            bm.get("reference_kind") != "prepared quotation"
            and role.benchmark_year
            and candidate.profile.costing_start
            and role.benchmark_year != candidate.profile.costing_start.year
        )
        treatment = year_draft.get("explanation", "") if year_changed else role.rate_notes
        if not meaningful(treatment) and legacy_applies:
            treatment = legacy.get("_explanation", "")
        if mismatch and not meaningful(treatment):
            errors.append(f"{role.label}: record the shared reference-year treatment.")
            continue
        if mismatch:
            reason += " Reference-year treatment (officer assumption): " + treatment
            role.rate_notes = treatment
        source = sources.get(
            role.id,
            legacy.get("_source", "")
            if shared_override
            else old.snapshots[role.id].get("quotation_reference", "")
            if old
            else legacy.get("_source", "")
            if legacy_applies
            else "",
        )
        if shared_override:
            source = legacy.get("_source", "")
        support = (
            ", ".join(row["record_id"] for row in bm["records"])
            if bm["available"]
            else "No comparable database allowance; officer assumption"
        )
        if source:
            support += "; officer-supplied quotation/document: " + source
        record_basis(
            candidate,
            "rate",
            [role.id],
            "Starting monthly allowance",
            reason,
            support,
            "officer assumption" if custom else "sourced evidence",
            officer,
        )
        candidate.decision_bases[-1].snapshots[role.id].update(
            reference_records=bm["records"],
            reference_dataset=bm.get("dataset_id", "synthetic-fixture-v1"),
            reference_method=bm["method"],
            reference_limitations=bm["limitations"],
            reference_comparability=bm.get("comparability_rule", "Validated fixture unit/scope match"),
            reference_recommendation_supported=bm.get("recommendation_supported", bm["available"]),
            quotation_reference=source,
            year_treatment=(
                bm["alignment"]
                if bm.get("reference_kind") == "prepared quotation"
                else treatment
                if mismatch
                else "Same reference and contract-start year"
            ),
            rate_selection="Officer-selected allowance" if custom else "Database arithmetic average",
            pricing_rationale=pricing_reason,
            shared_pricing_roles=[r.id for r in plan.roles if shared_pricing_applies(plan, r)]
            if shared_override
            else [],
        )
        if band := candidate.basis_drafts.get("illustrative_rate_bands", {}).get(role.id):
            candidate.decision_bases[-1].snapshots[role.id]["illustrative_planning_range"] = band
    candidate.basis_drafts.pop("pricing_year", None)
    candidate.basis_drafts.pop("pricing_sources", None)
    candidate.basis_drafts.pop("rate", None)
    return candidate, list(dict.fromkeys(errors))
