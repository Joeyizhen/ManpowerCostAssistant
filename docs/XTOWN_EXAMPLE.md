# Site Xtown example and illustrative role ranges — 30 October 2026

The Starting rates screen now offers an active role-specific minimum/average/maximum
slider when validated reference recommendations are unavailable. Missing headcount
rates start at the illustrated midpoint. Entered rates and explicitly cleared values
are retained. These authored demo assumptions are not database observations, market
rates or salary minima. Configure them in `services/planning_allowances.py`; validated
references can replace them later. Per-role reference-detail expanders are removed;
existing provenance remains in recorded decisions and exports.

## Ready-to-resume example

Saved project: **Appointment of FM Vendor to provide service for Site Xtown for 3 + 3 years (Example)**.
Load Site Xtown example creates a fresh working copy on a clean installation through the existing unsaved-edit guard. If an officer has already saved and edited their own copy, resume that project rather than replacing it with the fixture.

- Existing commercial site: two office blocks and a retail podium.
- 13 current / 17 proposed staff. Confirmed starting monthly manpower charges: SGD 69,000.
- Starts 1 January 2027: three base years plus three option years.
- General manpower: explicit illustrative 2.5% annual compounded allowance from Year 2.
- Cleaning workers use confirmed example category, quantity and salary-component
  inputs for the retained PWM schedules. Unpublished periods explicitly hold the
  last projected salary; this is an example assumption, not a published policy.
- Base SGD 2,600,772.06; option SGD 2,746,416.84; contract SGD 5,347,188.90.
- Opens the final Budget screen in the current five-screen interface (legacy wire
  step 5). Input checkpoints identify Example preparation, not officer approval.
  **Final budget approval remains outstanding.**

Saved-project identifiers, private snapshots and preservation reports remain local and are excluded from Git.

## Verification

The affected regression run had 66 passes and two outdated UI assertions. Both were
corrected to reflect the working controls and final budget metric. The final focused
run passes all five tests (`xtown-last-check.log`): authored defaults and retained
values/order, slider/exact input/clear behavior, example save/reopen/calculation,
sidebar loading, and the expanded per-role slider count. Ruff and whitespace checks
pass. No paid models, database imports, deployment or further integration were used.

Additional navigation checks: `xtown-nav-check.log` passes (1 test, 20.81s) for
active-reference example navigation with confirmed deployment retained;
`xtown-nav-resume.log` passes (1 test, 18.94s) for actual database save/resume
followed by Starting rates navigation. Both use isolated storage and no model calls.
Browser verification on the running 8511 app confirmed all five example rates
remain unchanged, each has an active illustrative range and marked average, and
no per-role reference-detail panels remain. Returning to Budget preserves all
input confirmations and the SGD 5,347,188.90 contract total. No final approval clicked.

Latest results-page cleanup: removed the redundant grey summary notes, the repeated
PWM eligibility caption, and the visible Assumptions and qualifications section.
The annual increase is followed by one plain PWM line referring to published MOM
rates. Unpublished-period treatments remain recorded and visible alongside PWM
schedule details; exclusions remain in the supporting tab. No stored decisions,
calculations, exports or confirmation checks were changed. Existing results and
saved-assumption checks: 8 passed in 29.54s (`budget-copy-verified.log`).

Follow-up display cleanup: the final Assumptions & sources tab no longer renders
per-role PWM category/publication/unknown-period notes or the raw reference-document
list. The single MOM source label remains. Stored PWM details, unpublished-period
treatments, evidence records, exports and confirmation safeguards are unchanged.
Existing results-page checks: 4 passed in 16.09s (`source-list-removal.log`).
