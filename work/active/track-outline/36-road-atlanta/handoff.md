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

## Deferred / still open

- **Visual QA (slice 36-b)** has not been done on this machine — the outline
  has not been visually verified in the app at the right scale/position.
  `visual_qa.status` in the outline JSON is still `"pending"`.
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
