"""Versioned prepared references; uploads and saved budgets never enter this store."""

import json
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import fmean, median

REFERENCE_SERVICE_VERSION = 3

LIMITATIONS = (
    "Conditional source quotations, not verified awarded prices. Award outcomes and actual calendar pricing "
    "years are unknown. Completed dates are synthetic. Source count/allocation units, inclusions and operational "
    "scope are not certified. No automatic time adjustment or FTE conversion is applied."
)
ADJUSTMENT = "None; source contract-year quotations, synthetic calendar dates excluded"


def root():
    return Path(
        os.getenv("MANPOWER_REFERENCE_DIR") or Path(__file__).resolve().parents[1] / "local_data/references"
    )


@lru_cache(maxsize=8)
def _read(path, stamp):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def active_snapshot():
    if os.getenv("MANPOWER_REFERENCE_SOURCE") == "synthetic":
        return None
    pointer = root() / "active.json"
    if not pointer.exists():
        return None
    value = json.loads(pointer.read_text(encoding="utf-8"))
    if value["active"] == "synthetic":
        return None
    return stored_snapshot(value["active"])


def stored_snapshot(dataset_id):
    path = root() / "snapshots" / (dataset_id + ".json")
    if path.resolve().parent != (root() / "snapshots").resolve():
        raise ValueError("Invalid reference snapshot identifier")
    result = _read(str(path), path.stat().st_mtime_ns)
    if result["dataset_id"] != dataset_id:
        raise ValueError("Reference snapshot and activation pointer disagree")
    return result


def recorded_reference_rows(bundle):
    """Resolve a recorded cohort against its immutable source, not the active replacement."""
    if "records" in bundle:
        return bundle["records"]
    if bundle.get("reference_kind") != "prepared quotation":
        return []
    ids = set(bundle.get("record_ids", []))
    try:
        snapshot = stored_snapshot(bundle["dataset_id"])
    except FileNotFoundError:
        return []  # Keep recorded IDs/methods; never substitute the current source on another machine.
    return [r for r in snapshot["records"] if r["record_id"] in ids]


def prepared(rows):
    return bool(rows and rows[0].get("reference_kind") == "prepared quotation")


def metadata(rows=None):
    if rows is not None:
        if prepared(rows):
            return {
                "dataset_id": rows[0]["dataset_id"],
                "retrieval_method": "equal-submission-source-line-v1",
                "label": "Prepared source quotations",
                "adjustment": ADJUSTMENT,
            }
        return {
            "dataset_id": "synthetic-fixture-v1",
            "label": "Synthetic demonstration",
            "adjustment": "Legacy demonstration scenario",
        }
    snapshot = active_snapshot()
    return (
        {
            "dataset_id": snapshot["dataset_id"],
            "source_name": snapshot["source_name"],
            "retrieval_method": "equal-submission-source-line-v1",
            "label": "Prepared source quotations",
            "adjustment": ADJUSTMENT,
        }
        if snapshot
        else metadata([])
    )


def title_mapping(label):
    snapshot = active_snapshot()
    if snapshot is None:
        return None
    key = label.strip().casefold()
    exact = next(
        (r["Role Title"] for r in snapshot["standard_roles"] if r["Role Title"].casefold() == key), None
    )
    if exact:
        return exact
    matches = [m for m in snapshot["mappings"] if str(m.get("Original Role Title", "")).casefold() == key]
    safe = (
        {m["Proposed Standard Role"] for m in matches if mapping_safe(m)}
        if all(mapping_safe(m) for m in matches)
        else set()
    )
    return next(iter(safe)) if len(safe) == 1 else None


def mapping_safe(mapping):
    return (
        bool(mapping.get("Proposed Standard Role"))
        and mapping.get("Mapping Review")
        in ("Reviewed title equivalence", "Reviewed using explicit cleaning section")
        and mapping.get("Combined Duties") == "Not established"
    )


def statistics(values, count=None):
    values = sorted(values)
    enough = (len(values) if count is None else count) >= 3

    def q(p):
        if not enough or not values:
            return None
        x = (len(values) - 1) * p
        lo = int(x)
        return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (x - lo)

    return {
        "sample_count": len(values) if count is None else count,
        "available": enough,
        "average": fmean(values) if enough else None,
        **{
            k: q(p)
            for k, p in [("minimum", 0), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("maximum", 1)]
        },
    }


