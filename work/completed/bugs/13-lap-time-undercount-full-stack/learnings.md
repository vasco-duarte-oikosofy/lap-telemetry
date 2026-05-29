# Learnings — Bug 13

- `scoring_last_lap_time_s` is safe as the authoritative duration only when read from the immediately following segment for normal session files.
- Same-segment scorer fallback must be opt-in and is only used for extracted single-lap reference parquets; otherwise an in-progress/final session segment can inherit the previous lap's scorer time.
- Older Parquet files without `scoring_last_lap_time_s` remain supported by falling back to `max(lap_time_s)`.
- Existing Python bug tests had drifted into root `tests/`; they now live under `dev/scripts/` and are run by `dev/scripts/test_bug_python_regressions.js` so the Node test-summary protocol sees them.
