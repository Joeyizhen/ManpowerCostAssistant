"""Deployable Python Excel export. Formulas, cached results and native charts share app calculations."""

import json
from io import BytesIO

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from services.calculations import budget, sensitivity
from services.evidence import LABEL, escalation_benchmark, rate_benchmark
from services.workflow import budget_status, finding_history, findings


def text(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def export_excel(plan, records, extra_sheets=None):
    result = budget(plan, records)  # Invalid inputs never produce a misleading numeric workbook.
    output = BytesIO()
    wb = xlsxwriter.Workbook(
        output, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    )
    from services.reference_data import LIMITATIONS, prepared

    source_label = ("Prepared source quotations. " + LIMITATIONS) if prepared(records) else LABEL
    wb.set_properties({"title": "FM Manpower Budget", "comments": source_label})
    wb.set_calc_mode("auto")
    title = wb.add_format({"bold": True, "font_size": 18, "font_color": "#172B42"})
    header = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#147D74", "text_wrap": True})
    wrap = wb.add_format({"text_wrap": True, "valign": "top", "font_size": 11})
    money = wb.add_format({"num_format": '#,##0.00;[Red](#,##0.00);"-"', "font_size": 11})
    percentage = wb.add_format({"num_format": "0.00%"})
    input_fmt = wb.add_format({"font_color": "#1551A5", "text_wrap": True, "valign": "top"})
    sheets = {}

    def sheet(name, columns, subtitle=source_label):
        ws = wb.add_worksheet(name)
        sheets[name] = ws
        ws.hide_gridlines(2)
        ws.set_default_row(28)
        ws.set_column(0, len(columns) - 1, 23, wrap)
        ws.set_column(0, 0, 30, wrap)
        ws.write(0, 0, name, title)
        ws.merge_range(1, 0, 1, max(1, len(columns) - 1), subtitle, wrap)
        ws.set_row(1, 34)
        ws.write_row(3, 0, columns, header)
        ws.set_row(3, 36)
        ws.freeze_panes(4, 1)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.repeat_rows(0, 3)
        ws.set_footer("&CVersion " + str(plan.version) + " | &P of &N")
        return ws

    summary = sheet(
        "Budget summary",
        ["Role / contract year"]
        + [f"Year {i}" for i in range(1, plan.profile.years + 1)]
        + ["Full contract total"],
    )
    summary.set_column(1, plan.profile.years + 1, 18, money)
    ops = sheet(
        "Operational requirements", ["Field", "Officer-confirmed value / answer", "Evidence / coverage"]
    )
    ops.set_column(1, 2, 66, wrap)
    manpower = sheet(
        "Manpower plan",
        [
            "Role ID",
            "Original role",
            "Mapping",
            "Responsibilities",
            "Included",
            "Quantity / FTE",
            "Deployment basis",
            "Operational calculation inputs",
            "Rationale",
            "Experience",
            "Qualifications",
            "Exclusion reason",
            "Officer table duty notes",
            "Deployment / allocation",
            "Current contract quantity / FTE",
            "Change from current (same basis)",
            "Quantity unit",
        ],
    )
    rates_ws = sheet(
        "Rate evidence",
        [
            "Role",
            "Selected monthly inclusive rate",
            "Origin",
            "Justification",
            "Filters",
            "Sample count",
            "Median",
            "Average (arithmetic)",
            "P25",
            "P75",
            "Minimum",
            "Maximum",
            "Pricing years",
            "Source record IDs",
            "Inclusions",
            "Limitations",
        ],
    )
    esc = sheet(
        "Escalation",
        [
            "Role",
            "Contract year",
            "Selected change",
            "Mode",
            "Rationale",
            "Schedule count",
            "Median schedule YoY",
            "P25",
            "P75",
            "Observed pair full range",
            "Source schedules",
            "Policies / overlap",
            "Method and uncertainty",
        ],
    )
    calc = sheet(
        "Annual calculations",
        [
            "Role ID",
            "Role",
            "Contract year",
            "Period start",
            "Period end",
            "Optional year",
            "Quantity",
            "Base monthly rate",
            "Year change",
            "Factor",
            "Monthly unit rate",
            "Annual before policy",
            "Policy annual per head",
            "Policy annual cost",
            "Annual total",
            "Flat baseline",
            "Excess over baseline",
            "Price source",
        ],
    )
    sens = sheet(
        "Sensitivity scenarios",
        ["Scenario", "Change delta", "Contract total", "Annual totals", "Construction method"],
    )
    decisions_ws = sheet(
        "Findings and decisions",
        [
            "Finding ID",
            "Code",
            "Role ID",
            "Year",
            "Finding",
            "Impact",
            "Blocking",
            "Status",
            "Justification",
            "Inclusion / exclusion",
            "Evidence",
            "Officer",
            "Timestamp",
            "Further approval",
        ],
    )
    sources = sheet(
        "Sources and limitations",
        [
            "Record ID / item",
            "Source",
            "Submission year",
            "Contract start year",
            "Duration",
            "Contract year",
            "Pricing year",
            "Submitted / awarded",
            "Scope",
            "Rate basis",
            "Currency",
            "Validation",
            "Provenance",
            "Limitations",
        ],
    )
    # Calculation rows are the owning build. Outputs reference them, with app-computed cached values.
    indices = {}
    previous = {}
    for row_idx, row in enumerate(result["rows"], 4):
        excel_row = row_idx + 1
        indices.setdefault(row["role_id"], []).append(row_idx)
        values = [
            row["role_id"],
            row["role"],
            row["year"],
            row["period_start"],
            row["period_end"],
            row["optional"],
            row["quantity"],
            row["base_rate"],
            row["escalation"],
            row["factor"],
            row["monthly_unit_rate"],
            row["annual_before_policy"],
            row["policy_annual_per_head"],
            row["policy_cost"],
            row["annual_cost"],
            row["flat_baseline"],
            row["excess_over_baseline"],
            row["source_record"],
        ]
        calc.write_row(row_idx, 0, values, input_fmt)
        calc.write_formula(row_idx, 9, f"=1+I{excel_row}", None, row["factor"])
        if row["source_record"] == "Officer-confirmed escalation assumption":
            prev = previous.get(row["role_id"])
            rate_formula = (
                f"=ROUND(K{prev}*J{excel_row},2)" if prev else f"=ROUND(H{excel_row}*J{excel_row},2)"
            )
            calc.write_formula(row_idx, 10, rate_formula, money, row["monthly_unit_rate"])
        calc.write_formula(
            row_idx, 11, f"=ROUND(G{excel_row}*K{excel_row}*12,2)", money, row["annual_before_policy"]
        )
        calc.write_formula(row_idx, 13, f"=ROUND(G{excel_row}*M{excel_row},2)", money, row["policy_cost"])
        calc.write_formula(row_idx, 14, f"=L{excel_row}+N{excel_row}+S{excel_row}", money, row["annual_cost"])
        calc.write_formula(
            row_idx, 15, f"=ROUND(G{excel_row}*H{excel_row}*12,2)", money, row["flat_baseline"]
        )
        calc.write_formula(row_idx, 16, f"=O{excel_row}-P{excel_row}", money, row["excess_over_baseline"])
        calc.write_number(row_idx, 18, row["pwm_cost"], money)
        calc.write_number(row_idx, 8, row["escalation"], percentage)
        previous[row["role_id"]] = excel_row
    for i, role in enumerate([r for r in plan.roles if r.included], 4):
        summary.write(i, 0, role.label)
        summary.write(3, plan.profile.years + 2, "Role ID", header)
        summary.write(i, plan.profile.years + 2, role.id)
        subtotal = 0
        for y, ix in enumerate(indices[role.id], 1):
            value = result["rows"][ix - 4]["annual_cost"]
            summary.write_formula(i, y, f"='Annual calculations'!O{ix + 1}", money, value)
            subtotal += value
        summary.write_formula(
            i,
            plan.profile.years + 1,
            f"=SUM(B{i + 1}:{xl_col_to_name(plan.profile.years)}{i + 1})",
            money,
            round(subtotal, 2),
        )
    total_row = 4 + len(indices)
    summary.write(total_row, 0, "Annual overall totals", header)
    for y, total in enumerate(result["annual_totals"], 1):
        col = xl_col_to_name(y)
        summary.write_formula(total_row, y, f"=SUM({col}5:{col}{total_row})", money, total)
    summary.write_formula(
        total_row,
        plan.profile.years + 1,
        f"=SUM(B{total_row + 1}:{xl_col_to_name(plan.profile.years)}{total_row + 1})",
        money,
        result["contract_total"],
    )
    metadata = [
        ("Project", plan.profile.name),
        (
            "Contract start",
            plan.profile.start.isoformat()
            if plan.profile.start
            else (
                f"{plan.profile.start_year}-{plan.profile.start_month:02d} (anticipated month; exact day unknown)"
                if plan.profile.start_month is not None
                else f"{plan.profile.start_year} (year only)"
            ),
        ),
        ("Base / option years", f"{plan.profile.base_years} base + {plan.profile.option_years} optional"),
        ("Base-period total (SGD)", result["base_total"]),
        ("Optional-period total (SGD)", result["option_total"]),
        ("Status", budget_status(plan, records)),
        ("Final officer", plan.final_officer or "Not confirmed"),
        ("Final date (UTC)", plan.final_date or "Not confirmed"),
        ("Version", plan.version),
        ("Rounding", result["rounding"]),
        (
            "Starting overview rounding",
            "The Step 4 monthly-total × 12 overview may differ by cents from annual starting charges for fractional quantities. Contract totals retain annual role rounding after quantity × unit rate × 12.",
        ),
        ("Excluded costs", plan.profile.exclusions),
        (
            "Policy treatment",
            "Nominal additive monthly component amounts; daily prorating by effective date; no general escalation on these additive amounts.",
        ),
        ("Approval", "Budget confirmation is separate from historical database maintenance."),
    ]
    for i, (label, value) in enumerate(metadata, total_row + 3):
        summary.write(i, 0, label)
        summary.merge_range(
            i, 1, i, plan.profile.years + 1, value, money if isinstance(value, (int, float)) else wrap
        )
        summary.set_row(i, 36 if len(str(value)) > 85 else 28)
    annual_chart = wb.add_chart({"type": "column"})
    annual_chart.add_series(
        {
            "name": "Annual manpower cost (SGD)",
            "categories": ["Budget summary", 3, 1, 3, plan.profile.years],
            "values": ["Budget summary", total_row, 1, total_row, plan.profile.years],
            "fill": {"color": "#147D74"},
        }
    )
    annual_chart.set_title({"name": "Annual costs (optional years included)"})
    annual_chart.set_y_axis({"num_format": "#,##0", "name": "SGD"})
    annual_chart.set_legend({"none": True})
    summary.insert_chart(total_row + 19, 0, annual_chart, {"x_scale": 1.5})
    wf_row = total_row + 36
    summary.write_row(wf_row, 0, ["Waterfall step", "Offset", "Contribution", "Running total"], header)
    steps = [("Flat baseline", result["waterfall"]["baseline"])] + [
        (f"Year {i + 1} excess", x) for i, x in enumerate(result["waterfall"]["additions"])
    ]
    running = 0
    for i, (label, amount) in enumerate(steps, wf_row + 1):
        offset = running if amount >= 0 else running + amount
        running = round(running + amount, 2)
        summary.write_row(i, 0, [label, offset, abs(amount), running])
    wf_end = wf_row + len(steps) + 1
    summary.write_row(wf_end, 0, ["Contract total", 0, result["contract_total"], result["contract_total"]])
    waterfall = wb.add_chart({"type": "column", "subtype": "stacked"})
    waterfall.add_series(
        {
            "name": "Offset",
            "categories": ["Budget summary", wf_row + 1, 0, wf_end, 0],
            "values": ["Budget summary", wf_row + 1, 1, wf_end, 1],
            "fill": {"none": True},
            "border": {"none": True},
        }
    )
    waterfall.add_series(
        {
            "name": "Contribution (absolute bar height)",
            "categories": ["Budget summary", wf_row + 1, 0, wf_end, 0],
            "values": ["Budget summary", wf_row + 1, 2, wf_end, 2],
            "fill": {"color": "#147D74"},
        }
    )
    waterfall.set_title({"name": "Escalation to full contract total"})
    waterfall.set_legend({"none": True})
    summary.insert_chart(wf_end + 4, 0, waterfall, {"x_scale": 1.5})
    summary.merge_range(
        wf_end + 2, 0, wf_end + 2, plan.profile.years + 1, result["waterfall"]["method"], wrap
    )
    summary.set_row(wf_end + 2, 40)
    op_rows = [
        [k.replace("_", " "), text(v), "Project profile / officer input"]
        for k, v in plan.profile.model_dump(mode="json").items()
    ]
    op_rows += [
        ["Existing support supplied", plan.input_support, "Officer input; clarify only material overlaps"],
        ["Contract context", plan.contract_kind, "Officer input"],
        [
            "Current deployment availability",
            plan.current_deployment_status,
            "Optional comparison context, not a staffing requirement",
        ],
        [
            "Costing period basis",
            plan.profile.period_basis,
            "Exact date retained as unknown when only a year was supplied",
        ],
    ]
    op_rows += [
        [r.id, r.description, f"{r.coverage}; {r.provider}; {r.evidence}"] for r in plan.responsibilities
    ]
    op_rows += [
        ["Officer conversation", m["content"], m.get("time", "")] for m in plan.chat if m["role"] == "user"
    ]
    for i, row in enumerate(op_rows, 4):
        ops.write_row(i, 0, row)
        ops.set_row(i, min(120, 28 * (1 + len(str(row[1])) // 85)))
    seen = {}
    eix = 4
    for i, r in enumerate(plan.roles, 4):
        manpower.write_row(
            i,
            0,
            [
                r.id,
                r.label,
                r.mapped_role or "Unmatched; original title retained",
                ", ".join(r.responsibility_ids),
                r.included,
                r.quantity,
                r.quantity_basis,
                text(r.coverage.model_dump() if r.coverage else {}),
                r.quantity_reason,
                r.experience,
                r.qualifications,
                r.exclusion_reason,
                r.duties_notes,
                r.deployment,
                r.current_quantity if plan.current_deployment_status == "known" else None,
                (r.quantity - r.current_quantity)
                if plan.current_deployment_status == "known"
                and r.quantity is not None
                and r.current_quantity is not None
                else None,
                r.quantity_unit,
            ],
        )
        manpower.set_row(i, 85)
        if not r.included:
            continue
        bm = rate_benchmark(
            records,
            r.mapped_role,
            r.benchmark_year,
            r.benchmark_status,
            r.benchmark_scope,
            quantity_unit=r.quantity_unit,
        )
        rates_ws.write_row(
            i,
            0,
            [
                r.label,
                r.rate,
                r.rate_origin,
                (
                    (
                        r.rate_reason
                        or "Officer-selected inclusive monthly budgeting allowance; no additional explanation supplied"
                    )
                    + " "
                    + r.rate_notes
                ).strip(),
                text(bm["filters"]),
                bm["sample_count"],
                bm["median"],
                bm["average"],
                bm["p25"],
                bm["p75"],
                bm["minimum"],
                bm["maximum"],
                text(bm["pricing_years"]),
                ", ".join(x["record_id"] for x in bm["records"]),
                bm.get("source_unit", "Inclusive monthly per head; component split unavailable"),
                bm["limitations"],
            ],
        )
        rates_ws.set_row(i, 110)
        eb = escalation_benchmark(records, r.mapped_role, r.benchmark_status, r.benchmark_scope)
        for year, change in enumerate(r.escalation, 1):
            esc.write_row(
                eix,
                0,
                [
                    r.label,
                    year,
                    change,
                    r.escalation_mode,
                    r.escalation_reason,
                    eb["sample_count"],
                    eb["median"],
                    eb["p25"],
                    eb["p75"],
                    text(eb["pair_full_range"]),
                    text(eb["schedules"]),
                    text([p.model_dump(mode="json") for p in r.policies]),
                    eb["method"] + " " + eb["limitations"],
                ],
            )
            esc.write_number(eix, 2, change, percentage)
            esc.set_row(eix, 100)
            eix += 1
        for record in bm["records"]:
            seen[record["record_id"]] = record
        for item in eb["changes"]:
            for rid in item["record_ids"]:
                found = next(x for x in records if x["record_id"] == rid)
                seen[rid] = found
        if r.schedule_id:
            for record in records:
                if record["schedule_id"] == r.schedule_id:
                    seen[record["record_id"]] = record
    for i, scenario in enumerate(sensitivity(plan, records), 4):
        sens.write_row(
            i,
            0,
            [
                scenario["scenario"],
                scenario["annual_change_delta"],
                scenario["contract_total"],
                text(scenario["annual_totals"]),
                scenario["method"],
            ],
        )
        sens.write_number(i, 1, scenario["annual_change_delta"], percentage)
        sens.set_row(i, 75)
    from services.decision_basis import trace_rows

    movements = trace_rows(plan, records)
    future_records = {}
    from services.reference_data import recorded_reference_rows

    for basis in plan.decision_bases:
        for detail in basis.snapshots.values():
            for row in recorded_reference_rows(detail.get("reference_data", {})):
                future_records[row["record_id"]] = row
    if future_records:
        fields = list(next(iter(future_records.values())))
        future_ws = sheet(
            "Future reference records",
            fields,
            "Recorded reference cohorts supporting annual increases; origins and qualifications retained, not verified market rates.",
        )
        for ix, row in enumerate(future_records.values(), 4):
            future_ws.write_row(ix, 0, [text(row.get(field)) for field in fields])
    if movements:
        keys = list(movements[0])
        basis_ws = sheet("Decision basis", keys)
        for ix, movement in enumerate(movements, 4):
            basis_ws.write_row(ix, 0, [text(movement[k]) for k in keys])
            basis_ws.set_row(ix, 100)
    pwm_rows = [m for row in result["rows"] for m in row["pwm_months"]]
    if pwm_rows:
        pwm_ws = sheet(
            "PWM monthly trace",
            ["Role ID", "Role", *list(pwm_rows[0])],
            "Official MOM wage facts and checked dates are cited separately. Salary inputs, eligibility and unpublished periods are officer-confirmed budgeting assumptions, not a legal compliance determination.",
        )
        ix = 4
        for row in result["rows"]:
            for month in row["pwm_months"]:
                pwm_ws.write_row(ix, 0, [row["role_id"], row["role"], *[text(v) for v in month.values()]])
                ix += 1
        for role in plan.roles:
            if role.pwm:
                pwm_ws.write_row(
                    ix + 1,
                    0,
                    [role.id, role.label, "Officer-confirmed inputs", text(role.pwm.model_dump(mode="json"))],
                )
                ix += 3
    calc.write(3, 18, "PWM salary + employer on-cost change", header)
    current = findings(plan, records)
    columns = [
        "id",
        "code",
        "role_id",
        "year",
        "message",
        "impact",
        "blocking",
        "status",
        "justification",
        "inclusion",
        "evidence",
        "officer",
        "timestamp",
        "further_approval",
    ]
    for i, f in enumerate(current + finding_history(plan, current), 4):
        decisions_ws.write_row(i, 0, [text(f.model_dump()[k]) for k in columns])
        decisions_ws.set_row(i, 90)
    hist_start = len(current + finding_history(plan, current)) + 6
    decisions_ws.write(hist_start, 0, "Decision and revision history", header)
    for i, h in enumerate(plan.history, hist_start + 1):
        decisions_ws.write_row(
            i,
            0,
            [h.get("time", ""), h.get("version", ""), h.get("officer", ""), h.get("action", ""), text(h)],
        )
        decisions_ws.set_row(i, 65)
    for i, r in enumerate(seen.values(), 4):
        sources.write_row(
            i,
            0,
            [
                r["record_id"],
                r["source"],
                r["submission_year"],
                r["contract_start_year"],
                r["contract_duration"],
                r["contract_year"],
                r["pricing_year"],
                r["award_status"],
                r["scope"],
                r["rate_basis"],
                r["currency"],
                r["validation_status"],
                r["data_origin"],
                (
                    LIMITATIONS
                    + " Rate origin: "
                    + r.get("rate_origin", "Unknown")
                    + "; "
                    + r.get("issue_flags", "")
                )
                if r.get("reference_kind") == "prepared quotation"
                else "Synthetic; causes unknown; no salary or experience breakdown",
            ],
        )
        sources.set_row(i, 56)
    offset = len(seen) + 5
    for i, d in enumerate(plan.documents, offset):
        sources.write_row(
            i,
            0,
            [
                d["sha256"],
                d["name"],
                "",
                "",
                "",
                "",
                "",
                "Officer supporting document",
                "",
                "",
                "",
                "Unvalidated",
                "Original bytes preserved separately",
                d["extraction_note"],
            ],
        )
    for ws in sheets.values():
        ws.autofilter(3, 0, max(4, ws.dim_rowmax), ws.dim_colmax)
    for name, rows in (extra_sheets or {}).items():
        keys = list(rows[0]) if rows else ["Information"]
        ws = wb.add_worksheet(name)
        ws.set_column(0, max(0, len(keys) - 1), 26, wrap)
        ws.freeze_panes(1, 1)
        ws.write_row(0, 0, keys, header)
        for i, row in enumerate(rows, 1):
            for j, key in enumerate(keys):
                value = row.get(key)
                if value is None:
                    ws.write_blank(i, j, None)
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    ws.write_number(i, j, value, money)
                else:
                    ws.write_string(i, j, str(text(value)), wrap)
            ws.set_row(i, 60)
    wb.close()
    return output.getvalue()
