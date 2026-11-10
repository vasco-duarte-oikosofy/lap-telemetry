# Bug 33 — The coach re-derives a reference lap's duration instead of using its certified time

## Symptom

The live coach's lap summary and the session debrief measure the same lap
against the same reference file and disagree by up to ~1 s, because they use
different reference baselines.

Paul Ricard 3A / DKR Ginetta, reference
`paul-ricard---3a_dkr-engineering-4-elms25_time_01.17.166.parquet`:

| quantity | value |
|---|---|
| filename (certified by the export) | **77.166 s** |
| `authoritative_duration()` on the extracted file | **77.626 s** |
| `max(lap_time_s)` in the file | 76.978 s |

`compare_laps()` reports `lap_time_delta_s = driver_lap − 77.626`, so every lap
of that combo reads **0.46 s worse** than it is. Across the 35 committed
references the re-derived value differs from the filename by up to **0.97 s**,
in both directions:

| track | filename | re-derived | Δ |
|---|---|---|---|
| Lusail International (DKR) | 111.975 | 112.948 | +0.973 |
| Laguna Seca (DKR) | 81.495 | 82.298 | +0.803 |
| Bahrain International (DKR) | 116.052 | 116.620 | +0.568 |
| Enzo e Dino Ferrari (DKR) | 100.607 | 101.107 | +0.500 |
| Paul Ricard 3A (DKR) | 77.166 | 77.626 | +0.460 |
| Paul Ricard 1A v2 Short (Ferrari 296) | 96.804 | 96.604 | −0.200 |

23 of the 35 references have no `authoritative_lap_time_s` stamp and are
affected. The 12 stamped ones are exact.

Per-corner losses are **not** affected: they come from the delta-t trace of the
two speed profiles. What shifts is the lap-level number the driver hears
("you lost four tenths") and, later, the debrief's share-of-gap ranking.

## Root cause

`authoritative_duration()` (bug 13/21/28) prefers, in order: explicit
`authoritative_lap_time_s` metadata → the difference between consecutive
**telemetry** lap-start ETs → the scorer's `scoring_last_lap_time_s` →
`max(lap_time_s)`.

An extracted reference lap is a **single segment** with no successor, so the
telemetry-clock method has nothing to difference. With no metadata stamp it
falls through to `scoring_last_lap_time_s`, which lags one lap and reads high.
`compare_laps()` passes `allow_same_segment_scoring=True`, which is exactly what
lets that stale scorer value become the baseline.

## What has already been tried — and why the coach was missed

The filename was established as the source of truth for extracted references
three separate times, on every surface except the coach:

| Commit | Surface | What it did |
|---|---|---|
| `cd1ef55` | **web UI** (`product/web/js/pipeline.js`) | `annotateSegments()` trusts the filename for single-lap reference files: `durationSource = 'reference_lap_filename'` ("file is a single contiguous lap, so trust the filename over both clocks") |
| `0e6978c` | **model generator** (`generate_track_coaching_model_from_reference.py`) | `parse_reference_lap_time_from_name()` — the model records the filename time as `reference_lap.lap_time_s` |
| `761de5d` | **duration primitive** (bug 28) | Introduced the telemetry-clock priority and `authoritative_lap_time_s`, deliberately replacing the scorer; correct for *sessions*, and it never reaches the filename |
| `c16abce` | **metadata stamps** | Stamped the manual Road Atlanta extract; 12 of 35 references now carry the stamp |
| `b9d…`/`c16abce` | tests | `test_reference_lap_duration.js` (JS filename rule) and `test_lap_duration_surfaces.py` (metadata stamp) cover web and export |

Every one of those fixes assumed the *consumer* would either be the web UI, the
model generator, or a stamped file. `lap_comparator.py` is none of the three: it
predates the filename rule, was migrated to the telemetry clock in `58f9f8b`
(bug 13) and has re-derived ever since. `validate_reference_laps.py` treats the
filename as the reference value, so the repository has always agreed that the
filename is correct — the coach simply never asked.

The session debrief (slice 02 of `session-debrief`) hit the same wall and solved
it locally in `session_inputs.reference_lap_time_s()`. That is the fix the coach
needs, and it is currently unreachable from `coach/`.

## Fix

1. Move `reference_lap_time_from_name()` / `reference_lap_time_s()` from
   `session_inputs` into `coach/lap_table.py` (shared, low-level), keeping the
   debrief re-export or updating its import.
2. `compare_laps()` already has `reference_lap_path`; use
   `reference_lap_time_s(ref_table, reference_lap_path)` instead of
   `segment_duration(..., allow_same_segment_scoring=True)`.
3. Test: a reference file without metadata resolves to its filename time;
   one with metadata keeps the stamp; `compare_laps` on the Paul Ricard fixture
   reports the lap delta against 77.166, not 77.626.
4. Live-verify a spoken lap summary against the on-screen gap before closing
   (per the bug protocol: a bug moves to `work/completed/bugs/` only after the
   user confirms a successful live test).

## Why this is not being fixed inside slice 03 of `session-debrief`

Slice 03 (consistency) never uses the reference baseline: its baselines are the
session's own best lap and best sector times, and its corner spreads come from
the delta-t trace. Only the lap-level `delta_s` is affected, and that is not used
until slice 05 ranks "share of the gap". The fix changes the numbers the driver
hears on every spoken lap summary, so it needs its own commit and a live check.

## Status

🐛 Open. Filed during `session-debrief` slice 02. Depends on: nothing. Blocks:
`session-debrief` slice 05's share-of-gap ranking (and every spoken lap summary,
until fixed).
