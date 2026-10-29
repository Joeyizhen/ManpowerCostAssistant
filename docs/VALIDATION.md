# 30 October 2026 — role ranges and saved Site Xtown example

See [implementation and checks](XTOWN_EXAMPLE.md). Final focused checks: **5 passed in 20.18s**; previous affected regression: 66 passed, two obsolete UI assertions subsequently corrected and verified. Saved project bodies and reference pointer unchanged; final example approval outstanding.

---

# 30 October 2026 — upload-first proposal review

- Final affected regression: **39 passed in 52.45s** (`outputs/evaluation/upload-first-verified.log`). Includes untouched-entry visibility, manual fallback, missing values/guidance, saved proposal compatibility, normal mixed sample through shared rates/general increase/PWM/results/final approval, and activity draft retention. All model interaction is disabled or mocked.
- The browser entry page now leads with upload and Read my proposal; empty tables and confirmation forms are absent until input is read or manual entry is chosen. The normal sample populated four roles and contract context successfully. No deliberate error-demo option remains visible.
- The revised sample contains 7 current / 8 proposed headcounts, starts January 2027 with one base plus one option year, and leaves future assumptions blank. Supplied monthly charges total SGD 35,500; the app's shared services recommend the applicable general and PWM treatment for officer confirmation. This supersedes the earlier ordinary sample's 2.5% and 2+1-year data below.
- Main app refreshed without switching, saving or approving its current project. Prior saved bodies, zero production proposal reviews and the active v3 pointer remain unchanged. Ruff, compilation, formatting, whitespace and a 155-file working-tree audit pass. No paid evaluation, source import/cleaning, deployment or further integration. See [upload-first implementation](TRACK2_UPLOAD_FIRST.md).

---

# 30 October 2026 — earlier standard uploads and annotated UI cleanup

- **64 passed in 212.84s** (`outputs/evaluation/oct30-verified.log`) across sample/legacy compatibility, officer journey, five-step UI, activity navigation and shared Track 2. New-role and retired-form fixtures reflect the current interface; calculation rules were preserved.
- Standard blank workbook plus a separate ordinary filled sample upload successfully. The sample has current 5 / proposed 6 headcounts, 2 base + 1 option year and one explicitly scoped 2.5% officer assumption. Monthly-cent rounding yields annual 339,600.00 / 348,090.00 / 356,792.52; contract 1,044,482.52.
- Browser verification on isolated actual-source data completed results, original comparison, 16-sheet Excel download and final approval. The original uncalculable total remained unavailable. Read-only service timings were under 0.1 seconds each, except workbook generation at 4.654 seconds. The prior rendering stall did not recur after restarting the corrected model-disabled preview wrapper.
- Removed the homepage draft reminder, unlisted-role form and shared-reason form. Prior custom titles, recorded rationales and legacy drafts remain preserved without hidden form blockers. Main-session current edits, both pre-existing saved bodies and the v3 pointer remain intact.
- Ruff, formatting, compilation, whitespace and current-working-tree privacy audit passed. Live model detection remains unverified; all tests were offline/mocked. No paid evaluations, source cleaning/generation/import, deployment, push or unrelated integration. See [current handover](HANDOVER_CURRENT_2026-10-30.md).

---

# 29 October 2026 — v3 reference and explicit PWM routing

- Activated `Excel_Selection_Completed_Sanitised_v3.xlsx`, dataset `21a2ad31f607d169-sprint2-reference-v2`; previous v2 snapshot retained for rollback. Required columns, record/control IDs and joins passed. 12,021 original observations are unchanged; 27 Standard Roles, 17 typical and six PWM Yes flags.
- Final fresh-process regression: **122 passed in 191.61 seconds** (`outputs/evaluation/v3-verified.log`). Covers isolated importer/activation checks, prepared PWM UI, role creation/renaming, exact flags, missing flags, job levels, calendar months, no overlap, saved references, mocked assistant mismatch/correction, five-step navigation and existing-proposal compatibility. No paid model calls.
- Two saved project bodies and their calculation results match before/after activation and app refresh. Main preview refreshed without saving, confirming or resetting the officer draft. Deployment now presents the two agreed actions without the duplicate discussion expander.
- 86 workbook PWM observations match the retained policy catalogue; 153 remain separate for mapping/basis/date review. No policy catalogue overwrite, rate cleaning, generated observations, unrelated integration, push or deployment. Live-model extraction/reasoning has not been evaluated. See [activation details and limitations](TRACK1_V3_REFERENCE.md).

