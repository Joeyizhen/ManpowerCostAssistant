# Track 1 five-step refinement — 28 October 2026

**Historical increment:** later refinements in the README and release checkpoint supersede the role-entry forms and reference defaults described here. The five-screen sequence and saved-navigation compatibility remain.

This increment builds on the preceding officer refinement. It keeps the calculator, PWM safeguards, evidence snapshots, accepted professional decisions and financial confirmation dependencies. The visible sequence is **Project → Deployment → Starting rates → Annual changes → Budget**. Deployment entry and confirmation use one table and one screen; assistant review remains optional. There is no separate sixth screen.

## Headcount update

New deployment entry uses whole-person headcount, without an FTE selector. Current headcount, proposed headcount and the change appear together and update from the edited table. Explicit zero exclusions remain valid; missing quantities show known subtotals and a pending comparison. An unanswered deployment context does not imply a zero current team. Saved earlier-unit entries are retained without conversion, excluded from headcount totals and can be replaced only with officer-entered headcounts. Assistant suggestions cannot introduce a new FTE quantity or round an allocation into people. The historical calculation engine and reference records still support saved earlier-unit projects.

Headcount update verification: 52 affected checks passed; final context/input checks passed 19 tests; headcount/assistant compatibility checks passed 19 tests. Original saved project rows were compared read-only; none were changed by this update.

## Retained and refined

- Project keeps the operational brief, anticipated month, base/option durations and calculated total. Exact dates are requested only by dated calculations. Missing project fields appear after attempted Continue.
- Deployment uses one editable table with headcount/FTE, applicable current/change columns and operational notes. Shared reasons remain optional for related roles; valid recorded reasons are reused. Exactly two main actions confirm deployment or open discussion. Assistant proposals show before/after changes and require acceptance; acceptance stays in Deployment.
- Starting rates retain direct numeric entry without a custom-mode checkbox. Supported references have a compact synchronised bar, average marker and clearly labelled range. Exact values outside the evidence range expand the selection domain without being clipped or relabelled as database evidence. An unavailable database recommendation has a neutral rail and an officer allowance input; no arbitrary market bounds or fake average are supplied. Explicitly cleared rates remain unanswered across navigation/reopening instead of being reseeded. A quotation is optional. Unsupported material allowances need a short budgeting reason, not a source-data investigation.
- Annual changes retain one direct percentage, a compact reference bar, the average marker and budget impact. The applicability summary replaces the repeated deployment table; role details remain secondary. Saved zero, different yearly profiles, distinct per-role constants, quotes and reasons are retained. General charge changes compound from Year 2; covered salary PWM remains separate with no inferred salary split or eligibility.
- Budget retains full/base/option totals, directly visible yearly chart/table, separate scenarios/deployment/sources views, explicit scenario adoption and final confirmation distinct from Save draft.

## Role source confirmed with the user

The active `Excel_Selection_Completed_Sanitised_v2.xlsx` has no Common Manpower worksheet or named range. The user confirmed **Standard Roles → Typical manpower? = Yes** as the common-role designation. The active taxonomy has **26 titles, 17 Yes entries**. Those entries supply the selectable typical pills, including the listed optional cleaning/security roles; none is added automatically. The remaining standard titles and identifiable source manpower titles supply the searchable additional control. Titles from unspecified source sections are not promoted to valid choices. Unsafe or combined mappings retain their source wording rather than becoming an invented equivalence.

The catalogue reads the active snapshot's stored Standard Roles and Role Mapping Review, so a validated new import updates the lists without changing a UI constant. Known aliases cannot create a duplicate, while seniority/combined/shift/shared distinctions are preserved. A clearly labelled unlisted-title control remains available, and unfinished text survives step navigation and saving.

## Saved six-screen compatibility

Persisted `ui_step` is a navigation wire location, not a financial gate. To avoid changing existing saved schema or gate evidence, the historical locations remain supported: 0 → Project; 1 or 2 → Deployment; 3 → Starting rates; 4 → Annual changes; 5 → Budget. The visible ordinal is mapped separately to 1–5. The old review location is canonicalised to Deployment in memory/on a later explicit save; original project rows are not batch rewritten. This changes no quantities, prices, reasons, decision signatures, version or confirmation records.

The five buttons are always present. Navigation captures unfinished controls and changes only location. Later steps can be opened before completion but display the missing prerequisite with a direct route rather than presenting incomplete totals as a complete budget. Opening a step does not initialise prices until deployment is confirmed. Back follows the five visible steps. Unfinished invalid project text is saved in draft state separately from the last valid financial facts; it blocks confirmation until corrected. A visit to pricing does not alter an older reference year or clear its confirmations; only a deliberate reference-year selection does so.

## Reference comparability

Private source investigations retained original titles, units and source-cell evidence without manufacturing full-time equivalents from property/shared allocations. Quoted unit charges alone cannot certify hours, relief, worker coverage or inclusions. Exact records and quotation values are kept in local verification evidence rather than published here.

Starting-rate recommendations require aligned denominator, coverage, inclusions and independent source support. Where those are missing, the current interface uses explicitly authored illustrative assumptions. Annual analysis retains eligible adjacent contract-year unit-rate pairs and equal submission weighting, with gaps excluded. These movements are not proven inflation. Consolidation leaves the current v3 pointer unchanged and does not activate v2. See [PREPARED_REFERENCES.md](PREPARED_REFERENCES.md).

## Verification

The full offline suite passed **331 tests in 625.45 seconds**. A final fix for hidden numeric controls returning blank was subsequently verified with **22 affected navigation/pricing checks in 59.73 seconds**, including exact retained values and unchanged financial facts/confirmations after visiting other steps. Isolated browser walkthrough, saved-project comparison and privacy results are recorded in `VALIDATION.md`. Test plans and preview databases are separate from production saved projects. No paid model evaluations, unrelated-track merge, push or deployment is included.
