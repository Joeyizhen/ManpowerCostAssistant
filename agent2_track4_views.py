"""Guided Streamlit UI for Agent 2 Track 4 historical benchmarking."""

from __future__ import annotations

import json
from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from services.agent import create_client
from services.agent2.track3 import (
    Track3InputError,
    parse_upload,
    role_mapping_options,
    role_mapping_table,
    validation_issues,
)
from services.agent2.track4 import (
    COST_INDEX,
    SYNTHETIC_LABEL,
    Track4Result,
    compare_with_history,
    cost_index_snapshot,
    export_track4_excel,
    generate_review_narrative,
    historical_input_fingerprint,
    load_synthetic_history,
    policy_evidence_snapshot,
    synthetic_track4_tenderers,
)
from services.config import settings

STEPS = [
    "Project Details",
    "Upload Tender",
    "Check Roles",
    "Comparison Setup",
    "Review Findings",
    "Export",
]

FACILITY_OPTIONS = [
    "Not specified", "Commercial", "Institutional", "Data Centre", "Healthcare", "Industrial", "Other"
]
SERVICE_OPTIONS = [
    "Integrated Facilities Management", "Mechanical & Electrical Maintenance", "Cleaning Services",
    "Security Services", "Building Maintenance", "Other FM Services",
]
MAX_TENDERERS = 5
TRACK4_ROLE_ALIASES = {
    "facility manager": "Facilities Manager",
    "facilities manager (fm)": "Facilities Manager",
    "senior facility manager": "Senior Facilities Manager",
    "senior facilities manager (sfm)": "Senior Facilities Manager",
    "assistant facility manager": "Assistant Facilities Manager",
    "assistant facilities manager": "Assistant Facilities Manager",
    "administrative assistant": "Administrative Assistant",
    "admin assistant": "Administrative Assistant",
    "property executive": "Property Executive",
    "building management system officer (bms officer) / building optimisation system officer (bos officer)": "BMS/BOS Officer",
    "bms officer": "BMS/BOS Officer",
    "technician (mobile)": "Technician",
}


