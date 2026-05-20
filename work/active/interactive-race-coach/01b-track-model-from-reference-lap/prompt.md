# Slice 01b: Track Model From Reference Lap

## Goal

Generate a reviewable track coaching model from a valid reference lap, using the reference lap telemetry to estimate corner apex distances for that specific circuit/layout and car.

The output model must include the car identity because apex-distance proxies can vary by car class, braking profile, grip level, and line. A Barcelona model derived from one car/reference lap must not silently be treated as universal truth for every car.

## Problem

`product/data/track-coaching/circuit-de-barcelona.json` is currently hand-authored. Its `apex_s_m` values are consumed by the coach, but they are not derived from the reference lap. This can make the coach sample the wrong entry/apex/exit points and rank misleading losses.

We need a deterministic script that inspects the reference lap and proposes a circuit coaching model whose corner apex distances are based on telemetry-derived local speed minima.

## Non-goals

- Do not build live coaching.
- Do not modify the LLM prompt contract.
- Do not overwrite existing track-coaching JSON without an explicit flag.
- Do not claim geometric apex detection. This slice detects a telemetry apex proxy, usually the local minimum-speed point.
- Do not solve every multi-apex/flat-out corner perfectly. Produce reviewable candidates and diagnostics.

## Required Behavior

Create a script, for example:

```bash
python3 dev/scripts/generate_track_coaching_model_from_reference.py \
  --reference-lap product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet \
  --track-id circuit-de-barcelona \
  --layout-id lmu-default \
  --out work/active/interactive-race-coach/01-offline-fact-generator/artifacts/circuit-de-barcelona.generated-track-coaching.json
```

The script must:

1. Load a reference lap Parquet file.
2. Require these columns if present in the current schema:
   - `lap_distance_m`
   - `speed_kph`
   - `lap_time_s`
   - `lap_number`
   - a car/vehicle identity column if available.
3. Determine and serialize the reference car identity.
   - Prefer an existing vehicle/car column if present.
   - If no car column exists in the Parquet schema, read from sidecar metadata if available.
   - If no car identity can be found, fail with a clear error unless `--car-id` is supplied.
4. Resample speed onto a 1-meter distance grid using the existing Python resampling helper or equivalent deterministic interpolation.
5. Smooth speed enough to avoid noisy one-sample minima.
6. Detect candidate apexes as meaningful local minima in speed.
7. Estimate corner zones around each candidate:
   - `s_start_m`: where speed begins a sustained drop before the local minimum.
   - `apex_s_m`: local minimum-speed distance.
   - `s_end_m`: where speed recovery stabilizes after the local minimum.
8. Emit a JSON coaching model compatible with the current loader, plus car metadata.
9. Emit a human-readable diagnostics report explaining every detected candidate.

## Proposed Output Schema

Keep current schema fields compatible with `load_track_coaching_model()`, but add reference metadata fields that the loader can ignore or validate in a later slice:

```json
{
  "schema_version": "1",
  "track_id": "circuit-de-barcelona",
  "layout_id": "lmu-default",
  "reference_lap": {
    "path": "product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet",
    "car_id": "dkr-engineering-4-elms25",
    "lap_time_s": 96.456,
    "detection_method": "speed_local_minimum_v1"
  },
  "lap_length_m": 4657.0,
  "corners": [
    {
      "id": "t1",
      "name": "turn 1",
      "s_start_m": 780.0,
      "apex_s_m": 829.0,
      "s_end_m": 870.0,
      "apex_side": "unknown"
    }
  ],
  "straight_zones": []
}
```

If `apex_side` is still required by the current validator, choose one of these implementation options:

- Prefer deriving it from an existing annotation/outline source if reliable.
- Otherwise add a script option like `--default-apex-side right` only for provisional generated output.
- Or emit a separate candidate JSON that is not accepted by the production loader until reviewed.

Do not invent precise apex sides silently without documenting the source.

## Algorithm Guidance

A simple first implementation is acceptable:

1. Sort telemetry by `lap_distance_m`.
2. Resample `speed_kph` onto integer meters.
3. Smooth with a centered rolling median or moving average, e.g. 7-15m window.
4. Compute local minima where:
   - speed is lower than nearby samples within a configurable radius;
   - speed drop/prominence exceeds a threshold, e.g. 5-10 km/h;
   - candidates are separated by a minimum distance, e.g. 60m.
