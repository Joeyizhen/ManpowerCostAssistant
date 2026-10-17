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
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=40).run()
    at.button(key="choose_track_1").click().run()
    assert not at.exception
    return at


def button(at, label):
    return next(b for b in at.button if b.label == label)


def fill_table(at, titles, quantities):
    next(t for t in at.text_area if t.label == "Short project brief").set_value(
        "Invented office FM team, weekday workload allowances; separate specialist contracts."
    ).run()
    next(t for t in at.number_input if t.label == "Contract start year").set_value(2028).run()
    next(t for t in at.number_input if t.label == "Base contract years").set_value(2).run()
    next(t for t in at.number_input if t.label == "Option years").set_value(2).run()
    next(r for r in at.radio if "replacing" in r.label).set_value("New contract/site/service").run()
    known = set(at.dataframe[0].value["Role title"])
    extras = [t for t in titles if t not in known]
    if extras:
        at.multiselect[0].set_value(extras).run()
        at.button(key="add_selected_roles").click().run()
    key = at.multiselect[0].key.removesuffix("_add") + "_table"
    selected = dict(zip(titles, quantities, strict=True))
    at.session_state[key] = {
        "edited_rows": {
            i: {
                "Proposed quantity / FTE": selected.get(title, 0),
                "Quantity basis": "FTE" if not float(selected.get(title, 0)).is_integer() else "headcount",
                "Duties / deployment notes": "Officer weekday workload allowance"
                if title in selected
                else "",
            }
            for i, title in enumerate(at.dataframe[0].value["Role title"])
        },
        "added_rows": [],
        "deleted_rows": [],
    }
    return at


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


def reviewed(monkeypatch, tmp_path):
    import services.agent as agent

    monkeypatch.setattr(agent, "converse", ready_guide)
    at = fill_table(
        blank(monkeypatch, tmp_path, live=True),
        ["Facility Manager", "Technician", "M&E Engineer"],
        [1, 3, 0.5],
    )
    button(at, "Review my manpower plan").click().run()
    assert not at.exception
    at.text_input(key="officer").set_value("Synthetic reviewing officer").run()
    at.button(key="apply_reviewed_details").click().run()
    assert not at.exception and at.session_state["stage"] == 4
    return at