---

# 28 October 2026 — headcount entry and comparison

- Removed the FTE choice from normal deployment entry. Current/proposed/change metrics use whole people, with incomplete subtotals for missing/invalid values. Excluded proposed zero rows still contribute their current staff to the comparison. Unspecified context does not assume current zero.
- Earlier saved units remain explicit and excluded from headcount totals until the officer supplies headcounts. No automatic FTE-to-person conversion or repricing. Assistant acceptance rejects newly introduced FTE/fractional headcounts.
- 52 affected journey/pricing/headcount checks passed; final summary/input checks: 19 passed in 23.83 seconds; headcount/assistant compatibility: 19 passed in 34.54 seconds. Tests use isolated databases and mocked/disabled model calls. Ruff, compilation and whitespace checks pass; saved production rows match the pre-update copy.

---

# 28 October 2026 — five-step Track 1 refinement

- Complete offline regression: **331 passed in 625.45 seconds** (`outputs/evaluation/five-release.log`). A final control-restore fix found in the read-only live-session check was then verified with **22 affected navigation/pricing checks passed in 59.73 seconds** (`outputs/evaluation/five-navigation-final.log`). Hidden Streamlit widget keys now reload retained rate values when returning to a screen; financial facts and confirmations are unchanged. Ruff, compilation, Git whitespace and working-tree privacy checks pass (62 files / zero findings). Test databases and test-only model mocks/guards were used; no paid evaluations.
- The five visible steps are Project, Deployment, Starting rates, Annual changes and Budget. Coverage includes all-step navigation, old six-screen locations, no confirmation from navigation, directly editable merged deployment/confirmation, explicit proposal acceptance, source-linked role choices, case/alias deduplication, unrestricted exact inputs, both bar directions, saved explicit zero and role/year profiles, unchanged-reference preservation, cleared-rate preservation, invalid unfinished project text save/reopen, mixed PWM components and scenario isolation/adoption.
- Browser checks used separate prepared and explicitly synthetic fixture databases on temporary ports 8512/8513. A typical pill added only one role, left quantity unanswered and removed the added alias from available choices. Monthly exact 9,000.00 and bar adjustment to 8,999.99 stayed synchronized with monthly/annual costs. Annual bar 2.33% and exact input 2.40% updated the preview while its 2.32% database-average marker stayed fixed. Original saved 2%/2.5%/3% role profiles were retained separately and restored to zero change from the recorded budget. Native keyboard control was used when browser auto-scroll placed a checkbox beneath the sticky navigation. Narrow-viewport labels wrap and currency figures remain complete.
- The synthetic walkthrough reaches Budget as step 5, with full/base/option totals and the annual component chart/table directly visible, plus separate scenarios, manpower and sources. No final officer budget was confirmed and no red runtime errors were observed. Local screenshots are retained under `outputs/evaluation/five-annual.png` and `five-budget.png`.
- Production database comparison: the main app independently recorded a revision **14 → 15** save during verification. Only navigation, confirmation versions and history changed; its profile, roles, responsibilities, decision bases and assumption drafts are identical to the pre-run copy. The other revision-10 project row is identical. The latest live revision is preserved, not rolled back. Test/preview project IDs and databases are separate. Five original reference/fixture hashes and the source workbook SHA256 are unchanged. Final audit details remain in `outputs/evaluation/five-preservation.json`.
- The active workbook has **26 Standard Roles / 17 Typical manpower? = Yes** entries, confirmed by the user as Common Manpower. Both UI lists resolve from the active snapshot; no UI-maintained production role list. Source-provenance identities have no duplicates. FM source extremes were traced to SHA-matched source columns and retained, not trimmed or automatically normalised. Missing comparable person/FTE deployment, hours/coverage and inclusions still prevent a verified monthly-price recommendation; that is a backend project-team gap, not an officer investigation task. Annual reference method and historical cohorts are unchanged. See [five-step implementation and exact data gaps](TRACK1_FIVE_STEP.md).
- Main app on port 8511 is left running; temporary previews are closed/stopped after visual checks. Existing unrelated track/integration work is retained. No push, unrelated merge, deployment or paid model evaluation.

