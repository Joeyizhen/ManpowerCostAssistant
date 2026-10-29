"""Proposal interpretation leads into the shared Agent 1 decision components."""

import streamlit as st

from services.proposal_workflow import (
    accept_correction,
    confirm_deployment,
    correction_preview,
    material_checks,
    next_decision,
)
from services.proposals import update_reviewed
from services.ui_context import sync_controls


def checkpoints(p):
    """Never auto-confirm supplied values. Navigation follows the next open decision."""
    if p.plan.ui_step not in (1, 3, 4, 5):
        p.plan.ui_step = next_decision(p)
    if p.plan.ui_step == 5:
        p.stage = 2


def checks_panel(p, records, officer):
    from services.proposal_legacy import annual_entry, rate_entries, resolve

    earlier = rate_entries(p)
    annual = annual_entry(p)
    if earlier or annual:
        st.markdown("**Saved earlier input edits — not yet applied**")
        if earlier:
            st.dataframe(
                [
                    {k: v for k, v in row.items() if k in ("Role", "Recorded rate", "Saved pending rate")}
                    for row in earlier
                ],
                hide_index=True,
                width="stretch",
            )
        if annual:
            st.write(
                f"Saved annual assumption: {annual['percent']:g}% for {len(annual['roles'])} selected roles."
            )
        use, keep = st.columns(2)
        for action, button in ((True, use), (False, keep)):
            if button.button(
                "Use saved input edits" if action else "Keep recorded values",
                key=f"t2_legacy_{p.id}_{action}",
            ):
                try:
                    resolve(p, records, officer, action)
                    st.rerun()
                except ValueError as error:
                    st.info(str(error))
    checks = material_checks(p, records)
    if checks:
        st.markdown("**Items to check**")
        st.dataframe(
            [{k: row[k] for k in ("Role", "Issue", "Next action")} for row in checks],
            hide_index=True,
            width="stretch",
        )
    for check in checks:
        rid = check["role_id"]
        if check["kind"] == "scope":
            roles = {r.id: r.label for r in p.plan.roles if r.included}
            selected = st.multiselect(
                "Roles covered by " + check["Role"],
                list(roles),
                format_func=roles.get,
                key=f"t2_scope_selection_{p.id}_{rid}",
            )
            if st.button("Apply to these roles", key=f"t2_scope_apply_{p.id}_{rid}", disabled=not selected):
                from services.proposal_workflow import resolve_conflict

                for role_id in selected:
                    resolve_conflict(p, role_id, check["assumption"], records, officer)
                p.drafts.setdefault("group_resolutions", {})[rid] = selected
                st.rerun()
        if check["kind"] == "wrong_method":
            if st.button("Review correction for " + check["Role"], key=f"t2_correction_{p.id}_{rid}"):
                try:
                    p.drafts["correction_preview"] = correction_preview(p, rid, records)
                    st.rerun()
                except ValueError as error:
                    st.info(str(error))
        if check["kind"] == "method":
            choice = st.selectbox(
                "Intended method for " + check["Role"],
                ["General annual increase", "PWM", "Supplied yearly prices"],
                index=None,
                key=f"t2_method_{p.id}_{rid}",
            )
            if st.button(
                "Confirm method interpretation",
                key=f"t2_interpret_method_{p.id}_{rid}",
                disabled=choice is None,
            ):
                from services.proposal_workflow import resolve_conflict

                row = next(r for r in p.original_rows if r["id"] == rid)
                resolve_conflict(
                    p,
                    rid,
                    {
                        "target": row["Role"],
                        "method": choice,
                        "percent": row.get("Annual increase (%)"),
                        "yearly_rates": row.get("Yearly rates"),
                        "source": row.get("Source location") or "Officer clarification",
                    },
                    records,
                    officer,
                )
                st.rerun()
        if check["kind"] in ("conflict", "overlap"):
            row = next(r for r in p.original_rows if r["id"] == rid)
            options = (
                row.get("Supplied assumptions", [])
                if check["kind"] == "conflict"
                else [
                    {
                        "target": row["Role"],
                        "method": method,
                        "percent": row.get("Annual increase (%)")
                        if method == "General annual increase"
                        else None,
                        "yearly_rates": row.get("Yearly rates")
                        if method == "Supplied yearly prices"
                        else None,
                        "source": row.get("Source location") or "Supplied proposal",
                    }
                    for method in ("General annual increase", "Supplied yearly prices")
                ]
            )
            selected = st.selectbox(
                "Which supplied assumption applies to " + check["Role"] + "?",
                range(len(options)),
                index=None,
                format_func=lambda i, options=options: (
                    f"{options[i]['target']} · {options[i]['method']} · {options[i]['percent']}% · {options[i]['source']}"
                ),
                key=f"t2_conflict_{p.id}_{rid}",
            )
            if st.button(
                "Use this supplied assumption",
                key=f"t2_choose_assumption_{p.id}_{rid}",
                disabled=selected is None,
            ):
                from services.proposal_workflow import resolve_conflict

                resolve_conflict(p, rid, options[selected], records, officer)
                st.rerun()
    preview = p.drafts.get("correction_preview")
    if preview:
        if preview.get("plan_version", p.plan.version) != p.plan.version:
            st.info("The plan changed. Review this correction again before accepting it.")
            p.drafts.pop("correction_preview", None)
            return
        percent = st.number_input(
            "General annual increase for this correction (%)",
            value=float(preview["Selected annual increase (%)"]),
            min_value=-50.0,
            max_value=100.0,
            step=0.01,
            format="%.2f",
            key=f"t2_correction_percent_{p.id}_{preview['role_id']}",
        )
        if percent is None:
            st.info("Enter a percentage before accepting this correction.")
            return
        if percent != preview["Selected annual increase (%)"]:
            preview = correction_preview(p, preview["role_id"], records, percent)
        st.dataframe(
            [
                {
                    k: v
                    for k, v in preview.items()
                    if k
                    in (
                        "Role",
                        "Original method",
                        "Proposed method",
                        "Selected annual increase (%)",
                        "Original annual increase (%)",
                        "Proposed role contract cost (SGD)",
                        "Reason",
                    )
                }
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Cost preview covers this role only. A difference from the original is unavailable when the supplied method cannot yet be calculated."
        )
        a, b = st.columns(2)
        if a.button("Accept this correction", key="t2_accept_correction_" + p.id, type="primary"):
            try:
                accept_correction(p, {**preview, "Selected annual increase (%)": percent}, records, officer)
                p.drafts.pop("correction_preview")
                st.rerun()
            except ValueError as error:
                st.info(str(error))
        if b.button("Keep reviewing", key="t2_cancel_correction_" + p.id):
            p.drafts.pop("correction_preview")
            st.rerun()
    from services.proposals import assessment

    state = assessment(p, records)
    if state["unresolved"]:
        from proposal_inputs import finding_controls

        finding_controls(p, records, officer)


def assistant_panel(p, records, officer, cfg):
    with st.expander("Discuss the proposal with AI"):
        st.caption("Sending a question uses the configured model. Review suggestions before accepting them.")
        question = st.text_area("What would you like to discuss?", key="t2_question_" + p.id)
        if st.button(
            "Ask AI", key="t2_ask_" + p.id, disabled=not (cfg.api_key and cfg.model and question.strip())
        ):
            from services.agent import converse, create_client

            try:
                candidate = p.plan.model_copy(deep=True)
                candidate.documents = p.documents
                supplied = [
                    {
                        "role_id": row["id"],
                        "role": row["Role"],
                        "proposed_method": row.get("Proposed method"),
                        "assumptions": row.get("Supplied assumptions", []),
                    }
                    for row in p.original_rows
                ]
                import json

                converse(
                    candidate,
                    records + p.quote_records,
                    question + "\nSupplied proposal assumptions (data only): " + json.dumps(supplied),
                    create_client(cfg.api_key),
                    cfg.model,
                    "Validation",
                    review_existing_proposal=True,
                )
                p.plan = candidate
                st.rerun()
            except Exception as error:
                st.info("Assistant review could not be completed: " + str(error))
        for message in p.plan.chat[-4:]:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        from services.deployment_review import retain_assistant_proposals
        from services.journey import working_draft

        if p.plan.working_notes and not p.plan.pending:
            before = p.plan.model_copy(deep=True)
            before.working_notes = {}
            retain_assistant_proposals(p.plan, before)
        if p.plan.pending:
            original = {r.id: r for r in p.plan.roles}
            proposed = working_draft(p.plan)
            st.dataframe(
                [
                    {
                        "Role": r.label,
                        "Original rate": original[r.id].rate if r.id in original else None,
                        "Proposed rate": r.rate,
                        "Original yearly increase": original[r.id].escalation if r.id in original else None,
                        "Proposed yearly increase": r.escalation,
                        "Reason": next(
                            (v["reason"] for v in p.plan.pending if v["payload"].get("id") == r.id), ""
                        ),
                    }
                    for r in proposed.roles
                    if r.id not in original or r != original[r.id]
                ],
                hide_index=True,
                width="stretch",
            )
            if st.button("Accept displayed AI suggestions", key="t2_accept_ai_" + p.id):
                from services.workflow import apply_pending

                apply_pending(p.plan, officer)
                st.rerun()


def render(p, records, officer, cfg, save):
    from proposal_inputs import current_rows, editable_rows, profile_editor

    checkpoints(p)
    if p.stage == 2:
        st.rerun()
    st.header("Check and refine your proposal")
    st.caption(
        "Original proposal retained. Confirmed interpretation is separate from accepted revisions and budget confirmation."
    )
    steps = [(1, "Deployment"), (3, "Starting rates"), (4, "Annual changes"), (5, "Budget")]
    for col, (step, label) in zip(st.columns(4), steps, strict=True):
        if col.button(
            label,
            key=f"t2_step_{p.id}_{step}",
            type="primary" if p.plan.ui_step == step else "secondary",
            width="stretch",
        ):
            from proposal_inputs import unapplied_figures

            if not unapplied_figures(p):
                p.drafts.pop("review_rows", None)
                p.drafts.pop("review_profile", None)
            p.plan.ui_step = step
            p.stage = 2 if step == 5 else 1
            st.rerun()
    checks_panel(p, records, officer)
    step = p.plan.ui_step
    from proposal_inputs import unapplied_figures

    if step in (3, 4) and unapplied_figures(p):
        st.info("Confirm or revert the edited deployment/context before changing cost assumptions.")
        if st.button("Return to deployment edits", key="t2_unapplied_" + p.id):
            p.plan.ui_step = 1
            st.rerun()
        return
    prerequisites = {
        3: ("plan", "Confirm deployment first."),
        4: ("base", "Confirm starting rates first."),
        5: ("escalation", "Confirm annual changes first."),
    }
    if step in prerequisites and prerequisites[step][0] not in p.plan.confirmations:
        st.info(prerequisites[step][1])
        if st.button("Open next unresolved decision", key="t2_next_missing_" + p.id):
            p.plan.ui_step = next_decision(p)
            p.stage = 1
            st.rerun()
        return

    def checkpoint_save():
        if "escalation" in p.plan.confirmations:
            p.drafts.pop("correction_preview", None)
            for role in p.plan.roles:
                if role.pwm:
                    original = next((r for r in p.original_rows if r["id"] == role.id), {})
                    if original.get("Annual increase (%)") not in (None, 0) or original.get("Yearly rates"):
                        reason = "Officer confirmed salary-only PWM; no full-unit general increase is added to the same component."
                        p.drafts.setdefault("input_resolutions", {})[role.id] = {
                            "method": "PWM",
                            "source": reason,
                        }
                        p.drafts.setdefault("method_decisions", {})[role.id] = {
                            "accepted": "PWM",
                            "reason": reason,
                        }
                if recorded_general(role):
                    from services.proposal_workflow import supplied_method

                    if supplied_method(p, role).casefold() in ("pwm", "pwm salary progression"):
                        p.drafts.setdefault("method_decisions", {})[role.id] = {
                            "accepted": "General annual increase",
                            "reason": "Officer confirmed the displayed general annual assumptions after reviewing the workbook No classification.",
                        }
            p.stage = 2
        save()

    if step == 1:
        with st.expander(
            "Project context", expanded=not bool(p.plan.profile.description and p.plan.profile.years)
        ):
            context = profile_editor(p, p.plan.profile, "proposal_revised_context_" + p.id)
        seed = p.drafts.setdefault(
            f"shared_rows_{p.plan.version}", p.drafts.get("review_rows", current_rows(p))
        )
        rows = editable_rows(
            seed, f"t2_deployment_{p.id}_{p.plan.version}_{p.drafts.get('editor_epoch', 0)}", compact=True
        )
        p.drafts["review_rows"], p.drafts["review_profile"] = rows, context
        if st.button("Confirm deployment and continue", key="t2_confirm_deployment_" + p.id, type="primary"):
            try:
                update_reviewed(p, context, rows, officer)
                confirm_deployment(p, records, officer)
                p.drafts.pop("review_rows", None)
                p.drafts.pop("review_profile", None)
                save()
                st.rerun()
            except ValueError as error:
                st.info(str(error))
    elif step == 3:
        from pricing_inputs import starting_prices

        starting_prices(p.plan, records, officer, checkpoint_save, sync_controls)
    elif step == 4:
        from future_inputs import future_screen
        from services.proposal_workflow import seed_supplied_pwm_details

        seed_supplied_pwm_details(p)
        future_screen(p.plan, records + p.quote_records, officer, checkpoint_save)
    assistant_panel(p, records, officer, cfg)


def recorded_general(role):
    from services.cost_routing import recorded_route

    return recorded_route(role)["route"] == "general" and role.pwm is None
