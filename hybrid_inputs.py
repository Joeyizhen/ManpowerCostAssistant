"""Track 1 screens and navigation around the existing shared workflow gates."""

import pandas as pd
import streamlit as st

import ui_drafts
from journey_inputs import (
    commit_rows,
    deployment_review_table,
    manpower_screen,
    pending_control_errors,
    project_prefix,
    project_screen,
    validate_manpower,
    validate_project,
)
from services.evidence import load_records
from services.hybrid import STEP_LABELS, comparison_rows
from services.journey import accept_review, prepare_review, working_draft
from services.manpower_checks import LOCAL_ACTOR, quantity_discrepancy, shared_basis_mismatches
from services.workflow import confirm


def confirmation_errors(plan, officer, records, gate=None, checkpoint=None):
    """Exercise existing validation on a throwaway copy; never confirm the live plan."""
    scope = (
        "operational"
        if checkpoint in ("requirements", "manpower")
        or gate in ("profile", "responsibilities", "quantities", "plan")
        else "rates"
        if checkpoint == "rates" or gate in ("rates", "base")
        else "all"
    )
    errors = pending_control_errors(plan, scope=scope)
    checking_officer = officer.strip() or LOCAL_ACTOR
    candidate = plan.model_copy(deep=True)
    try:
        if checkpoint:
            if candidate.review_checkpoint != checkpoint:
                result = prepare_review(candidate, checkpoint, records)
                if not result["ready"]:
                    return errors + result.get(
                        "missing_inputs", [result.get("action", "Review the remaining details.")]
                    )
            accept_review(candidate, checking_officer, records)
        else:
            confirm(candidate, gate, checking_officer, records)
    except ValueError as error:
        return errors + str(error).splitlines()
    return errors


def show_missing(errors):
    if errors:
        st.info("Before you can confirm:\n" + "\n".join(f"• {error}" for error in dict.fromkeys(errors)))


def sanity_changed(key):
    plan = st.session_state.plan
    rows = comparison_rows(plan)
    by_id = {row["id"]: row for row in rows}
    for index, values in st.session_state.get(key, {}).get("edited_rows", {}).items():
        original = st.session_state[key + "_base"][int(index)]
        if "Remarks / correction" in values:
            by_id[original["id"]]["Duties / deployment notes"] = values["Remarks / correction"]
    commit_rows(plan, rows)
    st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1


