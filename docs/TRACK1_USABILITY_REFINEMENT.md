# Track 1 usability refinement - 26 October 2026

This targeted refinement keeps the six-step EPV journey, existing calculations, earlier confirmations and saved-project format.

## Changes

- Step 4 keeps one compact pricing table, with observed-range controls and synchronised exact rates. Supporting details and exception inputs are expandable. In-range officer selections retain their comparison evidence automatically; unsupported rates and values outside the existing observed range still request a brief pricing basis. This uses the existing range-review boundary rather than a new financial threshold.
- A quotation or explanation can be applied once to selected roles. Figures remain unchanged. Each role retains evidence and the applicable role IDs internally. Changes to the relevant rate, unit, year or comparison context stop a stale shared basis being reused.
- Step 5 distinguishes an unanswered annual increase from an explicit 0%. Reference wording identifies within-schedule manpower unit-rate movements, excludes quantity changes and does not describe synthetic dates as observed wage trends. Existing annual compounding, yearly profiles and separate PWM safeguards are retained.
- Step 6 replaces the long saved-project action card with a concise action summary, expandable affected-role details and a direct route to Step 4. It explains that an out-of-range rate is a comparison flag, not proof the rate is wrong.
- Keep my figures, Correct the interpretation and Revise figures are separate choices. Relevant earlier explanations are reused. Unrecorded explanations survive switching choices; accepted findings retain the existing invalidation rules.
- Final confirmation follows the annual breakdown. Its disabled state names the next action nearby. Flat annual costs have an explanation based on the actual selected profile and deployment.
- Sensitivity displays lower, selected and higher total contract budgets prominently. The selected scenario has a visible zero-difference marker. Exploration remains read-only. Existing grouped deployment keeps headcount and FTE separate.

## Verification

The affected offline release regression passed **89 tests in 271.03 seconds**, covering the complete six-step synthetic walkthrough, shared pricing, current saved-project actions, retained answers, range/exact controls, custom and missing assumptions, annual compounding, saved yearly profiles, mixed PWM/general budgets, sensitivity, chart reconciliation, exports, storage and confirmation invalidation. This is an affected regression, not a claim that every repository test was run.

The original partially completed project was inspected through an isolated copy. The original snapshot remains byte-equivalent as a model at revision 13 / version 45. Its confirmed contract fields are three base years and four option years; these were preserved even though the project title differs. The existing PWM reference SHA-256 is unchanged. No new dataset was imported and no PWM workbook was updated.

Browser checks on an isolated database verified the saved-project action summary, three choices, flat-cost explanation, direct Step 4 route and compact pricing table. A completed mixed PWM/general example verified the annual breakdown before confirmation and three prominent sensitivity totals. Screenshots are retained locally under ignored outputs/evaluation/usability-*. Code lint, compilation and whitespace checks passed; the working-tree privacy scan covered 57 changed/new files with zero findings.

## Remaining limitations

The saved project still needs appropriate pricing bases for six roles, including two rate-range review flags. These decisions belong to the officer; this refinement does not invent quotations, explanations or approvals. A genuine shared quotation may now be recorded once for the relevant roles. Available benchmark evidence remains labelled synthetic, and does not establish actual market rates or policy requirements. Existing annual-role rounding is preserved, including the previously disclosed small FTE display reconciliation difference.

No paid model evaluation, deployment, staging, commit or push was performed.
