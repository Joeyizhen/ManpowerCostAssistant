# AI-Powered FM Manpower Cost Assistant

**DSS5105 Data Science Project in Practice · Sprint 2 · 30 October 2026**

An AI-assisted application for facilities management officers to prepare manpower budgets and review tender submissions. The system brings budget planning, proposal review and tender evaluation into one interface, with traceable assumptions and officer confirmation at key decisions.

Two agents support the workflow: **Agent 1 — Manpower Budget Planning** and **Agent 2 — Tender Review**. Python services calculate costs and variances; AI helps interpret inputs, explain findings and identify questions for clarification.

## Project team

| Team member | Student ID | Team contributions |
|---|---|---|
| Cheng Yi Zhen | A0333501W | Agent 1 — manpower budget planning and proposal review |
| Chua Wei Lin | A0170134U | Agent 2 — tender review and comparison |
| Quah Yi Tong | A0053240X | Agent 2 — tender review and comparison |
| Rita Indah Lestari | A0115171U | Agent 1 — manpower budget planning and proposal review |

All members contribute to data preparation, benchmark review, testing and the demonstration.

## Sprint 2 progress

| Workstream | Status | Current progress |
|---|---|---|
| Data and Benchmark | Completed for the prototype | Initial historical-data preparation and standardisation of role names, quantities, rate periods and tender-status fields. Unknown values and source limitations remain recorded. |
| Agent 1 — Manpower Budget Planning | In progress | Track 1 budget planning and core Track 2 proposal review are implemented. Integration of validated database-backed role, quantity and rate recommendations is paused pending Track 5. |
| Agent 2 — Tender Review | In progress | Tracks 3 and 4 support prototype cost comparisons, review findings and clarification questions. Track 5 and the connection to the planned shared database remain pending. |
| Test and Demo | In progress | Automated checks cover incomplete inputs, insufficient evidence and calculation accuracy. User testing, UI/UX refinement and end-to-end demonstration preparation continue. |

### Pending: Track 5 and shared database integration

**Tracks 1–4 are not yet connected to the planned shared database through a complete administrator-validation workflow. This integration depends on Track 5, which has not yet been implemented.**

Track 5 will allow a system administrator to review and validate uploaded historical manpower data before accepted records enter the shared database. The remaining work is to:

1. Build the upload, review and validation workflow in Track 5.
2. Establish the controlled process for adding validated records to the shared database.
3. Connect both agents' retrieval in Tracks 1–4 to those validated records, retaining source provenance and version information.

For Sprint 2, the agents use the existing reference services with locally provisioned prepared snapshots or labelled synthetic demonstration data. This supports the current prototype; it does not complete the planned Track 5-managed database integration. Database-backed recommendations remain subject to data availability and comparability checks.

### Available workflows

| Agent | Track | Current capability |
|---|---|---|
| Agent 1 | Track 1 — Build a new budget | Define the project, compare current and proposed deployment, select starting rates and annual changes, then review and export the budget. |
| Agent 1 | Track 2 — Review a proposed budget | Upload an existing proposal, check the captured figures, complete material gaps and review revisions through the shared budgeting screens. |
| Agent 2 | Track 3 — Compare against an approved budget | Verify budget and tenderer schedules, review role matches, compare quantities and costs, record clarifications and export findings. |
| Agent 2 | Track 4 — Review tender pricing | Compare submissions against historical references, flag unusual pricing and resourcing differences, and prepare clarification questions. Dedicated like-for-like cross-tenderer comparison remains pending. |
| Agent 2 | Track 5 — Maintain historical manpower data | Planned administrator workflow for validating uploaded records before they enter the shared database. |

Track 1 follows **Project → Deployment → Starting rates → Annual changes → Budget**. Track 2 starts with proposal upload and reuses the budgeting controls while keeping original figures separate from accepted revisions.

