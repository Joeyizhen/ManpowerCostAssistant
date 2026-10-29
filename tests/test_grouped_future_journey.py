"""Grouped Step 5 and handover journeys using synthetic data only."""

from io import BytesIO

import openpyxl
import pytest
from test_budget_basis_pwm import pwm_plan
from test_ui import blank, button

from services.calculations import budget
from services.decision_basis import meaningful, retained_basis
from services.evidence import load_records, map_role
from services.export import export_excel
from services.future_groups import general_proposal, general_reference
from services.journey import accept_review, prepare_review


def ready_plan(mixed=False):
    p = pwm_plan()
    if not mixed:
        p.roles = [p.roles[1]]
    for role in p.roles:
        role.mapped_role = map_role(role.label)
        role.rate_reason = "Synthetic quotation Q1 for inclusive monthly manpower charges"
        role.quantity_reason = "Existing deployment unchanged"
        role.escalation_reason = "Synthetic contractor renewal forecast"
    p.profile.name = "Synthetic grouped future-cost journey"
    for checkpoint in ("manpower", "rates"):
        assert prepare_review(p, checkpoint, load_records())["ready"]
        accept_review(p, "Synthetic officer", load_records())
    p.ui_step = 4
    return p


def open_future(monkeypatch, tmp_path, mixed=False):
    at = blank(monkeypatch, tmp_path)
    at.session_state["plan"] = ready_plan(mixed)
    at.run()
    assert not at.exception
    return at


def test_short_operational_rationale_digits_and_words_are_equivalent():
    assert meaningful("Two buildings × two officers")
    assert meaningful("2 buildings × 2 officers")
    assert meaningful("Contractor renewal forecast")
    assert meaningful("Quotation Q123")
    for vague in (
        "Need more manpower",
        "Higher annual increase",
        "Officer assumption",
        "more staff required",
    ):
        assert not meaningful(vague)


def test_shared_reference_equal_schedule_weights_and_excludes_service_prices():
    p = ready_plan()
    rows = load_records()
    bm = general_reference(p, rows, ["fm"])
    assert bm["available"] and bm["minimum"] <= bm["average"] <= bm["maximum"]
    p.roles.append(p.roles[0].model_copy(update={"id": "fm-annex"}))
    repeated = general_reference(p, rows, ["fm", "fm-annex"])
    assert repeated["sample_count"] == bm["sample_count"] and repeated["average"] == bm["average"]
    contaminated = [{**r, "inclusions": "Full trade/service price including materials"} for r in rows]
    assert not general_reference(p, contaminated, ["fm"])["available"]


def test_reference_preview_attaches_sources_without_mutating_or_reasking():
    p = ready_plan()
    before = p.model_dump_json()
    bm = general_reference(p, load_records(), ["fm"])
    q = general_proposal(p, load_records(), ["fm"], bm["average"] * 100, "", "", True, "Test")
    assert p.model_dump_json() == before
    assert retained_basis(q, q.roles[0], "escalation").classification == "sourced evidence"
    detail = q.decision_bases[-1].snapshots["fm"]
    assert detail["reference_data"]["record_ids"] and detail["quantity"] == 1
    assert q.roles[0].quantity_reason == p.roles[0].quantity_reason
    assert q.roles[0].rate_reason == p.roles[0].rate_reason
    assert "rates" in q.confirmations and "escalation" not in q.confirmations


def test_gap_requires_custom_assumption_and_mixed_pwm_is_unchanged():
    p = ready_plan(True)
    fm = next(r for r in p.roles if r.id == "fm")
    fm.mapped_role = None
    with pytest.raises(ValueError, match="supported selection"):
        general_proposal(p, [], ["fm"], 3, "", "", True, "Test")
    unsupported = general_proposal(p, [], ["fm"], 3, "", "", False, "Test")
    assert (
        retained_basis(
            unsupported, next(r for r in unsupported.roles if r.id == "fm"), "escalation"
        ).classification
        == "officer assumption"
    )
    q = general_proposal(p, [], ["fm"], 3, "Contractor renewal forecast", "Synthetic Q1", False, "Test")
    assert next(r for r in q.roles if r.id == "clean").pwm == p.roles[0].pwm
    actual = budget(q, [])
    fm_rows = [r for r in actual["rows"] if r["role_id"] == "fm"]
    clean_rows = [r for r in actual["rows"] if r["role_id"] == "clean"]
    assert fm_rows[1]["annual_cost"] == 98880
    assert all(r["monthly_unit_rate"] == 3000 and r["escalation"] == 0 for r in clean_rows)
    with pytest.raises(ValueError, match="active PWM"):
        general_proposal(p, [], ["clean", "fm"], 3, "Contractor renewal forecast", "", False, "Test")


