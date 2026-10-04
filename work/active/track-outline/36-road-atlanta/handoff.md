# Handoff — Slice 36 (Michelin Raceway Road Atlanta)

## What is on disk now (committed in `0494e0c`)

**Reference lap** (guarded export, fastest valid = lap 15 @ 1:16.809):
- `product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.809.parquet`
- Source session: `sessions/session_20261004T133118Z_michelin-raceway-road-atlanta_lmu_practice.parquet`
  (car `DKR Engineering #4:ELMS25` → catalog slug `ginetta-lmp3`,
  file car-id `dkr-engineering-4-elms25`).
- `validate_reference_laps.py` passes (26 refs, 0 failures). Provenance check
  matches the source session lap 15 at 76.809 s.
- The file carries schema metadata `authoritative_lap_time_s=76.809`.

> **Corrected 2026-10-04 (bug 28):** the first export named this file
> `_time_01.17.345` because our duration helper preferred the sim scorer's
> `mLastLapTime`, which lags a lap on Road Atlanta. The true in-game time is
> **1:16.809** (TinyPedal's recorded deltabest is 76.80896). See "Follow-up
> fixes" below.

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

## Refresh — new fastest lap, race 1:16.304 (2026-10-04, later)

Five Road Atlanta sessions now exist; the fastest valid lap is **race lap 15
in `session_20261004T164430Z_..._lmu_race.parquet` at 1:16.304**, faster than
the old practice 1:16.809. (The practice session `155735` shows a suspicious
1:15.994 for lap 22 with no sector times; the export guards correctly reject
it as restart-truncated/abandoned.)

- Reference refreshed via the guarded updater:
  `product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.304.parquet`
  (`_time_01.16.809` superseded and deleted; `authoritative_lap_time_s=76.304`).
- Coaching model refreshed from the new ref. The detector finds only 6 braking
  corners on this lap; the updater was run with `--allow-unmatched` so the 7
  unreproduced corners keep their curated geometry. **T4 (The Esses) is
  present** (880/1120/1300, `target_throttle_pct: 100`), as are T8/T9/T11/T12.
- Matched/refreshed geometry: T1, T2, T5, T6, T7, T10A. Kept geometry: T3,
  T4, T8, T9, T10B, T11, T12.
- Updater fix: `refresh_corners()` now copies curated fields (notably
  `target_throttle_pct`) when it applies new geometry, so a flat turn can
  never be stripped even if a neighbouring candidate matches it.
  Test: `dev/scripts/test_update_coaching_model.{py,js}`.
- `validate_reference_laps.py`: 26 refs, 0 failures.

## Follow-up fixes (same slice, found during live use)

1. **Outline was invisible** (`b903909`, bundle in `cd1ef55`). Not an outline
data problem: `inferTrackNameFromFileName` (fallback used when the sidecar
JSON is not loaded) only matched `..._lmu.parquet`. Current recorder files are
`..._lmu_practice/_quali/_race.parquet`, so the track name came out `null` and
`findOutlineByTrackName(null)` never drew anything. Fixed the regex to accept
`_lmu[._]`; extracted the helper to `product/web/js/trackNameInference.js`
(`c396279`) so it can be unit-tested. Verified: Road Atlanta canvas outline
pixels 6 → 1363.

2. **Reference lap duration was wrong (bug 28)** — first reported as
   "1:16.722 vs 1:17.345", but the *in-game* truth is 1:16.809; the earlier
   change to prefer 1:17.345 (`cd1ef55`, `0e6978c`) went the wrong way.
   Root cause: our duration helpers trusted the scorer's `mLastLapTime`
   (`scoring_last_lap_time_s`), which lags by one lap on Road Atlanta
   (77.345 = lap 14's time). TinyPedal derives the lap from consecutive
   **telemetry** lap-start ETs (`lmuTeleVeh.mLapStartET`). Our recorder stores
   `session_time_s - lap_time_s == mLapStartET`, so the same value is
   recoverable. `authoritative_duration` (Python) and `authDuration` (JS) now
   prefer that telemetry difference; the reference was re-exported to
   `_time_01.16.809` with `authoritative_lap_time_s` metadata; the model,
   generator, and app all read 1:16.809. Full details in
   `work/active/bugs/28-lap-duration-telemetry-clock/`.

New tests (registered in `package.json` `scripts.test`):
`dev/scripts/test_track_name_inference.js`,
`dev/scripts/test_reference_lap_duration.js`, and
`dev/scripts/test_lap_duration_telemetry.js`.

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
  --reference-lap product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.304.parquet \
  --track-config product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json \
  --print-facts
npm run build
```
