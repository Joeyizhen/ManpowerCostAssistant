"""Completed traces cannot consume more of the original live-test allowance."""

import json
from types import SimpleNamespace

import pytest

from scripts import evaluate_conversation


def test_completed_conversation_resume_stops_before_client_creation(tmp_path, monkeypatch):
    trace = tmp_path / "completed.jsonl"
    trace.write_text(json.dumps({"kind": "completed", "model": "test-model"}), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["evaluate_conversation", "--allow-live", "--resume", str(trace)])
    monkeypatch.setattr(
        evaluate_conversation, "settings", lambda: SimpleNamespace(api_key="test", model="test-model")
    )
    monkeypatch.setattr(
        evaluate_conversation, "create_client", lambda _: pytest.fail("No client should be created")
    )
    with pytest.raises(SystemExit) as error:
        evaluate_conversation.main()
    assert error.value.code == 2
