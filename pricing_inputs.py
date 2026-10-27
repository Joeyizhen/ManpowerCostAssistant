"""Compact starting-price rows; live inputs are separate from officer confirmation."""

import html

import streamlit as st

from services.calculations import monthly_role_cost
from services.decision_basis import meaningful, retained_basis
from services.journey import accept_review, prepare_review
from services.pricing import (
    apply_shared_pricing,
    needs_pricing_basis,
    pricing_proposal,
    reference,
    shared_pricing_applies,
    starting_overview,
)
from services.workflow import apply_change, invalidate

PRICING_UI_VERSION = 3


def rate_changed(rid, field, key, peer=None):
    plan = st.session_state.plan
    role = next(r for r in plan.roles if r.id == rid)
    value = st.session_state[key]
    if field == "rate" and value == 0:
        value = None
    if getattr(role, field) == value:
        return
    payload = role.model_dump(mode="json")
    payload[field] = value
    if field == "rate":
        payload.update(rate_reason="", rate_origin="Officer assumption")
    apply_change(
        plan, "role", payload, "Officer edited starting " + field.replace("_", " "), st.session_state.officer
    )
    if peer and value is not None:
        st.session_state[peer] = value


def pricing_source_changed(rid, key):
    plan = st.session_state.plan
    plan.basis_drafts.setdefault("pricing_sources", {})[rid] = st.session_state[key]
    invalidate(plan, "rates", "Officer revised starting-rate document reference", st.session_state.officer)


def year_changed(prefix):
    plan = st.session_state.plan
    plan.basis_drafts["pricing_year"] = {
        "roles": st.session_state[prefix + "_roles"],
        "explanation": st.session_state[prefix + "_text"],
    }
    invalidate(plan, "rates", "Officer revised the shared reference-year treatment", st.session_state.officer)


def keep_shared_editor(prefix):
    st.session_state.plan.basis_drafts["pricing_shared_editor"] = {
        name: st.session_state.get(prefix + "_" + name) for name in ("roles", "reason", "source")
    }


def shared_pricing_panel(plan, records, officer):
    prefix = f"pricing_shared_{plan.id}"
    saved = plan.basis_drafts.get("pricing_shared_editor", {})
    labels = {r.id: r.label for r in plan.roles if r.included}
    defaults = [
        r.id
        for r in plan.roles
        if r.included
        and needs_pricing_basis(r, reference(plan, r, records))
        and not retained_basis(plan, r, "rate")
    ]
    with st.expander("One quotation or explanation covers several roles"):
        st.caption(
            "Use this only when the same quotation or explanation genuinely covers the selected roles. It records the basis once and keeps every rate unchanged."
        )
        selected = st.multiselect(
            "Roles covered by this pricing basis",
            list(labels),
            default=saved.get("roles", defaults),
            format_func=lambda rid: labels[rid],
            key=prefix + "_roles",
            on_change=keep_shared_editor,
            args=(prefix,),
        )
        reason = st.text_area(
            "Shared pricing basis",
            value=saved.get("reason", ""),
            key=prefix + "_reason",
            on_change=keep_shared_editor,
            args=(prefix,),
            placeholder="For example: supplier quotation Q1 covers the inclusive monthly allowances for these roles.",
        )
        source = st.text_input(
            "Shared quotation / document (optional)",
            value=saved.get("source", ""),
            key=prefix + "_source",
            on_change=keep_shared_editor,
            args=(prefix,),
        )
        if st.button("Apply pricing basis to selected roles", key=prefix + "_apply"):
            try:
                apply_shared_pricing(plan, selected, reason, source, officer)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        if plan.basis_drafts.get("rate", {}).get("_shared"):
            st.caption(
                "Shared basis applied to the current allowances. Confirm starting rates below to record the pricing decision."
            )
            if st.button("Remove shared pricing draft", key=prefix + "_remove"):
                plan.basis_drafts.pop("rate", None)
                st.rerun()


