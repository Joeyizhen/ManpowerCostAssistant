# Upload-first proposal review — 30 October 2026

Track 2 now starts with **Upload your existing proposal** and the agreed copy:
“We'll capture the information you already have, identify any gaps, and guide you
through completing and reviewing your manpower budget.”

## Officer experience

1. Upload a proposal and select **Read my proposal**. Template/sample downloads and
   manual entry are secondary expandable options. No empty manpower table, project
   questionnaire or confirmation fields appear on the untouched upload page.
2. Check the captured project context and populated manpower table. Unknown values
   remain blank; concise guidance identifies missing context, quantities and charges.
   Blank future-increase columns are hidden until supplied. An original contract
   total is optional. Confirm the interpretation and inclusive monthly-charge basis.
3. Continue through the existing shared Deployment, Starting rates, Annual changes
   and Budget controls. Supplied values remain editable and are not requested again.
   Missing inputs, sources and eligibility are completed in the relevant step.

Original submitted files, captured rows and accepted revisions remain separate.
Saving, reading a document, accepting revisions and confirming a budget stay distinct.
Saved intake drafts and manual entry remain supported. A selected unread file must
be read or removed before loading a sample, so it cannot be silently lost.

## One normal mixed sample

**Try a sample proposal** loads the same workbook as **Download filled sample**:
`data/templates/track2-preplanned-budget-sample.xlsx`. It has:

- Existing office, January 2027 start, one base year plus one option year.
- Facilities Manager 1 → 1; Admin Executive 1 → 1; Technician 3 → 4; Cleaner 2 → 2.
- Seven current / eight proposed people, all headcount. Monthly supplied charges
  total SGD 35,500 and are explicitly invented proposal inputs.
- Future assumptions left blank for the shared services to recommend and the officer
  to review. No fixed percentage, original calculated total or approval is preloaded.
- Explicitly supplied Cleaner salary component of SGD 2,300 and two covered workers.
  The officer still confirms the category, eligibility and remaining-charge treatment.

The general group uses supported reference recommendations when available, with a
custom officer assumption available otherwise. PWM uses applicable salary movements
and calendar effective dates, never an inferred salary split or an overlapping
general increase on the same salary component. The sample period is within the
retained cleaning schedule's published coverage. The calculator and policy data are
unchanged. The old intentional-error workbook remains a regression fixture only;
its load/download controls are absent from the normal interface.

## Validation and boundaries

Final affected checks: **39 passed in 52.45s** (`upload-first-verified.log`). The entry page and normal mixed
sample were inspected in a separate model-disabled browser preview. Full normal
sample capture, shared decisions, PWM setup, results and final confirmation are
covered by isolated AppTest; originals and Track 1 session ownership remain intact.
No paid model evaluation, production project save, source import/cleaning, deployment
or additional Tracks 3/4 integration was performed. Live independent assistant
reasoning and OCR remain outside this verification.

Proposal UI marker is 6; runtime compatibility refreshes the intake helper too.
