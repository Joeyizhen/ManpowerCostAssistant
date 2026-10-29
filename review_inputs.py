"""Supporting final calculations are inspectable without overwhelming the handover."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from activity_nav import retained_key
from services.calculations import D, budget, cents
from services.evidence import rate_benchmark

COMPONENTS = {
    "Annual manpower increases": "#147D74",
    "PWM salary progression": "#8164B7",
    "Quoted future-price changes": "#4288B5",
    "Other component adjustments": "#B77625",
}


def cost_components(plan, result):
    modes = {r.id: r.escalation_mode for r in plan.roles}
    annual = []
    for year, total in enumerate(result["annual_totals"], 1):
        rows = [r for r in result["rows"] if r["year"] == year]
        general = [r for r in rows if modes[r["role_id"]] != "quoted schedule"]
        quoted = [r for r in rows if modes[r["role_id"]] == "quoted schedule"]
        item = {
            "Contract year": f"Year {year}" + (" (option)" if year > plan.profile.base_years else " (base)"),
            "Starting charges": cents(sum((D(r["flat_baseline"]) for r in rows), D(0))),
            "Annual manpower increases": cents(
                sum((D(r["annual_before_policy"]) - D(r["flat_baseline"]) for r in general), D(0))
            ),
            "PWM salary progression": cents(sum((D(r["pwm_cost"]) for r in rows), D(0))),
            "Quoted future-price changes": cents(
                sum((D(r["annual_before_policy"]) - D(r["flat_baseline"]) for r in quoted), D(0))
            ),
            "Other component adjustments": cents(sum((D(r["policy_cost"]) for r in rows), D(0))),
            "Total": total,
        }
        if cents(sum((D(item[k]) for k in ["Starting charges", *COMPONENTS]), D(0))) != total:
            raise ArithmeticError("Cost components do not reconcile with the annual budget")
        annual.append(item)
    totals = {
        k: cents(sum((D(row[k]) for row in annual), D(0))) for k in ["Starting charges", *COMPONENTS, "Total"]
    }
    if totals["Total"] != result["contract_total"]:
        raise ArithmeticError("Cost components do not reconcile with the contract budget")
    return annual, totals


def cost_comparison(plan, result):
    annual, totals = cost_components(plan, result)
    shown = [
        k for k in COMPONENTS if k in ("Annual manpower increases", "PWM salary progression") or totals[k]
    ]
    st.markdown("**What adds to the contract cost?**")
    st.caption(
        f"Starting charges: SGD {totals['Starting charges']:,.2f}. Changes below bring the full contract to SGD {totals['Total']:,.2f}."
    )
    if any(totals[k] for k in shown):
        chart = go.Figure(
            go.Bar(
                y=shown,
                x=[totals[k] for k in shown],
                orientation="h",
                marker_color=[COMPONENTS[k] for k in shown],
                text=[f"SGD {totals[k]:,.2f}" for k in shown],
                textposition="auto",
                hovertemplate="%{y}<br>SGD %{x:,.2f}<extra></extra>",
            )
        )
        chart.update_layout(
            height=180 + 38 * len(shown),
            margin=dict(l=10, r=20, t=15, b=35),
            xaxis_title="Additional cost over the full contract (SGD)",
            yaxis=dict(autorange="reversed"),
            showlegend=False,
        )
        st.plotly_chart(chart, width="stretch", key="contract_cost_causes")
    else:
        st.info(
            "No additional cost from annual increases or PWM is included. The contract retains the starting charges."
        )
    st.caption(
        "Annual manpower increases are the selected budgeting allowance, not measured inflation. PWM includes salary progression and any recorded incremental employer on-cost. Starting charges use the confirmed quantities for each year."
    )
    if any(totals[k] < 0 for k in shown):
        st.caption("Negative amounts are cost reductions.")
    with st.expander("Compare costs by year"):
        yearly = go.Figure()
        for label, colour in {"Starting charges": "#B6C5CE", **{k: COMPONENTS[k] for k in shown}}.items():
            yearly.add_bar(
                name=label,
                x=[r["Contract year"] for r in annual],
                y=[r[label] for r in annual],
                marker_color=colour,
                hovertemplate="%{x}<br>" + label + ": SGD %{y:,.2f}<extra></extra>",
            )
        yearly.update_layout(
            barmode="relative",
            height=390,
            margin=dict(l=10, r=15, t=15, b=90),
            yaxis_title="Annual cost (SGD)",
            legend=dict(orientation="h", y=-0.25),
            hovermode="x unified",
        )
        st.plotly_chart(yearly, width="stretch", key="yearly_cost_composition")
        st.dataframe(
            pd.DataFrame(annual)[["Contract year", "Starting charges", *shown, "Total"]],
            hide_index=True,
            width="stretch",
            column_config={
                k: st.column_config.NumberColumn(format="%.2f") for k in ["Starting charges", *shown, "Total"]
            },
        )
        st.caption(
            "Each year's starting charges plus the displayed changes equal its total. Quoted future-price differences and other evidenced adjustments are shown separately when present."
        )


def budget_details(plan, records):
    try:
        result = budget(plan, records)
        frame = pd.DataFrame(result["rows"])
        wide = frame.pivot(index=["role_id", "role"], columns="year", values="annual_cost")
        wide.columns = [
            f"Year {y}" + (" (option)" if y > plan.profile.base_years else "") for y in wide.columns
        ]
        wide["Contract total"] = wide.sum(axis=1).round(2)
        st.dataframe(
            wide,
            width="stretch",
            column_config={col: st.column_config.NumberColumn(format="%.2f") for col in wide.columns},
        )
        with st.expander("Annual calculations, assumptions and exclusions"):
            st.dataframe(frame, hide_index=True, width="stretch")
            st.caption(result["rounding"])
            st.caption(result["period_basis"])
            st.write("Excluded costs: " + plan.profile.exclusions)
        with st.expander("Supporting rate evidence and limitations"):
            rows = []
            for role in plan.roles:
                if role.included:
                    bm = rate_benchmark(
                        records,
                        role.mapped_role,
                        role.benchmark_year,
                        role.benchmark_status,
                        role.benchmark_scope,
                    )
                    rows.append(
                        {
                            "Role ID": role.id,
                            "Role": role.label,
                            "Reference year": role.benchmark_year,
                            "Allowance origin": role.rate_origin,
                            "Sample support": bm["sample_count"],
                            "Sources": ", ".join(r["record_id"] for r in bm["records"]),
                            "Limitations": bm["limitations"],
                        }
                    )
            st.dataframe(rows, hide_index=True, width="stretch")
    except ValueError as error:
        st.error(str(error))
        st.info(
            "Correct the invalid calculation inputs before exporting a numeric budget. The project snapshot remains available."
        )


FINAL_REVIEW_UI_VERSION = 20


def results_style():
    st.markdown(
        "<style>[data-testid='stMetricLabel'] p {white-space:normal; overflow:visible;} "
        "[data-testid='stMetricValue'] {font-size:clamp(1.1rem,2.4vw,2rem);}</style>",
        unsafe_allow_html=True,
    )


def go_to_step(plan, step):
    import ui_drafts
    from journey_inputs import pending_control_errors

    ui_drafts.capture(plan, pending_control_errors(plan))
    plan.ui_step = step
    st.rerun()


def annual_review(plan, result):
    from services.final_review import annual_breakdown, headcount_comparison

    rows, movements = annual_breakdown(plan, result)
    comparison = headcount_comparison(plan, result)
    baseline = "Starting-rate manpower cost"
    general = "Compounded annual manpower increase"
    if comparison["available"]:
        baseline = "Current headcount at starting rates"
        general = "General annual increase"
        rows = [
            {**item, **{k: v for k, v in old.items() if k.startswith("Change from previous")}}
            for item, old in zip(comparison["rows"], rows, strict=True)
        ]
        a, b, c = st.columns(3)
        a.metric("Year 0 comparison (SGD/year)", f"{comparison['baseline']:,.2f}")
        b.metric("Average budget (SGD/year)", f"{comparison['average']:,.2f}")
        c.metric(
            "Average change (SGD/year)",
            f"{comparison['increase']:+,.2f}",
            f"{comparison['increase_percent']:+.2f}%" if comparison["increase_percent"] is not None else None,
            delta_color="off",
        )
        st.caption(
            "Year 0 = current headcount × selected starting rates × 12; a comparison, not actual previous contract spending."
        )
    elif plan.contract_kind == "existing contract":
        st.caption(comparison["reason"])
    fields = [baseline]
    if comparison["available"] and any(r["Headcount change"] for r in rows):
        fields.append("Headcount change")
    if any(r[general] for r in rows):
        fields.append(general)
    if any(r["PWM increase"] for r in rows):
        fields.append("PWM increase")
    if any(r["Other adjustments"] for r in rows):
        fields.append("Other adjustments")
    chart = go.Figure()
    chart_rows = rows
    if comparison["available"]:
        chart_rows = [
            {
                "Contract year": "Year 0 (current)",
                **{f: comparison["baseline"] if f == baseline else 0 for f in fields},
            },
            *rows,
        ]
    colors = {
        baseline: "#9AAEBF",
        "Headcount change": "#4288B5",
        general: "#147D74",
        "PWM increase": "#8164B7",
        "Other adjustments": "#B77625",
    }
    for field in fields:
        chart.add_bar(
            name="Accumulated general increase"
            if field == general
            else ("Current headcount cost" if comparison["available"] else "Starting-rate cost")
            if field == baseline
            else field,
            x=[r["Contract year"] for r in chart_rows],
            y=[r[field] for r in chart_rows],
            marker_color=colors[field],
            hovertemplate="%{x}<br>SGD %{y:,.2f}<extra>%{fullData.name}</extra>",
        )
    if comparison["available"] and any(r["Headcount change"] < 0 for r in rows):
        chart.add_scatter(
            name="Annual total",
            x=[r["Contract year"] for r in rows],
            y=[r["Annual total"] for r in rows],
            mode="markers",
            marker=dict(color="#172B42", symbol="diamond", size=8),
            hovertemplate="%{x}<br>Total SGD %{y:,.2f}<extra></extra>",
        )
    chart.update_layout(
        barmode="relative",
        height=340,
        yaxis_title="Annual manpower cost (SGD)",
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=10, r=10, t=10, b=80),
    )
    st.plotly_chart(chart, width="stretch", key="annual_budget_breakdown")
    if comparison["available"]:
        st.markdown("**What drives the increase?**")
        st.dataframe(
            comparison["impacts"],
            hide_index=True,
            width="stretch",
            column_config={
                "Average change per year (SGD)": st.column_config.NumberColumn(format="accounting"),
                "Share of increase (%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )
        st.caption(
            "Percentages show shares of the net increase over Year 0. Price changes apply to proposed headcount; negative amounts are reductions."
        )
    st.dataframe(
        pd.DataFrame(rows).rename(
            columns={
                "Starting-rate manpower cost": "Starting-rate cost",
                "Compounded annual manpower increase": "Accumulated general increase",
                "Total annual manpower cost": "Annual total",
                "Change from previous year (SGD)": "Change from prior year (SGD)",
                "Change from previous year (%)": "Change from prior year (%)",
            }
        ),
        hide_index=True,
        width="stretch",
        column_config={
            key: st.column_config.NumberColumn(format="accounting")
            for key in [
                "Starting-rate cost",
                "Current headcount at starting rates",
                "Headcount change",
                "General annual increase",
                "Accumulated general increase",
                "PWM increase",
                "Other adjustments",
                "Annual total",
                "Change from prior year (SGD)",
            ]
        },
    )
    if not comparison["available"]:
        st.caption(
            "Starting-rate cost values each year's deployment at confirmed starting rates. General/PWM increases are accumulated additions to that baseline; the prior-year change is the difference between annual totals. Components reconcile to the budget."
        )
    if movements and any(r["Deployment change at starting rates"] for r in movements):
        with st.expander("Explain changes in yearly deployment"):
            st.dataframe(movements, hide_index=True, width="stretch")


def sensitivity_review(plan, records, on_edit=None):
    from services.final_review import sensitivity_rows

    rows, profiles = sensitivity_rows(plan, records)
    if not rows:
        st.info(
            "No future costs are affected by the general annual manpower increase. Quoted prices, PWM salary paths and fixed adjustments remain unchanged, so no three-way scenario comparison is shown."
        )
        return
    st.caption(
        "Lower/higher: minus/plus 1 percentage point from Year 2. Deployment, starting rates, quoted prices, PWM and fixed adjustments stay fixed. Your selected assumptions are unchanged."
    )
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config={
            "Full contract budget": st.column_config.NumberColumn(format="accounting"),
            "Difference from selected (SGD)": st.column_config.NumberColumn(format="accounting"),
        },
    )
    if on_edit is None:
        from services.scenario_selection import adopt_scenario

        lower, higher = st.columns(2)
        for column, label, delta, row in [
            (lower, "Adopt lower scenario", -0.01, rows[0]),
            (higher, "Adopt higher scenario", 0.01, rows[2]),
        ]:
            if column.button(
                label, key=f"adopt_scenario_{plan.id}_{delta}", disabled=row["Full contract budget"] is None
            ):
                try:
                    adopt_scenario(plan, delta, st.session_state.officer, records)
                    plan.ui_step = 4
                    st.rerun()
                except ValueError as error:
                    st.info(str(error))
    if any(r["Annual increase / yearly profile"].startswith("Varies by role") for r in rows):
        with st.expander("Scenario profiles by manpower group"):
            st.dataframe(profiles, hide_index=True, width="stretch")
    if st.button(
        "Change annual increase in Step 4" if on_edit is None else "Change future cost assumptions",
        key=f"final_sensitivity_edit_{plan.id}",
    ):
        if on_edit is None:
            go_to_step(plan, 4)
        else:
            on_edit()


def deployment_review(plan):
    from collections import Counter

    from services.final_review import deployment_rows

    rows = deployment_rows(plan)
    st.caption(
        "Grouped deployment view. Confirmed reporting relationships have not been recorded; no reporting lines are inferred from role titles."
    )
    for unit in dict.fromkeys(row["Unit"] for row in rows):
        group = [r for r in rows if r["Unit"] == unit]
        count = Counter(r["Role"] for r in group)
        seen = Counter()
        labels = []
        for row in group:
            seen[row["Role"]] += 1
            labels.append(row["Role"] + (f" (row {seen[row['Role']]})" if count[row["Role"]] > 1 else ""))
        chart = go.Figure(
            go.Bar(
                x=[r["Quantity"] for r in group],
                y=labels,
                orientation="h",
                marker_color="#147D74" if unit == "headcount" else "#8164B7",
                text=["Unanswered" if r["Quantity"] is None else f"{r['Quantity']:g}" for r in group],
                textposition="auto",
            )
        )
        chart.update_layout(
            title="Headcount"
            if unit == "headcount"
            else "FTE"
            if unit == "FTE"
            else "Recorded unit: " + unit,
            height=max(240, 85 + 40 * len(group)),
            xaxis_title=unit,
            yaxis=dict(autorange="reversed"),
            margin=dict(l=10, r=15, t=40, b=35),
        )
        st.plotly_chart(chart, width="stretch", key=f"final_deployment_{unit}")
    visible = [{k: r[k] for k in ("Role", "Quantity", "Unit")} for r in rows]
    st.dataframe(visible, hide_index=True, width="stretch")
    if any(r["Yearly quantities"] for r in rows):
        st.dataframe(
            [
                {
                    "Role": r["Role"],
                    "Unit": r["Unit"],
                    **{
                        f"Year {i + 1}": q
                        for i, q in enumerate(r["Yearly quantities"] or [r["Quantity"]] * plan.profile.years)
                    },
                }
                for r in rows
            ],
            hide_index=True,
            width="stretch",
        )


def restore_finding_controls(prefix):
    baseline = st.session_state.get("finding_inputs", {}).pop(prefix, {})
    for suffix, value in baseline.items():
        st.session_state[prefix + suffix] = value
    st.session_state.pop(prefix + "_model", None)
    st.session_state[prefix + "_choice"] = "Keep my figures"
    st.session_state.plan.basis_drafts.get("finding_choices", {}).pop(prefix, None)
    draft = st.session_state.plan.basis_drafts.get("_ui_controls", {})
    values = draft.get("values", {})
    for key in list(values):
        if key.startswith(prefix + "_"):
            values.pop(key)
    if draft and not values:
        st.session_state.plan.basis_drafts.pop("_ui_controls", None)


def remember_review_choice(prefix):
    import ui_drafts

    choice = st.session_state[prefix + "_choice"]
    st.session_state[prefix + "_status"] = "accepted exception"
    st.session_state.plan.basis_drafts.setdefault("finding_choices", {})[prefix] = choice
    previous = dict(st.session_state.plan.basis_drafts.get("_ui_controls", {}).get("values", {}))
    ui_drafts.capture(st.session_state.plan, ["Record or revert the edited finding decision"])
    values = st.session_state.plan.basis_drafts["_ui_controls"]["values"]
    for key, value in previous.items():
        values.setdefault(key, value)


def finding_control(plan, finding, officer, sync_controls):
    from services.final_review import rationale_for
    from services.workflow import record_decision

    prefix = f"finding_{plan.id}_{finding.id}_{finding.fingerprint}"
    reason = rationale_for(plan, finding)
    baseline = {
        "_status": finding.status,
        "_reason": reason,
        "_inclusion": finding.inclusion,
        "_further": finding.further_approval,
    }
    if st.session_state.pop(prefix + "_reset", False):
        st.session_state.pop(prefix + "_model", None)
    sync_controls(prefix, tuple(baseline.values()), baseline)
    st.session_state.setdefault("finding_inputs", {})[prefix] = baseline
    st.session_state.setdefault("finding_labels", {})[prefix] = finding.message
    if prefix + "_choice" not in st.session_state:
        st.session_state[prefix + "_choice"] = plan.basis_drafts.get("finding_choices", {}).get(
            prefix, "Keep my figures"
        )
    choice = st.radio(
        "How would you like to resolve this?",
        ["Keep my figures", "Correct the interpretation", "Revise figures"],
        key=retained_key(prefix + "_choice"),
        horizontal=True,
        on_change=remember_review_choice,
        args=(prefix,),
    )
    if choice == "Revise figures":
        st.caption("Return to the original input to revise it; this review does not change the figures.")
        return
    status = "accepted exception"
    if reason:
        st.caption(
            "Your relevant earlier explanation is reused below. Edit it only if the concern needs a different response."
        )
    justification = st.text_area(
        "Reason for retaining figures or correcting the interpretation",
        value=reason,
        key=retained_key(prefix + "_reason"),
    )
    with st.expander("Cost treatment or further approval, if relevant"):
        inclusion = st.text_input(
            "Cost inclusion / exclusion / impact treatment",
            value=finding.inclusion,
            key=retained_key(prefix + "_inclusion"),
        )
        further = st.text_input(
            "Further approval required (if any)",
            value=finding.further_approval,
            key=retained_key(prefix + "_further"),
        )
    if st.button("Record decision", key=prefix + "_record"):
        try:
            record_decision(plan, finding, status, justification, officer, inclusion, further)
            plan.history.append(
                {
                    "action": "Officer resolved review concern",
                    "choice": choice,
                    "finding_id": finding.id,
                    "version": plan.version,
                    "officer": officer,
                }
            )
            plan.basis_drafts.get("finding_choices", {}).pop(prefix, None)
            st.session_state.get("finding_inputs", {}).pop(prefix, None)
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    st.button(
        "Revert unrecorded edits", key=prefix + "_revert", on_click=restore_finding_controls, args=(prefix,)
    )


def supporting_review(plan, records, current, result):
    from services.final_review import source_summary

    st.markdown("**Starting monthly rates**")
    rates, _, _ = source_summary(plan, records)
    st.dataframe(
        [{key: value for key, value in row.items() if key != "Basis"} for row in rates],
        hide_index=True,
        width="stretch",
    )
    st.markdown("**Future cost assumptions**")
    explanations = list(
        dict.fromkeys(b.explanation for b in plan.decision_bases if b.kind == "escalation" and b.explanation)
    )
    if not explanations:
        explanations = list(
            dict.fromkeys(r.escalation_reason for r in plan.roles if r.included and r.escalation_reason)
        )
    for text in explanations:
        st.write(text)
    if not explanations:
        st.caption(
            "The selected annual increase is shown in the budget summary; no separate explanation is recorded."
        )
    if any(role.included and role.pwm for role in plan.roles):
        st.caption("Source of PWM: MOM website.")
    st.markdown("**Excluded costs**")
    st.write(
        plan.profile.exclusions
        or "No additional exclusions have been recorded. This EPV covers manpower charges only."
    )
    adjustments = [
        {
            "Role": r.label,
            "Adjustment": policy.name,
            "Component": policy.affected_component,
            "Effective date": str(policy.effective_date),
            "Source": policy.source,
        }
        for r in plan.roles
        if r.included
        for policy in r.policies
    ]
    if adjustments:
        st.markdown("**Other recorded adjustments**")
        st.dataframe(adjustments, hide_index=True, width="stretch")


def budget_totals(plan, result):
    if result:
        a, b, c = st.columns(3)
        a.metric("Full contract manpower budget (SGD)", f"{result['contract_total']:,.2f}")
        b.metric(
            "Base contract period - "
            + (f"Years 1-{plan.profile.base_years}" if plan.profile.base_years > 1 else "Year 1")
            + " (SGD)",
            f"{result['base_total']:,.2f}",
        )
        option_label = (
            (
                f"Years {plan.profile.base_years + 1}-{plan.profile.years}"
                if plan.profile.option_years > 1
                else f"Year {plan.profile.years}"
            )
            if plan.profile.option_years
            else "No option years"
        )
        c.metric("Optional extension - " + option_label + " (SGD)", f"{result['option_total']:,.2f}")
    else:
        st.info(
            "Budget totals are not yet available. Complete the specific inputs listed below; the project draft remains saved separately."
        )


def final_review(plan, records, officer, save, sync_controls):
    from journey_inputs import pending_control_errors
    from services.export import export_excel
    from services.final_review import action_presentation, review_state
    from services.workflow import confirm

    results_style()
    state = review_state(plan, records, pending_control_errors(plan))
    result = state["result"]
    (st.success if state["confirmed"] else st.info)("Budget status: " + state["status"])
    budget_totals(plan, result)
    profiles = {
        tuple(r.escalation)
        for r in plan.roles
        if r.included and not r.pwm and r.escalation_mode == "assumption"
    }
    if len(profiles) == 1 and next(iter(profiles)) and len(set(next(iter(profiles))[1:])) <= 1:
        profile = next(iter(profiles))
        st.write(
            f"Annual manpower increase: {profile[1]:.2%} from Year 2."
            if len(profile) > 1
            else "Annual manpower increase: not applicable to a single contract year."
        )
    else:
        st.write(
            "Annual manpower increase: varies by year or role; see the annual breakdown."
            if profiles
            else "Annual manpower increase: no general annual increase is recorded."
        )
    pwm_roles = [r for r in plan.roles if r.included and r.pwm]
    if pwm_roles:
        st.write("PWM increment: in accordance with rates published on the MOM website.")
    if state["actions"]:
        st.markdown("### What needs your attention")
    for index, action in enumerate(state["actions"]):
        with st.container(border=True):
            summary, why, details = action_presentation(plan, action)
            if action["kind"] == "finding":
                finding = next(f for f in state["findings"] if f.id == action["findings"][0])
                st.write(finding.message)
                st.caption(why)
                finding_control(plan, finding, officer, sync_controls)
                action_label = "Revise figures in Step " + str(action["step"] + 1)
            else:
                st.markdown(
                    "**"
                    + (
                        "Missing or invalid inputs"
                        if action["kind"] == "inputs"
                        else "Confirmation needed"
                        if action["kind"] == "confirmation"
                        else "Explanation needed"
                    )
                    + "**"
                )
                st.write(summary)
                # Optional table, without stacked or nested dropdowns.
                if details and st.toggle(
                    "Show affected roles", key=f"final_action_details_{plan.id}_{index}"
                ):
                    st.dataframe(
                        details,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Selected monthly rate": st.column_config.NumberColumn(format="accounting")
                        },
                    )
                action_label = (
                    "Complete pricing basis"
                    if action["step"] == 3 and action["kind"] == "judgement"
                    else "Edit rates"
                    if action["step"] == 3
                    else "Change annual increase"
                    if action["step"] == 4
                    else "Complete contract context"
                    if action["step"] == 0
                    else "Review deployment"
                )
            if st.button(action_label, key=f"final_action_{plan.id}_{index}"):
                affected_names = {row["Role"] for row in details if row.get("Role")}
                affected_ids = [r.id for r in plan.roles if r.label in affected_names]
                if action["kind"] == "finding":
                    affected_ids = [finding.role_id] if finding.role_id else affected_ids
                st.session_state["review_focus_" + plan.id] = {"step": action["step"], "roles": affected_ids}
                go_to_step(plan, action["step"])
    tabs = st.tabs(
        ["Budget", "Scenarios", "Manpower", "Assumptions & sources"],
        key=f"final_results_tab_{plan.id}",
        on_change="rerun",
    )
    with tabs[0]:
        if result:
            annual_review(plan, result)
        else:
            st.info("Annual costs will appear once the missing calculation inputs are completed.")
    with tabs[1]:
        if result:
            sensitivity_review(plan, records)
        else:
            st.caption("Complete the calculation inputs before comparing scenarios.")
    with tabs[2]:
        deployment_review(plan)
    with tabs[3]:
        supporting_review(plan, records, state["findings"], result)
    st.divider()
    download, confirmation = st.columns(2)
    with download:
        st.caption("Confirmed budget" if state["confirmed"] else "Draft budget - not yet confirmed")
        if result:
            st.download_button(
                "Download budget",
                export_excel(plan, records),
                file_name=f"fm-budget-{'confirmed' if state['confirmed'] else 'draft'}-v{plan.version}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.caption("A numeric budget export is available after correcting the calculation inputs.")
    with confirmation:
        if state["actions"]:
            short, _, _ = action_presentation(plan, state["actions"][0])
            st.caption("Before confirmation: " + short)
        if st.button(
            "Confirm final budget",
            key="confirm_final_budget",
            disabled=state["confirmed"]
            or bool(state["actions"])
            or bool(state["final_errors"])
            or result is None,
            type="primary",
        ):
            try:
                if "validation" not in plan.confirmations:
                    confirm(plan, "validation", officer, records)
                confirm(plan, "final", officer, records)
                save()
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    st.caption(f"Budget version {plan.version}")
