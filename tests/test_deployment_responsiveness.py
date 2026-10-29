"""Deployment readiness is read-only; unchanged confirmation stays valid."""

from test_ui import blank

from services.evidence import load_records
from services.workflow import apply_change
from services.xtown_example import xtown_plan


def forbidden(*args, **kwargs):
    raise AssertionError("Rendering unchanged deployment must not rehearse confirmation/findings")


def test_noop_role_skips_findings_but_real_edit_invalidates(monkeypatch):
    p = xtown_plan(load_records())
    original = p.model_dump_json()
    monkeypatch.setattr("services.workflow.findings", forbidden)
    apply_change(p, "role", p.roles[0].model_dump(mode="json"), "No change", "Test")
    assert p.model_dump_json() == original
    calls = []
    monkeypatch.setattr("services.workflow.findings", lambda *args: calls.append(True) or [])
    payload = p.roles[0].model_dump(mode="json")
    payload["quantity"] += 1
    apply_change(p, "role", payload, "Real staffing edit", "Test")
    assert calls == [True] and "plan" not in p.confirmations and "rates" not in p.confirmations
    assert p.history[-1]["previous_findings"] == []


def test_confirmed_continue_does_not_reconfirm_or_clear_later_approvals(monkeypatch, tmp_path):
    from services.journey import accept_review, prepare_review

    at = blank(monkeypatch, tmp_path)
    p = xtown_plan(load_records())
    p.ui_step = 1
    before = p.model_copy(deep=True)
    at.session_state["plan"] = p

    def prepare(candidate, checkpoint, records):
        if checkpoint == "manpower":
            forbidden()
        return prepare_review(candidate, checkpoint, records)

    def accept(candidate, officer, records):
        if candidate.review_checkpoint == "manpower":
            forbidden()
        return accept_review(candidate, officer, records)

    monkeypatch.setattr("hybrid_inputs.prepare_review", prepare)
    monkeypatch.setattr("hybrid_inputs.accept_review", accept)
    at.run()
    assert not at.exception
    assert at.button(key="use_manpower_plan").label == "Continue to starting rates"
    assert not at.button(key="use_manpower_plan").disabled
    at.button(key="use_manpower_plan").click().run()
    assert not at.exception and at.session_state["plan"].ui_step == 3
    after = at.session_state["plan"]
    assert after.confirmations == before.confirmations
    assert after.version == before.version and after.history == before.history


def test_missing_quantity_still_blocks_without_rehearsing_acceptance(monkeypatch, tmp_path):
    at = blank(monkeypatch, tmp_path)
    p = xtown_plan(load_records())
    p.ui_step = 1
    p.roles[0].quantity = None
    p.confirmations.clear()
    at.session_state["plan"] = p
    monkeypatch.setattr("hybrid_inputs.prepare_review", forbidden)
    monkeypatch.setattr("hybrid_inputs.accept_review", forbidden)
    at.run()
    assert not at.exception
    assert at.button(key="use_manpower_plan").label == "Confirm and continue"
    assert at.button(key="use_manpower_plan").disabled
    assert any("Facilities Manager" in x.value for x in at.info)
