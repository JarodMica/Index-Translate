# Public release review

Reviewed on 2026-10-04.

- Preserved data and model/Judge prompts
- Rejected invalid quality and missing soft-constraint Judge verdicts
- Corrected redaction-policy description

Validation checks cover dataset loading, input/reference separation, source hashes, IDs and offline scoring behavior. No paid Judge calls or full model inference were run. Historical leaderboard numbers are source-reported results, not remeasured in this release.
