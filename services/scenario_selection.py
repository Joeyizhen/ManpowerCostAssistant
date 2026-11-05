"""Explicit scenario adoption changes future assumptions, never prices or PWM."""

from services.calculations import budget
from services.decision_basis import record_basis
from services.workflow import apply_change


def adopt_scenario(plan, delta, officer, records):
    if delta not in (-0.01, 0.01):
        raise ValueError("Select the displayed lower or higher scenario")
    if plan.pending or plan.working_notes or plan.basis_drafts.get("common_future"):
        raise ValueError("Record or revert unfinished edits before adopting a scenario")
    candidate = plan.model_copy(deep=True)
    affected = []
    for role in list(candidate.roles):
        if not role.included or role.pwm or role.escalation_mode != "assumption":
            continue
        profile = [x + delta if i else x for i, x in enumerate(role.escalation)]
        item = role.model_copy(
            update={
                "escalation": profile,
                "escalation_reason": "Officer adopted the displayed scenario, shifting each Year 2 onward annual increase by "
                + f"{delta:+.0%}",
            }
        )
        apply_change(
            candidate,
            "role",
            item.model_dump(mode="json"),
            "Officer adopted a displayed future-cost scenario",
            officer,
        )
        affected.append(role.id)
    budget(candidate, records)  # Invalid scenarios never partially change the recorded plan.
    if affected:
        record_basis(
            candidate,
            "escalation",
            affected,
            "Officer-selected scenario",
            "Officer adopted the displayed lower annual-increase scenario"
            if delta < 0
            else "Officer adopted the displayed higher annual-increase scenario",
            "Selected budget scenario; unchanged starting rates, deployment, PWM and quoted prices",
            "officer assumption",
            officer,
        )
    plan.__dict__.update(candidate.__dict__)
