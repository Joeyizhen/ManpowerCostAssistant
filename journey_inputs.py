"""Project/manpower screens. Editing and navigation make no model calls or approvals."""

import re
from uuid import uuid4

import pandas as pd
import streamlit as st

from activity_nav import retained_key
from services.hybrid import (
    cell_text,
    comparison_rows,
    save_input_table,
    save_project_inputs,
    validate_comparison,
)
from services.journey import working_draft
from services.workflow import missing_for_gate

CONTEXTS = {"Existing contract": "existing contract", "New site / service": "new site / service"}
HEADCOUNT_UI_VERSION = 2
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
BRIEF_LABEL = "Describe the properties and operating conditions the FM team will manage"


def project_prefix(plan):
    return f"six_{plan.id}_project_v2"


def pending_control_errors(plan, scope="all"):
    """Unapplied UI choices must not be mistaken for stored officer selections."""
    errors = []
    if plan.basis_drafts.get("headcount_entry"):
        errors.append("Apply or clear the saved headcount update in Deployment before confirming.")
    if plan.basis_drafts.get("project_text"):
        errors.append(
            "Project: correct the unfinished project entry — " + plan.basis_drafts["project_text"]["error"]
        )
    key = st.session_state.get("six_editor_key", "")
    draft = working_draft(plan)
    if plan.id in key:
        if st.session_state.get(key + "_error"):
            errors.append(st.session_state[key + "_error"])
        shared_key = key.removesuffix("_table") + "_fte"
        selected = st.session_state.get(shared_key)
        recorded = {r.id for r in draft.roles if r.quantity_unit == "FTE"}
        if selected is not None and set(selected) != recorded:
            errors.append(
                "Apply the shared / part-time staffing selection, or restore the recorded selection."
            )
    for role in draft.roles if scope == "all" else []:
        if "pwm_" + role.id in plan.basis_drafts:
            errors.append(f"{role.label}: apply or revert the saved PWM input draft before confirmation.")
        prefix = f"esc_{plan.id}_{role.id}"
        mode = st.session_state.get(prefix + "_mode", plan.basis_drafts.get("future_mode_" + role.id))
        if mode is not None and mode != ("PWM salary progression" if role.pwm else role.escalation_mode):
            errors.append(
                f"{role.label}: apply the selected future price method, or return to the recorded method."
            )
        text = st.session_state.get(prefix + "_yearly_text")
        reason = st.session_state.get(prefix + "_yearly_reason")
        if (text is not None and text != ", ".join(f"{e * 100:g}" for e in role.escalation)) or (
            reason is not None and reason != role.escalation_reason
        ):
            errors.append(f"{role.label}: apply the edited yearly profile and reason before confirming.")
        if not st.session_state.get(prefix + "_clear_policy") and any(
            st.session_state.get(prefix + suffix)
            for suffix in (
                "_policy_name",
                "_policy_effective",
                "_policy_amount",
                "_policy_component",
                "_policy_source",
                "_policy_basis",
                "_policy_overlap",
            )
        ):
            errors.append(f"{role.label}: add the component adjustment, or clear the unadded adjustment.")
    kinds = {
        "operational": ("quantity",),
        "rates": ("quantity", "rate"),
        "all": ("quantity", "rate", "escalation", "policy"),
    }[scope]
    if scope == "all" and "common_future" in plan.basis_drafts:
        errors.append("Apply or revert the general annual allowance draft before confirming future costs.")
    for kind in kinds:
        if kind in plan.basis_drafts:
            errors.append(f"Record or revert the {kind} basis draft before confirmation.")
    for prefix, baseline in st.session_state.get("finding_inputs", {}).items() if scope == "all" else []:
        if (
            prefix.startswith(f"finding_{plan.id}_")
            and not st.session_state.get(prefix + "_reset")
            and any(
                prefix + suffix in st.session_state and st.session_state[prefix + suffix] != value
                for suffix, value in baseline.items()
            )
        ):
            label = st.session_state.get("finding_labels", {}).get(prefix, "this finding")
            errors.append(f"Record or revert the edited finding decision: {label}")
    return errors


def parse_start(text):
    text = text.strip()
    if not text:
        return None, None
    if re.fullmatch(r"[0-9]{4}", text):
        year, month = int(text), None  # Retain older year-only drafts without inventing a month.
    else:
        match = re.fullmatch(r"([A-Za-z]{3})\s+([0-9]{4})", text)
        if not match or match[1].title() not in MONTHS:
            raise ValueError("Enter the anticipated start as MMM YYYY, for example Jan 2028.")
        month, year = MONTHS.index(match[1].title()) + 1, int(match[2])
    if not 1900 <= year <= 2200:
        raise ValueError("Enter a start year between 1900 and 2200.")
    return year, month


