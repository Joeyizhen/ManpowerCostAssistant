"""Small invented workbook controls exercise the importer without publishing private data."""

import hashlib

import pandas as pd
import pytest
import xlsxwriter

from services import reference_data as ref
from services.evidence import load_records, rate_benchmark
from services.reference_import import activate, build_snapshot, import_workbook


def workbook(path):
    rows, controls, details, sources = [], [], [], []
    for bid, rate in enumerate([1000, 2000, 3000], 1):
        details.append(
            {
                "Tender Reference": f"T{bid}",
                "Tenderer": f"B{bid}",
                "Property Name": "P",
                "Tender ID": f"T{bid}",
                "Submission ID": f"B{bid}",
                "Schedule ID": f"S{bid}",
                "Property ID": f"P{bid}",
                "Submission Award Status": "Unknown",
            }
        )
        sources.append(
            {"Public Document Label": f"Source{bid}", "Submission ID": f"B{bid}", "Source ID": f"SRC{bid}"}
        )
        for year in [1, 2, 4]:
            rid = f"R{bid}-{year}"
            rows.append(
                {
                    "Record ID": rid,
                    "Tender Reference": f"T{bid}",
                    "Tenderer": f"B{bid}",
                    "Property Name": "P",
                    "Original Role Title": "FM",
                    "Quantity of Manpower": 1 if year == 1 else 2,
                    "Unit Rate per Month (SGD)": rate * (1 if year == 1 else 1.1),
                    "Quoted Period / Contract Year": f"Year {year}",
                    "Period From": "2024-01-01",
                }
            )
            controls.append(
                {
                    "Record ID": rid,
                    "Role Line ID": f"L{bid}",
                    "Mapping ID": "M1",
                    "Sanitised Source Reference": f"Source{bid} | p1",
                    "Completed Rate Basis": "Source-extracted",
                    "Completed Quantity Basis": "Source-extracted",
                    "Completed Rate Eligibility": "Conditional source-rate candidate",
                    "Completed Quantity Eligibility": "Conditional source-quantity candidate",
                    "Issue Flags": "",
                }
            )
    sheets = {
        "Manpower Data": rows,
        "Tender Details Data Base": details,
        "Record Controls": controls,
        "Source Register": sources,
        "Role Mapping Review": [
            {
                "Mapping ID": "M1",
                "Original Role Title": "FM",
                "Proposed Standard Role": "Facility Manager",
                "Mapping Review": "Reviewed title equivalence",
                "Combined Duties": "Not established",
                "Source Section": "manpower",
            }
        ],
        "Standard Roles": [
            {
                "Role Title": "Facility Manager",
                "Scope": "FM manpower",
                "Typical manpower?": "Yes",
                "PWM applies?": "No",
            }
        ],
        "PWM Trend": [
            {
                "Schedule ID": "TEST-PWM",
                "Job Level": "Invented",
                "Unit": "SGD/hour",
                "Wage Basis": "Gross",
                "Effective From": "2026-01-01",
            }
        ],
    }
    with xlsxwriter.Workbook(path) as book:
        for name in [*sheets, "Ambiguous Keys", "Issue Examples", "Readiness and Issues", "Data Dictionary"]:
            sheet = book.add_worksheet(name)
            values = sheets.get(name, [{"Note": "Synthetic test fixture"}])
            keys = list(values[0])
            sheet.write_row(0, 0, keys)
            for i, row in enumerate(values, 1):
                sheet.write_row(i, 0, [row.get(k) for k in keys])
    return path


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    monkeypatch.setenv("MANPOWER_REFERENCE_SOURCE", "prepared")
    monkeypatch.setenv("MANPOWER_REFERENCE_DIR", str(tmp_path / "refs"))
    return import_workbook(workbook(tmp_path / "test.xlsx"), activate_now=True)


