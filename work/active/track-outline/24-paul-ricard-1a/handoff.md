# Handoff — Slice 24: Paul Ricard 1A / Ginetta P3 reference, model and layout

## Result

- **Reference** `product/data/reference-laps/paul-ricard---1a_dkr-engineering-4-elms25_time_01.46.834.parquet`
  — lap 10 of `session_20261101T190458Z_paul-ricard---1a_lmu_race`, authoritative
  time **106.833862305 s**, 5323 rows, valid throughout. Exactly one reference now
  exists for this (track, car); the guarded exporter's audit added one and
  superseded none.
- **Model** `product/data/track-coaching/paul-ricard---1a_dkr-engineering-4-elms25.json`
  (+ `.diagnostics.txt`) — 14 curated zones, `layout_id: 1a`, `lap_length_m` 5696.9.
  Names come from the official all-configurations plan; **four full flat bends**
  (`verrerie_1`, `verrerie_2`, `mistral`, `garlaban`) carry `target_throttle_pct: 100`.
- **Outline** `product/data/track-outlines/paul-ricard---1a.json` — 500 centerline
  points, 500 per synthetic ±5 m boundary, 14 turn anchors on the same
  `lap_length_m` axis, compact-formatted to stay inside the file ceiling.
  Registered as `paul-ricard---1a` and `paul-ricard-1a` in
  `product/web/js/trackOutlineManifest.js`, module
  `product/web/js/staticPaulRicard1aOutlineData.js`.
- **TinyPedal** (sibling repo) — 14 official turn labels published as
  `data(track map): publish distinct Paul Ricard 1A official turn labels` (`e4b9ae06`),
  track-only, same-axis fractions. Real widget QA passes at 400/600 px × 0/90°.
- **Standalone build** rebuilt: `product/dist/compare.html`, 140 lines, byte-identical
  to a fresh `npm run build` (`artifacts/build-current.txt`).

This is **original 1A**, not 3A and not 1A-V2-Short: shallow flat first Verrerie
bends, uninterrupted Mistral (no chicane), full double-right Beausset loop. No
existing Paul Ricard asset was modified.

## Source and safe selection

`session_20261101T190458Z_paul-ricard---1a_lmu_race`, DKR Engineering #4:ELMS25
(catalogued slug `dkr-engineering-4-elms25`). The recording arrived as 84 closed
`partN` shards; they were frozen into ignored scratch (`var/tmp/paul-ricard-1a/`),
never merged, and the 17 overlapping `snapN` snapshots were excluded. Source
hashes before/after and the segment-aware candidate scan are in
`artifacts/source-manifest.json`, `artifacts/before-hashes.json`,
`artifacts/session-scan.txt`, `artifacts/comparison-extraction.txt`.
Selection is by segment, never by `lap_number=`, because the race contains a
sim restart (`artifacts/comparison-extraction.txt` shows 18 segments for 18
claimed laps, with segment 1 and 18 invalid). Qualifying lap 4 (107.091 s) was
seen and rejected as slower; the race lap is **0.257 s** faster.

`artifacts/scope-audit.json`: source hashes unchanged, the exported segment is
byte-equal to the reference, **139 other curated assets unchanged**, and
`artifacts/reference-validation.txt`: **34 reference laps, 0 failures**.

## New helpers worth knowing

`dev/scripts/create_paul_ricard_1a_assets.py` (150 lines) is a **one-shot
initializer**, not a general tool. It:
- asserts the detector produced exactly six brake/lift events at
  `[1480, 1600, 3871, 4394, 4732, 5377]` (six events are **not** six corners),
  restores the four WOT bends, and subdivides Hotel/Camp, Beausset and Lac/Pont
  from real steering/pedal signals;
- refuses to run against any reference other than the guarded 1:46.834 file;
- refuses to overwrite a *differing* existing model/outline and refuses to write
  a file above 437 lines;
- reuses `bake_outline_turns.bake_turns`, `trajectory_to_outline.resample_polyline`
  and `compute_boundaries`, so anchors stay on the model's distance axis.
For any future faster reference, use `dev/scripts/update_reference_and_coaching_model.py`
instead — do not re-run this initializer.

`dev/scripts/test_paul_ricard_1a.py` (131 lines, spawned from the thin
`test_paul_ricard_1a.js` wrapper per TESTING_LESSONS L12) guards: exactly one
1A/P3 reference, model exists with 14 zones / 4 flat, distinct layout id,
500-point outline with ±5 m synthetic boundaries, `lap_length_m` parity with the
model, all 14 turn anchors in range and inside the official names, no aliasing of
3A / 1A-V2-Short, and exact module↔JSON equality.

## Tests

- Feature `--pw --feature track-outline`: **945 assertions / 26 scripts pass**.
- Full `--pw`: **1954 passed, 6 scripts failed** — all six are the pre-existing
  Node-on-Windows ESM issue below, reproduced unchanged on a clean HEAD worktree.
- `artifacts/full-suite.txt` records both runs and the HEAD reproduction.

### Pre-existing failures (not this slice — do not "fix" here)

`test_static_outline_runtime_rendering`, `test_apex_annotations`,
`test_apex_metrics`, `test_apex_metrics_aggregate`,
`test_apex_metrics_surface_terrain`, `test_track_outline_schema_compat` all die on
`await import(path.join(ROOT, ...))` with
`ERR_UNSUPPORTED_ESM_URL_SCHEME ... Received protocol 'c:'` on Node v22.22.3.
They need `pathToFileURL()` like the newer tests already do. That is a separate
bug; slice 24 touches none of those files.

### Host prerequisites

- `python3` must resolve to a real interpreter. On this workstation only
  `python.exe` existed in `%LOCALAPPDATA%\Programs\Python\Python310` plus a
  WindowsApps `python3` stub (exit 9009), so five python-wrapper tests failed with
  "Python was not found". Adding a `python3.exe` beside `python.exe` fixed it; the
  repo was not changed for this.
- Export `PYTHONUTF8=1`, otherwise those wrappers crash with
  `UnicodeEncodeError: 'charmap' ... cp1252`.

## User action / remaining work

- **Restart the coach** (and reload TinyPedal's map) so the new reference, model
  and label file are picked up; a running process may still hold the previous
  1A state or a cached session.
- **Live by-eye confirmation is still pending** — `visual_qa.status` is `pending`
  and the automated `file://` render (`artifacts/compare-outline.png`,
  `artifacts/paul-ricard-1a-{400,600}-{0,90}.png`) must not be reported as human
  approval.
- Deferred TODOs: real (measured) 1A widths instead of the synthetic ±5 m shell;
  the six pre-existing ESM test failures above.

## Untouched on purpose

`coach-race.log` at the repository root is a runtime artifact of a live coach
session. It was not read, modified, staged or deleted.

Unrelated prior local commits were not pushed. Everything for this slice is
committed directly on `main` (and `master` in the TinyPedal repo); no other slice
was started.
