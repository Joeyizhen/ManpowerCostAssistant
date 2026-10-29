# Shareable application contents

## Publication set

The consolidated app includes both agents, all required UI/controller/service modules, tests, versioned contracts, runtime/development dependency manifests, the lockfile, Docker packaging and blank private-configuration examples.

Publishable runtime data is limited to labelled synthetic JSON fixtures, reviewed title context, the dated PWM catalogue and three explicitly authored proposal workbooks:

- `data/templates/track2-blank-template.xlsx`
- `data/templates/track2-preplanned-budget-sample.xlsx`
- `data/templates/track2-example-proposal.xlsx` (deliberate-error regression fixture)

The ordinary sample and Site Xtown loader work on a clean checkout. No private prepared workbook/database is needed to launch both activities.

## Excluded material

Credentials, real secrets, private source workbooks/raw records, local databases, saved officer projects, uploads, local activation pointers, outputs/evidence logs, environments/caches and personal session handoffs remain local. The Git and Docker ignore rules enforce these boundaries. Original local working files and Git history were checkpointed before consolidation.

Shareable documentation explains methods and limits without reproducing private source quotations or saved-project identifiers. Historical implementation notes describe their dated milestones; the README, deployment guide and current consolidation report define current behaviour.

## Audit

Before publishing, review the exact staged list and run `python -m scripts.audit_shareable`. The script reads all indexed blobs, checks paths, credential/private-path patterns, explicit synthetic provenance, authored workbook structure and representative private exclusions. It complements manual privacy review.

Use a clean export/checkout containing only indexed files to verify both agents. [VALIDATION.md](VALIDATION.md) records actual checks and their limits. Never treat an older baseline audit as certification of a later index.
