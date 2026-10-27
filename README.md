# AI-Powered FM Manpower Cost Assistant

Local Sprint 2 application with two activities: manpower budgeting and tender evaluation. Tracks 1/2 retain their current workflows; Tracks 3/4 run independently with labelled sample references. Direct budget transfer, shared-reference activation and Track 5 maintenance remain unavailable. The integration branch is a local demonstration milestone, not a production release.

| Owner | Agent | Tracks |
|---|---|---|
| Project owner | Agent 1: Manpower Budget Planning | 1 — Build New Plan; 2 — Review Proposed Plan |
| Teammate | Agent 2: Tender Review | 3 — Compare Against Approved Budget; 4 — Review and Compare Tenderer Proposals; 5 — Maintain Historical Manpower Database |

See [collaboration/branches](docs/COLLABORATION.md), [interfaces and synthetic budget](docs/INTERFACES.md), [checkpoint and known issues](docs/HANDOVER.md), [project brief](docs/PROJECT_BRIEF.md) and [validation](docs/VALIDATION.md). Private original handoffs and saved officer data are retained locally and excluded from Git.

## Local setup

Use Python 3.14 for the tested environment. The dependency declaration supports 3.11–3.14, but other versions have not been verified here. With `uv` installed, run from the repository root:

```powershell
uv sync --frozen --python 3.14
Copy-Item .env.example .env
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8511/`. The preview is local to this computer and stops if its process/computer stops. Existing users can run `.venv/Scripts/python.exe` directly instead of `uv run`.

Edit `.env` privately to set `OPENAI_API_KEY` and `OPENAI_MODEL` if live guidance is required. Alternatively use a private `.streamlit/secrets.toml`, copied from its example. Never put credentials in chat, source, command-line arguments or Git. No model is silently chosen. Each developer uses their own provider access; without a key the tables and synthetic Python tests work, while live review/chat is disabled. The synthetic integration example needs no API access.

Live guidance uses the Responses API with validated tools, finite limits and no automatic retries. The preview process needs outbound provider connectivity; a sandbox-restricted launch may serve the page but block guidance. Failed turns remain available for explicit retry. Shared hosting requires server-side OIDC login, PostgreSQL and an explicit allowlist; see [DEPLOYMENT.md](DEPLOYMENT.md). Do not expose local review mode publicly. No deployment is performed here.

## Sprint 2 navigation

Start with **Manpower budgeting** or **Tender evaluation**, then choose one of the two tasks. Back returns to that activity's options; Change activity returns to the landing page. Recorded models and unfinished value inputs remain separate for each workflow in the current session. Save/download still provides persistence beyond the session, and existing project-switch protections remain.

Tender evaluation runs independently from live budgeting projects. Track 4 currently compares proposals against synthetic historical references; dedicated cross-tenderer comparison is incomplete. Historical management is marked Planned. Ordinary comparison makes no model call; optional AI explanation requires a separate explicit action. See [the integration report](docs/SPRINT2_INTEGRATION.md) for source commits, checks and carried limitations.

## Current Track 1 behaviour

Enter a proposed tender title, operating-conditions description, anticipated start as MMM YYYY, and base/option terms in years (0 for no option). Month-only starts retain an unknown exact day; the first day is a disclosed illustrative costing boundary. Indicate existing contract or new site/service. The manpower screen presents eight common optional roles and lets you add inventory/custom titles. Proposed quantity 0 excludes a role; an unanswered field is not converted to 0. Fractional staffing uses FTE; posts need a confirmed staffing conversion. Current contract deployment is optional context. Copy-current and mark-unused-zero are explicit actions. Supporting documents and duty/contractor notes are optional. The pasted-list UI has been removed.

Review my manpower plan sends the retained brief, table and supporting text to the real LLM for targeted sanity checks; it does not approve anything. Correct the plan and use the single manpower confirmation before pricing. Rates use one reference year, arithmetic-average starting points when supported, editable sliders/exact inputs and optional assumptions. Unsupported roles retain their titles and need officer rates. Pricing shows monthly role costs and observed synthetic bands. Future-price controls are compact and expandable. Findings, full-contract charts, final officer confirmation and Excel share the final screen; final approval is an explicit officer action. Editing values invalidates dependent confirmations.

The six screens separate project details, manpower inputs, assistant review, rates, future changes and full-budget/export review. Back/Continue and saved step position preserve the draft; revisions invalidate dependent decisions. The sidebar can delete a selected saved project and its revision history after a named confirmation; this cannot be undone. Missing numeric cells are blank; narrow tables can still scroll horizontally. Saved/unsaved status and Save/Discard/Keep editing protect drafts when switching projects. See [the officer-experience review](docs/OFFICER_EXPERIENCE.md). New current/proposed/zero prompt behaviour has not been rechecked live. Native Excel recalculation, shared hosting and real market validity remain unverified. These are a documented development baseline, not a completed product claim.

## Current Track 2 behaviour

Add proposed budget → check figures and assumptions → view the reviewed budget. Paste a table or description, upload CSV/XLSX/PDF/DOCX/text, or enter rows manually. Confirm the interpreted units and inclusive monthly charges before review. Unknowns remain unanswered. Original figures, supplied totals and exact uploaded evidence are retained separately from accepted revisions; proposal reviews have their own saved revisions and snapshot recovery.