def parse_term(text, label, minimum):
    if not text.strip():
        return None
    if not re.fullmatch(r"[0-9]+", text.strip()) or not minimum <= int(text) <= 20:
        raise ValueError(f"{label}: enter a whole number from {minimum} to 20.")
    return int(text)


def start_text(profile):
    year = profile.start_year or (profile.start.year if profile.start else None)
    month = profile.start_month or (profile.start.month if profile.start else None)
    return f"{MONTHS[month - 1]} {year}" if year and month else str(year or "")


def project_changed(field=None):
    plan = st.session_state.plan
    p = working_draft(plan).profile
    prefix = project_prefix(plan)

    def value(name, default):
        return st.session_state.get(prefix + name, default)

    try:
        year, month = parse_start(value("_start", start_text(p)))
        base = parse_term(
            value("_base", str(p.base_years) if p.base_years is not None else ""), "Base term", 1
        )
        option = parse_term(
            value("_option", str(p.option_years) if p.option_years is not None else ""), "Option term", 0
        )
        if base is not None and option is not None and base + option > 20:
            raise ValueError("Base and option terms together cannot exceed 20 years.")
        exact = value("_exact", p.start)
        if field == "exact" and exact:
            year, month = exact.year, exact.month
            st.session_state[prefix + "_start"] = f"{MONTHS[month - 1]} {year}"
        elif field == "start" and exact and (year, month) != (exact.year, exact.month):
            exact = None
            st.session_state[prefix + "_exact"] = None
        save_project_inputs(
            plan,
            value("_brief", p.description),
            year,
            base,
            option,
            plan.contract_kind,
            name=value("_name", p.name),
            start=exact,
            clear_start=exact is None,
            start_month=month,
        )
        st.session_state.pop(prefix + "_error", None)
        plan.basis_drafts.pop("project_text", None)
    except ValueError as error:
        st.session_state[prefix + "_error"] = str(error)
        plan.basis_drafts["project_text"] = {
            name: value("_" + name, "") for name in ("name", "brief", "start", "base", "option")
        }
        plan.basis_drafts["project_text"]["error"] = str(error)


def project_screen(plan):
    p = working_draft(plan).profile
    prefix = project_prefix(plan)
    raw = plan.basis_drafts.get("project_text", {})
    st.text_input(
        "Project name",
        raw.get("name", p.name if p.name != "Untitled project" else ""),
        key=retained_key(prefix + "_name"),
        on_change=project_changed,
        placeholder="Appointment of FM Manpower for Site Corgi for 3 + 3 years",
    )
    st.text_area(
        BRIEF_LABEL,
        raw.get("brief", p.description),
        height=110,
        key=retained_key(prefix + "_brief"),
        on_change=project_changed,
        placeholder="For example: A 15-storey office building with ground-floor retail, operating daily from 8am–10pm, with critical equipment requiring after-hours response.",
    )
    st.caption("Enter the anticipated start as MMM YYYY and the terms as numbers of years.")
    a, b, c = st.columns(3)
    a.text_input(
        "Anticipated start month",
        raw.get("start", start_text(p)),
        placeholder="Jan 2028",
        key=retained_key(prefix + "_start"),
        on_change=project_changed,
        args=("start",),
        help="Month and year are enough for planning. An older year-only draft may keep its month unknown.",
    )
    b.text_input(
        "Base term (years)",
        raw.get("base", str(p.base_years) if p.base_years is not None else ""),
        placeholder="e.g. 3",
        key=retained_key(prefix + "_base"),
        on_change=project_changed,
        help="Enter the number of base-contract years.",
    )
    c.text_input(
        "Option term (years)",
        raw.get("option", str(p.option_years) if p.option_years is not None else ""),
        placeholder="e.g. 3, or 0 if none",
        key=retained_key(prefix + "_option"),
        on_change=project_changed,
        help="Enter the number of option years; use 0 if there are none.",
    )
    if p.base_years is not None and p.option_years is not None:
        st.caption(f"{p.base_years} base + {p.option_years} option = {p.years} years")


