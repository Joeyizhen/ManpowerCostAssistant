# AI-Powered FM Manpower Cost Assistant

A university capstone application for FM manpower budgeting and tender review. One Streamlit entrypoint, `app.py`, provides both agents and four workflows. Python calculates costs; optional AI guidance explains inputs and findings. Saving, accepting suggestions and confirming a budget are separate actions.

| Activity | Agent and workflows |
|---|---|
| Manpower budgeting | Agent 1: build a new budget (Track 1); review an uploaded proposal (Track 2) |
| Tender evaluation | Agent 2: compare submissions against an approved budget (Track 3); review tender pricing against historical references (Track 4) |

Track 5 historical-data maintenance is planned. Trusted transfer of a live budgeting project into tender review and dedicated like-for-like cross-tenderer comparison are incomplete. The app supports officer judgement; it does not select a winning tenderer or authenticate management approval.

## Run the complete app

Python 3.14 is the tested development version. The declared range is 3.11–3.14; other versions have not been verified. Select the consolidated branch from the PR, or a reviewed `main` containing it, then run:

```powershell
git clone --branch codex/consolidate-application https://github.com/Joeyizhen/ManpowerCostAssistant.git
cd ManpowerCostAssistant
uv sync --frozen --python 3.14
Copy-Item .env.example .env
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8511/`. Both activities start from this app. Preserve an existing private `.env` rather than copying over it. Without `uv`, install the locked runtime requirements into a virtual environment; see [setup and deployment](DEPLOYMENT.md).

No API key is needed for labelled examples, data entry, deterministic checks, calculations or exports. For optional live guidance, privately configure both `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env` or server-side Streamlit secrets. No model is silently selected. AI actions require an explicit request and can incur provider charges. Mocked/offline tests do not establish live assistant reliability.

## Current workflows

**Build a new budget:** Project → Deployment → Starting rates → Annual changes → Budget. New deployment uses whole-person headcount, shows current/proposed quantities and retains original role titles. Saved earlier units and financial decisions remain readable. AI discussion and officer confirmation are separate. Editable role-specific illustrative ranges fill genuinely missing rates; they are authored assumptions, not market evidence. Existing and explicitly cleared rates are retained.

General annual changes use a qualified reference when available or an explicit officer assumption. PWM treats a confirmed eligible salary component separately, with known worker quantities, category, dates and unpublished-period decisions. The same salary component cannot also receive a general increase. The retained policy catalogue is dated; it does not establish current applicability for every worker.

Results have Budget, Scenarios, Manpower, and Assumptions & sources tabs and evidence exports. Year 0 values current staffing at selected starting rates; it is not actual previous-contract spend. Average annual cost includes all base and option years. Headcount, general increases, PWM and other adjustments remain separate. See [cost comparison](docs/HEADCOUNT_COST_COMPARISON.md).

**Review a proposed budget:** upload first, check captured project/manpower figures, then complete gaps through the shared deployment/rates/annual-change/budget screens. CSV, XLSX, text PDF, DOCX and text extraction require officer checking; scanned PDFs have no OCR. Exact uploads and original figures stay separate from accepted revisions. [Blank and ordinary mixed-manpower templates](data/templates/) are included. The deliberate error example is retained only for regression. See [upload-first review](docs/TRACK2_UPLOAD_FIRST.md).

**Compare against an approved budget:** confirm the budget reference, read tenderer schedules, verify values and role matches, calculate variances, record clarification decisions and export. Project JSON download/resume retains tender-review work. Approval metadata is officer-confirmed, rather than a trusted transfer from Agent 1.

**Review tender pricing:** verify submissions/role matches, choose historical comparison context, inspect pricing findings, record officer decisions and export. Insufficient evidence must remain visible. Optional AI explanation is separate from ordinary calculation. See [the consolidation report](docs/SPRINT2_INTEGRATION.md) for teammate history and carried limitations.

## Reference data and persistence

A clean clone uses explicitly labelled synthetic demonstration records. These are invented examples, never verified tender prices. Role-title context alone does not establish a comparable rate. The Site Xtown loader and ordinary proposal sample work without the owner's private saved-project database or source workbook. Example preparation is not final officer approval.

Private prepared snapshots can be provisioned separately under `local_data/references` or a private `MANPOWER_REFERENCE_DIR`. No prepared workbook or raw records are shipped. The owner's local v3 activation is unchanged by consolidation; v2 is not activated. Do not regenerate/import sources to make a clone run. See [reference provisioning](docs/PREPARED_REFERENCES.md).

Budgeting projects and original uploads use `local_data/plans.db` by default. Back up this private storage. Agent 2 uses JSON download/resume; browser drafts alone are not durable. Shared hosting requires PostgreSQL, OIDC and an access list; that hosted combination remains unverified. [DEPLOYMENT.md](DEPLOYMENT.md) covers packaging, persistence and acceptance checks. GitHub publication does not deploy a service.

## Checks without paid calls

```powershell
uv run pytest -q
uv run ruff check .
uv run python -m compileall -q app.py activity_nav.py agent2_views.py agent2_track4_views.py services scripts tests
uv run python -m scripts.evaluate_live --split development --limit 3
```

The evaluation command is a zero-call dry run unless `--allow-live` is explicitly supplied. Do not add that flag for regression. On Windows, `scripts/check.ps1` uses unique project-local test storage. Latest combined results and limits are in [VALIDATION.md](docs/VALIDATION.md).

After deliberately staging reviewed files, run `uv run python -m scripts.audit_shareable`. It audits the complete index, including labelled data/templates and credential/private-path checks. Secrets, source workbooks, raw records, saved projects, uploads, outputs, environments and personal handoffs stay private.

## Collaboration and remaining work

Use feature/consolidation branches and a reviewed PR into `main`; preserve teammate history and never force-push. See [collaboration](docs/COLLABORATION.md), [project write-up](docs/PROJECT_BRIEF.md), [contracts](docs/INTERFACES.md) and [release checkpoint](docs/HANDOVER.md).

Only Deployment responsiveness has been profiled and improved: 26.01s to 1.67s in the same isolated active-reference profile. General step-switching lag is unresolved and has not been comprehensively timed. See [performance scope](docs/DEPLOYMENT_RESPONSIVENESS.md). Live assistant evaluation, trusted approval transfer, native Excel recalculation and hosted database/identity operation remain separate work.
