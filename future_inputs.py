"""Explicit PWM salary path and tender-unit escalation choices with budget effects."""

import re
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from activity_nav import retained_key
from services.calculations import budget
from services.decision_basis import meaningful, record_basis
from services.models import PWMConfig
from services.pwm import catalog, get_schedule, validate_pwm
from services.workflow import apply_change

GROUPED_UI_VERSION = 12


def select_general_increase(prefix, percent, custom):
    """Change the preview only; applying and confirming remain explicit."""
    for field, value in (("percent", percent), ("exact", percent), ("custom", custom)):
        st.session_state[prefix + "_" + field] = value
    st.session_state.plan.basis_drafts.setdefault("common_future", {}).update(percent=percent, custom=custom)


def keep_future_mode(key, rid):
    st.session_state.plan.basis_drafts["future_mode_" + rid] = st.session_state[key]


def pwm_trade(role):
    """UI discovery only; a title never confirms worker eligibility."""
    title = role.label.casefold()
    if re.search(r"\b(cleaners?|cleaning)\b", title):
        return "cleaning"
    if re.search(r"\b(landscap(?:e|ing)|gardeners?|horticultur\w*)\b", title):
        return "landscape"
    if re.search(r"\bsecurity\b", title) and (
        title.strip() == "security"
        or re.search(r"\b(guards?|officers?|supervisors?|team|personnel)\b", title)
    ):
        return "security"
    if re.search(r"\b(lift|escalator)s?\b", title) and re.search(
        r"\b(technicians?|maintenance|mechanics?|engineers?|specialists?|team|crew)\b", title
    ):
        return "lift"
    return None


def pwm_trade_hints(role):
    labels = [role.label, *re.split(r"\s*(?:&|\band\b|\+)\s*", role.label, flags=re.I)]
    return {hint for label in labels if (hint := pwm_trade(SimpleNamespace(label=label)))}


def future_method_options(plan, role):
    options = (
        ["assumption", "PWM salary progression"] if pwm_trade(role) else ["assumption", "quoted schedule"]
    )
    recorded = "PWM salary progression" if role.pwm else role.escalation_mode
    pending = plan.basis_drafts.get("future_mode_" + role.id)
    for value in (recorded, pending):
        if value and value not in options:
            options.append(value)  # Preserve existing saved settings for explicit review.
    return options


def retain_individual_drafts():
    import ui_drafts
    from journey_inputs import pending_control_errors

    ui_drafts.capture(st.session_state.plan, pending_control_errors(st.session_state.plan))


def role_overrides(plan):
    roles = {r.id: r.label for r in plan.roles if r.included}
    existing = [
        r.id
        for r in plan.roles
        if r.included
        and (
            r.escalation_mode == "quoted schedule"
            or r.policies
            or len(set(r.escalation[1:])) > 1
            or "pwm_" + r.id in plan.basis_drafts
            or "future_mode_" + r.id in plan.basis_drafts
        )
    ]
    st.markdown("**Different arrangements for individual roles (optional)**")
    return st.multiselect(
        "Show only roles needing a different increase or quoted yearly prices",
        list(roles),
        default=existing,
        format_func=lambda rid: roles[rid],
        key=retained_key(f"future_overrides_{plan.id}"),
        on_change=retain_individual_drafts,
    )


PWM_FIELDS = (
    "schedule_id",
    "covered_quantity",
    "starting_salary",
    "salary_source",
    "applicability_basis",
    "applicability_confirmed",
    "rationale",
    "remainder_flat_confirmed",
    "oncost_percent",
    "oncost_source",
    "beyond_published",
    "beyond_percent",
    "beyond_reason",
)


def keep_pwm_draft(prefix, rid):
    saved = st.session_state.plan.basis_drafts.setdefault("pwm_" + rid, {})
    saved.update(
        {
            name: st.session_state[prefix + "_" + name]
            for name in PWM_FIELDS
            if prefix + "_" + name in st.session_state
        }
    )