---

# 28 October 2026 — Track 1 officer journey refinement

- Complete final offline regression: **321 passed in 259.72 seconds** (`outputs/evaluation/officer-final-verified.log`). Workspace TEMP/TMP and isolated databases; paid-model calls mocked or guarded. Ruff, Python compilation and Git whitespace checks passed.
- Coverage includes new non-PWM Steps 1–6, relevant PWM/mixed component reconciliation, reopened drafts, shared operational-reason persistence, explicit assistant proposal acceptance, unchanged confirmation preservation, material invalidation, direct allowances, general compounding, custom inputs, existing zero/yearly/quoted profiles, distinct role-specific constants, read-only scenario previews and explicit adoption. Original reference switching cannot reprice accepted budgets.
- Browser walkthrough used only a separate synthetic preview database. Step 3 exposes the two requested actions; Step 4 preserves prices and retained explanations; Step 5 preserves distinct 2%/2.5%/3% role assumptions with zero change from recorded budget; Step 6 shows full/base/option SGD 2,505,318.72 / 1,624,907.04 / 880,411.68, four tabs and reconciled annual components. Scenario viewing did not adopt changes. No red runtime errors or live AI calls. Screenshots: `outputs/evaluation/officer-step3.png` and `officer-step6.png`.
- Read-only comparison after browser checks confirms **both production saved projects unchanged**. Five original reference/fixture hashes and the source workbook SHA256 are unchanged. Working-tree privacy scan: **56 files, zero findings**. Generated workbooks, private data and outputs remain ignored.
- Main app is available on loopback port 8511 (health 200). The saved officer project was reopened at Step 4 and the previously visible unsaved Admin Executive allowance restored to 5,030.45 without saving or confirming it. Temporary preview 8512 was closed/stopped. No final budget confirmation, push, merge, paid evaluation or deployment.
- FM source extremes were investigated, not trimmed. Unverified quote units, deployment and inclusions prevent a confident per-head/FTE recommendation; conditional statistics remain secondary. Existing PWM eligibility, salary evidence, calendar-month/FTE limits and unpublished-period decisions remain explicit. Calculation/rounding rules unchanged. See [implementation and limits](TRACK1_OFFICER_REFINEMENT.md).

---

# 27 October 2026 — prepared source connection

- Full offline regression after shared retrieval, UI and compatibility changes: **302 passed in 226.94 seconds**. A test-isolation issue found during the first combined run was corrected by restoring the legacy reference context before each legacy test.
- Prepared importer/query/UI follow-up, including two additional compounding/retained-quote checks: **9 passed in 18.41 seconds**. Tests use invented workbooks, isolated databases/stores and a paid-model-call guard.
- Final compact-evidence/review/export/PWM follow-up: **54 passed in 44.87 seconds**.
- Final provenance/unit/export/proposal checks: **70 passed in 49.48 seconds**. Ruff, compilation and whitespace checks passed. A working-tree privacy scan checked 36 changed/new files with zero findings; generated snapshots/workbooks remain ignored.
- Real selection: 12,021 rows; no ID/join problems; 7,057 conditional rate records, 6,884 annual-candidate records, 2,716 quantity records; 111 synthetic rates excluded. One source-rate average and one annual pair were independently recomputed in `scripts.reference_report`.
- Actual saved project remains JSON-equivalent at revision 14/version 54. Contract/base/option totals remain 8,150,733.48 / 3,321,473.52 / 4,829,259.96. Original workbook SHA256 and five retained reference/fixture hashes unchanged.
- Source-switch fingerprints, repeated imports, temporary isolated reversal, insufficient FTE/scope evidence, equal submission weighting, missing-year exclusion and all four workflow entries are covered. Prepared tender calculations and Excel export pass. PWM catalogue unchanged: 239 separate observations, 86 matching wage observations, 153 requiring review.
- Local app refreshed without restarting its session; browser verifies both activity choices at 127.0.0.1:8511. No paid model call, remote change or deployment. See [detailed readiness/limitations](PREPARED_REFERENCES.md).

---

# 27 October 2026 — Sprint 2 combined navigation

