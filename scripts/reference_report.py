"""Developer-only readiness and reproducible arithmetic examples for the active snapshot."""

import json
from collections import defaultdict
from statistics import fmean, median

from services.reference_data import active_snapshot, annual_reference, metadata, rate_reference


def report():
    snapshot = active_snapshot()
    if snapshot is None:
        return {"active": metadata(), "note": "Legacy synthetic source is active"}
    records = snapshot["records"]
    starting = rate_reference(records, "Admin Executive", quantity_unit="headcount")
    groups = defaultdict(list)
    for row in starting["records"]:
        groups[row["submission_id"]].append(row["unit_rate_monthly"])
    values = {key: median(rates) for key, rates in groups.items()}
    assert starting["average"] == fmean(values.values())
    annual = annual_reference(records, general=True)
    pair = annual["changes"][0]
    assert pair["change"] == pair["next_rate"] / pair["previous_rate"] - 1
    support = {r["record_id"]: r for r in records if r["record_id"] in pair["record_ids"]}
    previous, following = [support[rid] for rid in pair["record_ids"]]
    assert all(
        previous[key] == following[key]
        for key in ("submission_id", "property_id", "role_line_id", "rate_basis")
    )
    assert following["contract_year"] == previous["contract_year"] + 1
    return {
        "active": metadata(),
        "import": snapshot["readiness_report"],
        "starting_rate_example": {
            "role": "Admin Executive",
            "submission_medians": values,
            "average": starting["average"],
            "observed_minimum": starting["minimum"],
            "observed_maximum": starting["maximum"],
            "source_record_ids": starting["record_ids"],
            "source_references": list(dict.fromkeys(r["source"] for r in starting["records"])),
            "qualification": starting["limitations"],
        },
        "annual_pair_example": {
            **pair,
            "source_references": [support[rid]["source"] for rid in pair["record_ids"]],
            "rate_origins": [support[rid]["rate_origin"] for rid in pair["record_ids"]],
        },
        "general_annual_reference": {
            k: annual[k]
            for k in ("average", "minimum", "maximum", "sample_count", "pair_count", "method", "limitations")
        },
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
