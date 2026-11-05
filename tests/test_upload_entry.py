"""Upload first, then capture only supplied facts; no automatic approvals or model calls."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_manual_entry_and_reading_keep_missing_values_and_confirmations_separate(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'entry.db'}")
    monkeypatch.setenv("DEPLOYMENT_MODE", "local")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "")
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=90).run()
    at.button(key="activity_budgeting").click().run()
    at.button(key="choose_track_2").click().run()
    p = at.session_state["proposal"]
    assert not at.dataframe and not at.checkbox
    assert at.button(key="proposal_extract_" + p.id).disabled
    at.button(key="proposal_manual_" + p.id).click().run()
    assert at.dataframe and at.checkbox
    assert any(t.label == "Proposal / project title" for t in at.text_input)
    next(t for t in at.text_area if t.label == "Paste a table or describe the proposal").set_value(
        "Role,Quantity,Unit,Monthly rate\nTechnician,4,headcount,\nCleaner,2,headcount,3600"
    ).run()
    at.button(key="proposal_extract_" + p.id).click().run()
    p = at.session_state["proposal"]
    assert not at.exception and len(p.input_rows) == 2
    assert p.input_rows[0]["Monthly rate"] is None
    assert p.input_rows[1]["Monthly rate"] == 3600
    assert all(r["Annual increase (%)"] is None for r in p.input_rows)
    assert any("monthly charge for Technician" in info.value for info in at.info)
    assert p.original is None and not p.plan.confirmations and not p.plan.pending
    assert at.button(key="proposal_capture_" + p.id).disabled
