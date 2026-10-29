"""Read-only conversational context; pending suggestions never become approved facts."""

from services.models import GATES, STAGES, Profile, Responsibility, Role
from services.workflow import apply_pending, confirm, findings, missing_for_gate, proposal, record_decision

CHECKPOINTS = {
    "requirements": ["profile", "responsibilities"],
    "manpower": ["profile", "responsibilities", "quantities", "plan"],
    "rates": ["rates", "base"],
    "escalation": ["escalation"],
    "validation": ["validation"],
}


def working_draft(plan):
    draft = plan.model_copy(deep=True)
    notes = plan.working_notes
    if notes.get("base_version") == plan.version:
        if notes.get("profile"):
            draft.profile = Profile.model_validate(notes["profile"])
        for kind, model in [("responsibilities", Responsibility), ("roles", Role)]:
            for payload in notes.get(kind, []):
                item = model.model_validate(payload)
                setattr(draft, kind, [r for r in getattr(draft, kind) if r.id != item.id] + [item])
    for item in plan.pending:
        if item["base_version"] != plan.version:
            continue
        if item["kind"] == "profile":
            draft.profile = Profile.model_validate(item["payload"])
        elif item["kind"] == "responsibility":
            value = Responsibility.model_validate(item["payload"])
            draft.responsibilities = [r for r in draft.responsibilities if r.id != value.id] + [value]
        elif item["kind"] == "role":
            value = Role.model_validate(item["payload"])
            draft.roles = [r for r in draft.roles if r.id != value.id] + [value]
    return draft


def journey_context(plan, stage):
    index = STAGES.index(stage)
    gate = GATES[index] if index < len(GATES) else "final"
    draft = working_draft(plan)
    return {
        "current_step": stage,
        "gate": gate,
        "applied_missing_inputs": missing_for_gate(plan, gate),
        "draft_missing_inputs": missing_for_gate(draft, gate),
        "working_profile": draft.profile.model_dump(mode="json"),
        "working_responsibilities": [r.model_dump() for r in draft.responsibilities],
        "pending_review_count": sum(p["base_version"] == plan.version for p in plan.pending),
        "confirmation_is_officer_action": True,
        "working_roles": [
            {
                k: v
                for k, v in r.model_dump(mode="json").items()
                if "plan" in plan.confirmations
                or k
                in {
                    "id",
                    "label",
                    "mapped_role",
                    "mapping_reason",
                    "responsibility_ids",
                    "included",
                    "exclusion_reason",
                    "experience",
                    "qualifications",
                    "quantity",
                    "current_quantity",
                    "quantity_unit",
                    "quantity_basis",
                    "coverage",
                    "quantity_reason",
                    "yearly_quantities",
                    "duties_notes",
                    "deployment",
                }
            }
            for r in draft.roles
        ],
        "conversation_notes": plan.working_notes.get("notes", []),
        "review_checkpoint": plan.review_checkpoint,
        "recorded_decision_bases": [b.model_dump(mode="json") for b in plan.decision_bases],
        "unconfirmed_basis_drafts": plan.basis_drafts,
        "requirements_missing": missing_for_gate(draft, "profile")
        + missing_for_gate(draft, "responsibilities"),
    }


def update_notes(plan, profile=None, responsibilities=(), roles=(), notes=()):
    current = plan.working_notes if plan.working_notes.get("base_version") == plan.version else {}
    current = {**current, "base_version": plan.version}
    if profile is not None:
        current["profile"] = Profile.model_validate(profile).model_dump(mode="json")
    for kind, values, model in [
        ("responsibilities", responsibilities, Responsibility),
        ("roles", roles, Role),
    ]:
        merged = {v["id"]: v for v in current.get(kind, [])}
        for payload in values:
            value = model.model_validate(payload)
            merged[value.id] = value.model_dump(mode="json")
        current[kind] = list(merged.values())
    current["notes"] = list(dict.fromkeys([*current.get("notes", []), *notes]))[-40:]
    plan.working_notes = current
    plan.pending = []
    plan.review_checkpoint = ""


