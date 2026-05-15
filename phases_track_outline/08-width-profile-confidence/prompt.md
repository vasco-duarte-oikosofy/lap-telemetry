# Phase 08 — Width profile confidence and gap flags

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 8 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.4 Width profile contract
   - §0.5 Feature flags / delivery switches
   - "Phase 8 — Width profile confidence and gap flags"
3. Read prior handoffs:
   - `phases_track_outline/07-width-profile-cli/handoff.md`
   - `phases_track_outline/07-width-profile-cli/learnings.md`
4. Inspect nearby code/tests before adding files:
   - `scripts/export_width_profile.js`
   - `scripts/test_width_profile_export.js`
   - `package.json`
5. Write failing tests first.
6. Implement the confidence and gap/one-sided flag logic for width profile bins.
7. Stop when Phase 08 acceptance passes; do not start smoothing/interpolation, center path, boundary polylines, rendering, or diagnostics phases.

**Current state:**

- `phases_track_outline/CURRENT` is `08-width-profile-confidence`.
- Phase 07 added `scripts/export_width_profile.js`, which reads one or more Parquet sessions and writes raw unsmoothed left/right width bins to JSON.
- The §0.4 width profile contract already includes a `confidence` field per sample, but Phase 07 did not populate it (it was out of scope per the prompt).
- Real LMU data shows that `track_edge_m` can be negative for left-side samples (the sim encodes left/right sign in `track_edge_m` itself). Left-side bins in Phase 07 often have `left_width_m = 0` and `left_sample_count = 0` because negative `track_edge_m` rows still get binned but `max()` never exceeds existing positive values. The next phase should decide/document how negative `track_edge_m` values interact with width and confidence (they may indicate the car is beyond the approximated path on the left side and could be treated as valid widths using `abs(track_edge_m)`, or they may be flagged as uncertain — but check the spec and real data first).
- The binning rule in §0.4 uses `max(left_width[s_bin], track_edge_m)` without taking `abs()`. Phase 07 follows this literally. Phase 08 should review whether this is correct for negative `track_edge_m` and potentially add a note or fix.
- Existing browser/UI behavior should remain unchanged. This phase is CLI/helper driven only.

**Implementation guidance:**

- Add `confidence` and/or status fields to each sample in the profile output.
- Design a simple documented confidence rule, for example:
  - A bin with both left and right samples at reasonable counts is "complete" / high confidence.
  - A bin with only one side is "one-sided" / medium confidence.
  - A bin with very low sample counts (e.g., < N) is "low-sample" / low confidence.
  - A missing bin (a gap in the `s_m` sequence) is explicitly reported, not silently omitted.
- Include aggregate summary counts in CLI output/logs.
- Do not fill or smooth gaps yet — Phase 08.1 owns interpolation.
- Keep the profile raw and unsmoothed. Phase 08.1 adds smoothing.

**Acceptance criteria:**

- Complete bins (both sides, adequate samples) receive higher confidence than one-sided or low-sample bins.
- Missing bins are present or reported explicitly; they are not silently omitted.
- CLI summary reports counts for missing, one-sided, and low-confidence bins.
- Existing compare UI and apex features remain unchanged.
- Existing `npm test` remains green.

**Suggested tests:**

- Add test cases to `scripts/test_width_profile_export.js` or create a new test file following the existing pattern.
- Include at least:
  - A fixture producing complete, one-sided, low-sample, and missing (gap) bins.
  - Assertions that confidence values match the documented rule.
  - Assertions that missing bins are explicitly present or reported (not omitted).
  - Assertions that the CLI summary includes counts for missing, one-sided, and low-confidence bins.
- Avoid relying on large real `sessions/` files for core acceptance (but the Phase 07 real-session integration test may be extended for smoke).

**Out of scope:**

- Interpolation/smoothing (Phase 08.1).
- Center path generation (Phase 09).
- Boundary polylines (Phase 09.1).
- Browser UI changes.
- Automatic profile generation during recording or browser loading.
- Diagnostics reports (Phase 12).

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current. If no frontend bundle changes occur, still run the build and document whether `dist/compare.html` changed.
- `phases_track_outline/08-width-profile-confidence/learnings.md` exists.
- `phases_track_outline/08-width-profile-confidence/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `08.1-width-profile-smoothing`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 08.1.