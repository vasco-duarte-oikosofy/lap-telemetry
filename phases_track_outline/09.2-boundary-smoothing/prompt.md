# Phase 09.2 — Smooth boundary polylines

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 9.2 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially the newly added "Phase 9.2 — Smooth boundary polylines" section.
3. Read prior handoffs:
   - `phases_track_outline/09.1-boundary-polylines/handoff.md`
   - `phases_track_outline/09.1-boundary-polylines/learnings.md`
4. Inspect nearby code/tests before adding files:
   - `scripts/compute_boundaries.js` — the boundary derivation module from Phase 9.1
   - `scripts/test_compute_boundaries.js` — existing boundary tests
   - `scripts/width_profile_smoothing.js` — the moving-average smoothing module (model your approach similarly but adapted for polyline points)
   - `scripts/profile_viewer.js` — visual QA viewer (already has `--boundaries` support; regenerated boundaries should be visually smoother)
   - `data/circuit-de-spa-francorchamps-endurance/default/` — Spa endurance path.json, width-profile.json, boundaries.json for real-data Visual QA
   - `package.json`
5. Write failing tests first.
6. Implement boundary polyline smoothing.
7. Stop when Phase 9.2 acceptance passes; do not start Phase 10.

**Current state:**

- `phases_track_outline/CURRENT` is `09.2-boundary-smoothing`.
- Phase 9.1 produced `computeBoundaries()` which derives left/right boundary polylines from a center path + width profile. The boundaries are unsmoothed — each boundary point's position is computed independently, so the raw output inherits per-bin jitter from the path positions and oscillates in the normal direction.
- Visual QA with `profile_viewer.js` on Spa endurance data shows:
  - **Jitter:** The boundary lines oscillate because the center path positions are unsmoothed per-bin averages and the tangent/normal computation amplifies small position noise. Approximately 2,583 out of 5,615 path points have direction reversals in x. The boundary polylines need smoothing to be usable for rendering.
  - **Zero-width overlap:** 87% of bins are one-sided (only left or right width, not both). Where `left_width_m = 0`, the left boundary collapses onto the center line. This is a data coverage problem, not a smoothing problem — Phase 11 (low-confidence styling) and Phase 13 (calibration docs) address it. This phase does **not** fix overlap; it fixes jitter.
- The center path (`export_center_path.js`) has no smoothing. The width profile already has smoothing (`width_profile_smoothing.js`, using `SMOOTH_WINDOW = 5`). Boundary smoothing is a separate concern because it smooths the *output positions* (x_m, z_m) of the boundary polyline, not the input widths.
- `compute_boundaries.js` CLI shape: `--path <path.json> --profile <profile.json> --out <boundaries.json> [--smooth] [--overwrite]`. You will add `--smooth-boundary <window>` or similar option.
- `profile_viewer.js` accepts `--boundaries <boundaries.json>` and renders left/right polylines. After smoothing, regenerate `data/.../boundaries.json` and check the viewer for visual improvement.

**Problem analysis:**

The jitter has two sources:
1. **Path position noise:** Unsmoothed per-bin averages produce positions that oscillate between adjacent bins, causing the boundary to wobble even in nominally straight sections.
2. **Normal amplification:** Small position changes between adjacent path points cause the tangent direction to oscillate, and the perpendicular normal amplifies this into larger offsets.

Smoothing the boundary polyline positions (x_m, z_m) with a moving average or Chaikin-style subdivision addresses both sources simultaneously, because it smooths the *result* of the tangent-plus-offset computation rather than the *inputs*.

**Implementation guidance:**

- Add a `smoothBoundary(boundaryPoints, window)` function to `scripts/compute_boundaries.js` (or a new `scripts/boundary_smoothing.js` module — your choice based on file size). It smooths the x_m and z_m of each boundary independently using a moving average over `±window` bins.
- Zero-width boundary points (where `width_m === 0`) should stay at the center path position — do not smooth them away from the path. Treat zero-width points as barriers in the same spirit as `width_profile_smoothing.js` treats long-gap bins.
- Gaps in s_m (path points that skip bins, e.g., s_m jumps from 5 to 10) should not be bridged by the smoother — each contiguous segment of boundary points should be smoothed independently.
- The `computeBoundaries` function should gain an optional `smoothBoundaryWindow` parameter (default 0 = no smoothing). When > 0, apply boundary smoothing after computing raw boundaries.
- CLI gains `--smooth-boundary <window>` flag (default 0). This is orthogonal to `--smooth` (which controls width smoothing). A typical good value is 5–10.
- Export the smoothing function for unit testing.

**Output JSON changes:**

- The boundaries JSON gains a `smooth_boundary_window` field (0 = unsmoothed, >0 = the window used).
- Boundary point fields (`s_m, x_m, z_m, width_m, status, confidence`) remain the same — only `x_m` and `z_m` values change when smoothing is applied.

**Acceptance criteria:**

