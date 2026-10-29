"""Deterministic Track 3 comparison logic using verified project rows only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd
import xlsxwriter

from services.evidence import ROLES, load_records, map_role, position, rate_benchmark
from services.integration_contracts import BudgetDocument

REQUIRED_COLUMNS = ["Role", "Contract Year", "Quantity", "Quantity Unit", "Monthly Rate (SGD)", "Source"]
OPTIONAL_TENDER_COLUMNS = [
    "Annual Cost (SGD)",
    "Allowance (SGD)",
    "Overtime (SGD)",
    "Bonus (SGD)",
    "Levy (SGD)",
    "Employer CPF (SGD)",
    "Training (SGD)",
    "Equipment / Uniform (SGD)",
    "Shift / Deployment Basis",
    "Operating Hours per Week",
    "Relief Coverage",
    "Declared Total (SGD)",
]
UPLOAD_TYPES = {"csv", "xlsx", "xls", "json", "pdf", "docx"}

ROLE_COLUMN_NAMES = {"manpower role", "role", "designation"}
CURRENCY_COLUMN_NAMES = {"currency", "rate currency", "pricing currency"}
FREQUENCY_COLUMN_NAMES = {"pricing frequency", "rate frequency", "frequency", "rate basis"}

HIGH_VARIANCE_PERCENT = 0.15
MEDIUM_VARIANCE_PERCENT = 0.05
HIGH_VARIANCE_SGD = 250_000.0
MEDIUM_VARIANCE_SGD = 50_000.0


class Track3InputError(ValueError):
    """A user-facing input problem rather than an application failure."""


@dataclass
class Track3Result:
    overall: pd.DataFrame
    roles: pd.DataFrame
    findings: pd.DataFrame
    questions: pd.DataFrame


def variance_severity(amount: float | None, percentage: float | None) -> str:
    """Prioritise review using both relative and absolute financial impact."""
    absolute_amount = abs(float(amount)) if amount is not None and pd.notna(amount) else 0.0
    absolute_percentage = abs(float(percentage)) if percentage is not None and pd.notna(percentage) else 0.0
    if absolute_percentage >= HIGH_VARIANCE_PERCENT or absolute_amount >= HIGH_VARIANCE_SGD:
        return "High"
    if absolute_percentage >= MEDIUM_VARIANCE_PERCENT or absolute_amount >= MEDIUM_VARIANCE_SGD:
        return "Medium"
    return "Low"


@dataclass(frozen=True)
class ReviewReadiness:
    """Deterministic workflow status derived from the current verified inputs."""

    status: str
    label: str
    reasons: tuple[str, ...]
    current_fingerprint: str | None
    analysis_is_current: bool


def _canonical_frame(frame: pd.DataFrame | None) -> list[dict]:
    if frame is None:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15))


def analysis_input_fingerprint(
    project: dict,
    budget: pd.DataFrame | None,
    tenderers: dict[str, pd.DataFrame],
    role_mappings: pd.DataFrame | None,
) -> str | None:
    """Return a stable digest for every input that can affect Track 3 analysis."""
    if budget is None or not tenderers:
        return None
    relevant_project = {
        key: project.get(key) for key in ("duration", "base_years", "option_years", "start", "currency")
    }
    from services.reference_data import metadata

    payload = {
        "reference": metadata(),
        "project": relevant_project,
        "budget": _canonical_frame(budget),
        "tenderers": {name: _canonical_frame(tenderers[name]) for name in sorted(tenderers)},
        "role_mappings": _canonical_frame(role_mappings),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def review_readiness(
    project: dict,
    budget: pd.DataFrame | None,
    tenderers: dict[str, pd.DataFrame],
    role_mappings: pd.DataFrame | None,
    *,
    budget_confirmed: bool,
    mappings_confirmed: bool,
    result: Track3Result | None,
    analysed_fingerprint: str | None,
) -> ReviewReadiness:
    """Describe what the officer must do next without changing comparison arithmetic."""
    fingerprint = analysis_input_fingerprint(project, budget, tenderers, role_mappings)
    reasons: list[str] = []
    if not project.get("name"):
        reasons.append("Create the review project.")
    if budget is None:
        reasons.append("Add the approved manpower budget.")
    if not tenderers:
        reasons.append("Add at least one tenderer submission.")
    if budget is not None and (
        not budget_confirmed
        or not project.get("budget_approval_reference")
        or not str(project.get("budget_revision", "")).strip()
    ):
        reasons.append("Confirm the approved-budget reference and revision.")
    if budget is not None and not validation_issues(budget).empty:
        reasons.append("Resolve invalid or missing approved-budget values.")
    if any(not validation_issues(frame).empty for frame in tenderers.values()):
        reasons.append("Resolve invalid or missing tenderer values.")
    if budget is not None and tenderers and not mappings_confirmed:
        reasons.append("Review and confirm the role matches.")

    if reasons:
        return ReviewReadiness("checks_required", "Data checks required", tuple(reasons), fingerprint, False)
    if result is None:
        return ReviewReadiness("ready_to_calculate", "Ready to calculate comparison", (), fingerprint, False)
    if analysed_fingerprint != fingerprint:
        return ReviewReadiness(
            "stale",
            "Analysis out of date",
            ("Verified inputs or role matches changed. Recalculate before using the findings.",),
            fingerprint,
            False,
        )
    pending = (
        int((result.findings["Review Status"] == "Pending Review").sum())
        if not result.findings.empty and "Review Status" in result.findings
        else 0
    )
    if pending:
        return ReviewReadiness(
            "review_in_progress",
            "Review in progress",
            (f"{pending} finding(s) still require an officer decision.",),
            fingerprint,
            True,
        )
    return ReviewReadiness("ready", "Ready for management review", (), fingerprint, True)


def _normalise_columns(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    aliases = {
        "manpower role": "Role",
        "role": "Role",
        "designation": "Role",
        "contract year": "Contract Year",
        "year": "Contract Year",
        "quantity": "Quantity",
        "headcount": "Quantity",
        "fte": "Quantity",
        "quantity unit": "Quantity Unit",
        "unit": "Quantity Unit",
        "monthly rate": "Monthly Rate (SGD)",
        "monthly cost": "Monthly Rate (SGD)",
        "monthly rate (sgd)": "Monthly Rate (SGD)",
        "source": "Source",
    }
    renamed = {c: aliases.get(str(c).strip().casefold(), str(c).strip()) for c in frame.columns}
    result = frame.rename(columns=renamed).copy()
    if "Role" not in result:
        raise Track3InputError("No manpower role column was identified. Add a column named Role.")
    if "Contract Year" not in result:
        result["Contract Year"] = 1
    if "Quantity" not in result:
        result["Quantity"] = pd.NA
    if "Quantity Unit" not in result:
        result["Quantity Unit"] = "headcount"
    if "Monthly Rate (SGD)" not in result:
        result["Monthly Rate (SGD)"] = pd.NA
    if "Source" not in result:
        result["Source"] = source
    # Track 3 only requires the core fields. Preserve recognised tender breakdown
    # fields so Track 4 can assess missing cost and deployment assumptions.
    result = result[REQUIRED_COLUMNS + [c for c in OPTIONAL_TENDER_COLUMNS if c in result.columns]]
    result["Role"] = result["Role"].astype("string").str.strip()
    result["Contract Year"] = pd.to_numeric(result["Contract Year"], errors="coerce").astype("Int64")
    result["Quantity"] = pd.to_numeric(result["Quantity"], errors="coerce")
    result["Monthly Rate (SGD)"] = pd.to_numeric(result["Monthly Rate (SGD)"], errors="coerce")
    result["Quantity Unit"] = result["Quantity Unit"].astype("string").str.strip().str.casefold()
    result["Source"] = result["Source"].fillna(source).astype("string")
    for column in [c for c in OPTIONAL_TENDER_COLUMNS if c in result.columns and "(SGD)" in c]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if "Operating Hours per Week" in result:
        result["Operating Hours per Week"] = pd.to_numeric(
            result["Operating Hours per Week"], errors="coerce"
        )
    # Tender templates contain formatted spare rows. Ignore them until a role is entered.
    result = result[result["Role"].notna() & result["Role"].str.strip().ne("")].reset_index(drop=True)
    return result


def _validate_pricing_basis(frame: pd.DataFrame, source: str) -> None:
    """Reject pricing that cannot safely be treated as monthly SGD."""
    columns = {str(column).strip().casefold(): column for column in frame.columns}
    currency_column = next((columns[name] for name in CURRENCY_COLUMN_NAMES if name in columns), None)
    rate_headings = [
        str(column).strip()
        for column in frame.columns
        if str(column).strip().casefold() in {"monthly rate", "monthly cost", "monthly rate (sgd)"}
    ]
    if currency_column is not None:
        currencies = {
            str(value).strip().upper() for value in frame[currency_column].dropna() if str(value).strip()
        }
        if not currencies:
            raise Track3InputError(f"{source}: Currency is blank. Enter SGD for every priced row.")
        unsupported = sorted(currencies - {"SGD", "S$"})
        if unsupported:
            raise Track3InputError(
                f"{source}: only SGD can be compared in this release; found {', '.join(unsupported)}. "
                "Convert the source through an approved process and retain that assumption before upload."
            )
    elif rate_headings and not any(
        "sgd" in heading.casefold() or "s$" in heading.casefold() for heading in rate_headings
    ):
        raise Track3InputError(
            f"{source}: rate currency is not established. Add a Currency column containing SGD "
            "or use the heading Monthly Rate (SGD)."
        )

    frequency_column = next((columns[name] for name in FREQUENCY_COLUMN_NAMES if name in columns), None)
    if frequency_column is not None:
        frequencies = {
            str(value).strip().casefold() for value in frame[frequency_column].dropna() if str(value).strip()
        }
        if not frequencies:
            raise Track3InputError(
                f"{source}: Pricing Frequency is blank. Enter monthly for every priced row."
            )
        unsupported = sorted(frequencies - {"month", "monthly", "per month"})
        if unsupported:
            raise Track3InputError(
                f"{source}: rates must be monthly; found {', '.join(unsupported)}. "
                "Do not compare annual, daily or hourly prices as monthly rates."
            )

    annual_headings = [
        str(column)
        for column in frame.columns
        if any(term in str(column).strip().casefold() for term in ("annual rate", "yearly rate", "per annum"))
    ]
    if annual_headings:
        raise Track3InputError(
            f"{source}: annual pricing column detected ({', '.join(annual_headings)}). "
            "Provide verified monthly rates instead."
        )


def rows_from_budget_document(document: BudgetDocument, source: str | None = None) -> pd.DataFrame:
    rows = []
    for role in document.roles:
        for year in role.years:
            rows.append(
                {
                    "Role": role.original_title,
                    "Contract Year": year.contract_year,
                    "Quantity": year.quantity,
                    "Quantity Unit": role.quantity_unit,
                    "Monthly Rate (SGD)": year.monthly_unit_rate,
                    "Source": source or document.label,
                }
            )
    return _normalise_columns(pd.DataFrame(rows), source or document.label)


def load_synthetic_budget() -> tuple[pd.DataFrame, BudgetDocument]:
    path = Path(__file__).resolve().parents[2] / "data/sample/integration/approved_budget.synthetic.json"
    document = BudgetDocument.model_validate_json(path.read_text(encoding="utf-8"))
    return rows_from_budget_document(document), document


def synthetic_tenderers(budget: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Invented tenders for offline UI/testing; never represented as real evidence."""
    output = {}
    scenarios = {
        "Tenderer A": {"rate": 1.03, "tech_qty": None},
        "Tenderer B": {"rate": 0.91, "tech_qty": 4.0},
        "Tenderer C": {"rate": 1.14, "tech_qty": None},
    }
    for name, scenario in scenarios.items():
        frame = budget.copy()
        frame["Source"] = f"{name} synthetic pricing schedule"
        frame["Monthly Rate (SGD)"] = (frame["Monthly Rate (SGD)"] * scenario["rate"]).round(2)
        if scenario["tech_qty"] is not None:
            frame.loc[frame["Role"].str.contains("Technician", case=False), "Quantity"] = scenario["tech_qty"]
        if name == "Tenderer C":
            year_six = frame["Contract Year"] == frame["Contract Year"].max()
            frame.loc[year_six, "Monthly Rate (SGD)"] = (
                frame.loc[year_six, "Monthly Rate (SGD)"] * 1.12
            ).round(2)
        output[name] = frame
    return output


