"""Track 2 management summary and Excel evidence, using the shared budget results."""

import html

from services.proposals import assessment, comparison


def comparison_rows(p, records):
    c = comparison(p, records)
    old = {r.id: r for r in p.original.roles} if p.original else {}
    old_costs, new_costs = {}, {}
    for name, target in (("original", old_costs), ("reviewed", new_costs)):
        if c[name]:
            for row in c[name]["rows"]:
                target[row["role_id"]] = target.get(row["role_id"], 0) + row["annual_cost"]
    rows = []
    for role in p.plan.roles:
        prior = old.get(role.id)
        changes = [
            label
            for label, field in (
                ("Role/seniority", "label"),
                ("Quantity", "quantity"),
                ("Unit", "quantity_unit"),
                ("Starting rate", "rate"),
                ("Annual increase", "escalation"),
                ("PWM", "pwm"),
                ("Experience", "experience"),
            )
            if prior and getattr(prior, field) != getattr(role, field)
        ]
        if p.original and (p.original.profile.base_years, p.original.profile.option_years) != (
            p.plan.profile.base_years,
            p.plan.profile.option_years,
        ):
            changes.append("Contract term")
        if p.original and p.original.profile.costing_start != p.plan.profile.costing_start:
            changes.append("Contract timing")
        old_cost = old_costs.get(role.id, 0) if c["original"] else None
        new_cost = new_costs.get(role.id, 0) if c["reviewed"] else None
        rows.append(
            {
                "Role": role.label,
                "Original quantity": prior.quantity if prior else None,
                "Reviewed quantity": role.quantity,
                "Original unit": prior.quantity_unit if prior else None,
                "Reviewed unit": role.quantity_unit,
                "Original rate": prior.rate if prior else None,
                "Reviewed rate": role.rate,
                "Original yearly increases (%)": ", ".join(f"{v * 100:g}" for v in prior.escalation)
                if prior and prior.escalation
                else "Not supplied or awaiting interpretation",
                "Reviewed yearly increases (%)": ", ".join(f"{v * 100:g}" for v in role.escalation)
                if role.escalation
                else "Awaiting interpretation",
                "Original contract cost": old_cost,
                "Reviewed contract cost": new_cost,
                "Cost difference (SGD)": round(new_cost - old_cost, 2)
                if old_cost is not None and new_cost is not None
                else None,
                "Change drivers": "; ".join(changes) if prior else "Added role",
                "Original annual-change method": next(
                    (
                        r.get("Proposed method")
                        or ("Supplied yearly prices" if r.get("Yearly rates") else "General annual increase")
                        for r in p.original_rows
                        if r["id"] == role.id
                    ),
                    "Not supplied",
                ),
                "Accepted annual-change method": "PWM"
                if role.pwm
                else "Supplied yearly prices"
                if role.escalation_mode == "quoted schedule"
                else "General annual increase"
                if role.escalation
                else "Unanswered",
                "Reason": p.drafts.get("method_decisions", {})
                .get(role.id, {})
                .get("reason", role.escalation_reason),
            }
        )
    return rows


def workbook(p, records):
    from services.export import export_excel

    return export_excel(
        p.plan,
        records + p.quote_records,
        extra_sheets={
            "Original proposal": [
                {
                    key: row.get(key)
                    for key in (
                        "Role",
                        "Quantity",
                        "Unit",
                        "Monthly rate",
                        "Proposed method",
                        "Annual increase (%)",
                        "Supplied assumptions",
                        "Remarks",
                        "Source location",
                    )
                }
                for row in p.original_rows
            ],
            "Reviewed proposal": [
                {
                    "Role": r.label,
                    "Quantity": r.quantity,
                    "Unit": r.quantity_unit,
                    "Monthly rate": r.rate,
                    "Yearly increases": r.escalation,
                    "PWM": r.pwm.model_dump(mode="json") if r.pwm else None,
                    "Future basis": r.escalation_reason,
                }
                for r in p.plan.roles
            ],
            "Changes from original": comparison_rows(p, records),
            "Source locations": [
                {
                    "Role": r["Role"],
                    "Source location": r.get("Source location"),
                    "Original supplied assumptions": r.get("Supplied assumptions"),
                }
                for r in p.original_rows
            ],
        },
    )


def management_report(p, records):
    c, state = comparison(p, records), assessment(p, records)

    def esc(value):
        return html.escape(str(value if value is not None else "Unavailable"))

    def table(rows):
        if not rows:
            return "<p>No entries.</p>"
        keys = list(rows[0])
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{esc(k)}</th>" for k in keys)
            + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{esc(row.get(k))}</td>" for k in keys) + "</tr>" for row in rows)
            + "</tbody></table>"
        )

    from services.final_review import qualification_summary

    annual_rows = []
    old_years = c["original"]["annual_totals"] if c["original"] else []
    new_years = c["reviewed"]["annual_totals"] if c["reviewed"] else []
    for index in range(max(len(old_years), len(new_years))):
        annual_rows.append(
            {
                "Contract year": index + 1,
                "Original annual cost": old_years[index] if index < len(old_years) else None,
                "Reviewed annual cost": new_years[index] if index < len(new_years) else None,
            }
        )
    qualifications = "".join(
        "<p>" + esc(text) + "</p>" for text in qualification_summary(p.plan, state["findings"])
    )
    new = c["reviewed"]["contract_total"] if c["reviewed"] else None
    old = c["original"]["contract_total"] if c["original"] else None
    return (
        "<!doctype html><html><meta charset='utf-8'><title>Manpower proposal review</title><style>body{font:15px Arial;max-width:1100px;margin:40px auto;color:#172b42}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:8px;border:1px solid #ccd6df;text-align:left}h1,h2{color:#147d74}@media print{body{margin:1cm}}</style>"
        + f"<h1>{esc(p.name)}</h1><p>{'Confirmed' if 'final' in p.plan.confirmations else 'Draft - not approved'} | Version {p.plan.version}</p><h2>Manpower EPV</h2>"
        + table(
            [
                {
                    "Original supplied": p.original_claimed_total,
                    "Original recalculated": old,
                    "Reviewed": new,
                    "Difference": c["difference"],
                    "Difference (%)": c["percent"],
                }
            ]
        )
        + "<h2>Project requirements</h2><p>"
        + esc(p.plan.profile.description)
        + "</p><h2>Original and reviewed plan</h2>"
        + table(comparison_rows(p, records))
        + "<h2>Annual costs</h2>"
        + table(annual_rows)
        + "<h2>Material findings and officer decisions</h2>"
        + table(
            [
                {
                    "Finding": f.message,
                    "Consequence": f.impact,
                    "Decision": f.justification,
                    "Status": f.status,
                }
                for f in state["findings"]
                if f.blocking or requires_material(f)
            ]
        )
        + "<h2>Qualifications</h2>"
        + qualifications
        + "<p>Manpower charges only. Operational sufficiency, seniority and experience are not established by price comparisons alone. Reference data remains subject to its source limitations. Full sources and calculation detail are retained in the workbook.</p><p>Excluded costs: "
        + esc(p.plan.profile.exclusions or "Not separately recorded")
        + "</p></html>"
    )


def requires_material(f):
    from services.workflow import requires_decision

    return requires_decision(f) and f.code != "proposal_capability"
