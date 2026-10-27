"""Track 2 management summary and Excel evidence, using the shared budget results."""

import html
import io
import json

import xlsxwriter

from services.evidence import rate_benchmark
from services.proposals import assessment, comparison, rate_comparisons
from services.workflow import finding_history


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
                "Original contract cost": old_cost,
                "Reviewed contract cost": new_cost,
                "Cost difference (SGD)": round(new_cost - old_cost, 2)
                if old_cost is not None and new_cost is not None
                else None,
                "Change drivers": "; ".join(changes) if prior else "Added role",
            }
        )
    return rows


def workbook(p, records):
    state, c = assessment(p, records), comparison(p, records)
    if c["reviewed"] is None:
        raise ValueError("Complete the required numeric inputs before exporting a numeric review workbook")
    out = io.BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
    header = wb.add_format({"bold": True, "bg_color": "#147D74", "font_color": "white", "text_wrap": True})
    money = wb.add_format({"num_format": "#,##0.00"})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})

    def sheet(name, rows):
        ws = wb.add_worksheet(name)
        ws.set_column(0, 18, 24, wrap)
        ws.freeze_panes(3, 1)
        ws.merge_range(
            0,
            0,
            0,
            6,
            "Track 2 | " + p.name + " | " + ("Confirmed" if "final" in p.plan.confirmations else "Draft"),
            header,
        )
        if not rows:
            ws.write(2, 0, "No entries")
            return
        keys = list(rows[0])
        ws.write_row(2, 0, keys, header)
        for i, row in enumerate(rows, 3):
            for j, key in enumerate(keys):
                value = row.get(key)
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                if value is None:
                    ws.write_blank(i, j, None)
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    ws.write_number(i, j, value, money)
                else:
                    ws.write_string(i, j, str(value), wrap)
        ws.autofilter(2, 0, len(rows) + 2, len(keys) - 1)

    old = c["original"]["contract_total"] if c["original"] else None
    sheet(
        "Review summary",
        [
            {"Measure": key, "Value": value}
            for key, value in {
                "Original supplied EPV": p.original_claimed_total,
                "Original recalculated EPV": old,
                "Reviewed EPV": c["reviewed"]["contract_total"],
                "Difference from original calculation": c["difference"],
                "Difference (%)": c["percent"],
                "Assessment": "Review recommended"
                if state["unresolved"]
                else "Numeric review complete; operational sufficiency depends on recorded scope and officer assumptions",
                "Scope": "Manpower charges only",
                "Excluded costs": p.plan.profile.exclusions,
                "Reference limitation": "Reference records are demonstration data when labelled synthetic; proposal charges are private officer-supplied inputs",
                "Officer": p.plan.final_officer,
                "Confirmed at": p.plan.final_date,
            }.items()
        ],
    )
    sheet(
        "Project requirements",
        [{"Field": k, "Value": v} for k, v in p.plan.profile.model_dump(mode="json").items()],
    )
    sheet(
        "Original proposal",
        [
            {
                k: r.get(k)
                for k in (
                    "Role",
                    "Quantity",
                    "Unit",
                    "Monthly rate",
                    "Annual increase (%)",
                    "Yearly rates",
                    "Remarks",
                    "Experience",
                    "Qualifications",
                    "Source location",
                    "Supplied monthly total",
                    "Supplied annual total",
                    "Supplied contract total",
                )
            }
            for r in p.original_rows
        ],
    )
    sheet(
        "Reviewed proposal",
        [
            {
                "Role": r.label,
                "Included": r.included,
                "Quantity": r.quantity,
                "Unit": r.quantity_unit,
                "Monthly rate": r.rate,
                "Yearly increases": r.escalation,
                "Method": r.escalation_mode,
                "Experience": r.experience,
                "Qualifications": r.qualifications,
                "Operational basis": r.quantity_reason,
                "Rate basis": r.rate_reason,
                "Future basis": r.escalation_reason,
            }
            for r in p.plan.roles
        ],
    )
    sheet("Original vs reviewed", comparison_rows(p, records))
    sheet("Annual reviewed costs", c["reviewed"]["rows"])
    sheet("Annual original costs", c["original"]["rows"] if c["original"] else [])
    references = rate_comparisons(p.plan, records)
    for role, row in zip([r for r in p.plan.roles if r.included], references, strict=True):
        bm = rate_benchmark(
            records, role.mapped_role, role.benchmark_year, role.benchmark_status, role.benchmark_scope
        )
        row.update(
            {
                "Reference year": role.benchmark_year,
                "Filters": bm["filters"],
                "Limitations": bm["limitations"],
                "Sample sources": list(dict.fromkeys(r["source"] for r in bm["records"])),
                "Record identifiers": [r["record_id"] for r in bm["records"]],
            }
        )
    sheet("Reference comparisons", references)
    sheet(
        "Findings and decisions",
        [
            {
                "Finding": f.message,
                "Risk / consequence": f.impact,
                "Evidence": f.evidence,
                "Blocking": f.blocking,
                "Status": f.status,
                "Officer decision": f.justification,
                "Officer": f.officer,
                "Inclusion treatment": f.inclusion,
                "Expert / further review": f.further_approval,
            }
            for f in [*state["findings"], *finding_history(p.plan, state["findings"])]
        ],
    )
    sheet(
        "Source locations",
        [
            {"Document": d["name"], "SHA256": d["sha256"], "Extraction limitation": d["extraction_note"]}
            for d in p.documents
        ]
        + [
            {
                "Document": "Original pasted description",
                "SHA256": p.original_digest,
                "Extraction limitation": p.original_text,
            }
        ],
    )
    sheet(
        "Decision history",
        [{"Entry": json.dumps(x, ensure_ascii=False)} for x in [*p.history, *p.plan.history]],
    )
    wb.close()
    return out.getvalue()


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