def validate_project(plan):
    errors = missing_for_gate(working_draft(plan), "profile")
    replacements = {
        "Project description is missing (record 'unknown' if unknown)": "Describe the properties and operating conditions.",
        "Project base years is missing": "Enter the base term in years.",
        "Project option years is missing": "Enter option years, or 0 if there are none.",
        "Contract start year is missing (an exact date is optional)": "Enter the anticipated start, for example Jan 2028.",
    }
    errors = [replacements.get(error, error) for error in errors]
    if errors:
        raise ValueError("; ".join(errors))


def commit_rows(plan, rows, status=None, support=None, staff_defaults=False):
    p = working_draft(plan).profile
    if staff_defaults:
        rows = [dict(r) for r in rows]
        for row in rows:
            q = row.get("Proposed quantity / FTE")
            if (
                cell_text(q)
                and row.get("Quantity basis", "unspecified") == "unspecified"
                and float(q).is_integer()
            ):
                row["Quantity basis"] = "headcount"
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
    from services.decision_basis import meaningful, record_basis, retained_basis

    draft = working_draft(plan)
    for role in draft.roles:
        if (
            role.quantity is not None
            and meaningful(role.duties_notes)
            and not retained_basis(draft, role, "quantity")
        ):
            record_basis(
                plan,
                "quantity",
                [role.id],
                "Operational rationale",
                role.duties_notes,
                "Officer deployment table",
                "officer assumption",
                "Officer input",
            )


def editor_changed(key):
    plan = st.session_state.plan
    rows = [dict(r) for r in st.session_state[key + "_base"]]
    for index, values in st.session_state.get(key, {}).get("edited_rows", {}).items():
        rows[int(index)].update(values)
    by_id = {row["id"]: row for row in rows}
    rows = [
        {**row, **by_id.get(row["id"], {})}
        for row in comparison_rows(plan, common=False, include_pending=False)
    ]
    try:
        commit_rows(
            plan,
            rows,
            status="known" if plan.contract_kind == "existing contract" else "no existing deployment",
            staff_defaults=True,
        )
        st.session_state.pop(key + "_error", None)
        if any(
            "Quantity basis" in values
            for values in st.session_state.get(key, {}).get("edited_rows", {}).values()
        ):
            st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
    except ValueError:
        affected = [
            rows[int(i)].get("Role title") or f"row {int(i) + 1}"
            for i in st.session_state.get(key, {}).get("edited_rows", {})
        ]
        st.session_state[key + "_error"] = (
            "Check titles and non-negative staff quantities (maximum 10,000) for: "
            + ", ".join(affected)
            + ". The last valid draft is retained."
        )


def support_changed(key):
    plan = st.session_state.plan
    commit_rows(
        plan, comparison_rows(plan, common=False, include_pending=False), support=st.session_state[key]
    )


def current_status_changed(key):
    plan = st.session_state.plan
    p = working_draft(plan).profile
    save_project_inputs(
        plan,
        p.description,
        p.start_year or (p.start.year if p.start else None),
        p.base_years,
        p.option_years,
        CONTEXTS[st.session_state[key]],
    )
    st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1


def staffing_basis_changed(prefix):
    plan = st.session_state.plan
    rows = comparison_rows(plan, common=False, include_pending=False)
    shared = st.session_state.get(prefix + "_fte", [])
    for row in rows:
        row["Quantity basis"] = (
            "FTE"
            if row["id"] in shared
            else (
                st.session_state.get(prefix + "_convert_" + row["id"], "posts")
                if row["Quantity basis"] == "posts"
                else "headcount"
            )
        )
    commit_rows(plan, rows)
    st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1


def role_options(plan, scope):
    from services.role_catalogue import available_roles

    options = available_roles(plan)
    return options["typical"] + options["additional"]


def add_deployment_role(plan, title):
    from services.role_catalogue import identity

    values = comparison_rows(plan, common=False, include_pending=False)
    if not title or identity(title) in {identity(r["Role title"]) for r in values}:
        return
    values.append(
        {
            "id": "role-" + uuid4().hex[:8],
            "Role title": title.strip(),
            "Proposed quantity / FTE": None,
            "Current quantity / FTE": None,
            "Quantity basis": "headcount",
        }
    )
    commit_rows(plan, values)
    st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1


def add_role_control(plan, prefix):
    from services.role_catalogue import available_roles

    choices = available_roles(plan)
    if choices["typical"]:
        st.markdown("**Typical manpower**")
        selected = st.pills(
            "Typical manpower", choices["typical"], label_visibility="collapsed", key=prefix + "_typical"
        )
        if selected:
            add_deployment_role(plan, selected)
            st.rerun()
    selected = st.selectbox(
        "Add another role",
        choices["additional"],
        index=None,
        placeholder="Search other database roles",
        key=retained_key(prefix + "_add"),
    )
    if st.button("Add role", key="add_selected_roles", disabled=not selected):
        add_deployment_role(plan, selected)
        st.rerun()