- Straight-line fixture: smoothing a perfectly straight boundary returns the same straight line (tolerance < 0.01m per point).
- Jittered fixture: a boundary with synthetic high-frequency noise is visibly smoothed; the smoothed line's max deviation from the true shape is smaller than the raw line's max deviation.
- Curved fixture: smoothing a circular-arc boundary does not shrink the radius by more than a small tolerance (< 0.5m for a 100m-radius arc with window ≤ 10).
- Zero-width points remain at the center path position after smoothing (width_m=0 boundary points are barriers).
- Gaps in s_m are respected — smoothing does not bridge across discontinuous s_m jumps greater than `bin_size_m * 2`.
- Window=1 is identity (no smoothing). Window=0 is also identity (smoothing not applied).
- CLI `--smooth-boundary N` produces output with `smooth_boundary_window: N`; without the flag, `smooth_boundary_window: 0`.
- Existing `computeBoundaries` calls without `smoothBoundaryWindow` return the same output as before.
- Existing `npm test` remains green.
- Visual QA on Spa endurance boundaries: regenerate with `--smooth-boundary 5 --smooth` and confirm smoother lines in the profile viewer.

**Suggested tests:**

- Create test cases in `scripts/test_compute_boundaries.js` (or a new `scripts/test_boundary_smoothing.js` if the code is in a separate module).
- Include at least:
  - **Straight line identity.** Smooth a perfectly straight boundary (points along z-axis with constant offset) — result should be within 0.01m of the original.
  - **Jitter removal.** Create a straight boundary with sinusoidal noise on x_m (e.g., `x = offset + amplitude * sin(i * freq)`). After smoothing, the max deviation from the true line should be significantly smaller than the raw amplitude.
  - **Arc preservation.** Smooth a circular-arc boundary — the smoothed radius should be within 0.5m of the raw arc's radius.
  - **Zero-width barriers.** Insert boundary points with `width_m: 0` among points with non-zero width. Zero-width points should not be displaced.
  - **Gap barriers.** Insert a gap in s_m (e.g., jump from 5 to 20 mid-sequence). Smoothing should not bridge across the gap.
  - **Window=1 is identity.** Smoothing with window=1 should return values within epsilon of the original.
  - **CLI round-trip.** Run `compute_boundaries` with `--smooth-boundary 5` on the Spa data and verify `smooth_boundary_window: 5` in the output JSON.
  - **Integration with computeBoundaries.** Call `computeBoundaries({ ..., smoothBoundaryWindow: 5 })` and verify the output is smoothed.

**Visual QA:**

- Regenerate Spa endurance boundaries with `--smooth --smooth-boundary 5` and view in the profile viewer:
  ```bash
  node scripts/compute_boundaries.js \
    --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
    --profile data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
    --out data/circuit-de-spa-francorchamps-endurance/default/boundaries.json \
    --smooth --smooth-boundary 5 --overwrite
  node scripts/profile_viewer.js \
    data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
    --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
    --boundaries data/circuit-de-spa-francorchamps-endurance/default/boundaries.json \
    data/circuit-de-spa-francorchamps-endurance/default/spa-view.html
  ```
- Open `spa-view.html` and verify boundaries are smoother with less oscillation compared to the unsmoothed version.

**Out of scope:**

- Rendering boundaries in the browser compare app (Phase 10).
- Low-confidence styling (Phase 11).
- Diagnostics (Phase 12).
- Fixing one-sided/zero-width overlap (that's a data coverage issue, not a smoothing issue).
- Smoothing the center path itself (though that could be a future sub-phase).

**Visual check (required before committing):**

After all tests pass, you **must** do a side-by-side visual check using the profile viewer:

1. Regenerate boundaries **without** boundary smoothing (current baseline):
   ```bash
   node scripts/compute_boundaries.js \
     --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
     --profile data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
     --out data/circuit-de-spa-francorchamps-endurance/default/boundaries-raw.html.json \
     --smooth --overwrite
   node scripts/profile_viewer.js \
     data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
     --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
     --boundaries data/circuit-de-spa-francorchamps-endurance/default/boundaries-raw.html.json \
     data/circuit-de-spa-francorchamps-endurance/default/spa-view-raw.html
   ```

2. Regenerate boundaries **with** boundary smoothing:
   ```bash
   node scripts/compute_boundaries.js \
     --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
     --profile data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
     --out data/circuit-de-spa-francorchamps-endurance/default/boundaries.json \
     --smooth --smooth-boundary 5 --overwrite
   node scripts/profile_viewer.js \
     data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
     --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
     --boundaries data/circuit-de-spa-francorchamps-endurance/default/boundaries.json \
     data/circuit-de-spa-francorchamps-endurance/default/spa-view.html
   ```

3. Open both HTML files in a browser. **Ask the user to visually confirm** that:
   - The smoothed boundaries (spa-view.html) are visibly smoother with less oscillation than the raw boundaries (spa-view-raw.html).
   - The smoothed boundaries still follow the track shape correctly (no shrinking on curves, no drift on straights).
   - Zero-width segments (where one boundary collapses onto the center line) are not displaced by smoothing.

4. Only proceed to commit after the user confirms the visual check passes.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current.
- Visual check has been confirmed by the user.
- `phases_track_outline/09.2-boundary-smoothing/learnings.md` exists.
- `phases_track_outline/09.2-boundary-smoothing/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `10-learned-outline-rendering`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 10.