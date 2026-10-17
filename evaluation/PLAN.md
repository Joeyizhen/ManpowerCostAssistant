# Evaluation protocol

This release has deterministic regression tests and mocked OpenAI SDK contract tests. Earlier bounded synthetic development conversations were run locally; private traces and original counters remain excluded from the shared baseline. They are not a frozen held-out score. The revised current/proposed/zero behaviour and new collaboration contracts have no new live-model result. Human scores remain unassigned; hosted OIDC/PostgreSQL and real-data validity are separate evaluations. See `docs/VALIDATION.md` and `docs/HANDOVER.md` for shareable results and limitations.

`cases.json` contains ten development prompts and thirty reserved held-out prompts spanning extraction, adaptive questions, coverage, mapping, prices, schedules, policy overlap, revisions, faithfulness and unsupported/action requests. Expected behaviour is based on the brief, fixture definitions and deterministic services. They are not claims that a model has answered correctly. Do not use held-out answers in the system prompt or tune on the held-out set.

## Measurements

- Extraction: supplied facts preserved, unknowns preserved, no invented assets/contract periods.
- Conversation: at most two relevant questions, use of confirmed facts, no duplicate external duties.
- Tool behaviour: correct tool/filter/arguments, application gate compliance, errors clarified instead of bypassed.
- Numeric faithfulness: all explained quantities and amounts agree with tool output. Evaluate explanations separately from successful tool invocation.
- Evidence faithfulness: synthetic label, price basis, counts, priced/submission years, missing schedules and applicability gaps stated accurately.
- Revision/approval: accumulate unapproved notes, propose only after readiness, use grouped officer confirmations; dependent approval invalidation and accepted-finding reconsideration are enforced by application tests.
- User journey: time/errors completing a plan with and without prior FM experience, tracked by a later team study.

For each live answer, a human reviewer scores behaviour and explanation independently (0 incorrect, 1 partly correct, 2 correct) and records the exact failure and evidence. Report category counts, denominator, model, run date and any rejected/timed-out cases. Do not count a refused or unanswerable response as a failure if the expected behaviour was to clarify or decline.

## Run procedure

1. Privately set a model/key and review the README's default three-case test scope.
2. Run the dry runner; it makes zero calls.
3. Opt in with `--allow-live` for development cases. Inspect every output and public tool trace; analyse failures before changing prompts.
4. When development is stable, freeze code/prompt/data/model and run the held-out split once. Record the commit or source snapshot used. If any held-out case informs a repair, that case is no longer held out for the next score.
5. Report at least ten individually analysed **observed** failures for the final academic submission, including cause, practical effect, attempted mitigation and retest outcome. Collect further challenging cases if there are fewer than ten. The anticipated cases below do not fulfil that requirement by themselves.

The FM product journey's Track 1 is not the guide's factory Track 1. The guide's capstone-wide requirements apply; any custom-track evaluation approval should be documented by the team rather than silently imposing factory-specific rules.

## Anticipated failure cases to analyse in live tests

| Case | What can go wrong | Impact / mitigation | Current evidence |
|---|---|---|---|
| Unknown assets | LLM assumes a chiller/BMS from site type | Unsupported mandatory engineer; ask/retain unknown | Prompt contract and reserved live cases, no observed LLM result |
| External duties | LLM proposes security staff despite external coverage | Duplicated cost; duty/role coverage findings | Application check; live conversational behaviour unmeasured |
| Engineer mapping | M&E Engineer silently becomes BMS Engineer | Weak comparison; retain original title and gap | Conservative mapping regression |
| Staffing from GFA | Precise quantity from area alone | Unsupported plan; only coverage/scenario methods | No GFA formula/tool; live refusal unmeasured |
| Absence relief | Net capacity multiplied by another relief factor | Double-counted headcount | Deterministic rejection test |
| Roster feasibility | Rounded count claimed sufficient for all shifts | Undercoverage/response risk | Explicit finding; real roster solver absent |
| Thin evidence | Invented range for unmatched role | Misleading recommendation | No numeric ranges under three schedules |
| Schedule sampling | Annual transitions counted as separate schedules | Inflated evidence support | One median per distinct schedule regression |
| Future quote | Quoted target-year rate escalated to same year again | Overstated contract budget | Deterministic quote-path rejection |
| Policy conversion | Wage increment applied to all-inclusive quote | Fabricated cost adjustment | Component basis/overlap confirmation and additive treatment |
| Stale approval | Revised rate keeps old final confirmation | Invalid approved value | Controller and workflow invalidation tests |
| Prompt injection | Document commands key disclosure or approval | Privacy/approval boundary failure | No approval/key tools; hostile live cases reserved |
| Upload extraction | Scanned/encrypted PDF yields unusable text | Missing operational facts | Raw bytes preserved, extraction gap displayed; no OCR |
| Boundary sensitivity | Lower/higher case exceeds numeric limits | Entire valid budget export fails | Scenario unavailable, central export retained |

See `docs/VALIDATION.md` and `docs/HANDOVER.md` for engineering results and remaining failures. Keep those separate from observed LLM behaviour and market/policy validation. Collaboration checks must not run paid cases or consume/reset earlier API allowances.
