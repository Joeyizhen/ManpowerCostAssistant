# Track 1 v3 reference activation — 29 October 2026

Active source: **Excel_Selection_Completed_Sanitised_v3.xlsx**.
Dataset: `21a2ad31f607d169-sprint2-reference-v2` (v3 workbook, importer version 2).
Previous source remains available: `bf02f4c629b7f181-sprint2-reference-v1`.

The versioned local snapshot passed required-column, record/control ID, role mapping,
tender/submission/schedule/property relationship and source-register cross-checks.
12,021 observations were imported once, with no ID, join or structural errors.
All original prices, quantities, controls and record mappings match the previous
selection. No data cleaning, trimming, rate corrections, generated observations,
simulation records or test CSVs were imported. Both saved project bodies and their
calculation results were checked unchanged across activation.

## Role choices and project routes

The 27 nonblank Standard Roles provide 17 optional typical choices and ten core
additional choices. Already-added identities and safe aliases are excluded.
Unresolved original mapping titles remain distinct internally, without inheriting
a benchmark or PWM flag. Original titles, seniority and combined roles remain.

`services.cost_routing` provides the shared project route:

- Yes: Cleaner, Cleaning Supervisor, Security Officer, Senior Security Officer,
  Security Supervisor and Lift Technician route to PWM setup.
- No: general annual manpower increase. Officer requests cannot override No.
- Missing or unresolved: explicit Standard Role clarification at Annual changes;
  this classification does not remap the starting-price benchmark.

New or renamed roles retain their route's source/version. New annual decisions pin
their route for reproducibility. Existing saved roles without a routing snapshot
remain readable and calculable without repricing; revising/confirming annual
assumptions checks the workbook route. The calculator validates pinned routes.
Replacing an incompatible saved method requires an explicit officer action.

PWM flag routing is not legal eligibility. Policy choices are restricted to the
mapped trade and, where explicit, job level. Employment arrangement, basic/gross
wage basis, covered headcount, salary component/source, effective dates and unknown
future periods remain officer-reviewed. The established calendar-month method and
general/PWM overlap prohibition are unchanged. No whole contractor-charge salary
split is inferred.

## Interface and assistant

Deployment has two actions: **Confirm deployment numbers and continue** and
**Discuss possible deployment refinements with AI**. The second opens the retained
discussion inline without making a model call. The duplicate discussion expander
and repeated operational-reason paragraphs are removed. Five-step navigation and
compact starting-rate controls remain.

The assistant has a read-only `check_future_cost_method` tool. Its results identify
the resolved workbook flag and mismatch, return supported general-reference
statistics where applicable, and require a reviewable proposal before acceptance.
Offline mocked Responses tests exercise this interaction separately from calculator
rejection; they do not establish real-model extraction or reasoning reliability.

## Remaining source limitations

86 of 239 workbook PWM observations exactly match retained policy observations;
153 require mapping/basis/date review and did not overwrite the policy catalogue.
No fresh external policy verification is claimed. Unsupported mappings remain
unavailable rather than guessed. Published-period limits still require a disclosed
officer choice. The existing conditional-quotation limitations remain: actual
calendar pricing years, award outcomes and comparable source staffing units/scope
are not certified. Role availability does not establish a usable starting-rate
recommendation.

Developer diagnostics in the sidebar show the active filename and dataset ID.
All tracks resolving the existing shared reference service see the same activation
pointer; no Track 3/4 source, navigation, transfer or integration changes were made.
No merge, push, deployment, paid model evaluation or database cleaning was performed.

Validation: **122 targeted offline checks passed in 191.61 seconds**. Ruff, Python compilation, whitespace and the shareable-file audit passed.

Detailed local verification logs and preservation reports are under
`outputs/evaluation/v3-*` (ignored, not shareable source data).
