# Slice 34 — Daytona International Speedway Road Course (new track)

Add full track support for the Daytona International Speedway Road Course from a
new LMU session (race, `session_20260808T164304Z`):

1. Export + validate the reference lap (guarded scripts).
2. Generate + curate the coaching model (corner names, zones, apex sides).
3. Generate a trajectory track outline, register it, and rebuild the bundle.
4. Update `docs/TRACK_OUTLINE_COVERAGE.md`.
5. Verify with `--print-facts`; commit.

The reference lap must come from the **race** session (not the quali/practice),
per the user's instruction.
