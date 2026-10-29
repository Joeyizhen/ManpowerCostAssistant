# Shareable release checkpoint — 30 October 2026

The complete app is consolidated from `integration/sprint2` and the teammate's `feature/agent2` branch through a reviewable branch/PR. See [SPRINT2_INTEGRATION.md](SPRINT2_INTEGRATION.md) for exact source commits, and [VALIDATION.md](VALIDATION.md) for checks.

## Behaviour to retain

- Two activities expose Agent 1 budgeting/proposal review and Agent 2 tender evaluation from `app.py`.
- Track 1 has five visible screens. Legacy saved navigation/units, explicit missing/zero values, original role titles and confirmation dependencies remain supported.
- Track 2 starts with upload and shares the budgeting screens while preserving original files/figures separately from accepted revisions.
- Starting-rate sliders use honestly labelled authored illustrative assumptions where comparable source recommendations are unavailable.
- General increases and eligible salary-component PWM remain separate. Preserve published horizons, calendar-month treatment and explicit officer decisions; never apply both increases to the same salary component.
- Year 0 is current headcount at selected starting rates, not evidenced historic spend. Cost attribution and exports preserve reconciled totals.
- Agent 2's latest parsing/validation/review work must coexist with the combined activity menu and shared reference boundaries.
- Save, preview, accepting assistant changes, input confirmation and final approval remain distinct.

## Boundaries

Private saved projects, uploads, sources, databases, evidence logs and personal handoffs stay outside Git. The current local v3 activation is preserved. Importing/cleaning or activating v2 is separate work.

Do not reset current app sessions, overwrite saved examples from their fixtures, use destructive Git operations, force-push teammate branches or perform paid/hosted actions without their own scope.

## Remaining readiness limits

Trusted live-budget transfer, authenticated approval handoff, dedicated cross-tenderer comparison and Track 5 remain incomplete. Real hosted PostgreSQL/OIDC, native Excel recalculation and live assistant quality are unverified.

Only Deployment loading was profiled/optimised (26.01s to 1.67s in the same isolated active-reference profile). General step-switching lag is outstanding. Publication readiness is distinct from deployment acceptance and from a broad performance fix.