def review_summary(plan):
    draft = working_draft(plan)
    st.markdown("**What the assistant understands**" if plan.chat else "**Recorded understanding**")
    st.write(draft.profile.description or "Property description not provided.")
    st.caption(
        f"{draft.profile.base_years or '?'} base + {draft.profile.option_years if draft.profile.option_years is not None else '?'} option years"
    )
    duplicates = {}
    for role in draft.roles:
        if role.included:
            duplicates.setdefault(role.label.strip().casefold(), []).append(role)
    for group in duplicates.values():
        if len(group) > 1:
            st.warning(
                f"Repeated title: {group[0].label}. Check these are separate deployments: "
                + ", ".join(r.id for r in group)
                + ". Both rows are retained and costed separately."
            )
    st.markdown("**Sanity checks**")
    flagged = []
    for role in draft.roles:
        check = quantity_discrepancy(role, plan.contract_kind == "existing contract")
        if check:
            flagged.append(
                {
                    "id": role.id,
                    "Role": role.label,
                    "Current": role.current_quantity,
                    "Proposed": role.quantity,
                    "Check": check,
                    "Remarks / correction": role.duties_notes,
                }
            )
    # Preserve unfinished optional notes from the previous review layout without keeping obsolete gates.
    for prefix in list(st.session_state.get("finding_inputs", {})):
        if prefix.startswith(f"finding_{plan.id}_advice_"):
            baseline = st.session_state.finding_inputs.pop(prefix)
            text = st.session_state.get(prefix + "_reason", "")
            if text and text != baseline.get("_reason"):
                notes = plan.working_notes.setdefault("notes", [])
                retained = "Earlier optional review note: " + text
                if retained not in notes:
                    notes.append(retained)
                plan.working_notes.setdefault("base_version", plan.version)
    if flagged:
        st.caption(
            "Only material numerical mismatches are listed. Edit the deployment table below or retain a valid choice with a recorded explanation at final review."
        )
        key = f"sanity_{plan.id}_{st.session_state.get('six_epoch', 0)}"
        st.session_state[key + "_base"] = flagged
        frame = pd.DataFrame(flagged)
        st.dataframe(
            frame.style.format({"Current": "{:.2f}", "Proposed": "{:.2f}"}, na_rep="").map(
                lambda value: "color: #b42318; font-weight: bold", subset=["Check"]
            ),
            hide_index=True,
            width="stretch",
            placeholder="",
            column_config={
                "id": None,
                "Current": None
                if plan.contract_kind != "existing contract"
                else st.column_config.NumberColumn("Current", format="%.2f"),
                "Proposed": st.column_config.NumberColumn("Proposed", format="%.2f"),
                "Remarks / correction": st.column_config.TextColumn(width="large"),
                "Check": st.column_config.TextColumn("Remarks to check", width="medium"),
            },
        )
    else:
        st.caption(
            "No explicit numerical discrepancy found. Unchanged roles are status quo; no role-by-role justification is needed."
        )
    shared_checks = shared_basis_mismatches(draft)
    if shared_checks:
        st.caption(
            "Check the shared staffing basis against the selected totals. Revise it in Step 2 or retain the valid figures with a qualification at final review."
        )
        st.dataframe(
            pd.DataFrame(shared_checks)
            .drop(columns=["id"])
            .style.map(lambda value: "color: #b42318; font-weight: bold", subset=["Check"]),
            hide_index=True,
            width="stretch",
        )
    original = {r["id"]: r for r in plan.officer_manpower_input}
    changes = []
    for role in draft.roles:
        before = original.get(role.id)
        if before and any(
            before.get(k) != getattr(role, k)
            for k in ("label", "quantity", "quantity_unit", "included", "duties_notes")
        ):
            changes.append(
                {
                    "Original role": before["label"],
                    "Suggested role": role.label,
                    "Your quantity": before["quantity"],
                    "Suggested quantity": role.quantity,
                    "Your basis": before["quantity_unit"],
                    "Suggested basis": role.quantity_unit,
                    "Original remarks": before.get("duties_notes", ""),
                    "Suggested remarks": role.duties_notes,
                    "Reason": role.quantity_reason,
                }
            )
    if changes:
        st.markdown("**Suggested changes**")
        st.dataframe(changes, hide_index=True, width="stretch", placeholder="")
    with st.expander("Remaining assumptions and unknowns"):
        for name in ("operating_hours", "assets", "locations", "response_requirements"):
            value = getattr(draft.profile, name)
            st.write(f"{name.replace('_', ' ').capitalize()}: {value or 'Not provided; no value inferred'}")
        for role in draft.roles:
            if role.included:
                st.write(f"{role.label}: {role.quantity_reason or 'Quantity basis needs review'}")


def completed_steps(plan):
    """Input completion is distinct from officer confirmation; recheck after revisions."""
    complete = []
    for step, validate in [(0, validate_project), (1, validate_manpower)]:
        try:
            validate(plan)
            complete.append(step)
        except ValueError:
            break
    gates = [(2, ("plan",)), (3, ("rates", "base")), (4, ("escalation",)), (5, ("final",))]
    for step, required in gates:
        if all(g in plan.confirmations for g in required):
            complete.append(step)
    return complete


def maximum_step(plan):
    complete = completed_steps(plan)
    confirmed = max((i + 1 for i in complete if 2 <= i < 5), default=0)
    inputs = 2 if 1 in complete else 1 if 0 in complete else 0
    return max(inputs, confirmed)


def step_for_stage(stage):
    return 2 if stage <= 3 else 3 if stage <= 5 else 4 if stage == 6 else 5


def show_progress(plan):
    plan.input_steps_completed = completed_steps(plan)
    limit = maximum_step(plan)
    if plan.ui_step is None:
        plan.ui_step = limit
    plan.ui_step = min(plan.ui_step, limit)
    st.progress(len(plan.input_steps_completed) / 6)
    with st.expander("Your six steps"):
        for index, label in enumerate(STEP_LABELS):
            status = (
                "Complete"
                if index in plan.input_steps_completed
                else "Current"
                if index == plan.ui_step
                else "Next"
            )
            st.write(f"{index + 1}. {label} · {status}")
    with st.sidebar:
        selected = st.selectbox(
            "Go to step",
            list(range(limit + 1)),
            index=plan.ui_step,
            format_func=lambda i: f"{i + 1}. {STEP_LABELS[i]}",
            key=f"six_nav_{plan.id}_{plan.ui_step}_{limit}",
        )
        if selected != plan.ui_step:
            if ui_drafts.unsaved(plan, pending_control_errors(plan)):
                st.warning("Apply or revert your pending selection before leaving this step.")
            else:
                plan.ui_step = selected
                st.rerun()
    st.subheader(f"Step {plan.ui_step + 1} out of 6: {STEP_LABELS[plan.ui_step]}")


