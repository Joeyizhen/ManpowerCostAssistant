# Shared budget and tender interfaces — version 1.0

These are validated transfer documents for independent development. They do not implement Track 3–5, change the Track 1 UI or write to storage. Models are in `services/integration_contracts.py`; matching JSON schemas are in `contracts/`. Existing internal draft/working-note state remains in `services/models.py:Plan`.

## Distinct document and status types

| Document | Identifier | Status and meaning |
|---|---|---|
| Internal working proposal | `Plan.id`, version | May be incomplete; unconfirmed notes/proposals are not an approved budget |
| `manpower_budget` | `budget_id`, revision, source plan ID/version | `draft` = costed draft; `submitted` = awaiting approval; `approved` requires explicit approval metadata |
| `tender_submission` | submission/tender/tenderer IDs, target budget ID/revision | `draft` or `submitted`; a submitted tender has a submission timestamp and is never itself an approved budget |

Numeric transfer documents require complete reconciled role/year rows. An incomplete working plan stays in the existing app draft model rather than being silently filled for export. Status validation is **not authentication or approval authority**. A future production handoff must obtain the budget from trusted storage, verify its source version/final officer confirmation and access rights, and reject stale approvals. Do not trust an uploaded JSON `approved` string alone. No production Plan-to-contract adapter or historical import endpoint has been added.

## Field contract

| Fields | Rules |
|---|---|
| `schema_version`, `document_type`, `synthetic`, `label`, `revision` | Explicit version and origin; synthetic documents visibly say SYNTHETIC |
| Role ID, `original_title`, optional `mapped_benchmark_role` | IDs stay stable within a document lineage; never overwrite the supplied title or infer a senior/combined-role mapping |
| `matched_budget_role_id` | Optional explicit relationship for a future tender-to-budget mapping; tender-local IDs are not assumed to match budget IDs, and matching is not automatic |
| `quantity`, `quantity_unit`, `quantity_basis` | Positive included staffing in whole-person `headcount` or fractional `FTE`, with a stated operational basis. Posts require explicit conversion before a priced transfer |
| `excluded_roles` | Explicit zero exclusions, original ID/title and reason; excluded roles have no costed annual rows |
| `monthly_rate`, `rate_unit`, `source_rate_basis` | SGD inclusive monthly tendered manpower charge per head or per FTE, matching the quantity unit. Preserve source inclusions/conversion. These are not employee salary figures |
| `rate_pricing_year` | Year of the selected reference/base quote. A mismatch with the budget boundary needs a disclosed officer assumption; no automatic inflation normalisation |
| Contract period | Start year and optional actual date; base/option years distinguished; total at most 20; year-only boundaries explicitly illustrative |
| Annual rows | Contract-year index, annual boundary pricing year, inclusive start/end dates, option flag, actual quantity/rate, separately evidenced annual adjustment and annual cost |
| Evidence/assumption IDs | Every role references declared sources and operational/future-price assumptions. Fixture prices and officer allowances remain distinguishable |
| Totals | Role-year costs → yearly totals → base/option/full sums, reconciled in cents using the existing Python rounding rules |
| Approval | Actor, timestamp, reference and synthetic-approval marker. Draft/submitted budgets have no approval metadata; synthetic approvals cannot become real approvals |
| Tender submission | Budget ID/revision, tender/tenderer/submission IDs and submission time; preserve the tender's own roles, units, prices and source documents |

Submission date, evidence pricing year, contract-year index and annual boundary pricing year are separate concepts. An annual row may use a target-year quote or an assumption compounded by the existing calculator; it carries the resulting monthly unit rate. A forward-priced quote receives no extra escalation to that same year. Total manpower-cost changes are not evidence of role-rate inflation.

## Independent synthetic Track 3 starting point

`data/sample/integration/approved_budget.synthetic.json` is an entirely invented **SYNTHETIC APPROVED-BUDGET EXAMPLE — NOT A REAL APPROVAL OR TENDER**. Its fake approval is labelled synthetic and does not change any app project. It uses existing synthetic/demo inputs and the real budget service. Sources and officer assumptions are recorded; no raw BCT data was accessed. The source plan's arbitrary runtime ID is not copied into the fixture.

```python
from pathlib import Path
from services.integration_contracts import BudgetDocument

example = BudgetDocument.model_validate_json(
    Path("data/sample/integration/approved_budget.synthetic.json").read_text(encoding="utf-8")
)
assert example.synthetic and example.approval.synthetic_approval
```

The teammate can consume this fixture and invent separately labelled synthetic tender submissions on `feature/agent2`, without Agent 1 UI or OpenAI access. Validation rejects duplicate IDs, dangling evidence references, unit mismatches, missing years, inconsistent dates/status and non-reconciling amounts. JSON schema handles shape/types; use the Python models for cross-field arithmetic/reference checks. These checks do not score a tender or determine a winning bidder.

Regenerate the example and schemas locally with `uv run python -m scripts.build_integration_example`; this makes no API or database calls. To change the interface, coordinate through a PR, version any breaking change and update schemas/example/tests/docs together. Preserve old saved `Plan` snapshots through defaults/migrations rather than replacing their model wholesale.
