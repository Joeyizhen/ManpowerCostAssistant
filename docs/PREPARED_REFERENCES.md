# Reference provisioning and evidence boundaries

## Clean-checkout route

A fresh checkout needs no private workbook. It uses the explicitly labelled synthetic fixtures under `data/sample` and authored example workbooks under `data/templates`. Set `MANPOWER_REFERENCE_SOURCE=synthetic` to select this route explicitly. These invented examples are not verified tender prices or evidence for market recommendations.

The Site Xtown example is created from code without copying the owner's saved-project database. The normal proposal sample leaves future assumptions to the shared review screens. Saving an example or preparing its inputs is not final officer approval.

## Private prepared-data route

Reference services can resolve versioned prepared snapshots from `MANPOWER_REFERENCE_DIR`, defaulting to `local_data/references`. A separately authorised installation provisions its approved `snapshots/<dataset-id>.json` files and `active.json` pointer through a private channel. Keep source hashes, mapping review, field origins, record controls and policy schedule metadata intact.

No workbook, raw record population or private activation pointer is published. The current owner's v3 activation remains local and unchanged. Older v2 investigation reports are historical and must not be interpreted as deployment instructions. Consolidation does not import, clean, regenerate reference records or activate a version.

`scripts/import_references.py` and `scripts/reference_report.py` are developer tools for separately authorised reference administration; they are not required for app startup. Review the tools and the team's approved data instructions before use. Diagnostic reports can contain private source detail and must stay local. Do not run an import or activation merely because a deployment lacks private sources.

## Evidence meaning

- Original titles, seniority, combined duties, quantity units, provenance and unknown values remain distinct.
- Quoted monthly charges do not establish salary or a comparable full-time worker price. Dedicated/shared allocation, hours, relief and inclusions need independent evidence.
- Source observations and submission representatives have different statistical meanings. Repeated property/role lines must not increase a submission's statistical weight.
- Annual changes use eligible consecutive contract-year unit-rate pairs with a stable role/basis, then line/submission aggregation. They are quoted charge movements, not measured inflation. Missing years are not bridged.
- Three independent submissions are required by the prepared-reference recommendation rules; statistical support alone does not certify operational comparability.
- Unknown actual calendar pricing years and award outcomes remain unknown. Synthetic completed dates are excluded from real calendar adjustment.
- Where no aligned starting-rate recommendation is supported, editable authored illustrative ranges remain labelled as assumptions.

Private source examples, record identifiers, exact quotations and saved-project snapshots are retained locally for traceability. They are not copied into this public/shareable methodology document.

## PWM and saved decisions

The checked-in dated MOM policy catalogue is separate from imported observations and contractor-charge averages. Importing observations does not certify policy category, wage basis, effective dates or worker eligibility, and must not overwrite the policy catalogue without review. No salary split or employer-cost rate is inferred.

Accepted project evidence retains its recorded dataset/method/IDs. Keep those original snapshot files privately with restored projects if full source rows are required. Missing snapshots must not cause substitution from a different active source. Changing a global source does not automatically reprice saved budgets or approve decisions.

## Validation

Importer/query tests use invented workbooks. They exercise source relationships, exclusions, versioning, weighting, annual gaps, comparability, retained fingerprints and both activities. Current results are in [VALIDATION.md](VALIDATION.md). This consolidation performs no source refresh or policy re-verification.
