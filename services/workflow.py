"""Officer-only confirmations, approval invalidation and findings with retained history."""

import hashlib
import json
from uuid import uuid4

from services.calculations import budget, coverage_quantity
from services.evidence import ROLES, load_records, position, rate_benchmark
from services.models import GATES, Finding, Plan, Profile, Responsibility, Role, now


def invalidate(plan: Plan, from_gate: str, reason: str, officer: str):
    index = GATES.index(from_gate)
    removed = {g: plan.confirmations.pop(g) for g in GATES[index:] if g in plan.confirmations}
    if "final" in plan.confirmations:
        removed["final"] = plan.confirmations.pop("final")
    plan.final_date = ""
    plan.final_officer = ""
    plan.version += 1
    plan.history.append(
        {
            "time": now(),
            "version": plan.version,
            "officer": officer,
            "action": reason,
            "invalidated_confirmations": removed,
        }
    )


def apply_change(plan: Plan, kind: str, payload: dict, reason: str, officer: str):
    # Validate before committing; no partial mutation on error.
    candidate = plan.model_copy(deep=True)
    previous_findings = [f.model_dump() for f in findings(plan, load_records())]
    if kind == "profile":
        candidate.profile = Profile.model_validate({**candidate.profile.model_dump(), **payload})
        gate = "profile"
    elif kind == "responsibility":
        item = Responsibility.model_validate(payload)
        candidate.responsibilities = [r for r in candidate.responsibilities if r.id != item.id] + [item]
        gate = "responsibilities"
    elif kind == "role":
        item = Role.model_validate(payload)
        if item.mapped_role and item.mapped_role not in ROLES:
            raise ValueError("Mapping must use a supported role or remain unmatched")
        old = next((r for r in candidate.roles if r.id == item.id), None)
        candidate.roles = [r for r in candidate.roles if r.id != item.id] + [item]
        gate = "quantities"
        if old:
            operational = [
                "label",
                "mapped_role",
                "mapping_reason",
                "responsibility_ids",
                "included",
                "exclusion_reason",
                "quantity",
                "current_quantity",
                "quantity_unit",
                "quantity_basis",
                "quantity_reason",
                "coverage",
                "experience",
                "qualifications",
                "yearly_quantities",
                "duties_notes",
                "deployment",
            ]
            pricing = [
                "rate",
                "rate_reason",
                "rate_notes",
                "rate_origin",
                "benchmark_status",
                "benchmark_year",
                "benchmark_scope",
            ]
            if all(getattr(old, k) == getattr(item, k) for k in operational):
                gate = "rates" if any(getattr(old, k) != getattr(item, k) for k in pricing) else "escalation"
    else:
        raise ValueError("Unknown change type")
    invalidate(candidate, gate, reason, officer)
    if candidate.working_notes.get("base_version") == plan.version:
        notes = candidate.working_notes
        notes["base_version"] = candidate.version
        if kind == "profile":
            notes.pop("profile", None)
        else:
            field = "roles" if kind == "role" else "responsibilities"
            notes[field] = [r for r in notes.get(field, []) if r["id"] != payload["id"]]
    candidate.history.append(
        {
            "time": now(),
            "version": candidate.version,
            "officer": officer,
            "action": "Revision details",
            "kind": kind,
            "after": payload,
            "previous_findings": previous_findings,
        }
    )
    plan.__dict__.update(candidate.__dict__)


