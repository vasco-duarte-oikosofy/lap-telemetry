# Handoff — Slice 34 (Daytona International Speedway Road Course)

## What is on disk now (committed in this slice)

**Reference lap** (guarded export, race session, fastest valid = lap 11 @ 1:45.596):
- `product/data/reference-laps/daytona-international-speedway-road-course_dkr-engineering-4-elms25_time_01.45.596.parquet`
- Source session: `sessions/session_20260808T164304Z_daytona-international-speedway-road-course_lmu_race.parquet`
- NOTE: the fastest-looking race lap (lap 9 @ 1:44.521) was rejected by the
  export guards as an abandoned/cut lap (frame-count mismatch). Lap 11 was the
  fastest that passed the authoritative-duration guard.
- `validate_reference_laps.py` passes (0 failures).

**Coaching model** (generated then hand-curated):
- `product/data/track-coaching/daytona-international-speedway-road-course_dkr-engineering-4-elms25.json`
- `...diagnostics.txt`
- 8 corners: Turn 1, Turn 2 (Kink), International Horseshoe, Turn 4 (Kink),
  Turn 5, Turn 6, Turn 7, Bus Stop.
- Turn 2 and Turn 4 are fast kinks the throttle-brake detector missed; they were
  added manually from the steering trace. `t4` (a near-flat 2 kph-drop blip at
  1832 m) was retained as Turn 6.
- Verified: `generate_utterance --print-facts` resolves all corner IDs, no KeyError.

**Track outline** (trajectory, no TUMFTM data for Daytona):
- `product/data/track-outlines/daytona-international-speedway-road-course.json` (500 pts)
- Registered in `product/web/js/trackOutlineManifest.js` (+ backup file),
  ES module `product/web/js/staticDaytonaInternationalSpeedwayRoadCourseOutlineData.js`,
  `product/dist/compare.html` rebuilt via `npm run build`.
- `docs/TRACK_OUTLINE_COVERAGE.md` updated with a trajectory row.

## Feature flags / live

None new. The coach consumes the new coaching JSON via the same loader path.

## Corner-direction caveat (IMPORTANT)

The steering sign convention in these LMU reference laps is **not trustworthy
as a fixed left/right across tracks** (Laguna vs Daytona disagreed). I set the
apex sides from the LMU RaceControl turn guide instead of the raw steering
sign, because the guide is the authoritative layout reference. If a lap later
shows a wrong apex side, re-check against a track map rather than the steering
column alone. Apex side is secondary in the model (other models default to
"right" and are often wrong anyway).

## Deferred / still open

- **Laguna Seca is NOT committed.** Earlier work (reference lap + coaching model
  JSON/diagnostics) is uncommitted and the coaching model was **not curated**
  (corner names not finalized, Turn 10 not added) and the outline was never
  generated. That task was interrupted when the user redirected to Daytona.
- Full test suite has pre-existing environment failures on this machine:
  - `python3` resolves to the Microsoft Store stub (`...\WindowsApps\python3`)
    → "Python was not found" (status 9009). Use `python` (Python 3.10.11) instead.
  - Some Node ESM tests fail with `ERR_UNSUPPORTED_ESM_URL_SCHEME` (Windows path
    handling in the ESM loader) — environment, not caused by these data changes.
  - `test_static_track_outline_contract.js` **passes** (81 assertions) and
    validates the new outline schema.

## Useful commands

```bash
python dev/scripts/validate_reference_laps.py
bash scripts/test-summary.sh dev/scripts/test_static_track_outline_contract.js
npm run build
```
