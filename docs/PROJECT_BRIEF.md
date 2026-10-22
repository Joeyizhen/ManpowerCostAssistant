# Shareable project brief

AI-Powered FM Manpower Cost Assistant is a university capstone app, with Track 1 as its first implementation release. The Sprint 2 business deck supplies the FM objectives and two-agent/five-track framing; applicable capstone specifications govern academic deliverables and evaluation. The milestone does not limit the final product scope. Private source documents and development handoffs are retained locally and are not included here.

## Product scope and ownership

Agent 1 (project owner) covers Track 1 Build New Plan and Track 2 Review Proposed Plan. Agent 2 (teammate) covers Track 3 Compare Against Approved Budget, Track 4 Compare Tender Submissions with Historical Tenders, and Track 5 Maintain Historical Manpower Database. Tracks 1, 3 and 4 are implemented as development prototypes; Tracks 2 and 5 remain planned.

The existing Python/Streamlit app combines structured officer inputs, a real OpenAI tool-calling integration and deterministic Python services. The officer supplies a brief/period and current/proposed manpower, requests targeted assistant review, confirms manpower, chooses monthly inclusive rates and future-price assumptions, reviews findings/full-contract costs and confirms/export results. The model never approves a budget or updates historical evidence. Keys stay in private environment/hosting secrets.

## Checkpoint rather than finished redesign

Current/proposed tables offer eight common optional roles, zero exclusions, fractional FTE, inventory/custom titles, optional existing deployment and explicit copy/mark-zero actions. Existing saved projects remain supported. Shared calculations, evidence retrieval, charts, confirmation invalidation and nine-section Excel export remain.

The requested six-screen flow and compact pricing/future-change redesign are unfinished; [HANDOVER.md](HANDOVER.md) lists limitations. The model's newly extended comparison/zero behaviour has not been re-evaluated live. Automated calculation checks are not evidence of conversational reliability or real-world market validity.

## Evidence and calculation boundaries

- Use only reviewed role-title context and labelled synthetic fixtures in this baseline. Title presence does not establish a price benchmark. Do not access linked raw BCTs, other project data/notebooks, extract real records or populate a historical database without a separate instruction.
- Keep original titles, seniority, combined duties, explicit unknowns, units, currency, scope, submitted/awarded status, pricing years and source references. Current deployment is context, not proof of the right future quantity. No staffing prediction from GFA/building type; no compulsory positions inferred from a title list.
- Rates are inclusive monthly tender charges, not salaries. Arithmetic average is computed only from eligible comparable same-year records; thin evidence produces no range. Unsupported roles require officer assumptions.
- Distinguish FTE/headcount/posts, relief and capacity. Preserve meaningful human confirmations and invalidate dependent decisions after revisions. Invalid arithmetic cannot become an accepted exception.
- Distinguish submission year, contract year and calendar-priced year. Forward-quoted target-year prices receive no duplicate escalation. Separate supported policy components; never invent salary splits, legal defaults or inflation causes.
- Full contract value is the sum of role/year costs, with base/options, annual chart, reconciled waterfall and disclosed sensitivity. Export evidence, assumptions, operational reasons, findings and status.

No trade-cost estimation, cost-per-GFA prediction, winning-tenderer recommendation, autonomous historical import or model retraining is introduced. Preserve the previous prototype and unrelated projects. Publication, collaborator invitation and hosting remain separate actions; this preparation is local only.

## Track 3 checkpoint

Track 3 supports multiple verified tenderer schedules, reviewable role matching, contract/role variance findings, clarification questions, officer decisions, save/resume and traceable Excel export. Deterministic checks block missing contract years, duplicate role-year rows, incompatible headcount/FTE units, unsupported currencies and non-monthly rates. Relevant worksheets in an Excel workbook are combined with worksheet/row provenance; unrelated instruction sheets are ignored. Approval references are officer-confirmed metadata, not cryptographic proof or trusted-store authentication.

See [COLLABORATION.md](COLLABORATION.md) for ownership/branches and [INTERFACES.md](INTERFACES.md) for the versioned budget/tender contracts.
