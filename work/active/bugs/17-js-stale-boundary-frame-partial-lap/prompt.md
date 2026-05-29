# Bug 17: JS stale boundary frame makes a partial lap look complete and fastest

## Status

🐛 Open

## Observed symptom

In `dist/compare.html`, load:

```text
work/completed/bugs/16-slow-pitstop-lap-passes-guard/session_20260529T143959Z_bahrain-outer-circuit_lmu.parquet
```

Lap `19` is shown as a valid clean lap and receives the fastest-lap `★`, with
an apparent duration of about `51.085s`.

Visually, the plotted trace clearly ends shortly after turn 8 / before turn 9.
It is not a complete lap.

## Root cause

`product/web/js/pipeline.js` `annotateSegments()` currently computes segment
`minDist`, `maxDist`, and `duration` directly from the raw segment rows.

Lap 19 starts with stale cross-lap boundary frames:

```text
first frames of lap 19:
  lap_time_s ≈ -0.115s
  lap_distance_m ≈ 3509–3513m

then the actual lap starts:
  lap_time_s ≈ 0.085s
  lap_distance_m ≈ 3m

last useful frame:
  lap_time_s ≈ 51.085s
  lap_distance_m ≈ 2416m
```

Because the stale first frames are near end-of-lap, raw `maxDist` becomes about
`3513m`, which passes the current distance-completion guard:

```js
seg.maxDist >= trackLen * PARTIAL_DIST_FRAC
```

The lap therefore looks full-distance to the picker/star logic even though the
real usable lap only reaches about `2416m`.

## Relationship to earlier bugs

This is an unfixed **JS/UI edge case of Bug 12**, not Bug 16.

- Bug 12 handled stale/cross-lap frames for coaching/partial-lap comparison.
- Bug 16 handled full-distance laps that are implausibly slow.
- This bug is a UI segment-classification issue: stale start frames inflate
  `maxDist`, so an actually partial lap is treated as clean and can receive the
  fastest-lap star.

## Does Python have the same problem?

The Python coaching path already strips stale boundary frames in
`compare_laps()` before distance-coverage checks:

```python
not (lt < 0 and ld > track_model.lap_length_m * 0.5)
```

So coaching should reject lap 19 as partial after stale-frame removal.

The visible failure is in the JS `compare.html` picker/star path, where
`annotateSegments()` has not applied the same stale-boundary filtering before
computing segment coverage.

## Proposed solution

Update `product/web/js/pipeline.js` `annotateSegments()` so `minDist`, `maxDist`,
and duration-related segment metadata ignore stale start-boundary frames.

Use the same concept as `computeKeepIndices()` / Python `compare_laps()`:

```text
ignore rows where:
  lap_time_s < small threshold
  and lap_distance_m > estimatedTrackLen * 0.5
```

Because `annotateSegments()` currently computes `trackLen` while scanning
segments, the simplest safe implementation is likely two-pass:

1. First pass: compute a raw track length estimate across all segments.
2. Second pass: compute each segment's `minDist`, `maxDist`, and duration from
   rows that are not stale boundary frames.
3. Continue with existing partial/rolling/fastest logic.

After this fix, lap 19 should have effective coverage roughly:

```text
minDist ≈ 3m
maxDist ≈ 2416m
```

and therefore:

```text
partial = true
fastest = false
```

## Tests to add

### 1. `test_js_stale_boundary_frame_marks_lap_partial`

Create a JS regression test that imports `product/web/js/pipeline.js` and builds
synthetic segments:

- Track length about `3500m`.
- One normal complete lap reaching `3500m` in about `71s`.
- One lap with stale first frames near `3500m` and negative `lap_time_s`, then
  real data from `0m` to only `2400m` in about `51s`.

Call:

```js
annotateSegments(segments, distances, lapTimes, scoringLastLapTime)
```

Assert:

```js
partialLap.maxDist < 2500
partialLap.partial === true
partialLap.fastest === false
```

### 2. `test_real_lap19_not_fastest`

Use the real repro file:

```text
work/completed/bugs/16-slow-pitstop-lap-passes-guard/session_20260529T143959Z_bahrain-outer-circuit_lmu.parquet
```

Load its `lap_number`, `lap_distance_m`, `lap_time_s`, and
`scoring_last_lap_time_s` columns through the same JS pipeline test helper or a
small Python extractor feeding JS arrays.

Assert for segment/lap number `19`:

```js
seg.partial === true
seg.fastest === false
seg.maxDist is around 2416m, not 3513m
```

### 3. Existing behavior guard

Add/keep an assertion that a normal complete lap in the same file remains clean:

```js
lap 18 partial === false
```

This prevents over-filtering legitimate finish-line samples.

## Acceptance

- `dist/compare.html` marks lap 19 from the repro session as `partial`.
- Lap 19 no longer receives the fastest-lap `★`.
- Normal full laps in the same session remain unflagged.
- Existing Bug 12 and Bug 16 tests still pass.
- `bash scripts/test-summary.sh --feature interactive-race-coach` passes.
- `npm run build` succeeds and updates `product/dist/compare.html`.
