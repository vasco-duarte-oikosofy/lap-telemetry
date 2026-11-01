# Handoff — Slice 39: Long Beach labels in TinyPedal

## Root causes

1. The recorded `../tinypedal/trackmap/Grand Prix of Long Beach.svg` existed,
   but `tinypedal/data/turn_labels/Grand Prix of Long Beach.turns.json` did not.
   A coaching model and compare.html bundle do not publish that separate file.
   Existing render tests enumerate shipped label files, so a missing track was
   silently absent from their test set.
2. Exported apex_s_m uses the simulator's 3185.3 m lap-distance axis. The outline
   trace is 3400.385 m long because of geometric backtracking/jitter. Dividing by
   that trace length instead moved later labels far upstream (up to ~180 m).

## Delivered changes

### lap-telemetry (main)

- `dev/scripts/export_turn_labels_for_tinypedal.py`: --track selects one TinyPedal
  map, matching case/accents/punctuation. Unknown maps fail instead of exporting
  everything. Default all-track behavior remains available.
- Explicit positive finite outline lap_length_m overrides geometric normalization;
  legacy outlines without it keep byte-identical prior output. Invalid explicit
  lengths are rejected, not silently repaired/fallback-normalized.
- Long Beach outline gains only `lap_length_m: 3185.3`. Creator carries it from
  the coaching model; its guarded rerun is a no-op. Generated JS and standalone
  compare bundle refreshed through existing tools.
- No coaching/ref/outline coordinate, apex, official number/name or flat zone
  was changed. Flat T3 and T7 remain exactly as curated in slice 38.
- New isolated export regression + Node wrapper (optionally runs the real sibling
  Qt integration). `track-outline` feature suite registered with guards/shared UI.
- Model-creation guide Step 8 and MAP_TURN_NAMES spec now document the separate
  track-only publishing/check/reload step to prevent recurrence.

### TinyPedal (master) — commit `2d8d5a65`

- Generated packaged `tinypedal/data/turn_labels/Grand Prix of Long Beach.turns.json`:
  all **11 official numbered turns**, fractional apices on the simulator axis.
  Names/short_names are null so the widget displays T1..T11, not spoken Ten/Eleven.
- `tests/test_long_beach_turn_labels.py`: explicitly requires Long Beach data,
  checks loader/recorded-map anchor proximity and actual widget paint at 400/600px,
  0/90 degrees. Every label must change pixels relative to labels-off, not merely
  exist in a layout plan. No overlaps or off-canvas labels; real fonts required.
- No widget/layout/painter code or user settings/maps were edited. Existing
  generic layout/render/widget tests pass. The new test was force-added because
  TinyPedal's existing test*.py ignore rule otherwise hides new regression files.

## Verification

- Red first: `artifacts/test-first-red.txt` (missing file, wrong normalization,
  unsupported --track and actual loader failure).
- Feature --pw: **718 assertions / 19 scripts pass**.
- Full --pw with LONG_BEACH_TINY_ALL_TESTS=1: **1915 assertions / 75 scripts pass**;
  includes all three existing TinyPedal turn-label regressions plus this one.
  Uses the pre-existing temporary Windows ESM-path loader (stock bug 20 unchanged).
- Focused sibling integration plus old TinyPedal tests: 117 assertions pass via
  `bash scripts/test-summary.sh dev/scripts/test_long_beach_tinypedal.js` with
  LONG_BEACH_TINY_ALL_TESTS=1. No external dependency skips occurred here.
- All 11 labels visibly painted at 400/600px, both 0/90 orientations. Four real
  widget PNGs in artifacts; not mock drawings or pixel goldens. Windows native
  Qt platform provides actual system glyphs (do not force the empty-font offscreen
  plugin). Review screenshots inspected; user live overlay approval still pending.
- Scoped --check passes; all-track read-only --check reports **15 current files**.
- `before-hashes.json` + `scope-audit.json`: every original 14 label file, Long
  Beach SVG, coaching model and reference lap unchanged. Removing the new scalar
  metadata makes the outline exactly equal to its original parsed data.
- Build succeeds, current dist/compare.html; diff whitespace checks pass.

## Reproduce / collect review images

From lap-telemetry with its venv on PATH and PYTHONUTF8=1:

```bash
python dev/scripts/export_turn_labels_for_tinypedal.py --track "Grand Prix of Long Beach"
python dev/scripts/export_turn_labels_for_tinypedal.py --track "Grand Prix of Long Beach" --check
bash scripts/test-summary.sh --feature track-outline --pw
LONG_BEACH_TINY_ALL_TESTS=1 bash scripts/test-summary.sh dev/scripts/test_long_beach_tinypedal.js
```

The wrapper uses the sibling venv and real recorded SVG if available. Without
that external environment it explicitly skips only Qt integration; hermetic
export/axis regressions still execute. PNGs are refreshed under ignored
`var/tmp/long-beach-tinypedal/`; committed review copies are in slice artifacts.

## User action / boundaries

**Restart TinyPedal or reload the Long Beach map.** The widget loads turn JSON
when its map updates, not through a file watcher; an already-cached missing-data
result will not magically reload. Show turn names is already enabled in the
existing local presets; no preset was modified.

Only this slice was implemented. User's untracked coach-race.log was not read,
changed or staged. TinyPedal's pre-existing untracked .venv/ and var/ were left
alone. Both repos use their native branches (main/master); no unrelated local
commits were pushed. Live in-game visual confirmation remains pending.
