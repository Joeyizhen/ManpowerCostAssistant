"""Current checkpoint: structured project inputs and current/proposed comparison."""

import streamlit as st

from journey_inputs import commit_rows, manpower_screen, project_screen, validate_manpower, validate_project


def render_inputs(plan, cfg, request_guidance, stage, save_project):
    st.subheader("Project and contract details")
    project_screen(plan)
    st.subheader("Current and proposed manpower")
    rows = manpower_screen(plan)
    if st.button("Save input draft"):
        commit_rows(plan, rows)
        save_project()
        st.rerun()
    if st.button("Review my manpower plan", type="primary", disabled=not (cfg.api_key and cfg.model)):
        try:
            commit_rows(plan, rows)
            validate_project(plan)
            validate_manpower(plan)
            plan.manpower_review_requested = True
            save_project()
            request_guidance(
                "Review the supplied brief, contract details, current and proposed quantities, quantity basis, notes and retained answers together. "
                "Summarise meaningful changes. Current staffing is context, not proof of the right quantity. "
                "Zero means excluded; blank means unanswered. Do not automatically create mandatory positions or split a combined role. "
                "Check material gaps, duplicated duties, shared allocations and internal/contractor boundaries. "
                "Ask concise relevant follow-ups or prepare one manpower review. No prices, escalation, qualification questionnaire or approval.",
                stage,
            )
            save_project()
            st.rerun()
        except ValueError as error:
            st.error(str(error))
