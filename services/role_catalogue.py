"""Role choices from the active prepared taxonomy, with conservative alias identity."""

import re

from services.reference_data import active_snapshot, mapping_safe, title_mapping


def title_key(title):
    return re.sub(r"\s+", " ", title.strip()).casefold()


def identity(title):
    from services.evidence import map_role

    mapped = title_mapping(title) or (map_role(title) if active_snapshot() is None else None)
    protected = r"\b(senior|assistant|deputy|junior|principal|lead|chief|mobile|shift|shared|relief|cum)\b"
    if mapped and set(re.findall(protected, title.casefold())) != set(
        re.findall(protected, mapped.casefold())
    ):
        mapped = None
    if mapped and re.findall(r"\d+(?:\.\d+)?", title) != re.findall(r"\d+(?:\.\d+)?", mapped):
        mapped = None
    return title_key(mapped or title)


def catalogue(snapshot=None):
    source = snapshot if snapshot is not None else active_snapshot()
    if source is None:
        # Explicit demonstration context only, never a production typical list.
        from services.role_reference import role_titles

        return {"typical": [], "additional": role_titles(), "source": "Synthetic demonstration"}
    entries = source["standard_roles"]
    typical = [
        r["Role Title"] for r in entries if str(r.get("Typical manpower?", "")).strip().casefold() == "yes"
    ]
    additional = [
        r["Role Title"] for r in entries if str(r.get("Typical manpower?", "")).strip().casefold() == "no"
    ]
    unresolved = []
    # Unsafe/combined titles remain individual choices rather than being merged
    # into an overly broad standard title. Original source strings are retained.
    known = {title_key(t) for t in typical + additional}
    for mapping in source.get("mappings", []):
        title = str(mapping.get("Original Role Title") or "").strip()
        if (
            title
            and mapping.get("Source Section") in ("manpower", "cleaning", "security")
            and not mapping_safe(mapping)
            and title_key(title) not in known
        ):
            additional.append(title)
            unresolved.append(title)
            known.add(title_key(title))
    return {
        "typical": list(dict.fromkeys(typical)),
        "additional": sorted(set(additional), key=str.casefold),
        "source": "Standard Roles → Typical manpower? = Yes",
        "dataset_id": source["dataset_id"],
        "unresolved_original_titles": unresolved,
    }


def available_roles(plan):
    from services.deployment_review import officer_draft

    used = {identity(r.label) for r in officer_draft(plan).roles if r.included or r.quantity is not None}
    result = catalogue()
    typical_keys = {identity(t) for t in result["typical"]}

    def remaining(titles, excluded):
        seen, values = set(excluded), []
        for title in titles:
            key = identity(title)
            if key not in seen:
                values.append(title)
                seen.add(key)
        return values

    return {
        **result,
        "typical": remaining(result["typical"], used),
        "additional": remaining(result["additional"], used | typical_keys),
    }