def keep_unlisted_role(key):
    title = st.session_state.get(key, "")
    if title:
        st.session_state.plan.basis_drafts["role_entry"] = {"title": title}
    else:
        st.session_state.plan.basis_drafts.pop("role_entry", None)


def keep_deployment_reason(prefix):
    st.session_state.plan.basis_drafts["deployment_reason"] = {
        "roles": st.session_state.get(prefix + "_reason_roles", []),
        "reason": st.session_state.get(prefix + "_reason", ""),
    }


def shared_deployment_reason(plan, prefix):
    from services.decision_basis import meaningful, record_basis, retained_basis

    if st.session_state.pop(prefix + "_reason_reset", False):
        st.session_state.pop(prefix + "_reason_roles", None)
        st.session_state.pop(prefix + "_reason", None)
    saved = plan.basis_drafts.get("deployment_reason", {})
    draft = plan.model_copy(deep=True)
    draft.pending = []
    draft = working_draft(draft)
    labels = {r.id: r.label for r in draft.roles if r.included and r.quantity is not None}
    needs = [
        r.id
        for r in draft.roles
        if r.id in labels
        and not retained_basis(draft, r, "quantity")
        and not meaningful(r.duties_notes)
        and (
            not meaningful(r.quantity_reason)
            or r.quantity_reason.startswith("Officer-provided quantity in manpower table")
        )
        and (plan.contract_kind != "existing contract" or r.current_quantity != r.quantity)
    ]
    if not labels:
        return
    with st.expander("One operational reason covers related roles", expanded=bool(needs)):
        selected = st.multiselect(
            "Roles covered",
            list(labels),
            default=[rid for rid in saved.get("roles", needs) if rid in labels],
            format_func=labels.get,
            key=retained_key(prefix + "_reason_roles"),
            on_change=keep_deployment_reason,
            args=(prefix,),
        )
        reason = st.text_area(
            "Shared operational reason",
            value=saved.get("reason", ""),
            key=retained_key(prefix + "_reason"),
            on_change=keep_deployment_reason,
            args=(prefix,),
            placeholder="For example: two buildings require an on-site response team during opening hours.",
        )
        if st.button("Record shared reason", key=prefix + "_reason_record"):
            try:
                if plan.pending:
                    raise ValueError(
                        "Accept or dismiss assistant suggestions in Confirm deployment before recording this reason."
                    )
                record_basis(
                    plan,
                    "quantity",
                    selected,
                    "Operational rationale",
                    reason,
                    "Officer deployment decision",
                    "officer assumption",
                    st.session_state.officer,
                )
                plan.basis_drafts.pop("deployment_reason", None)
                st.session_state[prefix + "_reason_reset"] = True
                st.rerun()
            except ValueError as error:
                st.info(str(error))

        if saved.get("reason") and st.button("Clear unrecorded reason", key=prefix + "_reason_clear"):
            plan.basis_drafts.pop("deployment_reason", None)
            st.session_state[prefix + "_reason_reset"] = True
            st.rerun()