def test_ui_default_reference_is_preview_then_single_confirmation(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    assert not at.radio
    # Existing saved 2% profile is carried forward as an assumption, not silently replaced.
    assert at.number_input(key=f"common_future_{p.id}_percent").value == 2.0
    bm = general_reference(p, load_records(), ["fm"])
    at.number_input(key=f"common_future_{p.id}_percent").set_value(round(bm["average"] * 100, 2)).run()
    assert at.number_input(key=f"common_future_{p.id}_percent").value == round(bm["average"] * 100, 2)
    assert not at.button(key="confirm_escalation").disabled
    before = p.roles[0].rate_reason
    at.button(key="confirm_escalation").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 5
    assert at.session_state["plan"].roles[0].rate_reason == before
    assert "escalation" in at.session_state["plan"].confirmations
    assert not any("Starting category" == x.label for x in at.selectbox)


def test_new_reference_defaults_to_average_and_custom_draft_survives_save_resume(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    p.roles[0].escalation = []
    p.roles[0].escalation_reason = ""
    at.session_state["plan"] = p
    # New project identity ensures no old widget values are reused.
    p.id = "fresh-reference-test"
    at.session_state["plan"] = p
    at.run()
    bm = general_reference(p, load_records(), ["fm"])
    assert at.number_input(key=f"common_future_{p.id}_percent").value == round(bm["average"] * 100, 2)
    assert "escalation" not in p.confirmations
    at.number_input(key=f"common_future_{p.id}_percent").set_value(4.0).run()
    assert not at.button(key="confirm_escalation").disabled
    at.text_area(key=f"common_future_{p.id}_reason").set_value("Contractor renewal forecast").run()
    button(at, "Save draft").click().run()
    p = at.session_state["plan"]
    at.text_area(key=f"common_future_{p.id}_reason").set_value("Revised contractor renewal forecast").run()
    button(at, "Resume selected project").click().run()
    at.button(key="save_and_switch").click().run()
    assert not at.exception and not at.error
    assert at.text_area(key=f"common_future_{p.id}_reason").value == "Revised contractor renewal forecast"
    button(at, "Save draft").click().run()
    assert not at.error


def test_repeated_titles_final_ui_and_export_remain_distinct(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = ready_plan()
    p.roles.append(p.roles[0].model_copy(update={"id": "fm-annex", "quantity": 2, "current_quantity": 2}))
    from services.workflow import confirm

    confirm(p, "escalation", "Synthetic officer", load_records())
    p.ui_step = 5
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    expected = budget(p, load_records())
    assert len({r["role_id"] for r in expected["rows"]}) == 2
    wb = openpyxl.load_workbook(BytesIO(export_excel(p, load_records())), data_only=True)
    data = list(wb["Budget summary"].values)
    assert any("fm-annex" in row for row in data)
    assert any("fm" in row for row in data)
    assert any(x.label == "Download budget" for x in at.get("download_button")), (
        [x.value for x in at.error],
        [x.label for x in at.get("download_button")],
    )


def test_pwm_staging_and_unsupported_actual_dates_retain_drafts(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path, True)
    p = at.session_state["plan"]
    assert not at.radio
    assert len(at.selectbox(key=f"pwm_{p.id}_clean_schedule_id").options) > 0
    p.profile.start = p.profile.start.replace(day=15)
    p.basis_drafts["pwm_clean"] = {"starting_salary": 2345.0}
    at.session_state["plan"] = p
    at.run()
    assert not at.exception
    assert any("do not substitute an invented date" in x.value for x in at.info)
    assert p.basis_drafts["pwm_clean"]["starting_salary"] == 2345


def test_single_year_needs_no_new_annual_assumption():
    p = ready_plan()
    p.profile.option_years = 0
    q = general_proposal(p, [], ["fm"], None, "", "", False, "Test")
    assert q.roles[0].escalation == [0]
    assert budget(q, [])["contract_total"] == 96000


def test_layout_upgrade_captures_raw_future_draft_and_keeps_other_findings(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path)
    p = at.session_state["plan"]
    key = f"esc_{p.id}_fm_yearly_text"
    finding_key = f"finding_{p.id}_synthetic_reason"
    at.session_state[key] = "0, 4"
    at.session_state[finding_key] = "Retained officer qualification"
    at.session_state[f"grouped_future_migrated_{p.id}"] = False
    at.run()
    assert at.session_state["plan"].basis_drafts["_ui_controls"]["values"][key] == "0, 4"
    assert at.button(key="confirm_escalation").disabled
    at.button(key=f"future_clear_legacy_{p.id}").click().run()
    kept = at.session_state["plan"].basis_drafts["_ui_controls"]["values"]
    assert key not in kept and kept[finding_key] == "Retained officer qualification"
    button(at, "Save draft").click().run()
    assert (
        at.session_state["plan"].basis_drafts["_ui_controls"]["values"][finding_key]
        == "Retained officer qualification"
    )


def test_pwm_stage_changes_reuse_existing_salary_fields(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path, True)
    p = at.session_state["plan"]
    prefix = f"pwm_{p.id}_clean"
    at.checkbox(key=prefix + "_applicability_confirmed").uncheck().run()
    assert not any(x.key == prefix + "_starting_salary" for x in at.number_input)
    at.checkbox(key=prefix + "_applicability_confirmed").check().run()
    assert at.number_input(key=prefix + "_starting_salary").value == 2000
    assert at.number_input(key=prefix + "_covered_quantity").value == 2


def test_running_old_step5_helpers_reload_without_touching_models_or_session():
    from types import SimpleNamespace

    from services.runtime_compat import recover_stale_imports

    models = SimpleNamespace(Plan=SimpleNamespace(model_fields={"decision_bases": object()}))
    session = {"draft": "retained"}
    modules = {
        "services.models": models,
        "future_inputs": SimpleNamespace(),
        "services.decision_basis": object(),
        "services.export": object(),
        "session": session,
    }
    assert recover_stale_imports(modules)
    assert modules == {"services.models": models, "session": session}
    assert session["draft"] == "retained"


def test_matching_legacy_method_is_not_an_unfinished_decision(monkeypatch, tmp_path):
    at = open_future(monkeypatch, tmp_path)
    at.session_state["plan"].basis_drafts["future_mode_fm"] = "assumption"
    at.run()
    assert not any(x.label == "Retained unfinished inputs from the earlier layout" for x in at.expander)
    assert not at.button(key="confirm_escalation").disabled
