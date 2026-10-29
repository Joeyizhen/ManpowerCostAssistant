# Collaboration guide

## Branches and ownership

`main` is the reviewed shared baseline. The project owner works on Agent 1 (Tracks 1/2); the teammate works on Agent 2 (Tracks 3/4, with Track 5 planned). Track numbers and agent numbers are different: Agent 1 Track 2 is proposal review; the teammate's `feature/agent2` contains tender evaluation.

The combined application is prepared on `codex/consolidate-application` from the preserved `integration/sprint2` work and a merge of the teammate branch. Review its PR into `main`. Do not force-push developer branches or overwrite either person's work. Keep the combined `app.py` entrypoint when changing navigation.

## Review and publication

Each increment should include relevant tests, documentation and source/contract limitations. Shared changes to models, arithmetic, evidence, persistence or integration contracts need peer review. Agree interface impact through the PR; do not replace a whole shared module merely to resolve a conflict.

Before integrating, checkpoint tracked and untracked work and preserve useful private runtime data separately. Fetch remote refs, inspect actual history and resolve by intended behaviour. No destructive reset, clean or blanket ours/theirs resolution.

Stage reviewed paths deliberately, inspect the complete staged list and run `python -m scripts.audit_shareable`. That audit reads indexed blobs, so rerun it after changing the publication set. Never publish private workbooks, raw records, uploads, saved projects, credentials, local snapshots/outputs or personal handoffs.

Run combined offline checks and verify a clean package/checkout can exercise both agents. Push the working branch without force, open a PR into `main`, report actual results and obtain teammate review. Repository branch protection is not assumed; the PR convention still applies.

## Getting the whole app

Before the consolidation PR is merged:

```powershell
git fetch origin
git switch -c review/consolidated-app --track origin/codex/consolidate-application
uv sync --frozen --python 3.14
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

Use a fresh checkout or commit/checkpoint your own work before switching. Preserve private configuration. After the reviewed PR is merged, teams can clone/update `main` instead.

A clean clone uses labelled synthetic data; no private workbook/database is needed to open both activities. Optional model credentials are configured privately per installation. See [DEPLOYMENT.md](../DEPLOYMENT.md) for persistence/authentication and data provisioning.

## Incorporating later changes

Fetch first, inspect divergence, then merge reviewed `origin/main` updates into your own working branch. Resolve shared behaviour carefully and run affected checks before opening the next PR. Preserve original titles, units, source evidence, saved-project compatibility, deterministic totals and approval invalidation.

Budget approval, trusted cross-agent transfer, source-data maintenance and hosted deployment are distinct workflows. Publishing code does not approve a budget, activate a new source or deploy a hosted service. Collaborator invitations and repository visibility changes require their own instructions.

Exact source commits and compatibility decisions are recorded in [SPRINT2_INTEGRATION.md](SPRINT2_INTEGRATION.md).
