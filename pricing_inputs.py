"""Compact starting-price rows; live inputs are separate from officer confirmation."""

import streamlit as st

from activity_nav import retained_key
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
from services.reference_data import prepared
from services.ui_context import current_plan
from services.workflow import apply_change, invalidate

PRICING_UI_VERSION = 7


def rate_changed(rid, field, key, peer=None):
    plan = current_plan()
    role = next(r for r in plan.roles if r.id == rid)
    value = st.session_state[key]
    if field == "rate" and value == 0:
        value = None
    if field == "rate":
        if value is None:
            plan.basis_drafts.setdefault("rate_unanswered", {})[rid] = True
        elif "rate_unanswered" in plan.basis_drafts:
            plan.basis_drafts["rate_unanswered"].pop(rid, None)
            if not plan.basis_drafts["rate_unanswered"]:
                plan.basis_drafts.pop("rate_unanswered")
    if getattr(role, field) == value:
        return
    prior = retained_basis(plan, role, "rate")
    payload = role.model_dump(mode="json")
    payload[field] = value
    if field == "rate":
        payload.update(rate_reason="", rate_origin="Officer assumption")
        if rid in plan.basis_drafts.get("illustrative_rate_bands", {}) and value is not None:
            from services.planning_allowances import planning_reason

            payload["rate_reason"] = planning_reason(value)
    apply_change(
        plan, "role", payload, "Officer edited starting " + field.replace("_", " "), st.session_state.officer
    )
    if field == "rate_reason" and prior:
        plan.basis_drafts.setdefault("pricing_sources", {})[rid] = prior.snapshots[rid].get(
            "quotation_reference", ""
        )
    if peer and value is not None:
        st.session_state[peer] = value


def pricing_source_changed(rid, key):
    plan = current_plan()
    plan.basis_drafts.setdefault("pricing_sources", {})[rid] = st.session_state[key]
    invalidate(plan, "rates", "Officer revised starting-rate document reference", st.session_state.officer)


def year_changed(prefix):
    plan = current_plan()
    plan.basis_drafts["pricing_year"] = {
        "roles": st.session_state[prefix + "_roles"],
        "explanation": st.session_state[prefix + "_text"],
    }
    invalidate(plan, "rates", "Officer revised the shared reference-year treatment", st.session_state.officer)


