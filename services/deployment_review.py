"""Separate officer inputs, assistant proposals and deployment confirmation."""

from services.journey import working_draft
from services.workflow import apply_pending, proposal


def officer_draft(plan):
    candidate = plan.model_copy(deep=True)
    candidate.pending = []
    return working_draft(candidate)


def retain_assistant_proposals(plan, before):
    suggested = working_draft(plan)
    reasons = {(p["kind"], p["payload"].get("id")): p["reason"] for p in plan.pending}
    plan.working_notes = before.working_notes
    plan.pending = []
    plan.review_checkpoint = ""
    original = officer_draft(before)
    if suggested.profile != original.profile:
        proposal(
            plan,
            "profile",
            suggested.profile.model_dump(mode="json"),
            reasons.get(("profile", None), "Assistant suggested project context"),
        )
    duties = {d.id: d for d in original.responsibilities}
    for duty in suggested.responsibilities:
        if duty.id not in duties or duty != duties[duty.id]:
            proposal(
                plan,
                "responsibility",
                duty.model_dump(mode="json"),
                reasons.get(("responsibility", duty.id), "Assistant suggested duty context"),
            )
    originals = {r.id: r for r in original.roles}
    for role in suggested.roles:
        if role.id not in originals or role != originals[role.id]:
            proposal(
                plan,
                "role",
                role.model_dump(mode="json"),
                reasons.get(
                    ("role", role.id),
                    role.quantity_reason or role.duties_notes or "Assistant suggested deployment refinement",
                ),
            )


def accept_suggestions(plan, officer):
    candidate = officer_draft(plan)
    previous = {r.id: r for r in candidate.roles}
    for item in plan.pending:
        if item["kind"] != "role":
            continue
        data = item["payload"]
        old = previous.get(data.get("id"))
        unit, quantity = data.get("quantity_unit", "headcount"), data.get("quantity")
        unchanged_legacy = old and old.quantity_unit == unit and old.quantity == quantity
        if not unchanged_legacy and (
            unit != "headcount" or (quantity is not None and not float(quantity).is_integer())
        ):
            raise ValueError(
                "Enter the actual whole-person headcount for this suggestion; no FTE conversion is assumed."
            )
    candidate.pending = plan.pending
    candidate.working_notes = {}
    apply_pending(candidate, officer)
    candidate.review_checkpoint = ""
    candidate.ui_step = 1
    plan.__dict__.update(candidate.__dict__)