def pwm_form(plan, role, officer, on_draft=None):
    c = role.pwm
    prefix = f"pwm_{plan.id}_{role.id}"
    saved = plan.basis_drafts.get("pwm_" + role.id, {})
    if st.session_state.pop(prefix + "_reset", False):
        for name in PWM_FIELDS:
            st.session_state.pop(prefix + "_" + name, None)

    def params(name):
        return dict(
            key=retained_key(prefix + "_" + name),
            on_change=on_draft or keep_pwm_draft,
            args=(prefix, role.id),
        )

    def prior(name, default=None):
        value = saved.get(name, getattr(c, name, default) if c else default)
        return default if value is None else value

    trades = pwm_trade_hints(role)
    schedules = [
        row
        for row in catalog()["schedules"]
        if not trades or row["sector"] in trades or row["id"] == prior("schedule_id")
    ]
    choices = {
        row["id"]: f"{row['sector']} · {row['category']} · {row['job_level']} · {row['wage_basis']}"
        for row in schedules
    }
    st.markdown("**1. Category and eligibility**")
    st.caption(
        "Supported dates: an exact first-of-month contract start and an explicit full-time headcount. Partial months and FTE conversions are not yet supported. Keep your actual contract dates; drafts remain saveable."
    )
    if plan.profile.start is None or plan.profile.start.day != 1 or role.quantity_unit != "headcount":
        st.info(
            "PWM projection is unavailable for the recorded date/unit. Preserve this draft and resolve the date or worker basis from evidence; do not substitute an invented date."
        )
        return
    st.caption(
        "Apply official schedule percentage movements to the supplied salary component using the owner's budgeting method. This does not claim every worker legally needs that percentage rise. No salary split, CPF, bonus or trade amount is inferred."
    )
    selected = st.selectbox(
        "Confirm applicable PWM category / job level",
        list(choices),
        index=list(choices).index(prior("schedule_id")) if prior("schedule_id") in choices else None,
        placeholder="Select the confirmed sector, category and job level",
        format_func=lambda sid: choices[sid],
        **params("schedule_id"),
    )
    if selected is None:
        st.caption(
            "Select the applicable schedule before entering a salary component. A role title alone does not establish eligibility."
        )
        return
    source_schedule = get_schedule(selected)
    st.link_button("Official MOM schedule and eligibility", source_schedule["source"])
    st.caption(
        f"Checked {source_schedule['verified_on']} · published through {source_schedule['valid_until']} · {source_schedule['wage_basis']} · monthly full-time schedule"
    )
    with st.expander("Published wages, effective dates and applicability limits"):
        published = []
        previous = None
        for point in source_schedule["points"]:
            published.append(
                {
                    **point,
                    "Movement from previous published point (%)": (point["wage"] / previous - 1) * 100
                    if previous
                    else None,
                }
            )
            previous = point["wage"]
        st.dataframe(published, hide_index=True, width="stretch")
        st.write(catalog()["limitations"])
    from datetime import date

    if plan.profile.start < date.fromisoformat(source_schedule["points"][0]["effective"]):
        st.info(
            "The actual contract starts before this retained schedule. Obtain the correct source; the current draft is preserved."
        )
        return
    eligibility = st.text_area(
        "PWM category / covered-worker details, if needed",
        value=prior(
            "applicability_basis",
            f"{source_schedule['category']} / {source_schedule['job_level']}; covered workers confirmed against official eligibility",
        ),
        **params("applicability_basis"),
    )
    eligible = st.checkbox(
        "Confirm this wage basis and eligibility apply to the covered workers",
        value=prior("applicability_confirmed", False),
        **params("applicability_confirmed"),
    )
    if not eligible:
        st.caption(
            "Confirm the category and worker eligibility to enter the salary basis. No eligibility is inferred from the title."
        )
        return
    st.markdown("**2. Salary component and covered workers**")
    covered = st.number_input(
        "Covered workers (headcount)",
        value=prior("covered_quantity", int(min([role.quantity, *role.yearly_quantities]))),
        min_value=1,
        max_value=10000,
        step=1,
        **params("covered_quantity"),
    )
    salary = st.number_input(
        "Salary component per covered worker at contract start (SGD)",
        value=prior("starting_salary"),
        min_value=0.01,
        step=1.0,
        **params("starting_salary"),
    )
    salary_source = st.text_input(
        "Salary component source / quotation", value=prior("salary_source", ""), **params("salary_source")
    )
    reason = prior(
        "rationale",
        "Apply published salary schedule movements to the confirmed salary component; retain the remaining inclusive charge unchanged.",
    )
    flat = st.checkbox(
        "Confirm the remaining inclusive charge stays flat; replace this role's general escalation with the salary-only method",
        value=prior("remainder_flat_confirmed", False),
        **params("remainder_flat_confirmed"),
    )
    oncost = st.number_input(
        "Separately evidenced employer on-cost rate on the salary increment (%)",
        value=prior("oncost_percent", c.oncost_rate * 100 if c else 0.0),
        min_value=0.0,
        max_value=100.0,
        **params("oncost_percent"),
    )
    st.caption("Zero models no incremental employer on-cost; it is not a statutory contribution rate.")
    oncost_source = (
        st.text_input(
            "Employer on-cost source (required for a non-zero rate)",
            value=prior("oncost_source", ""),
            **params("oncost_source"),
        )
        if oncost
        else prior("oncost_source", "")
    )
    from datetime import date, timedelta

    end = (
        plan.profile.costing_start.replace(year=plan.profile.costing_start.year + plan.profile.years)
        if plan.profile.costing_start
        else None
    )
    needs_tail = end and end > date.fromisoformat(source_schedule["valid_until"]) + timedelta(days=1)
    tail, tail_rate, tail_reason = (
        prior("beyond_published", "unselected"),
        prior("beyond_percent", c.beyond_rate * 100 if c else 0.0),
        prior("beyond_reason", ""),
    )
    if needs_tail:
        tails = ["unselected", "hold last salary", "officer annual assumption"]
        tail = st.selectbox(
            "Beyond the published period", tails, index=tails.index(tail), **params("beyond_published")
        )
        if tail == "officer annual assumption":
            tail_rate = st.number_input(
                "Unpublished-period annual assumption (%)",
                value=tail_rate,
                min_value=-50.0,
                max_value=100.0,
                **params("beyond_percent"),
            )
        tail_reason = st.text_area(
            "Basis for unpublished-period treatment", value=tail_reason, **params("beyond_reason")
        )
    values = dict(
        schedule_digest=source_schedule["digest"],
        schedule_id=selected,
        covered_quantity=covered,
        starting_salary=salary,
        salary_source=salary_source,
        applicability_basis=eligibility,
        applicability_confirmed=eligible,
        rationale=reason,
        remainder_flat_confirmed=flat,
        oncost_rate=oncost / 100,
        oncost_source=oncost_source,
        beyond_published=tail,
        beyond_rate=tail_rate / 100,
        beyond_reason=tail_reason,
    )
    st.caption(
        "Calendar months; confirm an exact first-of-month contract start. Unpublished assumptions start at the first unpublished schedule month and repeat annually. Draft edits are retained automatically; Save project persists them without applying or approving them."
    )
    st.markdown("**3. Review salary projection**")
    apply = st.button("Apply salary progression to this role", key=prefix + "_apply")
    if st.button("Revert PWM input draft", key=prefix + "_revert"):
        plan.basis_drafts.pop("pwm_" + role.id, None)
        st.session_state[prefix + "_reset"] = True
        st.rerun()
    if covered and salary:
        try:
            preview = plan.model_copy(deep=True)
            item = role.model_copy(deep=True)
            item.pwm = PWMConfig.model_validate(values)
            item.escalation, item.escalation_mode, item.schedule_id = (
                [0.0] * plan.profile.years,
                "assumption",
                None,
            )
            preview.roles = [item]
            estimate = budget(preview, [])
            st.metric(
                "Role contract cost with this salary proposal (SGD)", f"{estimate['contract_total']:,.2f}"
            )
            st.caption(
                f"Salary/on-cost increase versus flat inclusive starting charges: SGD {sum(row['pwm_cost'] for row in estimate['rows']):,.2f}"
            )
        except ValueError as error:
            if apply:
                st.info(str(error))
    if apply:
        try:
            if covered is None or salary is None:
                raise ValueError(
                    "Enter the covered worker headcount and the known salary component at contract start."
                )
            item = role.model_copy(deep=True)
            item.pwm = PWMConfig.model_validate(values)
            item.escalation, item.escalation_mode, item.schedule_id = (
                [0.0] * plan.profile.years,
                "assumption",
                None,
            )
            item.escalation_reason = reason
            validate_pwm(item, plan.profile)
            candidate = plan.model_copy(deep=True)
            apply_change(
                candidate,
                "role",
                item.model_dump(mode="json"),
                "Officer selected salary-only PWM method; general profile replaced explicitly",
                officer,
            )
            record_basis(
                candidate,
                "escalation",
                [role.id],
                "PWM salary progression",
                reason,
                source_schedule["source"] + "; salary source: " + salary_source,
                "officer assumption",
                officer,
            )
            candidate.basis_drafts.pop("pwm_" + role.id, None)
            candidate.basis_drafts.pop("future_mode_" + role.id, None)
            plan.__dict__.update(candidate.__dict__)
            st.rerun()
        except ValueError as error:
            st.info(str(error))


