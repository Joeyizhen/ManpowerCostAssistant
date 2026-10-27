# Collaboration guide

The local integration/sprint2 branch composes the current Agent 1 checkpoint and Agent 2 source without changing main or either remote branch. Both budgeting workflows and the two standalone tender-review workflows are available. Trusted budget/submission transfers, shared-data activation and Track 5 remain separate work. See SPRINT2_INTEGRATION.md for verification and limitations.

## Ownership across five tracks

| Owner | Agent | Tracks |
|---|---|---|
| Project owner | Agent 1: Manpower Budget Planning | Track 1 — Build New Plan; Track 2 — Review Proposed Plan |
| Teammate | Agent 2: Tender Review | Track 3 — Compare Against Approved Budget; Track 4 — Review and Compare Tenderer Proposals; Track 5 — Maintain Historical Manpower Database |

`main` is the shared reviewed baseline. The owner's working branch is `feature/agent1`; the teammate creates `feature/agent2` from `origin/main` after the first authorised push. One branch per agent is sufficient now.

## Existing modules and future placement

| Area | Current modules | Coordination |
|---|---|---|
| Track 1 UI and controller | `app.py`, `hybrid_inputs.py`, `journey_inputs.py` | Agent 1 owns its flow; agree changes to entry navigation before editing |
| Agent 1 interpretation | `services/agent.py`, `journey.py`, `hybrid.py` | Preserve explicit human confirmations and bounded tool/API behaviour |
| Existing project contracts | `services/models.py` | Shared: preserve saved-project compatibility and distinguish unknown, zero and excluded |
| Cross-agent handoff | `services/integration_contracts.py`, `contracts/` | Shared: version and review changes; do not repurpose internal `Plan` as a tender submission |
| Arithmetic and export | `services/calculations.py`, `export.py` | Shared: retain cent rounding, annual/base/option reconciliation and source attribution |
| Retrieval and title context | `services/evidence.py`, `role_reference.py`, `data/` | Shared: synthetic fixtures only; reviewed titles are not validated prices |
| Validation and storage | `services/workflow.py`, `storage.py`, `uploads.py` | Shared: owner isolation, revision conflicts and approval invalidation must remain tested |
| Agent 2 Track 3 | `services/agent2/track3.py`, `agent2_views.py`, `tests/test_agent2_track3.py` | Teammate-owned; preserve deterministic arithmetic, source provenance and decision boundaries |
| Agent 2 Track 4 | `services/agent2/track4.py`, `agent2_track4_views.py` | Historical benchmarking prototype; direct cross-tenderer comparison remains incomplete |
| Future Track 5 | Planned maintenance workflow | Require intended-use approval, source provenance and versioning before publication |

Add focused tests under `tests/` and documentation under `docs/` for each increment. Coordinate tests/fixtures shared across both agents. Track 3 and Track 4 keep separate comparison states and remain distinct from future Track 5 maintenance permissions; Agent 1's `final` confirmation is not approval of a tender or import.

## Work and pull requests

Before editing a shared module, agree who owns that change and identify its interface impact. Prefer adding agent-specific modules around existing models rather than rewriting working Track 1 code. Each developer maintains tests/docs for their own work; shared changes receive the other person's review through a pull request.

After local changes pass the checks in the README:

```powershell
git status
git add -- <reviewed-files>
git diff --cached --stat
uv run python -m scripts.audit_shareable
git commit -m "Describe the tested increment"
# After publication is authorised, push only your own working branch:
git push -u origin feature/agent1
# Teammate uses: git push -u origin feature/agent2
```

Open a PR from the working branch into `main`; include concrete behaviour, tests, contract/schema changes, limitations and synthetic-data status. Ask the other person to review shared changes. Merge only a tested increment; keep `main` runnable. GitHub branch protection and PR settings have not been configured by this local preparation task.

## Incorporate reviewed updates

Commit your work first, then regularly merge the latest baseline into your own branch:

```powershell
git fetch origin
git switch feature/agent1
git merge origin/main
# Teammate performs the same operation on feature/agent2.
```

For conflicts, inspect both changes, coordinate with the other owner, preserve both intended behaviours, edit the conflict, run affected tests, then `git add` and complete the merge. Do not use blanket ours/theirs selection, discard the other person's work, reset a shared branch, force-push or rewrite published history. If a shared schema changes, agree the version/migration and update both sets of tests before merging.

## Publication status and historical first-push procedure

Baseline `02cbfc9` was published to the private repository on `main` and `feature/agent1` on 17 October 2026. The teammate is developing Agent 2 on `feature/agent2`. The following first-push/invitation procedure is retained as history; do not repeat it automatically. New pushes, invitations and deployment require their own instruction.

### Historical preparation instructions

The intended repository is `https://github.com/Joeyizhen/ManpowerCostAssistant.git`. Git inspection and an ignored bare audit clone found no remote refs/history and a clone HEAD of `main`. An unauthenticated REST metadata lookup was unavailable; repository visibility, collaborator permissions, branch protection and push rights are not verified. No remote was modified.

After the owner explicitly authorises the first push:

1. Run `git fetch origin` and inspect refs again. If remote history appeared since this preparation, stop and reconcile it; do not overwrite or force-push.
2. Verify the local `main` commit, current checks and staged/tracked privacy audit.
3. Push the prepared baseline and owner's branch:

```powershell
git push -u origin main
git push -u origin feature/agent1
```

4. The owner uses GitHub repository Settings → Collaborators/Manage access to invite the teammate's confirmed GitHub account. No invitation has been sent; do not guess the account or change visibility.
5. After access is accepted, the teammate clones and creates their branch:

```powershell
git clone https://github.com/Joeyizhen/ManpowerCostAssistant.git
cd ManpowerCostAssistant
git switch -c feature/agent2 origin/main
uv sync --frozen --python 3.14
Copy-Item .env.example .env
uv run pytest -q
```

They set their own Git identity and any API credentials privately. Agent 2 can validate the synthetic approved-budget example without a key or live API call. Both developers keep private databases/uploads/outputs outside tracking. Hosting, collaborator invitation, historical import and paid evaluations each remain separate authorised activities.
