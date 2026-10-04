# Slice 36 — Michelin Raceway Road Atlanta (new track)

Full track support for Michelin Raceway Road Atlanta from the new LMU session
(`session_20261004T133118Z`, car `DKR Engineering #4:ELMS25`, Ginetta LMP3):

1. Export + validate the reference lap (guarded scripts).
2. Generate + curate the coaching model using the **official Road Atlanta turn
   numbers** (12 turns; 10A/10B split). Keep the flat-out turns that the
   throttle/brake detector misses — they exist as real track geometry.
3. Generate a trajectory track outline, register it, rebuild the bundle.
4. Update `docs/TRACK_OUTLINE_COVERAGE.md`.
5. Verify with `--print-facts`; commit.

Carried over from slices 34/35: apex sides come from the track guide, not the
raw steering sign; flat corners need manual handling.
