# AI-Powered FM Manpower Cost Assistant

**DSS5105 Data Science Project in Practice · Sprint 3 · 13 November 2026**

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

## Sprint 3

| Workstream | Status | Current progress |
|---|---|---|
| Data and Benchmark | Completed for the prototype | The bundled reference dataset standardises role names, quantities, rate periods and tender-status fields. Unknown values and source limitations remain recorded. |
| Agent 1 — Manpower Budget Planning | Implemented for the Sprint 3 prototype | Tracks 1 and 2 support manpower budget preparation, uploaded-proposal review, confirmation controls and export. |
| Agent 2 — Tender Review | Implemented for the Sprint 3 prototype | Tracks 3 and 4 support multi-tender upload, visible input validation, role matching, cost comparisons, review findings, clarification questions and exports. |
| Test and Demo | In progress | Automated checks cover incomplete inputs, insufficient evidence and calculation accuracy. The upload screens provide templates and worked examples for clean and validation-focused walkthroughs. |

### Reference data used by the prototype

The project reference dataset was derived from real workplace tender submissions made available to the team for this project. Before use, confidential and identifying information, including organisation names, tenderer names and document identifiers, was removed or generalised. The remaining manpower information was standardised into 283 comparison records across 15 roles, with project reference years 2022–2026 used for consistent filtering.

The agents use this sanitised dataset to retrieve comparable roles, quantities, contract years and monthly rates. This allows the budgeting and tender-review workflows to be tested against realistic submission structures and pricing patterns. Internal source identifiers are non-identifying project references retained for reproducible calculations. The dataset is a project reference resource, not a live procurement system or an independently verified market benchmark.

Projects saved locally use SQLite by default. User uploads and saved project data remain separate from the project reference dataset and are not automatically added to it.

### Available workflows

| Agent | Track | Current capability |
|---|---|---|
| Agent 1 | Track 1 — Build a new budget | Define the project, compare current and proposed deployment, select starting rates and annual changes, then review and export the budget. |
| Agent 1 | Track 2 — Review a proposed budget | Upload an existing proposal, check the captured figures, complete material gaps and review revisions through the shared budgeting screens. |
| Agent 2 | Track 3 — Compare against an approved budget | Upload one approved budget and up to five tenderers, verify extracted schedules, resolve blocking input issues, review role matches, compare quantities and costs, record clarifications and export findings. |
| Agent 2 | Track 4 — Review tender pricing | Upload and validate up to five tenderers, review role matches, compare submissions against historical references, flag unusual pricing and resourcing differences, and prepare clarification questions. |

Track 1 follows **Project → Deployment → Starting rates → Annual changes → Budget**. Track 2 starts with proposal upload and reuses the budgeting controls while keeping original figures separate from accepted revisions.

The application supports officer judgement. Saving a draft, accepting an AI suggestion, confirming inputs and approving a final budget are separate actions. It does not select a winning tenderer.

## System requirements

- Windows, macOS or Linux with a writable project folder
- Python 3.11–3.14 (Python 3.14 is the tested development version)
- `uv` for dependency installation and command execution
- Git when cloning the repository
- Internet access for the initial dependency download
- A modern web browser
- A spreadsheet viewer is recommended for exported XLSX reports
- An OpenAI API key only for optional AI-written assessments; calculations, validation and exports work without one

## Run the Sprint 3 application

The combined Sprint 3 application is available on the default **`main`** branch. A normal clone provides the landing page with **Manpower budgeting** and **Tender evaluation**. The included Site Xtown example is for **Manpower budgeting only**.

Python 3.14 is the tested development version. With `uv` installed, use the commands for your operating system.

### Windows PowerShell

