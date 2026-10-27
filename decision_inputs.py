"""Shared explanations beside material decisions; incomplete answers are saveable drafts."""

import streamlit as st

from activity_nav import retained_key
from services.decision_basis import basis_errors, record_basis, retained_basis
from services.journey import working_draft
from services.manpower_checks import LOCAL_ACTOR


def keep_basis_draft(prefix, kind):
    plan = st.session_state.plan
    plan.basis_drafts[kind] = {
        key: st.session_state.get(prefix + key)
        for key in ("_roles", "_category", "_explanation", "_classification", "_source")
    }


def basis_panel(plan, kind, records):
    draft = working_draft(plan)
    errors = basis_errors(draft, kind, records)
    if not errors and kind not in plan.basis_drafts:
        old = next((b for b in reversed(plan.decision_bases) if b.kind == kind), None)
        if old:
            with st.expander("Recorded " + kind + " basis"):
                st.write(old.explanation)
                st.caption(old.classification + (" · " + old.source if old.source else ""))
                if st.button("Revise this basis", key=f"revise_basis_{plan.id}_{kind}"):
                    plan.basis_drafts[kind] = {
                        "_roles": old.role_ids,
                        "_category": old.category,
                        "_explanation": old.explanation,
                        "_source": old.source,
                        "_classification": old.classification,
                    }
                    st.rerun()
        return
    prompts = {
        "quantity": "What operational change or workload supports these quantities?",
        "rate": "What supports the selected starting allowance and its reference-year treatment?",
        "escalation": "Why is this future-price profile appropriate for the contract?",
        "policy": "What is the evidenced component adjustment and why does it not overlap?",
    }
    st.markdown("**" + prompts[kind] + "**")
    st.caption(
        "One explanation can cover several related roles. Recorded reasoning is not proof that the quantity or price is correct. You can save an incomplete draft."
    )
    labels = {r.id: r.label for r in draft.roles}
    needed = [r.id for r in draft.roles if any(e.startswith(r.label + ":") for e in errors)]
    prefix = f"basis_{plan.id}_{kind}"
    if st.session_state.pop(prefix + "_reset", False):
        for suffix in (
            "_roles",
            "_category",
            "_explanation",
            "_classification",
            "_source",
            "_unit_confirmed",
        ):
            st.session_state.pop(prefix + suffix, None)
    previous = next(
        (b for b in reversed(plan.decision_bases) if b.kind == kind and set(b.role_ids) & set(needed)), None
    )
    defaults = (
        {
            "_roles": needed,
            "_category": previous.category,
            "_explanation": previous.explanation,
            "_source": previous.source,
            "_classification": previous.classification,
        }
        if previous
        else {}
    )
    saved = plan.basis_drafts.get(kind, defaults)

    def options(suffix, default):
        return dict(
            key=retained_key(prefix + suffix), on_change=keep_basis_draft, args=(prefix, kind)
        ), saved.get(suffix, default)

    kwargs, default = options("_roles", needed)
    roles = st.multiselect(
        "Roles sharing this basis",
        list(labels),
        default=[r for r in default or [] if r in labels],
        format_func=lambda rid: labels[rid],
        **kwargs,
    )
    categories = [
        "Additional locations",
        "Longer coverage",
        "Increased workload",
        "Bringing work in-house",
        "Reduced scope / productivity",
        "Quotation / financial evidence",
        "Other operational or financial basis",
    ]
    categories = {
        "quantity": categories,
        "rate": [
            "Quotation / financial evidence",
            "Reference-year treatment",
            "Officer financial assumption",
            "Other operational or financial basis",
        ],
        "escalation": [
            "Tender-derived reference",
            "Quoted future prices",
            "Renewal allowance assumption",
            "Other operational or financial basis",
        ],
        "policy": [
            "Published policy / confirmed component",
            "Quotation / financial evidence",
            "Other operational or financial basis",
        ],
    }[kind]
    category = saved.get("_category") or categories[0]
    kwargs, default = options("_explanation", "")
    explanation = st.text_area(
        prompts[kind],
        value=default or "",
        placeholder="Give the specific workload change or financial source supporting this decision.",
        **kwargs,
    )
    kwargs, default = options("_source", "")
    source = st.text_input("Quotation or document reference (optional)", value=default or "", **kwargs)
    classification = "officer assumption"
    st.caption(
        "A supplied source and recorded rationale are not independent verification. Official PWM facts retain separate checked-date and version metadata."
    )
    unit_confirmed = (
        st.checkbox(
            "Confirm these are inclusive manpower unit allowances, not salaries or full trade/service prices",
            key=retained_key(prefix + "_unit_confirmed"),
        )
        if kind == "rate"
        else True
    )
    if st.button("Record shared basis", key=prefix + "_record"):
        try:
            if not unit_confirmed:
                raise ValueError("Confirm the allowance basis before recording this rate decision.")
            record_basis(
                plan,
                kind,
                roles,
                category,
                explanation,
                source,
                classification,
                st.session_state.get("officer") or LOCAL_ACTOR,
            )
            plan.basis_drafts.pop(kind, None)
            st.rerun()
        except ValueError as error:
            st.info(str(error))
    if st.button("Revert unrecorded basis", key=prefix + "_revert"):
        plan.basis_drafts.pop(kind, None)
        st.session_state[prefix + "_reset"] = True
        st.rerun()
    with st.expander("Affected decisions and previously recorded bases"):
        for error in errors:
            st.write(error)
        for role in draft.roles:
            old = next(
                (b for b in reversed(plan.decision_bases) if b.kind == kind and role.id in b.role_ids), None
            )
            if old:
                st.write(
                    f"{role.label}: {old.explanation} ({'current' if retained_basis(draft, role, kind) else 'values changed; review before reusing'})"
                )
