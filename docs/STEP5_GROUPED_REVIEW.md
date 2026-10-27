# Grouped future manpower costs — 25 October 2026

Step 5 now has three sections: a general annual increase, PWM workers when relevant, and financial impact with one confirmation action. The six-screen journey is unchanged.

## Shared annual increase

New supported groups start with the database arithmetic average as an unconfirmed recommendation. Each distinct comparable manpower-only schedule contributes its median consecutive-year unit-price change; the average, minimum and maximum all summarise those schedule medians with equal schedule weights. Repeated deployment rows do not add statistical weight. At least three schedules per role cohort are required. A gap in any affected cohort requires an explicit officer assumption for the group. Full trade/service records are excluded. All current reference records are labelled synthetic demonstration data, not market evidence.

The percentage control records two decimal places, matching its display. Raw schedule statistics remain attached separately; existing monthly currency rounding is unchanged.

An observed-range control retains its database basis automatically. A custom percentage requests one financial explanation and an optional document reference. Existing recorded assumptions and explanations are carried forward. The preview is separate from recorded assumptions. The primary action **Confirm future cost assumptions and continue** records the displayed selection and confirms it; Save project only persists draft work. A single-year contract has no anniversary increase to justify.

The audit includes the selected percentage, roles by stable ID, quantities, applicable periods, reference method and retained records. Excel adds a Future reference records sheet so source snapshots remain inspectable without relying on a long JSON cell. Starting monthly allowances and staffing explanations are not rewritten.

## PWM

Potential workers are grouped by cleaning, security, landscape and lift/escalator maintenance. Title hints do not prove eligibility. A grouping correction is available without a calculation-method questionnaire for every role. Existing special yearly arrangements remain retained and inspectable; replacing them requires an explicit choice.

PWM entry proceeds through category/eligibility, known salary component and covered workers, then projection review. Confirmed headcounts are reused. Salary splits are never inferred from inclusive charges. Recorded PWM setups show a compact summary with optional editing. Unsupported actual dates/units are explained before data entry and drafts remain saveable; no invented date is suggested.

The existing deterministic calendar-month salary-ratio method is unchanged. Official source, snapshot digest, checked date and published-period limits remain attached. Unpublished periods require an explicit officer treatment. No full-unit escalation is added to a PWM role. Its remaining inclusive charge and uncovered workers stay flat; a separately evidenced deployment/component model is needed for another treatment.

## Other Track 1 fixes

- Save and switch reloads the just-saved revision when resuming the open project, preventing the older pre-save snapshot and later optimistic-lock conflict.
- The final pivot uses role ID and title. Excel summary adds stable role IDs; legitimate repeated titles remain separate. Review warns about repeated titles without merging them.
- Rationale validation accepts concise concrete causes or sources and treats spelled-out numbers and digits consistently. Vague statements such as “Need more manpower” remain insufficient.
- Focused basis prompts replace generic category/classification forms. Earlier quantity/rate bases remain in the audit and are reused until relevant inputs change.
- Manpower review leads with included rows and units; exclusions are expandable and an empty Suggested changes section is hidden.
- Rate summaries put selected allowance, monthly role cost, unit, year, inclusions and source support together. Existing reference-year warnings and one shared treatment basis remain.
- Final review includes prominent totals and largest cost drivers, stable-ID breakdowns, outstanding decisions and traceable bases. Valid calculations can be exported as a labelled draft; final confirmation identifies the plan version and retains qualifications.
- Unfinished inputs from the earlier Step 5 layout are retained separately and require an explicit resolution before grouped confirmation. Saved finding edits are not discarded when resolving legacy future inputs.

## Remaining calculation decisions

No new salary, inflation, market price or policy rule was invented. Partial-month PWM, FTE/hourly conversions, overlapping component combinations and automatic splits across multiple PWM categories remain unsupported. Unpublished wage periods remain assumptions. See [remaining decisions](PENDING_DECISIONS.md).

Verification is offline with synthetic records and mocked assistant contracts. No paid model evaluations, deployment, commit or push are included. The user's saved project database is not used for the isolated visual preview.

Validation: **186 full-regression checks passed**, **51 affected checks passed** after draft/staging fixes, and **11 final focused journeys passed** after percentage-display alignment. Ruff, compilation and whitespace checks passed. A working-tree privacy audit scanned 43 changed/new shareable files with zero findings. An initial restricted-runtime attempt could not create test temporary files and stalled during UI startup; successful runs used an explicit workspace temporary directory and the permitted host runtime. Obsolete per-role control tests were replaced with grouped preview/confirmation and legacy-draft retention checks.

The running main app exposed a cached-helper ImportError during upgrade. Startup now refreshes the small compatibility guard before importing UI helpers; old Step 5 helpers and changed audit/export helpers are removed from the import cache without clearing session state or model classes. **33 focused UI/PWM/compatibility checks passed in 21.74 seconds** after this fix. The main app was reopened from the existing saved revision without changing or confirming its assumptions.

The complete synthetic example traversed all six screens, confirmed findings with retained qualifications, and exported the confirmed workbook without a provider call. Separate checks covered an explained staffing increase, a retained flagged value, custom escalation, mixed PWM/non-PWM totals, repeated titles, save/resume of the same project and unsupported real dates preserving drafts. Browser screenshots are kept locally in ignored `outputs/evaluation/`; they are not part of the shareable evidence fixture.
