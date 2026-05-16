# Phase 09.1 — Boundary polylines from path + widths

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 9.1 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.4 Width profile contract (for paired JSON shape)
   - §0.5 Feature flags / delivery switches
   - "Phase 9.1 — Derive boundary polylines from path + widths"
3. Read prior handoffs:
   - `phases_track_outline/09-center-path-cli/handoff.md`
   - `phases_track_outline/09-center-path-cli/learnings.md`
   - `phases_track_outline/08.1-width-profile-smoothing/handoff.md`
4. Inspect nearby code/tests before adding files:
   - `scripts/export_center_path.js` (path JSON: `points[{s_m, x_m, z_m, sample_count}]`)
   - `scripts/export_width_profile.js` (profile JSON: `samples[{s_m, left_width_m, right_width_m, left_width_smooth_m, right_width_smooth_m, ..., status, confidence}]`)
   - `scripts/width_profile_smoothing.js` (interpolation/smoothing module)
   - `scripts/profile_viewer.js` (visual QA viewer — consider extending to show boundaries)
   - `package.json`
5. Write failing tests first.
6. Implement boundary polyline derivation.
7. Stop when Phase 9.1 acceptance passes; do not start rendering, confidence styling, or diagnostics phases.

**Current state:**

- `phases_track_outline/CURRENT` is `09.1-boundary-polylines`.
- Phase 09 completed the center/path CLI producing path JSON with `points[{s_m, x_m, z_m, sample_count}]`. The path has no gap-filling — missing bins are simply absent. The path and width profile use the same binning rule (`Math.floor(raw_lap_distance_m / binSizeM) * binSizeM`), so their `s_m` keys should align for overlapping bins.
- Phase 08.1 completed interpolation and smoothing for width profiles. Smoothed fields `left_width_smooth_m` and `right_width_smooth_m` are available when the width profile is generated with `--smooth`. The smoothing module uses `MAX_INTERPOLATE_GAP = 10` and `SMOOTH_WINDOW = 5`.
- The width profile has `samples` (with gap-filled missing bins between min and max s_m), while the path has `points` (only bins with actual data). A boundary derivation step must align these two datasets by `s_m`.
- Width profile bins include `status` (complete/one-sided/low-sample/missing) and `confidence` (0–1). These must propagate to boundary points so downstream rendering can style low-confidence segments differently.
- Existing browser/UI behavior should remain unchanged. This phase is CLI/helper driven only.
- `scripts/profile_viewer.js` generates a standalone HTML viewer accepting `--path <path.json>`. Consider adding boundary polyline rendering to it for visual QA.
- The viewer currently shows: 2D track map (cyan center path) + width chart (raw/smooth left/right). Adding left/right boundary polylines on the track map would be the natural visual QA.

**Implementation guidance:**

- Create a new script `scripts/compute_boundaries.js` that:
  - Reads a path JSON and a width profile JSON (already exported to disk).
  - Aligns path points with width samples by matching `s_m`.
  - For each path point that has a matching width sample, computes a tangent from adjacent path points, derives a perpendicular normal, and offsets the path point left and right by the smoothed (or raw) widths.
  - Outputs left and right boundary polylines.
- CLI shape: `node scripts/compute_boundaries.js --path <path.json> --profile <profile.json> --out <boundaries.json> [--smooth] [--overwrite]`
  - `--smooth` uses `left_width_smooth_m`/`right_width_smooth_m` instead of raw widths.
  - `--overwrite` replaces existing output file.
