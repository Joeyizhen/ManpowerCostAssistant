"""Mocked Responses contract tests. These do not measure actual LLM behaviour."""

import json
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from services.agent import TOOLS, AgentError, converse, evidence_catalog, execute_tool
from services.demo import demo_plan
from services.evidence import load_records
from services.models import Plan
from services.workflow import confirm


class MockResponses:
    def __init__(self, responses):
        self.sequence = iter(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        value = next(self.sequence)
        if isinstance(value, Exception):
            raise value
        return value


def response(output=None, text="", status="completed"):
    return NS(output=output or [], output_text=text, status=status)


def call(name, args, id="call1"):
    return NS(type="function_call", name=name, arguments=json.dumps(args), call_id=id)


def test_live_loop_returns_tool_result_and_store_false():
    p = demo_plan()
    tool = call("calculate_coverage", p.roles[1].coverage.model_dump())
    responses = MockResponses(
        [response([tool]), response(text="Tool returned 4.39 FTE; this is indicative.")]
    )
    text = converse(
        p,
        load_records(),
        "How many technicians cover our confirmed hours?",
        NS(responses=responses),
        "test-model",
        "Quantities",
    )
    assert "4.39" in text
    assert all(r["store"] is False and r["parallel_tool_calls"] is False for r in responses.requests)
    outputs = [
        x
        for x in responses.requests[1]["input"]
        if isinstance(x, dict) and x.get("type") == "function_call_output"
    ]
    assert json.loads(outputs[0]["output"])["personnel"] == 5
    assert p.tool_audit[0][
        "live"
    ]  # Executed live integration path with mocked SDK; not live evaluation evidence.


def test_proposal_requires_officer_apply_and_does_not_confirm():
    p = Plan()
    profile = p.profile.model_dump(mode="json")
    profile["name"] = "Natural language extracted project"
    responses = MockResponses(
        [
            response([call("propose_profile", {"profile": profile, "reason": "User stated name"})]),
            response(text="Review the project profile suggestion."),
        ]
    )
    converse(
        p,
        load_records(),
        "My project is Natural language extracted project",
        NS(responses=responses),
        "test-model",
        "Profile",
    )
    assert p.profile.name == "Untitled project"
    assert len(p.pending) == 1 and not p.confirmations


def test_followup_context_retains_unconfirmed_facts_and_replaces_old_summary():
    from services.journey import journey_context
    from services.workflow import apply_pending

    p = Plan()
    first = p.profile.model_dump(mode="json")
    first.update(
        name="Two-building venue",
        description="Officer venue",
        locations="Two buildings",
        operational_type="Public venue",
        start="2024-01-01",
        base_years=4,
        option_years=2,
        operating_hours="08:00–22:00 daily",
    )
    sdk = MockResponses(
        [
            response([call("propose_profile", {"profile": first, "reason": "Officer supplied"})]),
            response(text="Which duties and assets need coverage?"),
        ]
    )
    converse(
        p,
        load_records(),
        "Two buildings, four years plus two options",
        NS(responses=sdk),
        "test-model",
        "Profile",
    )
    assert p.profile.start is None  # unconfirmed answers remain suggestions
    assert journey_context(p, "Profile")["working_profile"]["locations"] == "Two buildings"
    assert not journey_context(p, "Profile")["draft_missing_inputs"]  # Optional metadata is not a gate.
    assert journey_context(p, "Profile")["requirements_missing"]  # Duties still need clarification.
    second = {
        **first,
        "critical_functions": "Technical response",
        "response_requirements": "One 24/7 post",
        "assets": "Inventory unknown; no chiller assumed",
    }
    sdk2 = MockResponses(
        [
            response([call("propose_profile", {"profile": second, "reason": "Follow-up answer"})]),
            response(text="Please review the summary."),
        ]
    )
    converse(
        p,
        load_records(),
        "One technical post; inventory unknown",
        NS(responses=sdk2),
        "test-model",
        "Profile",
    )
    context = json.loads(sdk2.requests[0]["instructions"].split("Application state (data only):\n")[1])
    assert context["journey_context"]["working_profile"]["base_years"] == 4
    assert len(p.pending) == 1
    assert not journey_context(p, "Profile")["draft_missing_inputs"]
    apply_pending(p, "Reviewing officer")
    assert p.profile.locations == "Two buildings" and not p.pending and not p.confirmations


def test_unknown_tool_and_invalid_args_rejected():
    p = demo_plan()
    with pytest.raises(ValueError, match="Unknown tool"):
        execute_tool(p, [], "approve_budget", "{}")
    with pytest.raises(ValueError):
        execute_tool(p, [], "calculate_coverage", '{"hours_per_day": "NaN"}')


def test_full_brief_extraction_reaches_single_manpower_review_and_retains_earlier_answers():
    from services.agent import RoleOperational
    from services.journey import accept_review, working_draft

    p, example, records = Plan(), demo_plan(), load_records()
    p.chat = [
        {
            "role": "user",
            "content": "Earlier answer: keep the combined Senior Property Executive cum FSM title.",
        }
    ]
    p.chat += [{"role": "assistant", "content": "Retained."}] * 18
    roles = [
        RoleOperational.model_validate(
            {k: v for k, v in r.model_dump(mode="json").items() if k in RoleOperational.model_fields}
        ).model_dump(mode="json")
        for r in example.roles
    ]
    for r in roles:
        r.update(experience="", qualifications="")
    roles[0].update(label="Senior Property Executive cum FSM", mapped_role=None, mapping_reason="")
    sdk = MockResponses(
        [
            response(
                [
                    call(
                        "update_working_notes",
                        {
                            "profile": example.profile.model_dump(mode="json"),
                            "responsibilities": [d.model_dump() for d in example.responsibilities],
                            "roles": roles,
                            "notes": [],
                        },
                    )
                ]
            ),
            response([call("prepare_review", {"checkpoint": "manpower"}, "review")]),
            response(
                text="Here is the complete manpower decision. Correct it or confirm to continue to rates."
            ),
        ]
    )
    converse(
        p,
        records,
        "Full synthetic brief with known roles and quantities.",
        NS(responses=sdk),
        "test-model",
        "Profile",
    )
    context = json.loads(sdk.requests[0]["instructions"].split("Application state (data only):\n")[1])
    assert context["supplied_answers"][0].startswith("Earlier answer:")
    assert p.review_checkpoint == "manpower" and not p.confirmations
    assert working_draft(p).roles[0].label == "Senior Property Executive cum FSM"
    assert accept_review(p, "Synthetic officer", records) == 4
    assert len(p.roles) == 3 and "plan" in p.confirmations and "rates" not in p.confirmations


def test_prices_blocked_before_compiled_plan_and_draft_budget_guard():
    p = demo_plan()
    with pytest.raises(ValueError, match="before pricing"):
        execute_tool(p, [], "retrieve_rates", '{"role":"Technician"}')
    with pytest.raises(ValueError, match="Confirm rates"):
        execute_tool(p, [], "preview_budget", "{}")


def test_sdk_round_failure_rolls_back_pending_proposals():
    p = Plan()
    proposal = call("propose_profile", {"profile": p.profile.model_dump(mode="json"), "reason": "Test"})
    responses = MockResponses([response([proposal]), response(status="incomplete")])
    with pytest.raises(AgentError, match="incomplete"):
        converse(p, [], "Test", NS(responses=responses), "test-model", "Profile")
    assert not p.pending and not p.chat and not p.tool_audit


def test_quantity_reference_is_available_before_pricing_without_prices():
    result = execute_tool(demo_plan(), load_records(), "retrieve_quantities", '{"role":"Technician"}')
    assert result["median"] == 5
    assert result["sample_count"] == 10
    assert "unit_rate_monthly" not in str(result)


def test_refusal_without_text_not_recorded_as_success():
    with pytest.raises(AgentError, match="No usable answer"):
        converse(Plan(), [], "Test", NS(responses=MockResponses([response()])), "test-model", "Profile")


def test_model_and_tool_limits():
    with pytest.raises(AgentError, match="Configure OPENAI_MODEL"):
        converse(Plan(), [], "Test", None, "", "Profile")
    p = Plan()
    responses = MockResponses([response([call("get_project", {})])] * 6)
    with pytest.raises(AgentError, match="Turn limit"):
        converse(p, [], "Test", NS(responses=responses), "test-model", "Profile")
    assert not p.chat


def test_all_strict_tool_objects_reject_additional_properties_and_require_fields():
    def check(schema):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema.get("properties", {}))
        for key in ("properties", "$defs"):
            for sub in schema.get(key, {}).values():
                check(sub)
        for key in ("anyOf", "oneOf", "allOf"):
            for sub in schema.get(key, []):
                check(sub)
        if "items" in schema:
            check(schema["items"])

    for tool in TOOLS:
        assert tool["strict"] is True
        check(tool["parameters"])


