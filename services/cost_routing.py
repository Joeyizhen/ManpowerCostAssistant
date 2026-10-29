"""Workbook project routes, separate from legal worker eligibility and price mappings."""

from services.reference_data import active_snapshot, stored_snapshot, title_mapping

ROUTING_VERSION = 2

# Explicit taxonomy-to-policy families. These are not title keyword guesses or eligibility findings.
POLICY_LEVELS = {
    "Cleaner": ("cleaning", None),
    "Cleaning Supervisor": ("cleaning", "Supervisor"),
    "Security Officer": ("security", "Security officer"),
    "Senior Security Officer": ("security", "Senior security officer"),
    "Security Supervisor": ("security", "Security supervisor"),
    "Lift Technician": ("lift", None),
}


def resolve_route(role, standard=None):
    source = active_snapshot()
    if source is None:
        return {"route": "demonstration", "standard_role": None, "dataset_id": "synthetic-fixture-v1"}
    title = standard or title_mapping(role.label)
    if title and standard is None:
        from services.role_catalogue import identity, title_key

        if identity(role.label) != title_key(title):
            title = None
    return route_from_source(source, title, role.label)


def route_from_source(source, title, original_title):
    row = next((r for r in source["standard_roles"] if r["Role Title"] == title), {})
    flag = str(row.get("PWM applies?") or "").strip().casefold()
    return {
        "route": {"yes": "pwm", "no": "general"}.get(flag, "unresolved"),
        "standard_role": title,
        "pwm_flag": row.get("PWM applies?"),
        "dataset_id": source["dataset_id"],
        "source_name": source["source_name"],
        "original_title": original_title,
    }


def recorded_route(role):
    saved = role.future_routing
    if not saved or saved.get("original_title", role.label) != role.label:
        return resolve_route(role)
    try:
        source = stored_snapshot(saved["dataset_id"])
    except (KeyError, FileNotFoundError):
        return {**saved, "route": "unresolved"}
    return route_from_source(source, saved.get("standard_role"), role.label)


def schedule_choices(role):
    from services.pwm import catalog

    route = recorded_route(role)
    if route["route"] != "pwm":
        return []
    sector, level = POLICY_LEVELS.get(route["standard_role"], (None, None))
    return [
        s
        for s in catalog()["schedules"]
        if sector
        and s["sector"] == sector
        and (level is None or s["job_level"].casefold() == level.casefold())
    ]


def route_errors(role, enforce_current=False):
    # Old budgets have no routing snapshot. Reading them never rewrites history.
    if not role.included or (not role.future_routing and not enforce_current):
        return []
    route = recorded_route(role)
    if route["route"] == "unresolved":
        return [f"{role.label}: resolve the Standard Role and its PWM flag before confirming annual changes."]
    if route["route"] == "general" and role.pwm:
        return [
            f"{role.label}: Standard Roles marks PWM applies? = No. Review and accept a general annual increase instead; the saved method has not been changed."
        ]
    if route["route"] == "pwm":
        if not role.pwm:
            return [f"{role.label}: complete PWM category, covered-worker and salary-component setup."]
        if role.pwm.schedule_id not in {s["id"] for s in schedule_choices(role)}:
            return [
                f"{role.label}: the selected PWM schedule does not match the mapped role/job level. Review the category."
            ]
    return []


def pin_route(role, standard=None):
    if role.future_routing and standard is None:
        if recorded_route(role)["route"] == "unresolved":
            raise ValueError(f"{role.label}: recorded routing source is unavailable; resolve it explicitly.")
        return
    route = resolve_route(role, standard)
    if route["route"] == "unresolved":
        raise ValueError(
            f"{role.label}: resolve its Standard Role/PWM flag; no default to general increase is permitted."
        )
    if route["route"] != "demonstration":
        role.future_routing = route


def assistant_route_context(roles):
    return [{"role_id": r.id, "original_title": r.label, **recorded_route(r)} for r in roles]
