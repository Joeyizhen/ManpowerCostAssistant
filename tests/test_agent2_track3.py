"""Offline deterministic checks for Agent 2 Track 3."""

from io import BytesIO

import pandas as pd
import pytest
from openpyxl import load_workbook

from services.agent2.track3 import (
    Track3InputError,
    comparability_issues,
    compare_track3,
    export_track3_excel,
    load_synthetic_budget,
    parse_upload,
    role_mapping_table,
    synthetic_tenderers,
    validation_issues,
)


def test_synthetic_track3_compares_multiple_tenderers_and_flags_risks():
    budget, _ = load_synthetic_budget()
    result = compare_track3(budget, synthetic_tenderers(budget))
    assert set(result.overall["Tenderer"]) == {"Tenderer A", "Tenderer B", "Tenderer C"}
    assert "⚠ Below budget — clarify assumptions" in set(result.overall["Assessment"])
    assert "⚠ Above approved budget — review required" in set(result.overall["Assessment"])
    assert not result.findings.empty
    assert not result.questions.empty
    assert any("Technician" in value for value in result.findings["Finding"])
    assert any("contract year 6" in value for value in result.findings["Finding"])


def test_missing_values_are_flagged_and_not_changed_to_zero():
    frame = pd.DataFrame(
        [{"Role": "Technician", "Contract Year": 1, "Quantity": None, "Quantity Unit": "headcount", "Monthly Rate (SGD)": None, "Source": "test.csv"}]
    )
    issues = validation_issues(frame)
    assert set(issues["Field"]) == {"Quantity", "Monthly Rate (SGD)"}
    assert pd.isna(frame.loc[0, "Quantity"])


def test_csv_upload_aliases_and_excel_export():
    content = b"Manpower Role,Year,Headcount,Monthly Rate\nTechnician,1,4,4200\n"
    frame = parse_upload("Tenderer A.csv", content)
    assert list(frame.columns) == ["Role", "Contract Year", "Quantity", "Quantity Unit", "Monthly Rate (SGD)", "Source"]
    assert frame.loc[0, "Role"] == "Technician"

    budget, _ = load_synthetic_budget()
    result = compare_track3(budget, synthetic_tenderers(budget))
    binary = export_track3_excel({"name": "Synthetic Track 3"}, result, ["Synthetic only"])
    workbook = load_workbook(BytesIO(binary), read_only=True, data_only=False)
    assert {"Project Overview", "Overall Comparison", "Role Comparison", "Findings", "Clarification Questions", "Limitations"} <= set(workbook.sheetnames)


def test_missing_contract_year_is_blocked_before_cost_comparison():
    budget, _ = load_synthetic_budget()
    tender = synthetic_tenderers(budget)["Tenderer A"]
    tender = tender[tender["Contract Year"] < tender["Contract Year"].max()]
    with pytest.raises(Track3InputError, match="comparability issue"):
        compare_track3(budget, {"Tenderer A": tender})


def test_duplicate_role_year_is_blocked_before_cost_comparison():
    budget, _ = load_synthetic_budget()
    tender = synthetic_tenderers(budget)["Tenderer A"]
    tender = pd.concat([tender, tender.iloc[[0]]], ignore_index=True)
    issues = comparability_issues(budget, {"Tenderer A": tender})
    assert "Calculation integrity" in set(issues["Category"])
    with pytest.raises(Track3InputError, match="Duplicate rows"):
        compare_track3(budget, {"Tenderer A": tender})


def test_headcount_fte_mismatch_is_blocked():
    budget, _ = load_synthetic_budget()
    tender = synthetic_tenderers(budget)["Tenderer A"].copy()
    tender["Quantity Unit"] = "fte"
    with pytest.raises(Track3InputError, match="Quantity unit differs"):
        compare_track3(budget, {"Tenderer A": tender})


def test_project_duration_must_match_schedule_coverage():
    budget, _ = load_synthetic_budget()
    tender = synthetic_tenderers(budget)["Tenderer A"]
    with pytest.raises(Track3InputError, match="missing year"):
        compare_track3(budget, {"Tenderer A": tender}, expected_years=7)


def test_traceable_export_includes_verified_inputs_mapping_assumptions_and_audit():
    budget, _ = load_synthetic_budget()
    tenderers = synthetic_tenderers(budget)
    result = compare_track3(budget, tenderers, benchmark_year=2027)
    mappings = pd.DataFrame(
        [{"Original Role": "Technician", "Standard Role": "Technician", "Confirmed": True}]
    )
    binary = export_track3_excel(
        {
            "name": "Synthetic Track 3",
            "budget_confirmed": True,
            "budget_approval_reference": "SYNTHETIC",
            "budget_revision": 1,
        },
        result,
        ["Synthetic only"],
        budget=budget,
        tenderers=tenderers,
        role_mappings=mappings,
    )
    workbook = load_workbook(BytesIO(binary), read_only=True, data_only=False)
    assert {
        "Verified Budget",
        "Verified Tender Data",
        "Role Mapping",
        "Assumptions",
        "Audit Trail",
    } <= set(workbook.sheetnames)


def test_material_findings_are_ranked_and_questions_include_figures():
    budget, _ = load_synthetic_budget()
    result = compare_track3(budget, synthetic_tenderers(budget))
    assert {"Cost Variance to Budget (SGD)", "Cost Variance to Budget (%)", "Source Reference"} <= set(result.findings.columns)
    assert result.findings.iloc[0]["Cost Variance to Budget (SGD)"] == result.findings["Cost Variance to Budget (SGD)"].max()
    assert any("SGD" in question for question in result.questions["Clarification Question"])


def test_role_matching_keeps_tenderer_and_budget_titles_separate():
    budget, _ = load_synthetic_budget()
    tenderers = synthetic_tenderers(budget)
    mapping = role_mapping_table({"Approved budget": budget, **tenderers})
    assert {"Submitted by", "Role title in submission", "Compare as", "Why this is suggested"} == set(
        mapping.columns
    )
    assert set(mapping["Submitted by"]) == {"Approved budget", "Tenderer A", "Tenderer B", "Tenderer C"}
    assert not mapping.duplicated(["Submitted by", "Role title in submission"]).any()