def prepare_review(plan, checkpoint, records):
    if checkpoint not in CHECKPOINTS or checkpoint == "validation":
        raise ValueError("Use finding-decision proposals for validation review")
    required = {
        "rates": ["plan"],
        "escalation": ["rates", "base"],
    }.get(checkpoint, [])
    if any(g not in plan.confirmations for g in required):
        raise ValueError("Confirm the preceding decision before presenting this proposal")
    draft = working_draft(plan)
    if checkpoint not in ("requirements", "manpower") and (
        draft.profile != plan.profile
        or {r.id: r for r in draft.responsibilities} != {r.id: r for r in plan.responsibilities}
    ):
        return {
            "ready": False,
            "requires_confirmation": "manpower",
            "action": "Requirements changed. Review the revised requirements with the manpower proposal before pricing.",
        }
    if checkpoint in ("rates", "escalation"):
        operational = {
            "label",
            "mapped_role",
            "mapping_reason",
            "responsibility_ids",
            "included",
            "exclusion_reason",
            "experience",
            "qualifications",
            "quantity",
            "current_quantity",
            "quantity_unit",
            "quantity_basis",
            "coverage",
            "quantity_reason",
            "yearly_quantities",
            "duties_notes",
            "deployment",
        }
        old = {r.id: r for r in plan.roles}
        if any(
            r.id not in old or any(getattr(r, k) != getattr(old[r.id], k) for k in operational)
            for r in draft.roles
        ):
            return {
                "ready": False,
                "requires_confirmation": "manpower",
                "action": "The operational plan or mapping changed. Prepare manpower review for renewed officer confirmation before pricing.",
            }
        if checkpoint == "escalation":
            price_fields = {
                "rate",
                "rate_reason",
                "rate_notes",
                "rate_origin",
                "benchmark_year",
                "benchmark_status",
                "benchmark_scope",
            }
            if any(any(getattr(r, k) != getattr(old[r.id], k) for k in price_fields) for r in draft.roles):
                return {
                    "ready": False,
                    "requires_confirmation": "rates",
                    "action": "Monthly rates changed. Review and confirm rates before future prices.",
                }
    errors = [e for g in CHECKPOINTS[checkpoint] for e in missing_for_gate(draft, g, records)]
    if errors:
        return {
            "ready": False,
            "missing_inputs": list(dict.fromkeys(errors)),
            "action": "Keep gathering relevant answers; do not present a proposal yet",
        }
    if checkpoint in ("rates", "escalation"):
        from services.calculations import budget, preliminary

        calculation = preliminary(draft) if checkpoint == "rates" else budget(draft, records)
    else:
        calculation = None
    plan.pending = []
    if checkpoint in ("requirements", "manpower"):
        proposal(plan, "profile", draft.profile.model_dump(mode="json"), "Conversation requirements summary")
        for duty in draft.responsibilities:
            proposal(plan, "responsibility", duty.model_dump(), "Officer-supplied scope and coverage")
    if checkpoint != "requirements":
        for role in draft.roles:
            proposal(
                plan, "role", role.model_dump(mode="json"), f"Review {checkpoint} decision and its basis"
            )
    plan.review_checkpoint = checkpoint
    return {
        "ready": True,
        "checkpoint": checkpoint,
        "action": "Present concise summary for officer correction and confirmation",
        "confirmation_label": "Confirm manpower plan and continue to rates"
        if checkpoint == "manpower"
        else f"Confirm {checkpoint} and continue",
        "calculation": calculation,
        "findings": [
            f.model_dump()
            for f in findings(draft, records)
            if checkpoint != "manpower"
            or f.code.startswith(("unknown_", "coverage", "duplicate_", "undercoverage", "provider_"))
            or f.code
            in {
                "synthetic",
                "scenario",
                "unmatched",
                "mapping",
                "relief",
                "roster",
                "requirements",
                "role_scope",
            }
        ]
        if checkpoint != "requirements"
        else [],
    }


def accept_review(plan, officer, records):
    checkpoint = plan.review_checkpoint
    if checkpoint not in CHECKPOINTS:
        raise ValueError("No prepared decision is awaiting confirmation")
    candidate = plan.model_copy(deep=True)
    gathered = working_draft(plan)
    if checkpoint == "validation":
        if any(p["base_version"] != plan.version for p in plan.pending):
            raise ValueError("Refresh the findings after the revision")
        current = {f.id: f for f in findings(candidate, records)}
        for item in plan.pending:
            data = item["payload"]
            record_decision(
                candidate,
                current[data["finding_id"]],
                data["status"],
                data["justification"],
                officer,
                data["inclusion"],
                data["further_approval"],
            )
        candidate.pending = []
    else:
        apply_pending(candidate, officer)
    for gate in CHECKPOINTS[checkpoint]:
        confirm(candidate, gate, officer, records)
    candidate.working_notes = {}
    candidate.review_checkpoint = ""
    if checkpoint == "requirements" and (gathered.roles or plan.working_notes.get("notes")):
        update_notes(
            candidate,
            roles=[r.model_dump(mode="json") for r in gathered.roles],
            notes=plan.working_notes.get("notes", []),
        )
    plan.__dict__.update(candidate.__dict__)
    return {"requirements": 2, "manpower": 4, "rates": 6, "escalation": 7, "validation": 8}[checkpoint]


def record_draft_decision(plan, finding_id, status, justification, officer, records, treatment=""):
    """Review advice against the exact draft without applying or approving its suggestions."""
    candidate = plan.model_copy(deep=True)
    current = {f.id: f for f in findings(working_draft(candidate), records)}
    if finding_id not in current:
        raise ValueError("Refresh the sanity checks after changing the plan")
    prior_version = candidate.version
    record_decision(candidate, current[finding_id], status, justification, officer, treatment)
    if candidate.working_notes.get("base_version") == prior_version:
        candidate.working_notes["base_version"] = candidate.version
    for suggestion in candidate.pending:
        if suggestion["base_version"] == prior_version:
            suggestion["base_version"] = candidate.version
    plan.__dict__.update(candidate.__dict__)
