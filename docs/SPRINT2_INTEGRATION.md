# Shared reference increment — 27 October 2026

Prepared selection **bf02f4c629b7f181-sprint2-reference-v1** is now activated for both activities on `integration/sprint2`. The following navigation report is historical; its statements about inactive v2/unchanged evidence services describe the preceding milestone. See [the shared reference report](PREPARED_REFERENCES.md) for eligibility, equal-submission sampling, source examples, PWM differences, checks and reversible activation. Live budget transfer and direct cross-tenderer comparison are still separate follow-ups.

---

# Sprint 2 combined application — 27 October 2026

This is a local navigation and composition milestone. It makes four existing workflows accessible in one application. It does not establish a trusted cross-track handoff or activate shared historical data.

## Source preservation

- Shared baseline: `02cbfc9`.
- Agent 1 local checkpoint: `ec759de`, created on `feature/agent1` from an explicit reviewed 68-file list. Before that commit, all 256 tests passed in 248.42 seconds; lint and privacy checks passed. The complete indexed privacy audit inspected 107 files and 23 exclusion probes with zero findings.
- Agent 2 source: `a7923f3` on `origin/feature/agent2`, including earlier `88248da`. Both remote developer branches and remote main were refreshed and left unchanged.
- Integration work is on `integration/sprint2`, based on the Agent 1 checkpoint. Conflicts in app.py, README, collaboration guide and project brief were composed individually. Current budgeting screens were preserved, alongside the teammate's new modules and tests.
- The Agent 2 calculation services remain identical to their source commit. Existing Agent 1 calculator, model, storage, evidence and transfer-contract implementations are unchanged by this navigation increment.

No push, merge into main, force-push, reset or deployment is part of this task. Private saved projects, uploads, credentials, runtime outputs and environments are excluded from the commits.

## Officer-facing navigation

The landing page asks **What would you like to do?** and offers two equally prominent activities:

| Activity | Available tasks |
|---|---|
| Manpower budgeting | Build a new budget; Review a proposed budget |
| Tender evaluation | Compare submissions against an approved budget; Compare tenderer proposals |

Normal navigation omits agent architecture and track numbers. Each task has Back to activity options and Change activity actions, plus a current activity/task caption. Historical data management appears only as a Planned secondary status.

Each workflow keeps its own state. Navigation caches registered value inputs, including unfinished answers, separately from the recorded models. Button events and uploaded-file handles are never replayed. Tender project fields use immediately retained inputs while their explicit Save project and continue action still controls acceptance. Existing save, discard, restore and confirmation protections remain in the budgeting workflows. Navigation itself neither saves to the database nor confirms a decision. Save/download is still needed to retain work after the session ends.

Ordinary historical comparison is deterministic. The previous automatic model call on Compare tender pricing has been removed; optional AI explanation requires a separate button and uses the application's configured credentials without displaying them. No paid model evaluation was run.

## Available behaviour and honest boundaries

Tracks 1 and 2 retain their six-screen and three-screen journeys. Track 3 retains standalone verified schedule comparison, role matching, findings, clarification questions and workbook export. Track 4 retains its historical comparison, source/assumption views, officer review and export; it explicitly states that direct like-for-like cross-tenderer comparison is not yet available.

No live Track 1/2 project is selectable as a tender baseline. Existing standalone inputs and labelled synthetic examples are used for this milestone. Do not represent an uploaded approved label or an officer checkbox as authenticated management approval.

## Verification

Focused combined regression: **75 passed in 160.67 seconds**. This includes all four entry points, two activity choices, Back/Change activity, unsubmitted draft retention, separate workflow state, unchanged budgeting journeys, Agent 2 service checks and a complete synthetic tender calculation/export path. A model-client guard verifies that configured credentials do not cause a paid call during ordinary navigation or calculations.

The full combined regression passed **295 tests in 297.81 seconds**. A final **35 affected checks passed in 53.94 seconds** after the restored-input reset and checkbox-retention checks. Browser observations and preservation audit are recorded in VALIDATION.md and the latest HANDOVER.md entry. Earlier validation entries describe prior releases and should not be confused with a complete operational integration claim.

## Carried limitations and next work

1. Track 3's existing row adapter loses component adjustments, PWM detail and important document identity/approval metadata. It uses its own float totals and title-based grouping. Unit interpretation, supplied-total reconciliation and baseline fingerprints need correction before trusted live-budget transfer. This increment discloses the limitation rather than adding a lossy handoff.
2. Track 4 is primarily historical benchmarking. Its hard-coded wage-index/scenario treatment, insufficient-evidence aggregate behaviour, dataset fingerprinting and policy-source verification still need the integration-assessment fixes. Its existing calculation services are preserved for the demonstration, not endorsed as operational market rules.
3. Track 2 still needs separation of original arithmetic discrepancies from intentional revised-cost variance. Worksheet selection, secondary editor fields and reuse of the cleaner annual-increase control are follow-up work.
4. No Track 5 maintenance workflow is implemented. Candidate records need source review, intended-use approval, versioning and rollback before they become benchmark evidence. Uploading any proposal/submission does not publish it as historical evidence.
5. The v2 workbook is not imported or activated. Preserve source values, synthetic fills, unknown award status and synthetic calendar dates during its separate validation. Do not manufacture metadata to satisfy current schemas.
6. XLSX works in the current development environment. Older XLS requires an additional reader; the optional Node template builder also needs its external package. No new dependency installation or production hosting validation is claimed.
7. Browser-session drafts are not durable server saves for tender comparisons. Their existing JSON project download/resume remains the persistence mechanism. Raw tender-file immutability and owned revision storage remain future handoff work.

The next integration increment should agree approval authority and Track 4 scope, add a lossless versioned cost-document adapter and frozen baseline snapshots, and establish one versioned submission interpretation for both tender views. Shared-data activation remains a separately approved step.
