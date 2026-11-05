"""Authored demo allowances, explicitly separate from observed reference evidence."""

# SGD inclusive monthly charges per person. These are editable fictional planning
# assumptions requested for the demo, never market observations or salary minima.
BANDS = {
    "facilities manager": (6500, 9500),
    "facility manager": (6500, 9500),
    "senior facilities manager": (8500, 11500),
    "assistant facilities manager": (5000, 7000),
    "admin executive": (2800, 4200),
    "technician": (3000, 4800),
    "property executive": (3500, 5500),
    "senior property executive": (4500, 6500),
    "fire safety manager": (4500, 6500),
    "workplace safety and health officer": (4500, 6500),
    "m&e engineer": (5000, 8000),
    "bms engineer": (4500, 6500),
    "audio visual technician": (3000, 5000),
    "events manager": (4000, 6000),
    "account director": (9500, 14500),
    "cleaner": (2800, 4000),
    "cleaning supervisor": (4000, 5600),
    "security officer": (3000, 4200),
    "senior security officer": (3300, 4700),
    "security supervisor": (4200, 5800),
    "lift technician": (3500, 5500),
    "landscape worker": (2500, 3900),
}


def planning_range(role):
    label = " ".join(role.label.casefold().split())
    low, high = BANDS.get(label, (3500, 6500))
    return {
        "minimum": low,
        "average": (low + high) / 2,
        "maximum": high,
        "origin": "Illustrative planning range v1; not database or market evidence",
        "generic": label not in BANDS,
    }


def planning_reason(value):
    return (
        f"Officer planning allowance of SGD {value:,.2f} per person per month using an "
        "illustrative demonstration range; no market-rate evidence or supplier quotation is claimed."
    )


def seed_missing_allowances(plan, records, officer):
    from services.pricing import reference
    from services.workflow import apply_change

    if plan.pending or plan.working_notes:
        return
    order = {r.id: i for i, r in enumerate(plan.roles)}
    for role in list(plan.roles):
        if not role.included or role.quantity_unit != "headcount":
            continue
        bm = reference(plan, role, records)
        if bm.get("recommendation_supported"):
            continue
        band = planning_range(role)
        plan.basis_drafts.setdefault("illustrative_rate_bands", {})[role.id] = band
        if role.rate is not None or plan.basis_drafts.get("rate_unanswered", {}).get(role.id):
            continue
        payload = role.model_dump(mode="json")
        payload.update(
            rate=band["average"],
            rate_reason=planning_reason(band["average"]),
            rate_origin="Officer assumption",
        )
        apply_change(plan, "role", payload, "Populated an illustrative planning average for review", officer)
    plan.roles.sort(key=lambda r: order[r.id])