def manpower_screen(plan):
    prefix = f"six_{plan.id}_manpower_v2_{st.session_state.get('six_epoch', 0)}"
    labels = list(CONTEXTS)
    selected = next((i for i, label in enumerate(labels) if CONTEXTS[label] == plan.contract_kind), None)
    st.radio(
        "Deployment context",
        labels,
        index=selected,
        key=retained_key(prefix + "_status"),
        horizontal=True,
        on_change=current_status_changed,
        args=(prefix + "_status",),
    )
    existing = plan.contract_kind == "existing contract"
    st.write(
        "Enter current and proposed staff numbers. Leave unknown current numbers blank."
        if existing
        else "Enter the staff numbers proposed for the new site or service."
    )
    st.caption("Enter the number of people for each added role. Unused roles do not need to be added.")
    rows = comparison_rows(plan, common=False, include_pending=False)
    focus = st.session_state.get("review_focus_" + plan.id, {})
    if focus.get("step") == 1:
        rows.sort(key=lambda row: row["id"] not in focus.get("roles", []))
    dormant = {
        r["id"]
        for r in rows
        if r["id"].startswith("common-")
        and pd.isna(r["Proposed quantity / FTE"])
        and pd.isna(r["Current quantity / FTE"])
        and not r.get("Duties / deployment notes")
    }
    if dormant and st.button("Remove unused suggested roles", key="remove_unused_suggestions"):
        commit_rows(plan, [r for r in rows if r["id"] not in dormant])
        st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
        st.rerun()
    for row in rows:
        if pd.isna(row["Proposed quantity / FTE"]) and row["Quantity basis"] == "unspecified":
            row["Quantity basis"] = "headcount"  # New input rows use the disclosed whole-person default.
    if not rows:
        st.caption("Add the roles needed for this deployment below.")
        add_role_control(plan, prefix)
        return []
    key = prefix + "_table"
    st.session_state.six_editor_key = key
    st.session_state[key + "_base"] = rows
    frame = pd.DataFrame(rows)
    for name in ["Current quantity / FTE", "Proposed quantity / FTE", "Change"]:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    has_legacy_units = any(row["Quantity basis"] != "headcount" for row in rows)
    edited = st.data_editor(
        frame,
        key=key,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        height=min(650, 60 + 50 * len(rows)),
        row_height=50,
        placeholder="",
        disabled=["Change", "Quantity basis"],
        on_change=editor_changed,
        args=(key,),
        column_config={
            "id": None,
            "Deployment": None,
            "Role title": st.column_config.TextColumn("Role", required=True, width="large"),
            "Current quantity / FTE": st.column_config.NumberColumn(
                "Current quantity" if has_legacy_units else "Current headcount",
                min_value=0.0,
                max_value=10000.0,
                step=1.0,
                width="small",
            )
            if existing
            else None,
            "Proposed quantity / FTE": st.column_config.NumberColumn(
                "Proposed quantity" if has_legacy_units else "Proposed headcount",
                min_value=0.0,
                max_value=10000.0,
                step=1.0,
                width="small",
            ),
            "Change": st.column_config.NumberColumn("Change", width="small", format="%+.2f")
            if existing
            else None,
            "Quantity basis": st.column_config.TextColumn("Saved unit", width="small")
            if has_legacy_units
            else None,
            "Duties / deployment notes": st.column_config.TextColumn(
                "Operational rationale",
                width="large",
                help="Explain increases, decreases, shared allocations or important assumptions. A reason is required when a known current figure changes.",
            ),
        },
    )
    included = [
        r for r in rows if pd.notna(r["Proposed quantity / FTE"]) and r["Proposed quantity / FTE"] > 0
    ]
    incomplete = [r for r in rows if pd.isna(r["Proposed quantity / FTE"])]
    excluded = sum(pd.notna(r["Proposed quantity / FTE"]) and r["Proposed quantity / FTE"] == 0 for r in rows)
    st.caption(
        f"{len(included)} included roles · {excluded} excluded (0) · {len(incomplete)} unanswered proposed entries"
    )
    deployment_summary(edited.to_dict("records"), existing if plan.contract_kind != "unspecified" else None)
    if has_legacy_units:
        legacy_headcount_control(plan, prefix, existing)
    add_role_control(plan, prefix)
    with st.expander("Additional context (optional)"):
        st.text_area(
            "Anything not covered in the table",
            plan.input_support,
            key=retained_key(prefix + "_support"),
            height=85,
            on_change=support_changed,
            args=(prefix + "_support",),
            placeholder="Only add details the role notes do not cover, such as work handled by a separate contractor.",
        )
    return edited.to_dict("records")


def deployment_summary(rows, existing=False):
    from services.headcounts import comparison

    totals = comparison(rows, existing)
    current, proposed, change = st.columns(3)
    current.metric(
        "Current headcount"
        if not (totals["current_missing"] or totals["legacy_rows"])
        else "Known current headcount",
        str(totals["current"]),
    )
    proposed.metric(
        "Proposed headcount"
        if not (totals["proposed_missing"] or totals["legacy_rows"])
        else "Known proposed headcount",
        str(totals["proposed"]),
    )
    change.metric("Headcount change", f"{totals['change']:+d}" if totals["change"] is not None else "Pending")
    if totals["current_missing"] or totals["proposed_missing"]:
        st.caption(
            f"Incomplete comparison: {totals['current_missing']} current and {totals['proposed_missing']} proposed entries are unanswered or invalid. These are subtotals, not zero assumptions."
        )
    if totals["legacy_rows"]:
        st.caption(
            f"{totals['legacy_rows']} saved role(s) use earlier units and are excluded from this headcount comparison."
        )


