# Slice 52 — Silverstone National Circuit / Ferrari 296 GT3 (new car, existing track)

Status: ✅ Complete — reference 0:54.295 + 6-zone model; curated P3 content preserved, outline untouched (`edc3930`+`9c19ee2`+`0915a70`)
Trigger: *"rebase from remote, then pickup the F296/silverstone quali and race
sessions, and derive the reference lap and coaching model for that combo. We
already have the outline, no need for outline now"*

## Sessions in scope

Both recorded 2026-11-14 in `Vista AF Corse 2026 #21:LM` → catalogued slug
`ferrari-296-gt3` (entry already present in `vehicle_catalog.json`).

| Session | File | State |
|---|---|---|
| 06:52 quali | `sessions/session_20261114T065241Z_silverstone-national-circuit_lmu_quali.parquet` | finalized, 12 laps |
| 07:04 race | `sessions/session_20261114T070413Z_…_race.partN.parquet` (105 shards + 12 snaps) | **unfinalized** — sidecar `in_progress: true`, `ended_utc: null`, no canonical parquet |

The race data is complete through `part99` (session_time 2010.8 s, lap 33);
`part100`–`part104` are frozen-time duplicates written while the car sat parked.

Track slug `silverstone-national-circuit` already has a reference, a curated
6-corner model and an outline — but only for the Ginetta LMP3
(`dkr-engineering-4-elms25`, slice 51). There is **no** `ferrari-296-gt3` asset,
so the live coach currently cannot resolve this combo (bug 27 resolution).

## Goal

Onboard `(silverstone-national-circuit, ferrari-296-gt3)` — reference lap and
coaching model only.

1. **Reference lap** — guarded export of the fastest complete valid lap across
   the two sessions (`--min-lap-time-s 30`, the National lap is ~55 s in a GT3).
2. **Coaching model** — seed from the curated P3 model (official Silverstone
   National names/IDs/apex sides/short names/flat markers copied verbatim), then
   refresh geometry from the new reference through
   `update_reference_and_coaching_model.py --ref …`.
3. Prove every curated field survives byte-identical; the two flat bends
   (`Maggots`, `Woodcote`, `target_throttle_pct: 100`) must be preserved, not
   matched, because a flat corner has no braking event to detect.

## Explicitly out of scope (per the trigger)

- **The track outline** — `product/data/track-outlines/silverstone-national-circuit.json`
  stays byte-identical; `bake_outline_turns.py` still selects the P3 model, so
  the outline contract holds without re-baking.
- TinyPedal labels (derived from the outline, which does not change).
- The Silverstone GP-ELMS / International assets, and every other track.
- The live `coach-race.log` and the recorder's live session files.

## Required end state

1. `bash scripts/test-summary.sh --feature track-outline` green; full `--pw` suite green.
2. `npm run build` succeeds and `dist/compare.html` is current.
3. `handoff.md` + `learnings.md` in this folder; PLAN.md row marked ✅ with the commit.
