"""Project/manpower screens. Editing and navigation make no model calls or approvals."""

from uuid import uuid4

import pandas as pd
import streamlit as st

from services.hybrid import comparison_rows, save_input_table, save_project_inputs, validate_comparison
from services.journey import working_draft
from services.models import Role
from services.role_reference import role_titles
from services.workflow import missing_for_gate

CONTEXTS = {"Existing contract": "existing contract", "New contract/site/service": "new site / service"}
CURRENT = {
    "Current deployment known (enter what you know)": "known",
    "Existing deployment unavailable": "unavailable",
    "New contract/site—no existing deployment": "no existing deployment",
}


def project_changed():
    plan = st.session_state.plan
    p = working_draft(plan).profile
    prefix = f"six_{plan.id}_project"

    def value(name, default):
        return st.session_state.get(prefix + name, default)

    try:
        save_project_inputs(
            plan,
            value("_brief", p.description),
            value("_year", p.start_year),
            value("_base", p.base_years),
            value("_option", p.option_years),
            CONTEXTS.get(value("_kind", ""), plan.contract_kind),
            name=value("_name", p.name),
            start=value("_exact", p.start),
            clear_start=prefix + "_exact" in st.session_state and value("_exact", p.start) is None,
        )
    except ValueError:
        st.session_state.input_error = (
            "Check the contract dates and numeric inputs. Your earlier draft is retained."
        )


def project_screen(plan):
    p = working_draft(plan).profile
    prefix = f"six_{plan.id}_project"
    st.text_input(
        "Project name (optional)",
        p.name if p.name != "Untitled project" else "",
        key=prefix + "_name",
        on_change=project_changed,
    )
    st.text_area(
        "Short project brief",
        p.description,
        height=100,
        key=prefix + "_brief",
        on_change=project_changed,
        placeholder="What must this team manage? Include known operating hours or critical functions.",
    )
    labels = list(CONTEXTS)
    selected = next((i for i, label in enumerate(labels) if CONTEXTS[label] == plan.contract_kind), None)
    st.radio(
        "Are you replacing an existing contract or planning a new site/service?",
        labels,
        index=selected,
        key=prefix + "_kind",
        on_change=project_changed,
        horizontal=True,
    )
    a, b, c = st.columns(3)
    a.number_input(
        "Contract start year",
        min_value=1900,
        max_value=2200,
        value=p.start_year or (p.start.year if p.start else None),
        key=prefix + "_year",
        on_change=project_changed,
    )
    b.number_input(
        "Base contract years",
        min_value=1,
        max_value=20,
        value=p.base_years,
        key=prefix + "_base",
        on_change=project_changed,
    )
    c.number_input(
        "Option years",
        min_value=0,
        max_value=20,
        value=p.option_years,
        key=prefix + "_option",
        on_change=project_changed,
        help="Use 0 when there are no option years.",
    )
    with st.expander("Exact start date, if known (optional)"):
        st.date_input(
            "Exact contract start date",
            value=p.start,
            key=prefix + "_exact",
            on_change=project_changed,
            help="Effective-date policies and calendar-year schedules need an exact date. Otherwise the start year is enough.",
        )


def validate_project(plan):
    errors = missing_for_gate(working_draft(plan), "profile")
    if plan.contract_kind == "unspecified":
        errors.append("Indicate whether this is an existing contract or a new site/service.")
    if errors:
        raise ValueError("; ".join(errors))


def commit_rows(plan, rows, status=None, support=None):
    p = working_draft(plan).profile
    save_input_table(
        plan,
        p.description,
        p.start_year or (p.start.year if p.start else None),
        p.base_years,
        p.option_years,
        rows,
        plan.input_support if support is None else support,
        current_status=status,
    )


def editor_changed(key):
    plan = st.session_state.plan
    rows = [dict(r) for r in st.session_state[key + "_base"]]
    for index, values in st.session_state.get(key, {}).get("edited_rows", {}).items():
        rows[int(index)].update(values)
    try:
        commit_rows(plan, rows)
    except ValueError:
        st.session_state.input_error = "Use non-negative quantities up to 10,000 and valid role titles. The last valid draft is retained."


def support_changed(key):
    plan = st.session_state.plan
    commit_rows(plan, comparison_rows(plan), support=st.session_state[key])


def current_status_changed(key):
    plan = st.session_state.plan
    commit_rows(plan, comparison_rows(plan), status=CURRENT[st.session_state[key]])
    st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1


