"""Headcount comparisons never treat unanswered quantities or earlier units as people."""

import math


def comparison(rows, existing=False):
    people = [r for r in rows if r.get("Quantity basis") == "headcount"]

    def subtotal(field):
        values = [r.get(field) for r in people]
        valid = [
            float(v)
            for v in values
            if v is not None and math.isfinite(float(v)) and float(v) >= 0 and float(v).is_integer()
        ]
        return int(sum(valid)), len(values) - len(valid)

    proposed, proposed_missing = subtotal("Proposed quantity / FTE")
    current, current_missing = subtotal("Current quantity / FTE") if existing is not False else (0, 0)
    return {
        "current": current,
        "proposed": proposed,
        "current_missing": current_missing,
        "proposed_missing": proposed_missing,
        "change": proposed - current
        if not (current_missing or proposed_missing or len(rows) != len(people))
        else None,
        "legacy_rows": len(rows) - len(people),
    }
