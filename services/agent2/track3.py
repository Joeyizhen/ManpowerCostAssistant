"""Deterministic Track 3 comparison logic using verified project rows only."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import xlsxwriter

from services.evidence import ROLES, load_records, map_role, position, rate_benchmark

TRACK3_COMPARISON_ROLES = ROLES + [
    "Senior Facilities Manager",
    "BMS/BOS Officer",
    "Cleaning Supervisor",
    "Helpdesk Officer",
    "M&E Engineer",
    "Property Executive",
    "Security Supervisor",
]
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
    "Contract Duration (Years)",
    "Quoted Pricing Year",
    "Additional Escalation Applied (%)",
    "Officer Justification",
    "Officer Assumption Confirmed",
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


_YEAR_PATTERN = re.compile(r"(?:contract\s*)?(?:yr|year)\s*[-:]?\s*(\d{1,2})", re.IGNORECASE)
_ROLE_PREFIX_PATTERN = re.compile(r"^\s*(?:[a-z]|\d+)\s*[\)\.]\s*", re.IGNORECASE)
_COMPOSITION_ROLE_HEADINGS = {
    "description",
    "manpower description",
    "role",
    "manpower role",
    "designation",
    "position",
    "job title",
    "post",
}


def _is_monthly_rate_heading(value: str) -> bool:
    value = value.casefold().replace("\n", " ")
    return (
        any(term in value for term in ("rate", "price", "unit cost"))
        and any(term in value for term in ("month", "monthly", "/ mth", "/mth"))
        and "total" not in value
    )


def _is_quantity_heading(value: str) -> bool:
    value = value.casefold().replace("\n", " ")
    return any(
        term in value
        for term in ("quantity", "headcount", "no. of pax", "number of pax", "fte")
    )


def _is_unit_heading(value: str) -> bool:
    return value.casefold().strip() in {"unit", "uom", "unit of measure", "unit of measurement"}


def _contract_year_from_sheet(sheet: str, preview: pd.DataFrame) -> int | None:
    """Read the contract year from a worksheet name or its title rows."""
    candidates = [sheet]
    candidates.extend(
        str(value)
        for value in preview.to_numpy().ravel()
        if pd.notna(value) and str(value).strip()
    )
    for candidate in candidates:
        match = _YEAR_PATTERN.search(candidate)
        if match:
            return int(match.group(1))
    return None


def _clean_role_label(value: object) -> str:
    return _ROLE_PREFIX_PATTERN.sub("", str(value).strip()).strip()


def _parse_composition_rate_sheet(
    preview: pd.DataFrame, *, file_name: str, sheet: str
) -> pd.DataFrame | None:
    """Parse BCT-style site blocks with Description + repeated rate/quantity columns."""
    if preview.empty:
        return None
    normalised = preview.map(lambda value: str(value).strip().casefold() if pd.notna(value) else "")
    role_heading_cells = [
        (row, col)
        for row in range(min(20, len(normalised)))
        for col in range(normalised.shape[1])
        if normalised.iat[row, col] in _COMPOSITION_ROLE_HEADINGS
    ]
    subheader_row = next(
        (
            row
            for row in range(min(20, len(normalised)))
            if any(_is_monthly_rate_heading(value) for value in normalised.iloc[row])
            and any(_is_quantity_heading(value) for value in normalised.iloc[row])
        ),
        None,
    )
    if subheader_row is None:
        return None
    rate_columns = [
        col
        for col, value in enumerate(normalised.iloc[subheader_row])
        if _is_monthly_rate_heading(value)
    ]
    if not rate_columns:
        return None
    unit_col = next(
        (col for col, value in enumerate(normalised.iloc[subheader_row]) if _is_unit_heading(value)),
        max(rate_columns[0] - 1, 0),
    )
    eligible_role_headings = [cell for cell in role_heading_cells if cell[0] <= subheader_row]
    if eligible_role_headings:
        description_row, role_col = eligible_role_headings[-1]
    else:
        # In many tender forms the role header is merged, blank or named unpredictably.
        # The role values still sit immediately to the left of the pax/FTE unit column.
        description_row, role_col = max(subheader_row - 1, 0), max(unit_col - 1, 0)
        evidence_rows = 0
        for row in range(subheader_row + 1, min(len(preview), subheader_row + 30)):
            role_value = preview.iat[row, role_col]
            unit_value = preview.iat[row, unit_col]
            if (
                pd.notna(role_value)
                and str(role_value).strip()
                and pd.notna(unit_value)
                and str(unit_value).strip().casefold() in {"pax", "headcount", "fte"}
            ):
                evidence_rows += 1
        if evidence_rows < 1:
            return None
    blocks: list[tuple[int, int, str]] = []
    for rate_col in rate_columns:
        quantity_col = next(
            (
                col
                for col in range(rate_col + 1, min(rate_col + 4, normalised.shape[1]))
                if _is_quantity_heading(normalised.iat[subheader_row, col])
            ),
            None,
        )
        if quantity_col is None:
            continue
        site = ""
        for row in range(description_row, subheader_row + 1):
            candidate = preview.iat[row, rate_col] if rate_col < preview.shape[1] else None
            if pd.notna(candidate) and str(candidate).strip() and "unit rate" not in str(candidate).casefold():
                site = str(candidate).strip().replace("\n", " ")
                break
        blocks.append((rate_col, quantity_col, site or f"site block {len(blocks) + 1}"))
    if not blocks:
        return None
    contract_year = _contract_year_from_sheet(sheet, preview)
    if contract_year is None:
        raise Track3InputError(
            f"{file_name}, sheet '{sheet}': the manpower table was detected, but its contract "
            "year could not be established. Add a Year/Contract Year field, include Year 1 (or Yr1) "
            "in the worksheet title, or use the flat upload template."
        )

    rows: list[dict] = []
    excluded_labels = ("total monthly cost", "requirements and scope", "amount to be carried")
    for row_index in range(subheader_row + 1, len(preview)):
        raw_role = preview.iat[row_index, role_col] if role_col < preview.shape[1] else None
        if pd.isna(raw_role) or not str(raw_role).strip():
            continue
        role = _clean_role_label(raw_role)
        lowered_role = role.casefold()
        if any(label in lowered_role for label in excluded_labels):
            continue
        raw_unit = preview.iat[row_index, unit_col] if unit_col < preview.shape[1] else None
        unit = str(raw_unit).strip().casefold() if pd.notna(raw_unit) else ""
        if unit not in {"pax", "headcount", "fte"}:
            # Lump sums such as training and transition are not manpower roles.
            continue

        deployments = []
        missing_rate_for_quantity = False
        for rate_col, quantity_col, site in blocks:
            rate = pd.to_numeric(preview.iat[row_index, rate_col], errors="coerce")
            quantity = pd.to_numeric(preview.iat[row_index, quantity_col], errors="coerce")
            if pd.notna(quantity) and float(quantity) > 0:
                if pd.isna(rate):
                    missing_rate_for_quantity = True
                else:
                    deployments.append((float(rate), float(quantity), site))
        if not deployments and not missing_rate_for_quantity:
            continue
        total_quantity = sum(quantity for _, quantity, _ in deployments)
        total_cost = sum(rate * quantity for rate, quantity, _ in deployments)
        monthly_rate = (
            pd.NA
            if missing_rate_for_quantity or total_quantity <= 0
            else total_cost / total_quantity
        )
        sites = ", ".join(site for _, _, site in deployments)
        rows.append(
            {
                "Role": role,
                "Contract Year": contract_year,
                "Quantity": total_quantity if total_quantity > 0 else pd.NA,
                # "pax" is a person/headcount unit in tender schedules. Decimal
                # quantities represent a shared deployment across sites, not a
                # silent conversion to a different pricing unit.
                "Quantity Unit": "fte" if unit == "fte" else "headcount",
                "Monthly Rate (SGD)": monthly_rate,
                "Source": (
                    f"{file_name}, sheet '{sheet}', row {row_index + 1}"
                    + (f"; aggregated across {sites}" if sites else "")
                ),
            }
        )
    if not rows:
        return None
    return _normalise_columns(pd.DataFrame(rows), f"{file_name}, sheet '{sheet}'")


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
    payload = {
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
        "contract duration (years)": "Contract Duration (Years)",
        "contract duration": "Contract Duration (Years)",
        "quoted pricing year": "Quoted Pricing Year",
        "additional escalation applied (%)": "Additional Escalation Applied (%)",
        "additional escalation": "Additional Escalation Applied (%)",
        "officer justification": "Officer Justification",
        "officer assumption confirmed": "Officer Assumption Confirmed",
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
    for column in [
        "Contract Duration (Years)",
        "Quoted Pricing Year",
        "Additional Escalation Applied (%)",
    ]:
        if column in result:
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
                preview = pd.read_excel(excel, sheet_name=sheet, header=None)
                header_preview = preview.head(20)
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
                        for row_index, row in header_preview.iterrows()
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
                    composition = _parse_composition_rate_sheet(
                        preview, file_name=name, sheet=sheet
                    )
                    if composition is not None:
                        schedules.append(composition)
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
                    "No supported manpower schedule was found. Use either a flat table with a Role, "
                    "Manpower Role or Designation column, or a composition-of-rates sheet containing "
                    "Description with monthly Unit Rate and Quantity columns."
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
        quantity_unit = str(row["Quantity Unit"]).strip().casefold()
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
        elif (
            quantity_unit == "headcount"
            and float(row["Quantity"]) != int(float(row["Quantity"]))
            and "aggregated across" not in str(row.get("Source", "")).casefold()
        ):
            issues.append(
                {
                    "Row": index + 1,
                    "Field": "Quantity Unit",
                    "Issue": "Fractional quantity is labelled headcount; confirm it as FTE or enter a whole headcount",
                }
            )
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
        if quantity_unit not in {"headcount", "fte"}:
            issues.append({"Row": index + 1, "Field": "Quantity Unit", "Issue": "Use headcount or FTE"})
        if "Contract Duration (Years)" in frame and pd.isna(row["Contract Duration (Years)"]):
            issues.append(
                {
                    "Row": index + 1,
                    "Field": "Contract Duration (Years)",
                    "Issue": "Missing contract duration; confirm the period before calculation",
                }
            )
        if (
            "Quoted Pricing Year" in frame
            and "Additional Escalation Applied (%)" in frame
            and pd.notna(row["Quoted Pricing Year"])
            and int(row["Quoted Pricing Year"]) >= date.today().year
            and pd.notna(row["Additional Escalation Applied (%)"])
            and float(row["Additional Escalation Applied (%)"]) > 0
        ):
            issues.append(
                {
                    "Row": index + 1,
                    "Field": "Additional Escalation Applied (%)",
                    "Issue": "Future quoted rate already has additional escalation; confirm the escalation is not applied twice",
                }
            )
    if "Contract Duration (Years)" in frame:
        durations = pd.to_numeric(frame["Contract Duration (Years)"], errors="coerce").dropna()
        if not durations.empty and durations.nunique() == 1:
            duration = int(durations.iloc[0])
            for role, group in frame.groupby("Role"):
                years = set(pd.to_numeric(group["Contract Year"], errors="coerce").dropna().astype(int))
                missing = sorted(set(range(1, duration + 1)) - years)
                if missing:
                    issues.append(
                        {
                            "Row": int(group.index[0]) + 1,
                            "Field": "Contract Year",
                            "Issue": f"{role} is missing annual rate(s) for contract year(s) {', '.join(map(str, missing))}",
                        }
                    )
    return pd.DataFrame(issues, columns=["Row", "Field", "Issue"])


def validation_warnings(frame: pd.DataFrame) -> pd.DataFrame:
    """Return accepted-but-unusual inputs that should remain visible to the reviewer."""
    warnings = []
    confirmed_values = {"yes", "y", "true", "confirmed", "1"}
    for index, row in frame.reset_index(drop=True).iterrows():
        role = str(row.get("Role", "")).strip()
        quantity = pd.to_numeric(pd.Series([row.get("Quantity")]), errors="coerce").iloc[0]
        rate = pd.to_numeric(pd.Series([row.get("Monthly Rate (SGD)")]), errors="coerce").iloc[0]
        quantity_unit = str(row.get("Quantity Unit", "")).strip().casefold()
        justification = str(row.get("Officer Justification", "")).strip()
        assumption_confirmed = (
            str(row.get("Officer Assumption Confirmed", "")).strip().casefold()
            in confirmed_values
        )
        if pd.notna(rate) and float(rate) >= 15000 and justification:
            warnings.append(
                {
                    "Row": index + 1,
                    "Field": "Monthly Rate (SGD)",
                    "Review note": (
                        "High monthly rate accepted because an officer justification was supplied; "
                        "retain the justification in the review evidence."
                    ),
                }
            )
        if pd.notna(quantity) and 0 < float(quantity) < 1 and quantity_unit == "fte":
            warnings.append(
                {
                    "Row": index + 1,
                    "Field": "Quantity",
                    "Review note": (
                        f"Fractional deployment of {float(quantity):g} FTE accepted exactly as supplied."
                    ),
                }
            )
        no_benchmark_confirmed = any(
            phrase in justification.casefold()
            for phrase in ("no benchmark", "no comparable benchmark", "no comparable rate")
        )
        if role and map_role(role) is None and assumption_confirmed and no_benchmark_confirmed:
            warnings.append(
                {
                    "Row": index + 1,
                    "Field": "Role",
                    "Review note": (
                        "Unmatched role accepted with the officer's confirmed assumption. Keep it "
                        "separate for manual review; no benchmark will be invented."
                    ),
                }
            )
    return pd.DataFrame(warnings, columns=["Row", "Field", "Review note"])


def _role_key(value: str) -> str:
    return map_role(value) or value.strip()


def role_mapping_table(
    frames: dict[str, pd.DataFrame] | list[pd.DataFrame],
    *,
    standard_roles: list[str] | None = None,
    aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Return one reviewable role match per source document and submitted title."""
    if isinstance(frames, list):
        labelled = {f"Source {index}": frame for index, frame in enumerate(frames, 1)}
    else:
        labelled = frames
    available_roles = standard_roles or TRACK3_COMPARISON_ROLES
    exact_roles = {role.casefold(): role for role in available_roles}
    approved_aliases = {key.casefold(): value for key, value in (aliases or {}).items()}
    rows = []
    for submitted_by, frame in labelled.items():
        for role in sorted({str(value).strip() for value in frame["Role"].dropna()}):
            suggestion = exact_roles.get(role.casefold()) or approved_aliases.get(role.casefold())
            if suggestion is None and standard_roles is None:
                suggestion = map_role(role)
            if suggestion and suggestion.casefold() == role.casefold():
                reason = "Title already matches the standard role list"
            elif suggestion:
                reason = f"Suggested from a recognised abbreviation or alternative title: {suggestion}"
            else:
                reason = (
                    "No verified equivalent role exists in the comparison database. Choose a "
                    "database role only when the duties are genuinely equivalent; otherwise keep "
                    "the submitted title for manual review."
                )
            rows.append(
                {
                    "Submitted by": submitted_by,
                    "Role title in submission": role,
                    "Compare as": suggestion or role,
                    "Why this is suggested": reason,
                }
            )
    return pd.DataFrame(rows)


def role_mapping_options(
    mapping: pd.DataFrame, standard_roles: list[str] | None = None
) -> list[str]:
    """Offer reviewed standard roles without forcing unmatched titles into a wrong category."""
    submitted = set(mapping.get("Role title in submission", pd.Series(dtype="string")).astype(str))
    return sorted(set(standard_roles or TRACK3_COMPARISON_ROLES) | submitted)


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
        document_years = set(int(value) for value in frame["Contract Year"])
        if document_years != expected:
            missing = sorted(expected - document_years)
            extra = sorted(document_years - expected)
            detail = []
            if missing:
                detail.append("missing year(s) " + ", ".join(map(str, missing)))
            if extra:
                detail.append("unexpected year(s) " + ", ".join(map(str, extra)))
            issues.append(
                {
                    "Document": document,
                    "Category": "Contract-period coverage",
                    "Role": "All roles",
                    "Issue": "; ".join(detail),
                }
            )
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
            benchmark = rate_benchmark(records, role, year=benchmark_year, status="both")
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