- Agent 1 pre-checkpoint regression: **256 passed in 248.42 seconds**.
- Combined focused regression: **75 passed in 160.67 seconds**.
- Complete combined suite: **295 passed in 297.81 seconds**.
- After the final restore/default-input fix: **35 affected checks passed in 53.94 seconds**, including activity navigation, retained checkbox answers, proposal/results safeguards and grouped future/PWM journeys.
- The navigation tests open all four workflows and preserve independent drafts across Back and Change activity. Synthetic tender comparisons and exports retain the existing service results. A failing model-client guard verifies no ordinary navigation/calculation invokes AI, even with configured credentials.
- Agent 1's actual saved project remains identical at revision 14/version 54. Five reference hashes match the preserved baseline. Calculator/model/storage/contract implementations are unchanged from the checkpoint; Agent 2 calculation services match a7923f3 exactly. No v2 workbook was imported or activated.

Browser checks opened both activity menus and all four task entries at 985-pixel width, then verified recovery of the unchanged synthetic budget draft after visiting both tender workflows.

See [SPRINT2_INTEGRATION.md](SPRINT2_INTEGRATION.md) for capability boundaries and the remaining handoff work. Native Excel recalculation, live model quality and production deployment remain outside this milestone. Older entries are historical.

---

# 27 October 2026 — independent Track 1 and Track 2 verification

- Final affected regression: **82 passed in 73.02 seconds** across proposal services/UI, Track 1 results, decisions, agent mocks, annual-reference and PWM safeguards.
- Complete Track 1 and mixed-PWM offline walkthroughs: **54 passed in 101.65 seconds**.
- Final Track 2 concise-heading and monetary-format checks: **16 passed in 11.45 seconds**. This repeats proposal coverage after a presentation change; it is not an additional 16 unique tests.
- An earlier wider attempt passed 112 checks and hit one cold-start UI timeout. It is not claimed as a successful full-suite run. The final focused runs preload UI dependencies and pass.
- Browser: isolated synthetic database, original/reviewed EPV, recorded 0%, saved-review recovery, separate final approval, four results tabs and narrow layout. The real officer project was not edited or approved.
- Preservation audit: exact saved model equality at revision 14/version 54; five reference-file hashes unchanged; existing integration contracts/fixtures unchanged. Working-tree shareable scan: 68 files, zero findings before these final documentation updates. No v2 import/activation or reference-source update.
- Ruff, compilation and whitespace checks pass. All model responses in tests are mocked; no paid evaluation or deployment. Native Excel recalculation, production market validity and live assistant reliability remain unverified.

See [Track 1 results](STEP6_RESULTS_PAGE.md) and [Track 2 implementation](TRACK2_IMPLEMENTATION.md). Tracks 3/4 integration remains deferred. Older entries below are historical validation of earlier increments.

---

# 26 October 2026 - Track 1 usability refinement

See [the usability refinement report](TRACK1_USABILITY_REFINEMENT.md). **89 affected checks passed in 271.03 seconds**, including the full offline six-step walkthrough and mixed PWM journey. Compact pricing now supports one shared basis for selected roles; final-review actions are concise with three distinct choices, and confirmation follows the annual breakdown. Explicit zero and selected sensitivity totals remain visible. The original saved project (revision 13/version 45) and existing PWM reference hash are unchanged. No new dataset import, workbook update, paid model call or deployment.

---

# 26 October 2026 - Step 6 review and confirmation

See [the completed Step 6 report](STEP6_REVIEW_AND_CONFIRM.md). Final affected release regression: **54 passed in 99.75 seconds**. The existing saved project was checked read-only at revision 13/version 45 and remains identical. New coverage includes missing inputs, accepted decisions, rationale reuse, annual/Yoy/deployment reconciliation, non-mutating sensitivity, grouped units, draft exports and the existing final confirmation gates. The normal page follows the requested six-section order. Original calculation and saved-project rules remain intact; no paid model call or deployment.

---

# 26 October 2026 - final cost comparison

See [the final comparison report](FINAL_COST_COMPARISON.md). **42 affected checks passed in 61.42 seconds**: chart reconciliation, attribution, reductions, quoted schedules, variable quantities, mixed PWM, removed history/checkpoint UI, final confirmation and exports. Ruff, compilation and whitespace checks passed. No paid calls or deployment.

---

# 26 October 2026 - editable yearly table and visible PWM

