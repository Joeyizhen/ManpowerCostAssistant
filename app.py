"""Track 1 review app. Start: uv run streamlit run app.py"""
# ruff: noqa: E402 -- recover cached development helpers before importing their UI symbols

import base64
import hashlib
import importlib
from uuid import uuid4

import streamlit as st

import services.runtime_compat  # noqa: F401 -- recover stale development imports without losing sessions

importlib.reload(services.runtime_compat)
import ui_drafts
from future_inputs import future_screen
from hybrid_inputs import (
    confirmation_errors,
    navigation,
    render_inputs,
    show_missing,
    show_progress,
    step_for_stage,
)
from journey_inputs import commit_rows, pending_control_errors, project_prefix
from pricing_inputs import starting_prices
from services.agent import AgentError, converse, create_client
from services.calculations import preliminary
from services.config import settings
from services.demo import demo_plan
from services.evidence import (
    load_records,
)
from services.hybrid import comparison_rows, initialise_rates
from services.journey import accept_review, working_draft
from services.manpower_checks import LOCAL_ACTOR
from services.models import GATES, STAGES, Plan
from services.storage import ConflictError, Store
from services.uploads import preserve_document
from services.workflow import (
    apply_change,
    apply_pending,
    budget_status,
    confirm,
    findings,
    invalidate,
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
ui_drafts.restore(st.session_state.plan)
# Keep the officer identity when its input is hidden between guided steps or on the welcome screen.
st.session_state.officer = st.session_state.get("officer", "") or LOCAL_ACTOR
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
            st.caption("TRACK 2")
            st.subheader("Review a proposed plan")
            st.write(
                "Add a proposed budget, check its figures and assumptions, then view the reviewed budget."
            )
            if st.button("Review proposed plan", key="choose_track_2", width="stretch"):
                st.session_state.selected_track = 2
                st.rerun()
    st.caption(
        "This review release uses labelled synthetic evidence. Your current draft is retained when switching tracks."
    )
    st.stop()

if st.session_state.selected_track == 2:
    from proposal_inputs import render as render_proposal

    render_proposal(cfg, store, owner)
    st.stop()

records = load_records()
plan = st.session_state.plan


def officer():
    return st.session_state.officer.strip() or "Local reviewing officer"


def sync_controls(prefix, signature, values):
    """Refresh stale widgets after a retained/model/form change, before rendering them."""
    if st.session_state.get(prefix + "_model") != signature:
        for suffix, value in values.items():
            st.session_state[prefix + suffix] = value
        st.session_state[prefix + "_model"] = signature
    ui_drafts.restore_controls_after_sync(st.session_state.plan, prefix)


def changed_role(role_id, field, widget_key, other_key=None, transform=None, explicit=False):
    r = next(x for x in st.session_state.plan.roles if x.id == role_id)
    payload = r.model_dump(mode="json")
    value = st.session_state[widget_key]
    if transform:
        value = transform(value)
    payload[field] = value
    if payload == r.model_dump(mode="json") and not explicit:
        return
    if field == "escalation":
        payload["escalation_mode"] = "assumption"
        payload["pwm"] = None
        payload["schedule_id"] = None
        payload["escalation_reason"] = (
            f"Officer selected constant annual change of {value[1]:.2%}; "
            "budget scenario assumption, not an observed outcome."
            if len(value) > 1
            else "Single-year contract; no future annual change."
        )
    if field == "rate":
        payload["rate_origin"] = "Officer assumption"
        payload["rate_reason"] = (
            f"Officer budgeting allowance: SGD {value:,.2f} inclusive monthly per head; editable assumption."
            if value is not None
            else ""
        )
    try:
        apply_change(st.session_state.plan, "role", payload, f"Revised {r.label}: {field}", officer())
        if other_key:
            st.session_state[other_key] = st.session_state[widget_key] or 0.0
    except ValueError as e:
        st.session_state.ui_error = str(e)


def fingerprint(project):
    return hashlib.sha256(
        project.model_dump_json(exclude={"ui_step", "input_steps_completed"}).encode()
    ).hexdigest()


if "saved_fingerprint" not in st.session_state:
    try:
        saved_plan, _ = store.load(plan.id, owner)
        st.session_state.saved_fingerprint = fingerprint(saved_plan)
    except ValueError:
        st.session_state.saved_fingerprint = fingerprint(Plan(id=plan.id))


def unsaved():
    return (
        fingerprint(st.session_state.plan) != st.session_state.saved_fingerprint
        or bool(st.session_state.get(project_prefix(st.session_state.plan) + "_error"))
        or ui_drafts.unsaved(st.session_state.plan, pending_control_errors(st.session_state.plan))
    )


def new_session(new_plan, revision=0):
    # Clear project-dependent widget state when switching projects, to avoid stale sliders/approvals.
    for key in list(st.session_state):
        if key.startswith(
            (
                "six_",
                "hybrid_",
                "role_",
                "rate_",
                "esc_",
                "profile_",
                "finding_",
                "resp_",
                "confirm_",
                "common_future_",
                "future_",
                "pwm_",
                "basis_",
                "pricing_",
            )
        ):
            del st.session_state[key]
    st.session_state.plan = new_plan
    st.session_state.pop("next_stage", None)
    st.session_state.pop("delete_project_target", None)
    st.session_state.storage_revision = revision
    st.session_state.saved_fingerprint = (
        fingerprint(new_plan) if revision else fingerprint(Plan(id=new_plan.id))
    )
    st.session_state.pop("switch_target", None)
    if new_plan.ui_step is None:
        new_plan.ui_step = 0
    st.session_state.stage = 0
    st.session_state.review_open = False


def save():
    error = st.session_state.get(project_prefix(st.session_state.plan) + "_error")
    if error:
        st.error("Correct these entries before saving: " + error)
        return False
    try:
        ui_drafts.capture(st.session_state.plan, pending_control_errors(st.session_state.plan))
        st.session_state.storage_revision = store.save(
            st.session_state.plan, owner, st.session_state.storage_revision
        )
        st.session_state.saved_fingerprint = fingerprint(st.session_state.plan)
        st.success("Saved project and revision history. Saving does not confirm any planning decision.")
        return True
    except ConflictError as e:
        st.error(str(e))
    except Exception:
        st.error(
            "Save failed. Download a project snapshot to preserve your work; check storage configuration."
        )

    return False


def example_project():
    example = demo_plan()
    rows = comparison_rows(example)
    for row in rows:
        if row["Proposed quantity / FTE"] is None:
            row["Proposed quantity / FTE"] = 0.0
            row["Quantity basis"] = "headcount"
    commit_rows(example, rows)
    return example


def switch_project(new_plan, revision=0):
    if unsaved():
        st.session_state.switch_target = {"plan": new_plan, "revision": revision}
    else:
        new_session(new_plan, revision)
    st.rerun()


def request_guidance(message, current_stage, kind="message"):
    """Keep failed input outside approved facts, with an explicit retry rather than an automatic repeat."""
    try:
        with st.spinner("Thinking…"):
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
    project_status = st.empty()
    if "project_notice" in st.session_state:
        st.success(st.session_state.pop("project_notice"))
    if st.button("Change track", key="change_track", width="stretch"):
        st.session_state.selected_track = None
        st.rerun()
    if st.button("New blank project", width="stretch"):
        switch_project(Plan())
    if st.button("Load synthetic example", width="stretch"):
        switch_project(example_project())
    st.caption("The example contains invented officer inputs. Review and confirm every stage.")
    saved = store.list(owner)
    if saved:
        selected = st.selectbox(
            "Saved projects", saved, format_func=lambda x: f"{x['name']} · saved revision {x['revision']}"
        )
        if st.button("Resume selected project", width="stretch"):
            loaded, revision = store.load(selected["id"], owner)
            switch_project(loaded, revision)
        if st.button("Delete selected project", key="delete_project", width="stretch"):
            st.session_state.delete_project_target = dict(selected)
            st.rerun()
        target = st.session_state.get("delete_project_target")
        if target:
            st.warning(f"Delete ‘{target['name']}’ and all its saved revisions? This cannot be undone.")
            if target["id"] == plan.id:
                st.caption("This is the open project. Deleting it will also close its current draft.")
            yes, no = st.columns(2)
            if yes.button("Confirm deletion", key="confirm_delete_project", type="primary"):
                try:
                    store.delete(target["id"], owner, target["revision"])
                    if target["id"] == plan.id:
                        new_session(Plan())
                    st.session_state.pop("delete_project_target", None)
                    st.session_state.project_notice = f"Deleted ‘{target['name']}’."
                    st.rerun()
                except ConflictError as error:
                    st.session_state.pop("delete_project_target", None)
                    st.error(str(error))
                except Exception:
                    st.error("Deletion failed. The project was not removed; check storage configuration.")
            if no.button("Cancel", key="cancel_delete_project"):
                st.session_state.pop("delete_project_target", None)
                st.rerun()
    if st.button("Save project", width="stretch"):
        if save():
            st.rerun()
    switch_target = st.session_state.get("switch_target")
    if switch_target:
        st.warning(
            "You have unsaved changes. Save them or explicitly discard them before switching projects."
        )
        if st.button("Save and switch", key="save_and_switch"):
            if save():
                target = switch_target["plan"]
                if target.id == st.session_state.plan.id:
                    target, revision = store.load(target.id, owner)
                else:
                    revision = switch_target["revision"]
                new_session(target, revision)
                st.rerun()
        if st.button("Discard edits and switch", key="discard_and_switch"):
            new_session(switch_target["plan"], switch_target["revision"])
            st.rerun()
        if st.button("Keep editing", key="cancel_switch"):
            st.session_state.pop("switch_target", None)
            st.rerun()
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
                switch_project(loaded)
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


def show_save_status():
    project_status.caption(
        "Unsaved changes"
        if unsaved()
        else (
            f"Saved · revision {st.session_state.storage_revision}"
            if st.session_state.storage_revision
            else "New draft · not yet saved"
        )
    )


show_save_status()

st.caption("AI-POWERED FM MANPOWER COST ASSISTANT")
st.title("Build a new manpower plan")
st.caption("TRACK 1 · BUILD NEW PLAN")
project_name = working_draft(plan).profile.name
if project_name != "Untitled project":
    st.caption(f"Project: {project_name}")
if "ui_error" in st.session_state:
    st.error(st.session_state.pop("ui_error"))
if "input_error" in st.session_state:
    st.error(st.session_state.pop("input_error"))

if "next_stage" in st.session_state:
    plan.ui_step = step_for_stage(st.session_state.pop("next_stage"))
show_progress(plan)
ui_step = plan.ui_step
stage = [0, 2, 3, 4, 6, 7][ui_step]
st.session_state.stage = stage
phase_label = [
    "Project and contract details",
    "Current and proposed manpower",
    "Assistant review",
    "Monthly rates",
    "Future cost changes",
    "Full contract budget and export",
][ui_step]
st.session_state.review_open = ui_step >= 3
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
    contract_year = plan.profile.start_year or (plan.profile.start.year if plan.profile.start else None)
    if contract_year and reference_year != contract_year:
        st.warning(
            f"References are priced in {reference_year}; the contract starts in {contract_year}. No inflation or time adjustment has been applied. Select and document an explicit allowance for the intended contract period."
        )


def confirmation(gate, label, primary=True):
    if gate in plan.confirmations:
        st.success(
            f"{label} confirmed. You can revise this stage; affected later confirmations will be cleared."
        )
    errors = confirmation_errors(plan, st.session_state.officer, records, gate=gate)
    if errors:
        with st.expander("Inputs needed before confirmation", expanded=True):
            for error in errors:
                st.write(error)
    if st.button(
        f"Confirm {label}",
        key=f"confirm_{gate}",
        type="primary" if primary else "secondary",
        disabled=bool(errors),
    ):
        try:
            confirm(plan, gate, st.session_state.officer, records)
            st.session_state.next_stage = min(GATES.index(gate) + 1, 9)
            plan.ui_step = step_for_stage(st.session_state.next_stage)
            save()
            st.session_state.review_open = False
            st.rerun()
        except ValueError as e:
            st.error(str(e))


if stage <= 3:
    render_inputs(plan, cfg, request_guidance, stage, save)
if ui_step <= 1:
    navigation(plan)
    show_save_status()
    st.stop()

left, right = st.container(), st.container()
with (
    st.expander(
        "Discuss changes or ask the assistant",
        expanded=bool(st.session_state.get("manpower_help_open") or plan.pending),
    )
    if ui_step == 2
    else st.expander(
        "Ask about this budget" if ui_step == 5 else "Ask the assistant or add supporting documents"
    )
):
    if ui_step == 5:
        st.caption("Ask why costs change, what an assumption means, or what still needs checking.")
    elif ui_step >= 3:
        st.subheader(f"Ask about {phase_label.lower()}")
    elif not plan.chat:
        st.caption(
            "Ask about a discrepancy or describe the change you are considering. Your recorded answers are retained."
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
        "Sending a message or requesting a review uses OpenAI. Editing, navigation and confirmations make no automatic API call."
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
                placeholder="",
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
            st.dataframe(rows, hide_index=True, width="stretch", placeholder="")
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
                placeholder="",
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
        errors = (
            confirmation_errors(plan, st.session_state.officer, records, checkpoint=plan.review_checkpoint)
            if plan.review_checkpoint
            else []
        )
        show_missing(errors)
        if st.button(action, key="apply_reviewed_details", type="primary", disabled=bool(errors)):
            try:
                if plan.review_checkpoint:
                    st.session_state.next_stage = accept_review(plan, st.session_state.officer, records)
                    plan.ui_step = step_for_stage(st.session_state.next_stage)
                    save()
                else:
                    apply_pending(plan, officer())
                st.session_state.review_open = st.session_state.get("next_stage", stage) >= 4
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        st.caption(
            "The assistant cannot approve your budget or update historical evidence. You confirm each decision."
        )

if ui_step <= 2:
    navigation(plan)
    show_save_status()
    st.stop()


with right:
    st.divider()
    if ui_step not in (4, 5):
        st.caption(
            f"{'Working proposal awaiting your confirmation' if plan.working_notes or plan.pending else budget_status(plan, records)} · Version {plan.version}"
        )
    if stage == 4:
        starting_prices(plan, records, officer(), save, sync_controls)

    elif stage == 5:
        try:
            overview = preliminary(plan)
            a, b = st.columns(2)
            a.metric("Monthly manpower cost (SGD)", f"{overview['monthly']:,.2f}")
            b.metric("First-year manpower cost (SGD)", f"{overview['year_1']:,.2f}")
            st.dataframe(overview["rows"], hide_index=True, width="stretch", placeholder="")
            st.info(overview["label"])
        except ValueError as e:
            st.error(str(e))
        confirmation("base", "preliminary base-year overview")

    elif stage == 6:
        future_screen(plan, records, officer(), save)

    if ui_step == 5:
        from review_inputs import final_review

        final_review(plan, records, officer(), save, sync_controls)


navigation(plan)

show_save_status()
