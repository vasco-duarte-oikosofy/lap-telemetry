# Handoff — Slice 36 (Michelin Raceway Road Atlanta)

## What is on disk now (committed in `0494e0c`)

**Reference lap** (guarded export, fastest valid = lap 15 @ 1:17.345):
- `product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.17.345.parquet`
- Source session: `sessions/session_20261004T133118Z_michelin-raceway-road-atlanta_lmu_practice.parquet`
  (car `DKR Engineering #4:ELMS25` → catalog slug `ginetta-lmp3`,
  file car-id `dkr-engineering-4-elms25`).
- `validate_reference_laps.py` passes (26 refs, 0 failures). Legacy-time delta
  0.623 s vs `lap_time_s` is the known pre-authoritative export artifact.

**Coaching model** (curated, 13 entries = official 12 turns with 10A/10B split):
- `product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json`
  (+ `.diagnostics.txt`)
- Real braking corners: T1, T2, T3, T5, T6, T7, 10A, 10B.
- Flat/marker corners (real zones, `target_throttle_pct: 100`): T4 (Esses),
  T8, T9, T11, T12.
- The raw detector only found 7 of these; the rest were added manually from
  the speed/steering trace. `--print-facts` resolves every corner id.

**Track outline** (trajectory; no TUMFTM data for Road Atlanta):
- `product/data/track-outlines/michelin-raceway-road-atlanta.json` (500 pts)
- ES module `product/web/js/staticMichelinRacewayRoadAtlantaOutlineData.js`,
  manifest entry `michelin-raceway-road-atlanta`, `product/dist/compare.html`
  rebuilt (+~83 KB).
- `docs/TRACK_OUTLINE_COVERAGE.md` updated.

## Follow-up fixes (same slice, found during live use)

1. **Outline was invisible** (`b903909`, bundle in `cd1ef55`). Not an outline
data problem: `inferTrackNameFromFileName` (fallback used when the sidecar
JSON is not loaded) only matched `..._lmu.parquet`. Current recorder files are
`..._lmu_practice/_quali/_race.parquet`, so the track name came out `null` and
`findOutlineByTrackName(null)` never drew anything. Fixed the regex to accept
`_lmu[._]`; extracted the helper to `product/web/js/trackNameInference.js`
(`c396279`) so it can be unit-tested. Verified: Road Atlanta canvas outline
pixels 6 → 1363.

2. **Reference lap showed 1:16.722 instead of 1:17.345** (`cd1ef55` app,
`0e6978c` model/generator). Two consumers read `max(lap_time_s)`:
   - `annotateSegments()` in `pipeline.js` for a single-segment reference file
     (no next segment → no `scoring_last_lap_time_s`); now prefers the
     authoritative time parsed from `_time_MM.SS.mmm.parquet` via
     `parseReferenceLapTimeFromName()`.
   - the generator's `lap_time_s()`; now `parse_reference_lap_time_from_name()`
     with a `max(lap_time_s)` fallback. Existing Road Atlanta model patched to
     77.345.

New tests (registered in `package.json` `scripts.test`):
`dev/scripts/test_track_name_inference.js` and
`dev/scripts/test_reference_lap_duration.js`.

## Deferred / still open

- **Visual QA (slice 36-b)** has not been done by eye on this machine — the
  outline renders (1363 canvas pixels via headless probe, comparable to Spa's
  1823) but `visual_qa.status` in the outline JSON is still `"pending"`.
- `test_static_outline_runtime_rendering.js` and the other 5 outline/apex JS
  tests cannot run on this Windows box (dynamic `import()` of an absolute
  `c:\` path → `ERR_UNSUPPORTED_ESM_URL_SCHEME`). Manual `import()` of the
  manifest + module verified the outline resolves by slug and display name.

## Commands

```bash
python dev/scripts/validate_reference_laps.py
PYTHONIOENCODING=utf-8 python -m lap_telemetry.coach.generate_utterance --lap \
  --current-lap <lap.parquet> \
  --reference-lap product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.17.345.parquet \
  --track-config product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json \
  --print-facts
npm run build
```
