# Slice 35 — WeatherTech Raceway Laguna Seca (new track)

Add full track support for WeatherTech Raceway Laguna Seca from the new LMU
session (`session_20260808T155443Z`, car `vista-af-corse-2026-54-wec`):

1. Export + validate the reference lap (guarded scripts).
2. Generate + curate the coaching model (all 11 corners, including the
   detector-missed Turn 10).
3. Generate a trajectory track outline, register it, and rebuild the bundle.
4. Update `docs/TRACK_OUTLINE_COVERAGE.md`.
5. Verify with `--print-facts`; commit.

Carried over from the Daytona slice (34): apex sides come from the track guide,
not the raw steering sign.