- Affected table/general/PWM journeys: **23 passed in 84.51 seconds**.
- Final checks after disabling the constant controls in yearly mode and removing the unnecessary second percentage requirement: **11 passed in 56.63 seconds**.
- Verified legacy yearly-text loading, editable percentages, unanswered cells, saved draft persistence, explicit profile replacement, open Applicable manpower and PWM sections, and the full PWM save/apply/confirm journey.
- Browser verified with an isolated synthetic database on port 8512. Screenshot: outputs/evaluation/yearly-table-pwm-2026-10-26.jpg. No real project edits, paid model calls or deployment.
- Ruff, compilation and whitespace checks passed.

---

# 26 October 2026 - recommendation-first annual manpower cost increase

See [the Step 5 refinement report](STEP5_ANNUAL_RECOMMENDATION.md) for the fixed cohort, behaviour and limitations.

- Full regression attempt: **205 passed**, with two older UI expectations failing because they assumed the previous numeric control and automatic PWM title assignment. Those expectations now follow the synchronised exact control and explicit coverage-check selection.
- Final affected regression, including both corrected journeys, general-reference exclusions, custom/no-document assumptions, insufficient evidence, compounding, saved profiles and PWM safeguards: **55 passed in 55.17 seconds**. An earlier focused final-layout run also passed 20 checks.
- Ruff, Python compilation and whitespace checks passed. Working-tree privacy scan: **50 changed/new files, zero findings**.
- Browser: isolated synthetic database on port 8512. Verified the recommendation-first ordering, 3.17% displayed average, 2.50%-3.90% observed range and 24 fixed-cohort schedules; confirmed separate recorded cleaning PWM category and contract impact in the mixed fixture. Screenshot: ignored outputs/evaluation/annual-recommendation-2026-10-26.jpg.
- No paid model calls, policy-source changes, deployment, staging, commit or push. Existing officer project data was not modified by the preview.

---

# 26 October 2026 — compact deployment, pricing and final review

See [the completed refinement report](COMPACT_TRACK1_REVIEW.md). Full offline regression: **199 passed**; final affected checks: **63 passed**. Browser checks covered compact FTE pricing, saved revisions and confirmed qualified export availability in an isolated synthetic database. Existing annual contract rounding is retained; monthly × 12 differences are disclosed. No paid model call or deployment.

---

# 25 October 2026 — grouped Step 5 verification

See [the completed refinement report](STEP5_GROUPED_REVIEW.md) for behaviour, evidence method and remaining calculation decisions.

- Full offline regression: **186 passed in 117.16 seconds**.
- Affected UI, PWM and decision-basis checks after draft/staging fixes: **51 passed in 115.46 seconds**.
- Final focused grouped journeys after percentage alignment: **11 passed in 19.70 seconds**.
- Running-preview upgrade recovery: **33 focused UI/PWM/compatibility checks passed in 21.74 seconds**. A stale cached-helper import was recovered without clearing session state or model classes; the main app was reopened from its existing saved revision.
- Ruff, Python compilation and whitespace checks passed. Working-tree privacy audit: **43 changed/new shareable files, zero findings**.
- Browser: isolated synthetic database on port 8512; verified default average, observed range and sample count, PWM summary/staged editing, cost impact, save-and-switch, and a single primary future-cost confirmation. Ignored screenshot: `outputs/evaluation/grouped-step5-2026-10-25.jpg`.
- No paid model evaluations, deployment, push, staging or commit. Existing saved officer projects were not used in the preview.

The first restricted-runtime test attempt could not create temporary files and stalled at UI startup. Successful runs used an explicit workspace temp directory and the permitted host runtime. Earlier interface tests expecting removed per-role controls were revised to test grouped selection, explicit confirmation and retained legacy drafts.

---

## 20 October 2026 — simpler Step 5

Replaced the repeated role panels with one general annual allowance and shared reason. Show individual controls only for selected exceptions or retained special arrangements. New PWM setup is limited to explicit cleaning, security, lift/escalator technical and landscape trade titles; generic FM, Technician, M&E and fire safety roles receive no new PWM option. Combined titles retain all identified trade-category choices and their original title. Title discovery never establishes worker eligibility. Existing saved PWM settings remain reviewable.