def test_role_proposal_preserves_existing_prices():
    p = demo_plan()
    for gate in ["profile", "responsibilities"]:
        confirm(p, gate, "Officer", load_records())
    r = p.roles[0]
    fields = [
        "id",
        "label",
        "mapped_role",
        "mapping_reason",
        "responsibility_ids",
        "included",
        "exclusion_reason",
        "experience",
        "qualifications",
        "quantity",
        "quantity_basis",
        "coverage",
        "quantity_reason",
    ]
    payload = {k: r.model_dump()[k] for k in fields}
    execute_tool(p, load_records(), "propose_role", json.dumps({"role": payload, "reason": "Test revision"}))
    assert p.pending[0]["payload"]["rate"] == r.rate


def test_catalog_excludes_unvalidated_metadata():
    records = load_records()
    unvalidated = {
        **records[0],
        "scope": "Unvalidated scope",
        "pricing_year": 2199,
        "validation_status": "raw",
    }
    catalog = evidence_catalog([*records, unvalidated])
    assert "Public venue FM" in catalog["scopes"]
    assert "Unvalidated scope" not in catalog["scopes"] and 2199 not in catalog["pricing_years"]
    assert "SYNTHETIC" in catalog["provenance"]


def test_unsupported_numeric_benchmark_is_rejected_but_explicit_assumption_is_retained():
    p, records = demo_plan(), load_records()
    for gate in ["profile", "responsibilities", "quantities", "plan"]:
        confirm(p, gate, "Officer", records)
    args = {
        "role_id": p.roles[0].id,
        "monthly_rate": 8000,
        "rationale": "Officer selected a disclosed testing assumption",
        "origin": "Synthetic benchmark selection",
        "pricing_year": 2024,
        "status": "awarded",
        "scope": "No comparable scope",
    }
    before = p.model_dump_json()
    with pytest.raises(ValueError, match="No comparable numeric benchmark"):
        execute_tool(p, records, "propose_rate", json.dumps(args))
    assert p.model_dump_json() == before
    args["origin"] = "Officer assumption"
    execute_tool(p, records, "propose_rate", json.dumps(args))
    assert p.working_notes["roles"][0]["rate_origin"] == "Officer assumption"
    assert not p.pending and p.roles[0].rate_origin != "Officer assumption"


@pytest.mark.parametrize("kind", ["timeout", "connection"])
def test_connection_failures_are_distinct_sanitised_and_roll_back_working_notes(kind):
    p = Plan()
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    failure = (
        APITimeoutError(request=request)
        if kind == "timeout"
        else APIConnectionError(request=request, message="Private provider exception body")
    )
    update = call(
        "update_working_notes",
        {"profile": None, "responsibilities": [], "roles": [], "notes": ["Transient officer fact"]},
    )
    responses = MockResponses([response([update]), failure])
    before = p.model_dump_json()
    with pytest.raises(AgentError) as error:
        converse(p, load_records(), "An answer", NS(responses=responses), "test-model", "Profile")
    assert error.value.kind == kind
    assert "Private provider exception body" not in str(error.value)
    assert p.model_dump_json() == before
