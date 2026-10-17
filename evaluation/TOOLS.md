# Application tool specification

Tools run on the server with strict Pydantic schemas. Numbers come from Python retrieval/calculation services. The live tool list has no approval, secret access, arbitrary code execution, historical import or external browser tool.

| Tool | Purpose and boundaries |
|---|---|
| get_project | Confirmed facts, working context and validated synthetic catalog metadata. Prices withheld before manpower confirmation. |
| update_working_notes | Quietly accumulate supplied profile, duties, operational roles and notes before the bundled manpower decision. No proposal or approval; known table inputs and unknowns are retained. |
| prepare_review | Check readiness, then prepare requirements, manpower, rates or escalation for one meaningful officer decision. Material gaps block preparation. Earlier requirements, mapping, deployment or rate revisions require renewed confirmation of the affected decision. |
| calculate_coverage | Python weekly coverage, baseline/relief FTE and indicative personnel. Rejects net-capacity/relief double counting; does not establish law or roster feasibility. |
| retrieve_quantities | Synthetic filtered quantity references before pricing, without monetary fields. Not a workload rule. |
| retrieve_rates | Synthetic comparable inclusive prices, arithmetic average, quantiles, counts and sources. Requires manpower confirmation; fewer than three distinct schedules or mixed priced years yield no numeric range. |
| retrieve_escalation | Python schedule-based unit-price changes, medians, counts and exclusions. Tender-priced expectations, not realised inflation. |
| propose_rate / propose_rates | Quiet single/batch rate notes after manpower confirmation. Benchmark selections require available comparable evidence; explicit officer assumptions remain distinctly labelled. |
| propose_escalation / propose_escalation_profiles | Quiet single/batch future-price notes after rates confirmation. Every actual year needs a value, Year 1 zero; quote eligibility and policy overlaps remain checked by calculation services. |
| preview_budget | Runs Python for actual role/year, full/base/optional totals, waterfall and findings. Requires rates confirmation and valid future-price inputs. Cannot approve. Sensitivity is calculated separately by Python for app/export. |
| propose_finding_decisions | Prepare only officer-supplied decisions and justifications for every finding. Blocking arithmetic cannot be accepted as an exception. Explicit officer confirmation required. |

Legacy propose_profile, propose_responsibility and propose_role contracts remain for compatibility/tests but are excluded from live Responses tools. They are not the current journey.

Working notes retain officer table inputs and answers independently of approved facts. Review my manpower plan explicitly invokes the LLM for material sanity checks. The officer corrects and confirms one compiled manpower decision; no per-answer apply step. The application atomically applies it, records confirmations and advances directly to editable rates without an automatic interview. Rates/base-year overview are also grouped. Revisions invalidate affected confirmations and preserve history. Stale queues are rejected. Errors, refusals, incomplete responses or exceeded limits roll back partial turn updates.

Live limits: six Responses requests and twelve function calls per submitted turn, 3,500 output tokens per response, ninety-second request timeout, no automatic SDK retries. Errors are sanitised; raw internal reasoning is not persisted. Public tools/messages are evidence, not proof of model accuracy.

The opt-in `scripts.evaluate_hybrid` runner is a separate three-turn/18-request synthetic development case starting with structured inputs/table. Default is a zero-call dry run; `--allow-live` uses the configured private credentials. Requests/usage/snapshots are preserved locally; earlier traces are unchanged. After scripted manpower confirmation it verifies downstream calculations with explicitly synthetic officer selections, without further LLM calls or final approval.

The complete-conversation runner has an eighteen-turn / 108-request total ceiling. Resume preserves usage and refuses missing/inconsistent counters, exhausted allowances and completed/finally approved traces before client creation. The separate two-follow-up runner has its own two-turn / twelve-request ceiling and never alters the original trace or approves a budget.