def missing_for_gate(plan: Plan, gate: str, records=None):
    p = plan.profile
    errors = []
    if gate == "profile":
        for k in [
            "description",
            "base_years",
            "option_years",
        ]:
            if getattr(p, k) is None or getattr(p, k) == "":
                hint = (
                    "" if k in ("start", "base_years", "option_years") else " (record 'unknown' if unknown)"
                )
                errors.append(f"Project {k.replace('_', ' ')} is missing{hint}")
        if p.costing_start is None:
            errors.append("Contract start year is missing (an exact date is optional)")
        if p.start and p.start_year is not None and p.start.year != p.start_year:
            errors.append("Contract start date and year disagree; correct one of them")
        if p.years > 20:
            errors.append("Contract base plus option years cannot exceed 20")
    elif gate == "responsibilities":
        if not plan.responsibilities:
            errors.append("Record operational responsibilities, external coverage or unknown scope")
        for r in plan.responsibilities:
            if r.coverage == "external" and not r.provider.strip():
                errors.append(f"{r.id}: identify the external provider")
    elif gate in ("quantities", "plan"):
        if not any(r.included for r in plan.roles):
            errors.append("Include at least one role")
        known = {r.id for r in plan.responsibilities}
        for r in plan.roles:
            if not r.included:
                if not r.exclusion_reason.strip():
                    errors.append(f"{r.label}: record why the role was excluded")
                continue
            if r.quantity is None or r.quantity <= 0 or not r.quantity_reason.strip():
                errors.append(f"{r.label}: set quantity and deployment rationale")
            if r.quantity_unit == "posts":
                errors.append(f"{r.label}: convert posts to explicit headcount or FTE before confirmation")
            if not r.responsibility_ids or not set(r.responsibility_ids) <= known:
                errors.append(f"{r.label}: assign valid responsibilities")
            if r.quantity_basis == "coverage":
                try:
                    if r.coverage is None:
                        raise ValueError("Coverage inputs missing")
                    coverage_quantity(r.coverage)
                except ValueError as e:
                    errors.append(f"{r.label}: {e}")
    elif gate == "rates":
        for r in plan.roles:
            if r.included and r.rate is None:
                errors.append(f"{r.label}: enter a positive monthly manpower unit rate")
            if (
                r.included
                and r.rate_origin == "Synthetic benchmark selection"
                and not rate_benchmark(
                    records if records is not None else load_records(),
                    r.mapped_role,
                    r.benchmark_year,
                    r.benchmark_status,
                    r.benchmark_scope,
                )["available"]
            ):
                errors.append(
                    f"{r.label}: no sufficient synthetic comparable rates; use an explicit officer assumption"
                )
    elif gate == "escalation":
        for r in plan.roles:
            if r.included and (len(r.escalation) != p.years or not r.escalation_reason.strip()):
                errors.append(f"{r.label}: select and justify every contract year's escalation")
    return errors


def confirm(plan: Plan, gate: str, officer: str, records=None):
    if not officer.strip():
        raise ValueError("Officer name is required")
    if gate not in GATES + ["final"]:
        raise ValueError("Unknown confirmation stage")
    index = len(GATES) if gate == "final" else GATES.index(gate)
    missing = [g for g in GATES[:index] if g not in plan.confirmations]
    if missing:
        raise ValueError("Confirm earlier stages first: " + ", ".join(missing))
    errors = missing_for_gate(plan, gate, records)
    if gate in ("escalation", "validation", "final"):
        try:
            budget(plan, records or [])
        except ValueError as e:
            errors.append(str(e))
    if gate in ("validation", "final"):
        current = findings(plan, records or [])
        errors += [f.message for f in current if f.blocking]
        if gate == "final":
            errors += [
                f"Decision/justification required: {f.message}"
                for f in current
                if f.status == "unresolved risk"
                or f.justification == "Officer justification was not provided."
            ]
    if errors:
        raise ValueError("\n".join(dict.fromkeys(errors)))
    plan.confirmations[gate] = plan.version
    if gate == "final":
        plan.final_officer, plan.final_date = officer, now()
    plan.history.append(
        {"time": now(), "version": plan.version, "action": f"Confirmed {gate}", "officer": officer}
    )


def unlocked_stage(plan):
    for i, gate in enumerate(GATES):
        if gate not in plan.confirmations:
            return i
    return 9