def _initialise():
    defaults = {
        "track4_step": 1,
        "track4_project": {},
        "track4_tenderers": {},
        "track4_history": None,
        "track4_mappings": None,
        "track4_filters": {
            "Facility Type": "Any",
            "Service Category": "Any",
            "Pricing Year From": 2022,
        },
        "track4_result": None,
        "track4_analysis_fingerprint": None,
        "track4_last_analysis": None,
        "track4_policy_evidence": policy_evidence_snapshot(),
        "track4_upload_form_open": True,
        "track4_upload_version": 0,
        "track4_upload_notice": None,
        "track4_roles_confirmed": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    # The comparison database belongs to the assistant; users only upload the
    # tender that they want reviewed.
    if st.session_state.track4_history is None:
        st.session_state.track4_history = load_synthetic_history()


def _frame_json(frame):
    return None if frame is None else frame.to_json(orient="table", index=False)


def _save_bytes():
    result = st.session_state.track4_result
    payload = {
        "version": 1,
        "step": st.session_state.track4_step,
        "project": st.session_state.track4_project,
        "filters": st.session_state.track4_filters,
        "last_analysis": st.session_state.track4_last_analysis,
        "analysis_fingerprint": st.session_state.track4_analysis_fingerprint,
        "history": _frame_json(st.session_state.track4_history),
        "policy_evidence": _frame_json(st.session_state.track4_policy_evidence),
        "mappings": _frame_json(st.session_state.track4_mappings),
        "tenderers": {name: _frame_json(frame) for name, frame in st.session_state.track4_tenderers.items()},
        "result": None
        if result is None
        else {
            name: _frame_json(getattr(result, name))
            for name in (
                "summary",
                "comparisons",
                "findings",
                "questions",
                "overall",
                "adjustments",
                "policy_evidence",
                "narrative",
                "limitations",
            )
        },
    }
    return json.dumps(payload, indent=2).encode()


def _restore(raw: bytes):
    payload = json.loads(raw.decode())

    def read(value):
        return None if value is None else pd.read_json(StringIO(value), orient="table")

    st.session_state.track4_project = payload.get("project", {})
    st.session_state.track4_filters = payload.get("filters", {})
    st.session_state.track4_last_analysis = payload.get("last_analysis")
    st.session_state.track4_analysis_fingerprint = payload.get("analysis_fingerprint")
    st.session_state.track4_history = read(payload.get("history"))
    restored_policy = read(payload.get("policy_evidence"))
    st.session_state.track4_policy_evidence = (
        policy_evidence_snapshot() if restored_policy is None else restored_policy
    )
    st.session_state.track4_mappings = read(payload.get("mappings"))
    st.session_state.track4_tenderers = {
        name: read(value) for name, value in payload.get("tenderers", {}).items()
    }
    saved = payload.get("result")
    st.session_state.track4_result = (
        None if saved is None else Track4Result(**{name: read(value) for name, value in saved.items()})
    )
    st.session_state.track4_step = min(6, max(1, int(payload.get("step", 1))))


def _progress():
    step = st.session_state.track4_step
    st.progress(step / len(STEPS), text=f"Step {step} of {len(STEPS)} · {STEPS[step - 1]}")
    cols = st.columns(len(STEPS))
    for index, label in enumerate(STEPS, 1):
        cols[index - 1].caption(("● " if index == step else "✓ " if index < step else "○ ") + label)


def _is_stale():
    project, tenderers = (
        st.session_state.track4_project,
        st.session_state.track4_tenderers,
    )
    current = historical_input_fingerprint(
        tenderers,
        st.session_state.track4_mappings,
        st.session_state.track4_filters,
        project,
        st.session_state.track4_policy_evidence,
    )
    result = st.session_state.track4_result
    stale = result is not None and current != st.session_state.track4_analysis_fingerprint
    if stale:
        st.warning("Your inputs changed. Recalculate the comparison before exporting.")
    return stale


def _money(value):
    return f"S$ {float(value):,.0f}" if pd.notna(value) else "—"


def _position_label(variance):
    if variance is None or pd.isna(variance):
        return "🔵 Manual review required", "#1769aa"
    value = float(variance)
    if value >= 0.15:
        return "🔴 Much higher than usual", "#c0392b"
    if value >= 0.05:
        return "🟠 Higher than usual", "#d97706"
    if value <= -0.15:
        return "🔴 Much lower than usual", "#c0392b"
    if value <= -0.05:
        return "🟠 Lower than usual", "#d97706"
    return "🟢 Within the acceptable benchmark range", "#16835b"


def _overall_visual(overall):
    selected = st.selectbox(
        "Your submitted proposal",
        list(overall["Tenderer"]),
        help="Choose which uploaded proposal you want to compare with past similar submissions.",
    )
    row = overall[overall["Tenderer"] == selected].iloc[0]
    submitted_total = float(row["Submitted Total Cost (SGD)"])
    raw_comparable_submitted = row.get("Comparable Submitted Cost (SGD)", submitted_total)
    submitted = (
        float(raw_comparable_submitted)
        if pd.notna(raw_comparable_submitted)
        else submitted_total
    )
    coverage = row.get("Comparable Cost Coverage (%)", 1.0)
    raw_norm = row["Adjusted Historical Expected Total (SGD)"]
    raw_low = row["Adjusted Typical Range Low (SGD)"]
    raw_high = row["Adjusted Typical Range High (SGD)"]
    raw_variance = row["Total Variance (%)"]
    has_benchmark = all(pd.notna(value) for value in (raw_norm, raw_low, raw_high, raw_variance))
    if not has_benchmark:
        status, color = _position_label(None)
        st.markdown(
            f"""
<div style="border:1px solid #d7dee8;border-radius:12px;padding:20px 22px;background:#fff;">
  <div style="font-size:1.05rem;font-weight:750;margin-bottom:6px;">Where {selected} stands</div>
  <div style="color:#5d6b7e;margin-bottom:18px;">A reliable overall benchmark could not be calculated from the currently matched historical records.</div>
  <div style="border-left:5px solid {color};background:#eef5fb;padding:14px 16px;border-radius:6px;">
    <div style="font-weight:750;color:{color};margin-bottom:5px;">{status}</div>
    <div>Comparable historical evidence currently covers {float(coverage):.0%} of the submitted cost. Review the role matches and blue manual-review items; the assistant will not invent a whole-tender range.</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(4)
        cols[0].metric("Your submitted price", _money(submitted_total))
        cols[1].metric("Past-submission norm", "Not available")
        cols[2].metric("Difference", "Not measurable")
        cols[3].markdown(
            f"""
<div style="border:1px solid #d7dee8;border-radius:10px;padding:13px 16px;min-height:88px;display:flex;flex-direction:column;justify-content:center;">
  <div style="font-size:.76rem;color:#607086;font-weight:700;margin-bottom:7px;">OVERALL POSITION</div>
  <div style="font-size:1.05rem;font-weight:750;color:{color};line-height:1.25;">{status}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        return selected
    norm = float(raw_norm)
    low = float(raw_low)
    high = float(raw_high)
    variance = float(raw_variance)
    status, color = _position_label(variance)
    axis_low = min(low, submitted) * 0.96
    axis_high = max(high, submitted) * 1.04
    span = max(axis_high - axis_low, 1)

    def position(value):
        return max(2.0, min(98.0, (value - axis_low) / span * 100))

    band_left = position(low)
    band_width = max(position(high) - band_left, 2.0)
    marker_left = position(submitted)
    midpoint_left = position(norm)
    st.markdown(
        f"""
<div style="border:1px solid #d7dee8;border-radius:12px;padding:20px 22px 18px;background:#fff;">
  <div style="font-size:1.05rem;font-weight:750;margin-bottom:6px;">Where {selected} stands</div>
  <div style="color:#5d6b7e;margin-bottom:18px;">One scale showing your tender against comparable past submissions</div>
  <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:.82rem;color:#526277;margin-bottom:34px;">
    <span><span style="display:inline-block;width:24px;height:10px;border-radius:5px;background:#b9e6ce;margin-right:7px;"></span>Acceptable comparison range</span>
    <span><span style="display:inline-block;height:14px;border-left:3px dashed #147D74;margin:0 9px -2px 3px;"></span>Historical midpoint</span>
    <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{color};margin-right:7px;"></span>Your submitted tender</span>
  </div>
  <div style="position:relative;height:94px;margin:0 8px;">
    <div style="position:absolute;left:0;right:0;top:38px;height:8px;border-radius:8px;background:#e8edf3;"></div>
    <div style="position:absolute;left:{band_left:.2f}%;width:{band_width:.2f}%;top:32px;height:20px;border-radius:10px;background:#b9e6ce;"></div>
    <div style="position:absolute;left:{midpoint_left:.2f}%;top:59px;transform:translateX(-50%);color:#147D74;font-size:.78rem;font-weight:750;white-space:nowrap;text-align:center;">MIDPOINT<br>{_money(norm)}</div>
    <div style="position:absolute;left:{midpoint_left:.2f}%;top:27px;height:30px;border-left:3px dashed #147D74;"></div>
    <div style="position:absolute;left:{marker_left:.2f}%;top:1px;transform:translateX(-50%);color:{color};font-size:.78rem;font-weight:800;white-space:nowrap;text-align:center;">YOUR TENDER<br>{_money(submitted)} ({variance:+.1%})</div>
    <div style="position:absolute;left:{marker_left:.2f}%;top:26px;transform:translateX(-50%);width:24px;height:24px;border-radius:50%;background:{color};border:4px solid white;box-shadow:0 0 0 2px {color};"></div>
  </div>
  <div style="display:flex;justify-content:space-between;gap:18px;margin-top:0;flex-wrap:wrap;">
    <div><div style="font-size:.78rem;color:#607086;font-weight:700;">RANGE START</div><div style="font-weight:750;">{_money(low)}</div></div>
    <div style="text-align:right;"><div style="font-size:.78rem;color:#607086;font-weight:700;">RANGE END</div><div style="font-weight:750;">{_money(high)}</div></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    if low <= submitted <= high:
        st.success(
            f"At a glance: your tender is inside the acceptable comparison range "
            f"({_money(low)} to {_money(high)})."
        )
    else:
        direction = "above" if submitted > high else "below"
        st.warning(
            f"At a glance: your tender is {direction} the acceptable comparison range "
            f"({_money(low)} to {_money(high)})."
        )
    cols = st.columns(4)
    cols[0].metric("Comparable submitted price", _money(submitted))
    cols[1].metric("Past-submission norm", _money(norm))
    cols[2].metric("Difference", _money(submitted - norm), f"{variance:+.1%}")
    cols[3].markdown(
        f"""
<div style="border:1px solid #d7dee8;border-radius:10px;padding:13px 16px;min-height:88px;display:flex;flex-direction:column;justify-content:center;">
  <div style="font-size:.76rem;color:#607086;font-weight:700;margin-bottom:7px;">OVERALL POSITION</div>
  <div style="font-size:1.05rem;font-weight:750;color:{color};line-height:1.25;">{status}</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    return selected


def _render_overall_assessment(result, tenderer):
    overall = result.overall[result.overall["Tenderer"] == tenderer].iloc[0]
    raw_variance = overall["Total Variance (%)"]
    variance = float(raw_variance) if pd.notna(raw_variance) else None
    status, _ = _position_label(variance)
    findings = result.findings[result.findings["Tenderer"] == tenderer]
    attention = findings[findings["Priority"].isin(["High", "Medium", "Manual review"])]
    roles = ", ".join(attention["Standard Role"].drop_duplicates().head(3)) or "No material role outliers"
    st.markdown("#### Overall assessment")
    narrative = result.narrative.iloc[0]
    if narrative["Status"] == "AI-assisted interpretation":
        st.markdown(narrative["Narrative"])
        with st.expander("Evidence used by the AI assessment"):
            st.write(narrative["Evidence Basis"])
    else:
        if variance is None:
            st.markdown(
                f"""
- **Position:** {status}; an overall percentage cannot be calculated from the available comparable records.
- **Assessment:** The assistant has kept the result in manual review instead of creating an unsupported benchmark.
- **Roles needing attention:** {roles}.
- **What to clarify:** Confirm the role matches, pricing unit, scope, staffing and whether more comparable historical records are available.
                """
            )
        else:
            st.markdown(
                f"""
- **Position:** {status}; the submitted total is **{variance:+.1%}** against the comparable norm.
- **Assessment:** The submitted price is compared with the acceptable benchmark range after historical wage adjustment.
- **Roles needing attention:** {roles}.
- **What to clarify:** Confirm scope, staffing, relief coverage, statutory contributions and policy-related allowances.
                """
            )


def _priority_style(frame):
    colors = {
        "High": "background-color:#FDE8E8;color:#8A1C1C;font-weight:700",
        "Medium": "background-color:#FFF1D6;color:#7A4A00;font-weight:700",
        "Low": "background-color:#E7F6EC;color:#176B3A;font-weight:700",
        "Manual review": "background-color:#EAF2F8;color:#173B63;font-weight:700",
    }
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    if "Priority" in frame:
        for index, value in frame["Priority"].items():
            styles.loc[index, "Priority"] = colors.get(value, "")
    formats = {
        column: ("{:+.1%}" if "(%)" in column else "S$ {:+,.2f}" if "Difference" in column else "S$ {:,.2f}")
        for column in frame.columns
        if "(SGD)" in column or "(%)" in column
    }
    return frame.style.format(formats, na_rep="—").apply(lambda _: styles, axis=None)


def render_agent2_track4():
    _initialise()
    st.caption("FM MANPOWER COST ASSISTANT · AGENT 2 · TRACK 4")
    top, exit_col = st.columns([5, 1])
    top.title("Review and compare tenderer proposals")
    if exit_col.button("Change track", width="stretch", key="track4_change"):
        st.session_state.selected_track = None
        st.rerun()
    st.write(
        "Upload a tender proposal to see whether its pricing is in line with comparable past submissions, what needs attention and what to clarify."
    )
    _progress()
    if st.session_state.track4_step > 1:
        previous = STEPS[st.session_state.track4_step - 2]
        if st.button(f"← Back to {previous}", key=f"track4_global_back_{st.session_state.track4_step}"):
            st.session_state.track4_step -= 1
            st.rerun()
    stale = _is_stale()
    if st.session_state.track4_project:
        name = st.session_state.track4_project.get("name", "historical-review").replace(" ", "_")
        st.download_button(
            "Download project file to continue later",
            _save_bytes(),
            f"{name}_Track4_Project.json",
            "application/json",
            help="Downloads the project, comparison records, role matches, findings and reviewer notes. Nothing is saved to a server.",
        )
        st.caption(
            "Store this JSON file securely. Upload it under Project Details to resume later; nothing is saved to a server."
        )

    step = st.session_state.track4_step
    if step == 1:
        st.header("Create or resume a tender review")
        st.write("Tell us about the tender so we can compare it with the most relevant past submissions.")
        saved = st.file_uploader("Resume a saved Track 4 project", type=["json"], key="track4_resume")
        if saved and st.button("Resume saved project"):
            try:
                _restore(saved.getvalue())
                st.success("Project restored.")
                st.rerun()
            except Exception:
                st.error("This is not a valid saved Track 4 project file.")
        with st.form("track4_project_form"):
            name = st.text_input("Project name *", value=st.session_state.track4_project.get("name", ""))
            reference = st.text_input(
                "Tender reference", value=st.session_state.track4_project.get("reference", "")
            )
            c1, c2 = st.columns(2)
            agency = st.text_input(
                "Procuring agency", value=st.session_state.track4_project.get("agency", "")
            )
            c_dates = st.columns(2)
            closing = c_dates[0].date_input("Tender submission date")
            start = c_dates[1].date_input("Contract start date")
            c_period = st.columns(2)
            base_years = c_period[0].number_input("Base contract period (years)", 1, 20, 3)
            option_years = c_period[1].number_input(
                "Option period (years, if any)", 0, 20, 3,
                help="Enter 0 if the contract has no optional extension period.",
            )
            facility = c1.selectbox("Building / facility type", FACILITY_OPTIONS)
            service = c2.selectbox(
                "FM service category", SERVICE_OPTIONS,
            )
            scope_notes = st.text_area(
                "Important differences from a standard contract (optional)",
                key="track4_scope_notes",
                placeholder="e.g. 24/7 shifts, specialist certification, extra relief coverage or expanded duties",
                help="Share unusual staffing or service requirements that could reasonably explain a higher or lower price.",
            )
            if st.form_submit_button("Save project and continue", type="primary"):
                if not name.strip():
                    st.error("Enter a project name.")
                else:
                    st.session_state.track4_project = {
                        "name": name.strip(),
                        "reference": reference.strip(),
                        "agency": agency.strip(),
                        "submission_date": closing.isoformat(),
                        "contract_start": start.isoformat(),
                        "pricing_year": start.year,
                        "contract_duration_months": int((base_years + option_years) * 12),
                        "base_years": int(base_years),
                        "option_years": int(option_years),
                        "facility_type": facility,
                        "service_category": service,
                        "scope_notes": scope_notes.strip(),
                    }
                    st.session_state.track4_step = 2
                    st.rerun()
    elif step == 2:
        st.header("Upload tenderer submissions")
        st.write(
            "Upload each tenderer separately. After a submission is added, the form clears so you "
            "can add the next tenderer for side-by-side comparison."
        )
        tenderer_count = len(st.session_state.track4_tenderers)
        limit_reached = tenderer_count >= MAX_TENDERERS
        st.caption(f"{tenderer_count} of {MAX_TENDERERS} tenderer submissions added")
        version = st.session_state.track4_upload_version
        name = st.text_input(
            "Tenderer name",
            placeholder=f"e.g. Tenderer {chr(65 + tenderer_count)}",
            key=f"track4_tenderer_name_{version}",
            disabled=limit_reached,
        )
        files = st.file_uploader(
            "Upload one verified manpower schedule",
            type=["csv", "xlsx", "xls", "json"],
            accept_multiple_files=True,
            key=f"track4_tenderer_files_{version}",
            disabled=limit_reached,
            help=(
                "Supports flat role tables and multi-tab composition-of-rates workbooks. "
                "The assistant reads the contract year from each worksheet name/title and "
                "combines repeated site rate/quantity blocks by role."
            ),
        )
        if st.button(
            "Upload and add this tenderer",
            disabled=limit_reached,
            help="Add this submission, then clear the form for the next tenderer.",
        ):
            if not name.strip() or not files:
                st.error("Enter a tenderer name and select at least one completed schedule.")
            elif name.strip() in st.session_state.track4_tenderers:
                st.error(
                    "That tenderer name has already been added. Use a different name, or remove "
                    "the existing submission before replacing it."
                )
            else:
                try:
                    extracted = pd.concat(
                        [parse_upload(file.name, file.getvalue()) for file in files],
                        ignore_index=True,
                    )
                    st.session_state.track4_tenderers[name.strip()] = extracted
                    st.session_state.track4_result = None
                    st.session_state.track4_roles_confirmed = False
                    issue_count = len(validation_issues(extracted))
                    st.session_state.track4_upload_notice = (
                        f"{name.strip()} added with {issue_count} validation issue(s). "
                        "Review the extracted data before comparison."
                        if issue_count
                        else f"{name.strip()} submission accepted with no input validation issues."
                    )
                    st.session_state.track4_upload_version += 1
                    st.rerun()
                except Track3InputError as exc:
                    st.error(str(exc))
        if st.session_state.track4_upload_notice:
            st.success(st.session_state.track4_upload_notice)
        if st.session_state.track4_tenderers:
            st.markdown("#### Uploaded tenderers")
            remove_name = None
            for tenderer_name, frame in st.session_state.track4_tenderers.items():
                years = ", ".join(
                    str(value) for value in sorted(frame["Contract Year"].dropna().unique())
                )
                with st.container(border=True):
                    details, remove = st.columns([4, 1])
                    issue_count = len(validation_issues(frame))
                    if issue_count:
                        details.error(
                            f"{tenderer_name}: Needs correction — {issue_count} validation issue(s)."
                        )
                    else:
                        details.success(f"{tenderer_name}: Ready for verification.")
                    details.caption(
                        f"{len(frame)} extracted role-year rows · Contract year(s): {years}"
                    )
                    if remove.button(
                        "Remove",
                        key=f"track4_remove_tenderer_{tenderer_name}",
                        width="stretch",
                    ):
                        remove_name = tenderer_name
            if remove_name is not None:
                st.session_state.track4_tenderers.pop(remove_name, None)
                st.session_state.track4_mappings = None
                st.session_state.track4_roles_confirmed = False
                st.session_state.track4_result = None
                st.session_state.track4_analysis_fingerprint = None
                st.session_state.track4_upload_version += 1
                st.rerun()
            if tenderer_count < MAX_TENDERERS:
                st.info(
                    "Use the cleared form above to upload the next tenderer. "
                    "You can compare up to five submissions."
                )
            else:
                st.info("Five tenderers have been added. Remove one to upload a replacement.")
        with st.expander("Need an example to explore the feature?"):
            st.caption("This loads a clearly labelled demonstration tender. It does not replace or upload the comparison database.")
            if st.button("Use example tender"):
                st.session_state.track4_tenderers = synthetic_track4_tenderers(
                    include_comparison_vendors=True
                )
                st.session_state.track4_mappings = None
                st.session_state.track4_result = None
                st.session_state.track4_analysis_fingerprint = None
                st.rerun()
        if st.button(
            "Continue: verify all submissions and match roles",
            type="primary",
            disabled=not st.session_state.track4_tenderers or st.session_state.track4_history is None,
        ):
            st.session_state.track4_step = 3
            st.rerun()
    elif step == 3:
        st.header("Validation results and extracted tender data")
        st.write(
            "Review every uploaded value before comparison. Missing or contradictory values are never guessed or treated as zero."
        )
        issue_frames = []
        for document_name, document_frame in st.session_state.track4_tenderers.items():
            document_issues = validation_issues(document_frame)
            if not document_issues.empty:
                document_issues.insert(0, "Document", document_name)
                issue_frames.append(document_issues)
        if issue_frames:
            all_issues = pd.concat(issue_frames, ignore_index=True)
            st.error(f"Comparison stopped: resolve {len(all_issues)} input issue(s) below.")
            st.dataframe(all_issues, hide_index=True, width="stretch")
        else:
            st.success("All tenderer submissions passed input validation.")
        valid = True
        for name, frame in st.session_state.track4_tenderers.items():
            st.subheader(name)
            edited = st.data_editor(frame, hide_index=True, width="stretch", key=f"track4_editor_{name}")
            st.session_state.track4_tenderers[name] = edited
            issues = validation_issues(edited)
            valid = valid and issues.empty
            if not issues.empty:
                st.error(f"Resolve {len(issues)} missing or invalid value(s).")
                st.dataframe(issues, hide_index=True)
        history_roles = sorted(
            st.session_state.track4_history["Standard Role"].dropna().astype(str).unique()
        )
        mapping = role_mapping_table(
            st.session_state.track4_tenderers,
            standard_roles=history_roles,
            aliases=TRACK4_ROLE_ALIASES,
        )
        previous = st.session_state.track4_mappings
        if previous is not None and not previous.empty:
            saved = previous.set_index(["Submitted by", "Role title in submission"])["Compare as"]
            mapping["Compare as"] = mapping.apply(
                lambda row: saved.get(
                    (row["Submitted by"], row["Role title in submission"]), row["Compare as"]
                ),
                axis=1,
            )
        st.subheader("Check how each role will be compared")
        st.info(
            "A role is matched only when its title or an approved synonym exists in the comparison "
            "database. If no equivalent is found, check the duties before selecting a database role. "
            "Leaving the submitted title unchanged keeps it in manual review instead of forcing a "
            "misleading comparison."
        )
        mapping = st.data_editor(
            mapping,
            hide_index=True,
            width="stretch",
            column_config={
                "Compare as": st.column_config.SelectboxColumn(
                    "Role used for comparison",
                    options=role_mapping_options(mapping, history_roles),
                    required=True,
                )
            },
            disabled=["Submitted by", "Role title in submission", "Why this is suggested"],
        )
        st.session_state.track4_mappings = mapping
        roles_confirmed = st.checkbox(
            "I have checked the role matches and confirm they can be used for this comparison.",
            value=st.session_state.track4_roles_confirmed,
            disabled=not valid,
        )
        st.session_state.track4_roles_confirmed = roles_confirmed
        can_continue = valid and roles_confirmed
        continue_help = None
        if not can_continue:
            continue_help = (
                "Unable to proceed: resolve the validation errors above."
                if not valid
                else "Unable to proceed: confirm the role matches above."
            )
            st.info(continue_help)
        if st.button(
            "Confirm data and choose comparison settings",
            type="primary",
            disabled=not can_continue,
            help=continue_help,
        ):
            st.session_state.track4_step = 4
            st.rerun()
    elif step == 4:
        st.header("Choose which past submissions to compare")
        st.info(
            "The assistant first matches the role and pricing unit, then looks for past submissions with similar contract context. If too few matches are available, it clearly flags that the result needs manual review."
        )
        history = st.session_state.track4_history
        available_years = sorted(history["Pricing Year"].dropna().astype(int).unique())
        min_year, max_year = min(available_years), max(available_years)
        available_roles = sorted(history["Standard Role"].dropna().astype(str).unique())
        st.success(
            f"Comparison database coverage: {len(history)} reference records · "
            f"{len(available_roles)} standard roles · pricing years {min_year}–{max_year}."
        )
        with st.expander("See available comparison roles and years"):
            role_counts = (
                history.groupby("Standard Role", as_index=False)
                .agg(
                    Records=("Record ID", "count"),
                    Earliest_year=("Pricing Year", "min"),
                    Latest_year=("Pricing Year", "max"),
                )
                .rename(
                    columns={
                        "Standard Role": "Comparison role",
                        "Earliest_year": "Earliest year",
                        "Latest_year": "Latest year",
                    }
                )
            )
            st.dataframe(role_counts, hide_index=True, width="stretch")
            st.caption(
                "Prototype reference data; confirm source governance before operational use."
            )
        project, old = st.session_state.track4_project, st.session_state.track4_filters
        c1, c2, c3 = st.columns(3)
        facility_options = ["Any"] + FACILITY_OPTIONS[1:]
        facility = c1.selectbox(
            "Building / facility type", facility_options,
            index=facility_options.index(old.get("Facility Type", project.get("facility_type", "Any")))
            if old.get("Facility Type", project.get("facility_type", "Any")) in facility_options else 0,
        )
        service_options = ["Any"] + SERVICE_OPTIONS
        service = c2.selectbox(
            "FM service category",
            service_options,
            index=service_options.index(old.get("Service Category", project.get("service_category", "Any")))
            if old.get("Service Category", project.get("service_category", "Any")) in service_options else 0,
        )
        selected_year = int(old.get("Pricing Year From", min_year))
        selected_year = min(max(selected_year, min_year), max_year)
        year_from = c3.number_input(
            "Use submissions from",
            min_year,
            max_year,
            selected_year,
            help=(
                f"Choose {min_year} for the broadest evidence base. A later year uses fewer records "
                "and may increase manual-review results."
            ),
        )
        filters = {
            "Facility Type": facility,
            "Service Category": service,
            "Pricing Year From": int(year_from),
        }
        st.session_state.track4_filters = filters
        st.caption(
            f"Recommended starting point: {min_year}, with Building / facility type and FM service "
            "category set to Any. Narrow the filters only when the contract context genuinely requires it."
        )
        if st.button("Compare tender pricing", type="primary"):
            mapping_dict = {
                (row["Submitted by"], row["Role title in submission"]): row["Compare as"]
                for _, row in st.session_state.track4_mappings.iterrows()
            }
            try:
                st.session_state.track4_result = compare_with_history(
                    st.session_state.track4_tenderers,
                    st.session_state.track4_history,
                    facility_type=facility,
                    service_category=service,
                    gfa_band="Any",
                    pricing_year_from=int(year_from),
                    role_mappings=mapping_dict,
                    project=st.session_state.track4_project,
                    target_pricing_year=st.session_state.track4_project.get("pricing_year"),
                    policy_evidence=st.session_state.track4_policy_evidence,
                )
                configured = settings()
                if configured.api_key and configured.model:
                    st.session_state.track4_result.narrative = generate_review_narrative(
                        st.session_state.track4_result,
                        create_client(configured.api_key),
                        configured.model,
                    )
                st.session_state.track4_analysis_fingerprint = historical_input_fingerprint(
                    st.session_state.track4_tenderers,
                    st.session_state.track4_mappings,
                    filters,
                    st.session_state.track4_project,
                    st.session_state.track4_policy_evidence,
                )
                st.session_state.track4_last_analysis = (
                    datetime.now().astimezone().strftime("%d %b %Y, %H:%M")
                )
                st.session_state.track4_step = 5
                st.rerun()
            except Track3InputError as exc:
                st.error(str(exc))
    elif step == 5:
        result = st.session_state.track4_result
        if result is None:
            st.session_state.track4_step = 4
            st.rerun()
        st.header("Your tender pricing review")
        st.warning(SYNTHETIC_LABEL)
        st.write("Start with the overall position, then work through only the items that need attention.")
        overall_tab, attention_tab, roles_tab, policy_tab, questions_tab, evidence_tab = st.tabs(
            [
                "Overview",
                "Needs attention",
                "Role & cost summary",
                "Policy checks",
                "Clarification questions",
                "How it works",
            ]
        )
        with overall_tab:
            st.subheader("Is the total price in line with comparable submissions?")
            selected_tenderer = _overall_visual(result.overall)
            with st.container(border=True):
                _render_overall_assessment(result, selected_tenderer)
            # settings() reads environment variables and safely defaults when no
            # Streamlit secrets file exists; the deterministic review stays usable.
            configured = settings()
            if configured.api_key and configured.model:
                st.success(f"OpenAI is configured for AI-assisted assessment using {configured.model}.")
                if st.button("Regenerate AI assessment"):
                    with st.spinner("Explaining the verified calculations and cited policy evidence…"):
                        result.narrative = generate_review_narrative(
                            result, create_client(configured.api_key), configured.model
                        )
                    st.rerun()
            elif configured.api_key:
                st.warning(
                    "The OpenAI API key was detected, but no model has been configured. Add an "
                    "OPENAI_MODEL value to the private .env file, then restart the app. The "
                    "verified calculations remain available without AI."
                )
            elif configured.model:
                st.warning(
                    "An OpenAI model is configured, but the API key is missing. Add the key to the "
                    "private .env file and restart the app."
                )
            else:
                st.caption(
                    "OpenAI is not configured. Add both OPENAI_API_KEY and OPENAI_MODEL to the "
                    "private .env file, then restart the app."
                )
        with attention_tab:
            st.subheader("Items to review")
            st.caption("Choose a priority to see only those items, then record the review decision and notes.")
            if result.findings.empty:
                st.success("No items require clarification under the current rules.")
            else:
                priority_meta = {
                    "High": ("🔴", "Check before proceeding"),
                    "Medium": ("🟠", "Seek clarification"),
                    "Low": ("🟢", "Note and monitor"),
                    "Manual review": ("🔵", "Evidence is limited"),
                }
                st.session_state.setdefault("track4_priority_filter", "High")
                priority_columns = st.columns(4)
                for column, (priority, (icon, description)) in zip(
                    priority_columns, priority_meta.items(), strict=True
                ):
                    count = int((result.findings["Priority"] == priority).sum())
                    if column.button(
                        f"{icon} {priority}\n{count} item{'s' if count != 1 else ''} · {description}",
                        key=f"track4_filter_{priority}",
                        type="primary" if st.session_state.track4_priority_filter == priority else "secondary",
                        width="stretch",
                    ):
                        st.session_state.track4_priority_filter = priority
                        st.rerun()
                selected_priority = st.session_state.track4_priority_filter
                selected_icon = priority_meta[selected_priority][0]
                filtered = result.findings[result.findings["Priority"] == selected_priority]
                st.markdown(f"#### {selected_icon} {selected_priority} priority items")
                if filtered.empty:
                    st.success(f"There are no {selected_priority.lower()} priority items.")
                for index, item in filtered.iterrows():
                    variance = item["Variance to Adjusted Benchmark (%)"]
                    _, variance_color = _position_label(variance)
                    with st.container(border=True):
                        heading, amount = st.columns([4, 1])
                        heading.markdown(
                            f"**{item['Tenderer']} · {item['Standard Role']}**  \n"
                            f"{item['Finding Category']}"
                        )
                        amount.markdown(
                            f"<div style='text-align:right;font-size:1.2rem;font-weight:800;color:{variance_color}'>{variance:+.1%}</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Why it matters**  \n{item['What the Comparison Means']}")
                        st.markdown(
                            f"**What to check with the tenderer**  \n{item['Suggested Clarification Question']}"
                        )
                        decision, notes = st.columns([1, 2])
                        statuses = ["Pending Review", "Reviewed", "Resolved"]
                        current_status = item["Review Status"]
                        status_index = statuses.index(current_status) if current_status in statuses else 0
                        result.findings.at[index, "Review Status"] = decision.selectbox(
                            "Review status",
                            statuses,
                            index=status_index,
                            key=f"track4_status_{index}",
                        )
                        result.findings.at[index, "Officer Notes"] = notes.text_input(
                            "Officer notes",
                            value=str(item["Officer Notes"] or ""),
                            key=f"track4_notes_{index}",
                            placeholder="Record the response or follow-up needed",
                        )
        with roles_tab:
            st.subheader("Role-by-role pricing at a glance")
            st.caption("The norm is the middle price from comparable past submissions, restated to the tender year.")
            tenderer = st.selectbox(
                "Submitted proposal", list(result.overall["Tenderer"]), key="track4_role_tenderer"
            )
            available_roles = list(
                result.comparisons[result.comparisons["Tenderer"] == tenderer]["Standard Role"].drop_duplicates()
            )
            selected_role = st.selectbox("Role to review", available_roles, key="track4_role_selector")
            roles = result.comparisons[
                (result.comparisons["Tenderer"] == tenderer)
                & (result.comparisons["Standard Role"] == selected_role)
            ][[
                "Standard Role", "Tendered Monthly Rate (SGD)", "Adjusted Historical Benchmark (SGD)",
                "Variance to Adjusted Benchmark (%)", "Historical Position", "Priority", "Comparable Past Records",
                "Applicable Statutory Wage Floor (SGD)", "Statutory Wage Check",
            ]].copy()
            roles = roles.rename(columns={
                "Standard Role": "Role", "Tendered Monthly Rate (SGD)": "Tendered monthly rate",
                "Adjusted Historical Benchmark (SGD)": "Comparable tender norm",
                "Variance to Adjusted Benchmark (%)": "Difference from norm",
                "Historical Position": "Position", "Comparable Past Records": "Past submissions compared",
                "Applicable Statutory Wage Floor (SGD)": "Statutory wage-floor reference",
                "Statutory Wage Check": "Statutory check",
            })
            role = roles.iloc[0]
            role_status, role_color = _position_label(role["Difference from norm"])
            metrics = st.columns(4)
            metrics[0].metric("Tendered monthly rate", _money(role["Tendered monthly rate"]))
            metrics[1].metric("Comparable role norm", _money(role["Comparable tender norm"]))
            metrics[2].markdown(
                f"""
<div style="font-size:.88rem;color:#435166;margin-bottom:6px;">Difference</div>
<div style="display:inline-block;padding:7px 12px;border-radius:9px;background:{role_color}18;color:{role_color};font-size:1.7rem;font-weight:800;line-height:1.1;">
  {role['Difference from norm']:+.1%}
</div>
                """,
                unsafe_allow_html=True,
            )
            metrics[3].metric("Past records compared", int(role["Past submissions compared"]))
            with st.container(border=True):
                st.markdown(f"<div style='font-size:1.25rem;font-weight:750;color:{role_color}'>{role_status}</div>", unsafe_allow_html=True)
                st.write(role["Position"])
                if pd.notna(role["Statutory wage-floor reference"]):
                    st.warning(
                        f"PWM reference: {_money(role['Statutory wage-floor reference'])} monthly basic wage. "
                        f"{role['Statutory check']}"
                    )
                narrative = result.narrative.iloc[0]
                if narrative["Status"] == "AI-assisted interpretation":
                    st.markdown("**AI assessment of the likely cost drivers**")
                    st.markdown(narrative["Narrative"])
                else:
                    st.caption(
                        "Connect OpenAI to analyse whether this difference is mainly associated with the role rate, staffing quantity, contract scope or policy costs."
                    )
        with policy_tab:
            st.subheader("External cost factors to verify")
            st.info(
                "Policy and wage changes can legitimately raise prices. These checks identify what may apply; they do not prove that the tenderer included the cost. Ask the tenderer to confirm."
            )
            policy_columns = st.columns(3)
            for index, (_, item) in enumerate(result.policy_evidence.iterrows()):
                with policy_columns[index % 3].container(border=True):
                    st.caption(item["Source Organisation"].upper())
                    st.markdown(f"### {item['Policy or Economic Factor']}")
                    st.write(item["What Changed"])
                    st.markdown(f"**Who may be affected**  \n{item['Roles or Sectors Affected']}")
                    st.markdown(f"**What to verify**  \n{item['Likely Cost Implication']}")
                    st.link_button("Open official source ↗", item["Direct URL"], width="stretch")
                    st.caption(f"Source checked: {item['Date Accessed']}")
        with questions_tab:
            st.subheader("Clarification questions for tenderers")
            st.caption("Aligned with Track 3: review the suggested questions and choose which ones to include in the report.")
            edited_rows = []
            for index, row in result.questions.iterrows():
                with st.container(border=True):
                    left, right = st.columns([5, 1])
                    left.markdown(f"**{row['Tenderer']} · {row['Related Role']}**")
                    include = right.checkbox(
                        "Include", value=bool(row["Include in Report"]), key=f"track4_question_{index}"
                    )
                    st.write(row["Clarification Question"])
                    with st.expander("Why this question is suggested"):
                        st.write(row["Reason for Question"])
                    updated = row.copy()
                    updated["Include in Report"] = include
                    edited_rows.append(updated)
            if edited_rows:
                result.questions = pd.DataFrame(edited_rows).reset_index(drop=True)
        with evidence_tab:
            st.subheader("How the comparison is calculated")
            st.write("Five transparent steps turn past submission records into an officer-ready review.")
            steps = [
                ("1", "Match the role", "Standardise the submitted role and pricing unit so like is compared with like."),
                ("2", "Select comparable records", "Use similar service, facility and submission years chosen in Comparison Setup."),
                ("3", "Restate older prices", "Chain MOM Administrative & Support Services wage changes to convert earlier prices into tender-year equivalents."),
                ("4", "Find the norm", "Use the middle comparable price as the norm and the middle 50% as the usual range."),
                ("5", "Flag action", "Translate material differences or limited evidence into a priority and clarification question."),
            ]
            for row_start in (0, 3):
                columns = st.columns(3)
                for column, (number, title, description) in zip(columns, steps[row_start:row_start + 3], strict=False):
                    with column.container(border=True):
                        st.markdown(f"<div style='font-size:2rem;font-weight:800;color:#147D74'>{number}</div>", unsafe_allow_html=True)
                        st.markdown(f"**{title}**")
                        st.write(description)
            example_adjusted = 5000 * COST_INDEX[2026] / COST_INDEX[2022]
            st.info(
                f"Example: a 2022 monthly rate of SGD 5,000 becomes SGD {example_adjusted:,.0f} in 2026 because "
                f"5,000 × ({COST_INDEX[2026]:.4f} ÷ {COST_INDEX[2022]:.4f}) = {example_adjusted:,.0f}. "
                "The 2023–2025 steps use published MOM wage changes. The 2026 step is visibly marked as a scenario pending an approved full-year value."
            )
            st.warning(
                "We do not add a blanket policy surcharge. Instead, we check that any applicable PWM minimum wage is met. We also avoid counting employer CPF twice because it is already included in MOM's wage-change figures."
            )
            with st.expander("See the governed wage-index series", expanded=True):
                st.dataframe(
                    cost_index_snapshot(), hide_index=True, width="stretch",
                    column_config={
                        "Annual Change": st.column_config.NumberColumn(format="%.1f%%"),
                        "Cumulative Index (2022=1.000)": st.column_config.NumberColumn(format="%.4f"),
                        "Source": st.column_config.LinkColumn(display_text="Open MOM source ↗"),
                    },
                )
            with st.expander("See year-by-year cost assumptions"):
                st.dataframe(result.adjustments, hide_index=True, width="stretch")
            with st.expander("See limitations and safeguards"):
                st.dataframe(result.limitations, hide_index=True, width="stretch")
        st.session_state.track4_result = result
        back, _, export = st.columns([1.4, 3, 1])
        if back.button("← Revise comparison setup", width="stretch"):
            st.session_state.track4_step = 4
            st.rerun()
        if export.button("Prepare export", type="primary", disabled=stale, width="stretch"):
            st.session_state.track4_step = 6
            st.rerun()
    else:
        result = st.session_state.track4_result
        st.header("Export tender pricing review")
        if stale:
            st.error("Recalculate the comparison before exporting.")
        else:
            report = export_track4_excel(
                st.session_state.track4_project,
                result,
                st.session_state.track4_history,
                st.session_state.track4_mappings,
                st.session_state.track4_filters,
            )
            st.download_button(
                "Download tender pricing review",
                report,
                "Track4_Tender_Pricing_Review.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
            st.info(
                "The report includes filters, role matches, source record IDs, findings, clarification questions and limitations. It does not recommend an award."
            )
