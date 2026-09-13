# Bug 27 — Car-blind coaching resolution: live coach compares against the wrong car

## Symptom

While driving **fastest laps** in a Ferrari 296 GT3 (Vista AF Corse #54) at
Lusail, the live coach told the driver:

> "You lost seven tenths at the apex of turn 9."
> "You lost nine tenths at the apex of turn 2."

These losses are bogus — the driver was on purple laps. The utterances are
template-generated (no LLM; `llm=0ms` in the log), so the text faithfully
reflects the comparison facts. The facts themselves are wrong.

## Reproduction (exact)

The live coach resolves the reference lap and coaching model by **track name
only**. For Lusail there are two car combos on disk:

- `lusail-international-circuit_dkr-engineering-4-elms25` — **Ginetta LMP3**, ref 01.51.975 (~112 s)
- `lusail-international-circuit_vista-af-corse-2026-54-wec` — **Ferrari 296 GT3**, ref 01.59.237

`reference_resolver.resolve_reference_lap()` matches by track slug and, when
multiple files match, picks the **smallest `_time_`** (fastest) → the **LMP3**
reference. `track_model_resolver.resolve_track_model()` picks `matching[0]`
(alphabetical) → also the **LMP3** model. Neither resolver receives the
vehicle name, so the Ferrari laps are compared against an LMP3 reference ~7 s
per lap faster.

Reproduced offline (race lap 12, Ferrari, vs the DKR LMP3 reference + model,
template mode):

| Lap | Delta   | Template utterance                                  |
|-----|---------|-----------------------------------------------------|
| 10  | +5.62 s | "You lost nine tenths at the apex of turn 2."       |
| 12  | +5.54 s | "You lost seven tenths at the apex of turn 9."      |

These match the user's reported utterances verbatim. Against the **correct**
Ferrari reference, lap 12 says "You gained just over a tenth at turn 15…
You lost two tenths braking for turn 6" — grounded and correct.

## Root cause

1. `reference_resolver.py` and `track_model_resolver.py` match by **track slug
   only** and pick among multiple cars by fastest/first — they never consider
   the vehicle.
2. The live coach never passes the vehicle to the resolvers
   (`resolve_reference_lap(track_name)` — no car argument). `LapCompleted` /
   `NewLap` / `CornerExited` carry `track_name` but not `vehicle_name`, even
   though `Frame.vehicle_name` is available.
3. No canonical car mapping is used, so different liveries of the same car
   (e.g. the many Ferrari 296 GT3 entries) cannot be grouped. The repo already
   has `product/data/vehicle_catalog.json` for this, but it is unused by the
   resolvers — and it is missing the real session spelling
   `"Vista AF Corse 2026 #54:WEC"` (it has the typo `"Corsa"`; both spellings
   occur in real sessions).

Secondary: `LiveFactGenerator` re-loads and re-parses the coaching model JSON
on every lap (`load_track_coaching_model()` inside `generate*()`), while
`LiveCornerFactGenerator` already caches it. The model should be loaded once
per session and kept in memory.

## Fix

One vertical slice — **car-aware, per-session-cached coaching data resolution**:

1. New `car_catalog.py`: load `vehicle_catalog.json`; expose
   `canonical_car_slug(vehicle_name)` and `car_id_canonical_slug(car_id_slug)`
   using the same `vehicle_slug` rule as the export script (so filename car-ids
   round-trip).
2. Resolvers gain an optional `vehicle_name` argument. When provided, candidates
   are filtered to those whose car-id maps to the **same canonical car slug**
   as the live vehicle; among matches, prefer an exact car-id match, else
   fastest (reference) / first (model). When no vehicle is given, behavior is
   unchanged (backward compatible). When a vehicle is given but no candidate
   matches its car, return `None` (skip coaching) rather than use another car's
   data.
3. `LapCompleted` / `NewLap` / `CornerExited` carry `vehicle_name`, populated
   from `Frame.vehicle_name` in the detectors.
4. `coach_tap` passes `event.vehicle_name` through to the fact generators;
   `LiveFactGenerator` and `LiveCornerFactGenerator` pass it to the resolvers.
5. `LiveFactGenerator` caches the loaded `TrackCoachingModel` per resolved path
   (loaded once per session), matching `LiveCornerFactGenerator`.
6. `vehicle_catalog.json`: add the real spelling `"Vista AF Corse 2026 #54:WEC"`
   and the missing `"AF Corse 2025 #51:ELMS"` (both Ferrari 296 GT3). Keep the
   existing `"Corsa"` entry (real sessions use it too).

## Status

Confirmed fixed (commit 5b744ba) — verified in a live session. Moved to work/completed/bugs/.
