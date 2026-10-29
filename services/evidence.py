"""Validated synthetic fixture repository. Raw project uploads never enter benchmarks."""

import json
from pathlib import Path
from statistics import fmean, median

from pydantic import Field

from services.models import StrictModel

LABEL = "SYNTHETIC DATA — demonstration only; not real tenders or market evidence"
ROLES = [
    "Facilities Manager",
    "Assistant Facilities Manager",
    "Property Officer",
    "Administrative Assistant",
    "Technician",
    "BMS Engineer",
    "Customer Service Officer",
    "Environmental Engineer",
]
ALIASES = {
    "facility manager": "Facilities Manager",
    "facilities manager (fm)": "Facilities Manager",
    "fm": "Facilities Manager",
    "afm": "Assistant Facilities Manager",
    "assistant fm": "Assistant Facilities Manager",
    "po": "Property Officer",
    "admin executive": "Administrative Assistant",
    "admin exec": "Administrative Assistant",
    "admin assistant": "Administrative Assistant",
    "administrative asst": "Administrative Assistant",
    "tech": "Technician",
    "m&e technician": "Technician",
}


def map_role(label: str) -> str | None:
    # Never conflate Events Manager or M&E Engineer with unrelated titles.
    return next(
        (r for r in ROLES if r.casefold() == label.strip().casefold()), ALIASES.get(label.strip().casefold())
    )


class EvidenceRow(StrictModel):
    record_id: str
    schedule_id: str
    tender_id: str
    submission_year: int = Field(ge=1900, le=2200)
    contract_start_year: int = Field(ge=1900, le=2200)
    contract_duration: int = Field(ge=1, le=20)
    contract_year: int = Field(ge=1, le=20)
    pricing_year: int = Field(ge=1900, le=2200)
    raw_role_name: str
    standard_role: str
    quantity: float = Field(gt=0)
    unit_rate_monthly: float = Field(gt=0)
    currency: str
    rate_basis: str
    scope: str
    inclusions: str
    exclusions: str
    award_status: str
    validation_status: str
    data_origin: str
    source: str
    experience: str | None
    qualifications: str | None


def load_records() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "data/sample/historical.json"
    records = json.loads(path.read_text())
    # Administrative Assistant is the canonical comparison role. Historical
    # schedules used the equivalent title "Admin Executive"; retain the raw
    # submitted title while normalising its verified comparison category.
    for record in records:
        if record.get("standard_role") == "Admin Executive":
            record["standard_role"] = "Administrative Assistant"
    # Keep Track 3 and Track 4 role coverage aligned for the demonstration
    # database. These are labelled derived fixture records, not market data.
    derived_roles = {
        "Senior Facilities Manager": ("Facilities Manager", 1.35),
        "BMS/BOS Officer": ("BMS Engineer", 0.90),
        "Cleaning Supervisor": ("Customer Service Officer", 1.05),
        "Helpdesk Officer": ("Customer Service Officer", 0.95),
        "M&E Engineer": ("Environmental Engineer", 1.00),
        "Property Executive": ("Property Officer", 1.05),
        "Security Supervisor": ("Customer Service Officer", 1.15),
    }
    derived = []
    for role, (source_role, multiplier) in derived_roles.items():
        for record in records:
            if record.get("standard_role") != source_role:
                continue
            clone = dict(record)
            slug = role.casefold().replace("&", "and").replace("/", "-").replace(" ", "-")
            clone["record_id"] = f"{record['record_id']}-{slug}"
            clone["raw_role_name"] = role
            clone["standard_role"] = role
            clone["unit_rate_monthly"] = round(float(record["unit_rate_monthly"]) * multiplier, 2)
            clone["data_origin"] = "derived synthetic demonstration fixture"
            clone["source"] = f"Derived demonstration comparator for {role}"
            derived.append(clone)
    records.extend(derived)
    return [EvidenceRow.model_validate(r).model_dump() for r in records]


def quantile(values, p):
    values = sorted(values)
    ix = (len(values) - 1) * p
    lo = int(ix)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (ix - lo)


def stats(values: list[float], sample_count: int | None = None) -> dict:
    count = len(values) if sample_count is None else sample_count
    enough = count >= 3
    return {
        "sample_count": count,
        "available": enough,
        "average": fmean(values) if enough and values else None,
        **{
            key: quantile(values, p) if enough and values else None
            for key, p in [("minimum", 0), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("maximum", 1)]
        },
    }


def comparable(rows, role, status="awarded", scope=None):
    if status not in ("submitted", "awarded", "both"):
        raise ValueError("Unknown submitted/awarded filter")
    return [
        r
        for r in rows
        if r["standard_role"] == role
        and r["validation_status"] == "validated"
        and r["currency"] == "SGD"
        and r["rate_basis"] == "inclusive monthly per head"
        and r["award_status"] in ("submitted", "awarded")
        and (status == "both" or r["award_status"] == status)
        and (scope is None or r["scope"] == scope)
    ]


