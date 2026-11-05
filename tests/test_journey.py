"""Officer review boundaries when a conversational answer proposes several changes."""

import pytest

from services.demo import demo_plan
from services.evidence import load_records
from services.journey import accept_review, prepare_review, update_notes, working_draft
from services.models import Plan
from services.workflow import apply_pending, confirm, proposal


def test_reviewed_duties_apply_together_without_approving_stage():
    p = demo_plan()
    confirm(p, "profile", "Officer", load_records())
    confirm(p, "responsibilities", "Officer", load_records())
    for r in p.responsibilities[:2]:
        proposal(p, "responsibility", {**r.model_dump(), "evidence": "New officer answer"}, "Revised answer")
    apply_pending(p, "Officer")
    assert not p.pending
    assert "profile" in p.confirmations and "responsibilities" not in p.confirmations
    assert sum(r.evidence == "New officer answer" for r in p.responsibilities) == 2


def test_invalid_or_stale_review_batch_cannot_partially_apply():
    p = demo_plan()
    r = p.responsibilities[0]
    proposal(p, "responsibility", {**r.model_dump(), "evidence": "Changed"}, "Officer answer")
    p.pending.append({**p.pending[0], "id": "bad", "kind": "unsupported"})
    before = p.model_dump_json()
    with pytest.raises(ValueError):
        apply_pending(p, "Officer")
    assert p.model_dump_json() == before
    p.pending.pop()
    p.pending[0]["base_version"] -= 1
    before = p.model_dump_json()
    with pytest.raises(ValueError, match="predate"):
        apply_pending(p, "Officer")
    assert p.model_dump_json() == before


def test_answers_accumulate_without_presenting_a_proposal_until_requirements_ready():
    p = Plan()
    example = demo_plan()
    update_notes(p, profile={**example.profile.model_dump(mode="json"), "description": ""})
    result = prepare_review(p, "requirements", load_records())
    assert not result["ready"] and not p.pending
    assert p.profile.description == "" and working_draft(p).profile.base_years == 4
    update_notes(
        p,
        profile=example.profile.model_dump(mode="json"),
        responsibilities=[r.model_dump() for r in example.responsibilities],
    )
    assert prepare_review(p, "requirements", load_records())["ready"]
    assert not p.confirmations
    assert accept_review(p, "Officer", load_records()) == 2
    assert set(p.confirmations) == {"profile", "responsibilities"}
    assert not p.working_notes and not p.pending and not p.roles


def test_prior_answer_revision_requires_reconfirmation_and_external_duty_not_staffed():
    p = demo_plan()
    records = load_records()
    for gate in ["profile", "responsibilities", "quantities", "plan", "rates", "base"]:
        confirm(p, gate, "Officer", records)
    profile = p.profile.model_dump(mode="json")
    profile["operating_hours"] = "Corrected: 08:00–20:00 daily; technical post remains 24/7"
    update_notes(p, profile=profile)
    assert p.profile.operating_hours != profile["operating_hours"]
    assert prepare_review(p, "requirements", records)["ready"]
    accept_review(p, "Officer", records)
    assert p.profile.operating_hours == profile["operating_hours"]
    assert set(p.confirmations) == {"profile", "responsibilities"}
    role = p.roles[0].model_dump(mode="json")
    role["responsibility_ids"] = ["security"]
    update_notes(p, roles=[role])
    result = prepare_review(p, "manpower", records)
    assert result["ready"]
    assert any(f["code"].startswith("duplicate_") for f in result["findings"])


@pytest.mark.parametrize("checkpoint", ["rates", "escalation"])
@pytest.mark.parametrize("revision", ["profile", "responsibility"])
def test_unconfirmed_requirements_revision_blocks_later_review(checkpoint, revision):
    p, records = demo_plan(), load_records()
    for gate in ["profile", "responsibilities", "quantities", "plan", "rates", "base"]:
        confirm(p, gate, "Officer", records)
    if revision == "profile":
        update_notes(p, profile={**p.profile.model_dump(mode="json"), "operating_hours": "Revised hours"})
    else:
        duty = p.responsibilities[0].model_dump()
        update_notes(p, responsibilities=[{**duty, "description": "Revised operational responsibility"}])
    original = p.model_dump_json()
    result = prepare_review(p, checkpoint, records)
    assert result["requires_confirmation"] == "manpower" and not result["ready"]
    assert p.model_dump_json() == original


def test_changed_mapping_and_rate_require_their_own_confirmation():
    p, records = demo_plan(), load_records()
    for gate in ["profile", "responsibilities", "quantities", "plan", "rates", "base"]:
        confirm(p, gate, "Officer", records)
    role = p.roles[0].model_dump(mode="json")
    update_notes(p, roles=[{**role, "mapping_reason": "Revised comparability decision"}])
    assert prepare_review(p, "rates", records)["requires_confirmation"] == "manpower"
    update_notes(p, roles=[{**role, "rate": role["rate"] + 100}])
    assert prepare_review(p, "escalation", records)["requires_confirmation"] == "rates"
    assert prepare_review(p, "rates", records)["ready"]


def test_repeated_same_duty_does_not_require_reconfirmation():
    p, records = demo_plan(), load_records()
    for gate in ["profile", "responsibilities", "quantities", "plan"]:
        confirm(p, gate, "Officer", records)
    update_notes(p, responsibilities=[p.responsibilities[0].model_dump()])
    assert prepare_review(p, "rates", records)["ready"]