def tender_choices(plan, role, records, benchmark, officer):
    if not benchmark["available"]:
        return
    options = {
        "Median": benchmark["median"],
        "Average": benchmark["average"],
        "Higher reference (P75)": benchmark["p75"],
    }
    rows = []
    for label, value in options.items():
        sample = plan.model_copy(deep=True)
        sample.roles = [role.model_copy(deep=True)]
        r = sample.roles[0]
        r.pwm, r.policies, r.schedule_id = None, [], None
        r.escalation_mode, r.escalation = "assumption", [0.0] + [value] * (plan.profile.years - 1)
        try:
            result = budget(sample, records)
            flat = sum(row["flat_baseline"] for row in result["rows"])
            rows.append(
                {
                    "Choice": label,
                    "Annual change (%)": value * 100,
                    "Role contract cost (SGD)": result["contract_total"],
                    "Contract change from flat role rate (SGD)": round(result["contract_total"] - flat, 2),
                    "Base (SGD)": result["base_total"],
                    "Option (SGD)": result["option_total"],
                }
            )
        except ValueError:
            pass
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption(
            "Equal weight per distinct comparable manpower-only schedule: first compute its median consecutive-year unit-rate change, then summarise those medians. Higher means the 75th percentile, not a guaranteed safer allowance. These are quoted tender expectations, not realised inflation; component additions are excluded from this comparison."
        )
    chosen = st.selectbox(
        "Tender-derived reference or custom assumption",
        [*options, "Custom assumption"],
        index=3,
        key=retained_key(f"tender_choice_{plan.id}_{role.id}"),
    )
    if chosen in options and st.button("Select reference profile", key=f"tender_apply_{plan.id}_{role.id}"):
        payload = role.model_dump(mode="json")
        payload.update(
            pwm=None,
            escalation_mode="assumption",
            schedule_id=None,
            escalation=[0.0] + [options[chosen]] * (plan.profile.years - 1),
            escalation_reason="",
        )
        apply_change(
            plan, "role", payload, f"Officer selected {chosen} reference; rationale still required", officer
        )
        st.rerun()


def keep_common_draft(prefix):
    st.session_state.plan.basis_drafts["common_future"] = {
        field: st.session_state.get(prefix + "_" + field)
        for field in ("roles", "percent", "reason", "source")
    }