The application supports officer judgement. Saving a draft, accepting an AI suggestion, confirming inputs and approving a final budget are separate actions. It does not select a winning tenderer.

## Run the Sprint 2 application

The combined Sprint 2 application is available on the default **`main`** branch. A normal clone provides the landing page with **Manpower budgeting** and **Tender evaluation**, including the Site Xtown example. The integration history is recorded in [PR #1](https://github.com/Joeyizhen/ManpowerCostAssistant/pull/1).

Python 3.14 is the tested development version. With `uv` installed:

```powershell
git clone https://github.com/Joeyizhen/ManpowerCostAssistant.git
cd ManpowerCostAssistant
uv sync --frozen --python 3.14
Copy-Item .env.example .env
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8511/` on the same computer. Both agents run from `app.py`. Preserve an existing private `.env` rather than copying over it. Alternative installation and hosting configuration are covered in [DEPLOYMENT.md](DEPLOYMENT.md).

### Try the Site Xtown example

Choose **Manpower budgeting → Build a new budget**, open the sidebar and select **Load Site Xtown example**.

The included fictional project has a three-year base term plus three option years, 13 current staff and 17 proposed staff. It opens a populated budget for review and works without a private saved-project database or API key. Its rates and assumptions are illustrative; final officer approval is not preloaded.

A [blank proposal template and filled sample](data/templates/) are also included for Track 2. See [the Site Xtown example](docs/XTOWN_EXAMPLE.md) and [upload-first proposal review](docs/TRACK2_UPLOAD_FIRST.md).

## AI configuration and reference data

**No API key is needed to download the code, open the interface, load examples, calculate costs or export results.** To use optional AI guidance, configure both `OPENAI_API_KEY` and `OPENAI_MODEL` privately in `.env` or server-side Streamlit secrets. AI requests can incur provider charges. Credentials are excluded from Git.

A clean checkout uses explicitly labelled synthetic data. Private prepared references can be provisioned separately; original source workbooks, raw records, saved projects and uploads are not distributed through this repository. Starting-rate ranges shown as illustrative planning allowances are authored assumptions, not verified market prices.

General annual changes and eligible salary-component PWM are treated separately, with explicit applicability and published-period assumptions. See [reference provisioning](docs/PREPARED_REFERENCES.md) and [cost comparison methods](docs/HEADCOUNT_COST_COMPARISON.md) for calculation and evidence boundaries.

## Validation and next steps

The combined application passed **402 automated tests**, with three intentional skips requiring private officer snapshots. Verification included a clean package, fresh locked dependencies, both agents' workflows, confirmation safeguards, exports and an isolated server startup check. The publication audit found no issues in the 161-file shareable set.

These checks establish software behaviour; they do not replace live AI/task evaluation or user acceptance testing. Current priorities are:

- Complete Track 5 and connect both agents to the validated shared database.
- Continue user testing, improve step-switching responsiveness and refine the end-to-end demo.
- Complete task-based evaluation, report category results and analyse observed failures.
- Verify the selected deployment environment and persistence before shared use.

Trusted transfer of a live approved budget between agents remains incomplete. General navigation lag is still under review; only the Deployment screen has a measured loading improvement. Detailed results and limits are recorded in [VALIDATION.md](docs/VALIDATION.md).

## Further documentation

- [Project write-up and architecture](docs/PROJECT_BRIEF.md)
- [Setup and deployment](DEPLOYMENT.md)
- [Combined-agent implementation](docs/SPRINT2_INTEGRATION.md)
- [Collaboration and branch workflow](docs/COLLABORATION.md)
- [Reference provisioning and limitations](docs/PREPARED_REFERENCES.md)
- [Validation results](docs/VALIDATION.md)

Development checks:

```powershell
uv run pytest -q
uv run ruff check .
uv run python -m scripts.audit_shareable
```

The publication audit checks the complete Git index after reviewed files are staged. Private credentials, data, databases, uploads and development outputs remain excluded.
