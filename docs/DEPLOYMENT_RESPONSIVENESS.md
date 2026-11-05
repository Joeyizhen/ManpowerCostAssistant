# Deployment responsiveness — 30 October 2026

The Deployment page was simulating a complete prepare/apply/confirm transaction
just to decide whether to enable its action. An active-reference Site Xtown profile
measured 26.01 seconds, including 23 full findings passes and repeated PWM budgets.

Readiness now checks the officer draft's required inputs and retained quantity
basis directly, without preparing proposals or simulating confirmation. Actual
acceptance still validates the project and manpower and performs the normal
transaction. Missing values and stale/unaccepted assistant proposals still block.

Unchanged apply_change calls now return before calculating historical findings;
real changes retain their pre-edit findings history and invalidate later gates.
An already confirmed, unchanged deployment can Continue to starting rates without
reconfirming or clearing later approvals. Unconfirmed edits use Confirm and
continue; the other choice is Discuss deployment with AI. Both labels fit the
narrower screen. Hot reload rehydrates existing session facts, not a new project.

The same isolated active-reference profile now measures 1.67 seconds, with no
exceptions (`deployment-profile-before.log`, `deployment-profile-after.log`).
These are local profile measurements, not a guaranteed browser latency.

New regression checks exercise no-op versus real-edit invalidation, unchanged
continue without simulated acceptance, and specific missing-quantity blockers.
Existing workflow, officer journey, saved compatibility and shared proposal checks
also run with models disabled and isolated storage. User input and financial
calculation rules are not changed. No production project save/reset/confirmation,
paid model call, data-source activation or deployment is part of this fix.

Verification: affected regression had 67 passes and one new test whose mock also
blocked the unrelated Starting rates preflight. The mock was narrowed to Deployment;
all 3 focused responsiveness tests then passed in 25.38s. No application change
was needed for that test correction. Ruff/format checks pass. Live 937px browser
verification shows the enabled, untruncated Continue to starting rates control.
Workflow runtime marker is 2 and Deployment UI marker is 3. The user's current
unsaved session was refreshed without saving, resetting, or confirming it.