def shared_future_assumption(plan, officer):
    roles = {r.id: r.label for r in plan.roles if r.included and not r.pwm}
    if not roles:
        return
    saved = plan.basis_drafts.get("common_future", {})
    prefix = f"common_future_{plan.id}"
    if st.session_state.pop(prefix + "_reset", False):
        for field in ("roles", "percent", "reason", "source"):
            st.session_state.pop(prefix + "_" + field, None)
    defaults = [r.id for r in plan.roles if r.included and not r.pwm and r.escalation_mode == "assumption"]
    profiles = [r.escalation for r in plan.roles if r.id in defaults]
    uniform = (
        bool(profiles)
        and all(len(x) == plan.profile.years and len(set(x[1:])) <= 1 for x in profiles)
        and len({tuple(x) for x in profiles}) == 1
    )
    current = (profiles[0][1] * 100 if plan.profile.years > 1 else 0.0) if uniform else None

    def params(field):
        return dict(key=retained_key(prefix + "_" + field), on_change=keep_common_draft, args=(prefix,))

    st.markdown("### General annual allowance")
    st.write(
        "Set one annual increase for the FM team. Only add individual exceptions below when a role needs a different arrangement."
    )
    selected = st.multiselect(
        "Roles using this annual allowance",
        list(roles),
        default=[rid for rid in saved.get("roles", defaults) if rid in roles],
        format_func=lambda rid: roles[rid],
        **params("roles"),
    )
    value = st.number_input(
        "Annual increase (%) — enter 0 to keep prices unchanged",
        value=saved.get("percent", current),
        min_value=-50.0,
        max_value=100.0,
        step=0.1,
        **params("percent"),
    )
    reason = st.text_area(
        "Reason for this annual allowance",
        value=saved.get("reason", ""),
        placeholder="Explain the quotation or financial assumption supporting this increase for the selected roles.",
        **params("reason"),
    )
    source = st.text_input(
        "Quotation or reference, if available", value=saved.get("source", ""), **params("source")
    )
    st.caption(
        "Roles already using PWM salary progression are excluded. Applying this allowance replaces custom yearly increases or quoted prices for the selected roles; monthly starting allowances stay unchanged. Year 1 has no increase."
    )
    candidate = None
    if selected and value is not None:
        candidate = plan.model_copy(deep=True)
        for role in list(candidate.roles):
            if role.id in selected:
                payload = role.model_dump(mode="json")
                payload.update(
                    escalation=[0.0] + [value / 100] * (plan.profile.years - 1),
                    escalation_mode="assumption",
                    schedule_id=None,
                    escalation_reason=reason,
                )
                apply_change(candidate, "role", payload, "Officer applied general annual allowance", officer)
        try:
            from services.evidence import load_records

            estimate = budget(candidate, load_records())
            st.metric("Contract cost with this general allowance (SGD)", f"{estimate['contract_total']:,.2f}")
            st.caption(
                "Preview only. Apply below to record the allowance; confirmation remains a separate action."
            )
        except ValueError:
            pass
    apply, revert = st.columns([2, 1])
    if apply.button("Apply annual allowance to selected roles", key=prefix + "_apply", type="primary"):
        try:
            if candidate is None or not meaningful(reason):
                raise ValueError(
                    "Select the affected roles, enter the annual increase (including explicit 0), and explain its financial basis."
                )
            record_basis(
                candidate,
                "escalation",
                selected,
                "General annual allowance",
                reason,
                source,
                "sourced evidence" if source else "officer assumption",
                officer,
            )
            # The explicit replacement clears only annual/quote controls, preserving component drafts.
            original_controls = plan.basis_drafts.get("_ui_controls", {})
            policy_values = {
                key: value
                for key, value in original_controls.get("values", {}).items()
                if "_policy_" in key and any(key.startswith(f"esc_{plan.id}_{rid}_") for rid in selected)
            }
            if any(policy_values.values()):
                retained = candidate.basis_drafts.setdefault(
                    "_ui_controls", {"project_id": plan.id, "values": {}}
                )
                retained["values"].update(policy_values)
            candidate.basis_drafts.pop("common_future", None)
            for rid in selected:
                for suffix in (
                    "_model",
                    "_ui_draft_restored",
                    "_mode",
                    "_slider",
                    "_number",
                    "_yearly_text",
                    "_yearly_reason",
                ):
                    st.session_state.pop(f"esc_{plan.id}_{rid}" + suffix, None)
            plan.__dict__.update(candidate.__dict__)
            st.rerun()
        except ValueError as error:
            st.info(str(error))
    if "common_future" in plan.basis_drafts and revert.button(
        "Revert allowance draft", key=prefix + "_revert"
    ):
        plan.basis_drafts.pop("common_future", None)
        st.session_state[prefix + "_reset"] = True
        st.rerun()


def keep_group_draft(prefix):
    fields = (
        "roles",
        "percent",
        "reason",
        "source",
        "custom",
        "pwm_roles",
        "retain",
        "yearly_enabled",
        "yearly_text",
    )
    saved = st.session_state.plan.basis_drafts.setdefault("common_future", {})
    saved.update(
        {
            field: st.session_state[prefix + "_" + field]
            for field in fields
            if prefix + "_" + field in st.session_state
        }
    )


def keep_yearly_table(prefix, key, rows):
    edits = st.session_state.get(key, {}).get("edited_rows", {})
    for index, change in edits.items():
        if 0 <= int(index) < len(rows) and "Increase (%)" in change:
            rows[int(index)]["Increase (%)"] = change["Increase (%)"]
    values = [0.0] + [row["Increase (%)"] for row in rows]
    draft = st.session_state.plan.basis_drafts.setdefault("common_future", {})
    draft["yearly_values"] = values
    draft["yearly_text"] = ", ".join("" if x is None else str(x) for x in values)


