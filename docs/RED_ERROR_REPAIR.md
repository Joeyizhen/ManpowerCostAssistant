# Track 1 red-error repair — 28 October 2026

The reported red screen was reproduced on copies of both recent saved projects at Step 4. The prepared source quotations contain both integer and decimal monetary values. A slider with an integer minimum, decimal maximum and decimal step raised `StreamlitInvalidParameterTypeError`. Later-step attempts in an incomplete project returned to the same broken rates page, making the problem appear on multiple screens.

Starting-rate slider bounds, defaults and exact-entry limits now use consistent floats. The annual-increase range uses the same numeric convention. Development reload markers were updated so existing sessions load the corrected helpers without clearing their saved inputs.

A separate benchmark defect was reproduced: an unmapped role received a pooled reference across 20 roles and 79 submissions, assigning an unrelated starting rate. Role-specific rate, quantity and escalation retrieval now return insufficient evidence for a missing mapping. Explicit general-cohort annual analysis remains available. No existing rate or mapping is silently changed.

Regression coverage adds missing/blank/unmatched-role lookups, prevention of automatic rates for unmapped positions, and editing a slider with mixed integer/decimal source bounds. The affected run passed 38 checks; two additional existing pricing journeys timed out and then both passed in a separate 33.22-second rerun. Lint, formatting and compilation passed. Saved-project copies rendered the repaired rates page without exceptions or red messages; the older project's future-cost screen also rendered without red errors. A separate fresh results-screen check passed with all four tabs and no exceptions or red messages, and verified that the original saved record was byte-for-byte unchanged. The initial multi-screen results check timed out before this successful isolated rerun. No reference files were changed.

This repair does not suppress valid input requirements, approve assumptions, reprice saved budgets, publish the dataset, merge branches or make paid model calls. Broader visual simplification remains a separate task.