def keep_shared_editor(prefix):
    current_plan().basis_drafts["pricing_shared_editor"] = {
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
            key=retained_key(prefix + "_roles"),
            on_change=keep_shared_editor,
            args=(prefix,),
        )
        reason = st.text_area(
            "Shared pricing basis",
            value=saved.get("reason", ""),
            key=retained_key(prefix + "_reason"),
            on_change=keep_shared_editor,
            args=(prefix,),
            placeholder="For example: supplier quotation Q1 covers the inclusive monthly allowances for these roles.",
        )
        source = st.text_input(
            "Shared quotation / document (optional)",
            value=saved.get("source", ""),
            key=retained_key(prefix + "_source"),
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
    from services.planning_allowances import planning_range, seed_missing_allowances

    seed_missing_allowances(plan, records, officer)
    st.caption(
        "Enter the monthly allowance for each unit of your confirmed deployment. A quotation is optional. No automatic inflation adjustment is applied."
    )
    if plan.basis_drafts.get("illustrative_rate_bands"):
        st.caption(
            "Illustrative planning ranges are editable demo assumptions, not market data. Existing entered charges are retained."
        )
    columns = st.columns([2.1, 1.2, 2.8, 1.5])
    for col, title in zip(
        columns,
        ["Role", "Deployment", "Monthly unit allowance (SGD)", "Monthly role cost (SGD)"],
        strict=True,
    ):
        col.markdown("**" + title + "**")
    legacy = plan.basis_drafts.get("rate", {})
    focus = st.session_state.get("review_focus_" + plan.id, {})
    focused = set(focus.get("roles", [])) if focus.get("step") == 3 else set()
    if focused:
        st.caption("The affected pricing fields are shown first; existing rates and reasons are retained.")
    for role in sorted(plan.roles, key=lambda r: r.id not in focused):
        if not role.included:
            continue
        bm = reference(plan, role, records)
        prefix = f"rate_{plan.id}_{role.id}_{role.benchmark_year}"
        prior = retained_basis(plan, role, "rate")
        reason = role.rate_reason
        if prior and not meaningful(reason):
            reason = prior.snapshots[role.id].get("pricing_rationale", prior.explanation)
        shared = shared_pricing_applies(plan, role) and legacy.get("_shared", False)
        sync(prefix, (role.rate, role.rate_reason), {"_number": role.rate, "_rationale": reason})
        a, b, c, d = st.columns([2.1, 1.2, 2.8, 1.5], vertical_alignment="top")
        a.write(role.label)
        b.write(f"{role.quantity:g} {role.quantity_unit}")
        with c:
            from selection_controls import reference_bar

            if bm.get("recommendation_supported"):
                reference_bar(
                    "Select monthly rate — " + role.label,
                    prefix + "_bar",
                    role.rate,
                    round(bm["minimum"], 2),
                    round(bm["average"], 2),
                    round(bm["maximum"], 2),
                    rate_changed,
                    (role.id, "rate", prefix + "_bar", prefix + "_number"),
                )
            else:
                band = planning_range(role)
                reference_bar(
                    "Select monthly rate — " + role.label,
                    prefix + "_bar",
                    role.rate,
                    band["minimum"],
                    band["average"],
                    band["maximum"],
                    rate_changed,
                    (role.id, "rate", prefix + "_bar", prefix + "_number"),
                    average_label="Suggested planning average",
                    range_label="Illustrative minimum / maximum",
                )
        c.number_input(
            ("Monthly rate per FTE — " if role.quantity_unit == "FTE" else "Monthly rate per person — ")
            + role.label,
            min_value=0.0,
            max_value=10000000.0,
            value=None,
            format="%.2f",
            step=0.01,
            key=retained_key(prefix + "_number"),
            label_visibility="collapsed",
            on_change=rate_changed,
            args=(role.id, "rate", prefix + "_number"),
            help="Monthly manpower charge for one unit of the deployment above. A supporting quotation is optional.",
        )
        cost = monthly_role_cost(role)
        d.write(f"{cost:,.2f}" if cost is not None else "Awaiting rate")
        needs_note = needs_pricing_basis(role, bm) and role.rate is not None and not shared and not prior
        ask_note = needs_note and (
            not meaningful(role.rate_reason)
            or role.rate_reason.startswith(
                (
                    "Officer budgeting allowance:",
                    "Editable arithmetic-average starting point",
                    "Conditional source-quote average",
                )
            )
        )
        if ask_note or plan.basis_drafts.get("pricing_document_editors", {}).get(role.id):
            plan.basis_drafts.setdefault("pricing_document_editors", {})[role.id] = True
            c.text_area(
                "Short pricing reason — " + role.label,
                key=retained_key(prefix + "_rationale"),
                height=68,
                on_change=rate_changed,
                args=(role.id, "rate_reason", prefix + "_rationale"),
                placeholder="Briefly explain this allowance, for example additional experience or an agreed contractor allowance. Documents are optional.",
            )
        elif prior or (needs_note and meaningful(role.rate_reason)):
            c.caption("Recorded pricing reason retained.")
        elif shared:
            c.caption("Shared pricing reason applies.")
        source_value = plan.basis_drafts.get("pricing_sources", {}).get(
            role.id, prior.snapshots[role.id].get("quotation_reference", "") if prior else ""
        )
        if ask_note or source_value or plan.basis_drafts.get("pricing_document_editors", {}).get(role.id):
            c.text_input(
                "Quotation / document (optional) — " + role.label,
                value=source_value,
                key=retained_key(prefix + "_source"),
                on_change=pricing_source_changed,
                args=(role.id, prefix + "_source"),
            )
    shared_pricing_panel(plan, records, officer)
    mismatch = [
        r
        for r in plan.roles
        if r.included
        and not prepared(records)
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
            key=retained_key(prefix + "_roles"),
            on_change=year_changed,
            args=(prefix,),
        )
        notes = {r.rate_notes for r in mismatch if meaningful(r.rate_notes)}
        default = next(iter(notes)) if len(notes) == 1 else legacy.get("_explanation", "")
        st.text_area(
            "Reference-year treatment",
            value=saved.get("explanation", default),
            key=retained_key(prefix + "_text"),
            on_change=year_changed,
            args=(prefix,),
            placeholder="Explain whether the reference-year allowance is retained or how the selected rates account for the contract start.",
        )
    try:
        result = starting_overview(plan)
        a, b = st.columns(2)
        a.metric("Total monthly manpower cost (SGD)", f"{result['monthly']:,.2f}")
        b.metric("Starting annual manpower cost (SGD)", f"{result['year_1']:,.2f}")
        st.caption(
            "Annual starting cost uses each role’s quantity × monthly allowance × 12, rounded to cents. Future increases are reviewed in Step 4."
        )
        if result["annual_rounding_difference"]:
            st.caption(
                f"Rounding fractional FTE monthly totals can produce a small difference (SGD {abs(result['annual_rounding_difference']):,.2f}) from the annual budget. The annual amount above follows the budget calculation."
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
            st.session_state.pop("review_focus_" + plan.id, None)
            candidate.ui_step = 4
            plan.__dict__.update(candidate.__dict__)
            save()
            st.rerun()
        except ValueError as error:
            st.error(str(error))