The review reuses Track 1 calculations, eligible rate/annual-increase references, coverage checks and relevant PWM safeguards. Only material discrepancies require a recorded response; capability gaps remain qualifications rather than a routine questionnaire. Previewing a rate, applying changes, saving, confirming reviewed inputs and approving the final budget are separate actions. The four-tab results page compares original and reviewed EPV and provides a management report and evidence workbook. See [Track 2 implementation and limits](docs/TRACK2_IMPLEMENTATION.md).

Document extraction is conservative and requires officer checking. Scanned PDFs need manual transcription; no OCR or universal layout interpretation is claimed. Private quoted prices are proposal evidence, never new benchmark records. Live assistant review is optional and has not been evaluated with paid calls in this refinement. The v2 reference workbook remains inactive.

## Current Track 3 behaviour

Track 3 creates a tender-review project, confirms the approved-budget reference and revision, verifies multiple tenderer schedules, reviews role matches, compares full-contract and role-level costs, records officer comments/statuses, exports a traceable workbook and saves/resumes project JSON. Comparability checks block missing years, duplicate role-year rows and incompatible headcount/FTE units. Uploads must establish monthly SGD pricing; unsupported currencies and annual/daily/hourly frequencies are rejected rather than silently converted. Excel uploads inspect every worksheet containing a recognised role column and retain filename, worksheet and row provenance.

This is decision support only. Below-budget submissions produce clarification prompts rather than automatic savings or rejection conclusions, and the application does not select a tenderer. Track 3 remains a prototype: it does not authenticate signed approvals, convert currencies or pricing frequencies, extract PDF/Word tables, or establish production access controls.

## Synthetic evidence and handoff

- `data/sample/historical.json`: invented tender schedules with explicit synthetic provenance; no real BCT prices/records.
- `data/reference/role_titles.json`: reviewed title context only, with no benchmark-price eligibility implied.
- `data/sample/integration/approved_budget.synthetic.json`: invented approved-budget transfer example, with a clearly synthetic approval and no saved-project mutation. Agent 2 can develop against it independently.
- `services/integration_contracts.py` and `contracts/`: typed/versioned budget and tender-submission contracts. Shape validation does not establish a real human approval or trusted-store authorisation.

Do not open/import raw BCT sources, unrelated data/notebooks or real tender records for this baseline. No trade-cost estimate, cost-per-GFA prediction or winning-bidder recommendation is included. Preserve original titles, evidence limitations and explicit quantity/rate units. Arithmetic stays in Python; the LLM interprets/explains. Do not infer employee salaries, legal defaults or proven inflation from tender charges.

## Checks — no paid API calls

```powershell
uv run pytest -q
uv run ruff check app.py hybrid_inputs.py journey_inputs.py services scripts tests
uv run python -m compileall -q app.py hybrid_inputs.py journey_inputs.py services scripts tests
```

On Windows the existing `scripts/check.ps1` also runs a zero-call evaluation dry run. In this restricted workstation use its unique project-local pytest scratch setup if the default temporary directory is inaccessible. Real-model behaviour is evaluated separately from calculations/controller tests. Native Excel is not exercised by XML/formula/cached-value checks.

After staging reviewed files, run `uv run python -m scripts.audit_shareable` to inspect the complete index and verify exclusions without printing secrets. It rejects unlabelled datasets, unexpected binaries/paths and credential-shaped values; it complements manual privacy review rather than replacing it.

Regenerate the integration fixture/schemas with `uv run python -m scripts.build_integration_example`. Regenerate existing invented schedules only with `scripts.generate_synthetic`. Live runners require explicit `--allow-live`; do not add that flag for collaboration preparation. Existing usage ceilings/counters and completed private traces are preserved. The reserved evaluation set must not be used for development tuning or claimed as a scored result before a frozen human-reviewed evaluation.

## Git workflow and publication

`main` is the reviewed shared baseline. The owner works on `feature/agent1`; after the authorised first push and invitation, the teammate clones and creates `feature/agent2` from `origin/main`. Push each person's own branch, open tested increments as PRs to `main`, review shared changes and regularly merge `origin/main` into working branches. Do not force-push, reset shared history or discard the other person's changes. Exact first-push, invitation, clone and conflict-resolution steps are in [COLLABORATION.md](docs/COLLABORATION.md).

Local preparation does not push, invite collaborators, change repository visibility, deploy or populate historical evidence. API credentials, private notes, local DBs/uploads/outputs, raw documents, environments/caches and logs are excluded. [BASELINE_FILES.md](docs/BASELINE_FILES.md) describes the intended shareable set.


### Latest Track 1 refinement (19 October 2026)

The six steps now retain shared material-decision bases and distinguish missing rationale, invalid arithmetic and advisory qualifications. Step 5 offers comparable tender-rate references or an explicit salary-component PWM method using calendar months and a dated official MOM snapshot; no salary split or automatic statutory employer rate is inferred. See [walkthrough and method](docs/TRACK1_DECISION_BASIS_PWM.md) and [supported boundaries](docs/PENDING_DECISIONS.md). Unapplied drafts can be saved separately from applied facts and confirmations. Shared internal changes await peer review; the v1 transfer schema is unchanged.
