# Phase 01b — `s`-based cross-lap alignment, debug overlay

**Your task:** Implement Phase 01b from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 1b — `s`-based cross-lap alignment, with debug overlay"
2. Read `phases/01a-heatmap-single-lap/handoff.md` to understand current state
3. Implement `sLookup` and debug overlay per spec
4. Write tests first (following TESTING_LESSONS.md)
5. Follow XP working agreements in AGENTS.md

**Key requirements:**
- Implement `sLookup(lap, targetS)` with binary search + linear interpolation
- Implement dev-only monotonicity assertion on `lap_distance_m`
- Feature flag: `features.mapSAlignment`
- Dev-only debug overlay flag for tick marks
- Render debug tick marks every 100m on both laps using `sLookup`
- No cosmetic change to the main heatmap — this is a diagnostic feature

**Acceptance criteria:**
- Unit test: `sLookup` returns correct interpolation at exact and intermediate positions
- Unit test: `sLookup` is monotonic
- Property test: random `s` returns interpolated `s` within float-epsilon
- Dev-mode test: monotonicity assertion fires on deliberately-corrupted fixture
- Manual visual check: debug ticks line up across real lap pairs

**Out of scope:**
- Lap B ribbon rendering (Phase 1c)
- Side-by-side offset (Phase 1c)
- Zoom/pan (Phase 2)

**When done:**
- `npm test` passes (all existing + new 01b tests)
- `phases/01b-s-alignment/learnings.md` exists
- `phases/01b-s-alignment/handoff.md` exists
- Commit directly on `main`
- Update `phases/CURRENT` if needed

**Stop at green.** Do not start Phase 1c.