Validation: **179 tests passed in 235.55 seconds** in the full regression. A further **55 affected checks passed in 207.19 seconds** after the hidden-draft/replacement fix and combined-title filter. The earlier added edge check exposed stale annual controls after explicitly replacing an unapplied profile; the fix clears superseded annual controls while retaining component-adjustment drafts. The final stored-PWM switching message was also checked independently. Ruff, compilation, whitespace checks and the 40-file working-tree privacy scan passed. No calculation formula, policy snapshot, integration schema, real officer project or paid model evaluation changed.

The browser verified one shared 2.5% assumption for an invented FM/Technician team, SGD486000 for the two-year synthetic fixture, no ordinary-role PWM selector, and no repeated per-role panels. Screenshot: ignored `outputs/evaluation/step5-one-allowance-2026-10-20.jpg`. Browser data came from a separate synthetic database on8512 with dummy provider settings; current8511 and its unsaved officer project were left intact. Temporary preview is stopped after verification. Use Streamlit Rerun to load the edited source while retaining the existing draft.

---

Current decision-basis/PWM increment: **164 tests passed in 288.26 seconds**, **24 final focused checks passed in 106.69 seconds** after the saved-method and stage-scoped confirmation changes. Ruff, compilation and working-tree privacy audit passed (39 changed/new shareable files). Independent salary-ratio/calendar-month calculations, cached workbook reconciliation and synthetic UI/controller behaviour are distinct evidence; no live model score or paid evaluation is claimed. See [current report](TRACK1_DECISION_BASIS_PWM.md).

The earlier broad run retained an obsolete helper signature during development; a fresh run then found only the obsolete Back-navigation assertion. That assertion was corrected to reflect saved draft navigation, while future confirmation stays blocked. The final full regression passed. No private officer record, source document or usage counter was reset.

> **Current increment — 19 October 2026:** [Decision bases and PWM walkthrough](TRACK1_DECISION_BASIS_PWM.md) supersedes earlier PWM-pending, hidden-unit and draft-saving notes below. Calendar-month PWM is implemented with explicit eligibility/salary sources and non-overlap guards. See [remaining decisions](PENDING_DECISIONS.md). Earlier results are historical, not validation of this increment.

Validation for 19 October: **144 tests passed in 271.52 seconds**. Ruff, compilation and whitespace checks passed; working-tree privacy scan found no issues in 25 changed/new shareable files. The full suite includes deterministic calculation/reconciliation, saved-project compatibility, confirmation invalidation, narrow discrepancy parsing, table correction, rate overrides and a complete offline six-step walkthrough. Conversational contracts use mocked SDK replies; no paid/live model score is claimed. Initial targeted failures were test-harness setup (an unsupported exact title in a benchmark fixture and an invalid AppTest session-state lookup); the first full run also found an obsolete Continue-button assertion. These were corrected before the successful full regression.

The isolated synthetic browser server was stopped after checking the changed views. Main preview remains at loopback port 8511 using existing configuration. No push, deploy, import, commit, stage or change to existing saved officer projects. Escalation formulas, integration schemas and role inventory remain unchanged.

Latest annotation refinement: 132 tests passed in 120.58 seconds. Targeted advisory/mocked-conversation/offline-walkthrough subset: 33 passed in 28.14 seconds. Browser recorded synthetic advice and advanced unchanged staffing to rates without provider calls. Calculation tests and mocked conversation checks remain separate evidence; no new real-model score. Details: [officer experience](OFFICER_EXPERIENCE.md).

# Shareable validation record

## Officer-experience refinement — 17 October 2026

**129 offline tests passed in 106.26 seconds**; Ruff/compilation/whitespace checks passed. Final presentation changes passed another complete six-step walkthrough (1 test, 16.76s). Tests cover month precision and legacy year-only plans, guarded exact-date policies/quotes, conditional/blank grids, FTE and change reasons, saved-title/resume protection, unapplied controls and advanced drafts, readiness without approval mutation, rate-year warnings without silent adjustment, and full confirmation/export.

An isolated browser walkthrough completed all six screens and downloaded a synthetic qualified budget: SGD 2,505,318.72 (base 1,624,907.04; options 880,411.68). The downloaded workbook's cached annual sums, nine sheets and two charts reconciled. A separate read-only historical replay retains SGD 1,985,025.48 and original usage counters. No provider call, real project approval/deletion or native Excel recalculation occurred. Conversational tests use mocks and are not a real-model score. See [officer experience](OFFICER_EXPERIENCE.md) for scope, fixed failures, shared interface impact and remaining limits.

