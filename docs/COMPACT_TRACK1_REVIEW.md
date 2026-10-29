# 26 October 2026 — compact Track 1 review

The six-step journey is retained. Deployment edits, saving, assistant proposals and officer confirmation remain distinct actions.

## Completed changes

- Steps 2–3 use one deployment editor per screen, with role, applicable current deployment, proposal, unit, calculated change and operational rationale. Headcount and FTE totals update separately. Unknown current values stay unanswered. Stable row IDs preserve repeated titles. Meaningful table rationales become retained decision evidence without approving the plan; unchanged reruns do not append duplicate evidence.
- Step 3 retains material discrepancy checks and officer decisions. Corrections use the deployment editor; the sanity-check view is read-only. Valid staffing choices can be retained with their qualifications.
- Step 4 combines confirmed deployment, starting allowance and role monthly cost in compact rows. Supported arithmetic averages start as unconfirmed recommendations. The observed range, average marker and exact input stay synchronised. Outside-range selection is explicit; changed or unsupported allowances require a focused reason. References attach automatically. Related reference-year mismatches can share one explanation. Detailed evidence is expandable. Editing deployment explains later confirmation invalidation. A single primary action confirms starting rates and continues.
- Step 5 retains one shared general increase and staged relevant PWM groups. No staffing or starting-rate explanations are repeated. Existing worker eligibility, salary-component, calendar-month treatment and no-stacking rules are preserved. Stable IDs remain internal in the normal grouped table.
- Step 6 leads with contract/base/option totals, cost drivers, qualifications and outstanding decisions. Draft export and explicit versioned final confirmation sit near the summary. Calculations, charts, sensitivity, source material and audit details remain available in expandable sections. Confirmed qualified budgets retain qualifications in exports.
- Cached UI helper recovery includes the new modules without clearing model classes or draft sessions. Project switching clears superseded pricing widgets and retains saved values and sources.

## Synthetic walkthrough and checks

1. Enter contract context and confirmed units; unanswered current quantities remain unknown.
2. Enter deployment, an explained staffing change and fractional FTE. Live totals remain separate by unit; repeated titles retain distinct IDs.
3. Review material findings, retain a valid flagged choice with a reason, then explicitly confirm the displayed plan.
4. Inspect recommended allowances; adjust via range or exact entry; provide a reason for custom or unsupported prices. Record shared year treatment once and explicitly confirm rates.
5. Review the shared general increase and mixed eligible PWM/non-PWM fixture. Preserve component boundaries and inspect impact before confirmation.
6. Inspect totals and qualifications, export a draft, explicitly confirm the identified version and export the confirmed workbook. Saving and resuming retain decisions without implying confirmation.

Full offline regression: **199 passed in 248.53 seconds**, covering the complete synthetic journeys, retained findings, general/PWM calculations, save/resume, repeated titles, invalidation and exports. After the final rounding disclosure changes, **63 targeted checks passed in 38.52 seconds**. Browser checks used a separate synthetic database on port 8512: compact FTE pricing, saved revision status, final totals, qualified final confirmation and confirmed export availability. No assistant/model action was invoked.

## Remaining convention and limitations

The existing contract engine rounds annual role costs. Multiplying displayed cent-rounded monthly FTE totals by 12 can differ by cents. Step 4 now shows the requested monthly-total × 12 overview and explicitly discloses the difference from the retained annual starting-charge calculation; Step 6 and exports carry the qualification. The synthetic FTE case differs by SGD 0.06. No alternate contract rounding rule has been assumed.

Database allowance references remain synthetic demonstration evidence, not market rates. Unsupported prices remain officer assumptions or supplied quotations. PWM source/eligibility and unpublished-period qualifications remain explicit. No market rates, staffing requirements or policy rules were invented.

No paid model calls, deployment, staging, commit or push occurred. Existing officer project records were not modified by the isolated walkthrough.