def rate_benchmark(rows, role, year=None, status="awarded", scope=None):
    cohort = comparable(rows, role, status, scope)
    if year is not None:
        cohort = [r for r in cohort if r["pricing_year"] == year]
    else:
        # One base-year record per schedule, never repeated annual schedule rows as independent samples.
        cohort = [r for r in cohort if r["contract_year"] == 1]
    unique = {}
    duplicates = []
    for r in cohort:
        key = (r["schedule_id"], r["pricing_year"])
        if key in unique:
            duplicates.append(r["record_id"])
        else:
            unique[key] = r
    cohort = list(unique.values())
    pricing_years = sorted({r["pricing_year"] for r in cohort})
    rate_stats = stats([r["unit_rate_monthly"] for r in cohort])
    if len(pricing_years) > 1:
        rate_stats.update({k: None for k in ["average", "minimum", "p25", "median", "p75", "maximum"]})
        rate_stats["available"] = False
    return {
        "label": LABEL,
        "role": role,
        "filters": {"pricing_year": year, "status": status, "scope": scope},
        "method": "Arithmetic mean and linear quantiles; one rate per distinct schedule at selected pricing year, otherwise base year.",
        **rate_stats,
        "quantity_stats": stats([r["quantity"] for r in cohort]),
        "pricing_years": pricing_years,
        "records": cohort,
        "duplicate_records_excluded": duplicates,
        "limitations": "Synthetic inclusive quotes. No salary breakdown. No verified experience-price relationship."
        + (
            " Base-year rows span different priced years; choose one pricing year before using rate statistics."
            if len(pricing_years) > 1
            else ""
        ),
    }


def position(value, benchmark):
    if not benchmark["available"]:
        return "Insufficient comparable data"
    if value < benchmark["p25"]:
        return "Below comparable typical range"
    if value > benchmark["p75"]:
        return "Above comparable typical range"
    return "Within comparable typical range"


def quantity_benchmark(rows, role, year=None, status="awarded", scope=None):
    reference = rate_benchmark(rows, role, year, status, scope)
    fields = [
        "record_id",
        "schedule_id",
        "tender_id",
        "standard_role",
        "quantity",
        "scope",
        "pricing_year",
        "award_status",
        "source",
        "data_origin",
    ]
    return {
        "label": LABEL,
        "role": role,
        **reference["quantity_stats"],
        "filters": reference["filters"],
        "records": [{k: r[k] for k in fields} for r in reference["records"]],
        "method": "Historical quantity comparison from one record per schedule at selected year (otherwise base year). Linear quantiles.",
        "limitations": "Synthetic quantities are comparisons only, not deployment requirements or validated workload rules.",
    }


def escalation_benchmark(rows, role, status="awarded", scope=None):
    groups = {}
    for r in comparable(rows, role, status, scope):
        groups.setdefault(r["schedule_id"], []).append(r)
    schedules, changes, issues = [], [], []
    for sid, group in groups.items():
        group.sort(key=lambda r: r["contract_year"])
        schedule_changes = []
        year_ids = [r["contract_year"] for r in group]
        if len(year_ids) != len(set(year_ids)):
            issues.append({"schedule": sid, "issue": "Duplicate contract years; schedule excluded"})
            continue
        for prev, row in zip(group, group[1:], strict=False):
            if (
                row["contract_year"] != prev["contract_year"] + 1
                or row["pricing_year"] != prev["pricing_year"] + 1
            ):
                issues.append({"schedule": sid, "issue": "Missing/nonconsecutive years; no YoY across gap"})
                continue
            if any(row[k] != prev[k] for k in ["scope", "rate_basis", "standard_role", "currency"]):
                issues.append({"schedule": sid, "issue": "Scope or rate basis changed; pair excluded"})
                continue
            if prev["unit_rate_monthly"] <= 0:
                issues.append({"schedule": sid, "issue": "Zero/negative prior unit rate; pair excluded"})
                continue
            change = row["unit_rate_monthly"] / prev["unit_rate_monthly"] - 1
            item = {
                "schedule": sid,
                "from_year": prev["pricing_year"],
                "to_year": row["pricing_year"],
                "contract_year": row["contract_year"],
                "change": change,
                "record_ids": [prev["record_id"], row["record_id"]],
            }
            changes.append(item)
            schedule_changes.append(change)
        if schedule_changes:
            consecutive = (
                year_ids == list(range(1, group[0]["contract_duration"] + 1))
                and len(schedule_changes) == len(group) - 1
            )
            schedules.append(
                {
                    "schedule_id": sid,
                    "submission_year": group[0]["submission_year"],
                    "start_year": group[0]["contract_start_year"],
                    "duration": group[0]["contract_duration"],
                    "median_yoy": median(schedule_changes),
                    "complete": consecutive,
                    "cumulative": group[-1]["unit_rate_monthly"] / group[0]["unit_rate_monthly"] - 1
                    if consecutive
                    else None,
                }
            )
    return {
        "label": LABEL,
        "role": role,
        "filters": {"status": status, "scope": scope},
        **stats([s["median_yoy"] for s in schedules]),
        "method": "Each distinct schedule contributes one median YoY to summary statistics; unit rates only.",
        "pair_full_range": [min(x["change"] for x in changes), max(x["change"] for x in changes)]
        if changes
        else None,
        "schedules": schedules,
        "changes": changes,
        "issues": issues,
        "limitations": "Implied tender-price expectations, not realised growth. Causes unknown. Synthetic data.",
    }


def quoted_schedule(rows, schedule_id, role, calendar_years):
    cohort = comparable(rows, role, "both")
    cohort = [r for r in cohort if r["schedule_id"] == schedule_id]
    if len({r["scope"] for r in cohort}) != 1:
        raise ValueError("Quoted schedule must have a consistent scope")
    result = []
    for year in calendar_years:
        matches = [r for r in cohort if r["pricing_year"] == year]
        if len(matches) != 1:
            raise ValueError(f"Quoted schedule requires exactly one comparable price for {year}")
        result.append(matches[0])
    return result