def test_table_is_immediate_without_chat_or_internal_evidence(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    assert at.dataframe and at.multiselect
    assert {
        "Short project brief",
        "Existing internal staff, external contractors or combined duties (optional)",
    } <= {t.label for t in at.text_area}
    assert button(at, "Review my manpower plan").disabled
    assert not at.get("json") and not at.session_state["plan"].chat
    assert not any("Tool evidence" in e.label for e in at.expander)
    from services.hybrid import COMMON_ROLES

    assert at.dataframe[0].value["Role title"].tolist() == COMMON_ROLES
    assert at.dataframe[0].value["Proposed quantity / FTE"].isna().all()
    assert not any("Paste a manpower" in e.label for e in at.expander)


def test_actual_table_edits_survive_save_and_no_model_runs_on_edits(monkeypatch, tmp_path):
    import services.agent as agent

    requests = []
    monkeypatch.setattr(agent, "converse", lambda *args: requests.append(args))
    at = fill_table(
        blank(monkeypatch, tmp_path, live=True), ["Senior Property Executive cum FSM", "Technician"], [0.5, 4]
    )
    assert not requests
    button(at, "Save input draft").click().run()
    draft = working_draft(at.session_state["plan"])
    assert {r.label: r.quantity for r in draft.roles if r.included} == {
        "Senior Property Executive cum FSM": 0.5,
        "Technician": 4,
    }
    assert not requests and not at.session_state["plan"].confirmations
    assert len([r for r in at.session_state["plan"].officer_manpower_input if r["included"]]) == 2
    assert set(at.dataframe[0].value["Proposed quantity / FTE"]) == {0, 0.5, 4}


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
    button(at, "Review my manpower plan").click().run()
    assert not at.exception and len(requests) == 1
    assert not at.session_state["plan"].pending
    at.chat_input[0].set_value(
        "Yes: internal staff retain tenant enquiries; this team maintains records and reports."
    ).run()
    assert not at.exception and len(requests) == 2
    assert {r.quantity for r in working_draft(at.session_state["plan"]).roles if r.included} == {1, 3}
    at.text_input(key="officer").set_value("Synthetic officer").run()
    at.button(key="apply_reviewed_details").click().run()
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
    assert changed.rate == 25000 and changed.rate_reason
    assert at.slider(key=prefix + "_slider").value == 25000
    assert (
        "plan" in at.session_state["plan"].confirmations
        and "rates" not in at.session_state["plan"].confirmations
    )
    at.number_input(key=f"rate_{p.id}_{custom.id}_2028_number").set_value(6500.0).run()
    at.button(key="confirm_rates").click().run()
    assert not at.exception and at.session_state["stage"] == 6
    assert (
        "rates" in at.session_state["plan"].confirmations and "base" in at.session_state["plan"].confirmations
    )


def test_complete_hybrid_budget_charts_and_export(monkeypatch, tmp_path):
    at = reviewed(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    unsupported = next(r for r in p.roles if r.label == "M&E Engineer")
    at.number_input(key=f"rate_{p.id}_{unsupported.id}_2028_number").set_value(6500.0).run()
    at.button(key="confirm_rates").click().run()
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
    at.button(key="confirm_escalation").click().run()
    at.button(key="review_step").click().run()
    p = at.session_state["plan"]
    for f in findings(p, load_records()):
        record_decision(
            p, f, "accepted exception", "Reviewed synthetic workload/price limitations", "Synthetic officer"
        )
    at.run()
    at.button(key="confirm_validation").click().run()
    at.selectbox(key="stage").set_value(9).run()
    at.button(key="review_step").click().run()
    button(at, "Confirm full contract budget").click().run()
    assert not at.exception and "final" in at.session_state["plan"].confirmations
    assert len(at.get("plotly_chart")) == 2
    assert any("confirmed Excel" in b.label for b in at.get("download_button"))


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
    button(at, "Review my manpower plan").click().run()
    assert not at.exception and at.session_state["failed_turn"]
    assert next(r for r in working_draft(at.session_state["plan"]).roles if r.included).quantity == 4
    at.run()
    assert len(calls) == 1
    at.button(key="retry_failed_message").click().run()
    assert not at.exception and len(calls) == 2
    assert at.session_state["plan"].review_checkpoint == "manpower"


def test_explicit_copy_then_zero_does_not_answer_other_roles_or_call_api(monkeypatch, tmp_path):
    import services.agent as agent

    calls = []
    monkeypatch.setattr(agent, "converse", lambda *args: calls.append(args))
    at = blank(monkeypatch, tmp_path, live=True)
    next(r for r in at.radio if r.label == "Current contract deployment").set_value(
        "Current deployment known (enter what you know)"
    ).run()
    key = at.multiselect[0].key.removesuffix("_add") + "_table"
    at.session_state[key] = {
        "edited_rows": {
            0: {"Current quantity / FTE": 2.0, "Proposed quantity / FTE": 1.0, "Quantity basis": "headcount"},
            2: {"Proposed quantity / FTE": 4.0, "Quantity basis": "headcount"},
        },
        "added_rows": [],
        "deleted_rows": [],
    }
    at.button(key="copy_current").click().run()
    frame = at.dataframe[0].value
    assert frame.iloc[0]["Proposed quantity / FTE"] == 2
    assert frame.iloc[2]["Proposed quantity / FTE"] == 4
    assert frame.drop(index=[0, 2])["Proposed quantity / FTE"].isna().all()
    at.button(key="mark_unused_zero").click().run()
    draft = working_draft(at.session_state["plan"])
    assert {r.label: r.quantity for r in draft.roles if r.included} == {
        "Facility Manager": 2,
        "Technician": 4,
    }
    assert all(r.quantity == 0 for r in draft.roles if not r.included)
    assert not calls and not at.session_state["plan"].confirmations


def test_save_resume_preserves_comparison_without_approval(monkeypatch, tmp_path):
    at = fill_table(blank(monkeypatch, tmp_path), ["Facility Manager", "Technician"], [1, 4])
    button(at, "Save input draft").click().run()
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
    assert not at.session_state["plan"].confirmations
