# Phase 00.6 — Track Outline Background

**Your task:** Implement Phase 00.6 from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 0.6 — Track outline background"
2. Read `phases/00.5-walking-skeleton/handoff.md` to understand the current state
3. Implement the track outline feature per the spec
4. Write tests first (following TESTING_LESSONS.md)
5. Follow XP working agreements in AGENTS.md

**Reference:** See `screenshots/trajectory drawing for two laps on trackmap outline.png` for the desired visual

**Key requirements:**
- Draw faint track outline underneath lap polylines
- Low-contrast grey color (e.g., `rgba(120, 120, 120, 0.4)`)
- Draw order: outline → Lap B → Lap A (bottom to top)
- Feature flag: `features.mapTrackOutline`

**When done:**
- `npm test` passes (all existing tests + new 00.6 tests)
- `phases/00.6-track-outline/handoff.md` exists
- `phases/00.6-track-outline/learnings.md` exists
- Commit on branch `phase/00.6-track-outline`
- Update `phases/PLAN` to mark 00.6 as DONE

**Stop at green:** When acceptance passes, commit and stop. Don't start Phase 01a.
