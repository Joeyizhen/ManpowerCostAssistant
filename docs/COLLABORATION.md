# Collaboration guide

## Branches and team responsibilities

`main` contains the shared runnable Sprint 2 application. Agent 1 covers Tracks 1/2; Agent 2 covers Tracks 3/4, with Track 5 planned. Track numbers and agent numbers are different: Agent 1 Track 2 is proposal review; `feature/agent2` contains the tender-evaluation contribution. Team responsibilities are listed in the README.

The combined application was prepared on `codex/consolidate-application` from the preserved `integration/sprint2` work and a merge of the teammate branch, then published to `main` through PR #1 at the team's request. Ongoing changes should use feature branches and PRs. Do not force-push developer branches or overwrite either person's work. Keep the combined `app.py` entrypoint when changing navigation.

## Review and publication

Each increment should include relevant tests, documentation and source/contract limitations. Shared changes to models, arithmetic, evidence, persistence or integration contracts need peer review. Agree interface impact through the PR; do not replace a whole shared module merely to resolve a conflict.

Before integrating, checkpoint tracked and untracked work and preserve useful private runtime data separately. Fetch remote refs, inspect actual history and resolve by intended behaviour. No destructive reset, clean or blanket ours/theirs resolution.

Stage reviewed paths deliberately, inspect the complete staged list and run `python -m scripts.audit_shareable`. That audit reads indexed blobs, so rerun it after changing the publication set. Never publish private workbooks, raw records, uploads, saved projects, credentials, local snapshots/outputs or personal handoffs.

Run combined offline checks and verify a clean package/checkout can exercise both agents. Push the working branch without force, open a PR into `main`, report actual results and obtain teammate review. Repository branch protection is not assumed; the PR convention still applies.

## Getting the whole app

For a fresh installation:

```powershell
git clone https://github.com/Joeyizhen/ManpowerCostAssistant.git
cd ManpowerCostAssistant
uv sync --frozen --python 3.14
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

For an existing installation, commit/checkpoint your own work before switching to `main`, then update with `git pull --ff-only origin main`. Preserve private configuration. Both activities and the Site Xtown example are included in `main`; there is no need to select a separate agent branch to run the complete app.

A clean clone uses labelled synthetic data; no private workbook/database is needed to open both activities. Optional model credentials are configured privately per installation. See [DEPLOYMENT.md](../DEPLOYMENT.md) for persistence/authentication and data provisioning.

## Incorporating later changes

Fetch first, inspect divergence, then merge reviewed `origin/main` updates into your own working branch. Resolve shared behaviour carefully and run affected checks before opening the next PR. Preserve original titles, units, source evidence, saved-project compatibility, deterministic totals and approval invalidation.

Budget approval, trusted cross-agent transfer, source-data maintenance and hosted deployment are distinct workflows. Publishing code does not approve a budget, activate a new source or deploy a hosted service. Collaborator invitations and repository visibility changes require their own instructions.

Exact source commits and compatibility decisions are recorded in [SPRINT2_INTEGRATION.md](SPRINT2_INTEGRATION.md).
