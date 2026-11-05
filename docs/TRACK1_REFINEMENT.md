> **Current increment — 19 October 2026:** [Decision bases and PWM walkthrough](TRACK1_DECISION_BASIS_PWM.md) supersedes earlier PWM-pending, hidden-unit and draft-saving notes below. Calendar-month PWM is implemented with explicit eligibility/salary sources and non-overlap guards. See [remaining decisions](PENDING_DECISIONS.md). Earlier results are historical, not validation of this increment.

# Track 1 refinement — 17 October 2026

Latest browser-feedback/deletion increment: **110 tests passed in 72.76 seconds**; Ruff/compilation passed. Working-tree privacy scan: 12 files, zero findings. The initial six-step increment record follows; the browser-feedback section at the end supersedes its statement that storage was unchanged.

Continued from the published shared baseline `02cbfc9` on `feature/agent1`. The starting working tree was clean. Changes stay in Agent 1 UI/controller and its tests/docs; shared models, calculations, workflow/storage, export, integration DTOs, schemas and fixtures are unchanged. Agent 2 continues independently on `feature/agent2`.

## User-facing changes

1. Six separate screens: project/contract, current/proposed manpower, assistant review/manpower confirmation, monthly rates, future cost changes, and full budget/findings/export.
2. Back/Continue, a step list and progress indicator. The existing `ui_step` is saved with a project; input-completion markers are recalculated after revisions. Input completion is separate from officer approval. Old saved projects with confirmed gates can resume without a schema migration.
3. Current/proposed tables keep blank/zero/FTE and original-title semantics. Review uses the retained brief, quantities, notes and prior answers. Navigation and confirmations make no automatic provider call; targeted review/chat and explicit retries remain opt-in.
4. Monthly pricing adds Python-calculated role costs and a visual observed synthetic min–max band on the slider scale. Exact entry allows outside-range assumptions. Unsupported rates start blank with no invented band. Source details/notes remain expandable.
5. Future role controls start collapsed, showing the selected profile. Constant, yearly, quoted-schedule and evidenced policy controls remain. An explicit constant-change action supports a zero-change scenario without treating an untouched zero control as an officer choice. Selecting a constant profile clears quoted-schedule mode; shared double-escalation guards remain unchanged.
6. Findings, decision history, full/annual/base/option costs, charts, sensitivity, explicit final officer confirmation and draft/confirmed workbook downloads share the final screen. Validation/final confirmation still use the existing shared gates.

## Automated calculation and controller checks

**107 passed in 73.96 seconds**. Includes existing arithmetic/evidence/approval/storage/export/contract checks and updated mocked Streamlit checks for the six screens, actual editor deltas, Back/Continue, retained quantities, revision invalidation, saved step position, blank custom rates, monthly role costs, supported bands, explicit zero future-change choice, full budget/charts and export. Scoped Ruff and compilation passed. Changed shareable files passed the working-tree privacy scan with zero findings; the baseline index/exclusions were also audited separately. No commit or staging was performed.

The first sandbox UI run stalled before executing the app because Python's asyncio loopback socket was blocked; it was stopped. Tests passed with local loopback access. A replay wrapper initially checked a nonexistent report key after all reconciliation checks passed; corrected to `zero_api_calls` and rerun successfully. These were verification-environment/wrapper failures, not calculation failures.

A read-only replay of the preserved complete synthetic development conversation used zero provider calls. It reconciled SGD 1,985,025.48 (base SGD 1,295,114.04; options SGD 689,911.44), independent role/year cent rounding, annual sums, waterfall, sensitivity, supported retrieval, nine-sheet formulas/cached values and two native workbook charts in both preserved and current exports. Prior traces/reports/workbooks and usage counters were not rewritten: 15 attempts / 42 requests, 396,664 counted input / 10,647 output tokens remain historical evidence.

## Conversational checks — separate evidence

No paid/live model test was launched. Mocked replies cover targeted follow-up retention, one explicit manpower confirmation and explicit retry without automatic repeat. Those controller checks do not establish real-model faithfulness, current/proposed reasoning, zero-exclusion understanding or conversation quality. Prior live runs describe earlier builds and remain unscored development evidence. Existing limits/counters and held-out cases remain unchanged.

## Remaining limits and review

Browser review verified the project/manpower split, step header/progress, table, retained original synthetic titles and Back/Continue at narrow and desktop widths. Local screenshot: `outputs/evaluation/track1-six-step-manpower-2026-10-17.jpg` (ignored). The existing localhost:8511 preview was restarted to clear stale imports; saved projects were preserved and no model review/approval was triggered. Browser review used an unsaved labelled synthetic example. Later screens were exercised by mocked AppTest, not manually approved in the browser. Native Excel rendering/recalculation, real market evidence, broader human/live conversational evaluation, shared-host deployment and trusted approval-store integration remain unverified. Missing numeric cells can still display `None`; very narrow tables can still need horizontal scrolling. Reviewed title inventory and labelled synthetic fixtures are the only evidence used. No historical import, paid test, push, deployment, prototype or Pulse change occurred. Review shared-interface impact through the normal PR workflow before future integration changes.


## Browser feedback increment

- Main page title is now “Build a new manpower plan”; the optional project name appears separately. “Synthetic civic venue” remains the example's stored name, not the app title.
- Removed the repeated top-page synthetic banner. Synthetic provenance remains in fixture data, benchmark/source displays and exports.
- Every screen now uses one heading: “Step X out of 6: …”. Removed the duplicated step caption/section heading.
- Moved the additional staffing text into a collapsed optional context section, retaining existing notes. The short unit explanation uses the example “0.5 means half of one full-time role”; detailed unit guards remain in the column help and shared calculations.
- Added Delete selected project → named confirmation / Cancel in the sidebar. Confirmation permanently removes that owned planning project and its saved revisions. Deleting the open saved project closes its current draft; deleting another saved project retains the open draft. No actual saved officer project was deleted in development.

The shared storage addition is `Store.delete(project_id, owner, expected_revision)`: additive API, no table/schema/DTO migration and existing save/load/list signatures unchanged. Ownership, stale-revision protection and project/history transaction rollback are tested. This shared-module change should be called out for teammate review before merging; Agent 2 code and contracts are untouched.

Role-inventory harmonisation remains a separate review: clean presentation/spelling first, then explicitly agree aliases while preserving original titles, seniority and combined duties. No role equivalences or price eligibility were changed by this UI feedback increment.

Browser confirmation after refreshing the preview: neutral title, “Step 1 out of 6” heading, absent top synthetic banner and Delete control beside Resume. Screenshot: `outputs/evaluation/track1-browser-feedback-2026-10-17.jpg` (ignored). No existing project deletion or officer approval was performed.