def yearly_increase_table(plan, prefix, records):
    from services.future_groups import general_reference

    saved = plan.basis_drafts.setdefault("common_future", {})
    values = saved.get("yearly_values")
    if values is None and saved.get("yearly_text"):
        try:
            values = [float(x.strip()) for x in saved["yearly_text"].split(",")]
        except ValueError:
            values = []
    if values is None:
        profiles = [r.escalation for r in plan.roles if r.included and not r.pwm]
        if (
            profiles
            and all(len(x) == plan.profile.years for x in profiles)
            and len({tuple(x) for x in profiles}) == 1
        ):
            values = [round(x * 100, 2) for x in profiles[0]]
        else:
            chosen = saved.get("percent", st.session_state.get(prefix + "_percent"))
            if chosen is None:
                bm = general_reference(plan, records, [])
                chosen = round(bm["average"] * 100, 2) if bm["available"] else None
            values = [0.0] + [chosen] * (plan.profile.years - 1)
    if len(values) != plan.profile.years or values[0] != 0:
        st.warning(
            "The saved yearly profile does not match this contract. Enter the missing yearly percentages below; the original entries remain retained in the draft."
        )
        saved.setdefault("previous_yearly_entries", saved.get("yearly_text", values))
        values = [0.0] + [None] * (plan.profile.years - 1)
    st.caption("Year 1: 0% - confirmed starting rates. Enter increases for the later years below.")
    rows = [
        {
            "Contract year": year,
            "Period": "Base" if year <= plan.profile.base_years else "Option",
            "Increase (%)": values[year - 1],
        }
        for year in range(2, plan.profile.years + 1)
    ]
    frame = pd.DataFrame(rows, columns=["Contract year", "Period", "Increase (%)"])
    frame["Increase (%)"] = pd.to_numeric(frame["Increase (%)"], errors="coerce")
    key = prefix + "_yearly_table_" + str(plan.profile.years)
    edited = st.data_editor(
        frame,
        key=key,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        disabled=["Contract year", "Period"],
        column_config={
            "Increase (%)": st.column_config.NumberColumn(
                "Increase (%)", min_value=-50.0, max_value=100.0, step=0.01, format="%.2f"
            )
        },
        on_change=keep_yearly_table,
        args=(prefix, key, rows),
    )
    values = [0.0] + [float(x) if pd.notna(x) else None for x in edited["Increase (%)"]]
    saved["yearly_values"] = values
    saved["yearly_text"] = ", ".join("" if x is None else f"{x:g}" for x in values)
    return values


