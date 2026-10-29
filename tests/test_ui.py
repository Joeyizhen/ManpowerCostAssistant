"""Input-first Streamlit journeys using synthetic fixtures and mocked LLM replies."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from services.evidence import load_records
from services.journey import prepare_review, update_notes, working_draft
from services.workflow import findings, record_decision


def blank(monkeypatch, tmp_path, live=False):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ui.db'}")
    monkeypatch.setenv("DEPLOYMENT_MODE", "local")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-credential" if live else "")
    monkeypatch.setenv("OPENAI_MODEL", "test-model" if live else "")
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=90).run()
    at.button(key="activity_budgeting").click().run()
    at.button(key="choose_track_1").click().run()
    assert not at.exception
    return at


def button(at, label):
    return next(
        b
        for b in at.button
        if b.label == label or (label == "Confirm full contract budget" and b.key == "confirm_final_budget")
    )


def role_picker(at):
    return next(m for m in at.selectbox if m.label == "Add another role")


def fill_project(at):
    next(
        t
        for t in at.text_area
        if t.label == "Describe the properties and operating conditions the FM team will manage"
    ).set_value("Invented office FM team, weekday workload allowances; separate specialist contracts.").run()
    next(t for t in at.text_input if t.label == "Anticipated start month").set_value("Jan 2028").run()
    next(t for t in at.text_input if t.label == "Base term (years)").set_value("2").run()
    next(t for t in at.text_input if t.label == "Option term (years)").set_value("2").run()
    at.button(key="six_continue").click().run()
    next(r for r in at.radio if r.label == "Deployment context").set_value("New site / service").run()
    assert not at.exception and at.session_state["plan"].ui_step == 1
    return at


def fill_table(at, titles, quantities):
    fill_project(at)
    known = set(at.dataframe[0].value["Role title"]) if at.dataframe else set()
    for title in [t for t in titles if t not in known]:
        if title in role_picker(at).options:
            role_picker(at).set_value(title).run()
            at.button(key="add_selected_roles").click().run()
        else:
            seed_retained_role(at, title)
    key = role_picker(at).key.removesuffix("_add") + "_table"
    selected = dict(zip(titles, quantities, strict=True))
    at.session_state[key] = {
        "edited_rows": {
            i: {
                "Proposed quantity / FTE": selected.get(title, 0),
                "Quantity basis": "FTE" if not float(selected.get(title, 0)).is_integer() else "headcount",
                "Duties / deployment notes": "Synthetic weekday operations require dedicated coverage for tenant enquiries and equipment response"
                if title in selected
                else "",
            }
            for i, title in enumerate(at.dataframe[0].value["Role title"])
        },
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "Save draft").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 1
    return at


def seed_retained_role(at, title):
    """Legacy saved titles remain editable after removing the new unlisted-role form."""
    from journey_inputs import commit_rows
    from services.hybrid import comparison_rows

    p = at.session_state["plan"]
    rows = comparison_rows(p, common=False, include_pending=False)
    rows.append({"id": "retained-" + str(len(rows)), "Role title": title, "Quantity basis": "headcount"})
    commit_rows(p, rows)
    at.session_state["six_epoch"] = at.session_state.get("six_epoch", 0) + 1
    at.run()


def ready_guide(plan, records, message, client, model, stage):
    from services.models import Responsibility

    draft = working_draft(plan)
    duties, roles = [], []
    for r in draft.roles:
        if not r.included:
            continue
        duties.append(
            Responsibility(
                id="duty-" + r.id,
                description=r.duties_notes or "Officer accepted operational duties",
                coverage="plan",
            ).model_dump()
        )
        roles.append({**r.model_dump(mode="json"), "responsibility_ids": ["duty-" + r.id]})
    update_notes(plan, responsibilities=duties, roles=roles)
    assert prepare_review(plan, "manpower", records)["ready"]
    plan.chat.extend(
        [
            {"role": "user", "content": message},
            {
                "role": "assistant",
                "content": "Review this manpower decision, then confirm to continue to rates.",
            },
        ]
    )
    return plan.chat[-1]["content"]


def give_basis(at, kind):
    if kind == "rate":
        for item in list(at.text_area):
            if item.key and item.key.startswith("rate_") and item.key.endswith("_rationale"):
                at.text_area(key=item.key).set_value(
                    "Synthetic quotation covers the unchanged inclusive manpower scope"
                ).run()
        for item in list(at.text_area):
            if item.label == "Reference-year treatment":
                at.text_area(key=item.key).set_value(
                    "Retain reference-year allowances without extra inflation as a disclosed budget assumption"
                ).run()
        return at
    p = at.session_state["plan"]
    prefix = f"basis_{p.id}_{kind}"
    if not any(b.key == prefix + "_record" for b in at.button):
        return at
    at.multiselect(key=prefix + "_roles").set_value(
        [r.id for r in working_draft(p).roles if r.included]
    ).run()
    at.text_area(key=prefix + "_explanation").set_value(
        "Synthetic quotation covers the unchanged service scope; retain these allowances without additional reference-year inflation."
    ).run()
    if kind == "rate":
        at.checkbox(key=prefix + "_unit_confirmed").check().run()
    at.button(key=prefix + "_record").click().run()
    assert not at.exception
    return at


def show_role_overrides(at):
    # Step 5 now uses one shared future-cost assumption, with no per-role method questionnaire.
    p = at.session_state["plan"]
    if p.ui_step == 4:
        prefix = f"common_future_{p.id}"
        field = next((x for x in at.number_input if x.key == prefix + "_percent"), None)
        if field and field.value is None:
            field.set_value(0.0).run()
        reason = next((x for x in at.text_area if x.key == prefix + "_reason"), None)
        if reason and not reason.value:
            reason.set_value("Synthetic contractor renewal forecast for the unchanged manpower scope").run()
    return at


def reviewed(monkeypatch, tmp_path):
    import services.agent as agent

    monkeypatch.setattr(agent, "converse", ready_guide)
    at = fill_table(
        blank(monkeypatch, tmp_path, live=True),
        ["Facility Manager", "Technician", "M&E Engineer"],
        [1, 3, 0.5],
    )
    at.button(key="revise_manpower_plan").click().run()
    at.chat_input[0].set_value("Review the deployment for material discrepancies").run()
    assert not at.exception
    at.button(key="accept_deployment_suggestions").click().run()
    at.button(key="use_manpower_plan").click().run()
    assert not at.exception and at.session_state["stage"] == 4
    return at


def test_project_then_manpower_steps_without_chat_or_internal_evidence(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    assert not any("Drafts stay in this session" in c.value for c in at.caption)
    assert not at.dataframe and not at.multiselect
    assert not any(t.value == "Build a new manpower plan" for t in at.title)
    assert any(h.value == "Step 1 out of 5: Project" for h in at.subheader)
    assert not any("SYNTHETIC DATA" in c.value for c in at.caption)
    assert not at.button(key="six_continue").disabled
    fill_project(at)
    assert not at.dataframe and role_picker(at)
    assert any(h.value == "Step 2 out of 5: Deployment" for h in at.subheader)
    assert not any(
        e.label in {"Add an unlisted role", "One operational reason covers related roles"}
        for e in at.expander
    )
    assert not any(e.label == "Additional context (optional)" for e in at.expander)
    assert "Anything not covered in the table" not in {t.label for t in at.text_area}
    assert not any(b.label == "Review plan" for b in at.button)
    assert not at.get("json") and not at.session_state["plan"].chat
    assert not any("Tool evidence" in e.label for e in at.expander)

    assert not working_draft(at.session_state["plan"]).roles
    assert role_picker(at).value is None
    assert not any("Paste a manpower" in e.label for e in at.expander)


def test_actual_table_edits_survive_save_and_no_model_runs_on_edits(monkeypatch, tmp_path):
    import services.agent as agent

    requests = []
    monkeypatch.setattr(agent, "converse", lambda *args: requests.append(args))
    at = fill_table(
        blank(monkeypatch, tmp_path, live=True), ["Senior Property Executive cum FSM", "Technician"], [0.5, 4]
    )
    assert not requests
    button(at, "Save draft").click().run()
    draft = working_draft(at.session_state["plan"])
    assert {r.label: r.quantity for r in draft.roles if r.included} == {
        "Senior Property Executive cum FSM": 0.5,
        "Technician": 4,
    }
    assert not requests and not at.session_state["plan"].confirmations
    assert len([r for r in at.session_state["plan"].officer_manpower_input if r["included"]]) == 2
    assert set(
        next(
            d.value
            for d in at.dataframe
            if "Proposed quantity / FTE" in d.value.columns
            and set(d.value["Proposed quantity / FTE"]) == {0.5, 4}
        )["Proposed quantity / FTE"]
    ) == {0.5, 4}


def test_table_and_targeted_followup_reach_one_confirmation(monkeypatch, tmp_path):
    import services.agent as agent

    requests = []

    def guide(plan, records, message, client, model, stage):
        requests.append(message)
        if len(requests) == 1:
            plan.chat.extend(
                [
                    {"role": "user", "content": message},
                    {
                        "role": "assistant",
                        "content": "Does the internal team retain tenant enquiries, leaving this team with reports only?",
                    },
                ]
            )
            return plan.chat[-1]["content"]
        return ready_guide(plan, records, message, client, model, stage)

    monkeypatch.setattr(agent, "converse", guide)
    at = fill_table(blank(monkeypatch, tmp_path, live=True), ["Admin Executive", "Technician"], [1, 3])
    at.button(key="revise_manpower_plan").click().run()
    at.chat_input[0].set_value("Review the deployment for material discrepancies").run()
    assert not at.exception and len(requests) == 1
    assert not at.session_state["plan"].pending
    at.chat_input[0].set_value(
        "Yes: internal staff retain tenant enquiries; this team maintains records and reports."
    ).run()
    assert not at.exception and len(requests) == 2
    assert {r.quantity for r in working_draft(at.session_state["plan"]).roles if r.included} == {1, 3}
    at.button(key="accept_deployment_suggestions").click().run()
    at.button(key="use_manpower_plan").click().run()
    assert not at.exception and at.session_state["stage"] == 4
    assert len(requests) == 2  # No automatic pricing interview after manpower confirmation.
    assert set(at.session_state["plan"].confirmations) == {
        "profile",
        "responsibilities",
        "quantities",
        "plan",
    }


def test_average_defaults_and_slider_do_not_require_justification(monkeypatch, tmp_path):
    at = reviewed(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    r = next(r for r in p.roles if r.label == "Facility Manager")
    from services.evidence import rate_benchmark

    assert r.rate == round(rate_benchmark(load_records(), r.mapped_role, 2028)["average"], 2)
    custom = next(r for r in p.roles if r.label == "M&E Engineer")
    assert custom.rate is None
    prefix = f"rate_{p.id}_{r.id}_2028"
    at.number_input(key=prefix + "_number").set_value(25000.0).run()
    assert not at.exception
    changed = next(item for item in at.session_state["plan"].roles if item.id == r.id)
    assert changed.rate == 25000 and not changed.rate_reason
    at.text_area(key=prefix + "_rationale").set_value(
        "Synthetic quotation includes extended callout coverage"
    ).run()
    assert not any(sl.key == prefix + "_slider" for sl in at.slider)
    assert at.number_input(key=prefix + "_number").value == 25000
    assert (
        "plan" in at.session_state["plan"].confirmations
        and "rates" not in at.session_state["plan"].confirmations
    )
    at.number_input(key=f"rate_{p.id}_{custom.id}_2028_number").set_value(6500.0).run()
    next(box for box in at.selectbox if box.label == "Reference pricing year").set_value(2024).run()
    assert any("2024" in w.value and "2028" in w.value and "No inflation" in w.value for w in at.warning)
    assert next(item for item in at.session_state["plan"].roles if item.id == r.id).rate == 25000
    give_basis(at, "rate")
    at.button(key="confirm_rates").click().run()
    show_role_overrides(at)
    assert not at.exception and at.session_state["stage"] == 6
    assert (
        "rates" in at.session_state["plan"].confirmations and "base" in at.session_state["plan"].confirmations
    )


def test_complete_hybrid_budget_charts_and_export(monkeypatch, tmp_path):
    at = reviewed(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    unsupported = next(r for r in p.roles if r.label == "M&E Engineer")
    at.number_input(key=f"rate_{p.id}_{unsupported.id}_2028_number").set_value(6500.0).run()
    give_basis(at, "rate")
    at.button(key="confirm_rates").click().run()
    show_role_overrides(at)
    p = at.session_state["plan"]
    from services.workflow import apply_change

    for r in list(p.roles):
        apply_change(
            p,
            "role",
            {
                **r.model_dump(mode="json"),
                "escalation": [0, 0.02, 0.02, 0.02],
                "escalation_reason": "Explicit synthetic officer future-price assumption",
            },
            "Synthetic future-price selection",
            "Synthetic officer",
        )
    at.run()
    give_basis(at, "escalation")
    at.button(key="confirm_escalation").click().run()
    p = at.session_state["plan"]
    for f in findings(p, load_records()):
        record_decision(
            p,
            f,
            "accepted exception",
            "Retain the synthetic allowance because the documented contractor scope covers these operating hours",
            "Synthetic officer",
        )
    at.run()
    button(at, "Confirm full contract budget").click().run()
    assert not at.exception and "final" in at.session_state["plan"].confirmations
    assert len(at.get("plotly_chart")) >= 2
    assert any("Confirmed budget" == x.value for x in at.caption)


def test_failed_review_retains_table_and_explicit_retry_only(monkeypatch, tmp_path):
    import services.agent as agent

    calls = []

    def guide(*args):
        calls.append(args[2])
        if len(calls) == 1:
            raise agent.AgentError("The app could not connect to OpenAI.", kind="connection")
        return ready_guide(*args)

    monkeypatch.setattr(agent, "converse", guide)
    at = fill_table(blank(monkeypatch, tmp_path, live=True), ["Technician"], [4])
    at.button(key="revise_manpower_plan").click().run()
    at.chat_input[0].set_value("Review the deployment for material discrepancies").run()
    assert not at.exception and at.session_state["failed_turn"]
    assert next(r for r in working_draft(at.session_state["plan"]).roles if r.included).quantity == 4
    at.run()
    assert len(calls) == 1
    at.button(key="retry_failed_message").click().run()
    assert not at.exception and len(calls) == 2
    assert at.session_state["plan"].review_checkpoint == ""
    assert at.session_state["plan"].pending


def test_explicit_copy_then_zero_does_not_answer_other_roles_or_call_api(monkeypatch, tmp_path):
    at = fill_table(blank(monkeypatch, tmp_path), ["Facility Manager", "Technician"], [2, 4])
    assert len(working_draft(at.session_state["plan"]).roles) == 2
    assert not any(x.key in ("copy_current", "mark_unused_zero") for x in at.button)
    assert not at.session_state["plan"].confirmations
    assert {r.label: r.quantity for r in working_draft(at.session_state["plan"]).roles} == {
        "Facility Manager": 2,
        "Technician": 4,
    }


def test_save_resume_preserves_comparison_without_approval(monkeypatch, tmp_path):
    at = fill_table(blank(monkeypatch, tmp_path), ["Facility Manager", "Technician"], [1, 4])
    button(at, "Save draft").click().run()
    saved_id = at.session_state["plan"].id
    button(at, "New blank project").click().run()
    assert at.session_state["plan"].id != saved_id
    button(at, "Resume selected project").click().run()
    assert not at.exception and at.session_state["plan"].id == saved_id
    draft = working_draft(at.session_state["plan"])
    assert {r.label: r.quantity for r in draft.roles if r.included} == {
        "Facility Manager": 1,
        "Technician": 4,
    }
    assert "Invented office" in draft.profile.description
    assert at.session_state["plan"].ui_step == 1
    assert not at.session_state["plan"].confirmations


def test_back_navigation_retains_inputs_and_manpower_revision_relocks_pricing(monkeypatch, tmp_path):
    at = reviewed(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    original = {r.id: r.quantity for r in p.roles}
    calls = len(p.chat)
    at.button(key="six_back").click().run()
    assert at.session_state["plan"].ui_step == 1
    assert at.button(key="use_manpower_plan").disabled is False
    assert at.session_state["plan"].ui_step == 1
    assert {r.id: r.quantity for r in working_draft(at.session_state["plan"]).roles} == original
    key = role_picker(at).key.removesuffix("_add") + "_table"
    index = list(at.dataframe[0].value["Role title"]).index("Technician")
    at.session_state[key] = {
        "edited_rows": {index: {"Proposed quantity / FTE": 5.0}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "Save draft").click().run()
    p = at.session_state["plan"]
    assert not at.exception and "plan" not in p.confirmations
    assert len(p.chat) == calls
    assert at.session_state["plan"].ui_step == 1 and not any(b.key == "six_continue" for b in at.button)
    assert (
        next(r for r in working_draft(at.session_state["plan"]).roles if r.label == "Technician").quantity
        == 5
    )
    assert not any(b.key == "confirm_rates" for b in at.button)


def test_compact_rates_costs_band_and_explicit_zero_future_profile(monkeypatch, tmp_path):

    at = reviewed(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    assert not any("Monthly role cost (SGD)" in d.value.columns for d in at.dataframe)
    for r in p.roles:
        if r.included:
            assert at.number_input(key=f"rate_{p.id}_{r.id}_2028_number").value == r.rate
    assert len(at.slider) == len([r for r in p.roles if r.included])
    assert not at.get("plotly_chart")
    unsupported = next(r for r in p.roles if r.label == "M&E Engineer")
    at.number_input(key=f"rate_{p.id}_{unsupported.id}_2028_number").set_value(6500.0).run()
    give_basis(at, "rate")
    at.button(key="confirm_rates").click().run()
    show_role_overrides(at)
    assert at.session_state["plan"].ui_step == 4
    prefix = f"common_future_{p.id}"
    at.number_input(key=prefix + "_percent").set_value(2.5).run()
    # Preview is separate from recorded inputs until the single confirmation.
    assert all(r.escalation == [] for r in at.session_state["plan"].roles if r.included)
    at.button(key="confirm_escalation").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 5
    assert len(at.get("plotly_chart")) >= 2
    assert not any(b.key == "confirm_validation" for b in at.button)
    assert button(at, "Confirm full contract budget")
    assert any(b.label == "Download budget" for b in at.get("download_button"))
    assert "final" not in at.session_state["plan"].confirmations


def test_delete_selected_project_needs_confirmation_and_preserves_another_draft(monkeypatch, tmp_path):
    from services.storage import Store

    at = blank(monkeypatch, tmp_path)
    first = at.session_state["plan"]
    first.profile.name = "Synthetic project to remove"
    button(at, "Save draft").click().run()
    first_id = first.id
    button(at, "New blank project").click().run()
    active_id = at.session_state["plan"].id
    store = Store(f"sqlite:///{tmp_path / 'ui.db'}")
    at.button(key="delete_project").click().run()
    assert store.load(first_id, "local-review")[1] == 1
    assert any("Synthetic project to remove" in w.value for w in at.warning)
    at.button(key="cancel_delete_project").click().run()
    assert store.load(first_id, "local-review")[1] == 1
    at.button(key="delete_project").click().run()
    at.button(key="confirm_delete_project").click().run()
    assert not at.exception and store.list("local-review") == []
    assert at.session_state["plan"].id == active_id
    # Deleting the open saved project closes it, preventing accidental resaving of the removed identity.
    at.session_state["plan"].profile.name = "Synthetic active project"
    button(at, "Save draft").click().run()
    at.run()
    at.button(key="delete_project").click().run()
    at.button(key="confirm_delete_project").click().run()
    assert not at.exception and store.list("local-review") == []
    assert at.session_state["plan"].id != active_id and not at.session_state["plan"].confirmations


def test_unsaved_switch_can_be_cancelled_or_saved_without_confirmation(monkeypatch, tmp_path):
    from services.storage import Store

    at = blank(monkeypatch, tmp_path)
    next(t for t in at.text_input if t.label == "Project name").set_value("Synthetic unsaved tender").run()
    original_id = at.session_state["plan"].id
    button(at, "New blank project").click().run()
    assert at.session_state["plan"].id == original_id
    assert any("unsaved changes" in w.value for w in at.warning)
    at.button(key="cancel_switch").click().run()
    assert at.session_state["plan"].id == original_id
    button(at, "New blank project").click().run()
    at.button(key="save_and_switch").click().run()
    assert not at.exception and at.session_state["plan"].id != original_id
    store = Store(f"sqlite:///{tmp_path / 'ui.db'}")
    assert store.list("local-review")[0]["name"] == "Synthetic unsaved tender"
    loaded, _ = store.load(original_id, "local-review")
    assert not loaded.confirmations


def test_plain_contract_fields_missing_inputs_and_invalid_text_protect_valid_draft(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    assert not at.number_input and not at.chat_input
    assert not any("To continue:" in i.value for i in at.info)
    at.button(key="six_continue").click().run()
    assert any("anticipated start" in i.value for i in at.info)
    fill_project(at)
    at.button(key="six_back").click().run()
    next(t for t in at.text_input if t.label == "Anticipated start month").set_value("bad date").run()
    assert not at.button(key="six_continue").disabled
    assert any("MMM YYYY" in i.value for i in at.info)
    assert working_draft(at.session_state["plan"]).profile.start_month == 1
    button(at, "Save draft").click().run()
    assert not at.error and at.session_state["storage_revision"] > 0
    assert at.session_state["plan"].basis_drafts["project_text"]["start"] == "bad date"


def test_synthetic_example_walks_all_five_steps_offline_and_exports(monkeypatch, tmp_path):
    from services.calculations import budget
    from services.demo import demo_plan

    at = blank(monkeypatch, tmp_path)
    legacy_example = demo_plan()
    legacy_example.ui_step = 0
    at.session_state["plan"] = legacy_example
    at.run()
    assert at.session_state["plan"].ui_step == 0 and not at.session_state["plan"].confirmations
    example = at.session_state["plan"]
    assert example.contract_kind == "existing contract"
    assert example.current_deployment_status == "known"
    assert sum(r.current_quantity for r in example.roles) == 6
    assert sum(r.quantity for r in example.roles) == 7
    assert not at.button(key="six_continue").disabled
    at.button(key="six_continue").click().run()
    assert at.session_state["plan"].ui_step == 1
    assert all(r.quantity_unit == "headcount" for r in working_draft(at.session_state["plan"]).roles)
    assert at.dataframe[0].proto.placeholder == ""
    assert at.session_state["plan"].ui_step == 1
    assert not at.session_state["plan"].chat
    at.button(key="use_manpower_plan").click().run()
    assert at.session_state["plan"].ui_step == 3
    give_basis(at, "rate")
    at.button(key="confirm_rates").click().run()
    show_role_overrides(at)
    assert at.session_state["plan"].ui_step == 4
    assert any("monthly_unit_rate" in d.value.columns for d in at.dataframe)
    give_basis(at, "escalation")
    at.button(key="confirm_escalation").click().run()
    assert at.session_state["plan"].ui_step == 5
    assert "final" not in at.session_state["plan"].confirmations
    assert not any("Events Manager" in info.value and "Record a decision" in info.value for info in at.info)
    p = at.session_state["plan"]
    for f in findings(p, load_records()):
        assert not f.blocking
        record_decision(
            p,
            f,
            "data limitation",
            "Synthetic officer explicitly reviewed this limitation",
            "Synthetic walkthrough officer",
        )
    at.run()
    button(at, "Confirm full contract budget").click().run()
    p = at.session_state["plan"]
    assert not at.exception and "final" in p.confirmations
    assert len(at.get("plotly_chart")) >= 2
    assert any("Confirmed budget" == x.value for x in at.caption)
    result = budget(p, load_records())
    assert round(sum(result["annual_totals"]), 2) == result["contract_total"]
    assert p.chat == []


def test_conditional_columns_blank_cells_and_explicit_shared_allocation(monkeypatch, tmp_path):
    import json

    at = fill_table(blank(monkeypatch, tmp_path), ["Facility Manager"], [0.5])
    frame = next(d for d in at.dataframe if "Proposed quantity / FTE" in d.value.columns)
    config = json.loads(frame.proto.columns)
    assert config["Current quantity / FTE"]["hidden"] and config["Change"]["hidden"]
    assert frame.proto.placeholder == ""
    r = working_draft(at.session_state["plan"]).roles[0]
    assert r.quantity == 0.5 and r.quantity_unit == "FTE"
    assert not at.exception


def test_unapplied_future_method_saves_draft_but_cannot_be_confirmed(monkeypatch, tmp_path):
    at = reviewed(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    unsupported = next(r for r in p.roles if r.label == "M&E Engineer")
    at.number_input(key=f"rate_{p.id}_{unsupported.id}_2028_number").set_value(6500.0).run()
    give_basis(at, "rate")
    at.button(key="confirm_rates").click().run()
    show_role_overrides(at)
    role = next(r for r in at.session_state["plan"].roles if r.included)
    at.session_state["plan"].basis_drafts["future_mode_" + role.id] = "quoted schedule"
    at.run()
    assert at.button(key="confirm_escalation").disabled
    button(at, "Save draft").click().run()
    assert not at.error
    at.button(key=f"future_clear_legacy_{p.id}").click().run()
    assert not at.exception and not at.button(key="confirm_escalation").disabled


def test_advanced_drafts_are_not_lost_or_mistaken_for_recorded_assumptions(monkeypatch, tmp_path):
    at = reviewed(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    unsupported = next(r for r in p.roles if r.label == "M&E Engineer")
    at.number_input(key=f"rate_{p.id}_{unsupported.id}_2028_number").set_value(6500.0).run()
    give_basis(at, "rate")
    at.button(key="confirm_rates").click().run()
    show_role_overrides(at)
    p = at.session_state["plan"]
    role = next(r for r in p.roles if r.included)
    prefix = f"esc_{p.id}_{role.id}"
    at.session_state[prefix + "_yearly_text"] = "0, 1, 2, 3"
    at.run()
    button(at, "Save draft").click().run()
    assert (
        at.session_state["plan"].basis_drafts["_ui_controls"]["values"][prefix + "_yearly_text"]
        == "0, 1, 2, 3"
    )
    assert at.button(key="confirm_escalation").disabled
    at.session_state[prefix + "_yearly_text"] = "0, 2, 3, 4"
    at.run()
    button(at, "New blank project").click().run()
    assert at.session_state["switch_target"]
    at.button(key="cancel_switch").click().run()
    at.button(key=f"future_clear_legacy_{p.id}").click().run()
    assert not at.exception and not at.button(key="confirm_escalation").disabled


def test_status_quo_needs_no_name_or_per_role_justification(monkeypatch, tmp_path):
    import services.agent as agent

    calls = []
    monkeypatch.setattr(agent, "converse", lambda *args: calls.append(args))
    at = fill_table(blank(monkeypatch, tmp_path), ["Facility Manager"], [1])
    assert not any(t.label == "Reviewing officer" for t in at.text_input)
    assert not any(t.label == "Brief reason, correction or uncertainty" for t in at.text_area)
    assert not at.button(key="use_manpower_plan").disabled
    at.button(key="revise_manpower_plan").click().run()
    assert at.session_state["manpower_help_open"]
    at.button(key="use_manpower_plan").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 3
    assert "name not collected" in at.session_state["officer"]
    assert next(r for r in at.session_state["plan"].roles if r.included).quantity == 1
    assert not calls


def test_material_mismatch_is_a_single_editable_table(monkeypatch, tmp_path):
    from services.journey import update_notes

    at = fill_table(blank(monkeypatch, tmp_path), ["Technician"], [2])
    p = at.session_state["plan"]
    p.contract_kind = "existing contract"
    r = working_draft(p).roles[0]
    update_notes(
        p, roles=[{**r.model_dump(), "current_quantity": 2, "duties_notes": "additional 4 pax for support"}]
    )
    at.run()
    flags = [d for d in at.dataframe if "Check" in d.value.columns]
    assert len(flags) == 1 and "figures show +0" in flags[0].value.iloc[0]["Check"]
    assert any("Proposed quantity / FTE" in d.value.columns for d in at.dataframe)
    assert not any(t.label == "Brief reason, correction or uncertainty" for t in at.text_area)
    assert not at.exception


def test_pwm_draft_save_apply_confirm_and_mixed_role_budget(monkeypatch, tmp_path):
    import runpy

    from services.calculations import budget
    from services.journey import accept_review
    from services.storage import Store

    at = blank(monkeypatch, tmp_path)
    p = runpy.run_path(str(Path(__file__).with_name("test_budget_basis_pwm.py")))["pwm_plan"]()
    config = p.roles[0].pwm.model_copy(deep=True)
    p.roles[0].pwm = None
    for role in p.roles:
        role.rate_reason = (
            "Synthetic quotation covers inclusive manpower duties for these workers at contract start"
        )
        role.escalation_reason = (
            "Synthetic renewal allowance covers annual labour costs for the unchanged operating scope"
        )
    for checkpoint in ("manpower", "rates"):
        assert prepare_review(p, checkpoint, load_records())["ready"]
        accept_review(p, "Synthetic officer", load_records())
    p.ui_step = 4
    at.session_state["plan"] = p
    at.run()
    prefix = f"pwm_{p.id}_clean"
    # Relevant titles are candidates; the officer explicitly opens the coverage check.
    at.multiselect(key=f"common_future_{p.id}_pwm_roles").set_value(["clean"]).run()
    at.selectbox(key=prefix + "_schedule_id").set_value(config.schedule_id).run()
    at.checkbox(key=prefix + "_applicability_confirmed").check().run()
    at.number_input(key=prefix + "_covered_quantity").set_value(2).run()
    at.number_input(key=prefix + "_starting_salary").set_value(2000.0).run()
    at.text_input(key=prefix + "_salary_source").set_value(config.salary_source).run()
    at.text_area(key=prefix + "_applicability_basis").set_value(config.applicability_basis).run()
    at.checkbox(key=prefix + "_applicability_confirmed").check().run()
    at.checkbox(key=prefix + "_remainder_flat_confirmed").check().run()
    at.number_input(key=prefix + "_oncost_percent").set_value(10.0).run()
    at.text_input(key=prefix + "_oncost_source").set_value(config.oncost_source).run()
    button(at, "Save draft").click().run()
    assert not at.exception and not at.error
    saved, _ = Store(f"sqlite:///{tmp_path / 'ui.db'}").load(p.id, "local-review")
    assert saved.roles[0].pwm is None and saved.basis_drafts["pwm_clean"]["starting_salary"] == 2000
    assert "escalation" not in saved.confirmations
    at.button(key=prefix + "_apply").click().run()
    applied = next(r for r in at.session_state["plan"].roles if r.id == "clean")
    assert applied.pwm.covered_quantity == 2
    assert "escalation" not in at.session_state["plan"].confirmations
    assert not at.button(key="confirm_escalation").disabled
    at.button(key="confirm_escalation").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 5
    total = budget(at.session_state["plan"], load_records())
    assert next(r for r in total["rows"] if r["role_id"] == "clean")["pwm_cost"] == 2349.73
    button(at, "Confirm full contract budget").click().run()
    assert not at.exception and "final" in at.session_state["plan"].confirmations
