"""Independent synthetic activity journeys; navigation must never call a model."""

from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

import agent2_track4_views
import agent2_views  # noqa: F401 -- preload UI dependencies before the test script runner


def start(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'activities.db'}")
    monkeypatch.setenv("DEPLOYMENT_MODE", "local")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-credential")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    def forbidden(*args, **kwargs):
        raise AssertionError("Navigation and ordinary calculations must not call a paid model")

    monkeypatch.setattr(agent2_track4_views, "create_client", forbidden)
    return AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=60).run()


def label(elements, text):
    return next(x for x in elements if x.label == text)


def choose(at, activity, track):
    at.button(key="activity_" + activity).click().run()
    at.button(key=f"choose_track_{track}").click().run()
    assert not at.exception


def test_two_activities_four_entries_and_unsubmitted_drafts_survive(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    assert {b.label for b in at.button} == {"Manpower budgeting", "Tender evaluation"}
    choose(at, "budgeting", 1)
    label(at.text_input, "Proposed tender title").set_value("Synthetic budgeting draft").run()
    original_plan_id = at.session_state["plan"].id
    at.button(key="activity_back").click().run()
    assert at.title[0].value == "Manpower budgeting"
    at.button(key="choose_track_2").click().run()
    label(at.text_input, "Proposal / project title").set_value("Synthetic proposal draft").run()
    label(at.text_area, "Paste a table or describe the proposal").set_value("Unapplied original text").run()
    label(
        at.checkbox,
        "The rate column represents inclusive monthly manpower charges per head/FTE, not salary alone",
    ).check().run()
    proposal_id = at.session_state["proposal"].id
    at.button(key="activity_change").click().run()
    choose(at, "tender", 3)
    label(at.text_input, "Project name *").set_value("Synthetic budget comparison draft").run()
    at.button(key="activity_back").click().run()
    assert any("Planned" in x.value for x in at.caption)
    at.button(key="choose_track_4").click().run()
    label(at.text_input, "Project name *").set_value("Synthetic historical review draft").run()
    at.button(key="activity_back").click().run()
    at.button(key="choose_track_3").click().run()
    assert label(at.text_input, "Project name *").value == "Synthetic budget comparison draft"
    at.button(key="activity_back").click().run()
    at.button(key="choose_track_4").click().run()
    assert label(at.text_input, "Project name *").value == "Synthetic historical review draft"
    assert any("not yet available" in x.value for x in at.info)
    at.button(key="activity_change").click().run()
    choose(at, "budgeting", 2)
    assert label(at.text_input, "Proposal / project title").value == "Synthetic proposal draft"
    assert label(at.text_area, "Paste a table or describe the proposal").value == "Unapplied original text"
    assert at.session_state["proposal"].id == proposal_id
    assert label(
        at.checkbox,
        "The rate column represents inclusive monthly manpower charges per head/FTE, not salary alone",
    ).value
    assert not at.session_state["proposal"].interpretation_confirmed
    at.button(key="activity_back").click().run()
    at.button(key="choose_track_1").click().run()
    assert label(at.text_input, "Proposed tender title").value == "Synthetic budgeting draft"
    assert at.session_state["plan"].id == original_plan_id
    assert not at.session_state["plan"].confirmations
    assert not any("TRACK " in x.value or "AGENT " in x.value for x in at.caption)
    at.button(key="activity_change").click().run()
    choose(at, "tender", 3)
    at.session_state["agent2_project"] = {"name": "Restored synthetic project"}
    at.session_state["activity_input_reset"] = 3
    at.run()
    assert label(at.text_input, "Project name *").value == "Restored synthetic project"
    assert not at.exception


def test_standalone_tender_calculations_exports_and_navigation_are_offline(monkeypatch, tmp_path):
    from services.agent2.track3 import compare_track3, load_synthetic_budget, synthetic_tenderers

    at = start(monkeypatch, tmp_path)
    choose(at, "tender", 3)
    label(at.text_input, "Project name *").set_value("Synthetic standalone budget comparison").run()
    label(at.button, "Save project and continue").click().run()
    label(at.button, "Load synthetic approved budget and 3 tenderers").click().run()
    label(
        at.checkbox, "I have checked the role matches and confirm they can be used for this comparison."
    ).check().run()
    label(at.button, "Confirm data and compare").click().run()
    assert not at.exception
    budget, _ = load_synthetic_budget()
    expected = compare_track3(budget, synthetic_tenderers(budget), expected_years=6, benchmark_year=2027)
    pd.testing.assert_frame_equal(at.session_state["agent2_result"].overall, expected.overall)
    before = at.session_state["agent2_result"].overall.copy(deep=True)
    at.button(key="activity_change").click().run()
    choose(at, "tender", 4)
    label(at.text_input, "Project name *").set_value("Synthetic standalone historical review").run()
    label(at.date_input, "Contract start date").set_value(date(2026, 1, 1)).run()
    label(at.button, "Save project and continue").click().run()
    label(at.button, "Use example tender").click().run()
    label(at.button, "Verify the submission and match roles").click().run()
    label(at.button, "Confirm roles and choose comparison settings").click().run()
    label(at.button, "Compare tender pricing").click().run()
    assert not at.exception
    assert at.session_state["track4_result"].narrative.iloc[0]["Status"] == "Deterministic fallback"
    label(at.button, "Prepare export").click().run()
    assert not at.exception
    assert any(x.label == "Download tender pricing review" for x in at.get("download_button"))
    pd.testing.assert_frame_equal(at.session_state["agent2_result"].overall, before)
    assert not at.session_state["plan"].roles
