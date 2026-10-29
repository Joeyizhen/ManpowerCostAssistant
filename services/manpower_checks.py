"""Narrow checks of explicit numerical claims; no inferred staffing requirements."""

import re

LOCAL_ACTOR = "Local plan user (name not collected)"


def stated_addition(text):
    """Check an officer's explicit per-location arithmetic, not an inferred staffing rule."""
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    def numeric(match):
        return str(words[match.group()])

    text = re.sub(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b", numeric, text.casefold())
    if re.search(r"\b(?:not|if|might|may|could|consider)\b", text):
        return None
    ratio = re.search(
        r"(\d+)\s+additional\s+(?:buildings|locations|sites)\b.{0,70}?require\s+(\d+)\s+(?:dedicated\s+)?(?:officers|workers|staff|people|cleaners|technicians)\s+each\b",
        text,
    )
    if ratio:
        return int(ratio[1]) * int(ratio[2])
    decrease = re.search(
        r"(?:reduce\s+by|decrease\s+by|remove)\s+(\d+)\s+(?:pax|officers|workers|staff|people|cleaners|technicians)\b",
        text,
    )
    if decrease:
        return -int(decrease[1])
    direct = re.search(
        r"(?:additional|increase\s+by|add)\s+(\d+)\s+(?:pax|officers|workers|staff|people|cleaners|technicians)\b",
        text,
    )
    return int(direct[1]) if direct else None


def shared_basis_mismatches(plan):
    from services.decision_basis import signature

    rows = []
    for index, basis in enumerate(plan.decision_bases):
        if basis.kind != "quantity":
            continue
        roles = [r for r in plan.roles if r.id in basis.role_ids]
        if not roles or any(basis.signatures.get(r.id) != signature(plan, r, "quantity") for r in roles):
            continue
        if len({r.quantity_unit for r in roles}) > 1:
            continue  # Headcount and FTE are separate measures, never an additive total.
        claimed = stated_addition(basis.explanation)
        if claimed is None or any(r.quantity is None for r in roles):
            continue
        if plan.contract_kind != "new site / service" and any(r.current_quantity is None for r in roles):
            continue
        current = 0 if plan.contract_kind == "new site / service" else sum(r.current_quantity for r in roles)
        proposed = sum(r.quantity for r in roles)
        if abs(proposed - current - claimed) > 1e-8:
            rows.append(
                {
                    "id": f"shared_basis_{index}",
                    "Role": "; ".join(r.label for r in roles),
                    "Current": current,
                    "Proposed": proposed,
                    "Check": f"Shared basis implies +{claimed:g}; selected figures show {proposed - current:+g}.",
                    "Remarks": basis.explanation,
                }
            )
    return rows


def quantity_discrepancy(role, existing=True):
    if role.quantity is None:
        return ""
    note = role.duties_notes.casefold()
    # Negated/conditional claims and multiple numeric changes need contextual human review.
    if re.search(r"\b(not|no|if|might|may|could|consider)\b", note):
        return ""
    unit = r"\s*(?:pax|people|persons?|staff|headcount|fte)\b"
    additions = re.findall(
        r"(?:additional|add(?:ing)?|increase(?:d)?(?:\s+by)?|\+)\s*(\d+(?:\.\d+)?)" + unit, note
    )
    reductions = re.findall(
        r"(?:reduce(?:d)?\s+by|decrease(?:d)?\s+by|remove)\s*(\d+(?:\.\d+)?)" + unit, note
    )
    claims = {float(n) for n in additions} | {-float(n) for n in reductions}
    if existing and role.current_quantity is not None and len(claims) == 1:
        claim = claims.pop()
        actual = role.quantity - role.current_quantity
        if abs(claim - actual) > 1e-8:
            return f"Remarks say {claim:+g}; figures show {actual:+g}."
    totals = {
        float(n) for n in re.findall(r"(?:proposed|propose|total(?:\s+of)?)\s+(\d+(?:\.\d+)?)" + unit, note)
    }
    if len(totals) == 1 and abs(totals.pop() - role.quantity) > 1e-8:
        return (
            "The total stated in the remarks differs from the proposed figure. Clarify the remarks or figure."
        )
    return ""


def rate_display_bounds(selected, benchmark):
    """Frame observed data and any officer override, rather than an arbitrary 0–10k scale."""
    if not benchmark["available"]:
        return None
    points = [benchmark["minimum"], benchmark["maximum"]]
    if selected is not None:
        points.append(selected)
    low, high = min(points), max(points)
    padding = max((high - low) * 0.15, high * 0.03, 1)
    return max(0.0, low - padding), high + padding
