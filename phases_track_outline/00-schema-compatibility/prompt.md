# Phase 00 — Schema compatibility safety net

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 0 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially "Phase 0 — Schema compatibility safety net".
3. Write failing compatibility tests first.
4. Make the smallest code change that lets legacy sessions and future-shaped sessions both load safely.
5. Do not record new channels yet.

**Acceptance criteria:**
- Legacy session fixture loads without errors.
- Future-shaped session fixture with all new fields loads without errors.
- Missing `raw_lap_distance_m` falls back to existing distance only where a feature explicitly allows fallback.
- No rendered UI changes compared with the pre-phase baseline.

**Out of scope:**
- Recording new telemetry channels.
- Apex calculations.
- Width-profile generation.
- UI changes.

**When done:**
- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current if build output changes.
- `phases_track_outline/00-schema-compatibility/learnings.md` exists.
- `phases_track_outline/00-schema-compatibility/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `01-recorder-track-edge-channels`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 1.
