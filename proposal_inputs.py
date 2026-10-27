"""Track 2: add a proposal, check it, then view the reviewed budget."""

import hashlib
import json

import pandas as pd
import streamlit as st

from activity_nav import retained_key
from services.models import Coverage
from services.proposals import (
    COLUMNS,
    Proposal,
    ProposalStore,
    apply_yearly,
    assessment,
    capture_original,
    comparison,
    confirm_review,
    extract_document,
    interpret_text,
    rate_comparisons,
    restore_copy,
    update_reviewed,
)
from services.storage import ConflictError
from services.workflow import apply_change, confirm, record_decision

PROPOSAL_UI_VERSION = 2


def digest(p):
    return hashlib.sha256(p.model_dump_json().encode()).hexdigest()


def remember_controls(p):
    """Persist unfinished answers, excluding buttons and uploaded-file handles."""
    starts = (
        "proposal_context_",
        "proposal_revised_context_",
        "proposal_text_",
        "proposal_shared_roles_",
        "proposal_shared_percent_",
        "proposal_shared_note_",
        "proposal_shared_year_note_",
        "proposal_use_ref_",
        "proposal_future_row_",
        "proposal_future_method_",
        "proposal_yearly_source_",
        "proposal_pwm_",
        "proposal_question_",
        "proposal_operational_note_",
        "proposal_reason_",
        "proposal_decision_",
        "proposal_rate_",
        "t2_cov_",
    )
    saved = p.drafts.setdefault("controls", {})
    for key in st.session_state:
        if (
            key.startswith(starts)
            and not key.startswith(("t2_cov_keep_", "t2_cov_use_"))
            and not key.endswith(("_apply", "_record", "_revert"))
            and any(token in key for token in [p.id, *(r.id for r in p.plan.roles)])
        ):
            value = st.session_state[key]
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                continue
            saved[key] = value


def role_label(p, rid):
    role = next(r for r in p.plan.roles if r.id == rid)
    duplicates = [r for r in p.plan.roles if r.label == role.label]
    return role.label + (f" (row {duplicates.index(role) + 1})" if len(duplicates) > 1 else "")


def _set_stage(stage):
    st.session_state.proposal.stage = stage
    st.rerun()


def pwm_draft(prefix, rid):
    from future_inputs import PWM_FIELDS

    p = st.session_state.proposal
    p.plan.basis_drafts.setdefault("pwm_" + rid, {}).update(
        {
            field: st.session_state[prefix + "_" + field]
            for field in PWM_FIELDS
            if prefix + "_" + field in st.session_state
        }
    )


def profile_editor(p, current, key):
    seed = p.drafts.get(key, current.model_dump(mode="json"))
    name = st.text_input(
        "Proposal / project title", value=seed.get("name", ""), key=retained_key(key + "_name")
    )
    brief = st.text_area(
        "What must this team support?",
        value=seed.get("description", ""),
        key=retained_key(key + "_brief"),
        placeholder="Property, operating hours, critical functions and any existing specialist support. Unknown details can remain unknown.",
    )
    a, b, c = st.columns(3)
    year = a.number_input(
        "Start year",
        value=seed.get("start_year"),
        min_value=1900,
        max_value=2200,
        step=1,
        key=retained_key(key + "_year"),
    )
    base = b.number_input(
        "Base years",
        value=seed.get("base_years"),
        min_value=1,
        max_value=20,
        step=1,
        key=retained_key(key + "_base"),
    )
    option = c.number_input(
        "Option years (0 if none)",
        value=seed.get("option_years"),
        min_value=0,
        max_value=20,
        step=1,
        key=retained_key(key + "_option"),
    )
    with st.expander("Exact start date or exclusions, when relevant"):
        exact = st.text_input(
            "Exact contract start (YYYY-MM-DD, only if known)",
            value=seed.get("start") or "",
            key=retained_key(key + "_start"),
        )
        exclusions = st.text_area(
            "Excluded costs / separately procured support",
            value=seed.get("exclusions", ""),
            key=retained_key(key + "_exclusions"),
        )
    values = {
        **current.model_dump(mode="json"),
        "name": name,
        "description": brief,
        "start_year": year,
        "base_years": base,
        "option_years": option,
        "start": exact or None,
        "exclusions": exclusions,
    }
    p.drafts[key] = values
    return values


def editable_rows(rows, key):
    from services.evidence import ROLES

    data = pd.DataFrame(
        [{**{c: r.get(c) for c in COLUMNS}, "id": r.get("id")} for r in rows], columns=["id", *COLUMNS]
    )
    for col in (
        "Quantity",
        "Monthly rate",
        "Annual increase (%)",
        "Supplied monthly total",
        "Supplied annual total",
        "Supplied contract total",
    ):
        data[col] = pd.to_numeric(data[col], errors="coerce").astype("Float64")
    edited = st.data_editor(
        data,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=key,
        column_config={
            "id": None,
            "Role": st.column_config.TextColumn(width="medium"),
            "Unit": st.column_config.SelectboxColumn(options=["unspecified", "headcount", "FTE", "posts"]),
            "Mapping": st.column_config.SelectboxColumn(options=["", *ROLES]),
            **{
                c: st.column_config.NumberColumn(format="%.2f")
                for c in ("Quantity", "Monthly rate", "Annual increase (%)")
            },
        },
    )
    clean = edited.astype(object).where(pd.notna(edited), None).to_dict("records")
    old = {str(r.get("id")): r for r in rows}
    return [{**old.get(str(r.get("id")), {}), **r} for r in clean if str(r.get("Role") or "").strip()]


