# Phase 08.1 — Interpolate and smooth width profile

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 8.1 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.4 Width profile contract
   - "Phase 8.1 — Interpolate and smooth width profile"
3. Read prior handoffs:
   - `phases_track_outline/08-width-profile-confidence/handoff.md`
   - `phases_track_outline/08-width-profile-confidence/learnings.md`
4. Inspect nearby code/tests before adding files:
   - `scripts/export_width_profile.js` (current profile builder + confidence/status)
   - `scripts/test_width_profile_confidence.js` (confidence tests pattern)
   - `scripts/test_width_profile_export.js` (original export tests pattern)
   - `package.json`
5. Write failing tests first.
6. Implement interpolation and smoothing for width profile bins.
7. Stop when Phase 08.1 acceptance passes; do not start center path, boundary polylines, rendering, or diagnostics phases.

**Current state:**

- `phases_track_outline/CURRENT` is `08.1-width-profile-smoothing`.
- Phase 08 added `confidence` and `status` fields to every width profile sample, and filled gap bins explicitly (status `"missing"`, confidence 0). The profile now contains all bins from min to max `s_m` with no silent omissions.
- Phase 08 also fixed `track_edge_m` to use `Math.abs()` — negative left-side LMU values are now correctly treated as positive widths.
- Each sample currently has: `s_m`, `left_width_m`, `right_width_m`, `left_sample_count`, `right_sample_count`, `status`, `confidence`.
- `status` is one of: `"complete"`, `"low-sample"`, `"one-sided"`, `"missing"`.
- `buildProfileFromRows(rows, binSizeM)` returns `{ samples, skipped, missing_bins, one_sided_bins, low_sample_bins, complete_bins }`.
- `exportWidthProfile` writes the raw profile to JSON. The CLI prints a confidence summary.
- The Spa endurance real session went from ~5615 bins (Phase 07, no gap fill) to ~7094 bins (Phase 08, gap-filled) — about 20% are gap bins needing interpolation.
- Existing browser/UI behavior should remain unchanged. This phase is CLI/helper driven only.

**Implementation guidance:**

- Add an `interpolateAndSmooth(samples, options)` pure function (or similar) that takes the raw profile samples and produces a render-ready result.
- **Interpolation:** Linear interpolation across missing/one-sided gaps. A "short gap" is a consecutive run of bins with `status === "missing"` shorter than a configurable threshold (suggest `MAX_INTERPOLATE_GAP = 10` bins, i.e. 10m at default bin_size). For short gaps, interpolate `left_width_m` and `right_width_m` from the nearest non-missing neighbors on each side.
- **Long gaps:** Bins in gaps longer than the threshold should keep their original zero widths and `status: "missing"`. Do not silently bridge them.
- **Smoothing:** After interpolation, apply a simple moving-average smoother to `left_width_m` and `right_width_m` with a fixed window size (suggest `SMOOTH_WINDOW = 5` bins). Only smooth bins that have non-zero width data (interpolated or original). Do not smooth across long gaps.
- **Preserve raw data:** The smoothed/interpolated values must live in separate fields (e.g. `left_width_smooth_m`, `right_width_smooth_m`) so that the raw `left_width_m`, `right_width_m`, `left_sample_count`, `right_sample_count`, `status`, and `confidence` remain untouched. Alternatively, the function can return a new array alongside the original samples.
- The `exportWidthProfile` CLI should gain a `--smooth` flag (default off). When enabled, it runs interpolation + smoothing and includes the smoothed fields in the output JSON.
- Keep the existing raw-only output as the default — existing tests and consumers must not break.

**Acceptance criteria:**

- Short missing gaps are linearly interpolated with expected values.
- Long gaps remain flagged low-confidence / missing and are not silently bridged.
- Smoothing changes width values but does not change raw sample counts or confidence.
- Existing raw-profile tests (Phase 07 + 08) remain green without modification.
- Existing compare UI and apex features remain unchanged.

**Suggested tests:**

- Create a new test file `scripts/test_width_profile_smoothing.js` following the existing pattern.
- Include at least:
  - A fixture with a short gap (e.g. 3 missing bins between two complete bins) — assert interpolated widths are the linear midpoint.
  - A fixture with a long gap (e.g. 15 missing bins) — assert they remain missing/zero (not interpolated).
  - A fixture showing that smoothing narrows the difference between adjacent bins (moving-average effect) without changing zero-width gap bins inside long gaps.
  - A fixture confirming that raw `left_width_m`, `right_width_m`, `left_sample_count`, `right_sample_count`, `status`, `confidence` are untouched after smoothing.
  - A CLI invocation with `--smooth` that produces output containing smoothed fields.
  - A CLI invocation without `--smooth` that produces the same output as before (raw only).
- Use `buildProfileFromRows` from the existing module to build fixture samples efficiently — no need for Parquet round-trips in core tests.
- Add a smoke test: the Spa endurance session runs with `--smooth` without errors.

**Out of scope:**

- Center path generation (Phase 09).
- Boundary polylines (Phase 09.1).
- Browser UI changes.
- Automatic profile generation during recording or browser loading.
- Diagnostics reports (Phase 12).
- Smoothing configurable via CLI args (keep it simple: fixed window; tuning can come later).

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current. If no frontend bundle changes occur, still run the build and document whether `dist/compare.html` changed.
- `phases_track_outline/08.1-width-profile-smoothing/learnings.md` exists.
- `phases_track_outline/08.1-width-profile-smoothing/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `09-center-path-cli`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 09.