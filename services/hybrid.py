"""Officer input tables and editable rate defaults; no model calls or approvals."""

import csv
import io
import math
import re
from uuid import uuid4

from services.evidence import map_role, rate_benchmark
from services.journey import update_notes, working_draft
from services.models import Profile, Role
from services.workflow import apply_change, invalidate

COMMON_ROLES = [
    "Facility Manager",
    "Admin Executive",
    "Technician",
    "Property Executive",
    "Fire Safety Manager",
    "Workplace Safety and Health Officer",
    "M&E Engineer",
    "BMS Engineer",
]
# Wire locations remain compatible with saved six-screen projects. Old review
# location 2 aliases Deployment; no financial facts or confirmations migrate.
STEP_ROUTES = (0, 1, 3, 4, 5)
STEP_LABELS = ["Project", "Deployment", "Deployment", "Starting rates", "Annual changes", "Budget"]


def canonical_step(step):
    return 1 if step == 2 else step


def step_number(step):
    return STEP_ROUTES.index(canonical_step(step)) + 1


def cell_text(value):
    return "" if value is None or (isinstance(value, float) and math.isnan(value)) else str(value).strip()


def table_rows(plan, include_excluded=False):
    return [
        {
            "id": r.id,
            "Role title": r.label,
            "Quantity / FTE": r.quantity,
            "Duties / coverage notes": r.duties_notes,
            "Deployment": r.deployment,
        }
        for r in working_draft(plan).roles
        if r.included or include_excluded
    ]


def comparison_rows(plan, common=True, include_pending=True):
    source = plan
    if not include_pending:
        source = plan.model_copy(deep=True)
        source.pending = []
    roles = list(working_draft(source).roles)
    if common:
        existing = {r.label.casefold() for r in roles}
        # Retain a saved title/alias instead of adding an equivalent second FM row.
        for index, title in enumerate(COMMON_ROLES):
            aliases = {title.casefold()}
            if index == 0:
                aliases |= {"facilities manager", "facilities manager (fm)"}
            if not existing & aliases:
                roles.append(Role(id=f"common-{index}", label=title))
    order = {label.casefold(): i for i, label in enumerate(COMMON_ROLES)}
    roles.sort(key=lambda r: order.get(r.label.casefold(), 100))
    return [
        {
            "id": r.id,
            "Role title": r.label,
            "Current quantity / FTE": r.current_quantity
            if plan.current_deployment_status == "known"
            else None,
            "Proposed quantity / FTE": r.quantity if r.included or r.quantity == 0 else 0,
            "Change": quantity_difference(r.current_quantity, r.quantity if r.included else 0)
            if plan.current_deployment_status == "known"
            else None,
            "Quantity basis": r.quantity_unit,
            "Duties / deployment notes": r.duties_notes,
            "Deployment": r.deployment,
        }
        for r in roles
        if not (not common and not r.included and r.quantity is None)
    ]


def quantity_difference(current, proposed):
    if (
        current is None
        or proposed is None
        or not math.isfinite(float(current))
        or not math.isfinite(float(proposed))
    ):
        return None
    return float(proposed) - float(current)


def save_project_inputs(
    plan, brief, year, base, option, kind, name=None, start=None, clear_start=False, start_month=...
):
    candidate = plan.model_copy(deep=True)
    draft = working_draft(candidate)
    payload = draft.profile.model_dump(mode="json")
    payload.update(description=brief.strip(), start_year=year, base_years=base, option_years=option)
    if start_month is not ...:
        payload["start_month"] = start_month
    if name is not None:
        payload["name"] = name.strip() or "Untitled project"
    if clear_start:
        payload["start"] = None
    elif start is not None:
        payload["start"] = start
    elif draft.profile.start and draft.profile.start.year != year:
        payload["start"] = None
    profile = Profile.model_validate(payload)
    if profile != draft.profile or kind != candidate.contract_kind:
        if candidate.confirmations:
            invalidate(
                candidate,
                "profile",
                "Officer revised project inputs; review dependent decisions",
                "Officer input",
            )
        candidate.contract_kind = kind
        if kind == "new site / service":
            candidate.current_deployment_status = "no existing deployment"
        elif kind == "existing contract":
            candidate.current_deployment_status = "known"
        update_notes(
            candidate,
            profile=profile.model_dump(mode="json"),
            roles=[r.model_dump(mode="json") for r in draft.roles],
            responsibilities=[d.model_dump() for d in draft.responsibilities],
        )
    plan.__dict__.update(candidate.__dict__)


