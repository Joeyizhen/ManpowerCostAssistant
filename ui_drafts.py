"""Persist unapplied text/choices separately from calculation facts and approvals."""

from datetime import date

import streamlit as st

SUFFIXES = (
    "_mode",
    "_yearly_text",
    "_yearly_reason",
    "_policy_name",
    "_policy_effective",
    "_policy_amount",
    "_policy_component",
    "_policy_source",
    "_policy_basis",
    "_policy_overlap",
    "_status",
    "_reason",
    "_inclusion",
    "_further",
)


def encode(value):
    return {"date": value.isoformat()} if isinstance(value, date) else value


def decode(value):
    return date.fromisoformat(value["date"]) if isinstance(value, dict) and set(value) == {"date"} else value


def controls(plan):
    return {
        key: encode(st.session_state[key])
        for key in st.session_state
        if key.startswith((f"esc_{plan.id}_", f"finding_{plan.id}_")) and key.endswith(SUFFIXES)
    }


def raw_pending(pending_errors):
    return any(
        any(
            tag in error
            for tag in ("edited yearly profile", "component adjustment", "edited finding decision")
        )
        for error in pending_errors
    )


def capture(plan, pending_errors):
    if not raw_pending(pending_errors):
        # A finding editor on another screen has no current baseline. Preserve its
        # saved draft until that editor is revisited, recorded or explicitly reverted.
        prior = plan.basis_drafts.get("_ui_controls", {})
        baselines = st.session_state.get("finding_inputs", {})
        hidden = {
            key: value
            for key, value in prior.get("values", {}).items()
            if key.startswith(f"finding_{plan.id}_")
            and not any(key.startswith(prefix + "_") for prefix in baselines)
        }
        if hidden:
            plan.basis_drafts["_ui_controls"] = {"project_id": plan.id, "values": hidden}
        else:
            plan.basis_drafts.pop("_ui_controls", None)
        return
    plan.basis_drafts["_ui_controls"] = {"project_id": plan.id, "values": controls(plan)}


def restore(plan):
    saved = plan.basis_drafts.get("_ui_controls", {})
    prior_id = saved.get("project_id", plan.id)
    values = saved.get("values", {})
    if prior_id != plan.id:
        values = {key.replace(prior_id, plan.id): value for key, value in values.items()}
        saved.update(project_id=plan.id, values=values)
    for key, value in values.items():
        if key not in st.session_state:
            st.session_state[key] = decode(value)


def restore_controls_after_sync(plan, prefix):
    flag = prefix + "_ui_draft_restored"
    if not st.session_state.get(flag):
        for key, value in plan.basis_drafts.get("_ui_controls", {}).get("values", {}).items():
            if key.startswith(prefix + "_"):
                st.session_state[key] = decode(value)
        st.session_state[flag] = True


def unsaved(plan, pending_errors):
    if not raw_pending(pending_errors):
        return False
    return controls(plan) != plan.basis_drafts.get("_ui_controls", {}).get("values", {})