def capture_page(p, save):
    st.header("1. Add proposed budget")
    st.caption("A document is optional. Supply what is known; missing inputs remain blank.")
    values = profile_editor(p, p.plan.profile, "proposal_context_" + p.id)
    p.name = values["name"].strip() or "Untitled proposal review"
    p.input_profile = values
    text = st.text_area(
        "Paste a table or describe the proposal",
        value=p.input_text,
        key=retained_key("proposal_text_" + p.id),
        placeholder="Role,Quantity,Unit,Monthly rate,Annual increase (%)\nFacility Manager,1,headcount,8000,3",
    )
    p.input_text = text
    files = st.file_uploader(
        "Proposal documents",
        type=["csv", "xlsx", "pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="proposal_files_" + p.id,
        max_upload_size=5,
    )
    if st.button("Extract proposal for checking", key="proposal_extract_" + p.id):
        try:
            rows, notes = interpret_text(text) if text.strip() else ([], [])
            docs = list(p.documents)
            for file in files:
                doc = extract_document(file.name, file.getvalue())
                if not any(d["sha256"] == doc["sha256"] for d in docs):
                    docs.append(doc)
            rows.extend(r for doc in docs for r in doc["rows"])
            p.documents, p.input_rows = docs, rows
            p.drafts["original_editor_seed"] = rows
            p.drafts["extraction_notes"] = notes
            p.drafts["extract_epoch"] = p.drafts.get("extract_epoch", 0) + 1
            st.rerun()
        except Exception:
            st.error(
                "This document could not be read reliably. Your draft is retained; use a text-readable PDF, XLSX, CSV, DOCX or enter the proposal table manually."
            )
    for note in [
        *p.drafts.get("extraction_notes", []),
        *(d["extraction_note"] for d in p.documents if d["extraction_note"]),
    ]:
        st.caption(note)
    st.markdown("**Confirm the interpreted proposal**")
    st.caption(
        "Keep original seniority and combined titles. Units must say headcount or FTE. Amounts are SGD; leave unknown rates/increases blank. Zero quantity explicitly excludes a role."
    )
    p.input_rows = editable_rows(
        p.drafts.setdefault("original_editor_seed", p.input_rows),
        f"proposal_original_rows_{p.id}_{p.drafts.get('extract_epoch', 0)}",
    )
    quoted = [r for r in p.input_rows if r.get("Yearly rates")]
    if quoted:
        st.caption(
            "Year-specific quoted monthly prices were identified. Inspect these against the source; the engine does not add a second general increase to full quoted prices."
        )
        st.dataframe(
            [
                {"Role": r["Role"], **{f"Year {i + 1}": v for i, v in enumerate(r["Yearly rates"])}}
                for r in quoted
            ],
            hide_index=True,
            width="stretch",
        )
    total = st.number_input(
        "Supplied full-contract EPV, if stated (SGD)",
        value=p.claimed_total,
        min_value=0.0,
        key=retained_key("proposal_total_" + p.id),
    )
    p.claimed_total = total
    inclusive = st.checkbox(
        "The rate column represents inclusive monthly manpower charges per head/FTE, not salary alone",
        key=retained_key("proposal_basis_" + p.id),
    )
    accurate = st.checkbox(
        "The interpreted table and project context accurately record my proposal; unknowns are left unanswered",
        key=retained_key("proposal_interpret_" + p.id),
    )
    if st.button(
        "Confirm captured proposal and continue",
        disabled=not (inclusive and accurate),
        key="proposal_capture_" + p.id,
        type="primary",
    ):
        try:
            capture_original(p, values, p.input_rows, inclusive)
            save()
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def current_rows(p):
    originals = {r["id"]: r for r in p.original_rows}
    return [
        {
            **originals.get(r.id, {}),
            "id": r.id,
            "Role": r.label,
            "Quantity": r.quantity if r.included else 0,
            "Unit": r.quantity_unit,
            "Monthly rate": r.rate,
            "Pricing basis": r.rate_reason,
            "Annual increase (%)": r.escalation[1] * 100
            if len(r.escalation) > 1 and len(set(r.escalation[1:])) == 1
            else 0.0
            if len(r.escalation) == 1
            else None,
            "Remarks": r.duties_notes,
            "Experience": r.experience,
            "Qualifications": r.qualifications,
            "Mapping": r.mapped_role or "",
        }
        for r in p.plan.roles
    ]


def future_controls(p, records, officer):
    if unapplied_figures(p):
        st.info("Apply or revert the edited figures before changing future costs.")
        return
    from future_inputs import pwm_form, pwm_trade_hints
    from services.future_groups import general_proposal, general_reference

    roles = [r for r in p.plan.roles if r.included]
    st.markdown("**Annual manpower cost increase**")
    bm = general_reference(p.plan, records, [])
    if bm["available"]:
        st.caption(
            f"Database average {bm['average']:.2%}; observed {bm['minimum']:.2%} to {bm['maximum']:.2%}. Tender manpower charges, not observed wage inflation."
        )
    else:
        st.caption(
            "No validated general reference cohort is available. Enter an officer assumption explicitly."
        )
    selected = st.multiselect(
        "Apply a shared increase to these roles",
        [r.id for r in roles if not r.pwm and r.escalation_mode != "quoted schedule"],
        format_func=lambda rid: role_label(p, rid),
        key=retained_key("proposal_shared_roles_" + p.id),
    )
    percent = st.number_input(
        "Shared annual increase (%)",
        value=None,
        min_value=-50.0,
        max_value=100.0,
        key=retained_key("proposal_shared_percent_" + p.id),
    )
    note = st.text_input("Optional explanation / reference", key=retained_key("proposal_shared_note_" + p.id))
    use_reference = st.checkbox(
        "Use the supported database average for the selected roles",
        key=retained_key("proposal_use_ref_" + p.id),
        disabled=not bm["available"],
    )
    st.caption(
        "Year 1 keeps its starting rates. The same percentage compounds from Year 2. Applying a shared increase replaces a custom profile only for the explicitly selected roles."
    )
    if st.button("Apply shared future assumption", key="proposal_shared_apply_" + p.id):
        try:
            chosen = bm["average"] * 100 if use_reference and bm["available"] else percent
            if chosen is None:
                raise ValueError(
                    "Enter an annual percentage or choose the supported reference; blank is not zero"
                )
            p.plan = general_proposal(p.plan, records, selected, chosen, note, "", use_reference, officer)
            p.drafts.pop("review_rows", None)
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    st.markdown("**Different yearly assumptions or quoted prices**")
    rid = st.selectbox(
        "Manpower row",
        [r.id for r in roles],
        format_func=lambda rid: role_label(p, rid),
        key=retained_key("proposal_future_row_" + p.id),
        index=None,
    )
    if rid:
        role = next(r for r in roles if r.id == rid)
        mode = st.radio(
            "Future price basis",
            ["Yearly officer assumptions", "Quoted calendar-year prices"],
            horizontal=True,
            key=retained_key("proposal_future_method_" + p.id + rid),
        )
        rows = [
            {
                "Year": i + 1,
                "Increase (%)": role.escalation[i] * 100 if i < len(role.escalation) else None,
                "Quoted monthly rate": next(
                    (
                        row.get("Yearly rates", [])[i]
                        for row in p.original_rows
                        if row["id"] == rid and len(row.get("Yearly rates", [])) > i
                    ),
                    None,
                ),
            }
            for i in range(p.plan.profile.years)
        ]
        seed_key = f"year_seed_{rid}_{p.plan.version}"
        year_seed = p.drafts.setdefault(seed_key, p.drafts.get("year_table_" + rid, rows))
        table = st.data_editor(
            pd.DataFrame(year_seed),
            disabled=["Year"],
            hide_index=True,
            width="stretch",
            key=f"proposal_years_{p.id}_{rid}_{p.plan.version}_{p.drafts.get('editor_epoch', 0)}",
        )
        p.drafts["year_table_" + rid] = table.astype(object).where(pd.notna(table), None).to_dict("records")
        source = st.text_input(
            "Quoted-price source or optional yearly-assumption note",
            key=retained_key("proposal_yearly_source_" + p.id + rid),
        )
        if st.button("Apply yearly prices", key="proposal_yearly_apply_" + p.id + rid):
            try:
                if mode == "Quoted calendar-year prices" and not source.strip():
                    raise ValueError("Identify the supplied quotation for these future prices")
                apply_yearly(
                    p,
                    rid,
                    table["Increase (%)"].tolist(),
                    table["Quoted monthly rate"].tolist() if mode == "Quoted calendar-year prices" else None,
                    source,
                    officer,
                )
                p.drafts.pop("review_rows", None)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    relevant = [r for r in roles if pwm_trade_hints(r) or r.pwm]
    if relevant:
        st.markdown("**PWM salary progression**")
        pwm_id = st.selectbox(
            "Confirmed covered trade workers, if applicable",
            [r.id for r in relevant],
            format_func=lambda rid: role_label(p, rid),
            index=None,
            key=retained_key("proposal_pwm_" + p.id),
        )
        if pwm_id:
            before_version = p.plan.version
            try:
                pwm_form(p.plan, next(r for r in relevant if r.id == pwm_id), officer, on_draft=pwm_draft)
            finally:
                if p.plan.version != before_version:
                    p.drafts.pop("review_rows", None)


def operational_controls(p, officer):
    if unapplied_figures(p):
        st.info("Apply or revert edited figures before recording a coverage revision.")
        return
    from services.calculations import coverage_quantity

    st.caption(
        "Coverage, seniority and experience cannot be proved by a historical rate. No workload staffing standard or reporting line is inferred. Retain supplied titles; record only material corrections."
    )
    if re_continuous(p.plan.profile.description):
        st.info(
            "Continuous operation is stated. If continuous on-site attendance is required, confirm simultaneous positions, capacity hours and relief below. Otherwise retain this as a specific scope uncertainty."
        )
    role_id = st.selectbox(
        "Check a known coverage requirement",
        [r.id for r in p.plan.roles if r.included],
        format_func=lambda rid: role_label(p, rid),
        index=None,
        key=retained_key("proposal_coverage_role_" + p.id),
    )
    if not role_id:
        return
    role = next(r for r in p.plan.roles if r.id == role_id)
    a, b, c = st.columns(3)
    hours = a.number_input(
        "Hours/day",
        value=None,
        min_value=0.1,
        max_value=24.0,
        key=retained_key("t2_cov_hours_" + p.id + "_" + role_id),
    )
    days = b.number_input(
        "Days/week",
        value=None,
        min_value=1,
        max_value=7,
        key=retained_key("t2_cov_days_" + p.id + "_" + role_id),
    )
    posts = c.number_input(
        "Simultaneous positions",
        value=None,
        min_value=1,
        max_value=1000,
        key=retained_key("t2_cov_posts_" + p.id + "_" + role_id),
    )
    capacity = st.number_input(
        "Productive/capacity hours per person per week",
        value=None,
        min_value=0.1,
        max_value=168.0,
        key=retained_key("t2_cov_capacity_" + p.id + "_" + role_id),
    )
    basis = st.radio(
        "Capacity basis",
        ["gross", "net"],
        horizontal=True,
        key=retained_key("t2_cov_basis_" + p.id + "_" + role_id),
    )
    relief = st.number_input(
        "Relief factor (1 for net hours)",
        value=None,
        min_value=1.0,
        max_value=3.0,
        key=retained_key("t2_cov_relief_" + p.id + "_" + role_id),
    )
    reason = st.text_input(
        "Operational source / scope of this coverage requirement",
        key=retained_key("t2_cov_reason_" + p.id + "_" + role_id),
    )
    if all(x is not None for x in (hours, days, posts, capacity, relief)):
        try:
            cov = Coverage(
                hours_per_day=hours,
                days_per_week=days,
                simultaneous_posts=posts,
                capacity_hours=capacity,
                capacity_basis=basis,
                relief_factor=relief,
                round_to_personnel=role.quantity_unit == "headcount",
            )
            estimate = coverage_quantity(cov)
            st.info(
                f"Indicative requirement: {estimate['fte']:.2f} FTE; {estimate['suggested_quantity']:g} on the selected unit basis. This is not proof of a feasible roster."
            )
            keep, use = st.columns(2)
            for button, replace in (
                (
                    keep.button(
                        "Record coverage and retain proposed quantity",
                        key="t2_cov_keep_" + p.id + "_" + role_id,
                    ),
                    False,
                ),
                (use.button("Use indicative quantity", key="t2_cov_use_" + p.id + "_" + role_id), True),
            ):
                if button:
                    if not reason.strip():
                        raise ValueError("Record the actual operational basis for the coverage calculation")
                    item = role.model_copy(deep=True)
                    item.coverage, item.quantity_basis, item.quantity_reason = cov, "coverage", reason
                    if replace:
                        item.quantity = estimate["suggested_quantity"]
                    apply_change(
                        p.plan,
                        "role",
                        item.model_dump(mode="json"),
                        "Officer reviewed known coverage requirement",
                        officer,
                    )
                    p.drafts.pop("review_rows", None)
                    st.rerun()
        except ValueError as error:
            st.error(str(error))


def re_continuous(text):
    import re

    return bool(re.search(r"24\s*[/x]\s*7|round.the.clock|continuous", text, re.I))


def finding_controls(p, records, officer):
    state = assessment(p, records)
    for f in state["blockers"]:
        st.error(f.message)
    for message in state["basis_actions"]:
        st.info(
            "Pricing/future basis needed: "
            + message
            + " Update the corresponding row in Figures or Future costs."
        )
    if not state["unresolved"]:
        st.success(
            "No unrecorded material decisions. Recorded risks and evidence limitations remain in the results and export."
        )
    for f in state["unresolved"]:
        with st.container(border=True):
            st.write(f.message)
            st.caption(f.impact)
            choice = st.radio(
                "Officer action",
                [
                    "Keep valid figures / accept corrected calculation",
                    "Correct interpretation",
                    "Revise inputs",
                    "Expert review / unresolved",
                ],
                horizontal=True,
                key=retained_key(f"proposal_decision_{p.id}_{f.id}_{f.fingerprint}"),
            )
            if choice == "Revise inputs":
                st.caption(
                    "Use Figures or Future costs to revise the proposal; valid source figures remain in Original proposal."
                )
                continue
            role = next((r for r in p.plan.roles if r.id == f.role_id), None)
            prior = (
                f.justification
                if f.officer
                else (role.rate_reason if role and f.code == "rate_range" else "")
            )
            if prior.startswith(
                ("Inclusive monthly manpower charge supplied", "Officer selected inclusive monthly allowance")
            ):
                prior = ""
            reason = st.text_area(
                "Relevant explanation or correction",
                value=prior,
                key=retained_key(f"proposal_reason_{p.id}_{f.id}_{f.fingerprint}"),
            )
            if st.button("Record this decision", key=f"proposal_record_{p.id}_{f.id}_{f.fingerprint}"):
                try:
                    record_decision(
                        p.plan,
                        f,
                        "unresolved risk" if choice == "Expert review / unresolved" else "accepted exception",
                        reason,
                        officer,
                        further_approval="Expert review requested"
                        if choice == "Expert review / unresolved"
                        else "",
                    )
                    p.history.append(
                        {"action": choice, "finding": f.message, "reason": reason, "version": p.plan.version}
                    )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


def unapplied_figures(p):
    if "review_rows" not in p.drafts:
        return False

    def cleaned(rows):
        fields = [
            "id",
            "Role",
            "Quantity",
            "Unit",
            "Monthly rate",
            "Pricing basis",
            "Annual increase (%)",
            "Remarks",
            "Experience",
            "Qualifications",
            "Mapping",
            "Source location",
        ]
        return [{key: row.get(key) if row.get(key) is not None else "" for key in fields} for row in rows]

    return cleaned(p.drafts["review_rows"]) != cleaned(current_rows(p)) or p.drafts.get(
        "review_profile", p.plan.profile.model_dump(mode="json")
    ) != p.plan.profile.model_dump(mode="json")


def pending_rate(p):
    return any(
        p.drafts.get("controls", {}).get(f"proposal_rate_{p.id}_{r.id}_{p.plan.version}_exact", r.rate)
        != r.rate
        for r in p.plan.roles
    )


def rate_controls(p, records, officer):
    from services.evidence import rate_benchmark

    roles = [r for r in p.plan.roles if r.included]
    rid = st.selectbox(
        "Inspect or adjust a monthly rate",
        [r.id for r in roles],
        index=None,
        format_func=lambda rid: role_label(p, rid),
        key=retained_key("proposal_rate_role_" + p.id),
    )
    if not rid:
        return
    role = next(r for r in roles if r.id == rid)
    bm = rate_benchmark(
        records, role.mapped_role, role.benchmark_year, role.benchmark_status, role.benchmark_scope
    )
    prefix = f"proposal_rate_{p.id}_{rid}_{p.plan.version}"

    def sync(source, target):
        value = st.session_state[source]
        if target.endswith("_exact") or (value is not None and bm["minimum"] <= value <= bm["maximum"]):
            st.session_state[target] = value

    st.session_state.setdefault(prefix + "_exact", role.rate)
    if bm["available"] and bm["minimum"] < bm["maximum"]:
        low, high = float(bm["minimum"]), float(bm["maximum"])
        initial = role.rate if role.rate is not None and low <= role.rate <= high else round(bm["average"], 2)
        st.session_state.setdefault(prefix + "_range", float(initial))
        st.slider(
            "Observed monthly range (SGD)",
            min_value=low,
            max_value=high,
            step=0.01,
            key=retained_key(prefix + "_range"),
            on_change=sync,
            args=(prefix + "_range", prefix + "_exact"),
        )
        position = (bm["average"] - low) / (high - low) * 100
        st.markdown(
            f'<div style="position:relative;height:18px;font-size:11px"><span style="position:absolute;left:{position:.2f}%;transform:translateX(-50%)">◆ average</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Observed minimum {low:,.2f} · average {bm['average']:,.2f} · maximum {high:,.2f} · {bm['sample_count']} schedules; reference year {role.benchmark_year}."
        )
    exact = st.number_input(
        "Exact proposed monthly rate (SGD)",
        min_value=0.01,
        max_value=10000000.0,
        key=retained_key(prefix + "_exact"),
        on_change=sync if bm["available"] else None,
        args=(prefix + "_exact", prefix + "_range") if bm["available"] else None,
    )
    basis = st.text_input(
        "Pricing basis for a custom or unsupported allowance", key=retained_key(prefix + "_basis")
    )
    if bm["available"] and exact is not None and not bm["minimum"] <= exact <= bm["maximum"]:
        st.caption(
            "The exact amount is outside the observed range. The range bar does not replace it; record the relevant pricing basis."
        )

    def reset_rate():
        st.session_state[prefix + "_exact"] = role.rate
        if bm["available"] and bm["minimum"] < bm["maximum"]:
            st.session_state[prefix + "_range"] = float(initial)

    st.button("Revert unrecorded rate", key=prefix + "_revert", on_click=reset_rate)
    if st.button("Use the displayed rate", key=prefix + "_apply", disabled=unapplied_figures(p)):
        try:
            from services.decision_basis import meaningful

            supported = bm["available"] and exact is not None and bm["minimum"] <= exact <= bm["maximum"]
            if not supported and not meaningful(basis):
                raise ValueError(
                    "Record a supplier quotation, budgeting basis or specific uncertainty for this allowance"
                )
            if exact == role.rate and not basis:
                st.info("This amount is already recorded; its existing pricing basis is retained.")
                return
            item = role.model_copy(deep=True)
            item.rate = exact
            item.rate_reason = (
                basis
                or f"Officer selected inclusive monthly allowance within the eligible tender reference range for {role.benchmark_year}; demonstration comparison, not a verified market price."
            )
            item.rate_origin = (
                "Synthetic benchmark selection" if supported and not basis else "Officer assumption"
            )
            apply_change(
                p.plan, "role", item.model_dump(mode="json"), "Officer applied a reviewed rate", officer
            )
            p.drafts.pop("review_rows", None)
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def check_page(p, records, officer, cfg):
    st.header("2. Check figures and assumptions")
    st.caption("Apply revisions explicitly. The original proposal and source documents remain unchanged.")
    for message in p.drafts.get("quote_interpretation_issues", []):
        st.info(
            "Original quoted-price projection is unavailable: "
            + message
            + " The original prices remain preserved; record a supported reviewed treatment in Future costs."
        )
    figures, operations, future, issues = st.tabs(
        ["Figures", "Operational checks", "Future costs", "Material findings"],
        key="proposal_check_tab_" + p.id,
    )
    with figures:
        values = profile_editor(p, p.plan.profile, "proposal_revised_context_" + p.id)
        seed_key = f"review_editor_seed_{p.plan.version}"
        rows = editable_rows(
            p.drafts.setdefault(seed_key, p.drafts.get("review_rows", current_rows(p))),
            f"proposal_reviewed_rows_{p.id}_{p.plan.version}_{p.drafts.get('editor_epoch', 0)}",
        )
        p.drafts["review_rows"], p.drafts["review_profile"] = rows, values
        st.caption(
            "To exclude an original role, enter zero with a reason; keep its evidence row. Rate comparisons are review flags, not proof a price is wrong."
        )
        if st.button("Apply reviewed figures", key="proposal_apply_" + p.id):
            try:
                update_reviewed(p, values, rows, officer)
                p.drafts.pop("review_rows", None)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        if unapplied_figures(p) and st.button(
            "Revert unapplied figure edits", key="proposal_revert_figures_" + p.id
        ):
            p.drafts.pop("review_rows", None)
            p.drafts.pop("review_profile", None)
            p.drafts[f"review_editor_seed_{p.plan.version}"] = current_rows(p)
            p.drafts["editor_epoch"] = p.drafts.get("editor_epoch", 0) + 1
            st.rerun()
        st.dataframe(
            rate_comparisons(p.plan, records),
            hide_index=True,
            width="stretch",
            column_config={
                key: st.column_config.NumberColumn(format="accounting")
                for key in ("Proposed rate", "Reference average", "Minimum", "Maximum")
            },
        )
        rate_controls(p, records, officer)
        target_year = p.plan.profile.costing_start.year if p.plan.profile.costing_start else None
        year_gaps = [
            r
            for r in p.plan.roles
            if r.included and r.benchmark_year and target_year and r.benchmark_year != target_year
        ]
        if year_gaps:
            st.caption(
                "Reference pricing year differs from contract start for: "
                + "; ".join(r.label for r in year_gaps)
                + ". No inflation adjustment is applied automatically."
            )
            treatment = st.text_area(
                "Shared treatment of the reference-year difference",
                key=retained_key("proposal_shared_year_note_" + p.id),
            )
            if st.button(
                "Record reference-year treatment",
                key="proposal_year_basis_" + p.id,
                disabled=unapplied_figures(p),
            ):
                try:
                    from services.decision_basis import meaningful

                    if not meaningful(treatment):
                        raise ValueError(
                            "Explain why these reference-year allowances are retained or adjusted for the actual contract start"
                        )
                    for row in year_gaps:
                        item = row.model_copy(update={"rate_notes": treatment})
                        apply_change(
                            p.plan,
                            "role",
                            item.model_dump(mode="json"),
                            "Officer recorded shared reference-year treatment",
                            officer,
                        )
                    p.drafts.pop("review_rows", None)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    with operations:
        operational_controls(p, officer)
        question = st.text_area(
            "Optional targeted assistant question", key=retained_key("proposal_question_" + p.id)
        )
        st.caption(
            "Only an explicit request below uses the configured model. No automatic calls occur while editing, saving or navigating."
        )
        if st.button(
            "Ask for proposal comments",
            disabled=not (cfg.api_key and cfg.model and question.strip()),
            key="proposal_ask_" + p.id,
        ):
            from services.agent import converse, create_client

            try:
                candidate = p.plan.model_copy(deep=True)
                candidate.documents = p.documents
                converse(
                    candidate,
                    records + p.quote_records,
                    "Track 2: review this existing proposal. Ask only material questions, preserve seniority/combined titles and original figures. Price differences do not prove staffing adequacy. Suggestions need officer acceptance. "
                    + question,
                    create_client(cfg.api_key),
                    cfg.model,
                    "Validation",
                    review_existing_proposal=True,
                )
                p.plan = candidate
                st.rerun()
            except Exception as error:
                st.error("Assistant review could not be completed: " + str(error))
        for item in p.plan.chat[-4:]:
            st.write(item.get("content", item.get("text", "")))
        if p.plan.pending:
            proposed = []
            for item in p.plan.pending:
                payload = item.get("payload", {})
                role = next((r for r in p.plan.roles if r.id == payload.get("id")), None)
                proposed.append(
                    {
                        "Role": payload.get("label") or (role.label if role else "Project context"),
                        "Proposed values": "; ".join(
                            f"{key}: {payload[key]}"
                            for key in (
                                "quantity",
                                "quantity_unit",
                                "rate",
                                "escalation",
                                "experience",
                                "qualifications",
                            )
                            if key in payload
                        ),
                        "Reason": item.get("reason", ""),
                    }
                )
            st.dataframe(proposed, hide_index=True, width="stretch")
            if st.button(
                "Accept the displayed assistant revisions",
                key="proposal_accept_suggestions_" + p.id,
                disabled=unapplied_figures(p),
            ):
                from services.workflow import apply_pending

                try:
                    apply_pending(p.plan, officer)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        if (p.plan.pending or p.plan.working_notes) and st.button(
            "Discard unaccepted assistant suggestions", key="proposal_discard_assistant_" + p.id
        ):
            p.plan.pending, p.plan.working_notes = [], {}
            p.history.append(
                {"action": "Officer discarded unaccepted assistant suggestions", "version": p.plan.version}
            )
            st.rerun()
    with future:
        future_controls(p, records, officer)
    with issues:
        finding_controls(p, records, officer)
        supporting = st.file_uploader(
            "Supporting evidence for this review, if needed",
            type=["csv", "xlsx", "pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="proposal_support_" + p.id,
            max_upload_size=5,
        )
        if st.button(
            "Attach selected supporting evidence",
            key="proposal_attach_support_" + p.id,
            disabled=not supporting,
        ):
            try:
                documents = list(p.documents)
                for file in supporting:
                    document = extract_document(file.name, file.getvalue())
                    if not any(d["sha256"] == document["sha256"] for d in documents):
                        documents.append(document)
                p.documents = documents
                p.history.append(
                    {
                        "action": "Officer added supporting evidence; original proposal unchanged",
                        "version": p.plan.version,
                    }
                )
                st.rerun()
            except Exception:
                st.error(
                    "This supporting document could not be read reliably. The existing proposal and evidence remain unchanged."
                )
    note = st.text_area(
        "Shared operational basis or specific retained scope uncertainty",
        value=p.drafts.get("deployment_note", ""),
        key=retained_key("proposal_operational_note_" + p.id),
        placeholder="What supports retaining this proposed deployment? If coverage is not established, state the specific uncertainty and how it will be checked.",
    )
    p.drafts["deployment_note"] = note
    checked = st.checkbox(
        "I have checked the proposal context, roles, quantities/units, rates, capability and future costs, including retained qualifications",
        key=retained_key("proposal_checked_" + p.id),
    )
    state = assessment(p, records)
    if state["blockers"] or state["unresolved"]:
        st.caption(
            f"Before continuing: {len(state['blockers'])} invalid/missing input issue(s), {len(state['unresolved'])} material decision(s). See Material findings. Missing experience alone is a qualification, not an automatic arithmetic blocker."
        )
    if unapplied_figures(p) or pending_rate(p):
        st.info("Apply or revert the edited figures/rate before confirming the reviewed inputs.")
    if p.plan.pending or p.plan.working_notes:
        st.info(
            "Assistant suggestions or notes are not accepted revisions. Apply or discard them before confirmation."
        )
    if st.button(
        "Confirm reviewed inputs and view budget",
        disabled=not checked
        or bool(
            state["blockers"]
            or state["unresolved"]
            or state["basis_actions"]
            or p.plan.pending
            or p.plan.working_notes
            or unapplied_figures(p)
            or pending_rate(p)
        ),
        type="primary",
        key="proposal_review_confirm_" + p.id,
    ):
        try:
            confirm_review(p, records, officer, note)
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def result_page(p, records, officer, save):
    from review_inputs import (
        annual_review,
        deployment_review,
        results_style,
        sensitivity_review,
        supporting_review,
    )
    from services.proposal_export import comparison_rows, management_report, workbook

    results_style()
    st.header("3. Your reviewed manpower budget")
    state, c = assessment(p, records), comparison(p, records)
    result = c["reviewed"]
    reviewed_ready = (
        all(
            gate in p.plan.confirmations
            for gate in (
                "profile",
                "responsibilities",
                "quantities",
                "plan",
                "rates",
                "base",
                "escalation",
                "validation",
            )
        )
        and not unapplied_figures(p)
        and not pending_rate(p)
    )
    if not reviewed_ready:
        st.info(
            "Draft calculation preview. Confirm the reviewed inputs in Check figures and assumptions before approving this budget."
        )
    if result is None:
        st.error("The reviewed calculation needs correction. Return to Check figures and assumptions.")
        return
    confirmed = "final" in p.plan.confirmations and not state["blockers"] and not state["unresolved"]
    st.info("Confirmed reviewed budget" if confirmed else "Draft reviewed budget - not yet approved")
    a, b, d = st.columns(3)
    a.metric(
        "Original recalculated EPV (SGD)",
        f"{c['original']['contract_total']:,.2f}" if c["original"] else "Incomplete original",
    )
    b.metric("Reviewed full contract EPV (SGD)", f"{result['contract_total']:,.2f}")
    d.metric(
        "Change from original calculation (SGD)",
        f"{c['difference']:+,.2f}" if c["difference"] is not None else "Unavailable",
    )
    if c["percent"] is not None:
        st.caption(f"Difference: {c['percent']:+.2f}%. A percentage alone does not establish reasonableness.")
    if p.original_claimed_total is not None:
        st.caption(
            f"Original supplied EPV: SGD {p.original_claimed_total:,.2f}; retained separately from recalculated totals."
        )
    st.caption(
        f"Base period: {p.plan.profile.base_years} years, SGD {result['base_total']:,.2f}. Option: {p.plan.profile.option_years} years, SGD {result['option_total']:,.2f}."
    )
    profiles = {
        tuple(r.escalation)
        for r in p.plan.roles
        if r.included and not r.pwm and r.escalation_mode == "assumption"
    }
    if len(profiles) == 1 and len(next(iter(profiles))) > 1 and len(set(next(iter(profiles))[1:])) == 1:
        st.caption(
            f"Selected annual manpower increase: {next(iter(profiles))[1]:.2%} from Year 2, compounded."
        )
    elif profiles:
        st.caption("Annual manpower increase varies by role/year; see the Budget and Scenarios tabs.")
    if any(r.included and r.pwm for r in p.plan.roles):
        st.caption("PWM salary progression applies to the recorded covered workers and salary component.")
    from services.final_review import source_summary

    if source_summary(p.plan, records)[2]:
        st.caption("Demo reference data — replace with validated tender data before operational use.")
    tabs = st.tabs(
        ["Budget", "Scenarios", "Manpower", "Assumptions & sources"],
        key="proposal_results_tab_" + p.id,
        on_change="rerun",
    )
    with tabs[0]:
        annual_review(p.plan, result)
        st.markdown("**Original vs reviewed**")
        st.dataframe(
            comparison_rows(p, records),
            hide_index=True,
            width="stretch",
            column_config={
                name: st.column_config.NumberColumn(name, format="%.2f")
                for name in (
                    "Original rate",
                    "Reviewed rate",
                    "Original contract cost",
                    "Reviewed contract cost",
                    "Cost difference (SGD)",
                )
            },
        )
    with tabs[1]:
        sensitivity_review(p.plan, records + p.quote_records, on_edit=lambda: _set_stage(1))
    with tabs[2]:
        deployment_review(p.plan)
    with tabs[3]:
        supporting_review(p.plan, records, state["findings"], result)
        if p.documents:
            st.dataframe(
                [
                    {
                        "Document": d["name"],
                        "Evidence role": "Original proposal"
                        if any(o["sha256"] == d["sha256"] for o in p.original_documents)
                        else "Supplementary evidence",
                        "Extraction note": d["extraction_note"],
                    }
                    for d in p.documents
                ],
                hide_index=True,
                width="stretch",
            )
        st.caption(
            "The original uploaded bytes, extracted rows and original claimed totals are preserved in the proposal snapshot. Accepted revisions do not overwrite them."
        )
    st.divider()
    st.caption("Confirmed exports" if confirmed else "Draft exports - no approval is implied")
    st.download_button(
        "Download reviewed budget",
        workbook(p, records),
        file_name=f"proposal-{'confirmed' if confirmed else 'draft'}-v{p.plan.version}.xlsx",
        key="proposal_workbook_" + p.id,
    )
    st.download_button(
        "Download management review report",
        management_report(p, records).encode(),
        file_name="manpower-proposal-review.html",
        mime="text/html",
        key="proposal_report_" + p.id,
    )
    if state["blockers"] or state["unresolved"]:
        st.caption(
            "Before confirmation: return to Check figures and assumptions to resolve the listed material issues."
        )
    if st.button(
        "Confirm reviewed budget",
        key="proposal_final_" + p.id,
        disabled=confirmed
        or not reviewed_ready
        or bool(
            state["blockers"]
            or state["unresolved"]
            or state["basis_actions"]
            or p.plan.pending
            or p.plan.working_notes
        ),
        type="primary",
    ):
        try:
            confirm(p.plan, "final", officer, records + p.quote_records)
            save()
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    st.caption(f"Reviewed budget version {p.plan.version}. Original proposal evidence remains unchanged.")


def render(cfg, store, owner):
    from services.evidence import load_records

    storage = ProposalStore(store.engine)
    st.session_state.setdefault("proposal", Proposal())
    st.session_state.setdefault("proposal_revision", 0)
    p = st.session_state.proposal = Proposal.model_validate(st.session_state.proposal.model_dump(mode="json"))
    for key, value in p.drafts.get("controls", {}).items():
        if key not in st.session_state:
            st.session_state[key] = value
    remember_controls(p)
    officer = st.session_state.get("officer", "") or "Local reviewing officer"
    records = load_records()

    def save():
        try:
            remember_controls(p)
            st.session_state.proposal_revision = storage.save(p, owner, st.session_state.proposal_revision)
            st.session_state.proposal_saved_hash = digest(p)
            return True
        except (ConflictError, ValueError) as error:
            st.error(str(error))
            return False

    with st.sidebar:
        st.caption("MANPOWER BUDGETING · REVIEW PROPOSED BUDGET")
        st.write(
            "Saved"
            if st.session_state.get("proposal_saved_hash") == digest(p)
            else "Unsaved proposal changes"
        )
        if st.button("Save proposal draft", key="proposal_save"):
            st.session_state.proposal_save_requested = True
        saved = storage.list(owner)
        choices = {r["id"]: f"{r['name']} · revision {r['revision']}" for r in saved}
        selected = st.selectbox(
            "Saved proposal reviews",
            list(choices),
            format_func=choices.get,
            index=None,
            key=retained_key("proposal_saved_selection"),
        )
        if st.button("Resume proposal", disabled=selected is None, key="proposal_resume"):
            st.session_state.proposal_switch = selected
        if st.button("New proposal review", key="proposal_new"):
            st.session_state.proposal_switch = "new"
        snapshot_slot = st.empty()
        restore = st.file_uploader(
            "Restore proposal snapshot", type=["json"], key="proposal_restore_file", max_upload_size=40
        )
        if st.button("Restore as a separate review", disabled=restore is None, key="proposal_restore"):
            try:
                value = Proposal.model_validate_json(restore.getvalue())
                value = restore_copy(value)
                st.session_state.proposal_restore_candidate = value
                st.session_state.proposal_switch = "restore"
            except ValueError as error:
                st.error(str(error))
    target = st.session_state.get("proposal_switch")
    if target:
        st.info(
            "Save the current review before switching, or explicitly discard its unsaved edits. Downloading a snapshot is also available."
        )
        a, b, c = st.columns(3)
        keep = a.button("Save and switch", key="proposal_save_switch")
        discard = b.button("Discard unsaved edits and switch", key="proposal_discard_switch")
        if c.button("Keep this proposal open", key="proposal_cancel_switch"):
            st.session_state.pop("proposal_switch")
            st.rerun()
        if discard or keep:
            st.session_state.proposal_switch_action = "discard" if discard else "save"
    if p.stage != 2:
        st.title("Review and improve a proposed manpower budget")
    steps = ["Add proposed budget", "Check figures and assumptions", "View reviewed budget"]
    if p.original:
        selected_stage = st.radio(
            "Proposal journey",
            [1, 2],
            index=0 if p.stage == 1 else 1,
            format_func=lambda x: steps[x],
            horizontal=True,
            key=retained_key(f"proposal_navigation_{p.id}_{p.stage}"),
        )
        if selected_stage != p.stage:
            p.stage = selected_stage
            st.rerun()
    if p.stage == 0:
        capture_page(p, save)
    elif p.stage == 1:
        check_page(p, records, officer, cfg)
    else:
        result_page(p, records, officer, save)
    if st.session_state.pop("proposal_save_requested", False):
        if save():
            st.success("Saved proposal draft. Saving does not accept suggestions or confirm the budget.")

    remember_controls(p)
    snapshot_slot.download_button(
        "Download proposal snapshot",
        p.model_dump_json(indent=2),
        file_name="proposal-review-snapshot.json",
        key="proposal_snapshot",
    )
    action = st.session_state.pop("proposal_switch_action", None)
    if action and (action == "discard" or save()):
        if target == "new":
            new, revision = Proposal(), 0
        elif target == "restore":
            new, revision = st.session_state.pop("proposal_restore_candidate"), 0
        else:
            new, revision = storage.load(target, owner)
        new.drafts["original_editor_seed"] = new.input_rows
        if new.drafts.get("review_rows"):
            new.drafts[f"review_editor_seed_{new.plan.version}"] = new.drafts["review_rows"]
        new.drafts["editor_epoch"] = new.drafts.get("editor_epoch", 0) + 1
        st.session_state.proposal, st.session_state.proposal_revision = new, revision
        st.session_state.proposal_saved_hash = digest(new) if revision else ""
        st.session_state.pop("proposal_switch")
        st.rerun()
