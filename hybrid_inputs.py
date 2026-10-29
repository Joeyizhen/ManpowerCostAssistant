"""Five routed officer screens around the existing financial confirmation gates."""

import pandas as pd
import streamlit as st

import ui_drafts
from journey_inputs import (
    commit_rows,
    manpower_screen,
    pending_control_errors,
    project_prefix,
    project_screen,
    validate_manpower,
    validate_project,
)
from services.deployment_review import accept_suggestions, officer_draft
from services.evidence import load_records
from services.hybrid import STEP_LABELS, STEP_ROUTES, canonical_step, step_number
from services.journey import accept_review, prepare_review
from services.manpower_checks import LOCAL_ACTOR, quantity_discrepancy, shared_basis_mismatches
from services.workflow import confirm


def confirmation_errors(plan, officer, records, gate=None, checkpoint=None):
    scope = (
        "operational"
        if checkpoint in ("requirements", "manpower")
        or gate in ("profile", "responsibilities", "quantities", "plan")
        else "rates"
        if checkpoint == "rates" or gate in ("rates", "base")
        else "all"
    )
    errors = pending_control_errors(plan, scope=scope)
    if checkpoint == "manpower":
        from services.workflow import missing_for_gate

        # Readiness is a read-only input check, not a rehearsal of applying and
        # confirming every proposal. Actual acceptance still validates all gates.
        draft = officer_draft(plan)
        errors += [
            error
            for gate in ("profile", "responsibilities", "quantities", "plan")
            for error in missing_for_gate(draft, gate, records)
        ]
        if any(item["base_version"] != plan.version for item in plan.pending):
            errors.append("Refresh or dismiss suggestions made before the latest revision.")
        return list(dict.fromkeys(errors))
    candidate = plan.model_copy(deep=True)
    try:
        if checkpoint:
            if candidate.review_checkpoint != checkpoint:
                result = prepare_review(candidate, checkpoint, records)
                if not result["ready"]:
                    return errors + result.get(
                        "missing_inputs", [result.get("action", "Review the remaining details.")]
                    )
            accept_review(candidate, officer.strip() or LOCAL_ACTOR, records)
        else:
            confirm(candidate, gate, officer.strip() or LOCAL_ACTOR, records)
    except ValueError as error:
        errors += str(error).splitlines()
    return errors


def show_missing(errors):
    if errors:
        st.info("Before you can confirm:\n" + "\n".join(f"• {e}" for e in dict.fromkeys(errors)))


DEPLOYMENT_REVIEW_UI_VERSION = 3


def review_summary(plan):
    draft = officer_draft(plan)
    flagged = []
    for role in draft.roles:
        check = quantity_discrepancy(role, plan.contract_kind == "existing contract")
        if check:
            flagged.append(
                {
                    "Role": role.label,
                    "Current": role.current_quantity,
                    "Proposed": role.quantity,
                    "Check": check,
                    "Recorded reason": role.duties_notes,
                }
            )
    flagged.extend(shared_basis_mismatches(draft))
    if flagged:
        st.caption(
            "Check these material discrepancies; correct the figures or the recorded reason in the table."
        )
        st.dataframe(
            pd.DataFrame(flagged).style.map(lambda _: "color:#b42318", subset=["Check"]),
            hide_index=True,
            width="stretch",
            column_config={"id": None},
        )


def completed_steps(plan):
    complete = []
    for step, validate in [(0, validate_project), (1, validate_manpower)]:
        try:
            validate(plan)
            complete.append(step)
        except ValueError:
            break
    for step, gates in [(2, ("plan",)), (3, ("rates", "base")), (4, ("escalation",)), (5, ("final",))]:
        if all(g in plan.confirmations for g in gates):
            complete.append(step)
    return complete


def maximum_step(plan):
    complete = completed_steps(plan)
    confirmed = max((i + 1 for i in complete if 2 <= i < 5), default=0)
    return canonical_step(max(2 if 1 in complete else 1 if 0 in complete else 0, confirmed))


def step_for_stage(stage):
    return 1 if stage <= 3 else 3 if stage <= 5 else 4 if stage == 6 else 5


def visit_step(plan, step):
    ui_drafts.capture(plan, pending_control_errors(plan))
    plan.ui_step = canonical_step(step)


def show_progress(plan):
    # Preserve legacy wire locations, including the old review alias, without
    # changing any saved financial inputs, signatures or confirmation records.
    if plan.ui_step is None:
        plan.ui_step = maximum_step(plan)
    plan.ui_step = canonical_step(plan.ui_step)
    complete = completed_steps(plan)
    status = {
        0: 0 in complete,
        1: "plan" in plan.confirmations,
        3: "base" in plan.confirmations,
        4: "escalation" in plan.confirmations,
        5: "final" in plan.confirmations,
    }
    st.markdown(
        "<style>.st-key-five_step_navigation {position:sticky;top:2.5rem;z-index:20;"
        "background:var(--background-color,#f8fafc);padding:.35rem 0;}"
        ".st-key-five_step_navigation button p {font-size:.85rem;white-space:nowrap;}</style>",
        unsafe_allow_html=True,
    )
    with st.container(key="five_step_navigation"):
        for column, step in zip(st.columns(5), STEP_ROUTES, strict=True):
            column.button(
                f"{'✓ ' if status[step] else ''}{step_number(step)}. {STEP_LABELS[step]}",
                key=f"step_nav_{step}",
                type="primary" if step == plan.ui_step else "secondary",
                width="stretch",
                on_click=visit_step,
                args=(plan, step),
                help="Completed" if status[step] else "Needs input or confirmation",
            )
    st.subheader(f"Step {step_number(plan.ui_step)} out of 5: {STEP_LABELS[plan.ui_step]}")