5. For each candidate, walk backward until speed stops increasing backward / the braking slope weakens to estimate `s_start_m`.
6. Walk forward until speed recovery weakens or a max zone size is reached to estimate `s_end_m`.
7. Reject candidates that are too shallow, too close to lap boundaries, or inside another accepted candidate zone.

The script should expose thresholds as CLI flags with sensible defaults.

## Diagnostics Required

Write a text or JSON diagnostics artifact beside the generated model. It must include, per candidate:

- corner id
- `s_start_m`
- `apex_s_m`
- `s_end_m`
- min speed at apex
- entry speed at start
- exit speed at end
- speed drop before apex
- recovery after apex
- rejection reason for rejected candidates, if practical

Example diagnostics lines:

```text
t1 apex=829m start=781m end=872m min=116.3kph drop=102.4kph recovery=38.0kph accepted
t2 apex=941m start=890m end=987m min=122.1kph drop=31.5kph recovery=44.2kph accepted
```

## Testing

Before changing tests, read `docs/TESTING_LESSONS.md`.

Add a test script such as:

```text
dev/scripts/test_generate_track_coaching_model_from_reference.js
```

The test should follow the repo test protocol: each assertion prints `[PASS]` or `[FAIL]`, exits non-zero on failure, and can be run through:

```bash
bash scripts/test-summary.sh dev/scripts/test_generate_track_coaching_model_from_reference.js
```

### Unit Tests

Use synthetic telemetry generated inside the test. Verify:

1. A single V-shaped speed trace produces one apex at the expected distance.
2. Two separated V-shaped speed traces produce two corners in distance order.
3. Noise around the minimum does not create duplicate apexes.
4. Min-distance merging keeps the strongest candidate.
5. Missing car identity fails unless `--car-id` is provided.
6. The generated JSON includes reference metadata with `car_id`.

### Integration / Golden Test

Run the generator against the Barcelona reference lap:

```bash
python3 dev/scripts/generate_track_coaching_model_from_reference.py \
  --reference-lap product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet \
  --track-id circuit-de-barcelona \
  --layout-id lmu-default \
  --car-id dkr-engineering-4-elms25 \
  --out /tmp/circuit-de-barcelona.generated-track-coaching.json \
  --diagnostics-out /tmp/circuit-de-barcelona.generated-track-coaching.diagnostics.txt
```

Assert the generated output:

1. Is valid JSON.
2. Includes `reference_lap.car_id`.
3. Includes sorted, non-overlapping corner zones.
4. Includes apex distances near the visually observed Barcelona reference minima, within a review tolerance:
   - t1 near 829m
   - t2 near 941m
   - t3 near 1162m
   - t4 near 1730m
5. Includes diagnostics for accepted candidates.

Use tolerances rather than exact values, e.g. ±20m, because smoothing and thresholds may move the detected local minimum slightly.

### Manual Validation

After implementation, run:

```bash
bash scripts/test-summary.sh dev/scripts/test_generate_track_coaching_model_from_reference.js
bash scripts/test-summary.sh
npm run build
```

Then inspect the generated diagnostics and compare candidate distances against the telemetry UI. The generated model is not considered trusted until the first-sector candidates match the known visual checks above.

## Acceptance Criteria

- A generator script exists and runs from repo root on macOS/Linux and from PowerShell on Windows using normal Python path handling.
- The script can generate a reviewable Barcelona model from the existing reference lap.
- The output records the reference car identity.
- Tests cover synthetic apex detection and Barcelona reference-lap smoke behavior.
- Existing tests pass.
- `npm run build` succeeds.
- `handoff.md` and `learnings.md` are created for this slice if/when implemented.

## Definition of Done

- [ ] Script implemented.
- [ ] Tests added and passing.
- [ ] Generated Barcelona artifact written under this slice's `artifacts/` folder, not silently replacing product data.
- [ ] Diagnostics artifact written under this slice's `artifacts/` folder.
- [ ] Full test suite passes.
- [ ] Build succeeds.
- [ ] Handoff documents the algorithm, thresholds, generated files, and how to review them.
- [ ] Learnings documents limitations, especially multi-apex and car-specific behavior.
