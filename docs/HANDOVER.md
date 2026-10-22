# Collaboration baseline handover — 17 October 2026

This is a sanitised shareable note. Original private development handovers, local officer projects, source documents and evaluation traces remain locally preserved and excluded from tracking.

## Existing Track 1 checkpoint

The latest implementation increment added common optional roles and current/proposed manpower, explicit zero exclusions, FTE/unit guards, optional current deployment, copy-current/mark-zero actions, saved-project compatibility and comparison information in Excel. Pasted-list UI was removed; its parser remains for legacy development scripts. Exact supported FM aliases retain the original title. Calculations/retrieval/workflow/storage/export remain shared services.

The checkpoint passed **94 automated checks** before collaboration preparation. A zero-call replay reconciled the preserved complete synthetic budget and workbook. Existing published test notes are development evidence, not a held-out score. No additional paid live test is authorised for collaboration preparation, and no existing API allowance is reset.

## Collaboration additions

- Local repository intended for `main` baseline and owner's `feature/agent1`; teammate creates `feature/agent2` after the first authorised push.
- [COLLABORATION.md](COLLABORATION.md) assigns all five tracks, module ownership, PR/review/merge rules, shared-file coordination and setup/invitation steps.
- [INTERFACES.md](INTERFACES.md), `services/integration_contracts.py` and `contracts/` define version 1.0 budget/tender transfer documents, without implementing the remaining tracks.
- `data/sample/integration/approved_budget.synthetic.json` is an invented, explicitly synthetic approved-budget development example, not a real approval or saved officer plan.
- `scripts/audit_shareable.py` audits the indexed file set, exclusions, credential/private-path patterns and fixture provenance without echoing secret values. `.gitignore` also excludes private original notes, raw documents/records and runtime artifacts. Original setup/protocol files were backed up in ignored local storage before sanitisation.

## Agent 2 Track 3 continuation — 18 October 2026

Track 3 is now implemented as a development prototype in `agent2_views.py` and `services/agent2/track3.py`, with focused regression tests. It supports approved-budget confirmation, multiple tenderers, verified editable schedules, role matching, deterministic comparisons/findings/questions, officer review fields, save/resume and traceable Excel export. Upload validation blocks missing values/years, duplicate role-year rows, incompatible quantity units, unsupported currencies and non-monthly pricing. Excel parsing combines recognised schedule worksheets and retains filename, sheet and row references.

This does not establish production readiness. Approval authenticity, subtotal/declared-total reconciliation, richer base/option analysis, accepted-exception history, reviewer timestamps, access control and PDF/Word extraction remain open work. Track 4 now has a synthetic-data historical-comparison prototype; Track 5 database administration, validation, versioning and access controls are not implemented.

## Known incomplete work and failures

Six visible steps, consistent Back/Continue/progress, compact rate/future-change controls, a monthly role-cost column, observed slider band and consolidation of findings/full-budget/export are **not finished**. Existing grouped inputs/legacy internal stages remain. Some numeric missing cells display `None`, and narrow tables can require horizontal scrolling. Step fields reserved in models are not implemented navigation.

New current/proposed/zero context and prompt behaviour have not been tested with a real LLM. Earlier live cases apply to earlier builds. Native Excel rendering/recalculation, shared-host OIDC/PostgreSQL, public deployment and real market evidence remain unverified. No current automated Track 1 calculation failure was known at the saved checkpoint; [VALIDATION.md](VALIDATION.md) records collaboration check results separately.

Fixed checkpoint defects included a missing singular FM alias and pandas blank/NaN handling in copy-current/mark-zero. These regressions remain tested. DTO/schema validation is not proof of human approval or a secure production handoff; a trusted-store adapter/access review is still required before real integration.

## Remote and publication status

Git read inspection and an ignored bare audit clone found an empty repository with clone HEAD `main`; there was no remote history/file tree to merge at inspection. An unauthenticated REST metadata lookup was unavailable. Repository visibility, push rights, branch protection and invitation rights were not tested by a push or remote configuration change.

No GitHub push, collaborator invitation, hosting/deployment, raw BCT access, historical import or previous-prototype/unrelated-project modification occurred. Personal Git author details are repository-local configuration/commit metadata, not application configuration or fixtures.

## Exact next steps

1. Review the local baseline commit, [BASELINE_FILES.md](BASELINE_FILES.md), checks and [COLLABORATION.md](COLLABORATION.md). Keep private sources/data/secrets local.
2. Await explicit first-push instruction. Re-fetch before pushing; if remote history appeared, reconcile rather than force-push.
3. After authorised baseline/branch push and owner-sent invitation, teammate clones and creates `feature/agent2` from `origin/main`, installs locked dependencies and runs synthetic tests without a key.
4. Agent 2 can start against the versioned synthetic budget fixture. Coordinate changes to models/calculations/evidence/workflow/storage/navigation/export through PRs; preserve Track 1 tests and do not infer tender approval from a budget flag.
5. Resume the broader Track 1 redesign or new bounded live tests only under a separate instruction. Keep all earlier usage ceilings/counters intact.