def parse_upload(name: str, content: bytes) -> pd.DataFrame:
    suffix = name.rsplit(".", 1)[-1].casefold() if "." in name else ""
    if suffix not in UPLOAD_TYPES:
        raise Track3InputError("Use CSV, Excel, JSON, PDF or Word files.")
    if suffix in {"pdf", "docx"}:
        raise Track3InputError(
            "This prototype preserves PDF and Word files but cannot reliably extract their tables yet. "
            "Enter the verified rows manually or upload CSV/Excel/JSON."
        )
    try:
        location_prefix = name
        if suffix == "csv":
            frame = pd.read_csv(BytesIO(content))
            _validate_pricing_basis(frame, name)
        elif suffix in {"xlsx", "xls"}:
            excel = pd.ExcelFile(BytesIO(content))
            schedules = []
            for sheet in excel.sheet_names:
                preview = pd.read_excel(excel, sheet_name=sheet, header=None, nrows=20)
                schedule_headings = {
                    "contract year",
                    "year",
                    "quantity",
                    "headcount",
                    "fte",
                    "quantity unit",
                    "unit",
                    "monthly rate",
                    "monthly cost",
                    "monthly rate (sgd)",
                    "source",
                }
                header_row = next(
                    (
                        row_index
                        for row_index, row in preview.iterrows()
                        if (
                            {str(value).strip().casefold() for value in row.dropna()} & ROLE_COLUMN_NAMES
                            and len(
                                {str(value).strip().casefold() for value in row.dropna()} & schedule_headings
                            )
                            >= 2
                        )
                    ),
                    None,
                )
                if header_row is None:
                    continue
                candidate = pd.read_excel(excel, sheet_name=sheet, header=header_row)
                headings = {str(column).strip().casefold() for column in candidate.columns}
                if not headings.intersection(ROLE_COLUMN_NAMES):
                    continue
                sheet_source = f"{name}, sheet '{sheet}'"
                _validate_pricing_basis(candidate, sheet_source)
                normalised = _normalise_columns(candidate, name)
                normalised["Source"] = [
                    f"{source} | {sheet_source}, row {row_number}"
                    for source, row_number in zip(
                        normalised["Source"].astype(str),
                        range(header_row + 2, len(normalised) + header_row + 2),
                        strict=True,
                    )
                ]
                schedules.append(normalised)
            if not schedules:
                raise Track3InputError(
                    "No worksheet with a Role, Manpower Role or Designation column was found."
                )
            return pd.concat(schedules, ignore_index=True)
        else:
            raw = json.loads(content.decode("utf-8"))
            if isinstance(raw, dict) and raw.get("document_type") == "manpower_budget":
                return rows_from_budget_document(BudgetDocument.model_validate(raw), name)
            frame = pd.DataFrame(raw if isinstance(raw, list) else raw.get("rows", []))
            _validate_pricing_basis(frame, name)
    except Track3InputError:
        raise
    except Exception as exc:
        raise Track3InputError(
            "The file could not be read as a manpower schedule. Check its format and headings."
        ) from exc
    normalised = _normalise_columns(frame, name)
    normalised["Source"] = [
        f"{source} | {location_prefix}, row {row_number}"
        for source, row_number in zip(
            normalised["Source"].astype(str), range(2, len(normalised) + 2), strict=True
        )
    ]
    return normalised


