# Project write-up

## Purpose

The FM Manpower Cost Assistant is a university capstone prototype supporting officers who prepare manpower budgets and review tender submissions. It combines structured inputs, deterministic cost calculations, traceable evidence and optional AI explanation. An officer retains responsibility for input interpretation, assumptions, confirmations and procurement decisions.

## Two agents, one application

Agent 1 covers Track 1 (build a budget) and Track 2 (review a proposed budget). Agent 2 is the teammate's implementation and covers Track 3 (compare submissions against an approved budget) and Track 4 (historical tender-price review). Both agents start from `app.py` through Manpower budgeting or Tender evaluation. Track 5 historical-data maintenance remains planned.

Track 1 has five visible screens: Project, Deployment, Starting rates, Annual changes and Budget. Deployment is headcount-first and preserves original titles, seniority and combined duties. Original/current staffing remains distinct from proposed staffing. Rates can use clearly labelled authored illustrative ranges where comparable reference evidence is unavailable. General increases and eligible salary-component PWM remain separate.

Track 2 starts with an uploaded proposal. Captured inputs populate the shared budgeting screens; officers complete material gaps without retyping supplied facts. Exact uploads, original figures and accepted revisions remain separate. A blank template and an ordinary mixed-manpower sample are included. An intentional-error workbook is retained for regression rather than offered in the normal journey.

Agent 2 accepts verified budget/submission schedules, reviewable role matches, deterministic comparisons, clarification decisions and workbook exports. Tender-review project JSON provides download/resume. This is distinct from Agent 1's owned saved-project revision store. Trusted live-budget transfer, authenticated management approval and dedicated like-for-like cross-tenderer comparison are not complete.

## Architecture and safeguards

The Streamlit interface calls shared Python services for models, calculations, workflow gates, evidence, persistence and exports. Optional assistant tools interpret or propose reviewable changes; Python remains authoritative for arithmetic. Saving, previewing, accepting proposals, confirming inputs and final approval are separate events. Material edits invalidate dependent confirmations; unknowns are not converted into zero.

Budgeting calculations retain monthly charges, annual/base/option totals, dated salary-component treatment and explicit unpublished-period assumptions. Year 0 uses current quantities at selected starting rates, not actual historic spend. Average cost includes all base and option years. Net-increase attribution retains signed reductions and avoids invalid percentages for zero baselines/non-positive increases.

Versioned integration contracts and labelled synthetic handoff fixtures are included for independent development. Schema validity is not evidence of an authorised human approval. The current app does not automatically transfer an approved live budget or promote uploaded proposals into historical references.

## Data and evidence

A clean checkout runs on invented, explicitly labelled synthetic fixtures. Authored illustrative allowances are assumptions, not observed prices, employee salaries or verified market recommendations. Private workbooks, raw records, databases, uploads and development outputs are excluded from publication.

The shared reference services support separately provisioned private versioned snapshots with provenance, eligibility and retained decision evidence. The current local v3 activation is preserved; consolidation does not clean/import data or activate v2. Source title matches and quoted rates alone do not establish comparable staffing coverage, inclusions, award outcomes or calendar pricing years. The dated PWM catalogue needs applicability checks and does not justify an inferred salary split.

## Verification and limits

[VALIDATION.md](VALIDATION.md) records the combined offline regression and clean-publication checks. Synthetic calculation tests and mocked assistant tests do not establish real-model reasoning quality, validated market predictions or deployment readiness.

No paid evaluation or hosted deployment is performed. Real PostgreSQL/OIDC operation, native Excel recalculation, broader navigation performance and trusted cross-agent handoff remain unverified. Only Deployment loading has an isolated before/after improvement (26.01s to 1.67s); other step-switching lag remains outstanding.

See [setup/deployment](../DEPLOYMENT.md), [consolidation history](SPRINT2_INTEGRATION.md), [reference provisioning](PREPARED_REFERENCES.md) and [collaboration](COLLABORATION.md).