def starting_prices(plan, records, officer, save, sync):
    from hybrid_inputs import confirmation_errors, show_missing

    st.caption(
        "These are inclusive manpower charges per head or FTE, not employee salaries or full trade/service prices. No salary split or inflation adjustment is inferred."
    )
    if st.button("Edit deployment", key="pricing_edit_deployment"):
        plan.ui_step = 1
        st.rerun()
    st.caption(
        "Deployment is carried forward. Editing it invalidates manpower confirmation and all affected rates, future costs and final confirmations when quantities or units change."
    )
    shared_pricing_panel(plan, records, officer)
    headers = st.columns([2.1, 1.2, 3.2, 1.6])
    for col, title in zip(
        headers,
        ["Role", "Confirmed quantity / unit", "Monthly rate per person / FTE", "Monthly role cost"],
        strict=True,
    ):
        col.markdown("**" + title + "**")
    legacy = plan.basis_drafts.get("rate", {})
    for role in plan.roles:
        if not role.included:
            continue
        bm = reference(plan, role, records)
        prefix = f"rate_{plan.id}_{role.id}_{role.benchmark_year}"
        retained_reason = role.rate_reason
        prior = retained_basis(plan, role, "rate")
        if prior and (
            not meaningful(retained_reason) or retained_reason.startswith("Officer budgeting allowance:")
        ):
            retained_reason = prior.snapshots[role.id].get("pricing_rationale", prior.explanation)
        shared = shared_pricing_applies(plan, role) and legacy.get("_shared", False)
        if shared_pricing_applies(plan, role) and (
            shared
            or not meaningful(retained_reason)
            or retained_reason.startswith("Officer budgeting allowance:")
        ):
            retained_reason = legacy.get("_explanation", "")
        sync(
            prefix,
            (role.rate, role.rate_reason),
            {"_slider": role.rate, "_number": role.rate, "_rationale": retained_reason},
        )
        a, b, c, d = st.columns([2.1, 1.2, 3.2, 1.6], vertical_alignment="top")
        a.write(role.label)
        b.write(f"{role.quantity:g} {role.quantity_unit}")
        unit = "FTE" if role.quantity_unit == "FTE" else "person"
        cost = monthly_role_cost(role)
        d.write(f"SGD {cost:,.2f}" if cost is not None else "Awaiting rate")
        outside = bool(
            bm["available"] and role.rate is not None and not bm["minimum"] <= role.rate <= bm["maximum"]
        )
        controls = c.container()
        details = c.expander("Edit basis / custom rate")
        if bm["available"]:
            custom = details.checkbox("Use another rate", value=outside, key=prefix + "_custom")
            low, high = round(bm["minimum"], 2), round(bm["maximum"], 2)
            if not custom and (role.rate is None or not low <= role.rate <= high):
                controls.caption(
                    "The recorded allowance is retained. Use another rate to edit it, or select a supported reference below."
                )
            slider_key = prefix + "_slider"
            current = (
                role.rate if role.rate is not None and low <= role.rate <= high else round(bm["average"], 2)
            )
            if st.session_state.get(slider_key) is None or not low <= st.session_state[slider_key] <= high:
                st.session_state[slider_key] = current
            if not custom and low < high:
                controls.slider(
                    f"Range for {role.label} (SGD per {unit})",
                    min_value=low,
                    max_value=high,
                    value=None,
                    step=0.01,
                    format="%.2f",
                    key=slider_key,
                    on_change=rate_changed,
                    args=(role.id, "rate", slider_key, prefix + "_number"),
                    label_visibility="collapsed",
                )
                position = min(100, max(0, (bm["average"] - low) / (high - low) * 100))
                controls.markdown(
                    f'<div style="position:relative;height:18px;font-size:11px;color:#475467"><span style="position:absolute;left:{position:.2f}%;transform:translateX(-50%)">◆ average</span></div>',
                    unsafe_allow_html=True,
                )
            controls.caption(f"Min {low:,.2f} · Average {bm['average']:,.2f} · Max {high:,.2f}")
        else:
            custom = True
            controls.caption(
                "Officer assumption: no comparable range. Enter a quotation-based allowance or an officer assumption."
            )
        # The numeric value always remains inspectable, including retained out-of-range allowances.
        controls.number_input(
            f"Monthly rate per {unit} — {role.label}",
            min_value=0.0 if custom or outside else round(bm["minimum"], 2),
            max_value=10000000.0 if custom or outside else round(bm["maximum"], 2),
            value=None,
            format="%.2f",
            step=0.01,
            key=prefix + "_number",
            label_visibility="collapsed",
            disabled=outside and not custom,
            on_change=rate_changed,
            args=(role.id, "rate", prefix + "_number", None if custom else slider_key),
        )
        old = retained_basis(plan, role, "rate")
        if (
            needs_pricing_basis(role, bm)
            and role.rate is not None
            and not shared
            and (not old or role.id in plan.basis_drafts.get("pricing_sources", {}))
        ):
            details.text_area(
                "Pricing rationale — " + role.label,
                key=prefix + "_rationale",
                height=68,
                on_change=rate_changed,
                args=(role.id, "rate_reason", prefix + "_rationale"),
                placeholder="State the quotation or financial reason for this selected allowance.",
            )
            source = plan.basis_drafts.get("pricing_sources", {}).get(role.id, legacy.get("_source", ""))
            details.text_input(
                "Quotation / document (optional) — " + role.label,
                value=source,
                key=prefix + "_source",
                on_change=pricing_source_changed,
                args=(role.id, prefix + "_source"),
            )
        elif shared:
            details.caption("Using the shared pricing basis; no repeated explanation is needed.")
        elif old:
            details.caption("Recorded pricing basis retained.")
        elif bm["available"]:
            details.caption(
                "Within the observed range. The reference records and selected allowance are retained automatically."
            )
    mismatch = [
        r
        for r in plan.roles
        if r.included
        and r.benchmark_year
        and plan.profile.costing_start
        and r.benchmark_year != plan.profile.costing_start.year
        and not retained_basis(plan, r, "rate")
    ]
    if mismatch or "pricing_year" in plan.basis_drafts:
        prefix = f"pricing_year_{plan.id}"
        saved = plan.basis_drafts.get("pricing_year", {})
        labels = {r.id: r.label for r in plan.roles if r.included}
        st.caption(
            "Reference pricing and contract-start years differ. Record the treatment once for related rows; no automatic inflation is applied."
        )
        # Both widgets exist before a callback can run.
        st.multiselect(
            "Rows sharing the reference-year treatment",
            list(labels),
            default=saved.get("roles", [r.id for r in mismatch]),
            format_func=lambda rid: labels[rid],
            key=prefix + "_roles",
            on_change=year_changed,
            args=(prefix,),
        )
        notes = {r.rate_notes for r in mismatch if meaningful(r.rate_notes)}
        default = next(iter(notes)) if len(notes) == 1 else legacy.get("_explanation", "")
        st.text_area(
            "Reference-year treatment",
            value=saved.get("explanation", default),
            key=prefix + "_text",
            on_change=year_changed,
            args=(prefix,),
            placeholder="Explain whether the reference-year allowance is retained or how the selected rates account for the contract start.",
        )
    with st.expander("Rate evidence, inclusions and earlier explanations"):
        for role in plan.roles:
            if role.included:
                bm = reference(plan, role, records)
                st.markdown("**" + html.escape(role.label) + "**")
                st.caption(
                    f"Pricing year {role.benchmark_year} · {bm['sample_count']} comparable schedules · {role.rate_origin}"
                )
                st.write(bm["method"] + " " + bm["limitations"])
                st.dataframe(bm["records"], hide_index=True, width="stretch")
                old = retained_basis(plan, role, "rate")
                if old:
                    st.write(old.explanation)
                    st.caption(old.source)
    try:
        result = starting_overview(plan)
        a, b = st.columns(2)
        a.metric("Total monthly manpower cost (SGD)", f"{result['monthly']:,.2f}")
        b.metric("Starting annual manpower cost (SGD)", f"{result['display_annual']:,.2f}")
        st.caption("Starting annual cost = monthly total × 12. Future changes are reviewed in Step 5.")
        if result["annual_rounding_difference"]:
            st.info(
                f"FTE rounding: the monthly × 12 overview differs by SGD {abs(result['annual_rounding_difference']):,.2f} from the retained annual starting-charge calculation of SGD {result['year_1']:,.2f}. Contract budgets keep the existing rule: annual role amounts are rounded after quantity × unit rate × 12."
            )
    except ValueError:
        known = sum(monthly_role_cost(role) or 0 for role in plan.roles if role.included)
        missing = sum(role.rate is None for role in plan.roles if role.included)
        a, b = st.columns(2)
        a.metric("Known monthly subtotal (SGD)", f"{known:,.2f}")
        b.metric("Starting annual subtotal (SGD)", f"{known * 12:,.2f}")
        st.caption(
            f"Incomplete subtotal: {missing} included rates are unanswered. No zero allowance is inferred; complete them for the full total."
        )
    candidate, errors = pricing_proposal(plan, records, officer)
    if not errors:
        errors += confirmation_errors(candidate, officer, records, checkpoint="rates")
    show_missing(errors)
    if st.button(
        "Confirm starting rates and continue", key="confirm_rates", type="primary", disabled=bool(errors)
    ):
        try:
            review = prepare_review(candidate, "rates", records)
            if not review["ready"]:
                raise ValueError("; ".join(review.get("missing_inputs", [review["action"]])))
            accept_review(candidate, officer, records)
            candidate.ui_step = 4
            plan.__dict__.update(candidate.__dict__)
            save()
            st.rerun()
        except ValueError as error:
            st.error(str(error))
