"""Safety boundaries at the combined-agent integration points."""

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from services.agent2.track3 import (
    comparability_issues,
    parse_upload,
    role_mapping_options,
    role_mapping_table,
    validation_issues,
)
from services.evidence import load_records


def composition(*, quantity=2, rate=None):
    book = Workbook()
    sheet = book.active
    sheet.title = "Year 1"
    for cell, value in {
        "C3": "Description",
        "D4": "Unit",
        "E4": "Unit Rate per month",
        "F4": "Quantity",
        "C6": "Technician",
        "D6": "pax",
        "E6": rate,
        "F6": quantity,
    }.items():
        sheet[cell] = value
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def test_composition_keeps_known_quantity_when_its_rate_is_missing():
    frame = parse_upload("invented.xlsx", composition())
    assert frame.iloc[0]["Quantity"] == 2
    assert pd.isna(frame.iloc[0]["Monthly Rate (SGD)"])
    assert "Missing rate" in " ".join(validation_issues(frame)["Issue"])


def test_provenance_text_does_not_make_fractional_headcount_valid():
    frame = parse_upload("invented.xlsx", composition(quantity=0.5, rate=4000))
    assert frame.iloc[0]["Quantity Unit"] == "headcount"
    assert "Fractional quantity" in " ".join(validation_issues(frame)["Issue"])


def test_period_coverage_is_checked_for_each_role():
    frame = pd.DataFrame(
        [
            {
                "Role": role,
                "Contract Year": year,
                "Quantity": 1,
                "Quantity Unit": "headcount",
                "Monthly Rate (SGD)": 4000,
                "Source": "invented",
            }
            for role, year in [("Technician", 1), ("Facilities Manager", 1), ("Facilities Manager", 2)]
        ]
    )
    issues = comparability_issues(frame, {"Tenderer": frame}, expected_years=2)
    assert ((issues["Role"] == "Technician") & issues["Issue"].str.contains("missing year")).any()


def test_shared_synthetic_population_remains_the_checked_in_fixture():
    import json

    expected = json.loads((Path(__file__).resolve().parents[1] / "data/sample/historical.json").read_text())
    assert load_records() == expected


def test_empty_reference_role_list_does_not_fall_back_to_demo_categories():
    frame = pd.DataFrame([{"Role": "Technician"}])
    mapping = role_mapping_table({"Tenderer": frame}, standard_roles=[])
    assert "No verified equivalent" in mapping.iloc[0]["Why this is suggested"]
    assert role_mapping_options(mapping, []) == ["Technician"]


def test_tender_role_choices_use_the_active_prepared_catalogue(monkeypatch):
    monkeypatch.setattr(
        "services.reference_data.active_snapshot",
        lambda: {"standard_roles": [{"Role Title": "Source-only reviewed role"}], "mappings": []},
    )
    frame = pd.DataFrame([{"Role": "Source-only reviewed role"}])
    mapping = role_mapping_table({"Tenderer": frame})
    assert mapping.iloc[0]["Why this is suggested"] == "Title already matches the standard role list"
    assert role_mapping_options(mapping) == ["Source-only reviewed role"]


@pytest.mark.parametrize(
    "field", ["Quantity", "Contract Year", "Monthly Rate (SGD)", "Contract Duration (Years)"]
)
def test_nonfinite_inputs_block_review_without_crashing(field):
    row = {
        "Role": "Technician",
        "Contract Year": 1,
        "Quantity": 1,
        "Quantity Unit": "headcount",
        "Monthly Rate (SGD)": 4000,
        "Contract Duration (Years)": 1,
        "Source": "invented",
    }
    row[field] = float("inf")
    assert not validation_issues(pd.DataFrame([row])).empty
