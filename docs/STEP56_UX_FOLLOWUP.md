# Step 5–6 officer-facing refinement — 26 October 2026

Saved zero annual increases now have explicit preview choices: use the supported reference average or keep 0%. The choice changes the future-cost draft, not recorded rates, quantities, approvals or the saved database. Step 5 confirmation applies the reviewed assumption using the existing calculation and workflow rules. Step 6 links back to Step 5 when a zero profile has an available reference comparison.

The annual table defaults to Year, Annual cost, Change (SGD) and Change (%). A separate control reveals the cost components, with annual total before the additional columns. Inapplicable PWM series/columns and empty adjustment series are omitted; chart colours remain attached to their components. Actual PWM assignments remain visible even when their incremental cost is zero.

The review uses a short demo-reference disclosure only when the active records identify themselves as synthetic. Detailed provenance, limitations, calculations and decisions remain available in Rates, assumptions and sources and in the existing export. The deployment heading is Manpower included in this budget. The final button is Confirm budget, retaining version information and all existing validation gates. The assistant section is Ask about this budget.

No saved officer project, reference dataset, wage schedule or workbook was changed. The existing synthetic reference remains active.

Validation: 36 focused checks passed across the new saved-zero/compact-review journeys and existing final review, annual recommendation, usability and cost-attribution suites. Ruff and Python compilation passed. Streamlit UI checks used isolated test databases outside the restricted sandbox because its local socket-pair setup cannot run inside that sandbox.

## Workbook readiness

The supplied v2 workbook was inspected read-only. It contains 12,021 selected manpower records and eleven sheets, including Record Controls, Role Mapping Review, Source Register, issue registers and PWM Trend. Record Controls identifies 7,057 conditional source-rate candidates, 4,853 rates requiring review and 111 synthetic rates excluded from observed-rate use. All 12,021 calendar-date fields are labelled synthetic. Its readiness sheet states that annual pairs are candidates rather than approved comparisons and award/submission outcomes remain unknown.

Recommended integration is a separate staged reference source. Preserve record/role-line identifiers, field-level eligibility and unresolved mappings; do not promote candidate records automatically. The current application expects confirmed pricing years, awarded status and comparable scope, so an explicit adapter and eligibility review are required before replacing its synthetic references. Contract-year rate changes must not be recast as calendar-year wage inflation. No import was performed in this change.
