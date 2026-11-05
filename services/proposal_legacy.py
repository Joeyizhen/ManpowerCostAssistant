"""Retain unaccepted entries from the earlier proposal editor without applying them."""

import re


def rate_entries(p):
    controls = p.drafts.get("controls", {})
    consumed = set(p.drafts.get("legacy_consumed", []))
    entries = []
    for role in p.plan.roles:
        pattern = re.compile(re.escape(f"proposal_rate_{p.id}_{role.id}_") + r"(\d+)_exact$")
        found = [
            (int(match[1]), key, value)
            for key, value in controls.items()
            if (match := pattern.fullmatch(key))
        ]
        if not found:
            continue
        _, key, value = max(found)
        if key not in consumed and value != role.rate:
            entries.append(
                {
                    "key": key,
                    "role_id": role.id,
                    "Role": role.label,
                    "Recorded rate": role.rate,
                    "Saved pending rate": value,
                }
            )
    return entries


def annual_entry(p):
    key = "proposal_shared_percent_" + p.id
    controls = p.drafts.get("controls", {})
    if key not in controls or controls[key] is None or key in p.drafts.get("legacy_consumed", []):
        return None
    ids = controls.get(
        "proposal_shared_roles_" + p.id, [r.id for r in p.plan.roles if r.included and not r.pwm]
    )
    roles = [r for r in p.plan.roles if r.id in ids and r.included]
    percent = float(controls[key])
    expected = [0] + [percent / 100] * max(0, p.plan.profile.years - 1)
    if roles and all(r.escalation == expected and not r.pwm for r in roles):
        return None
    return {
        "key": key,
        "roles": [r.id for r in roles],
        "percent": percent,
        "note": controls.get("proposal_shared_note_" + p.id, ""),
    }


def pending(p):
    return bool(rate_entries(p) or annual_entry(p))


def prepare(p):
    if p.drafts.get("legacy_baselines_checked"):
        return
    controls = p.drafts.get("controls", {})
    consumed = p.drafts.setdefault("legacy_consumed", [])
    for role in p.plan.roles:
        for key, value in controls.items():
            if (
                key.startswith(f"proposal_rate_{p.id}_{role.id}_")
                and key.endswith("_exact")
                and value == role.rate
            ):
                consumed.append(key)
    entry = annual_entry(p)
    key = "proposal_shared_percent_" + p.id
    if key in controls and entry is None:
        consumed.append(key)
    p.drafts["legacy_baselines_checked"] = True


def resolve(p, records, officer, apply):
    from services.future_groups import general_proposal
    from services.workflow import apply_change

    candidate = p.model_copy(deep=True)
    entries = rate_entries(candidate)
    annual = annual_entry(candidate)
    if apply:
        for entry in entries:
            role = next(r for r in candidate.plan.roles if r.id == entry["role_id"])
            payload = role.model_dump(mode="json")
            payload.update(
                rate=entry["Saved pending rate"],
                rate_origin="Officer assumption",
                rate_reason=candidate.drafts.get("controls", {}).get(
                    entry["key"].removesuffix("_exact") + "_reason", ""
                ),
            )
            apply_change(
                candidate.plan, "role", payload, "Officer accepted a saved earlier rate edit", officer
            )
        if annual:
            candidate.plan = general_proposal(
                candidate.plan,
                records,
                annual["roles"],
                annual["percent"],
                annual["note"],
                "",
                False,
                officer,
            )
    candidate.drafts.setdefault("legacy_consumed", []).extend(
        [e["key"] for e in entries] + ([annual["key"]] if annual else [])
    )
    candidate.history.append(
        {
            "action": "Officer applied saved earlier input edits"
            if apply
            else "Officer kept recorded values instead of earlier pending input edits",
            "version": candidate.plan.version,
        }
    )
    p.__dict__.update(candidate.__dict__)