def manpower_screen(plan):
    st.write(
        "What manpower is deployed under your current contract, and what are you proposing for the new contract? The assistant will review the differences and identify points that may need clarification."
    )
    st.caption(
        "Common roles to consider, not mandatory positions. Blank proposed quantity means unanswered; 0 means not included. Current deployment is optional, not proof of the right quantity."
    )
    prefix = f"six_{plan.id}_manpower_{st.session_state.get('six_epoch', 0)}"
    statuses = list(CURRENT)
    selected = next(i for i, label in enumerate(statuses) if CURRENT[label] == plan.current_deployment_status)
    st.radio(
        "Current contract deployment",
        statuses,
        index=selected,
        key=prefix + "_status",
        horizontal=True,
        on_change=current_status_changed,
        args=(prefix + "_status",),
    )
    rows = comparison_rows(plan)
    key = prefix + "_table"
    st.session_state[key + "_base"] = rows
    frame = pd.DataFrame(rows)
    for name in ["Current quantity / FTE", "Proposed quantity / FTE", "Change"]:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    edited = st.data_editor(
        frame,
        key=key,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        height=350,
        disabled=["Change"]
        + (["Current quantity / FTE"] if plan.current_deployment_status != "known" else []),
        on_change=editor_changed,
        args=(key,),
        column_config={
            "id": None,
            "Deployment": None,
            "Role title": st.column_config.TextColumn(required=True, width="medium"),
            "Current quantity / FTE": st.column_config.NumberColumn(
                "Current", min_value=0.0, max_value=10000.0, step=0.5, width="small"
            ),
            "Proposed quantity / FTE": st.column_config.NumberColumn(
                "Proposed", min_value=0.0, max_value=10000.0, step=0.5, width="small"
            ),
            "Change": st.column_config.NumberColumn("Change", width="small", format="%+.2f"),
            "Quantity basis": st.column_config.SelectboxColumn(
                options=["unspecified", "headcount", "FTE", "posts"], width="small"
            ),
            "Duties / deployment notes": st.column_config.TextColumn(
                "Duties / deployment notes (optional)", width="large"
            ),
        },
    )
    st.caption(
        "Headcount means whole people each costed at the full monthly charge; FTE permits shared/fractional allocation. The basis applies to both columns: if current units differ, leave that figure blank and explain in notes. Convert posts before pricing."
    )
    a, b = st.columns(2)
    if a.button(
        "Copy current quantities into proposed plan",
        disabled=plan.current_deployment_status != "known",
        key="copy_current",
    ):
        values = edited.to_dict("records")
        for row in values:
            if pd.notna(row["Current quantity / FTE"]):
                row["Proposed quantity / FTE"] = row["Current quantity / FTE"]
        commit_rows(plan, values)
        st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
        st.rerun()
    if b.button("Mark remaining unused roles as zero", key="mark_unused_zero"):
        values = edited.to_dict("records")
        for row in values:
            if pd.isna(row["Proposed quantity / FTE"]):
                row["Proposed quantity / FTE"] = 0.0
        commit_rows(plan, values)
        st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
        st.rerun()
    selected = st.multiselect(
        "Add another role",
        role_titles(),
        accept_new_options=True,
        key=prefix + "_add",
        placeholder="Search the reviewed inventory or type a custom title",
    )
    if st.button("Add selected roles", key="add_selected_roles", disabled=not selected):
        values = edited.to_dict("records")
        for title in selected:
            if title.casefold() not in {r["Role title"].casefold() for r in values}:
                r = Role(id="role-" + uuid4().hex[:8], label=title)
                values.append(
                    {
                        "id": r.id,
                        "Role title": title,
                        "Proposed quantity / FTE": None,
                        "Current quantity / FTE": None,
                        "Quantity basis": "unspecified",
                    }
                )
        commit_rows(plan, values)
        st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
        st.rerun()
    st.text_area(
        "Existing internal staff, external contractors or combined duties (optional)",
        plan.input_support,
        key=prefix + "_support",
        height=85,
        on_change=support_changed,
        args=(prefix + "_support",),
        placeholder="For example: FM also performs FSM duties; trade contractors deliver specialist servicing; MA supervises.",
    )
    return edited.to_dict("records")


def validate_manpower(plan):
    validate_comparison(comparison_rows(plan))
