"""Streamlit UI for Agent 2 Track 3."""

from __future__ import annotations

import json
from datetime import date
from io import StringIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.agent2.track3 import (
    REQUIRED_COLUMNS,
    Track3InputError,
    comparability_issues,
    compare_track3,
    export_track3_excel,
    load_synthetic_budget,
    parse_upload,
    role_mapping_options,
    role_mapping_table,
    synthetic_tenderers,
    validation_issues,
)

STEPS = ["Create Project", "Upload Documents", "Verify Data", "Review Analysis", "Export Report"]


def _state():
    defaults = {
        "agent2_step": 1,
        "agent2_project": {},
        "agent2_budget": None,
        "agent2_tenderers": {},
        "agent2_budget_source": "",
        "agent2_result": None,
        "agent2_role_mappings": None,
        "agent2_role_mappings_confirmed": False,
        "agent2_role_mapping_fingerprint": None,
        "agent2_budget_confirmed": False,
        "agent2_limitations": [
            "Historical rate comparisons use the records available to this prototype. Synthetic records are demonstration evidence only and must not be treated as verified market prices.",
            "The analysis compares the verified quantities, units, monthly rates and contract years supplied by the reviewer. It does not independently confirm tender compliance, service quality, staffing adequacy or the authenticity of approvals.",
            "Findings and clarification questions are decision-support prompts. They do not reject a tenderer, recommend an award or replace procurement, legal, finance and operational review.",
            "Source references are derived from uploaded filenames, the first Excel worksheet and row numbers where available. Reviewers must check the original signed submission before relying on a finding.",
            "Any accepted exception, unresolved clarification, manual role match or excluded cost component should be recorded here before the report is used.",
        ],
        "agent2_demo": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _frame_json(frame: pd.DataFrame | None) -> str | None:
    return None if frame is None else frame.to_json(orient="table", index=False)


def _save_project_bytes() -> bytes:
    result = st.session_state.agent2_result
    payload = {
        "version": 1,
        "step": st.session_state.agent2_step,
        "project": st.session_state.agent2_project,
        "budget_source": st.session_state.agent2_budget_source,
        "budget_confirmed": st.session_state.agent2_budget_confirmed,
        "demo": st.session_state.agent2_demo,
        "limitations": st.session_state.agent2_limitations,
        "budget": _frame_json(st.session_state.agent2_budget),
        "tenderers": {name: _frame_json(frame) for name, frame in st.session_state.agent2_tenderers.items()},
        "role_mappings": _frame_json(st.session_state.agent2_role_mappings),
        "role_mappings_confirmed": st.session_state.agent2_role_mappings_confirmed,
        "result": None if result is None else {
            "overall": _frame_json(result.overall), "roles": _frame_json(result.roles),
            "findings": _frame_json(result.findings), "questions": _frame_json(result.questions),
        },
    }
    return json.dumps(payload, indent=2).encode("utf-8")


def _restore_project(content: bytes):
    from services.agent2.track3 import Track3Result

    payload = json.loads(content.decode("utf-8"))
    def read_frame(value):
        return None if value is None else pd.read_json(StringIO(value), orient="table")

    st.session_state.agent2_project = payload.get("project", {})
    st.session_state.agent2_budget_source = payload.get("budget_source", "")
    st.session_state.agent2_budget_confirmed = payload.get("budget_confirmed", False)
    st.session_state.agent2_demo = payload.get("demo", False)
    st.session_state.agent2_limitations = payload.get("limitations", [])
    st.session_state.agent2_budget = read_frame(payload.get("budget"))
    st.session_state.agent2_tenderers = {name: read_frame(value) for name, value in payload.get("tenderers", {}).items()}
    st.session_state.agent2_role_mappings = read_frame(payload.get("role_mappings"))
    st.session_state.agent2_role_mappings_confirmed = payload.get("role_mappings_confirmed", False)
    saved_result = payload.get("result")
    st.session_state.agent2_result = None if saved_result is None else Track3Result(
        overall=read_frame(saved_result["overall"]), roles=read_frame(saved_result["roles"]),
        findings=read_frame(saved_result["findings"]), questions=read_frame(saved_result["questions"]),
    )
    st.session_state.agent2_step = min(5, max(1, int(payload.get("step", 1))))


def _progress(step: int):
    st.progress(step / len(STEPS), text=f"Step {step} of {len(STEPS)} · {STEPS[step - 1]}")
    cols = st.columns(len(STEPS))
    for index, label in enumerate(STEPS, 1):
        cols[index - 1].caption(("● " if index == step else "✓ " if index < step else "○ ") + label)


def _nav(*, back: int | None = None, forward: int | None = None, forward_label: str = "Continue"):
    left, _, right = st.columns([1, 3, 1])
    if back and left.button("← Back", width="stretch"):
        st.session_state.agent2_step = back
        st.rerun()
    if forward and right.button(forward_label, type="primary", width="stretch"):
        st.session_state.agent2_step = forward
        st.rerun()


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def _current_result():
    """Keep active browser sessions compatible with renamed result headings."""
    result = st.session_state.agent2_result
    if result is None:
        return None
    result.overall.rename(
        columns={
            "Variance (SGD)": "Variance to Budget (SGD)",
            "Initial Position": "Assessment",
        },
        inplace=True,
    )
    result.overall["Assessment"] = result.overall["Assessment"].replace(
        {
            "Potential price dive — review": "⚠ Below budget — clarification required",
            "Unusually high — review": "⚠ Above budget — review required",
            "Within review threshold": "✓ Within the current ±10% threshold",
            "⚠ Significantly below budget — review": "⚠ Below budget — clarification required",
            "⚠ Significantly above budget — review": "⚠ Above budget — review required",
            "✓ Within review threshold": "✓ Within the current ±10% threshold",
        }
    )
    result.overall.loc[result.overall["Variance (%)"] > 0, "Assessment"] = "⚠ Above approved budget — review required"
    result.overall.loc[result.overall["Variance (%)"] < 0, "Assessment"] = "⚠ Below budget — clarify assumptions"
    result.overall.loc[result.overall["Variance (%)"] == 0, "Assessment"] = "✓ Matches approved budget"
    result.findings.rename(
        columns={
            "SGD Impact": "Cost Variance to Budget (SGD)",
            "Percentage Impact": "Cost Variance to Budget (%)",
            "Submitted Value": "Tendered Cost (SGD)",
        },
        inplace=True,
    )
    if "Category" not in result.findings:
        result.findings.insert(
            2,
            "Category",
            result.findings["Finding"].map(_finding_category),
        )
    result.findings["Category"] = result.findings["Category"].replace(
        {
            "Escalation": "Year-on-year manpower cost escalation",
            "Pricing / cost": "Role cost variance",
            "Quantity / deployment": "Staffing quantity and deployment",
        }
    )
    return result


def _finding_category(text: str) -> str:
    value = str(text).casefold()
    if "increase" in value and "contract year" in value:
        return "Year-on-year manpower cost escalation"
    if "missing" in value:
        return "Missing role / coverage"
    if "proposes" in value and "budgeted" in value:
        return "Staffing quantity and deployment"
    return "Role cost variance"


def _overall_style(frame: pd.DataFrame):
    """Use colour plus explicit assessment text; colour is never the only signal."""
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    for index, row in frame.iterrows():
        variance = float(row["Variance (%)"])
        if variance > 0:
            css = "background-color: #FDE8E8; color: #8A1C1C; font-weight: 600"
        elif variance < 0:
            css = "background-color: #FFF1D6; color: #7A4A00; font-weight: 600"
        else:
            css = "background-color: #E7F6EC; color: #176B3A; font-weight: 600"
        for column in ["Variance to Budget (SGD)", "Variance (%)", "Assessment"]:
            styles.loc[index, column] = css
    return (
        frame.style.format(
            {
                "Approved Budget (SGD)": "S$ {:,.2f}",
                "Tendered Cost (SGD)": "S$ {:,.2f}",
                "Variance to Budget (SGD)": "S$ {:,.2f}",
                "Variance (%)": "{:.1%}",
            }
        ).apply(lambda _: styles, axis=None)
    )


def _variance_style(frame: pd.DataFrame, columns: list[str]):
    """Apply consistent above/below-budget colour cues to signed variances."""
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    for index, row in frame.iterrows():
        for column in columns:
            value = row.get(column)
            if pd.isna(value):
                continue
            styles.loc[index, column] = (
                "background-color: #FDE8E8; color: #8A1C1C; font-weight: 600"
                if float(value) > 0
                else "background-color: #FFF1D6; color: #7A4A00; font-weight: 600"
                if float(value) < 0
                else "background-color: #E7F6EC; color: #176B3A; font-weight: 600"
            )
    formats = {
        column: "{:+.1%}" if "(%)" in column else "{:+,.1f}" if column == "Quantity Variance" else "S$ {:+,.2f}"
        for column in columns
    }
    return frame.style.format(formats, na_rep="—").apply(lambda _: styles, axis=None)


def _finding_style(frame: pd.DataFrame):
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    severity_css = {
        "High": "background-color: #FDE8E8; color: #8A1C1C; font-weight: 700",
        "Medium": "background-color: #FFF1D6; color: #7A4A00; font-weight: 700",
        "Low": "background-color: #E7F6EC; color: #176B3A; font-weight: 700",
    }
    for index, row in frame.iterrows():
        styles.loc[index, "Severity"] = severity_css.get(str(row.get("Severity")), "")
        for column in ["Cost Variance to Budget (SGD)", "Cost Variance to Budget (%)"]:
            value = row.get(column)
            if pd.notna(value):
                styles.loc[index, column] = (
                    "background-color: #FDE8E8; color: #8A1C1C; font-weight: 600"
                    if float(value) > 0 else "background-color: #FFF1D6; color: #7A4A00; font-weight: 600"
                )
    return frame.style.format(
        {
            "Cost Variance to Budget (SGD)": "S$ {:+,.2f}",
            "Cost Variance to Budget (%)": "{:+.1%}",
            "Tendered Cost (SGD)": "S$ {:,.2f}",
            "Approved Budget Value": "S$ {:,.2f}",
        }, na_rep="—"
    ).apply(lambda _: styles, axis=None)


def _editor(label: str, frame: pd.DataFrame, key: str) -> pd.DataFrame:
    st.markdown(f"#### {label}")
    edited = st.data_editor(
        frame,
        key=key,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Role": st.column_config.TextColumn(required=True, help="Keep the tenderer's original title."),
            "Contract Year": st.column_config.NumberColumn(min_value=1, step=1, required=True),
            "Quantity": st.column_config.NumberColumn(min_value=0.0, step=0.5, required=True),
            "Quantity Unit": st.column_config.SelectboxColumn(options=["headcount", "fte"], required=True),
            "Monthly Rate (SGD)": st.column_config.NumberColumn(min_value=0.0, format="S$ %.2f", required=True),
            "Source": st.column_config.TextColumn(required=True),
        },
    )
    issues = validation_issues(edited)
    if issues.empty:
        st.success(f"{len(edited)} verified rows ready for analysis.", icon="✅")
    else:
        st.warning(f"Resolve {len(issues)} missing or invalid value(s). Blank values are not treated as zero.")
        st.dataframe(issues, hide_index=True, width="stretch")
    return edited


