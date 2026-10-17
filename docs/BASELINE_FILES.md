# Reviewed baseline contents

## Intended tracked files

The reviewed initial candidate set contains **65 files**. No remaining-track implementation is added.

- Existing application: `app.py`, `hybrid_inputs.py`, `journey_inputs.py`, `services/`, tests and development scripts. Track 1 implementation remains in place.
- Reproducible setup: `pyproject.toml`, `uv.lock`, hashed runtime `requirements.txt`, Dockerfile, safe blank environment/Streamlit examples, public theme settings, ignore/line-ending rules and setup/deployment instructions.
- Shared collaboration contracts: `services/integration_contracts.py`, two JSON schemas, deterministic fixture generator and an explicitly synthetic approved-budget example. No Agent 2 comparison/import logic.
- Synthetic evidence: existing invented schedules and reviewed role-title context. No source workbooks or validated real tender prices.
- Sanitised documentation in `docs/`, `evaluation/PLAN.md`, `evaluation/TOOLS.md`, reserved/development case definitions and current data requirements.

## Excluded and preserved locally

API keys/credentials, `.env` files, real Streamlit secrets, raw BCT/real tender documents/records, local databases, uploads, outputs/private traces/screenshots/workbooks, environments/caches, logs, temporary files, notebooks and credential containers. Root private build brief/handover/implementation/validation notes and historical development reviews are ignored; shareable replacements are linked from README. Private originals of rewritten setup/protocol documents were copied to ignored local storage before editing.

The previous prototype and unrelated projects lie outside this root and are untouched. They are not copied into this repository. Git metadata, author settings and audit clones are not staged application files. The bare remote audit clone is in ignored local storage.

## Verification

Before the baseline commit, review `git diff --cached --stat` and run `python -m scripts.audit_shareable`. It scans the complete index, checks representative exclusions and labels, and reports only paths/rule failures rather than sensitive contents. The initial commit is prepared only after successful checks, confirmed repository-local author identity and verification of compatible remote history. Publication remains unauthorised until explicitly requested.

Initial preparation result: 65 indexed files, 23 exclusion probes, zero audit findings; 105 automated tests passed. Safe configuration examples contain blank credentials. No application source/controller/calculation behaviour was changed by this collaboration preparation.
