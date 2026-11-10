# Handoff — Slice 01: session lap inventory

## State on disk

New modules:

| File | Job |
|---|---|
| `product/python/lap_telemetry/session_laps.py` | Enumerate and classify the laps of a session |
| `product/python/lap_telemetry/debrief.py` | `lap-telemetry debrief` entry point (`--list` only, for now) |
| `product/python/lap_telemetry/coach/lap_table.py` | Table slicing + lap-duration helpers, extracted from `lap_comparator` |

Changed:

- `product/python/lap_telemetry/coach/lap_comparator.py` — imports the helpers
  from `lap_table`; **357 lines** (was 422, ceiling is 437).
- `product/python/lap_telemetry/cli.py` — new `debrief` subcommand with
  `--list`.
- `package.json` — `testFeatures["session-debrief"]` now includes
  `dev/scripts/test_session_lap_inventory.js` (14 scripts total).
- `docs/specs/session-debrief-coach.md` — `invalid` added to the lap class
  table (the `lap_valid` rule needed a status to report).

Tests: `dev/scripts/test_session_lap_inventory.py` (+ `.js` wrapper), 41
assertions, including the real 25-segment Paul Ricard fixture and a temp-dir
shard-merge case.

## Commands

```bash
bash scripts/test-summary.sh --feature session-debrief        # 19 scripts, 484 assertions, green
bash scripts/test-summary.sh                                 # 1553 passed, 4 pre-existing failures
```

The full suite has four failures on this machine that also fail at the
pre-slice baseline `1417653` (verified in a `git worktree`): two duration tests
that need untracked recordings under `sessions/`, `test_turn_labels_parity`
(needs `../tinypedal/.venv`) and `test_turn_labels_scale` (160/161 named turns).
`dev/scripts/test_nonblocking_coach_pipeline.js` also fails at baseline and is
not part of `package.json` `scripts.test`.

PYTHONPATH=product/python python3 -m lap_telemetry debrief \
  dev/sessions/session_20260524T141613Z_paul-ricard---3a_lmu.parquet --list
```

Expected on that fixture: 25 segments, 19 eligible, 17 clean, segment 0
`out-lap`, segment 16 (21.9 s) `in-lap`, segment 17 (119.1 s, stopped 8.4 s)
`pit-lap`, segments 23–24 `incomplete`.

`npm run build` was **not** run: this slice touches no `web/` file and no
`product/data/` file, so `dist/compare.html` cannot have changed.

## API worth knowing about slice 02

```python
from lap_telemetry.session_laps import load_session, classify_laps, LapStatus

session = load_session(path)          # merges .partN shards in memory
records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
eligible = [r for r in records if r.eligible]   # .clean tells you representatives
```

- `LapRecord.start_row` / `.end_row` are the half-open row range of the
  segment — feed them to `lap_table.slice_segment` to get one lap's table.
  **Do not filter by `lap_number`.**
- `LapStatus` constants: `ELIGIBLE`, `OUT_LAP`, `IN_LAP`, `PIT_LAP`,
  `INCOMPLETE`, `SHORT`, `INVALID`.
- `MIN_ELIGIBLE_LAPS = 5` is exported; the hard gate belongs to slice 02.
- `classify_laps` is session-relative (median interior lap as yardstick) and
  does not need a reference lap. Slice 02 must resolve the reference
  separately via `reference_resolver` / `track_model_resolver`.

## Deferred / next

- Slice 02: resolve the reference + coaching model for (track, car), compare
  every eligible lap at **segment** granularity, uncapped, and print
  `SessionDebriefFacts` JSON. This is where `compare_laps` gains a segment
  argument (or a table-taking sibling) — `lap_comparator` has ~80 lines of
  headroom now, but a new `compare_laps_table` wrapper in `lap_table`/a new
  module may be cleaner.
- Sector times (`last_sector_1_s` / `last_sector_2_s`) are **not** extracted
  yet; slice 03 owns them for the optimal-lap metric. The extraction logic
  currently lives inside `summary.py:_run_file` and will need lifting out.
- `debrief` without `--list` intentionally exits 1 with "not implemented yet".
- No `--json`, no `--track`/`--car` overrides, no output directory handling
  yet — all slice 02+.
- `sessions/` is gitignored; debrief artifacts will land there.