def eligible(rows, role=None, use="rate", scope=None):
    return [
        r
        for r in rows
        if r.get("reference_kind") == "prepared quotation"
        and r.get("eligibility", {}).get(use, False)
        and (role is None or r["standard_role"] == role)
        and (scope is None or r["scope"] == scope)
    ]


def rate_reference(rows, role, year=None, status=None, scope=None, contract_year=1, quantity_unit=None):
    # None is a useful all-role filter for cohort analysis, but is never a
    # comparable role for an individual rate recommendation.
    cohort = (
        [r for r in eligible(rows, role, "rate", scope) if r["contract_year"] == contract_year]
        if role and role.strip()
        else []
    )
    if quantity_unit and quantity_unit.casefold() == "fte":
        cohort = []  # A source count/allocation label is not an established FTE denominator.
    groups = defaultdict(list)
    for r in cohort:
        groups[r["submission_id"]].append(r)
    representatives = [median(r["unit_rate_monthly"] for r in group) for group in groups.values()]
    result = statistics(representatives)
    if result["available"]:
        result.update(
            minimum=min(r["unit_rate_monthly"] for r in cohort),
            maximum=max(r["unit_rate_monthly"] for r in cohort),
        )
    return {
        **result,
        "label": "Prepared source quotations — conditional comparison",
        "role": role,
        "filters": {
            "contract_year": contract_year,
            "pricing_year": None,
            "status": "Unknown; no awarded-only claim",
            "scope": scope,
        },
        "method": "Contract-year 1 eligible quotes. Median across each submission's role lines/properties, then arithmetic mean with equal submission weights. Observed min/max use eligible source quotes; quartiles use submission medians. At least three distinct submissions.",
        "records": cohort,
        "record_ids": [r["record_id"] for r in cohort],
        "quote_count": len(cohort),
        "submission_count": len(groups),
        "schedule_count": len({r["schedule_id"] for r in cohort}),
        "pricing_years": [],
        "duplicate_records_excluded": [],
        "quantity_stats": quantity_reference(rows, role, scope=scope),
        "dataset_id": metadata(rows)["dataset_id"],
        "reference_kind": "prepared quotation",
        "limitations": LIMITATIONS,
        "alignment": "Actual pricing year unknown; assess the starting allowance for the intended contract. No inflation adjustment.",
        "source_unit": "Source count/allocation unit; headcount/FTE interpretation unverified",
    }


def quantity_reference(rows, role, year=None, status=None, scope=None):
    cohort = (
        [r for r in eligible(rows, role, "quantity", scope) if r["contract_year"] == 1]
        if role and role.strip()
        else []
    )
    groups = defaultdict(list)
    for row in cohort:
        groups[row["submission_id"]].append(row["quantity"])
    return {
        **statistics([median(v) for v in groups.values()]),
        "label": "Source count comparison",
        "role": role,
        "records": cohort,
        "filters": {"contract_year": 1, "quantity_basis": "Source count; operational basis unconfirmed"},
        "method": "Median source counts within each submission, equal submission weights. Synthetic quantities and unresolved fractional allocations excluded independently of rates.",
        "limitations": "Source counts do not establish staffing requirements, headcount, FTE, relief or a feasible roster.",
        "dataset_id": metadata(rows)["dataset_id"],
    }