def validation_issues(frame: pd.DataFrame) -> pd.DataFrame:
    issues = []
    for index, row in frame.reset_index(drop=True).iterrows():
        if not str(row["Role"]).strip() or str(row["Role"]) == "<NA>":
            issues.append({"Row": index + 1, "Field": "Role", "Issue": "Missing manpower role"})
        if pd.isna(row["Contract Year"]) or row["Contract Year"] < 1:
            issues.append({"Row": index + 1, "Field": "Contract Year", "Issue": "Missing or invalid year"})
        if pd.isna(row["Quantity"]):
            issues.append(
                {"Row": index + 1, "Field": "Quantity", "Issue": "Missing quantity; not treated as zero"}
            )
        elif row["Quantity"] < 0:
            issues.append({"Row": index + 1, "Field": "Quantity", "Issue": "Quantity cannot be negative"})
        if pd.isna(row["Monthly Rate (SGD)"]):
            issues.append(
                {
                    "Row": index + 1,
                    "Field": "Monthly Rate (SGD)",
                    "Issue": "Missing rate; not treated as zero",
                }
            )
        elif row["Monthly Rate (SGD)"] < 0:
            issues.append(
                {"Row": index + 1, "Field": "Monthly Rate (SGD)", "Issue": "Rate cannot be negative"}
            )
        if row["Quantity Unit"] not in {"headcount", "fte"}:
            issues.append({"Row": index + 1, "Field": "Quantity Unit", "Issue": "Use headcount or FTE"})
    return pd.DataFrame(issues, columns=["Row", "Field", "Issue"])