def test_import_hash_stable_ids_idempotence_and_revert(prepared, tmp_path):
    path = tmp_path / "test.xlsx"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    again = import_workbook(path, activate_now=True)
    assert again == prepared
    assert len(list((ref.root() / "snapshots").glob("*.json"))) == 1
    assert len({r["record_id"] for r in prepared["records"]}) == 9
    assert prepared["source_sha256"] == digest
    assert prepared["readiness_report"]["join_problems"] == {}
    row = prepared["records"][0]
    assert row["award_status"] == "Unknown" and row["pricing_year"] is None
    assert row["calendar_date_basis"] == "Synthetic" and row["raw_role_name"] == "FM"
    assert row["mapping_id"] == "M1" and row["role_line_id"] == "L1"
    assert ref.title_mapping("FM") == "Facility Manager"
    activate("synthetic")
    assert ref.active_snapshot() is None
    activate(prepared["dataset_id"])
    assert load_records() == prepared["records"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_shared_rates_annual_pairs_and_no_calendar_inference(prepared):
    rows = load_records()
    bm = rate_benchmark(rows, "Facility Manager", year=2028, status="awarded")
    assert bm["average"] == 2000 and bm["minimum"] == 1000 and bm["maximum"] == 3000
    assert bm["sample_count"] == 3 and bm["filters"]["pricing_year"] is None
    assert not rate_benchmark(rows, "Facility Manager", quantity_unit="FTE")["available"]
    assert not rate_benchmark(rows, "Facility Manager", scope="Invented office scope")["available"]
    annual = ref.annual_reference(rows, general=True)
    assert annual["average"] == pytest.approx(0.1)
    assert annual["pair_count"] == 3 and len(annual["issues"]) == 3
    assert all(p["quantity_changed"] for p in annual["changes"])
    assert all((p["from_year"], p["to_year"]) == (1, 2) for p in annual["changes"])
    assert len(prepared["pwm_observations"]) == 1
    assert not any(r["record_id"] == "TEST-PWM" for r in rows)


@pytest.mark.parametrize("role", [None, "", "   ", "No matching specialist"])
def test_unmapped_roles_never_receive_all_role_benchmarks(prepared, role):
    from services.evidence import comparable, escalation_benchmark, quantity_benchmark

    rows = load_records()
    bm = rate_benchmark(rows, role)
    assert not bm["available"] and bm["sample_count"] == 0
    assert bm["average"] is None and bm["records"] == []
    assert not quantity_benchmark(rows, role)["available"]
    assert not escalation_benchmark(rows, role)["available"]
    assert comparable(rows, role) == []
    # The explicitly requested shared FM cohort remains available.
    assert ref.annual_reference(rows, general=True)["available"]


def test_unmapped_role_has_no_automatic_starting_rate(prepared):
    from services.hybrid import initialise_rates
    from services.models import Plan, Role

    p = Plan(roles=[Role(id="unmatched", label="Specialist without a mapping", quantity=1)])
    before = p.model_dump_json()
    initialise_rates(p, load_records(), None)
    assert p.roles[0].rate is None and p.model_dump_json() == before


def test_mixed_integer_decimal_rate_bounds_render_and_edit(prepared, monkeypatch):
    from streamlit.testing.v1 import AppTest

    import pricing_inputs

    original = pricing_inputs.reference

    def mixed_bounds(plan, role, records):
        return {**original(plan, role, records), "minimum": 1000, "maximum": 3000.25}

    monkeypatch.setattr(pricing_inputs, "reference", mixed_bounds)
    at = AppTest.from_string(
        """
import streamlit as st
from pricing_inputs import starting_prices
from services.models import Plan, Profile, Role
from services.evidence import load_records
st.session_state.setdefault("officer", "Synthetic officer")
st.session_state.setdefault("plan", Plan(
    profile=Profile(start_year=2027, base_years=1, option_years=1),
    roles=[Role(id="r", label="Facility Manager", mapped_role="Facility Manager",
                quantity=1, quantity_unit="headcount", rate=2000.0)]))
def sync(prefix, model, values):
    for suffix, value in values.items():
        st.session_state.setdefault(prefix + suffix, value)
starting_prices(st.session_state.plan, load_records(), "Synthetic officer", lambda: None, sync)
""",
        default_timeout=30,
    ).run()
    assert not at.exception
    slider = next(x for x in at.number_input if x.label.startswith("Monthly rate per"))
    slider.set_value(2500.25).run()
    assert not at.exception
    assert at.session_state["plan"].roles[0].rate == 2500.25


def test_source_origins_and_mapping_independent_of_rate(prepared, tmp_path):
    # Change controls in a second tiny fixture, not the user's workbook.
    import openpyxl

    path = tmp_path / "test.xlsx"
    book = openpyxl.load_workbook(path)
    sheet = book["Record Controls"]
    columns = {cell.value: cell.column for cell in sheet[1]}
    sheet.cell(2, columns["Completed Quantity Basis"], "Synthetic")
    sheet.cell(2, columns["Completed Quantity Eligibility"], "Excluded synthetic quantity")
    sheet.cell(3, columns["Completed Rate Basis"], "Synthetic")
    sheet.cell(4, columns["Issue Flags"], "Partial period")
    book.save(path)
    snapshot = build_snapshot(path)
    a, b, c = snapshot["records"][:3]
    assert a["eligibility"]["rate"] and not a["eligibility"]["quantity"]
    assert not b["eligibility"]["rate"] and b["eligibility"]["quantity"]
    assert c["eligibility"]["rate"] and not c["eligibility"]["annual"]
    book["Role Mapping Review"].cell(2, 5, "Combined")
    book.save(path)
    assert not any(r["eligibility"]["rate"] for r in build_snapshot(path)["records"])


def tender(unit="headcount", role="Facility Manager"):
    return {
        "Test bid": pd.DataFrame(
            [
                {
                    "Role": role,
                    "Contract Year": 1,
                    "Quantity": 2.0,
                    "Quantity Unit": unit,
                    "Monthly Rate (SGD)": 2100.0,
                }
            ]
        )
    }


def test_both_activities_same_evidence_and_unsupported_is_not_zero(prepared):
    from services.agent2.track4 import compare_with_history

    result = compare_with_history(tender(), ref.historical_frame(), pricing_year_from=None)
    row = result.comparisons.iloc[0]
    bm = rate_benchmark(load_records(), "Facility Manager")
    assert row["Historical Median Monthly Rate (SGD)"] == bm["median"]
    assert set(row["Historical Record IDs"].split(", ")) == set(bm["record_ids"])
    assert result.adjustments["Adjustment Factor"].eq(1).all()
    assert result.overall.iloc[0]["Submitted Total Cost (SGD)"] == 50400
    for kwargs, values in [
        ({}, tender("fte")),
        ({"facility_type": "Commercial"}, tender()),
        ({}, tender(role="Unknown role")),
    ]:
        unsupported = compare_with_history(values, ref.historical_frame(), pricing_year_from=None, **kwargs)
        assert pd.isna(unsupported.overall.iloc[0]["Adjusted Historical Expected Total (SGD)"])
        assert unsupported.overall.iloc[0]["Overall Interpretation"] == "Insufficient comparable data"


def test_equal_submission_weights_not_source_row_weights(prepared):
    from copy import deepcopy

    rows = deepcopy(prepared["records"])
    for i in range(20):
        for row in prepared["records"][:3]:
            r = deepcopy(row)
            r.update(record_id=f"extra{i}-{r['record_id']}", role_line_id=f"Extra{i}")
            rows.append(r)
    assert ref.rate_reference(rows, "Facility Manager")["average"] == 2000
    assert ref.annual_reference(rows, general=True)["average"] == pytest.approx(0.1)


def test_prepared_budgeting_prices_compound_without_accepting_suggestions(prepared):
    from datetime import date

    from services.calculations import budget
    from services.future_groups import general_proposal
    from services.hybrid import initialise_rates
    from services.models import Plan, Profile, Role
    from services.pricing import pricing_proposal

    p = Plan(
        profile=Profile(start=date(2027, 1, 1), base_years=2, option_years=0),
        roles=[
            Role(
                id="r",
                label="Facility Manager",
                mapped_role="Facility Manager",
                quantity=1,
                quantity_unit="headcount",
                escalation=[0, 0],
            )
        ],
    )
    initialise_rates(p, load_records(), None)
    assert p.roles[0].rate is None and not p.confirmations
    p.roles[0].rate = 2000
    p.roles[
        0
    ].rate_reason = "Officer allowance aligned to the confirmed deployment; source unit uncertainty retained"
    priced, errors = pricing_proposal(p, load_records(), "Test officer")
    assert not errors and not priced.confirmations
    assert priced.decision_bases[-1].snapshots["r"]["reference_dataset"] == prepared["dataset_id"]
    changed = general_proposal(priced, load_records(), ["r"], 10, "", "", True, "Test officer")
    assert budget(changed, load_records())["contract_total"] == 50400
    assert priced.roles[0].escalation == [0, 0] and not changed.confirmations
    bundle = changed.decision_bases[-1].snapshots["r"]["reference_data"]
    assert "records" not in bundle and bundle["pair_count"] == 3
    activate("synthetic")
    assert set(r["record_id"] for r in ref.recorded_reference_rows(bundle)) == set(bundle["record_ids"])


def test_duplicate_years_fractional_counts_and_legacy_quotes(prepared):
    from copy import deepcopy

    from services.evidence import legacy_records, quoted_schedule

    rows = deepcopy(prepared["records"])
    rows[1]["unit_rate_monthly"] = rows[0]["unit_rate_monthly"]
    assert ref.annual_reference(rows)["changes"][0]["change"] == 0
    duplicate = deepcopy(rows[0])
    duplicate["record_id"] = "duplicate-year"
    rows.append(duplicate)
    assert ref.annual_reference(rows)["pair_count"] == 2
    old = legacy_records()
    first = next(r for r in old if r["contract_year"] == 1)
    years = [first["pricing_year"]]
    assert quoted_schedule(
        load_records(), first["schedule_id"], first["standard_role"], years
    ) == quoted_schedule(old, first["schedule_id"], first["standard_role"], years)


def test_reference_fingerprints_and_saved_prices_are_separate(prepared):
    from services.agent2.track3 import analysis_input_fingerprint
    from services.agent2.track4 import historical_input_fingerprint
    from services.hybrid import initialise_rates
    from services.models import Plan, Role

    p = Plan(
        roles=[
            Role(
                id="r",
                label="Facility Manager",
                mapped_role="Facility Manager",
                quantity=1,
                quantity_unit="headcount",
                rate=9999,
                escalation=[0, 0.0],
            )
        ]
    )
    before = p.model_dump(mode="json")
    initialise_rates(p, load_records(), None)
    assert p.model_dump(mode="json") == before

    frame = tender()["Test bid"]
    first = analysis_input_fingerprint({}, frame, tender(), None)
    history = historical_input_fingerprint(tender(), None, {})
    activate("synthetic")
    assert analysis_input_fingerprint({}, frame, tender(), None) != first
    assert historical_input_fingerprint(tender(), None, {}) != history
    assert p.model_dump(mode="json") == before


def test_four_active_workflows_and_prepared_historical_export(prepared, monkeypatch, tmp_path):
    from datetime import date

    from test_activity_navigation import choose, label, start

    at = start(monkeypatch, tmp_path)
    choose(at, "budgeting", 1)
    assert not at.exception
    at.button(key="activity_back").click().run()
    at.button(key="choose_track_2").click().run()
    assert not at.exception
    at.button(key="activity_change").click().run()
    choose(at, "tender", 3)
    label(at.text_input, "Project name *").set_value("Prepared offline test").run()
    label(at.button, "Save project and continue").click().run()
    label(at.button, "Load synthetic approved budget and 3 tenderers").click().run()
    label(
        at.checkbox, "I have checked the role matches and confirm they can be used for this comparison."
    ).check().run()
    label(at.button, "Confirm data and compare").click().run()
    assert not at.exception and not at.session_state["agent2_result"].overall.empty
    at.button(key="activity_change").click().run()
    choose(at, "tender", 4)
    label(at.text_input, "Project name *").set_value("Prepared historical test").run()
    label(at.date_input, "Contract start date").set_value(date(2026, 1, 1)).run()
    label(at.button, "Save project and continue").click().run()
    label(at.button, "Use example tender").click().run()
    label(at.button, "Verify the submission and match roles").click().run()
    label(at.button, "Confirm roles and choose comparison settings").click().run()
    assert not at.exception
    label(at.button, "Compare tender pricing").click().run()
    assert not at.exception
    assert "Dataset Version" in at.session_state["track4_result"].overall
    label(at.button, "Prepare export").click().run()
    assert not at.exception
    assert any(x.label == "Download tender pricing review" for x in at.get("download_button"))
