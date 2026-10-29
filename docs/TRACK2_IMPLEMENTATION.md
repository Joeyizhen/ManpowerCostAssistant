# Shared Track 2 budgeting workflow — 30 October 2026

Track 2 is an alternative entry into Agent 1: **Upload existing proposal → check figures
and assumptions → view the reviewed budget**. After interpretation, its decision
navigation opens Deployment, Starting rates, Annual changes and Budget using the
shared services and controls. Supplied, sufficient inputs remain populated. Track 1
keeps its five-screen journey and its independent active Plan.

## Current implementation

- Standard upload files are `data/templates/track2-blank-template.xlsx` and
  `data/templates/track2-preplanned-budget-sample.xlsx`. Both use Project, Proposed
  manpower and Proposed escalation sheets. The filled sample is an invented existing
  office with 7 current and 8 proposed staff, a January 2027 start and 1 base plus
  1 option year. Four roles include general FM manpower and two Cleaners. Monthly
  starting charges total SGD 35,500. Future assumptions are blank: the shared annual
  screen recommends a supported general increase and guides the PWM setup. No
  contract total is preloaded or approved. All proposal charges are illustrative.
- The first screen leads with upload and Read my proposal. Template/sample controls
  and manual entry are secondary. Project fields, the captured table and confirmation
  controls appear only after reading input, loading the normal sample or choosing
  manual entry. Saved intake drafts remain accessible. Exact missing context,
  quantities and monthly charges are listed for completion in the shared review.
- Try a sample proposal reads the same ordinary workbook offered for download. The
  older intentional-error workbook is retained only as a regression fixture; its
  download and load path are removed from the normal interface.
- Downloadable blank and example Excel workbooks have Project, Proposed manpower
  and Proposed escalation sheets. Current deployment is optional. The same parser
  handles upload and Load example proposal, without preloaded findings or approvals.
- Deployment-only proposals are supported. Readable questionable methods import as
  assumptions to review; malformed structure identifies the field or worksheet.
  Other supported CSV, generic XLSX, TXT, PDF and DOCX routes remain available.
- Captured documents, original rows, source locations, original model and digest
  remain separate from the reviewed plan. Explicit current quantities select the
  existing-contract comparison; absent current quantities stay unanswered.
- `services/cost_routing.py` supplies the same prepared Standard Roles flags to both
  tracks. An explicit No cannot be overridden by title keywords. Missing mapping or
  eligibility requires clarification; PWM never implies a salary split.
- Material checks identify the role, issue and next action. A wrong PWM assignment
  offers a preview of the general reference or an explicit custom assumption if
  evidence is insufficient. Acceptance is separate from preview, save and approval.
  Editing the plan invalidates a stale correction preview.
- `services/ui_context.py` directs shared pricing, annual-change and decision
  callbacks to the active Track 2 plan. Existing pending form edits from the earlier
  proposal interface remain unapplied until the officer uses or dismisses them.
- The calculator, references, effective-date/PWM safeguards, annual compounding,
  confirmation invalidation, result components and workbook exporter are reused.
  Results have Budget, Scenarios, Manpower, Assumptions & sources and Changes from
  your original proposal tabs. Original/reviewed percentages, quantities, rates,
  methods and reasons accompany calculable cost differences. An uncalculable
  original has no manufactured original total or variance.

## Short demonstration

1. Open Manpower budgeting → Review a proposed budget → Need a template or sample?
   → Try a sample proposal. Or upload the filled sample and select Read my proposal.
2. Check the populated project context and four role rows. Confirm inclusive monthly
   charge semantics and the captured interpretation. No annual percentage is supplied.
3. Confirm the deployment and supplied starting charges in the shared review steps.
4. At Annual changes, inspect the supported general annual recommendation for the
   FM roles. No exact rate is hardcoded into the sample or invented if unavailable.
5. At Annual changes, review the Cleaner's actual category and eligibility. The
   example explicitly supplies two covered workers and an invented salary component
   of SGD 2,300 per worker; neither is inferred from its SGD 3,600 contractor charge.
   Confirm the flat remainder and apply salary-only PWM before continuing.
6. Confirm future assumptions and inspect the shared budget and Changes from your original proposal; export a
   draft or separately confirm the budget after resolving essential missing inputs.

The example contains invented proposal inputs, not observed reference records.
These steps deliberately retain the necessary officer confirmations.

## Verification and limits

Current verification is recorded in the latest handover and validation log. Template
extraction, deterministic detection/calculation, mocked assistant interaction and
browser interaction are assessed separately. Mocked interaction does not prove live
assistant detection. No paid model evaluation was run.

The active prepared source is the existing sanitised v3 snapshot, with its original
provenance and comparability limitations. No reference cleaning, generated historical
records, new import, unrelated integration, merge, push or deployment was performed.
Missing comparable unit/inclusion evidence still prevents a supported monthly-rate
recommendation. Published PWM schedule coverage and first-of-month handling remain
explicit safeguards; OCR, live assistant quality and production hosting are unverified.

---

# Historical checkpoint — 27 October 2026 (superseded above)

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