def navigation(plan):
    step = canonical_step(plan.ui_step)
    index = STEP_ROUTES.index(step)
    back, onward = st.columns(2)
    back.button(
        "Back",
        key="six_back",
        disabled=index == 0,
        width="stretch",
        on_click=visit_step,
        args=(plan, STEP_ROUTES[max(0, index - 1)]),
    )
    if step == 0:
        errors = []
        try:
            validate_project(plan)
        except ValueError as error:
            errors += str(error).split("; ")
        error = st.session_state.get(project_prefix(plan) + "_error") or plan.basis_drafts.get(
            "project_text", {}
        ).get("error")
        if error:
            errors.insert(0, error)
        if st.session_state.get(f"project_attempt_{plan.id}") and errors:
            st.info("To continue:\n" + "\n".join(f"• {e}" for e in dict.fromkeys(errors)))
        if onward.button("Continue", key="six_continue", width="stretch"):
            st.session_state[f"project_attempt_{plan.id}"] = True
            if not errors:
                visit_step(plan, 1)
            st.rerun()


def assistant_changes(plan):
    if not plan.pending:
        return
    changes = []
    base = officer_draft(plan)
    originals = {r.id: r for r in base.roles}
    for item in plan.pending:
        data = item["payload"]
        if item["kind"] == "role":
            old = originals.get(data.get("id"))
            changes.append(
                {
                    "Role": data.get("label", "Role"),
                    "Current": f"{old.quantity} {old.quantity_unit}" if old else "Not included",
                    "Suggested": f"{data.get('quantity')} {data.get('quantity_unit', 'unit not confirmed')}",
                    "Current role / remarks": old.label + ": " + old.duties_notes if old else "",
                    "Suggested remarks": data.get("duties_notes", ""),
                    "Reason": item["reason"],
                }
            )
        elif item["kind"] == "profile":
            before = base.profile.model_dump(mode="json")
            for field, value in data.items():
                if before.get(field) != value:
                    changes.append(
                        {
                            "Item": field.replace("_", " ").capitalize(),
                            "Current": str(before.get(field) or "Not recorded"),
                            "Suggested": str(value or "Not recorded"),
                            "Reason": item["reason"],
                        }
                    )
        elif item["kind"] == "responsibility":
            changes.append(
                {
                    "Item": "Duty",
                    "Current": "Recorded deployment",
                    "Suggested": data.get("description", ""),
                    "Reason": item["reason"],
                }
            )
    st.markdown("**Assistant suggestions — not yet applied**")
    st.dataframe(changes, hide_index=True, width="stretch")
    accept, dismiss = st.columns(2)
    if accept.button("Accept suggested changes", key="accept_deployment_suggestions"):
        try:
            accept_suggestions(plan, st.session_state.officer)
            st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
            st.rerun()
        except ValueError as error:
            st.info(str(error))
    if dismiss.button("Dismiss suggestions", key="dismiss_deployment_suggestions"):
        plan.pending = []
        plan.review_checkpoint = ""
        st.rerun()


def render_inputs(plan, cfg, request_guidance, stage, save_project):
    if plan.ui_step == 0:
        project_screen(plan)
        return
    rows = manpower_screen(plan)
    key = st.session_state.get("six_editor_key", "")
    if key and st.session_state.get(key, {}).get("edited_rows"):
        commit_rows(plan, rows)
    review_summary(plan)
    assistant_changes(plan)
    errors = confirmation_errors(
        plan, st.session_state.officer or LOCAL_ACTOR, load_records(), checkpoint="manpower"
    )
    if plan.pending:
        errors.append("Accept or dismiss the assistant suggestions before confirming your deployment.")
    show_missing(errors)
    already_confirmed = "plan" in plan.confirmations and not plan.pending and not plan.working_notes
    primary, secondary = st.columns(2)
    if primary.button(
        "Continue to starting rates" if already_confirmed else "Confirm and continue",
        key="use_manpower_plan",
        type="primary",
        width="stretch",
        disabled=bool(errors),
    ):
        try:
            validate_project(plan)
            validate_manpower(plan)
            if already_confirmed:
                plan.ui_step = 3
                st.rerun()
            prepared = prepare_review(plan, "manpower", load_records())
            if not prepared["ready"]:
                raise ValueError("; ".join(prepared.get("missing_inputs", [])))
            accept_review(plan, st.session_state.officer or LOCAL_ACTOR, load_records())
            plan.ui_step = 3
            save_project()
            st.rerun()
        except ValueError as error:
            st.info(str(error))
    if secondary.button("Discuss deployment with AI", key="revise_manpower_plan", width="stretch"):
        st.session_state.manpower_help_open = True
        st.rerun()