- Export a function `computeBoundaries({ pathPoints, profileSamples, useSmooth })` for tests. This is a pure function — it takes arrays, not files.
- Export `computeTangentNormal(points, index)` for unit testing — the tangent/normal math is the most error-prone part.
- Output boundaries JSON shape:
  ```json
  {
    "track_id": "circuit-de-spa-francorchamps-endurance",
    "layout_id": "default",
    "bin_size_m": 1,
    "use_smooth": true,
    "left": [
      { "s_m": 0, "x_m": -130.4, "z_m": 647.2, "width_m": 7.4, "status": "complete", "confidence": 1.0 },
      ...
    ],
    "right": [
      { "s_m": 0, "x_m": -143.5, "z_m": 645.1, "width_m": 6.8, "status": "complete", "confidence": 1.0 },
      ...
    ],
    "summary": {
      "path_points": 5615,
      "profile_samples": 7094,
      "matched_bins": 5600,
      "unmatched_path": 15,
      "left_boundary_points": 5600,
      "right_boundary_points": 5600
    }
  }
  ```
- Boundary points only exist where path and profile both have data at the same `s_m`. Path points without a matching width bin are counted in `unmatched_path` but do not produce boundary points.
- Tangent calculation: at interior points, use the vector from the previous point to the next point. At endpoints, use the vector from the point to its neighbor. Normalize to unit length.
- Normal: rotate tangent 90° — for LMU's coordinate system (x-right, z-forward in the horizontal plane), the "left" normal when traveling forward (increasing z) is tangent rotated -90° (i.e., `(-tz, tx)` where tangent = `(tx, tz)`). Verify with a known fixture.
- Offset: `left_boundary = (x - normal_x * left_width, z - normal_z * left_width)`, `right_boundary = (x + normal_x * right_width, z + normal_z * right_width)`. Verify direction with a straight-line fixture where the car travels in the +z direction — left boundary should be at -x, right at +x.
- Propagate `status` and `confidence` from the width sample to the boundary point.

**Acceptance criteria:**

- Straight-line fixture: boundary offsets are exactly the expected distance on correct sides.
- Curved fixture: boundaries stay on consistent sides (left boundary always left of travel direction, right always right).
- Low-confidence/missing width bins propagate status and confidence to boundary points.
- Path points without matching width data are counted but produce no boundary points.
- Tangent/normal calculation handles endpoints and colinear points correctly.
- Existing center-path and width-profile CLI behavior is unchanged.
- Existing `npm test` remains green.

**Suggested tests:**

- Create a new test file `scripts/test_compute_boundaries.js` following the existing pattern.
- Include at least:
  - **Straight-line path + known widths → exact boundary offsets.** E.g., path points along z-axis (x=0, z increasing), widths left=5, right=3 → left boundary at x=-5, right at x=+3.
  - **Curved path (arc) → boundaries on consistent sides.** E.g., circular arc — left boundary should be outside the arc, right inside (or vice versa depending on direction).
  - **Endpoint tangent handling.** First and last points use one-sided tangent.
  - **Missing width bins produce no boundary points.** A path point at s=5 with no matching width sample should not appear in the boundary arrays.
  - **Status/confidence propagation.** A one-sided width bin should produce a boundary point with status="one-sided" and confidence=0.5.
  - **Smooth vs raw widths.** With `--smooth`, boundary offsets use smoothed widths; without, they use raw.
  - **CLI invocation** — exit 0, valid JSON output.
  - **Real session integration** (Spa endurance) — smoke test that reads exported path+profile JSON and produces boundaries JSON.
- Reuse the pure function for all geometry tests (no Parquet needed).

**Visual QA:**

- Consider extending `scripts/profile_viewer.js` to optionally accept `--boundaries <boundaries.json>` and render left/right boundary polylines on the 2D track map (e.g., red/green lines flanking the cyan center path).
- This is optional but highly recommended for verifying the boundary geometry looks correct before Phase 10 renders it in the main app.

**Out of scope:**

- Rendering boundaries in the browser compare app (Phase 10).
- Low-confidence styling (Phase 11).
- Diagnostics (Phase 12).
- Smoothing the boundary output (use smoothed width input instead).
- Gap-filling boundaries where path or width data is missing.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current. If no frontend bundle changes occur, still run the build and document whether `dist/compare.html` changed.
- `phases_track_outline/09.1-boundary-polylines/learnings.md` exists.
- `phases_track_outline/09.1-boundary-polylines/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `10-learned-outline-rendering`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 10.