def annual_reference(rows, role=None, status=None, scope=None, general=False):
    groups = defaultdict(list)
    for r in eligible(rows, role, "annual", scope):
        if general and (r["source_section"] != "manpower" or r["role_scope"] != "FM manpower"):
            continue
        groups[(r["submission_id"], r["property_id"], r["role_line_id"])].append(r)
    schedules, pairs, issues = [], [], []
    bids = defaultdict(list)
    for (bid, prop, line), group in groups.items():
        ordered = sorted(group, key=lambda r: r["contract_year"])
        years = [r["contract_year"] for r in ordered]
        if len(years) != len(set(years)):
            issues.append({"schedule": line, "issue": "Duplicate role-line contract years; excluded"})
            continue
        changes = []
        for prev, row in zip(ordered, ordered[1:], strict=False):
            if row["contract_year"] != prev["contract_year"] + 1:
                issues.append({"schedule": line, "issue": "Missing year; no bridging"})
                continue
            if any(row[k] != prev[k] for k in ("rate_basis", "standard_role", "source_section", "currency")):
                continue
            change = row["unit_rate_monthly"] / prev["unit_rate_monthly"] - 1
            changes.append(change)
            pairs.append(
                {
                    "schedule": line,
                    "submission_id": bid,
                    "property_id": prop,
                    "role_line_id": line,
                    "from_year": prev["contract_year"],
                    "to_year": row["contract_year"],
                    "contract_year": row["contract_year"],
                    "change": change,
                    "record_ids": [prev["record_id"], row["record_id"]],
                    "previous_rate": prev["unit_rate_monthly"],
                    "next_rate": row["unit_rate_monthly"],
                    "quantity_changed": row["quantity"] != prev["quantity"],
                }
            )
        if changes:
            value = median(changes)
            bids[bid].append(value)
            schedules.append(
                {
                    "schedule_id": line,
                    "submission_id": bid,
                    "property_id": prop,
                    "median_yoy": value,
                    "submission_year": None,
                    "start_year": None,
                    "duration": max(years),
                    "complete": False,
                    "cumulative": None,
                }
            )
    representatives = [median(values) for values in bids.values()]
    ids = {rid for pair in pairs for rid in pair["record_ids"]}
    return {
        **statistics(representatives),
        "label": "Quoted contract-year rate movements",
        "role": role,
        "filters": {"outcome": "Unknown", "calendar_normalisation": "None", "general_manpower_only": general},
        "method": "Next monthly unit rate / previous monthly unit rate - 1, consecutive years within the same submission/property/role line and basis. Median pairs per line, median lines per submission, equal submission weights. Quantity changes never enter the rate formula. No calendar-year inference.",
        "limitations": LIMITATIONS
        + " Repeated source-line basis is a conditional comparison, not certification of unchanged duties or wage components.",
        "schedules": schedules,
        "changes": pairs,
        "issues": issues,
        "pair_full_range": [min(p["change"] for p in pairs), max(p["change"] for p in pairs)]
        if pairs
        else None,
        "records": [r for r in rows if r["record_id"] in ids],
        "record_ids": sorted(ids),
        "submission_count": len(bids),
        "pair_count": len(pairs),
        "dataset_id": metadata(rows)["dataset_id"],
        "reference_kind": "prepared quotation",
        "gaps": [],
        "cohort": {
            "id": "prepared-fm-title-source-line-v1",
            "scope": "Reviewed FM titles and manpower source section; operational scope unknown",
        },
    }


def historical_frame():
    import pandas as pd

    snapshot = active_snapshot()
    if snapshot is None:
        return None
    frame = pd.DataFrame(
        [
            {
                "Record ID": r["record_id"],
                "Tender Reference": r["tender_id"],
                "Tenderer ID": r["submission_id"],
                "Facility Type": "Unknown",
                "Service Category": "Unknown",
                "GFA Band": "Unknown",
                "Region": "Unknown",
                "Standard Role": r["standard_role"],
                "Original Submitted Role": r["raw_role_name"],
                "Contract Year": r["contract_year"],
                "Pricing Year": None,
                "Quantity": r["quantity"],
                "Quantity Unit": "source count/allocation unconfirmed",
                "Monthly Rate (SGD)": r["unit_rate_monthly"],
                "Source File": r["source_file"],
                "Source Sheet or Page": r["source"],
                "Source Row": r["source_row"],
                "Source Type": "Prepared conditional source quotation",
                "Synthetic": r["rate_origin"] == "Synthetic",
                "Dataset Version": snapshot["dataset_id"],
                "Submission ID": r["submission_id"],
                "Property ID": r["property_id"],
                "Role Line ID": r["role_line_id"],
                "Rate Eligible": r["eligibility"]["rate"],
            }
            for r in snapshot["records"]
        ]
    )
    frame.attrs.update(dataset_id=snapshot["dataset_id"], adjustment_method=ADJUSTMENT)
    return frame
