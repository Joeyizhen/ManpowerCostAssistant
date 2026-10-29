# Combined application — 30 October 2026

## Source history

The consolidation branch is `codex/consolidate-application`, based on local `integration/sprint2` at `b743d98`. Local budgeting/proposal refinements, templates, services, tests and documentation were preserved before integration.

The GitHub fetch found the teammate's `feature/agent2` at `c8e42e2`. Its three new commits are:

| Commit | Teammate change |
|---|---|
| `f1f16f0` | Improve Agent 2 Track 3/4 validation workflows |
| `3eb022c` | Show only Agent 2 tracks on its landing page |
| `c8e42e2` | Align Track 4 landing button style |

Earlier teammate commits `88248da` and `a7923f3` remain ancestors of the combined branch. The user referred to this teammate contribution as “track 2”; the branch/entrypoints establish that it is Agent 2, whose implemented workflows are Tracks 3/4. Agent 1's Track 2 is still proposal review.

The consolidation preserves both source histories and is published to the default `main` branch through PR #1 at the team's request. A normal clone now contains both activities and the Site Xtown example. Neither developer branch is force-pushed or overwritten; ongoing changes continue through the branch/PR workflow.

## Integrated behaviour

One `app.py` exposes Manpower budgeting and Tender evaluation, with all four workflows. Agent 1 retains five visible budget screens and upload-first proposal review, original/revised figures, retained saved inputs, deterministic calculations, evidence exports and explicit confirmations.

The teammate increment adds composition-of-rates workbook parsing across year tabs/site blocks, upload feedback, correction visibility, up to five tenderers, removal/replacement controls, reviewable role choices, an explicit Track 4 role-confirmation action and clearer historical-coverage handling. Supported extraction still needs officer verification. Legacy XLS requires its optional reader; XLSX/CSV/JSON are the normal tender-schedule route. PDF/Word tender schedule extraction is not implemented.

Ordinary calculations/navigation make no model call. Both tender views offer a separate explicit AI explanation using server-side app settings; a failed explanation does not change calculations or automatically retry.

## Conflict and compatibility decisions

- Retain the combined activity menu. The teammate's Agent-2-only landing page suits its branch but would hide budgeting/proposal review in the shared app.
- Retain the shared evidence loader, saved canonical role names, private snapshot selection and original synthetic population. Do not remap Admin Executive decisions or manufacture new global benchmark records from other roles. Extra tender-review titles remain selectable without a promised benchmark.
- Keep explicit synthetic labels on the teammate's expanded historical demonstration. These examples are not validated market data.
- Preserve missing-year checks for each role, separate headcount/FTE, known quantities with missing rates and the rule that source text cannot override a fractional-headcount blocker. Do not fill omissions with zero or silently convert shared allocations to FTE.
- Prepared-source calendar years remain unknown. New synthetic year filters do not become real calendar evidence, and hard-coded demo aliases cannot override the prepared source's reviewed mapping.
- Compare historical aggregates only where evidence supports them. The teammate's 80% comparable-cost threshold is a prototype review convention, not an award or market-validity rule.
- Keep input registration and separate workflow state across activity changes. Saving, accepting AI changes, confirming inputs and approving a final budget remain distinct.

## Packaging and privacy

The complete publishable set includes UI/service modules, tests, contracts, dependency manifests, lockfile, runtime assets and three authored proposal templates. A clean installation uses labelled synthetic references and example loaders without the owner's private sources/database.

Private workbooks/raw records, activation pointers, saved projects, uploads, credentials, evidence outputs and personal handoffs stay local. Exact private quotations and saved-project identifiers were removed from shareable methodology notes; original local evidence was preserved before editing. Source import/cleaning is separate, v3 remains the local active source, and v2 is not activated.

See [README](../README.md), [setup/deployment](../DEPLOYMENT.md), [reference provisioning](PREPARED_REFERENCES.md) and [validation](VALIDATION.md).

## Remaining limits

Trusted live-budget transfer and authenticated approval handoff are incomplete. Track 4 primarily compares against historical references; dedicated like-for-like cross-tenderer comparison and Track 5 maintenance remain incomplete. Agent 2 uses project JSON download/resume, rather than Agent 1's owned revision store.

The historical demonstration's wage-index/scenario constants and policy-source claims are retained prototype logic, not newly verified economic/legal guidance. Prepared-source operational comparability, actual pricing years and award outcomes remain qualified.

Only Deployment loading has an isolated 26.01s to 1.67s improvement. Other step-switching lag is unresolved. Offline regression does not certify live-model quality, native Excel recalculation or real hosted PostgreSQL/OIDC operation. No paid calls or hosted deployment are part of consolidation.
