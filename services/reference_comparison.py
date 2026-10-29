"""Historical tender view backed by the same conditional quote queries as budgeting."""

import pandas as pd

from services.reference_data import ADJUSTMENT, LIMITATIONS, active_snapshot, rate_reference, title_mapping


def compare_prepared(
    tenderers,
    historical,
    *,
    facility_type="Any",
    service_category="Any",
    gfa_band="Any",
    pricing_year_from=None,
    role_mappings=None,
    project=None,
    **_,
):
    from services.agent2.track3 import Track3InputError, validation_issues, variance_severity
    from services.agent2.track4 import Track4Result

    snapshot = active_snapshot()
    if snapshot is None:
        raise Track3InputError("The prepared reference snapshot is not active")
    version = snapshot["dataset_id"]
    if set(historical["Dataset Version"].dropna()) != {version}:
        raise Track3InputError(
            "The reference dataset changed. Reload the active references before recalculating."
        )
    if not tenderers or any(frame.empty for frame in tenderers.values()):
        raise Track3InputError("Add at least one valid manpower line for each tenderer")
    rows, questions, adjustments = [], [], []
    context_supported = (
        all(
            x in (None, "", "Any", "Unknown", "Not specified")
            for x in (facility_type, service_category, gfa_band)
        )
        and pricing_year_from is None
    )
    for tenderer, raw in tenderers.items():
        if not validation_issues(raw).empty:
            raise Track3InputError(f"Resolve the missing or invalid values in {tenderer} before comparison")
        frame = raw.copy()
        frame["Standard Role"] = [
            (role_mappings or {}).get((tenderer, str(role)), title_mapping(str(role)) or str(role))
            for role in frame["Role"]
        ]
        for role, group in frame.groupby("Standard Role"):
            if group["Contract Year"].duplicated().any():
                raise Track3InputError(
                    f"{tenderer}: {role} has repeated role/year lines. Keep allocations distinct and review their mapping before comparison."
                )
            first = group.sort_values("Contract Year").iloc[0]
            units = set(group["Quantity Unit"].astype(str).str.casefold())
            unit = next(iter(units)) if len(units) == 1 else "incompatible"
            bm = rate_reference(snapshot["records"], role, quantity_unit=unit)
            usable = bm["available"] and unit == "headcount" and context_supported
            rate, qty = float(first["Monthly Rate (SGD)"]), float(first["Quantity"])
            cost = float((group["Quantity"] * group["Monthly Rate (SGD)"] * 12).sum())
            median = bm["median"] if usable else None
            low, high = (bm["p25"], bm["p75"]) if usable else (None, None)
            diff = rate - median if median is not None else None
            pct = diff / median if median else None
            quantity_months = float(group["Quantity"].sum() * 12)
            expected = median * quantity_months if median is not None else None
            impact = cost - expected if expected is not None else None
            priority = variance_severity(impact, pct) if usable else "Manual review"
            position = (
                (
                    "Above conditional source range"
                    if rate > high
                    else "Below conditional source range"
                    if rate < low
                    else "Within conditional source range"
                )
                if usable
                else "Insufficient comparable data"
            )
            reason = (
                "Contract-year 1 source quotes; equal submission weights. No calendar adjustment. Source count/allocation alignment remains conditional."
                if usable
                else "No compatible supported cohort. FTE conversion, missing scope metadata and synthetic dates are not filled or inferred."
            )
            evidence = (
                "; ".join(dict.fromkeys(r["source"] for r in bm["records"]))
                if usable
                else "No supported comparable reference"
            )
            question = (
                f"Confirm the monthly pricing denominator and source-scope alignment for {role}."
                if usable
                else f"Provide a comparable source quotation or retain an explicit assumption for {role}; no benchmark is available."
            )
            row = {
                "Tenderer": tenderer,
                "Submitted Role": ", ".join(group["Role"].astype(str).unique()),
                "Standard Role": role,
                "Standard Role Used for Comparison": role,
                "Contract Year or Period": "Full contract",
                "Tendered Quantity": qty,
                "Quantity Unit": unit,
                "Tendered Monthly Rate (SGD)": rate,
                "Tendered Full-Contract Cost (SGD)": cost,
                "Historical Original Median (SGD)": median,
                "Historical Median Monthly Rate (SGD)": median,
                "Adjusted Historical Benchmark (SGD)": median,
                "Adjusted Historical Range Low (SGD)": low,
                "Adjusted Historical Range High (SGD)": high,
                "Variance to Adjusted Benchmark (SGD)": diff,
                "Variance to Adjusted Benchmark (%)": pct,
                "Estimated Full-Contract Difference (SGD)": impact,
                "Comparable Past Records": bm["sample_count"] if usable else 0,
                "Historical Years Used": "Contract year 1; calendar year unknown",
                "Historical Position": position,
                "Priority": priority,
                "Applicable Statutory Wage Floor (SGD)": None,
                "Statutory Wage Check": "PWM references are separate; no salary component or eligibility inferred",
                "Statutory Source URL": None,
                "What the Comparison Means": reason,
                "Possible Explanation": "Price, scope and allocation differences require officer interpretation",
                "What Remains Uncertain": LIMITATIONS,
                "Historical Record IDs": ", ".join(bm["record_ids"]) if usable else "",
                "How Records Were Selected": bm["method"],
                "Why These Historical Records Were Selected": bm["method"],
                "Comparison Limitations": LIMITATIONS,
                "Supporting Evidence": evidence,
                "Source Reference": evidence,
                "Similar Historical Rates Found": bm["sample_count"] if usable else 0,
                "Historical Comparison": position,
                "Difference from Historical Median (SGD)": diff,
                "Difference from Historical Median (%)": pct,
                "Typical Historical Range – Low (SGD)": low,
                "Typical Historical Range – High (SGD)": high,
                "Finding Category": "Conditional source quote comparison"
                if usable
                else "Insufficient comparable evidence",
                "Suggested Clarification Question": question,
                "Review Status": "Pending Review",
                "Officer Notes": "",
                "Dataset Version": version,
                "Adjustment Method": ADJUSTMENT,
                "Reference Expected Contract Cost (SGD)": expected,
                "Reference Contract Low (SGD)": low * quantity_months if usable else None,
                "Reference Contract High (SGD)": high * quantity_months if usable else None,
            }
            rows.append(row)
            if priority != "Low":
                questions.append(
                    {
                        "Tenderer": tenderer,
                        "Priority": priority,
                        "Related Role": role,
                        "Reason for Question": reason,
                        "Clarification Question": question,
                        "Supporting Evidence": evidence,
                        "Source Reference": evidence,
                        "Include in Report": True,
                    }
                )
            if usable:
                adjustments.extend(
                    {
                        "Tenderer": tenderer,
                        "Standard Role": role,
                        "Historical Record ID": r["record_id"],
                        "Submission ID": r["submission_id"],
                        "Original Monthly Rate (SGD)": r["unit_rate_monthly"],
                        "Adjusted Monthly Rate (SGD)": r["unit_rate_monthly"],
                        "Adjustment Factor": 1,
                        "Adjustment Method": ADJUSTMENT,
                        "Dataset Version": version,
                        "Source": r["source"],
                    }
                    for r in bm["records"]
                )
    comparisons = pd.DataFrame(rows)
    findings = comparisons.copy()
    findings.insert(0, "S/N", range(1, len(findings) + 1))
    q = pd.DataFrame(
        questions,
        columns=[
            "Tenderer",
            "Priority",
            "Related Role",
            "Reason for Question",
            "Clarification Question",
            "Supporting Evidence",
            "Source Reference",
            "Include in Report",
        ],
    )
    q.insert(0, "S/N", range(1, len(q) + 1))
    totals = []
    for tenderer, group in comparisons.groupby("Tenderer"):
        complete = group["Reference Expected Contract Cost (SGD)"].notna().all()
        submitted = float(group["Tendered Full-Contract Cost (SGD)"].sum())
        expected = float(group["Reference Expected Contract Cost (SGD)"].sum()) if complete else None
        low = float(group["Reference Contract Low (SGD)"].sum()) if complete else None
        high = float(group["Reference Contract High (SGD)"].sum()) if complete else None
        variance = submitted - expected if expected is not None else None
        totals.append(
            {
                "Tenderer": tenderer,
                "Submitted Total Cost (SGD)": submitted,
                "Adjusted Historical Expected Total (SGD)": expected,
                "Adjusted Typical Range Low (SGD)": low,
                "Adjusted Typical Range High (SGD)": high,
                "Total Variance (SGD)": variance,
                "Total Variance (%)": variance / expected if expected else None,
                "Overall Interpretation": (
                    "Above conditional source range"
                    if submitted > high
                    else "Below conditional source range"
                    if submitted < low
                    else "Within conditional source range"
                )
                if complete
                else "Insufficient comparable data",
                "Main Cost Drivers": ", ".join(group["Standard Role"]),
                "Important Limitation": "Conditional flat source-quote comparison using submitted yearly quantities; not a future-price forecast. "
                + LIMITATIONS,
                "Dataset Version": version,
                "Adjustment Method": ADJUSTMENT,
            }
        )
    overall = pd.DataFrame(totals)
    policy = pd.DataFrame(
        [
            {
                "Evidence Type": "Separate retained policy catalogue",
                "Policy or Economic Factor": "PWM salary components",
                "What Changed": "No policy amount or wage index is added by this historical comparison.",
                "Effective Date": "Use the recorded applicable schedule",
                "Roles or Sectors Affected": "Only confirmed eligible workers",
                "Likely Cost Implication": "Confirm salary basis, effective dates, covered workers and separate employer costs in the budgeting workflow.",
                "Source Organisation": "Retained PWM reference catalogue",
                "Page Title": "Existing policy references retained unchanged",
                "Direct URL": "https://www.mom.gov.sg/employment-practices/progressive-wage-model",
                "Date Accessed": "Not verified by this comparison; existing catalogue dates retained",
            }
        ]
    )
    narrative = pd.DataFrame(
        [
            {
                "Status": "Deterministic fallback",
                "Narrative": " ".join(f"{r['Tenderer']}: {r['Overall Interpretation']}." for r in totals),
                "Evidence Basis": "Prepared source quotations, version " + version + "; " + ADJUSTMENT,
            }
        ]
    )
    limitations = pd.DataFrame(
        {
            "Limitation": [
                LIMITATIONS,
                "No hard-coded wage index or synthetic calendar normalisation.",
                "A full reference total is unavailable if any role lacks comparable evidence.",
                "Results support human review and do not recommend an award.",
            ]
        }
    )
    return Track4Result(
        overall.copy(),
        comparisons,
        findings,
        q,
        overall,
        pd.DataFrame(adjustments),
        policy,
        narrative,
        limitations,
    )