def _role_key(value: str) -> str:
    return map_role(value) or value.strip()


def role_mapping_table(frames: dict[str, pd.DataFrame] | list[pd.DataFrame]) -> pd.DataFrame:
    """Return one reviewable role match per source document and submitted title."""
    if isinstance(frames, list):
        labelled = {f"Source {index}": frame for index, frame in enumerate(frames, 1)}
    else:
        labelled = frames
    rows = []
    for submitted_by, frame in labelled.items():
        for role in sorted({str(value).strip() for value in frame["Role"].dropna()}):
            suggestion = map_role(role)
            if suggestion and suggestion.casefold() == role.casefold():
                reason = "Title already matches the standard role list"
            elif suggestion:
                reason = f"Suggested from a recognised abbreviation or alternative title: {suggestion}"
            else:
                reason = "No standard match found — choose a role or keep this as a separate role"
            rows.append(
                {
                    "Submitted by": submitted_by,
                    "Role title in submission": role,
                    "Compare as": suggestion or role,
                    "Why this is suggested": reason,
                }
            )
    return pd.DataFrame(rows)


def role_mapping_options(mapping: pd.DataFrame) -> list[str]:
    """Offer reviewed standard roles without forcing unmatched titles into a wrong category."""
    submitted = set(mapping.get("Role title in submission", pd.Series(dtype="string")).astype(str))
    return sorted(set(ROLES) | submitted)