def findings(plan: Plan, records):
    result = []

    def add(code, message, impact, role=None, blocking=False, evidence="", year=None):
        rid = role.id if role else ""
        fid = f"{code}:{rid}:{year or ''}"
        context = {
            "profile": plan.profile.model_dump(mode="json"),
            "role": role.model_dump(mode="json")
            if role
            else [r.model_dump(mode="json") for r in plan.responsibilities],
            "message": message,
        }
        fp = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        item = Finding(
            id=fid,
            code=code,
            role_id=rid,
            year=year,
            message=message,
            impact=impact,
            blocking=blocking,
            fingerprint=fp,
            evidence=evidence,
        )
        old = plan.decisions.get(fid)
        if old and old.fingerprint == fp and not blocking:
            item = old.model_copy(deep=True)
        elif code in ["synthetic", "unmatched", "thin_evidence"]:
            item.status = "data limitation"
        result.append(item)

    add(
        "synthetic",
        "All retrieved tender evidence is synthetic.",
        "Budget is for testing; rates and increases do not establish market prices.",
        evidence="data/sample/historical.json",
    )
    for key in ["assets", "locations", "operating_hours", "response_requirements", "critical_functions"]:
        value = getattr(plan.profile, key)
        if value and "unknown" in value.casefold():
            add(
                f"unknown_{key}",
                f"Project {key.replace('_', ' ')} contains an unknown requirement.",
                "Operational scope may be incomplete; retain this qualification until clarified.",
            )
    for i, gate in enumerate(GATES[:5]):
        for error in missing_for_gate(plan, gate, records):
            add(f"missing_{i}_{len(result)}", error, "Cannot confirm required inputs.", blocking=True)
    active = [r for r in plan.roles if r.included]
    for responsibility in plan.responsibilities:
        assigned = [r.label for r in active if responsibility.id in r.responsibility_ids]
        if responsibility.coverage == "unknown" or (responsibility.coverage == "plan" and not assigned):
            add(
                f"coverage_{responsibility.id}",
                f"Unresolved coverage: {responsibility.description}",
                "A required duty may be omitted.",
            )
        if len(assigned) > 1 or (assigned and responsibility.coverage in ("external", "not applicable")):
            add(
                f"duplicate_{responsibility.id}",
                f"Possible duplicated coverage: {responsibility.description} ({', '.join(assigned)})",
                "Deployment may duplicate another role or external provider.",
            )
    for r in active:
        if not r.mapped_role:
            add(
                "unmatched",
                f"{r.label}: original title retained; no supported benchmark mapping.",
                "Officer rate/scenario requires separate evidence.",
                r,
            )
        if r.mapped_role and r.label.casefold() != r.mapped_role.casefold() and not r.mapping_reason.strip():
            add(
                "mapping",
                f"{r.label}: explain mapping to {r.mapped_role}.",
                "Comparability is unverified.",
                r,
            )
        if r.quantity_basis == "officer scenario":
            add(
                "scenario",
                f"{r.label}: quantity is an officer scenario; no validated workload rule.",
                "No precise workload staffing requirement is established.",
                r,
                evidence=r.quantity_reason,
            )
        elif r.coverage and r.quantity:
            try:
                calculated = coverage_quantity(r.coverage)
                if r.quantity + 1e-8 < calculated["fte"]:
                    add(
                        "undercoverage",
                        f"{r.label}: selected quantity {r.quantity:g} is below indicative FTE {calculated['fte']:.2f}.",
                        "Relief or required coverage may be insufficient.",
                        r,
                        evidence=json.dumps(calculated),
                    )
                for year, quantity in enumerate(r.yearly_quantities, 1):
                    if quantity + 1e-8 < calculated["fte"]:
                        add(
                            "undercoverage_year",
                            f"{r.label}: Year {year} quantity {quantity:g} is below indicative FTE {calculated['fte']:.2f}.",
                            "Required shift/relief coverage may be insufficient in this year.",
                            r,
                            evidence=json.dumps(calculated),
                            year=year,
                        )
                if r.coverage.capacity_basis == "gross" and r.coverage.relief_factor == 1:
                    add(
                        "relief",
                        f"{r.label}: gross capacity has no relief allowance.",
                        "Absence costs/coverage may be omitted.",
                        r,
                    )
                if r.coverage.round_to_personnel:
                    add(
                        "roster",
                        f"{r.label}: rounded personnel count needs roster feasibility review.",
                        "Headcount calculation does not establish feasible shifts or response coverage.",
                        r,
                    )
            except ValueError as e:
                add("coverage_math", f"{r.label}: {e}", "Invalid quantity arithmetic.", r, True)
        bm = rate_benchmark(records, r.mapped_role, r.benchmark_year, r.benchmark_status, r.benchmark_scope)
        if not bm["available"]:
            add(
                "thin_evidence",
                f"{r.label}: fewer than three comparable rate schedules.",
                "No reference range is supplied.",
                r,
            )
        elif r.rate is not None and (r.rate < bm["minimum"] or r.rate > bm["maximum"]):
            add(
                "rate_range",
                f"{r.label}: {position(r.rate, bm).lower()}.",
                "A review flag, not proof the price is wrong.",
                r,
                evidence=json.dumps(
                    {
                        k: bm[k]
                        for k in ["sample_count", "minimum", "p25", "median", "p75", "maximum", "filters"]
                    }
                ),
            )
        if any(abs(e) > 0.1 for e in r.escalation):
            add(
                "unusual_escalation",
                f"{r.label}: annual changes exceed ±10%.",
                "Material assumption needs review.",
                r,
            )
        if len(r.escalation) != plan.profile.years:
            add(
                "missing_years",
                f"{r.label}: escalation years missing.",
                "Contract total unavailable.",
                r,
                True,
            )
        for policy in r.policies:
            add(
                "policy_source",
                f"{r.label}: policy/component adjustment source is officer-supplied and unverified.",
                "Verify applicability, effective date and overlap; additive treatment is an officer assumption.",
                r,
                evidence=policy.source,
            )
        if r.policies and any(r.escalation):
            add(
                "policy_overlap",
                f"{r.label}: component adjustments coexist with general price changes.",
                "Review whether general increases already include the component change; officer overlap checkbox alone is not source evidence.",
                r,
                evidence=r.escalation_reason,
            )
    if not plan.profile.exclusions.strip():
        add(
            "exclusions",
            "Excluded costs have not been disclosed.",
            "Total may be mistaken for an all-in procurement budget.",
        )
    try:
        budget(plan, records)
    except ValueError as e:
        add(
            "arithmetic",
            str(e),
            "Invalid required arithmetic inputs cannot be accepted as an exception.",
            blocking=True,
        )
    return result


