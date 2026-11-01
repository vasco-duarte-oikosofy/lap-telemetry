# Handoff — Slice 40: faster Long Beach / Ferrari 499P reference

## Result

- New reference: `product/data/reference-laps/grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm_time_01.14.871.parquet`.
- **Lap 7, 74.871093750 s, 3731 rows, valid throughout**. Previous lap was
  75.888671875 s: exact improvement **1.017578125 s** (displayed 1.018 s).
- Old `_time_01.15.889.parquet` removed by the guarded exporter. Still exactly
  one reference for this track/car and 33 references globally.
- Model: `product/data/track-coaching/grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm.json`.
  New reference path/time and seven refreshed braking-corner geometry triples.
  All 11 IDs, official names, spoken aliases, sides, targets, straight zones and
  layout/lap length retained. T3/T7 and reviewed T10/T11 dictionaries are unchanged.
- Raw eight-event detector diagnostics added beside the model. These detector
  indices are NOT the official 11-turn numbering; do not renumber the model from
  that diagnostic. The unclaimed 2828 m event is the preserved T11 hairpin, not
  an extra official corner.

## Source and safe selection

`sessions/session_20261101T175418Z_grand-prix-of-long-beach_lmu_practice.parquet`,
Ferrari AF Corse 2026 #50:LM. Initially only partN files/in-progress metadata
were present. During read-only inspection the recorder independently recovered
those into the canonical file (53817 rows, recovered=true, in_progress=false).
The incomplete shard-list check aborted before assembling anything; no partial
merge was used. Source SHA256 stayed stable through selection/update/audit.

Only the recovered canonical file was scanned. Overlapping snapN files were
excluded; source data/sidecar were not edited or cleaned up. Segment-aware scan
rejects the short apparent 50/16 s laps and garage/abandoned segments. See
artifacts/source-manifest.json and session-scan.txt for exact selection evidence.

## Why a small updater safety addition was necessary

The old read-only preview let flat T3 claim T4's braking event, T4 claim T5, and
T10 claim the combined hairpin event, leaving T5/T11 unmatched. --allow-unmatched
alone would keep the WRONG matched geometry. No default matcher rewrite was made.

`--preserve-geometry <stable-id> ...` now explicitly excludes reviewed corners
from event claiming and keeps their full dictionaries. Unknown IDs fail closed
before product writes. These intentional preservations don't require
--allow-unmatched; any other unexpected unmatched corner still aborts.
The remaining matched corners still pass the ordinary pre-export geometry guard.
Reference paths are serialized with as_posix() for portable committed data.

```bash
export PATH="$PWD/.venv/Scripts:$PATH" PYTHONPATH="$PWD/product/python" PYTHONUTF8=1
python dev/scripts/update_reference_and_coaching_model.py \
  --session sessions/session_20261101T175418Z_grand-prix-of-long-beach_lmu_practice.parquet \
  --track-id grand-prix-of-long-beach \
  --preserve-geometry t3 t7 t10 t11 --max-geometry-delta-m 25
```

Seven automatic matches passed (largest change: T4 exit +21 m). Retained T3/T7
zones are still genuinely full-throttle/no-brake left bends on the new lap, and
T10/T11 retain opposite steering directions and their real split. Detailed
before/after triples and measured signals: artifacts/corner-review.md.
Re-running the same command is a no-op: artifacts/idempotent-refresh.txt.
Do not rerun the frozen slice-38 asset creator on this already-curated model.

## Map consistency

- Re-baked all 11 anchor positions/tangents against the new reference and updated
  changed apex distances. Map names remain T1..T11 (not spoken Ten/Eleven).
- Centerline and both 500-point synthetic boundary arrays remain exactly unchanged.
- `turns_reference_lap` points to the new ref. Geometry's old alignment source
  stays historical; `alignment.reference_lap_revision` pins the original 90c6e6e
  Git version so its superseded reference can be recovered without pretending
  the retained outline was generated from the new lap.
- Generated outline JS and standalone compare bundle current.
- TinyPedal **master commit `2e45c0eb`** refreshes only the Long Beach packaged
  fractions. All 11 labels remain painted at 400/600px and 0/90 degrees, with no
  overlaps/off-canvas labels. Real-widget and compare review PNGs are in artifacts.

## Verification

- Red first: artifacts/test-first-red.txt. New preservation and pre-export-abort
  tests live in test_update_coaching_model.py; current-reference data/UI tests
  resolve the model's path instead of hardcoding the original reference filename.
- Feature --pw: **804 assertions / 23 scripts pass**.
- Full --pw with sibling Qt regressions: **1931 assertions / 75 scripts pass**,
  using the existing temporary Windows ESM-path loader; bug 20 unchanged.
- Whole-folder reference validator exits 0: **33 refs, zero failures**, with the
  exact new canonical source identified. The legacy-time note compares raw sampled
  lap_time_s to the authoritative time; do not rename the ref from that fallback.
- Export audit changes ONE reference. Scope audit: **79 other reference/model/
  TinyPedal-label files byte-unchanged**, all curation and four reviewed corner
  dictionaries unchanged, all outline coordinates and source recording unchanged.
- --print-facts on segment-extracted lap 6: **+1.322 s** against new ref, valid
  official IDs/aliases. Reference-vs-itself: delta 0, no losses/gains.
- Track-only export plus all-track --check: 15 TinyPedal label files current.
- Build and whitespace checks pass. No recording/CPU-performance code changed.

## User action / remaining work

**Restart the coach**: its session caches may still contain the deleted old ref
and previously loaded model. Restart/reload TinyPedal to pick up refreshed anchors.
Live by-eye confirmation remains pending, not claimed by automated render tests.

The user's coach-race.log was not read/modified/staged. Existing TinyPedal .venv/
var/ remain untouched. No other slice was started; changes stay on native
main/master branches and unrelated prior local commits were not pushed.
