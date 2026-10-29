# Headcount and price comparison — 30 October 2026

The Budget chart now separates current headcount valued at selected starting rates,
headcount changes at those same rates, general compounded annual increases, PWM
and other adjustments. Year 0 is a comparison bar, not an extra contract year or
actual historic spending. Average budget is the full contract total divided by
base plus option years. Driver percentages are shares of the net increase over
Year 0, not shares of the entire budget. Headcount changes are attributed first;
price changes are measured on proposed yearly staffing, so interactions are not
double counted. All annual components reconcile to the existing calculation.

Site Xtown: Year 0 SGD 650,400/year; average budget SGD 891,198.15/year;
change SGD 240,798.15/year (+37.02%). Average drivers: headcount SGD 177,600
(73.75%); general increase SGD 28,382.66 (11.79%); PWM SGD 34,815.49 (14.46%).
Full contract total remains SGD 5,347,188.90.

Missing current quantities/rates or incompatible units disable the comparison,
without replacing unknowns with zero or blocking the normal budget. Excluded roles
with known current workers remain in the baseline. Yearly staffing changes and
reductions retain signed values. A zero Year 0 baseline has no percentage increase;
non-positive net changes have no share-of-increase percentages. Negative chart
segments include annual-total markers. Nothing changes stored inputs, approvals,
calculations, pricing assumptions or the existing export.

Targeted checks cover annual reconciliation, average and shares, unknown versus
explicit zero, legacy units, removed roles, reductions, yearly staffing, UI Year 0
and headcount segments, plus existing results, scenario and confirmation checks.

Verification: `headcount-attribution-verified.log`: **24 passed in 35.25s**.
The running 8511 app also shows the Year 0 bar, separate headcount segment, average
annual metrics and three driver percentages. Ruff checks pass. No paid model
calls, benchmark imports, deployment or additional integration were performed.
