# Handoff — Slice 35 (WeatherTech Raceway Laguna Seca)

## What is on disk now (committed in this slice)

**Reference lap** (guarded export, fastest valid = lap 4 @ 1:27.905):
- `product/data/reference-laps/weathertech-raceway-laguna-seca_vista-af-corse-2026-54-wec_time_01.27.905.parquet`
- Source session: `sessions/session_20260808T155443Z_weathertech-raceway-laguna-seca_lmu_practice.parquet` (car `vista-af-corse-2026-54-wec`)
- `validate_reference_laps.py` passes (20 refs, 0 failures).

**Coaching model** (curated, 11 corners):
- `product/data/track-coaching/weathertech-raceway-laguna-seca_vista-af-corse-2026-54-wec.json` (+ `.diagnostics.txt`)
- Corners: Turn 1, Andretti Hairpin, Turn 3, Turn 4, Turn 5, Turn 6, Turn 7,
  Corkscrew (Turn 8), Rainey Curve (Turn 9), Turn 10, Turn 11.
- The throttle-brake detector found 10 corners; Turn 10 (a fast ~150 kph corner
  at 3200 m, between Turn 9 and Turn 11) was **not detected** (continuous braking
  into Turn 11) and was added manually.
- Verified: `generate_utterance --print-facts` resolves all corner IDs, no KeyError.

**Track outline** (trajectory, no TUMFTM data for Laguna Seca):
- `product/data/track-outlines/weathertech-raceway-laguna-seca.json` (500 pts)
- Registered in `product/web/js/trackOutlineManifest.js` (+ backup),
  ES module `product/web/js/staticWeathertechRacewayLagunaSecaOutlineData.js`,
  `product/dist/compare.html` rebuilt.
- `docs/TRACK_OUTLINE_COVERAGE.md` updated.

## Apex-side caveat

The steering sign convention in LMU reference laps is **not portable across
tracks** and even conflicted within the Laguna lap (steering vs position trace
disagreed at Turn 6). Apex sides were taken from the track guides (Trackpedia /
NASA) — the authoritative layout reference. Re-verify against a track map if a
later lap reports a wrong side. Apex side is secondary in the model.

## Deferred / still open

- Full test suite has pre-existing environment failures on this machine:
  `python3` is the Microsoft Store stub ("Python was not found", 9009) — use
  `python`; some Node ESM tests fail with `ERR_UNSUPPORTED_ESM_URL_SCHEME`.
  Neither is caused by track data. `test_static_track_outline_contract.js`
  passes (81 assertions).

## Commands

```bash
python dev/scripts/validate_reference_laps.py
bash scripts/test-summary.sh dev/scripts/test_static_track_outline_contract.js
npm run build
```