def record_decision(plan, finding, status, justification, officer, inclusion="", further_approval=""):
    if finding.blocking:
        raise ValueError("Revise blocking inputs; exceptions cannot bypass invalid arithmetic")
    if status not in ("accepted exception", "unresolved risk", "data limitation"):
        raise ValueError("Resolved findings must be resolved by changing the underlying inputs")
    if not justification.strip():
        raise ValueError("Record an officer justification")
    invalidate(plan, "validation", f"Finding decision: {finding.id}", officer)
    item = finding.model_copy(deep=True)
    item.status, item.justification, item.officer, item.timestamp = status, justification, officer, now()
    item.inclusion, item.further_approval = inclusion, further_approval
    plan.decisions[item.id] = item
    plan.history.append(
        {"time": now(), "version": plan.version, "action": "Finding decision", **item.model_dump()}
    )


def finding_history(plan, current):
    current_ids = {f.id for f in current}
    observed = {}
    for entry in plan.history:
        for item in entry.get("previous_findings", []):
            observed[item["id"]] = Finding.model_validate(item)
    observed.update(plan.decisions)
    return [f.model_copy(update={"status": "resolved"}) for f in observed.values() if f.id not in current_ids]


def budget_status(plan, records):
    current = findings(plan, records)
    if "final" in plan.confirmations:
        return "Confirmed qualified budget" if current else "Confirmed budget"
    if any(f.blocking for f in current):
        return "Incomplete draft"
    return "Qualified draft" if current else "Draft"


def proposal(plan, kind, payload, reason):
    # Validate tool proposals without touching approved facts.
    scratch = plan.model_copy(deep=True)
    apply_change(scratch, kind, payload, reason, "LLM proposal validation")
    item = {
        "id": str(uuid4()),
        "kind": kind,
        "payload": payload,
        "reason": reason,
        "origin": "LLM-generated suggestion requiring officer confirmation",
        "time": now(),
        "base_version": plan.version,
    }
    # A follow-up answer revises the same suggestion instead of leaving conflicting versions to apply.
    target = (kind, payload.get("id"))
    plan.pending = [p for p in plan.pending if (p["kind"], p["payload"].get("id")) != target]
    plan.pending.append(item)
    return {"proposal_id": item["id"], "status": "Pending officer review; structured plan unchanged"}


def apply_pending(plan, officer):
    """Explicit officer action applies a reviewed set atomically, without approving a stage."""
    if not plan.pending:
        raise ValueError("There are no suggestions to review")
    if any(p["base_version"] != plan.version for p in plan.pending):
        raise ValueError("Suggestions predate a revision. Ask the assistant to refresh them or discard them.")
    candidate = plan.model_copy(deep=True)
    for item in list(plan.pending):
        apply_change(candidate, item["kind"], item["payload"], item["reason"], officer)
    candidate.pending = []
    plan.__dict__.update(candidate.__dict__)