def navigation(plan):
    step = plan.ui_step
    pending = pending_control_errors(
        plan, scope="operational" if step <= 2 else "rates" if step == 3 else "all"
    )
    errors = list(pending)
    if step in (0, 1):
        try:
            (validate_project if step == 0 else validate_manpower)(plan)
        except ValueError as error:
            errors.extend(str(error).split("; "))
        if step == 0 and st.session_state.get(project_prefix(plan) + "_error"):
            errors.insert(0, st.session_state[project_prefix(plan) + "_error"])
        if errors:
            st.info("To continue:\n" + "\n".join(f"• {error}" for error in dict.fromkeys(errors)))
    back, onward = st.columns(2)
    if back.button(
        "Back", key="six_back", disabled=step == 0 or ui_drafts.unsaved(plan, pending), width="stretch"
    ):
        plan.ui_step -= 1
        st.rerun()
    if (
        step < 5
        and step not in (2, 3, 4)
        and onward.button(
            "Continue",
            key="six_continue",
            width="stretch",
            disabled=bool(errors) or maximum_step(plan) <= step,
        )
    ):
        plan.ui_step += 1
        st.rerun()
    if step == 3 and maximum_step(plan) <= step:
        st.caption("Review and explicitly confirm this decision to continue.")


def render_inputs(plan, cfg, request_guidance, stage, save_project):
    if plan.ui_step == 0:
        project_screen(plan)
    elif plan.ui_step == 1:
        rows = manpower_screen(plan)
        from decision_inputs import basis_panel

        basis_panel(plan, "quantity", load_records())
        try:
            key = st.session_state.get("six_editor_key", "")
            if st.session_state.get(key, {}).get("edited_rows"):
                commit_rows(plan, rows)
        except ValueError as error:
            st.error(str(error))
            st.stop()
    else:
        rows = comparison_rows(plan)
        review_summary(plan)
        st.markdown("**Exact manpower plan awaiting your review**")
        rows = deployment_review_table(plan)

    if st.button("Save input draft"):
        if save_project():
            st.rerun()
    if plan.ui_step != 2:
        return
    st.markdown("**What would you like to do next?**")
    errors = confirmation_errors(
        plan, (st.session_state.get("officer", "") or LOCAL_ACTOR), load_records(), checkpoint="manpower"
    )
    show_missing(errors)
    review_choice, continue_choice, revise_choice = st.columns(3)
    review_choice.caption("Get assistant comments")
    continue_choice.caption("Confirm staffing; choose rates")
    revise_choice.caption("Ask about a revision")
    if continue_choice.button(
        "Use this plan",
        key="use_manpower_plan",
        type="primary",
        width="stretch",
        disabled=bool(errors),
    ):
        try:
            validate_project(plan)
            validate_manpower(plan)
            result = prepare_review(plan, "manpower", load_records())
            if not result["ready"]:
                raise ValueError("; ".join(result.get("missing_inputs", [result["action"]])))
            accept_review(plan, (st.session_state.get("officer", "") or LOCAL_ACTOR), load_records())
            plan.ui_step = 3
            save_project()
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    st.caption(
        "Choose one option: request comments, use the displayed plan and select rates, or discuss changes."
    )
    if revise_choice.button("Discuss changes", key="revise_manpower_plan", width="stretch"):
        st.session_state.manpower_help_open = True
        st.rerun()
    st.caption("Edit figures with Back, or discuss a change in the assistant section below.")
    if not (cfg.api_key and cfg.model):
        st.info(
            "Assistant comments need a configured API key and model. You can still confirm valid figures and continue to rates."
        )
    if review_choice.button("Review plan", width="stretch", disabled=not (cfg.api_key and cfg.model)):
        try:
            commit_rows(plan, rows)
            validate_project(plan)
            validate_manpower(plan)
            plan.manpower_review_requested = True
            save_project()
            request_guidance(
                "Review the brief, contract, current and proposed quantities, units, remarks and retained answers together. "
                "Highlight contradictions between remarks and numerical changes. Zero is excluded; blank is unanswered. "
                "Preserve combined roles and seniority. Do not create mandatory staffing requirements. "
                "Give concise sanity checks and material follow-ups. Officers may keep valid figures with reasons or acknowledge uncertainty. "
                "Describe discrepancies directly without self-justifying explanations. "
                "No prices, escalation, qualification questionnaire or approval.",
                stage,
            )
            save_project()
            st.session_state.manpower_help_open = True
            st.rerun()
        except ValueError as error:
            st.error(str(error))
