# Public release review

Reviewed on 2026-10-04.

- Removed video provenance filenames and added composite case IDs
- Preserved source prompts, labels, scoring fields and syllable modules
- Introduced engine-independent saved-prediction evaluation and configuration-keyed Judge cache
- Strict score parsing, fixed missing-prediction denominator, slope and per-group summaries
- Removed internal endpoint; supplied dependencies and dataset card

Validation checks cover dataset loading, input/reference separation, source hashes, IDs and offline scoring behavior. No paid Judge calls or full model inference were run. Historical leaderboard numbers are source-reported results, not remeasured in this release.