def validate_comparison(rows):
    unanswered = [
        r["Role title"]
        for r in rows
        if r.get("Proposed quantity / FTE") is None
        or (isinstance(r.get("Proposed quantity / FTE"), float) and math.isnan(r["Proposed quantity / FTE"]))
    ]
    if unanswered:
        raise ValueError(
            "Enter proposed quantities or explicitly mark unused roles as zero: " + ", ".join(unanswered)
        )
    included = [r for r in rows if r["Proposed quantity / FTE"] > 0]
    if not included:
        raise ValueError("Include at least one role with a positive proposed quantity.")
    for row in included:
        unit, value = row.get("Quantity basis", "unspecified"), row["Proposed quantity / FTE"]
        if unit not in ("headcount", "FTE"):
            raise ValueError(
                f"{row['Role title']}: select headcount or FTE. Posts require an explicit staffing conversion first."
            )
        if unit == "headcount" and not float(value).is_integer():
            raise ValueError(f"{row['Role title']}: enter a whole number of people for headcount.")


def parse_manpower_list(text):
    """Read explicit quantities; never split combined titles or guess missing values."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(role|role title)[,\t]", line, flags=re.I):
            continue
        separator = "\t" if "\t" in line else ","
        values = next(csv.reader(io.StringIO(line), delimiter=separator))
        if len(values) >= 2:
            label, quantity, *notes = values
            note = ", ".join(notes).strip()
        else:
            match = re.fullmatch(r"(.+?)\s*(?:[:=]|\s+[xÃ—â€“-])\s*(\d+(?:\.\d+)?)\s*", line)
            if not match:
                raise ValueError(f"Use Role title, quantity for: {line[:100]}")
            label, quantity = match.groups()
            note = ""
        quantity = float(quantity.strip())
        if not label.strip() or not math.isfinite(quantity) or not 0 < quantity <= 10000:
            raise ValueError("Each pasted row needs a role title and a positive quantity / FTE")
        rows.append(
            {
                "id": f"role-{uuid4().hex[:8]}",
                "Role title": label.strip(),
                "Quantity / FTE": quantity,
                "Duties / coverage notes": note,
                "Deployment": "unspecified",
            }
        )
    if not rows:
        raise ValueError("Paste at least one role and quantity")
    return rows


def save_input_table(
    plan, brief, start_year, base_years, option_years, rows, support="", current_status=None
):
    candidate = plan.model_copy(deep=True)
    candidate.pending = []  # An officer edit cannot implicitly accept assistant suggestions.
    draft = working_draft(candidate)
    status = current_status or candidate.current_deployment_status
    profile = draft.profile.model_dump(mode="json")
    profile.update(
        description=brief.strip(), start_year=start_year, base_years=base_years, option_years=option_years
    )
    if profile["start"] and draft.profile.start.year != start_year:
        profile["start"] = None
    existing = {r.id: r for r in draft.roles}
    roles, retained = [], set()
    for row in rows:
        label = cell_text(row.get("Role title"))
        quantity = row.get("Proposed quantity / FTE", row.get("Quantity / FTE"))
        if not label and (quantity is None or (isinstance(quantity, float) and math.isnan(quantity))):
            continue
        if not label:
            raise ValueError("A quantity needs a role title")
        if quantity is not None and isinstance(quantity, float) and math.isnan(quantity):
            quantity = None
        old = existing.get(row.get("id"))
        role = (
            old.model_copy(deep=True)
            if old
            else Role(id=row.get("id") or f"role-{uuid4().hex[:8]}", label=label)
        )
        if old and old.label != label:
            role.mapped_role = map_role(label)
            role.mapping_reason = "Supported exact title/alias for review" if role.mapped_role else ""
            role.rate, role.rate_reason, role.escalation = None, "", []
        elif not old:
            role.mapped_role = map_role(label)
            role.mapping_reason = "Supported exact title/alias for review" if role.mapped_role else ""
        if quantity != role.quantity:
            role.coverage = None
            role.quantity_basis = "officer scenario"
        role.label, role.quantity = label, quantity
        if not old or old.label != label:
            from services.cost_routing import resolve_route

            route = resolve_route(role)
            if route["route"] != "demonstration":
                role.future_routing = route
        if "Current quantity / FTE" in row and status == "known":
            raw_current = row.get("Current quantity / FTE")
            role.current_quantity = None if not cell_text(raw_current) else float(raw_current)
        if "Quantity basis" in row:
            role.quantity_unit = cell_text(row.get("Quantity basis")) or "unspecified"
        role.duties_notes = cell_text(
            row.get("Duties / deployment notes", row.get("Duties / coverage notes"))
        )
        role.deployment = cell_text(row.get("Deployment")) or "unspecified"
        role.quantity_reason = (
            role.quantity_reason
            or "Officer-provided quantity in manpower table; workload allowance, not a staffing prediction"
        )
        role.included, role.exclusion_reason = (
            quantity != 0,
            "Officer selected zero; not included in the proposed plan" if quantity == 0 else "",
        )
        retained.add(role.id)
        roles.append(role.model_dump(mode="json"))
    for r in draft.roles:
        if r.id not in retained:
            excluded = r.model_copy(deep=True)
            excluded.included, excluded.exclusion_reason = (
                False,
                "Officer removed this row from the input table",
            )
            roles.append(excluded.model_dump(mode="json"))
    # Only actual edits clear decisions; navigation/saving an unchanged table does not.
    changed = (
        profile != draft.profile.model_dump(mode="json")
        or {r["id"]: r for r in roles} != {r.id: r.model_dump(mode="json") for r in draft.roles}
        or support.strip() != candidate.input_support
        or status != candidate.current_deployment_status
    )
    if changed and candidate.confirmations:
        gate = "profile" if profile != draft.profile.model_dump(mode="json") else "quantities"
        invalidate(
            candidate,
            gate,
            "Officer revised manpower comparison or support; renew dependent decisions",
            "Officer input",
        )
    candidate.input_support = support.strip()
    candidate.current_deployment_status = status
    if changed:
        candidate.officer_manpower_input = [
            {
                k: r[k]
                for k in [
                    "id",
                    "label",
                    "quantity",
                    "current_quantity",
                    "quantity_unit",
                    "included",
                    "duties_notes",
                    "deployment",
                ]
            }
            for r in roles
        ]
        candidate.manpower_review_requested = False
        update_notes(
            candidate,
            profile=profile,
            roles=roles,
            responsibilities=[d.model_dump() for d in draft.responsibilities],
        )
    plan.__dict__.update(candidate.__dict__)


def initialise_rates(plan, records, year, update_existing=False):
    """Editable defaults are unconfirmed; the officer confirms the whole rates decision."""
    from services.reference_data import prepared

    if prepared(records):
        for r in list(plan.roles):
            if not r.included or r.rate is not None or plan.basis_drafts.get("rate_unanswered", {}).get(r.id):
                continue  # Activating references never changes a recorded allowance or its metadata.
            from services.pricing import reference

            bm = reference(plan, r, records)
            if bm.get("recommendation_supported", bm["available"]):
                payload = r.model_dump(mode="json")
                payload.update(
                    rate=round(bm["average"], 2),
                    benchmark_year=None,
                    rate_origin="Prepared reference selection",
                    rate_reason=f"Conditional source-quote average across {bm['sample_count']} submissions; contract-year 1. Calendar pricing year and operational unit alignment remain unverified. Officer confirmation required.",
                )
                apply_change(
                    plan,
                    "role",
                    payload,
                    "Prepared conditional rate comparison; no approval",
                    "System starting point",
                )
        return
    for r in list(plan.roles):
        if (
            not r.included
            or (r.rate is not None and not update_existing)
            or plan.basis_drafts.get("rate_unanswered", {}).get(r.id)
        ):
            continue
        payload = r.model_dump(mode="json")
        payload["benchmark_year"] = year
        bm = rate_benchmark(records, r.mapped_role, year, r.benchmark_status, r.benchmark_scope)
        if bm["available"] and r.rate is None:
            payload.update(
                rate=round(bm["average"], 2),
                rate_origin="Synthetic benchmark selection",
                rate_reason=f"Editable arithmetic-average starting point from {bm['sample_count']} synthetic schedules priced in {year}; inclusive monthly per head. Awaiting rate confirmation.",
            )
        if payload != r.model_dump(mode="json"):
            apply_change(
                plan,
                "role",
                payload,
                "Prepared editable rate references; no rate approval",
                "System starting point",
            )