def _mapped_role(value: str, mappings: dict | None, document: str | None) -> str:
    mappings = mappings or {}
    role = str(value)
    for key in ((document, role), f"{document}::{role}" if document else None, role):
        if key is not None and key in mappings:
            return str(mappings[key]).strip()
    return _role_key(role)


def _prepared(
    frame: pd.DataFrame,
    role_mappings: dict | None = None,
    document: str | None = None,
) -> pd.DataFrame:
    issues = validation_issues(frame)
    if not issues.empty:
        raise Track3InputError("Resolve all missing or invalid verified values before analysis.")
    result = frame.copy()
    result["Standard Role"] = result["Role"].map(lambda value: _mapped_role(value, role_mappings, document))
    result["Annual Cost"] = result["Quantity"] * result["Monthly Rate (SGD)"] * 12
    return result


def comparability_issues(
    budget: pd.DataFrame,
    tenderers: dict[str, pd.DataFrame],
    *,
    expected_years: int | None = None,
    role_mappings: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Find issues that could make a budget comparison materially misleading."""
    issues: list[dict] = []
    prepared = {"Approved budget": _prepared(budget, role_mappings, "Approved budget")}
    prepared.update({name: _prepared(frame, role_mappings, name) for name, frame in tenderers.items()})
    budget_years = set(int(value) for value in prepared["Approved budget"]["Contract Year"])
    expected = set(range(1, expected_years + 1)) if expected_years else budget_years

    for document, frame in prepared.items():
        for (role, year), group in frame.groupby(["Standard Role", "Contract Year"], dropna=False):
            if len(group) > 1:
                issues.append(
                    {
                        "Document": document,
                        "Category": "Calculation integrity",
                        "Role": role,
                        "Issue": f"Duplicate rows for contract year {int(year)}",
                    }
                )
        for role, group in frame.groupby("Standard Role"):
            years = set(int(value) for value in group["Contract Year"])
            if years != expected:
                missing = sorted(expected - years)
                extra = sorted(years - expected)
                detail = []
                if missing:
                    detail.append("missing year(s) " + ", ".join(map(str, missing)))
                if extra:
                    detail.append("unexpected year(s) " + ", ".join(map(str, extra)))
                issues.append(
                    {
                        "Document": document,
                        "Category": "Contract-period coverage",
                        "Role": role,
                        "Issue": "; ".join(detail),
                    }
                )
            units = sorted(set(group["Quantity Unit"]))
            if len(units) > 1:
                issues.append(
                    {
                        "Document": document,
                        "Category": "Quantity and unit",
                        "Role": role,
                        "Issue": "Mixed quantity units within the same role: " + ", ".join(units),
                    }
                )

    budget_p = prepared["Approved budget"]
    for tenderer, frame in prepared.items():
        if tenderer == "Approved budget":
            continue
        for role in sorted(set(budget_p["Standard Role"]) & set(frame["Standard Role"])):
            budget_units = set(budget_p.loc[budget_p["Standard Role"] == role, "Quantity Unit"])
            tender_units = set(frame.loc[frame["Standard Role"] == role, "Quantity Unit"])
            if budget_units != tender_units:
                issues.append(
                    {
                        "Document": tenderer,
                        "Category": "Quantity and unit",
                        "Role": role,
                        "Issue": (
                            f"Quantity unit differs from the approved budget "
                            f"({', '.join(sorted(tender_units))} versus {', '.join(sorted(budget_units))})"
                        ),
                    }
                )
    return pd.DataFrame(issues, columns=["Document", "Category", "Role", "Issue"])


def compare_track3(
    budget: pd.DataFrame,
    tenderers: dict[str, pd.DataFrame],
    *,
    variance_threshold: float = 0.10,
    escalation_threshold: float = 0.08,
    expected_years: int | None = None,
    benchmark_year: int | None = None,
    role_mappings: dict[str, str] | None = None,
) -> Track3Result:
    if not tenderers:
        raise Track3InputError("Add at least one tenderer before analysis.")
    comparison_issues = comparability_issues(
        budget,
        tenderers,
        expected_years=expected_years,
        role_mappings=role_mappings,
    )
    if not comparison_issues.empty:
        first = comparison_issues.iloc[0]
        raise Track3InputError(
            f"Resolve {len(comparison_issues)} comparability issue(s) before analysis. "
            f"First issue: {first['Document']} — {first['Role']}: {first['Issue']}."
        )
    budget_p = _prepared(budget, role_mappings, "Approved budget")
    tender_p = {name: _prepared(frame, role_mappings, name) for name, frame in tenderers.items()}
    budget_total = float(budget_p["Annual Cost"].sum())
    overall_rows, role_rows, findings, questions = [], [], [], []
    budget_roles = set(budget_p["Standard Role"])
    records = load_records()

    for tenderer, frame in tender_p.items():
        total = float(frame["Annual Cost"].sum())
        variance = total - budget_total
        pct = variance / budget_total if budget_total else None
        overall_rows.append(
            {
                "Tenderer": tenderer,
                "Approved Budget (SGD)": budget_total,
                "Tendered Cost (SGD)": total,
                "Variance to Budget (SGD)": variance,
                "Variance (%)": pct,
                "Assessment": "⚠ Below budget — clarify assumptions"
                if pct is not None and pct < 0
                else (
                    "⚠ Above approved budget — review required"
                    if pct is not None and pct > 0
                    else "✓ Matches approved budget"
                ),
            }
        )
        if pct is not None and pct != 0:
            direction = "above" if pct > 0 else "below"
            findings.append(
                {
                    "Finding ID": f"{tenderer}-overall-cost".casefold().replace(" ", "-"),
                    "Tenderer": tenderer,
                    "Role": "All roles",
                    "Contract Year": "Full contract",
                    "Category": "Total cost",
                    "Severity": variance_severity(variance, pct),
                    "Cost Variance to Budget (SGD)": variance,
                    "Cost Variance to Budget (%)": pct,
                    "Tendered Cost (SGD)": total,
                    "Approved Budget Value": budget_total,
                    "Source Reference": ", ".join(sorted(set(frame["Source"].astype(str)))),
                    "Finding": f"Full-contract manpower cost is {abs(pct):.1%} {direction} the approved budget.",
                    "Why it matters": "The total difference may reflect staffing, rate, coverage or pricing assumptions that require clarification.",
                    "Supporting evidence": f"Approved budget SGD {budget_total:,.2f}; tendered cost SGD {total:,.2f}.",
                    "Suggested action": "Request a quantified breakdown of the quantity, unit-rate and escalation drivers.",
                    "Review Status": "Pending Review",
                    "Officer Comment": "",
                }
            )
            questions.append(
                {
                    "Tenderer": tenderer,
                    "Related Role": "All roles",
                    "Clarification Question": (
                        f"Your full-contract manpower cost is SGD {total:,.2f}, which is SGD {abs(variance):,.2f} "
                        f"({abs(pct):.1%}) {direction} the approved budget. Please quantify the quantity, "
                        "unit-rate and escalation drivers of this difference."
                    ),
                }
            )
        tender_roles = set(frame["Standard Role"])
        for role in sorted(budget_roles | tender_roles):
            b = budget_p[budget_p["Standard Role"] == role]
            t = frame[frame["Standard Role"] == role]
            b_y1 = b[b["Contract Year"] == b["Contract Year"].min()] if not b.empty else b
            t_y1 = t[t["Contract Year"] == t["Contract Year"].min()] if not t.empty else t
            b_qty = float(b_y1["Quantity"].sum()) if not b_y1.empty else 0.0
            t_qty = float(t_y1["Quantity"].sum()) if not t_y1.empty else 0.0
            b_rate = float(b_y1["Monthly Rate (SGD)"].mean()) if not b_y1.empty else None
            t_rate = float(t_y1["Monthly Rate (SGD)"].mean()) if not t_y1.empty else None
            b_cost = float(b["Annual Cost"].sum()) if not b.empty else 0.0
            t_cost = float(t["Annual Cost"].sum()) if not t.empty else 0.0
            cost_pct = (t_cost - b_cost) / b_cost if b_cost else None
            benchmark = rate_benchmark(
                records,
                role,
                year=benchmark_year,
                status="both",
                quantity_unit=str(t_y1["Quantity Unit"].iloc[0]) if not t_y1.empty else None,
            )
            benchmark_text = position(t_rate, benchmark) if t_rate is not None else "No submitted rate"
            role_rows.append(
                {
                    "Tenderer": tenderer,
                    "Standard Role": role,
                    "Approved Budget Quantity": b_qty,
                    "Tendered Quantity": t_qty,
                    "Quantity Variance": t_qty - b_qty,
                    "Approved Budget Monthly Rate (SGD)": b_rate,
                    "Tendered Monthly Rate (SGD)": t_rate,
                    "Role Cost Variance to Budget (SGD)": t_cost - b_cost,
                    "Role Cost Variance to Budget (%)": cost_pct,
                    "Comparison with Similar Past Rates": benchmark_text,
                    "Similar Past Rates Found": benchmark["sample_count"],
                }
            )
            if role in budget_roles and role not in tender_roles:
                finding = f"{role} is missing from the tenderer's verified schedule."
                action = f"Confirm how {role} responsibilities will be covered."
                severity = "High"
                category = "Missing role / coverage"
            elif b_qty and t_qty < b_qty:
                finding = f"{tenderer} proposes {t_qty:g} versus {b_qty:g} budgeted for {role}."
                action = "Clarify deployment coverage, shifts, relief and responsibility allocation."
                severity = "High" if t_qty <= b_qty * 0.75 else "Medium"
                category = "Staffing quantity and deployment"
            elif cost_pct is not None and abs(cost_pct) >= variance_threshold:
                finding = f"{role} contract cost differs from budget by {cost_pct:.1%}."
                action = "Request the quantity, unit-rate and escalation basis for this role."
                severity = variance_severity(t_cost - b_cost, cost_pct)
                category = "Role cost variance"
            else:
                finding = action = severity = category = None
            if finding:
                fid = f"{tenderer}-{role}".casefold().replace(" ", "-")
                findings.append(
                    {
                        "Finding ID": fid,
                        "Tenderer": tenderer,
                        "Role": role,
                        "Contract Year": "Full contract",
                        "Category": category,
                        "Severity": severity,
                        "Cost Variance to Budget (SGD)": t_cost - b_cost,
                        "Cost Variance to Budget (%)": cost_pct,
                        "Tendered Cost (SGD)": t_cost,
                        "Approved Budget Value": b_cost,
                        "Source Reference": ", ".join(sorted(set(t["Source"].astype(str))))
                        if not t.empty
                        else "No submitted row",
                        "Finding": finding,
                        "Why it matters": "The difference may affect service coverage or budget sufficiency.",
                        "Supporting evidence": f"Budget cost SGD {b_cost:,.2f}; tender cost SGD {t_cost:,.2f}.",
                        "Suggested action": action,
                        "Review Status": "Pending Review",
                        "Officer Comment": "",
                    }
                )
                questions.append(
                    {
                        "Tenderer": tenderer,
                        "Related Role": role,
                        "Clarification Question": (
                            f"For {role}, the submitted full-contract cost is SGD {t_cost:,.2f} versus "
                            f"SGD {b_cost:,.2f} in the approved budget. {action}"
                        ),
                    }
                )

        for role, group in frame.groupby("Standard Role"):
            ordered = group.sort_values("Contract Year")
            changes = ordered["Monthly Rate (SGD)"].pct_change().dropna()
            if not changes.empty and float(changes.max()) > escalation_threshold:
                peak_index = changes.idxmax()
                year = int(ordered.loc[peak_index, "Contract Year"])
                rate = float(changes.loc[peak_index])
                findings.append(
                    {
                        "Finding ID": f"{tenderer}-{role}-escalation".casefold().replace(" ", "-"),
                        "Tenderer": tenderer,
                        "Role": role,
                        "Contract Year": year,
                        "Category": "Year-on-year manpower cost escalation",
                        "Severity": "High" if rate >= HIGH_VARIANCE_PERCENT else "Medium",
                        "Cost Variance to Budget (SGD)": None,
                        "Cost Variance to Budget (%)": rate,
                        "Tendered Cost (SGD)": float(ordered.loc[peak_index, "Monthly Rate (SGD)"]),
                        "Approved Budget Value": None,
                        "Source Reference": str(ordered.loc[peak_index, "Source"]),
                        "Finding": f"{role} increases by {rate:.1%} in contract year {year}.",
                        "Why it matters": "The increase exceeds the review threshold and may drive later-year cost.",
                        "Supporting evidence": f"Verified year-by-year rates in {ordered.iloc[0]['Source']}.",
                        "Suggested action": "Clarify the escalation, policy increase and any double counting.",
                        "Review Status": "Pending Review",
                        "Officer Comment": "",
                    }
                )
                questions.append(
                    {
                        "Tenderer": tenderer,
                        "Related Role": role,
                        "Clarification Question": f"Explain the {rate:.1%} increase in contract year {year} and confirm whether policy and inflation effects overlap.",
                    }
                )

    finding_frame = pd.DataFrame(findings)
    if not finding_frame.empty:
        finding_frame["_severity"] = (
            finding_frame["Severity"].map({"High": 0, "Medium": 1, "Low": 2}).fillna(3)
        )
        finding_frame = (
            finding_frame.sort_values(
                ["_severity", "Cost Variance to Budget (SGD)", "Tenderer", "Category"],
                ascending=[True, False, True, True],
                na_position="last",
            )
            .drop(columns="_severity")
            .reset_index(drop=True)
        )
    question_frame = pd.DataFrame(questions).drop_duplicates()
    if not question_frame.empty:
        severity_lookup = finding_frame.set_index(["Tenderer", "Role"])["Severity"].to_dict()
        question_frame["Priority"] = question_frame.apply(
            lambda row: severity_lookup.get((row["Tenderer"], row["Related Role"]), "Medium"),
            axis=1,
        )
        question_frame["_priority"] = (
            question_frame["Priority"].map({"High": 0, "Medium": 1, "Low": 2}).fillna(3)
        )
        question_frame = (
            question_frame.sort_values(["_priority", "Tenderer", "Related Role"])
            .drop(columns="_priority")
            .reset_index(drop=True)
        )
        question_frame.insert(0, "S/N", range(1, len(question_frame) + 1))
    return Track3Result(
        overall=pd.DataFrame(overall_rows),
        roles=pd.DataFrame(role_rows),
        findings=finding_frame,
        questions=question_frame,
    )


def export_track3_excel(
    project: dict,
    result: Track3Result,
    limitations: list[str],
    *,
    budget: pd.DataFrame | None = None,
    tenderers: dict[str, pd.DataFrame] | None = None,
    role_mappings: pd.DataFrame | None = None,
    thresholds: dict[str, float] | None = None,
) -> bytes:
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True, "strings_to_formulas": False})
    workbook.set_properties({"title": "Track 3 Tender Review", "comments": "Decision support only"})
    title = workbook.add_format({"bold": True, "font_size": 18, "font_color": "#173B63"})
    header = workbook.add_format(
        {"bold": True, "font_color": "white", "bg_color": "#147D74", "text_wrap": True}
    )
    wrap = workbook.add_format({"text_wrap": True, "valign": "top"})
    money = workbook.add_format({"num_format": "S$ #,##0.00;[Red](S$ #,##0.00)", "valign": "top"})
    percent = workbook.add_format({"num_format": "0.0%;[Red](0.0%)", "valign": "top"})

    def add_sheet(name: str, frame: pd.DataFrame):
        ws = workbook.add_worksheet(name[:31])
        ws.hide_gridlines(2)
        ws.write(0, 0, name, title)
        ws.write_row(2, 0, list(frame.columns), header)
        for r, values in enumerate(frame.itertuples(index=False, name=None), 3):
            for c, value in enumerate(values):
                fmt = (
                    percent
                    if "(%)" in str(frame.columns[c])
                    else money
                    if "SGD" in str(frame.columns[c])
                    else wrap
                )
                ws.write(r, c, "" if pd.isna(value) else value, fmt)
        for c, column in enumerate(frame.columns):
            ws.set_column(c, c, min(48, max(14, len(str(column)) + 3)), wrap)
        ws.freeze_panes(3, 1)
        ws.autofilter(2, 0, max(2, len(frame) + 2), max(0, len(frame.columns) - 1))
        return ws

    overview = pd.DataFrame(
        [
            ("Project Name", project.get("name", "")),
            ("Tender Reference", project.get("reference", "")),
            ("Facility Type", project.get("facility_type", "")),
            ("Service Category", project.get("service", "")),
            ("Base Contract Period (Years)", project.get("base_years", project.get("duration", ""))),
            ("Option Period (Years)", project.get("option_years", 0)),
            ("Total Potential Contract Period (Years)", project.get("duration", "")),
            ("Approved Budget Source", project.get("budget_source", "")),
            ("Decision Boundary", "Decision support only; no award recommendation"),
        ],
        columns=["Field", "Value"],
    )
    add_sheet("Project Overview", overview)
    if budget is not None:
        add_sheet("Verified Budget", budget)
    if tenderers:
        verified_tenders = pd.concat(
            [frame.assign(Tenderer=name) for name, frame in tenderers.items()], ignore_index=True
        )
        add_sheet("Verified Tender Data", verified_tenders)
    if role_mappings is not None:
        add_sheet("Role Mapping", role_mappings)
    threshold_values = thresholds or {"Overall / role cost variance": 0.10, "Annual escalation": 0.08}
    add_sheet(
        "Assumptions",
        pd.DataFrame(
            [
                (name, value, "Officer review trigger; not an award rule")
                for name, value in threshold_values.items()
            ],
            columns=["Threshold", "Value", "Purpose"],
        ),
    )
    add_sheet("Overall Comparison", result.overall)
    add_sheet("Role Comparison", result.roles)
    add_sheet("Findings", result.findings)
    add_sheet("Clarification Questions", result.questions)
    add_sheet("Limitations", pd.DataFrame({"Limitation / accepted exception": limitations}))
    add_sheet(
        "Audit Trail",
        pd.DataFrame(
            [
                ("Budget reference confirmed", project.get("budget_confirmed", False)),
                ("Budget approval reference", project.get("budget_approval_reference", "")),
                ("Budget revision", project.get("budget_revision", "")),
                ("Reviewer", project.get("reviewer", "")),
                (
                    "Pending findings at export",
                    int((result.findings["Review Status"] == "Pending Review").sum())
                    if not result.findings.empty
                    else 0,
                ),
            ],
            columns=["Audit item", "Value"],
        ),
    )
    workbook.close()
    output.seek(0)
    return output.getvalue()