## Browser feedback and project deletion — 17 October 2026

**110 automated tests passed in 72.76 seconds**; scoped Ruff and compilation passed. This includes title/step/context presentation and the new owner/revision-guarded transactional deletion method, Cancel and current/other draft handling. Synthetic test databases only; no existing saved officer project was removed. Working-tree privacy scan: 12 changed shareable files, zero findings. No paid/live conversational check; mocked controller evidence remains separate from deterministic tests. Calculation/export modules are unchanged after the earlier zero-call replay.

## Resumed six-step Track 1 refinement — 17 October 2026

**107 automated tests passed in 73.96 seconds**; scoped Ruff and compilation passed. Six-screen navigation, saved step, Back/Continue, revision relocking, role costs, synthetic bands and explicit zero future changes are included alongside the unchanged service/contract regressions. The preserved complete-budget/Excel replay reconciles SGD 1,985,025.48 with zero provider calls and unchanged historical counters. Full scope/failure notes: [Track 1 refinement](TRACK1_REFINEMENT.md).

Conversational evidence is separate: updated UI tests use mocked replies; no new paid/live model case or human score is claimed. Native Excel rendering/recalculation remains untested.

## Saved Track 1 checkpoint

On 17 October 2026 the saved checkpoint passed 94 automated tests, scoped Ruff and compilation. Tests cover current/proposed/zero/FTE quantities, editor deltas, explicit copy/mark-zero, save/resume, conservative mapping, mocked review/retry, rate assumptions, escalation, approval invalidation, storage isolation, full-cost arithmetic, charts and Excel formulas/cached values. Automated checks do not establish real conversational reliability.

A zero-call replay of a preserved complete synthetic development conversation reconciled SGD 1,985,025.48, annual/base/option totals, supported retrieval, waterfall, sensitivity, nine-sheet Excel and two native charts. The earlier prefilled demo remains a separate invented scenario. Private traces/output workbooks are not committed; their original usage counters are retained locally.

Historical live development runs were bounded and are not a frozen held-out score. No new live API test was run for the zero/current-deployment increment or this collaboration preparation. Revised prompt/schema behaviour still needs bounded live evaluation later. Original limits remain six requests/twelve tools per turn, 3,500 output tokens per response, 90-second timeout and no automatic retries; runner-specific ceilings remain unchanged. Human/held-out scores are unassigned.

## Collaboration verification

Final collaboration run: **105 tests passed in 36.10 seconds**. Scoped Ruff and compilation passed. The original Track 1 suite remained intact; new contract/schema/privacy tests passed. Development/live-hybrid runners were exercised only in zero-call dry-run mode. The preserved complete-budget replay again reconciled its unchanged totals and workbooks without API calls. The staged audit scanned 65 files and verified 23 exclusion probes with no findings; it did not print secret values.

Run the tests and staged-file audit documented in the README. New tests validate synthetic fixture/schema freshness, cross-field amount/reference/unit/period checks, distinct approval/submission states and privacy-audit rules. The integration example is regenerated solely from the existing invented demo and Python calculator, without keys/database access. It does not confirm a real budget or implement Agent 2 comparisons.

Final local run results are recorded with the collaboration baseline preparation. No hosted service, real tender evidence, native Excel recalculation or multi-user hosted deployment is established by these checks. Remaining product/UI limitations are listed in [HANDOVER.md](HANDOVER.md).


Final scoped-draft checks: a saved future-source selection remains pending when the widget is absent. It blocks future/final confirmation while earlier staffing/rate steps remain usable, avoiding a navigation trap. Draft saving still inspects and preserves all draft categories. The latest source passed Ruff, compilation, whitespace validation and the 39-file privacy audit. Isolated synthetic preview was stopped after verification; existing port8511 was not accessed or restarted.

Final browser checks verified the lower/selected/higher comparison and grouped deployment view. An additional repeated-title/different-profile UI check passed in 19.84 seconds, so scenario profile details remain visible for distinct positions sharing a title. The final working-tree privacy scan covered 55 changed/new files with zero findings.
