"""Track 1 review app. Start: uv run streamlit run app.py"""

import base64
import hashlib
import math
from uuid import uuid4

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hybrid_inputs import render_inputs
from services.agent import AgentError, converse, create_client
from services.calculations import budget, preliminary, sensitivity
from services.config import settings
from services.demo import demo_plan
from services.evidence import (
    LABEL,
    escalation_benchmark,
    load_records,
    rate_benchmark,
)
from services.export import export_excel
from services.hybrid import initialise_rates
from services.journey import accept_review, journey_context, prepare_review, working_draft
from services.models import GATES, STAGES, Plan, PolicyAdjustment
from services.storage import ConflictError, Store
from services.uploads import preserve_document
from services.workflow import (
    apply_change,
    apply_pending,
    budget_status,
    confirm,
    finding_history,
    findings,
    invalidate,
    missing_for_gate,
    record_decision,
    unlocked_stage,
)

st.set_page_config(
    page_title="FM Manpower Cost Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def boot():
    try:
        secrets = st.secrets.to_dict()
    except FileNotFoundError:
        secrets = {}
    try:
        cfg = settings(secrets)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    owner = "local-review"
    if cfg.mode == "shared":
        if "auth" not in secrets:
            st.error("Shared hosting requires Streamlit OIDC authentication configured privately in secrets.")
            st.stop()
        if not st.user.is_logged_in:
            st.title("FM Manpower Cost Assistant")
            if st.button("Sign in to plan a budget"):
                st.login()
            st.stop()
        email = st.user.get("email", "").casefold()
        if email not in cfg.allowed_emails:
            st.error("Your account is not on this app's access list.")
            st.stop()
        if not st.user.get("iss") or not st.user.get("sub") or st.user.get("email_verified") is False:
            st.error(
                "Your identity provider must supply a stable issuer/subject and an accepted email identity."
            )
            st.stop()
        owner = hashlib.sha256(
            (str(st.user.get("iss", "")) + ":" + str(st.user.get("sub", "")) + ":" + email).encode()
        ).hexdigest()
    try:
        store = Store(cfg.database_url)
    except Exception:
        st.error(
            "Storage could not be opened. Check the server database configuration. Credentials are not displayed."
        )
        st.stop()
    if "plan" not in st.session_state:
        st.session_state.plan = Plan()
        st.session_state.storage_revision = 0
        st.session_state.stage = 0
        st.session_state.officer = ""
    else:
        # Streamlit hot reload can leave session objects from the previous Pydantic class.
        # Rehydrate the same facts into current models; do not clear answers or approvals.
        st.session_state.plan = Plan.model_validate(st.session_state.plan.model_dump(mode="json"))
    return cfg, store, owner


cfg, store, owner = boot()
# Keep the officer identity when its input is hidden between guided steps or on the welcome screen.
st.session_state.officer = st.session_state.get("officer", "")
if "selected_track" not in st.session_state:
    st.session_state.selected_track = None
if "review_open" not in st.session_state:
    st.session_state.review_open = False

if st.session_state.selected_track is None:
    st.caption("FM MANPOWER COST ASSISTANT · AGENT 1")
    st.title("What would you like to do?")
    st.write("Choose a starting point. We’ll work through it together, one step at a time.")
    build, review = st.columns(2, gap="large")
    with build:
        with st.container(border=True):
            st.caption("TRACK 1")
            st.subheader("Build a new plan")
            st.write("Describe your project. Establish the duties and people needed, then review the budget.")
            if st.button("Build new plan", key="choose_track_1", type="primary", width="stretch"):
                st.session_state.selected_track = 1
                st.rerun()
    with review:
        with st.container(border=True):
            st.caption("TRACK 2 · PLANNED")
            st.subheader("Review a proposed plan")
            st.write(
                "Check an existing manpower proposal and its assumptions. This journey is planned for a later release."
            )
            if st.button("Review proposed plan", key="choose_track_2", width="stretch"):
                st.session_state.selected_track = 2
                st.rerun()
    st.caption(
        "This review release uses labelled synthetic evidence. Your current draft is retained when switching tracks."
    )
    st.stop()

if st.session_state.selected_track == 2:
    st.caption("TRACK 2 · REVIEW PROPOSED PLAN")
    st.title("Start with the proposal. Review one question at a time.")
    st.info("Track 2 is planned. Proposal upload and review are not implemented in this release.")
    st.write("Track 1 is available now. Your existing draft has been retained.")
    if st.button("Back to track selection", key="back_to_tracks"):
        st.session_state.selected_track = None
        st.rerun()
    st.stop()

records = load_records()
plan = st.session_state.plan


def officer():
    return st.session_state.officer.strip() or "Local reviewing officer"


def changed_role(role_id, field, widget_key, other_key=None, transform=None):
    r = next(x for x in st.session_state.plan.roles if x.id == role_id)
    payload = r.model_dump(mode="json")
    value = st.session_state[widget_key]
    if transform:
        value = transform(value)
    payload[field] = value
    if payload == r.model_dump(mode="json"):
        return
    if field == "rate":
        payload["rate_origin"] = "Officer assumption"
        payload["rate_reason"] = (
            f"Officer budgeting allowance: SGD {value:,.2f} inclusive monthly per head; editable assumption."
        )
    try:
        apply_change(st.session_state.plan, "role", payload, f"Revised {r.label}: {field}", officer())
        if other_key:
            st.session_state[other_key] = st.session_state[widget_key]
    except ValueError as e:
        st.session_state.ui_error = str(e)


def new_session(new_plan):
    # Clear project-dependent widget state when switching projects, to avoid stale sliders/approvals.
    for key in list(st.session_state):
        if key.startswith(
            ("six_", "hybrid_", "role_", "rate_", "esc_", "profile_", "finding_", "resp_", "confirm_")
        ):
            del st.session_state[key]
    st.session_state.plan = new_plan
    st.session_state.storage_revision = 0
    st.session_state.stage = unlocked_stage(new_plan)
    st.session_state.review_open = False


def save():
    try:
        st.session_state.storage_revision = store.save(
            st.session_state.plan, owner, st.session_state.storage_revision
        )
        st.success("Saved project and revision history.")
    except ConflictError as e:
        st.error(str(e))
    except Exception:
        st.error(
            "Save failed. Download a project snapshot to preserve your work; check storage configuration."
        )


def request_guidance(message, current_stage, kind="message"):
    """Keep failed input outside approved facts, with an explicit retry rather than an automatic repeat."""
    try:
        with st.spinner("Reviewing your answers and checking the next decision…"):
            converse(plan, records, message, create_client(cfg.api_key), cfg.model, STAGES[current_stage])
    except Exception as error:
        # Never display unexpected exception bodies: they may contain provider input or credentials.
        st.session_state.failed_turn = {
            "id": str(uuid4()),
            "project_id": plan.id,
            "message": message,
            "stage": current_stage,
            "kind": kind,
            "error": str(error)
            if isinstance(error, AgentError)
            else "The guidance turn could not finish. No proposed changes were applied.",
        }
        return False
    st.session_state.pop("failed_turn", None)
    st.session_state.hybrid_epoch = st.session_state.get("hybrid_epoch", 0) + 1
    st.session_state.six_epoch = st.session_state.get("six_epoch", 0) + 1
    return True


with st.sidebar:
    st.caption("AGENT 1 · MANPOWER BUDGET PLANNING")
    st.title("Build new plan")
    st.caption("Track 1")
    if st.button("Change track", key="change_track", width="stretch"):
        st.session_state.selected_track = None
        st.rerun()
    if st.button("New blank project", width="stretch"):
        new_session(Plan())
        st.rerun()
    if st.button("Load synthetic example", width="stretch"):
        new_session(demo_plan())
        st.rerun()
    st.caption("The example contains invented officer inputs. Review and confirm every stage.")
    saved = store.list(owner)
    if saved:
        selected = st.selectbox(
            "Saved projects", saved, format_func=lambda x: f"{x['name']} · saved revision {x['revision']}"
        )
        if st.button("Resume selected project", width="stretch"):
            loaded, revision = store.load(selected["id"], owner)
            new_session(loaded)
            st.session_state.storage_revision = revision
            st.rerun()
    if st.button("Save project", width="stretch"):
        save()
    st.download_button(
        "Download project snapshot",
        plan.model_dump_json(indent=2),
        file_name=f"fm-plan-v{plan.version}.json",
        mime="application/json",
        width="stretch",
    )
    with st.expander("Restore a downloaded snapshot"):
        snapshot = st.file_uploader("Project JSON", type=["json"], key="snapshot")
        if snapshot and st.button("Restore as a new draft"):
            try:
                if snapshot.size > 30 * 1024 * 1024:
                    raise ValueError("Snapshot exceeds 30 MB")
                loaded = Plan.model_validate_json(snapshot.getvalue())
                loaded.id = str(uuid4())
                invalidate(
                    loaded,
                    "profile",
                    "Restored snapshot as a new draft; imported approvals require renewed review",
                    officer(),
                )
                loaded.pending = []
                new_session(loaded)
                st.rerun()
            except ValueError:
                st.error("Invalid snapshot. Required fields/numeric values must be valid.")
    st.divider()
    if cfg.api_key and cfg.model:
        st.success("Live OpenAI configured")
        st.caption(f"Model: {cfg.model}")
    else:
        st.info("Live guidance awaiting private API key and model configuration.")
        st.caption("Review controls work now. No simulated chat is presented as a live agent.")
    if cfg.mode == "shared":
        if st.button("Sign out"):
            st.logout()
    else:
        st.caption(
            "Local review mode. Saved projects are available to users of this computer. Shared hosting requires login and PostgreSQL."
        )

st.caption("AI-POWERED FM MANPOWER COST ASSISTANT")
st.title(
    plan.profile.name if plan.profile.name != "Untitled project" else "Plan the people. Explain the budget."
)
st.caption("TRACK 1 · BUILD NEW PLAN")
st.caption(LABEL)
if "ui_error" in st.session_state:
    st.error(st.session_state.pop("ui_error"))
if "input_error" in st.session_state:
    st.error(st.session_state.pop("input_error"))

max_stage = unlocked_stage(plan)
if "next_stage" in st.session_state:
    st.session_state.stage = st.session_state.pop("next_stage")
st.session_state.stage = min(st.session_state.stage, max_stage)
with st.sidebar:
    with st.expander("Review earlier steps"):
        stage = st.selectbox(
            "Journey stage",
            list(range(max_stage + 1)),
            format_func=lambda i: (
                f"{i + 1:02d}  {STAGES[i]}" + ("  ✓" if i < 8 and GATES[i] in plan.confirmations else "")
            ),
            key="stage",
        )
        st.progress(min(max_stage / 9, 1))
phase_number, phase_label = (
    (1, "Requirements and manpower")
    if stage <= 3
    else (2, "Monthly rates")
    if stage <= 5
    else (3, "Future cost changes")
    if stage == 6
    else (4, "Review findings")
    if stage == 7
    else (5, "Full contract budget")
)
st.caption(f"Decision {phase_number} of 5 · {phase_label}")
if stage == 4:
    reference_years = sorted({r["pricing_year"] for r in records})
    existing_years = {r.benchmark_year for r in plan.roles if r.included and r.benchmark_year is not None}
    desired_year = (
        next(iter(existing_years))
        if len(existing_years) == 1
        else (
            plan.profile.start_year
            or (plan.profile.start.year if plan.profile.start else reference_years[-1])
        )
    )
    default_year = desired_year if desired_year in reference_years else reference_years[-1]
    reference_year = st.selectbox(
        "Reference pricing year",
        reference_years,
        index=reference_years.index(default_year),
        key=f"rate_{plan.id}_common_year",
    )
    st.caption(
        "All references below use this pricing year and SGD inclusive monthly charges per head. No automatic time-normalisation is applied."
    )
    initialise_rates(plan, records, reference_year)
if "queued_guidance" in st.session_state:
    event = st.session_state.pop("queued_guidance")
    if cfg.api_key and cfg.model:
        request_guidance(event, stage, kind="next_question")


def confirmation(gate, label):
    if gate in plan.confirmations:
        st.success(
            f"{label} confirmed. You can revise this stage; affected later confirmations will be cleared."
        )
    errors = missing_for_gate(plan, gate)
    if errors:
        with st.expander("Inputs needed before confirmation", expanded=True):
            for error in errors:
                st.write(error)
    if st.button(f"Confirm {label}", key=f"confirm_{gate}", type="primary"):
        try:
            confirm(plan, gate, st.session_state.officer, records)
            st.session_state.next_stage = min(GATES.index(gate) + 1, 9)
            st.session_state.review_open = False
            st.rerun()
        except ValueError as e:
            st.error(str(e))


if stage <= 3:
    render_inputs(plan, cfg, request_guidance, stage, save)

left, right = st.container(), st.container()
with left:
    st.subheader("Assistant review" if stage <= 3 else f"Let’s work on {phase_label.lower()}")
    if stage <= 3 and not plan.chat:
        st.caption(
            "Select Review my manpower plan above when your first draft is ready. Any material follow-ups will appear here."
        )
    starters = [
        "Tell me your project brief: what the FM team should do, the start year and base/option years, any roles and quantities you already know, and what existing staff or contractors handle. Share everything you have; I’ll ask only about the remaining material gaps.",
        "Which duties should this team cover? Tell me which services other teams or contractors already handle.",
        "Which roles do you have in mind? For continuous coverage, describe the hours and number of simultaneous posts.",
        "Let’s check the proposed roles against the duties before considering prices. Is any responsibility missing or covered twice?",
        "We can now review monthly rates against the synthetic references. Tell me which role you want to start with.",
        "Review the first-year overview. Is there an assumption you would like to change before looking at future years?",
        "How should future prices be treated? We can review price schedules and clearly labelled officer assumptions.",
        "Let’s review the remaining gaps. Which finding would you like to address first?",
        "The contract overview brings the annual costs together. Ask about an amount or open the review to inspect charts and export evidence.",
        "Review the budget and its qualifications before recording your final confirmation.",
    ]
    if plan.chat:
        st.caption("Continue from your answers below. You can correct an earlier detail at any time.")
    with st.container(border=False):
        if not plan.chat and stage >= 4:
            with st.chat_message("assistant"):
                st.write(starters[stage])
        for m in plan.chat[-2:]:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        if len(plan.chat) > 2:
            with st.expander("Earlier conversation"):
                for old_message in plan.chat[:-2]:
                    st.write(old_message["content"])
    with st.expander("Add supporting documents, if you have any"):
        st.caption(
            "Optional. Your brief and manpower table are enough to start; attach a document only if it helps the review."
        )
        uploaded = st.file_uploader(
            "TXT, Markdown or text PDF (up to 5 MB)", type=["txt", "md", "pdf"], key="document"
        )
        if uploaded and st.button("Preserve document for review"):
            try:
                doc = preserve_document(uploaded.name, uploaded.getvalue())
                if not any(d["sha256"] == doc["sha256"] for d in plan.documents):
                    plan.documents.append(doc)
                    invalidate(
                        plan, "profile", "Added supporting document; review operational profile", officer()
                    )
                st.success("Original preserved. Extracted text is unvalidated and cannot enter benchmarks.")
            except ValueError as e:
                st.error(str(e))
        for d in plan.documents:
            st.caption(f"{d['name']}: {d['extraction_note']}")
            st.download_button(
                "Download preserved original",
                base64.b64decode(d["raw_base64"]),
                file_name=d["name"],
                key=d["sha256"],
            )
    st.caption(
        "Messages, attached project text and confirmation actions use OpenAI to guide the next decision. You approve each decision."
    )
    message = st.chat_input(
        "Describe, revise or ask a targeted question", disabled=not (cfg.api_key and cfg.model)
    )
    if message:
        request_guidance(message, stage)
        st.rerun()
    failed = st.session_state.get("failed_turn")
    if failed and failed["project_id"] == plan.id:
        st.warning(failed["error"])
        if failed["kind"] == "message":
            st.caption("Your message is kept below. Edit it if needed, then retry when ready.")
            retry_message = st.text_area(
                "Message kept for retry",
                value=failed["message"],
                key=f"retry_text_{failed['id']}",
                height=100,
            )
        else:
            st.caption(
                "Your confirmation is recorded. Retry to get the next question; you do not need to confirm again."
            )
            retry_message = failed["message"]
        if failed["stage"] != stage:
            st.info("The journey has moved on. Continue in the conversation using the current step.")
        elif st.button(
            "Retry message" if failed["kind"] == "message" else "Retry next question",
            key="retry_failed_message",
            disabled=not (retry_message.strip() and cfg.api_key and cfg.model),
        ):
            request_guidance(retry_message, stage, failed["kind"])
            st.rerun()
        if st.button("Dismiss retry", key="dismiss_failed_message"):
            st.session_state.pop("failed_turn", None)
            st.rerun()
    if plan.pending and (plan.review_checkpoint == "manpower" or stage >= 4):
        st.subheader("Ready for your review" if plan.review_checkpoint else "Here is what I understand")
        st.caption("Review this decision, or correct it in the conversation before confirming.")
        draft = working_draft(plan)
        if any(p["kind"] == "profile" for p in plan.pending):
            p = draft.profile
            st.write(f"**Site:** {p.operational_type or 'Unknown'} · {p.locations or 'Location unknown'}")
            st.write(
                f"**Contract:** {p.start or p.start_year or 'Start year unknown'} · "
                f"{p.base_years if p.base_years is not None else '?'} base years + "
                f"{p.option_years if p.option_years is not None else '?'} optional years"
            )
            st.write(f"**Operations:** {p.operating_hours or 'Opening/coverage hours unknown'}")
            st.write(f"**Assets:** {p.assets or 'Unknown; no equipment assumed'}")
        duties = [p["payload"] for p in plan.pending if p["kind"] == "responsibility"]
        if duties:
            st.dataframe(
                [{"Duty": d["description"], "Covered by": d["provider"] or d["coverage"]} for d in duties],
                hide_index=True,
                width="stretch",
            )
        roles = [p["payload"] for p in plan.pending if p["kind"] == "role"]
        if roles:
            rows = []
            officer_quantities = {r["id"]: r["quantity"] for r in plan.officer_manpower_input}
            for r in roles:
                row = {"Role": r["label"], "Quantity": r["quantity"], "Basis": r["quantity_reason"]}
                if r["id"] in officer_quantities and officer_quantities[r["id"]] != r["quantity"]:
                    row["Your entered quantity"] = officer_quantities[r["id"]]
                if "plan" in plan.confirmations:
                    row["Monthly rate (SGD)"] = r["rate"]
                if plan.review_checkpoint == "escalation":
                    row["Yearly changes (%)"] = [100 * x for x in r["escalation"]]
                    row["Future-price basis"] = r["escalation_reason"]
                rows.append(row)
            st.dataframe(rows, hide_index=True, width="stretch")
        decisions = [p["payload"] for p in plan.pending if p["kind"] == "decision"]
        if decisions:
            current = {f.id: f for f in findings(plan, records)}
            st.dataframe(
                [
                    {
                        "Finding": current[d["finding_id"]].message,
                        "Decision": d["status"],
                        "Your justification": d["justification"],
                    }
                    for d in decisions
                ],
                hide_index=True,
                width="stretch",
            )
        if plan.review_checkpoint:
            st.text_input(
                "Reviewing officer", key="officer", placeholder="Name recorded with your confirmation"
            )
        checkpoint_labels = {
            "requirements": "requirements",
            "manpower": "manpower plan",
            "rates": "monthly rates and base-year overview",
            "escalation": "future cost profile",
            "validation": "finding decisions",
        }
        action = (
            (
                "Confirm manpower plan and continue to rates"
                if plan.review_checkpoint == "manpower"
                else "Confirm " + checkpoint_labels[plan.review_checkpoint] + " and continue"
            )
            if plan.review_checkpoint
            else "Use these details"
        )
        if st.button(action, key="apply_reviewed_details", type="primary"):
            try:
                if plan.review_checkpoint:
                    checkpoint = plan.review_checkpoint
                    st.session_state.next_stage = accept_review(plan, st.session_state.officer, records)
                    if checkpoint != "manpower":
                        st.session_state.queued_guidance = f"Officer action: I confirmed the {checkpoint} decision in the interface. Lead me through the next decision; use my retained answers and ask only what is still needed."
                else:
                    apply_pending(plan, officer())
                st.session_state.review_open = st.session_state.get("next_stage", stage) >= 4
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        st.caption(
            "The assistant cannot approve your budget or update historical evidence. You confirm each decision."
        )
    context = journey_context(plan, STAGES[stage])
    ready = 5 <= stage < 7 and not context["applied_missing_inputs"] and not plan.pending
    if (ready or st.session_state.review_open) and not plan.review_checkpoint:
        st.text_input("Reviewing officer", key="officer", placeholder="Name recorded with your confirmation")
    if ready and not st.session_state.review_open:
        st.success("This step has the details needed for your review.")
        with st.expander("Review current step summary"):
            if stage == 0:
                st.dataframe(
                    [
                        {"Requirement": k.replace("_", " ").capitalize(), "Your details": str(v)}
                        for k, v in plan.profile.model_dump(mode="json").items()
                    ],
                    hide_index=True,
                    width="stretch",
                )
            elif stage == 1:
                st.dataframe(
                    [
                        {"Duty": r.description, "Covered by": r.provider or r.coverage, "Basis": r.evidence}
                        for r in plan.responsibilities
                    ],
                    hide_index=True,
                    width="stretch",
                )
            else:
                rows = []
                for r in plan.roles:
                    row = {
                        "Role": r.label,
                        "Included": r.included,
                        "Quantity": r.quantity,
                        "Deployment basis": r.quantity_reason,
                        "Duties": ", ".join(
                            d.description for d in plan.responsibilities if d.id in r.responsibility_ids
                        ),
                    }
                    if stage >= 4:
                        row.update({"Monthly rate (SGD)": r.rate, "Rate basis": r.rate_reason})
                    if stage == 6:
                        row.update(
                            {
                                "Yearly changes (%)": [100 * x for x in r.escalation],
                                "Future-price basis": r.escalation_reason,
                            }
                        )
                    rows.append(row)
                st.dataframe(rows, hide_index=True, width="stretch")
                st.caption("Open step review below for the detailed calculations, evidence and adjustments.")
        if st.button(
            "Confirm manpower plan and continue to rates" if stage in (2, 3) else "Confirm and continue",
            key="guided_confirm",
            type="primary",
        ):
            try:
                if stage in (2, 3):
                    prepared = prepare_review(plan, "manpower", records)
                    if not prepared["ready"]:
                        raise ValueError("Clarify the remaining manpower inputs in chat")
                    st.session_state.next_stage = accept_review(plan, st.session_state.officer, records)
                else:
                    confirm(plan, GATES[stage], st.session_state.officer, records)
                    st.session_state.next_stage = stage + 1
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    if stage >= 4 and st.button(
        "Hide step review" if st.session_state.review_open else "Review and confirm this step",
        key="review_step",
        type="primary" if not plan.pending else "secondary",
    ):
        st.session_state.review_open = not st.session_state.review_open
        st.rerun()

if stage <= 3 or not st.session_state.review_open:
    st.stop()


with right:
    st.divider()
    st.caption(
        f"{'Working proposal awaiting your confirmation' if plan.working_notes or plan.pending else budget_status(plan, records)} · Version {plan.version}"
    )
    st.subheader(STAGES[stage])
    if stage == 4:
        st.write(
            "Choose your monthly budgeting allowance. A supported arithmetic average is an editable starting point; unsupported roles need your own assumption."
        )
        summaries = []
        for r in plan.roles:
            if not r.included:
                continue
            bm = rate_benchmark(records, r.mapped_role, reference_year, r.benchmark_status, r.benchmark_scope)
            summaries.append(
                {
                    "Role": r.label,
                    "Quantity / FTE": r.quantity,
                    "Minimum (SGD)": bm["minimum"],
                    "Average (SGD)": bm["average"],
                    "Maximum (SGD)": bm["maximum"],
                    "Selected monthly rate (SGD)": r.rate,
                    "Reference": f"{bm['sample_count']} synthetic schedules"
                    if bm["available"]
                    else "No benchmark; officer assumption",
                }
            )
        st.dataframe(
            summaries,
            hide_index=True,
            width="stretch",
            column_config={
                name: st.column_config.NumberColumn(format="%.2f")
                for name in ["Minimum (SGD)", "Average (SGD)", "Maximum (SGD)", "Selected monthly rate (SGD)"]
            },
        )
        for r in plan.roles:
            if not r.included:
                continue
            bm = rate_benchmark(records, r.mapped_role, reference_year, r.benchmark_status, r.benchmark_scope)
            prefix = f"rate_{plan.id}_{r.id}_{reference_year}"
            st.markdown(f"**{r.label} · quantity {r.quantity:g}**")
            if not bm["available"]:
                st.info(
                    "No sufficient comparable benchmark in the active synthetic dataset. Enter an officer-supplied monthly manpower allowance; an inventory title alone does not provide a validated rate."
                )
            else:
                st.caption(
                    f"Synthetic minimum {bm['minimum']:,.2f} · arithmetic average {bm['average']:,.2f} · maximum {bm['maximum']:,.2f} · {bm['sample_count']} distinct schedules priced in {reference_year}."
                )
            initial = float(r.rate or 0)
            upper = float(
                max(10000, math.ceil(initial / 1000) * 1000, math.ceil((bm["maximum"] or 0) / 1000) * 1000)
            )
            a, b = st.columns([3, 1])
            a.slider(
                "Monthly rate (SGD per head)",
                min_value=0.0,
                max_value=upper,
                value=initial,
                step=10.0,
                key=prefix + "_slider",
                on_change=changed_role,
                args=(r.id, "rate", prefix + "_slider", prefix + "_number"),
            )
            b.number_input(
                "Exact monthly rate",
                min_value=0.0,
                max_value=10000000.0,
                value=initial,
                step=1.0,
                format="%.2f",
                key=prefix + "_number",
                on_change=changed_role,
                args=(r.id, "rate", prefix + "_number", prefix + "_slider"),
            )
            if r.rate and bm["available"] and (r.rate < bm["minimum"] or r.rate > bm["maximum"]):
                st.warning(
                    "Selected allowance is outside the observed synthetic minimum–maximum. Check that this is intentional; you may retain it."
                )
            with st.expander(f"{r.label}: sources, sample count and limitations"):
                st.caption(
                    f"Pricing year {reference_year}; {r.benchmark_status}; scope {r.benchmark_scope or 'all active scopes'}. Average is the arithmetic mean of distinct comparable schedule records."
                )
                st.caption(bm["method"] + " " + bm["limitations"])
                st.dataframe(
                    [
                        {
                            k: row[k]
                            for k in [
                                "record_id",
                                "schedule_id",
                                "source",
                                "pricing_year",
                                "unit_rate_monthly",
                                "scope",
                                "award_status",
                                "rate_basis",
                                "data_origin",
                            ]
                        }
                        for row in bm["records"]
                    ],
                    hide_index=True,
                    width="stretch",
                )
                st.text_area(
                    "Budget assumption notes (optional)",
                    r.rate_notes,
                    key=prefix + "_reason",
                    on_change=changed_role,
                    args=(r.id, "rate_notes", prefix + "_reason"),
                )
        try:
            overview = preliminary(plan)
            st.metric("Preliminary first-year cost (SGD)", f"{overview['year_1']:,.2f}")
            st.caption(overview["label"])
        except ValueError:
            st.caption("Enter each unsupported role's rate to see the first-year total.")
        if st.button("Confirm monthly rates and continue", key="confirm_rates", type="primary"):
            try:
                result = prepare_review(plan, "rates", records)
                if not result["ready"]:
                    raise ValueError(
                        "; ".join(
                            result.get("missing_inputs", [result.get("action", "Review remaining inputs")])
                        )
                    )
                st.session_state.next_stage = accept_review(plan, st.session_state.officer, records)
                st.session_state.review_open = True
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    elif stage == 5:
        try:
            overview = preliminary(plan)
            a, b = st.columns(2)
            a.metric("Monthly manpower cost (SGD)", f"{overview['monthly']:,.2f}")
            b.metric("First-year manpower cost (SGD)", f"{overview['year_1']:,.2f}")
            st.dataframe(overview["rows"], hide_index=True, width="stretch")
            st.info(overview["label"])
        except ValueError as e:
            st.error(str(e))
        confirmation("base", "preliminary base-year overview")

    elif stage == 6:
        st.write(
            "Select changes for the actual contract period. Historical future quotes reflect implied tender-price expectations; causes are unknown."
        )
        for r in plan.roles:
            if not r.included:
                continue
            prefix = f"esc_{plan.id}_{r.id}"
            with st.expander(r.label, expanded=True):
                eb = escalation_benchmark(records, r.mapped_role, r.benchmark_status, r.benchmark_scope)
                if eb["available"]:
                    st.info(
                        f"{eb['sample_count']} distinct schedules; median schedule YoY {eb['median']:.2%}; typical {eb['p25']:.2%}–{eb['p75']:.2%}; full {eb['minimum']:.2%}–{eb['maximum']:.2%}."
                    )
                else:
                    st.info("Insufficient comparable escalation schedules; no range supplied.")
                with st.expander("Schedules, yearly changes and limitations"):
                    st.write(eb["method"])
                    st.write(eb["limitations"])
                    st.dataframe(eb["schedules"], hide_index=True, width="stretch")
                    st.dataframe(eb["changes"], hide_index=True, width="stretch")
                    st.dataframe(eb["issues"], hide_index=True)
                mode = st.radio(
                    "Future rate method",
                    ["assumption", "quoted schedule"],
                    index=0 if r.escalation_mode == "assumption" else 1,
                    key=prefix + "_mode",
                )
                if mode == "assumption":
                    current = r.escalation[1] * 100 if len(r.escalation) > 1 else 0.0
                    value = st.slider(
                        "Constant annual change (%) for a disclosed scenario",
                        min_value=-50.0,
                        max_value=100.0,
                        value=float(current),
                        step=0.1,
                        key=prefix + "_slider",
                        on_change=changed_role,
                        args=(
                            r.id,
                            "escalation",
                            prefix + "_slider",
                            prefix + "_number",
                            lambda x: [0.0] + [x / 100] * (plan.profile.years - 1),
                        ),
                    )
                    st.number_input(
                        "Precise constant change (%)",
                        min_value=-50.0,
                        max_value=100.0,
                        value=float(value),
                        step=0.1,
                        key=prefix + "_number",
                        on_change=changed_role,
                        args=(
                            r.id,
                            "escalation",
                            prefix + "_number",
                            prefix + "_slider",
                            lambda x: [0.0] + [x / 100] * (plan.profile.years - 1),
                        ),
                    )
                    st.caption(
                        "Moving a constant control replaces the whole assumed profile. Use yearly changes below when the basis differs by year."
                    )
                    with st.form(prefix + "_yearly"):
                        profile_text = st.text_input(
                            "Role-specific yearly changes (%), starting with 0 for Year 1",
                            ", ".join(f"{e * 100:g}" for e in r.escalation),
                        )
                        reason = st.text_area(
                            "Evidence / reason for the selected profile", r.escalation_reason
                        )
                        if st.form_submit_button("Apply yearly escalation profile"):
                            try:
                                changes = [float(x.strip()) / 100 for x in profile_text.split(",")]
                                if len(changes) != plan.profile.years or changes[0] != 0:
                                    raise ValueError("Enter one change per contract year; Year 1 must be 0")
                                payload = r.model_dump(mode="json")
                                payload.update(
                                    escalation=changes,
                                    escalation_reason=reason,
                                    escalation_mode="assumption",
                                    schedule_id=None,
                                )
                                apply_change(
                                    plan, "role", payload, "Officer selected yearly escalation", officer()
                                )
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                else:
                    schedules = [s["schedule_id"] for s in eb["schedules"]]
                    if not schedules:
                        st.warning("No quoted schedules for this mapped role/filter.")
                    else:
                        sid = st.selectbox("Synthetic quoted schedule", schedules, key=prefix + "_schedule")
                        st.caption(
                            "Using a quote requires full target-year coverage, a 1 January contract start and an equal target-year base rate. No extra general escalation is applied."
                        )
                        if st.button("Use quoted prices without extra escalation", key=prefix + "_quote"):
                            payload = r.model_dump(mode="json")
                            payload.update(
                                escalation=[0.0] * plan.profile.years,
                                escalation_mode="quoted schedule",
                                schedule_id=sid,
                                escalation_reason=f"Retrieved synthetic target-year prices from {sid}; no double escalation",
                            )
                            apply_change(
                                plan, "role", payload, "Officer selected quoted future prices", officer()
                            )
                            st.rerun()
                with st.expander("Component policy adjustments, if separately evidenced"):
                    st.caption(
                        "Use an evidenced absolute monthly amount for an affected component. It is additive, prorated by days from its effective date, and does not itself receive general escalation. No automatic wage-to-inclusive-rate conversion."
                    )
                    if r.policies:
                        st.dataframe([p.model_dump(mode="json") for p in r.policies], hide_index=True)
                    with st.form(prefix + "_policy"):
                        name = st.text_input("Policy / adjustment name")
                        effective = st.date_input("Effective date", value=None)
                        amount = st.number_input(
                            "Additional monthly amount per head (SGD)", min_value=0.01, value=None
                        )
                        component = st.text_input("Affected component and conversion basis")
                        source = st.text_input("Source document / URL (officer supplied, unverified)")
                        basis_ok = st.checkbox("I confirm the amount's component-to-inclusive-cost basis")
                        overlap_ok = st.checkbox(
                            "I reviewed overlap with general increases and existing future quotes"
                        )
                        if st.form_submit_button("Add evidenced adjustment"):
                            try:
                                policy = PolicyAdjustment(
                                    name=name,
                                    effective_date=effective,
                                    annual_monthly_increment=amount,
                                    affected_component=component,
                                    source=source,
                                    basis_confirmed=basis_ok,
                                    overlap_reviewed=overlap_ok,
                                )
                                payload = r.model_dump(mode="json")
                                payload["policies"].append(policy.model_dump(mode="json"))
                                apply_change(
                                    plan, "role", payload, "Officer added component adjustment", officer()
                                )
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    if r.policies and st.button(
                        "Remove selected role's policy adjustments", key=prefix + "_remove"
                    ):
                        payload = r.model_dump(mode="json")
                        payload["policies"] = []
                        apply_change(
                            plan, "role", payload, "Officer removed component adjustments", officer()
                        )
                        st.rerun()
        try:
            result = budget(plan, records)
            st.metric("Current full contract scenario (SGD)", f"{result['contract_total']:,.2f}")
        except ValueError as e:
            st.warning(str(e))
        confirmation("escalation", "future cost profile")

    elif stage == 7:
        current = findings(plan, records)
        st.write(
            "Resolve inputs by revising earlier stages, record an exception or retain an unresolved risk. Invalid arithmetic remains blocking."
        )
        for f in current:
            with st.expander(f"{'Blocking' if f.blocking else f.status.title()}: {f.message}", expanded=True):
                st.write(f.impact)
                if f.evidence:
                    st.caption(f.evidence)
                if f.blocking:
                    st.error("Revise required inputs. This finding cannot be accepted as an exception.")
                    continue
                with st.form(f"finding_{f.id}_{f.fingerprint}"):
                    statuses = ["unresolved risk", "accepted exception", "data limitation"]
                    status = st.selectbox(
                        "Decision", statuses, index=statuses.index(f.status) if f.status in statuses else 0
                    )
                    justification = st.text_area(
                        "Officer justification",
                        ""
                        if f.justification == "Officer justification was not provided."
                        else f.justification,
                    )
                    inclusion = st.text_input("Cost inclusion / exclusion / impact treatment", f.inclusion)
                    further = st.text_input("Further approval required (if any)", f.further_approval)
                    if st.form_submit_button("Record decision"):
                        try:
                            record_decision(plan, f, status, justification, officer(), inclusion, further)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
        with st.expander("Resolved findings and previous decisions"):
            st.dataframe(
                [
                    {
                        "Finding": f.message,
                        "Status": f.status,
                        "Officer": f.officer,
                        "Decision": f.justification,
                    }
                    for f in finding_history(plan, current)
                ],
                hide_index=True,
            )
            st.dataframe(
                [{k: h.get(k, "") for k in ["time", "officer", "action", "version"]} for h in plan.history],
                hide_index=True,
            )
        confirmation("validation", "validation review")

    elif stage in (8, 9):
        try:
            result = budget(plan, records)
            a, b, c = st.columns(3)
            a.metric("Full contract (SGD)", f"{result['contract_total']:,.2f}")
            b.metric("Base period (SGD)", f"{result['base_total']:,.2f}")
            c.metric("Optional period (SGD)", f"{result['option_total']:,.2f}")
            frame = pd.DataFrame(result["rows"])
            wide = frame.pivot(index="role", columns="year", values="annual_cost")
            wide.columns = [
                f"Year {y}" + (" (option)" if y > plan.profile.base_years else "") for y in wide.columns
            ]
            wide["Contract total"] = wide.sum(axis=1)
            st.dataframe(wide, width="stretch")
            year_labels = [
                f"Year {i + 1}" + (" (option)" if i >= plan.profile.base_years else "")
                for i in range(plan.profile.years)
            ]
            fig = go.Figure(
                go.Bar(
                    x=year_labels,
                    y=result["annual_totals"],
                    marker_color=[
                        "#147D74" if i < plan.profile.base_years else "#8CABB9"
                        for i in range(plan.profile.years)
                    ],
                )
            )
            fig.update_layout(
                title="Annual manpower costs",
                yaxis_title="SGD",
                height=330,
                margin=dict(l=15, r=15, t=50, b=20),
            )
            st.plotly_chart(fig, width="stretch")
            waterfall = result["waterfall"]
            wf = go.Figure(
                go.Waterfall(
                    x=["Flat baseline"]
                    + [f"Year {i + 1} excess" for i in range(plan.profile.years)]
                    + ["Contract total"],
                    measure=["absolute"] + ["relative"] * plan.profile.years + ["total"],
                    y=[waterfall["baseline"]] + waterfall["additions"] + [0],
                    increasing={"marker": {"color": "#147D74"}},
                    decreasing={"marker": {"color": "#DB7658"}},
                    totals={"marker": {"color": "#172B42"}},
                )
            )
            wf.update_layout(
                title="Escalation to full contract value",
                yaxis_title="SGD",
                height=360,
                margin=dict(l=15, r=15, t=50, b=20),
            )
            st.plotly_chart(wf, width="stretch")
            st.caption(waterfall["method"])
            try:
                st.dataframe(sensitivity(plan, records), hide_index=True, width="stretch")
            except ValueError as e:
                st.warning(f"Sensitivity unavailable: {e}")
            with st.expander("Annual calculations, assumptions and exclusions"):
                st.dataframe(frame, hide_index=True, width="stretch")
                st.caption(result["rounding"])
                st.caption(result["period_basis"])
                st.write("Excluded costs: " + plan.profile.exclusions)
                st.write(
                    "Policies use confirmed nominal additive component amounts, prorated by effective date; no general escalation is applied to those additions."
                )
            current = findings(plan, records)
            for f in current:
                st.warning(f"{f.status}: {f.message} {f.justification}")
            st.download_button(
                "Download "
                + ("confirmed" if "final" in plan.confirmations else "draft")
                + " Excel evidence workbook",
                export_excel(plan, records),
                file_name=f"fm-budget-v{plan.version}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
            st.caption(
                "Includes operational inputs, manpower plan, rates, escalation, annual formulas, sensitivity, decisions, sources and charts."
            )
            if stage == 8 and st.button("Continue to officer confirmation"):
                st.session_state.next_stage = 9
                st.rerun()
            if stage == 9:
                st.write(
                    "A confirmed budget requires all planning confirmations, valid calculations and recorded finding decisions with justifications. Synthetic evidence and accepted exceptions remain qualifications."
                )
                if st.button("Confirm full contract budget", disabled="final" in plan.confirmations):
                    try:
                        confirm(plan, "final", st.session_state.officer, records)
                        save()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                if "final" in plan.confirmations:
                    st.success(
                        f"{budget_status(plan, records)} · officer {plan.final_officer} · {plan.final_date}"
                    )
        except ValueError as e:
            st.error(str(e))
            st.info(
                "Revise the affected inputs before exporting a numeric budget. Your project snapshot remains available."
            )
