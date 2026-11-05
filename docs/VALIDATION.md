# Consolidation validation — 30 October 2026

## Final combined checks

The publishable app was exported from the reviewed Git index (161 files), without private source workbooks, saved projects, uploads, secrets, reference activation pointers or personal handoffs. The clean package used a separate environment with fresh frozen-lockfile downloads on Windows / Python 3.14.2. External network/model connections were blocked during tests; Streamlit's internal localhost connections remained available.

| Check | Result |
|---|---|
| Full offline regression on final clean-package code | **402 passed, 3 skipped in 270.97s (0:04:30)** |
| Focused verification of the final pricing/fixture fixes | 22 passed, 1 skipped in 30.14s |
| Earlier combined-agent/reference integration checks | 71 passed in 47.45s |
| Fresh locked dependency installation | 68 packages; imports and installed-package compatibility passed |
| Runtime requirements versus frozen lock export | Exact match, ignoring generated comments |
| Isolated clean-package Streamlit startup | Health endpoint HTTP 200; model configuration disabled |
| Lint, Python compilation and Git whitespace | Passed |
| Complete staged privacy audit | 161 indexed files, 23 exclusion probes, zero findings |

The three intentional skips require private local officer snapshots. Those files do not belong in a shareable checkout. Synthetic and invented prepared-workbook tests cover the public route without substituting private records.

## Behaviour exercised

- Both activities and all four workflow entrypoints, Back/Change activity, separate draft state and ordinary calculation without model calls.
- Track 1's five visible screens, missing/zero quantities, retained rates, illustrative allowances, general/PWM separation, confirmation invalidation and unchanged-confirmation navigation.
- Upload-first proposal intake, authored templates, original/revised figures, shared review controls, material input gaps, save/reopen and exports.
- Agent 2 flat/composition workbook parsing, contract-year completeness, headcount/FTE checks, role matching/confirmation, insufficient evidence, deterministic comparison and workbook/project download/resume.
- Active prepared-role choices versus synthetic fallback categories, unchanged shared synthetic population and source boundaries. Changed tender role matches require fresh confirmation.
- Versioned integration contracts and synthetic handoff reconciliation. Schema validity remains separate from authenticated human approval.

The initial full run found a stale synthetic description and repeated individual reason editors after applying a shared pricing basis. The labelled fixture description was refreshed without changing totals or schemas. The UI now hides redundant editors while retaining stored reasons/drafts; confirmation and invalidation services remain authoritative. Both fixes passed focused checks before this final full run.

## Preservation and privacy

A verified local recovery checkpoint preserved tracked/untracked working files, useful private runtime/evidence files, a consistent saved-project database snapshot and Git history before integration. Existing saved project/revision rows, private configuration and reference files were compared read-only. Additional saves in the live session were retained, rather than rolled back. The running user app was not restarted.

The staged audit scans exact indexed blobs and checks private exclusions, secret/private-path patterns, synthetic provenance and authored workbook structure. Manual review removed private source quotations and saved identifiers from shareable methodology notes. Private originals, logs and preservation reports remain under ignored local storage.

The current local v3 reference activation remains unchanged. The separately authored synthetic integration fixture was regenerated only to match its current demo description. No source workbook cleaning/import, reference population regeneration or v2 activation was performed.

## Practical limits

Offline/mocked tests do not establish live assistant reasoning, real-world market validity or current policy applicability. The historical demo's wage/scenario constants are retained prototype logic, not newly verified legal/economic guidance. No paid model evaluation was run.

No hosted deployment, real PostgreSQL/OIDC acceptance, Docker build or native Excel recalculation is claimed. Other declared Python versions and operating systems remain unverified. Trusted live-budget transfer, authenticated approval handoff, dedicated cross-tenderer comparison and Track 5 are incomplete.

Only Deployment has an isolated before/after profile: 26.01s to 1.67s. General step-switching lag remains unresolved and is not certified by regression tests. Publication readiness is separate from operational deployment acceptance.

See [the consolidation report](SPRINT2_INTEGRATION.md), [setup/deployment](../DEPLOYMENT.md) and [reference provisioning](PREPARED_REFERENCES.md). Detailed historical test logs and personal handoffs are local evidence; they are not deployment assets.