def future_screen(plan, records, officer, save):
    from hybrid_inputs import confirmation_errors, show_missing
    from services.future_groups import general_proposal, general_reference, impact
    from services.workflow import confirm

    migration_key = f"grouped_future_migrated_{plan.id}"
    if not st.session_state.get(migration_key):
        import ui_drafts
        from journey_inputs import pending_control_errors

        ui_drafts.capture(plan, pending_control_errors(plan))
        st.session_state[migration_key] = True
    prefix = f"common_future_{plan.id}"
    if st.session_state.pop(prefix + "_group_reset", False):
        st.session_state.pop(prefix + "_pwm_roles", None)
    saved = plan.basis_drafts.get("common_future", {})
    roles = {r.id: r for r in plan.roles if r.included}
    hints = [rid for rid, r in roles.items() if pwm_trade_hints(r) or r.pwm]
    pwm_ids = [rid for rid in saved.get("pwm_roles", hints) or [] if rid in roles]
    # Active PWM cannot be silently removed through a grouping correction.
    pwm_ids = list(dict.fromkeys(pwm_ids + [r.id for r in roles.values() if r.pwm]))
    legacy = [
        r.id
        for r in roles.values()
        if not r.pwm
        and (r.escalation_mode == "quoted schedule" or r.policies or len(set(r.escalation[1:])) > 1)
    ]

    def params(field):
        return dict(key=retained_key(prefix + "_" + field), on_change=keep_group_draft, args=(prefix,))

    active = [r.id for r in roles.values() if r.pwm]
    # A suggested title is not an assignment or eligibility confirmation.
    pwm_ids = list(
        dict.fromkeys([rid for rid in saved.get("pwm_roles", active) or [] if rid in roles] + active)
    )
    st.markdown("### Annual manpower cost increase")
    annual_controls = st.container()
    retain = True if legacy else False
    yearly_enabled, yearly_text, yearly_values = False, "", None
    with st.expander("Use different increases by year"):
        if legacy:
            st.caption(
                "Saved yearly prices/profiles and component adjustments are retained. Replacing a profile requires an explicit choice; component adjustments remain subject to overlap review."
            )
            st.dataframe(
                [
                    {
                        "Role": roles[rid].label,
                        "Yearly increases (%)": [x * 100 for x in roles[rid].escalation],
                        "Quoted schedule": roles[rid].schedule_id,
                    }
                    for rid in legacy
                ],
                hide_index=True,
            )
            retain = st.checkbox(
                "Keep saved yearly profiles and special arrangements",
                value=saved.get("retain", True) if saved.get("retain") is not None else True,
                **params("retain"),
            )
        yearly_enabled = st.checkbox(
            "Use different increases by year",
            value=bool(saved.get("yearly_enabled")),
            **params("yearly_enabled"),
        )
        if yearly_enabled:
            yearly_values = yearly_increase_table(plan, prefix, records)
            yearly_text = ", ".join("Unanswered" if x is None else f"{x:g}" for x in yearly_values)
    general = [rid for rid in roles if rid not in pwm_ids and (not retain or rid not in legacy)]
    st.markdown("**Applicable manpower**")
    st.dataframe(
        [
            {
                "Manpower": roles[rid].label,
                "Quantity": roles[rid].quantity,
                "Unit": roles[rid].quantity_unit,
            }
            for rid in general
        ],
        hide_index=True,
        width="stretch",
    )
    candidate, proposal_error = plan.model_copy(deep=True), None
    value, reason, source, custom = None, "", "", False
    with annual_controls:
        if general and plan.profile.years > 1:
            bm = general_reference(plan, records, general)
            profiles = [roles[rid].escalation for rid in general]
            uniform = (
                all(len(x) == plan.profile.years and len(set(x[1:])) <= 1 for x in profiles)
                and len({tuple(x) for x in profiles}) == 1
            )
            current = profiles[0][1] * 100 if uniform else None
            current_basis = next(
                (
                    b
                    for b in reversed(plan.decision_bases)
                    if b.kind == "escalation" and set(general).issubset(b.role_ids)
                ),
                None,
            )
            prior_custom = bool(
                current_basis and current_basis.category != "Comparable database reference"
            ) or (current is not None and not current_basis)
            if (
                current is not None
                and bm["available"]
                and not (round(bm["minimum"] * 100, 2) <= current <= round(bm["maximum"] * 100, 2))
            ):
                prior_custom = True
            if bm["available"]:
                if current == 0 and not yearly_enabled:
                    st.info(
                        "Your saved budget uses 0% annual increase. Keep it if intentional, "
                        "or preview the recommended average below. Your saved budget stays unchanged until confirmation."
                    )
                    recommended, keep_zero = st.columns(2)
                    recommended.button(
                        f"Use recommended average ({bm['average'] * 100:.2f}%)",
                        key=prefix + "_use_average",
                        on_click=select_general_increase,
                        args=(prefix, round(bm["average"] * 100, 2), False),
                    )
                    keep_zero.button(
                        "Keep 0%",
                        key=prefix + "_keep_zero",
                        on_click=select_general_increase,
                        args=(prefix, 0.0, True),
                    )
                a, b, c = st.columns(3)
                a.metric("Recommended database average", f"{bm['average'] * 100:.2f}%")
                b.metric("Lower allowance", f"{bm['minimum'] * 100:.2f}%")
                c.metric("Higher allowance", f"{bm['maximum'] * 100:.2f}%")
                st.caption(
                    f"Observed minimum and maximum from {bm['sample_count']} distinct awarded Office FM manpower schedules. Based on unit-rate movements within each quoted schedule, excluding quantity changes. Synthetic references do not measure historical wage trends."
                )
                custom = st.checkbox(
                    "Use another percentage",
                    value=bool(saved.get("custom", prior_custom)),
                    disabled=yearly_enabled,
                    **params("custom"),
                )
            else:
                custom = True
                st.info(
                    "Valid general manpower reference evidence is unavailable (fewer than three comparable schedules). Enter an officer assumption; no average or range is invented."
                )
            default = saved.get("percent")
            if default is None:
                default = (
                    current
                    if current is not None
                    else round(bm["average"] * 100, 2)
                    if bm["available"]
                    else None
                )

            def synced(field):
                st.session_state[prefix + "_percent"] = st.session_state[prefix + "_" + field]
                st.session_state[prefix + "_exact"] = st.session_state[prefix + "_percent"]
                keep_group_draft(prefix)

            if not custom:
                low, high = round(bm["minimum"] * 100, 2), round(bm["maximum"] * 100, 2)
                default = round(default if low <= default <= high else bm["average"] * 100, 2)
                if (
                    st.session_state.get(prefix + "_percent") is None
                    or not low <= st.session_state[prefix + "_percent"] <= high
                ):
                    st.session_state[prefix + "_percent"] = default
                st.session_state[prefix + "_exact"] = st.session_state[prefix + "_percent"]
                if low < high:
                    st.slider(
                        "Annual manpower cost increase within observed range (%)",
                        min_value=low,
                        max_value=high,
                        value=None,
                        step=0.01,
                        format="%.2f%%",
                        key=retained_key(prefix + "_percent"),
                        on_change=synced,
                        args=("percent",),
                        disabled=yearly_enabled,
                    )
                    position = 100 * (bm["average"] * 100 - low) / (high - low)
                    st.markdown(
                        f'<div style="position:relative;height:24px"><span style="position:absolute;left:{max(0, min(95, position)):.2f}%;font-size:0.8rem">&#9670; average</span></div>',
                        unsafe_allow_html=True,
                    )
                st.number_input(
                    "Selected annual manpower cost increase (%)",
                    min_value=low,
                    max_value=high if low < high else None,
                    step=0.01,
                    key=retained_key(prefix + "_exact"),
                    on_change=synced,
                    args=("exact",),
                    disabled=yearly_enabled,
                )
                value = st.session_state[prefix + "_percent"]
            else:
                value = st.number_input(
                    "Annual manpower cost increase (%)",
                    value=default,
                    min_value=-50.0,
                    max_value=100.0,
                    step=0.01,
                    disabled=yearly_enabled,
                    **params("percent"),
                )
            if custom or yearly_enabled:
                if yearly_enabled:
                    st.caption("Using the yearly table below; the constant-percentage controls are inactive.")
                prior_note = (
                    current_basis.snapshots.get(general[0], {}).get(
                        "optional_note", current_basis.explanation
                    )
                    if current_basis
                    else roles[general[0]].escalation_reason
                )
                reason = st.text_area(
                    "Alignment note (optional)", value=saved.get("reason") or prior_note, **params("reason")
                )
                source = st.text_input(
                    "Document reference (optional)",
                    value=saved.get("source")
                    or (current_basis.source if current_basis and prior_custom else ""),
                    **params("source"),
                )
                st.caption(
                    "A note or document can support an alignment check. Without one, the selection remains an unverified officer-entered assumption; it does not block confirmation."
                )
            st.caption(
                "The selected yearly percentages compound from Year 2 to the end of the contract."
                if yearly_enabled
                else "The selected percentage compounds annually from Year 2 to the end of the contract."
            )
            if not yearly_enabled:
                if value is None:
                    st.info(
                        "Annual increase is unanswered. Enter a percentage, including 0% if you intend to keep unit rates flat."
                    )
                elif value == 0:
                    st.info(
                        "0% selected: general manpower unit rates stay at their starting rates. Deployment changes, PWM and other recorded adjustments remain separate."
                    )
            try:
                yearly = yearly_values if yearly_enabled else None
                if yearly is not None:
                    missing = [
                        f"Year {i + 1}: enter an increase or explicit zero."
                        for i, x in enumerate(yearly)
                        if x is None
                    ]
                    if missing:
                        raise ValueError(" ".join(missing))
                candidate = general_proposal(
                    plan, records, general, value, reason, source, not custom, officer, yearly_percent=yearly
                )
            except ValueError as error:
                proposal_error = str(error)
        elif general:
            st.info(
                "One contract year: starting monthly charges are retained; no anniversary increase is needed."
            )
            candidate = general_proposal(plan, records, general, 0.0, "", "", False, officer)
    st.markdown("### PWM salary progression")
    if not active:
        st.caption("No workers are assigned to PWM salary progression.")
    st.caption(
        "For covered cleaning, security, landscape and lift/escalator workers. Confirm eligibility and the known salary component before applying PWM."
    )
    with st.container(border=True):
        choices = list(dict.fromkeys(hints + active))
        if choices:
            chosen = st.multiselect(
                "Workers to check for PWM coverage",
                choices,
                default=[rid for rid in pwm_ids if rid in choices],
                format_func=lambda rid: roles[rid].label,
                **params("pwm_roles"),
            )
            if set(chosen + active) != set(pwm_ids):
                st.rerun()
            st.caption(
                "A title suggests a trade only. Confirm eligibility and category before applying salary progression. Recorded PWM stays active until explicitly replaced below."
            )
        else:
            st.caption(
                "No relevant trade workers are in this deployment. Add the applicable trade workers in deployment to set up PWM; general FM and Technician titles do not establish coverage."
            )
        if not choices and st.button(
            "Edit deployment to add PWM workers", key=f"future_edit_pwm_deployment_{plan.id}"
        ):
            plan.ui_step = 1
            st.rerun()
        for rid in pwm_ids:
            if not roles[rid].pwm:
                st.markdown("**Check eligibility: " + roles[rid].label + "**")
                pwm_form(plan, roles[rid], officer)
        for rid, role in roles.items():
            if "pwm_" + rid in plan.basis_drafts:
                if st.button(
                    "Revert unfinished PWM draft for " + role.label, key=f"future_revert_pwm_{plan.id}_{rid}"
                ):
                    plan.basis_drafts.pop("pwm_" + rid, None)
                    st.session_state[f"pwm_{plan.id}_{rid}_reset"] = True
                    st.rerun()
    if active:
        st.caption(
            "Title matches suggest trades only. Confirm the category and covered workers, then the known salary component. Calendar months are used; general escalation is not added to the PWM component."
        )

        def sector_for(rid):
            item = roles[rid]
            return (
                get_schedule(item.pwm.schedule_id)["sector"]
                if item.pwm
                else "/".join(sorted(pwm_trade_hints(item))) or "Confirm category"
            )

        last_sector = None
        for rid in sorted(active, key=sector_for):
            sector = sector_for(rid)
            if sector != last_sector:
                st.markdown(
                    "#### "
                    + {
                        "cleaning": "Cleaning",
                        "security": "Security",
                        "landscape": "Landscape",
                        "lift": "Lift/escalator maintenance",
                    }.get(sector, sector)
                )
                last_sector = sector
            role = roles[rid]
            st.markdown(f"**{role.label} · {role.quantity:g} {role.quantity_unit} confirmed**")
            if role.pwm:
                schedule = get_schedule(role.pwm.schedule_id)
                st.dataframe(
                    [
                        {
                            "Category": schedule["category"],
                            "Job level": schedule["job_level"],
                            "Covered workers": role.pwm.covered_quantity,
                            "Starting salary component (SGD)": role.pwm.starting_salary,
                            "Source": schedule["source"],
                            "Published through": schedule["valid_until"],
                        }
                    ],
                    hide_index=True,
                    width="stretch",
                )
                st.caption(
                    "Recorded PWM salary movements; remaining inclusive charges and uncovered workers stay flat. A separate supported deployment row is needed for a different increase; no salary split is inferred."
                )
                try:
                    validate_pwm(role, plan.profile)
                    needs_review = False
                except ValueError:
                    needs_review = True
                with st.expander(
                    "Review or change the recorded PWM setup",
                    expanded=needs_review or "pwm_" + rid in plan.basis_drafts,
                ):
                    pwm_form(plan, role, officer)
            else:
                pwm_form(plan, role, officer)
            if role.pwm and st.button(
                "Move this row to the general increase group", key=f"future_move_{plan.id}_{rid}"
            ):
                payload = role.model_dump(mode="json")
                payload.update(pwm=None, escalation=[], escalation_reason="")
                apply_change(
                    plan,
                    "role",
                    payload,
                    "Officer explicitly replaced PWM grouping; new annual assumption awaiting confirmation",
                    officer,
                )
                group_draft = plan.basis_drafts.setdefault("common_future", {})
                group_draft["pwm_roles"] = [item for item in pwm_ids if item != rid]
                plan.basis_drafts.pop("pwm_" + rid, None)
                st.session_state[prefix + "_group_reset"] = True
                st.rerun()
    retained_inputs = {
        key: value
        for key, value in plan.basis_drafts.items()
        if key in ("escalation", "policy")
        or (
            key.startswith("future_mode_")
            and (
                key.removeprefix("future_mode_") not in roles
                or value
                != (
                    "PWM salary progression"
                    if roles[key.removeprefix("future_mode_")].pwm
                    else roles[key.removeprefix("future_mode_")].escalation_mode
                )
            )
        )
    }
    old_controls = plan.basis_drafts.get("_ui_controls", {})
    future_controls = {
        key: value
        for key, value in old_controls.get("values", {}).items()
        if key.startswith(f"esc_{plan.id}_")
    }
    if future_controls:
        retained_inputs["_ui_controls"] = future_controls
    if retained_inputs:
        with st.expander("Retained unfinished inputs from the earlier layout", expanded=True):
            st.write(
                "These saved edits are separate from the recorded assumptions. Keep them for review, or explicitly return to the recorded values before using the new grouped preview."
            )
            st.dataframe(
                [
                    {
                        "Saved future input": key.replace("future_mode_", "Future method: ").replace(
                            "_ui_controls", "Unapplied yearly/component entries"
                        ),
                        "Retained draft": str(value),
                    }
                    for key, value in retained_inputs.items()
                ],
                hide_index=True,
                width="stretch",
            )
            if st.button(
                "Keep recorded values instead of these unfinished inputs",
                key=f"future_clear_legacy_{plan.id}",
            ):
                plan.history.append(
                    {
                        "action": "Officer discarded unfinished legacy future inputs",
                        "version": plan.version,
                        "officer": officer,
                        "retained_inputs": retained_inputs,
                    }
                )
                for key in retained_inputs:
                    if key == "_ui_controls":
                        for control in future_controls:
                            old_controls["values"].pop(control, None)
                        if not old_controls["values"]:
                            plan.basis_drafts.pop(key, None)
                    else:
                        plan.basis_drafts.pop(key, None)
                for key in list(st.session_state):
                    if key.startswith(f"esc_{plan.id}_"):
                        del st.session_state[key]
                st.rerun()
    if retain and legacy:
        from decision_inputs import basis_panel

        with st.expander("Review bases for saved special arrangements"):
            basis_panel(plan, "escalation", records)
            basis_panel(plan, "policy", records)
    # PWM apply reruns the screen. General preview uses the currently recorded PWM settings.
    st.markdown("### Contract cost impact")
    if "escalation" in plan.confirmations:
        st.success(
            f"Recorded future assumptions confirmed at plan version {plan.confirmations['escalation']}. Preview edits require renewed confirmation."
        )
    try:
        recorded = impact(plan, records)
    except ValueError:
        recorded = None
    try:
        preview = impact(candidate, records) if not proposal_error else None
    except ValueError as error:
        preview = None
        proposal_error = str(error)
    if preview:
        st.caption("Preview awaiting officer confirmation")
        if general:
            st.write(
                "Selected general manpower increases: " + yearly_text + "."
                if yearly_enabled
                else f"Selected annual manpower cost increase: {value if value is not None else 0:g}% from Year 2, compounded annually."
            )
        if retain and legacy:
            st.caption(
                "Saved yearly arrangements retained for: " + ", ".join(roles[rid].label for rid in legacy)
            )
        if pwm_ids:
            st.caption("Separate PWM salary progression: " + ", ".join(roles[rid].label for rid in pwm_ids))
        a, b, c = st.columns(3)
        for column, label in ((a, "Contract"), (b, "Base"), (c, "Option")):
            column.metric(label + " (SGD)", f"{preview[label]:,.2f}")
        st.caption(
            f"Future cost change from flat starting charges: SGD {preview['Change from flat starting charges']:,.2f}."
        )
        if recorded:
            st.metric(
                "Change from recorded contract budget (SGD)",
                f"{preview['Contract'] - recorded['Contract']:,.2f}",
            )
        st.caption(
            "Starting charges and quantities are unchanged. Saving preserves the draft; this preview does not approve it."
        )
        with st.expander("Yearly calculations and selected methods"):
            if general:
                selected_percent = value if plan.profile.years > 1 else 0.0
                selected_basis = (
                    "officer assumption"
                    if custom
                    else "supported reference"
                    if plan.profile.years > 1
                    else "single-year starting charges"
                )
                st.write(
                    f"Annual manpower cost increases: {yearly_text if yearly_enabled else str(selected_percent) + '%'}; {selected_basis}; "
                    + ", ".join(roles[rid].label for rid in general)
                )
            if recorded:
                st.dataframe(
                    [{"State": "Recorded", **recorded}, {"State": "Preview", **preview}],
                    hide_index=True,
                    width="stretch",
                )
            st.dataframe(
                [
                    {
                        k: row[k]
                        for k in (
                            "role_id",
                            "role",
                            "year",
                            "quantity",
                            "monthly_unit_rate",
                            "policy_cost",
                            "pwm_cost",
                            "annual_cost",
                        )
                    }
                    for row in budget(candidate, records)["rows"]
                ],
                hide_index=True,
                width="stretch",
            )
    # Do not lose legacy pending controls or silently approve unfinished PWM setup.
    errors = [proposal_error] if proposal_error else []
    if retained_inputs:
        errors.append(
            "Review the retained unfinished inputs above, or explicitly keep the recorded values before confirming the grouped preview."
        )
    errors += [
        f"{roles[rid].label}: complete PWM-specific setup, or move this row to the general group."
        for rid in pwm_ids
        if not roles[rid].pwm
    ]
    candidate.basis_drafts.pop("common_future", None)
    if not errors:
        errors += confirmation_errors(candidate, officer, records, gate="escalation")
    show_missing(list(dict.fromkeys(errors)))
    if st.button(
        "Confirm future cost assumptions and continue",
        key="confirm_escalation",
        type="primary",
        disabled=bool(errors),
    ):
        try:
            confirm(candidate, "escalation", officer, records)
            candidate.ui_step = 5
            plan.__dict__.update(candidate.__dict__)
            save()
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    st.caption(
        "Confirmation records the displayed groups, percentages, periods and sources. Later relevant changes invalidate affected confirmations."
    )