def legacy_headcount_control(plan, prefix, existing):
    rows = comparison_rows(plan, common=False, include_pending=False)
    legacy = {r["id"]: r["Role title"] for r in rows if r["Quantity basis"] != "headcount"}
    saved = plan.basis_drafts.get("headcount_entry", {})
    with st.expander("Update saved quantities to headcount"):
        st.caption(
            "Earlier units are retained unchanged. Enter the actual number of people to replace a saved entry; no conversion is assumed."
        )
        rid = st.selectbox("Saved role", list(legacy), format_func=legacy.get, key=prefix + "_legacy_role")
        entered = saved if saved.get("role") == rid else {}
        entry_key = prefix + "_legacy_" + rid
        current = (
            st.number_input(
                "Current number of people",
                min_value=0,
                max_value=10000,
                value=entered.get("current"),
                step=1,
                key=entry_key + "_current",
                on_change=keep_headcount_entry,
                args=(entry_key, rid),
            )
            if existing
            else None
        )
        proposed = st.number_input(
            "Proposed number of people",
            min_value=0,
            max_value=10000,
            value=entered.get("proposed"),
            step=1,
            key=entry_key + "_proposed",
            on_change=keep_headcount_entry,
            args=(entry_key, rid),
        )
        if st.button("Use these headcounts", key=prefix + "_legacy_apply", disabled=proposed is None):
            for row in rows:
                if row["id"] == rid:
                    row.update(
                        {
                            "Quantity basis": "headcount",
                            "Proposed quantity / FTE": proposed,
                            "Current quantity / FTE": current,
                        }
                    )
            commit_rows(plan, rows)
            plan.basis_drafts.pop("headcount_entry", None)
            st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
            st.rerun()
        if saved and st.button("Clear headcount update", key=prefix + "_legacy_clear"):
            plan.basis_drafts.pop("headcount_entry", None)
            st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
            st.rerun()


def keep_headcount_entry(key, rid):
    st.session_state.plan.basis_drafts["headcount_entry"] = {
        "role": rid,
        "current": st.session_state.get(key + "_current"),
        "proposed": st.session_state.get(key + "_proposed"),
    }


def deployment_review_table(plan):
    rows = comparison_rows(plan, common=False, include_pending=False)
    included = [
        row for row in rows if pd.notna(row["Proposed quantity / FTE"]) and row["Proposed quantity / FTE"] > 0
    ]
    key = f"six_{plan.id}_review_{st.session_state.get('six_epoch', 0)}_table"
    st.session_state.six_editor_key = key
    st.session_state[key + "_base"] = included
    frame = pd.DataFrame(
        included,
        columns=list(rows[0])
        if rows
        else [
            "id",
            "Role title",
            "Current quantity / FTE",
            "Proposed quantity / FTE",
            "Change",
            "Quantity basis",
            "Duties / deployment notes",
            "Deployment",
        ],
    )
    for column in ("Current quantity / FTE", "Proposed quantity / FTE", "Change"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    existing = plan.contract_kind == "existing contract"
    st.data_editor(
        frame,
        key=key,
        hide_index=True,
        width="stretch",
        placeholder="",
        row_height=50,
        disabled=["id", "Change"],
        on_change=editor_changed,
        args=(key,),
        column_config={
            "id": None,
            "Deployment": None,
            "Role title": st.column_config.TextColumn("Role", width="large"),
            "Current quantity / FTE": st.column_config.NumberColumn("Current deployment", min_value=0.0)
            if existing
            else None,
            "Proposed quantity / FTE": st.column_config.NumberColumn("Proposed deployment", min_value=0.0),
            "Quantity basis": st.column_config.TextColumn("Saved unit")
            if any(r["Quantity basis"] != "headcount" for r in rows)
            else None,
            "Change": st.column_config.NumberColumn("Change", format="%+.2f") if existing else None,
            "Duties / deployment notes": st.column_config.TextColumn("Operational rationale", width="large"),
        },
    )
    deployment_summary(rows, existing)
    excluded = [row for row in rows if row not in included]
    if excluded:
        with st.expander(f"Excluded or unanswered rows ({len(excluded)})"):
            st.dataframe(excluded, hide_index=True, column_config={"id": None})
    return rows


def validate_manpower(plan):
    if plan.contract_kind == "unspecified":
        raise ValueError("Choose Existing contract or New site / service above the manpower table.")
    rows = comparison_rows(plan, common=False, include_pending=False)
    validate_comparison(rows)
