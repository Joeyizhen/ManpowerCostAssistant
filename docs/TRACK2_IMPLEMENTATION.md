# Independent Track 2 proposal review — 27 October 2026

Track 2 is implemented locally as **Add proposed budget → check figures and assumptions → view the reviewed budget**. It does not copy Track 1's six screens. Track 1 remains the new-plan journey. Integration with Tracks 3/4 is deferred.

## What is available

- Capture pasted tables, conservative free text, manual rows, CSV, XLSX, text PDFs and DOCX. Check interpreted context, titles, quantities, units and inclusive monthly charges before freezing the original. Missing values remain unknown; zero exclusions are explicit.
- Preserve original figures, stated totals, yearly quotations, raw columns, file bytes, hashes and extraction locations separately from accepted revisions. Supplementary documents do not overwrite original evidence. An original digest prevents accidental rewriting in the proposal store.
- Review figures, operational checks, future costs and material findings in tabs. Rate previews have a range/average marker and synchronised exact control; applying a revision is explicit. Unapplied edits cannot be silently confirmed.
- Reuse eligible reference filters, annual compounding, explicit year-specific profiles, supported quoted schedules, coverage arithmetic and relevant PWM controls. No market rate, salary split, eligibility or staffing requirement is inferred. Optional assistant review is requested explicitly and works on a review copy; it cannot approve the budget.
- Retain valid professional choices with a recorded material justification, correction or specific uncertainty. Reuse relevant earlier bases. Missing experience/qualification details are presented as a qualification rather than a routine per-role questionnaire.
- Show original recalculated EPV, reviewed EPV, dollar/percentage variance, base/option totals and annual components. The four results tabs reuse Track 1 presentation components. Draft Excel and printable HTML management reports precede a separate final confirmation.
- Save proposal drafts with owned optimistic revisions, preserve unapplied answers, protect switching with Save/Discard/Keep open, and download/restore snapshots as separate unapproved reviews. Saving neither accepts suggestions nor approves a budget.

## Architecture and scope

`services/proposals.py` wraps the existing Plan model. Independent `proposal_reviews` and `proposal_review_snapshots` tables use the configured database engine and authenticated owner. Existing Track 1 project tables and Plan schema are not repurposed. `proposal_inputs.py` supplies the three screens; `services/proposal_export.py` generates the comparison workbook and management report.

All financial results come from the existing calculator. Proposal-specific quoted records are supplied privately to its quoted-schedule lookup, with explicit source and validation labels; ordinary benchmark comparability excludes them. They are not appended to reference files or used for reference training. Changes to shared helpers are optional callbacks, reusable result styling and safe development reload markers; their Track 1 defaults are preserved.

The existing welcome selector now opens Track 2. No navigation, transfer, teammate merge or application restructuring for Tracks 3/4 was added. Integration contracts, schema fixtures and teammate work were not edited in this increment. No prior useful integration work was reverted or deleted. Reference importing remains separate, and the v2 workbook is inactive.

## Verification and readiness

The final affected run passed **82 checks in 73.02 seconds**, including all 16 new proposal tests and the affected Track 1 results, decisions, agent mocks, annual-reference and PWM checks. A separate complete Track 1/mixed-PWM walkthrough run passed **54 checks in 101.65 seconds**. All **16 proposal checks passed again in 11.45 seconds** after the final concise results heading and monetary formatting. An earlier broader run passed 112 checks but hit one cold-start UI timeout; that timeout is not represented as a green full-suite run. The final proposal UI test preloads its dependencies and passed in the affected run.

Coverage includes immutable originals, independent storage/ownership/concurrency, unknown versus zero, source extraction, material arithmetic discrepancies, accepted revisions, revised units and dates, preserved pricing provenance, private quote exclusions/no double escalation, compounding, single-year contracts, unsupported original quotation retention, safe exports, draft persistence, snapshot recovery and separate review/final approval. Browser verification uses an isolated synthetic database; no real officer project is approved or edited.

## Remaining limitations

- This is a local development release using labelled synthetic reference evidence, not validated operational market pricing. The active reference files and PWM source records are unchanged.
- Extraction does not provide OCR or universal layout understanding. Scanned PDFs and ambiguous tables need officer transcription/correction. XLSX extraction reads stored values without executing formulas/macros. The officer confirms interpretation and SGD/monthly/unit semantics.
- Existing quoted-schedule calendar/mapping and PWM effective-date/eligibility safeguards remain. Unsupported original schedules are preserved as evidence but may have no calculable original EPV until interpreted; unknown totals are not displayed as zero. Salary components and unpublished periods require explicit treatment.
- Adequacy, capability and coverage are not proven by cost comparisons. Record the actual operational basis or a specific retained uncertainty; optional coverage arithmetic uses officer inputs, not an invented staffing standard.
- Live assistant quality, native Excel recalculation and production hosting have not been validated here. All model tests are mocked; no paid evaluation, deployment, stage, commit or push was performed.