```powershell
git clone https://github.com/Joeyizhen/ManpowerCostAssistant.git
cd ManpowerCostAssistant
uv sync --frozen --python 3.14
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

### macOS or Linux terminal

```bash
git clone https://github.com/Joeyizhen/ManpowerCostAssistant.git
cd ManpowerCostAssistant
uv sync --frozen --python 3.14
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8511/` on the same computer. Both agents run from `app.py`. No `.env` file or API key is required for the default local workflow. Optional AI-written guidance requires private `OPENAI_API_KEY` and `OPENAI_MODEL` settings; preserve an existing `.env` rather than replacing it. Alternative installation and hosting configuration are covered in [DEPLOYMENT.md](DEPLOYMENT.md).

## Demo workflows

### Agent 1 Manpower budgeting

#### Track 1 Build a new budget with Site Xtown

Site Xtown provides a guided budgeting scenario with the project details, deployment and starting assumptions already populated.

1. Choose **Manpower budgeting → Build a new budget**.
2. Open the sidebar and select **Load Site Xtown example**.
3. Review the project and deployment, work through the starting rates and annual changes, then review and export the budget.

The example has a three-year base term plus three option years, 13 current staff and 17 proposed staff. It works without an API key. Its rates and assumptions are prepared for demonstration, and final officer approval is intentionally left to the user. See [the Site Xtown example](docs/XTOWN_EXAMPLE.md).

#### Track 2 Review a proposed budget

1. Choose **Manpower budgeting → Review a proposed budget**.
2. Start with the supplied example or upload the [blank proposal template or filled sample](data/templates/).
3. Verify the captured details, resolve missing assumptions, review revisions and export the completed budget.

The application keeps the submitted figures separate from accepted revisions. See [upload-first proposal review](docs/TRACK2_UPLOAD_FIRST.md).

### Agent 2 Tender evaluation

#### Track 3 Compare against an approved budget

1. Choose **Tender evaluation → Compare against approved budget**.
2. Upload one approved manpower budget, enter its approval details and add up to five tenderers.
3. Review the validation results and role matches, resolve all blocking issues, then compare quantities and costs and export the findings.

The validation screen detects missing contract duration or quantity, an unlabelled fractional headcount, missing annual rates within the stated contract period and possible double escalation of a future quoted rate. Comparison remains blocked until required corrections and confirmations are complete.

#### Track 4 Review and compare tenderer proposals

1. Choose **Tender evaluation → Review and compare tenderer proposals**.
2. Complete the project details, continue to **Upload tenderer submissions**, then open **Need an example to explore the feature?** and select **Use example tender**.
3. Verify the extracted submissions and role matches, select the comparison context, then review the pricing findings and clarification questions.

Track 4 supports up to five tenderers and uses the bundled reference dataset for repeatable comparisons. When evidence coverage is insufficient, the application keeps the result in manual review instead of inventing a benchmark. Submitted role titles remain visible even when a standard comparison role is selected.

## AI configuration and reference data

**No API key is needed to download the code, open the interface, load examples, calculate costs or export results.** To use optional AI guidance, configure both `OPENAI_API_KEY` and `OPENAI_MODEL` privately in `.env` or server-side Streamlit secrets. AI requests can incur provider charges. Credentials are excluded from Git.

A clean checkout uses the bundled example reference dataset described above. Private prepared references can be provisioned separately; original source workbooks, raw records, saved projects and uploads are not distributed through this repository. Starting-rate ranges shown as illustrative planning allowances are authored assumptions, not verified market prices.

General annual changes and eligible salary-component PWM are treated separately, with explicit applicability and published-period assumptions. See [reference provisioning](docs/PREPARED_REFERENCES.md) and [cost comparison methods](docs/HEADCOUNT_COST_COMPARISON.md) for calculation and evidence boundaries.

## Validation and next steps

The merged Sprint 3 application passed **404 automated tests**, with three intentional skips that require private officer snapshots. The suite covers both agents' workflows, confirmation safeguards, exports, input validation and comparison calculations.

These checks establish software behaviour; they do not replace live AI/task evaluation or user acceptance testing. Current priorities are:

- Continue user testing, improve step-switching responsiveness and refine the end-to-end demo.
- Complete task-based evaluation, report category results and analyse observed failures.
- Verify the selected deployment environment and persistence before shared use.

Trusted transfer of a live approved budget between agents remains incomplete. General navigation lag is still under review; only the Deployment screen has a measured loading improvement. Detailed results and limits are recorded in [VALIDATION.md](docs/VALIDATION.md).

## Further documentation

- [Project write-up and architecture](docs/PROJECT_BRIEF.md)
- [Setup and deployment](DEPLOYMENT.md)
- [Reference provisioning and limitations](docs/PREPARED_REFERENCES.md)
- [Validation results](docs/VALIDATION.md)

Development checks:

```powershell
uv run pytest -q
uv run ruff check .
uv run python -m scripts.audit_shareable
```

The publication audit checks the complete Git index after reviewed files are staged. Private credentials, data, databases, uploads and development outputs remain excluded.