def render_agent2_track3():
    _state()
    st.caption("FM MANPOWER COST ASSISTANT · AGENT 2 · TRACK 3")
    top, exit_col = st.columns([5, 1])
    top.title("Compare tenderers against an approved budget")
    if exit_col.button("Change track", width="stretch"):
        st.session_state.selected_track = None
        st.rerun()
    st.write(
        "Compare manpower costs and deployment against your approved budget, identify key variances "
        "and generate clarification questions. You make the final evaluation decision."
    )
    step = st.session_state.agent2_step
    _progress(step)

    if st.session_state.agent2_project:
        project_name = st.session_state.agent2_project.get("name", "tender-review").replace(" ", "_")
        st.download_button(
            "Save project for later",
            data=_save_project_bytes(),
            file_name=f"{project_name}_Track3_Project.json",
            mime="application/json",
            help="Download the full working project, including verified data, role matches and officer decisions.",
        )

    if step == 1:
        st.header("Create a tender review project")
        st.write("Start with the basic contract context. Only the project name is required.")
        saved_project = st.file_uploader("Resume a saved Track 3 project", type=["json"], key="agent2_saved_project")
        if saved_project and st.button("Resume saved project"):
            try:
                _restore_project(saved_project.getvalue())
                st.success("Saved project restored. You can continue reviewing and amend earlier decisions.")
                st.rerun()
            except Exception:
                st.error("This file is not a valid saved Track 3 project.")
        project = st.session_state.agent2_project
        with st.form("agent2_project_form"):
            name = st.text_input("Project name *", value=project.get("name", ""), placeholder="e.g. Central Campus IFM Tender")
            c1, c2 = st.columns(2)
            facility = c1.selectbox(
                "Building / facility type",
                ["Not specified", "Commercial", "Institutional", "Data Centre", "Healthcare", "Industrial", "Other"],
                index=["Not specified", "Commercial", "Institutional", "Data Centre", "Healthcare", "Industrial", "Other"].index(project.get("facility_type", "Not specified")),
            )
            service = c2.selectbox(
                "FM service category",
                ["Integrated Facilities Management", "Mechanical & Electrical Maintenance", "Cleaning Services", "Security Services", "Building Maintenance", "Other FM Services"],
                index=["Integrated Facilities Management", "Mechanical & Electrical Maintenance", "Cleaning Services", "Security Services", "Building Maintenance", "Other FM Services"].index(project.get("service", "Integrated Facilities Management")),
            )
            c3, c4, c5, c6 = st.columns(4)
            base_years = c3.number_input(
                "Base contract period (years)",
                1,
                20,
                int(project.get("base_years", project.get("duration", 6))),
            )
            option_years = c4.number_input(
                "Option period (years, if any)",
                0,
                20,
                int(project.get("option_years", 0)),
                help="Enter 0 if the contract has no optional extension period.",
            )
            start = c5.date_input("Contract start date", value=date.fromisoformat(project.get("start", "2027-01-01")))
            reference = c6.text_input("Tender reference number", value=project.get("reference", ""))
            description = st.text_area("Project description (optional)", value=project.get("description", ""))
            submitted = st.form_submit_button("Save project and continue", type="primary", width="stretch")
        if submitted:
            if not name.strip():
                st.error("Enter a project name before continuing.")
            elif base_years + option_years > 20:
                st.error("The base and option periods together cannot exceed 20 years.")
            else:
                st.session_state.agent2_project = {
                    "name": name.strip(), "facility_type": facility, "service": service,
                    "base_years": base_years,
                    "option_years": option_years,
                    "duration": base_years + option_years,
                    "start": start.isoformat(), "reference": reference.strip(),
                    "description": description.strip(), "currency": "SGD",
                }
                st.session_state.agent2_step = 2
                st.rerun()

    elif step == 2:
        st.header("Upload the documents for comparison")
        st.info("For a quick tour, load the clearly labelled synthetic example. No OpenAI key is required.")
        if st.button("Load synthetic approved budget and 3 tenderers", type="primary", width="stretch"):
            budget, document = load_synthetic_budget()
            st.session_state.agent2_budget = budget
            st.session_state.agent2_tenderers = synthetic_tenderers(budget)
            st.session_state.agent2_budget_source = document.label
            st.session_state.agent2_project["budget_source"] = document.label
            st.session_state.agent2_project.update(
                {
                    "budget_id": document.budget_id,
                    "budget_revision": document.revision,
                    "budget_approval_reference": document.approval.approval_reference,
                    "budget_confirmed": True,
                }
            )
            st.session_state.agent2_budget_confirmed = True
            st.session_state.agent2_demo = True
            st.session_state.agent2_step = 3
            st.rerun()

        st.subheader("A. Approved manpower budget")
        source = st.text_input("Budget source / reference", value=st.session_state.agent2_budget_source, placeholder="e.g. Management-approved FY2027 manpower budget")
        budget_file = st.file_uploader("Upload approved manpower budget", type=["csv", "xlsx", "xls", "json"], key="agent2_budget_upload")
        if budget_file and st.button("Read approved budget"):
            try:
                st.session_state.agent2_budget = parse_upload(budget_file.name, budget_file.getvalue())
                st.session_state.agent2_budget_source = source or budget_file.name
                st.session_state.agent2_project["budget_source"] = source or budget_file.name
                st.session_state.agent2_budget_confirmed = False
                st.success("Budget schedule loaded. Verify every extracted value in the next step.")
            except Track3InputError as exc:
                st.error(str(exc))
        if st.session_state.agent2_budget is not None and not st.session_state.agent2_demo:
            st.caption("Confirm that this is the current management-approved budget before comparison.")
            approval_reference = st.text_input(
                "Approval reference *",
                value=st.session_state.agent2_project.get("budget_approval_reference", ""),
                placeholder="e.g. approval paper, email or system reference",
            )
            revision = st.text_input(
                "Budget revision *",
                value=str(st.session_state.agent2_project.get("budget_revision", "")),
                placeholder="e.g. Rev 2",
            )
            confirmed = st.checkbox(
                "I confirm this is the current approved manpower budget for this tender.",
                value=st.session_state.agent2_budget_confirmed,
            )
            st.session_state.agent2_budget_confirmed = confirmed
            st.session_state.agent2_project.update(
                {
                    "budget_approval_reference": approval_reference.strip(),
                    "budget_revision": revision.strip(),
                    "budget_confirmed": confirmed,
                }
            )

        st.subheader("B. Tenderer submissions")
        tenderer_name = st.text_input("Tenderer name", placeholder="e.g. Tenderer A")
        tender_files = st.file_uploader("Upload one verified manpower schedule", type=["csv", "xlsx", "xls", "json"], accept_multiple_files=True, key="agent2_tender_upload")
        if st.button("Add tenderer"):
            if not tenderer_name.strip() or not tender_files:
                st.error("Enter a tenderer name and select at least one schedule.")
            else:
                try:
                    if tenderer_name.strip() in st.session_state.agent2_tenderers:
                        raise Track3InputError("A tenderer with this name already exists. Remove or rename it before uploading again.")
                    frames = [parse_upload(file.name, file.getvalue()) for file in tender_files]
                    st.session_state.agent2_tenderers[tenderer_name.strip()] = pd.concat(frames, ignore_index=True)
                    st.success(f"{tenderer_name.strip()} added. Verify the extracted schedule before analysis.")
                except Track3InputError as exc:
                    st.error(str(exc))
        if st.session_state.agent2_tenderers:
            st.write("**Tenderers added:** " + ", ".join(st.session_state.agent2_tenderers))
        approval_ready = st.session_state.agent2_budget_confirmed and bool(
            st.session_state.agent2_project.get("budget_approval_reference")
        ) and bool(str(st.session_state.agent2_project.get("budget_revision", "")).strip())
        ready = st.session_state.agent2_budget is not None and bool(st.session_state.agent2_tenderers) and approval_ready
        if not ready:
            st.caption("Add one confirmed approved budget, its approval reference and revision, and at least one tenderer to continue.")
        left, _, right = st.columns([1, 3, 1])
        if left.button("← Back", width="stretch"):
            st.session_state.agent2_step = 1
            st.rerun()
        if right.button("Verify extracted data", type="primary", disabled=not ready, width="stretch"):
            st.session_state.agent2_step = 3
            st.rerun()

    elif step == 3:
        st.header("Verify the extracted manpower data")
        st.write("Correct any value below. The analysis uses only the information you confirm here.")
        if st.session_state.agent2_demo:
            st.warning("SYNTHETIC DEMONSTRATION DATA — not real tenders, market evidence or management approval.")
        budget = _editor("Approved budget", st.session_state.agent2_budget, "agent2_budget_editor")
        st.session_state.agent2_budget = budget
        verified = validation_issues(budget).empty
        tenderers = {}
        for index, (name, frame) in enumerate(st.session_state.agent2_tenderers.items()):
            edited = _editor(name, frame, f"agent2_tender_editor_{index}")
            tenderers[name] = edited
            verified = verified and validation_issues(edited).empty
        st.session_state.agent2_tenderers = tenderers
        mapping = role_mapping_table({"Approved budget": budget, **tenderers})
        previous = st.session_state.agent2_role_mappings
        if previous is not None and not previous.empty:
            if {"Submitted by", "Role title in submission", "Compare as"} <= set(previous.columns):
                saved = previous.set_index(["Submitted by", "Role title in submission"])["Compare as"]
                mapping["Compare as"] = mapping.apply(
                    lambda row: saved.get(
                        (row["Submitted by"], row["Role title in submission"]), row["Compare as"]
                    ),
                    axis=1,
                )
        st.markdown("#### Match equivalent roles for comparison")
        st.write(
            "Different tenderers may use different titles for similar work. For each submitted title, "
            "choose the common role it should be compared as. Check the duties before combining roles; "
            "the original submitted title will still be retained."
        )
        st.caption(
            "The choices include the standard FM role list and every submitted title, so an unmatched role "
            "can remain separate instead of being forced into the wrong category."
        )
        st.info(
            "To change a match, click a cell under **Role used for comparison** and select a different role. "
            "You can revise any suggested match before confirming the table once below."
        )
        mapping = st.data_editor(
            mapping,
            hide_index=True,
            width="stretch",
            key="agent2_role_mapping_editor",
            column_config={
                "Submitted by": st.column_config.TextColumn(help="The approved budget or tenderer that used this title."),
                "Role title in submission": st.column_config.TextColumn(help="The role title exactly as submitted."),
                "Compare as": st.column_config.SelectboxColumn(
                    "Role used for comparison",
                    options=role_mapping_options(mapping),
                    required=True,
                    help="Click the cell to replace the suggested role with the role that should be used in the comparison.",
                ),
                "Why this is suggested": st.column_config.TextColumn(
                    help="Explains whether the title already matches, uses a recognised alternative, or needs your decision."
                ),
            },
            disabled=["Submitted by", "Role title in submission", "Why this is suggested"],
        )
        st.session_state.agent2_role_mappings = mapping
        valid_matches = bool(mapping["Compare as"].astype(str).str.strip().all())
        mapping_fingerprint = tuple(
            mapping[["Submitted by", "Role title in submission", "Compare as"]]
            .astype(str)
            .itertuples(index=False, name=None)
        )
        previous_fingerprint = st.session_state.agent2_role_mapping_fingerprint
        if previous_fingerprint is not None and previous_fingerprint != mapping_fingerprint:
            st.session_state.agent2_role_mappings_confirmed = False
        st.session_state.agent2_role_mapping_fingerprint = mapping_fingerprint
        mappings_confirmed = st.checkbox(
            "I have checked the role matches and confirm they can be used for this comparison.",
            value=st.session_state.agent2_role_mappings_confirmed,
            disabled=not valid_matches,
        )
        st.session_state.agent2_role_mappings_confirmed = mappings_confirmed
        mapping_dict = {
            (row["Submitted by"], row["Role title in submission"]): row["Compare as"]
            for _, row in mapping.iterrows()
        }
        comparison_errors = pd.DataFrame()
        if verified and mappings_confirmed:
            comparison_errors = comparability_issues(
                budget,
                tenderers,
                expected_years=int(st.session_state.agent2_project.get("duration", 0)) or None,
                role_mappings=mapping_dict,
            )
        if not mappings_confirmed:
            st.warning("Review the proposed role matches, make any changes, then confirm once to continue.")
        elif not comparison_errors.empty:
            st.error("Resolve the following completeness or comparability issues before comparison.")
            st.dataframe(comparison_errors, hide_index=True, width="stretch")
        left, _, right = st.columns([1, 3, 1])
        if left.button("← Back to uploads", width="stretch"):
            st.session_state.agent2_step = 2
            st.rerun()
        if right.button("Confirm data and compare", type="primary", disabled=not (verified and mappings_confirmed and comparison_errors.empty), width="stretch"):
            try:
                st.session_state.agent2_result = compare_track3(
                    budget,
                    tenderers,
                    expected_years=int(st.session_state.agent2_project.get("duration", 0)) or None,
                    benchmark_year=date.fromisoformat(st.session_state.agent2_project["start"]).year,
                    role_mappings=mapping_dict,
                )
                st.session_state.agent2_step = 4
                st.rerun()
            except Track3InputError as exc:
                st.error(str(exc))

    elif step == 4:
        result = _current_result()
        if result is None:
            st.session_state.agent2_step = 3
            st.rerun()
        st.header("Review tenderer differences")
        st.info(
            "These results highlight differences for you to check. "
            "They do not decide which tenderer should be selected."
        )
        total_findings = len(result.findings)
        affected_tenderers = result.findings["Tenderer"].nunique() if total_findings else 0
        category_count = result.findings["Category"].nunique() if total_findings else 0
        a, b, c = st.columns(3)
        a.metric("Tenderers compared", len(result.overall))
        b.metric("Tenderers requiring attention", affected_tenderers)
        c.metric("Findings to review", total_findings)
        overview = pd.DataFrame()
        if total_findings:
            overview = (
                result.findings.groupby("Category", as_index=False)
                .agg(
                    **{
                        "Findings to review": ("Finding ID", "count"),
                        "Affected tenderers": ("Tenderer", lambda values: ", ".join(sorted(set(values)))),
                    }
                )
                .sort_values(["Findings to review", "Category"], ascending=[False, True])
            )
        overall_tab, role_tab, questions_tab = st.tabs(
            ["Overall Cost", "Roles, Deployment & Findings", "Clarification Questions"]
        )
        with overall_tab:
            st.dataframe(
                _overall_style(result.overall),
                hide_index=True, width="stretch",
            )
            st.caption(
                "🟢 Matches approved budget   ·   🔴 Above approved budget — review required   ·   "
                "🟠 Below approved budget — clarify assumptions before treating it as a saving"
            )
            budget_value = float(result.overall["Approved Budget (SGD)"].iloc[0])
            chart = result.overall.copy()
            chart["Comparison label"] = chart["Variance (%)"].map(
                lambda value: f"{abs(value):.1%} {'above' if value > 0 else 'below' if value < 0 else 'at'} budget"
            )
            chart["Colour"] = chart["Variance (%)"].map(
                lambda value: "#C84A4A" if value > 0 else "#D28B21" if value < 0 else "#2E8B57"
            )
            chart["Bar label"] = chart.apply(
                lambda row: f"S$ {row['Tendered Cost (SGD)']:,.0f}<br>{row['Comparison label']}", axis=1
            )
            st.caption(f"Approved budget reference: S$ {budget_value:,.0f} (dotted line)")
            figure = go.Figure(
                go.Bar(
                    x=chart["Tenderer"],
                    y=chart["Tendered Cost (SGD)"],
                    name="Tendered manpower cost",
                    marker_color=chart["Colour"],
                    marker_line_width=0,
                    text=chart["Bar label"],
                    textposition="outside",
                    customdata=chart[["Variance to Budget (SGD)", "Variance (%)", "Assessment"]],
                    hovertemplate=(
                        "<b>%{x}</b><br>Tendered cost: S$ %{y:,.2f}<br>"
                        "Variance to budget: S$ %{customdata[0]:,.2f} (%{customdata[1]:.1%})<br>"
                        "Assessment: %{customdata[2]}<extra></extra>"
                    ),
                )
            )
            figure.add_hline(
                y=budget_value,
                line_dash="dot",
                line_width=3,
                line_color="#52606D",
            )
            figure.update_layout(
                title="Tenderer submission costs against approved budget",
                xaxis_title="Tenderer",
                yaxis_title="Full contract manpower cost (SGD)",
                showlegend=False,
                hovermode="x",
                bargap=0.38,
                barcornerradius=8,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin={"l": 20, "r": 20, "t": 70, "b": 20},
                yaxis={
                    "tickprefix": "S$ ",
                    "tickformat": ",.0f",
                    "rangemode": "tozero",
                    "range": [0, float(chart["Tendered Cost (SGD)"].max()) * 1.18],
                    "gridcolor": "rgba(82,96,109,0.16)",
                    "zeroline": False,
                },
                xaxis={"showgrid": False},
            )
            st.plotly_chart(figure, width="stretch", key="agent2_budget_comparison_chart")
            st.caption(
                "🟢 Matches budget   ·   🔴 Above-budget review   ·   "
                "🟠 Below-budget clarification   ·   ··· Approved budget"
            )
            if total_findings:
                st.markdown("#### What needs your attention")
                st.write(
                    f"The comparison identified {total_findings} findings across {category_count} review categories. "
                    "Open **Roles, Deployment & Findings** for the supporting figures and suggested actions."
                )
                st.dataframe(overview, hide_index=True, width="stretch")
            else:
                st.success("No findings exceeded the current review thresholds.")
        with role_tab:
            selected = st.selectbox("Show tenderer", list(result.overall["Tenderer"]))
            role_view = result.roles[result.roles["Tenderer"] == selected]
            st.dataframe(
                _variance_style(
                    role_view,
                    ["Quantity Variance", "Role Cost Variance to Budget (SGD)", "Role Cost Variance to Budget (%)"],
                ),
                hide_index=True, width="stretch",
            )
            st.caption(
                "🔴 Positive values exceed the approved budget or quantity · 🟠 Negative values are below it · "
                "‘Comparison with Similar Past Rates’ shows where the submitted monthly rate sits against comparable records; "
                "‘Number of Comparable Past Records’ shows how many records support that comparison."
            )
            st.markdown("#### Findings to review")
            st.caption(
                "🔴 High: may materially affect affordability, completeness or service coverage · "
                "🟠 Medium: requires clarification before relying on the comparison · 🟢 Low: note and monitor."
            )
            if result.findings.empty:
                st.success("No findings require review.")
            else:
                st.dataframe(_finding_style(result.findings.drop(columns=["Review Status", "Officer Comment"], errors="ignore")), hide_index=True, width="stretch")
                st.markdown("##### Record the officer’s decision")
                reviewed = st.data_editor(
                    result.findings[["Finding ID", "Tenderer", "Finding", "Review Status", "Officer Comment"]],
                    key="agent2_findings_editor",
                    width="stretch", hide_index=True,
                    column_config={
                        "Review Status": st.column_config.SelectboxColumn(options=["Pending Review", "Reviewed", "Resolved"], required=True),
                        "Officer Comment": st.column_config.TextColumn(help="Record your decision or accepted exception."),
                    },
                    disabled=["Finding ID", "Tenderer", "Finding"],
                )
                result.findings = result.findings.drop(columns=["Review Status", "Officer Comment"]).merge(
                    reviewed[["Finding ID", "Review Status", "Officer Comment"]], on="Finding ID", how="left"
                )
                st.session_state.agent2_result = result
        with questions_tab:
            st.dataframe(result.questions, hide_index=True, width="stretch")
        left, _, right = st.columns([1, 3, 1])
        if left.button("← Revise verified data", width="stretch"):
            st.session_state.agent2_step = 3
            st.rerun()
        if right.button("Review and prepare report", type="primary", width="stretch"):
            st.session_state.agent2_step = 5
            st.rerun()

    else:
        result = _current_result()
        st.header("Export the tender review report")
        st.write("The workbook contains the comparison, findings, tenderer-specific questions and limitations.")
        limitations_text = st.text_area(
            "Limitations and accepted exceptions",
            value="\n".join(st.session_state.agent2_limitations),
            height=150,
            help="Include unresolved red flags that the final costing or evaluation did not address.",
        )
        limitations = [line.strip() for line in limitations_text.splitlines() if line.strip()]
        st.session_state.agent2_limitations = limitations
        pending = int((result.findings["Review Status"] == "Pending Review").sum()) if not result.findings.empty else 0
        acknowledged = True
        if pending:
            st.warning(f"{pending} finding(s) are still pending review.")
            acknowledged = st.checkbox(
                "I acknowledge that pending findings remain and will not treat this report as an award recommendation."
            )
        mapping = st.session_state.agent2_role_mappings
        workbook = export_track3_excel(
            {**st.session_state.agent2_project, "reviewer": "Local reviewing officer"},
            result,
            limitations,
            budget=st.session_state.agent2_budget,
            tenderers=st.session_state.agent2_tenderers,
            role_mappings=mapping,
            thresholds={"Overall / role cost variance": 0.10, "Annual escalation": 0.08},
        )
        st.download_button(
            "Download Track 3 Excel report",
            data=workbook,
            file_name="Track_3_Tender_Review.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", width="stretch",
            disabled=not acknowledged,
        )
        if acknowledged:
            st.success("Report prepared. Check pending findings before management or procurement discussion.")
        _nav(back=4)
