# Phase 09.3 — Infer missing one-sided boundary widths

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 9.3 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.4 Width profile contract
   - Phase 8.1 — Interpolate and smooth width profile
   - Phase 9.1 — Derive boundary polylines from path + widths
   - Phase 9.2 — Smooth boundary polylines
   - Phase 9.3 — Infer missing one-sided boundary widths from local total width
3. Read prior handoffs/learnings:
   - `phases_track_outline/09.1-boundary-polylines/handoff.md`
   - `phases_track_outline/09.1-boundary-polylines/learnings.md`
   - `phases_track_outline/09.2-boundary-smoothing/handoff.md`
   - `phases_track_outline/09.2-boundary-smoothing/learnings.md`
   - `phases_track_outline/10-learned-outline-rendering/handoff.md`
   - `phases_track_outline/10-learned-outline-rendering/learnings.md`
4. Inspect nearby code/tests before adding files:
   - `scripts/compute_boundaries.js` — boundary derivation + smoothing CLI
   - `scripts/test_compute_boundaries.js` — boundary derivation tests
   - `scripts/test_boundary_smoothing.js` — current smoothing tests
   - `scripts/width_profile_smoothing.js` — interpolation/gap conventions
   - `scripts/profile_viewer.js` — visual QA viewer
   - `data/circuit-de-spa-francorchamps-endurance/default/` — Spa visual QA artifacts
   - `package.json`
5. Write failing tests first.
6. Implement the smallest explicit inference heuristic.
7. Stop when Phase 9.3 acceptance passes; do not start TUMFTM import or Phase 11 styling.

**Current state:**

- Phase 10 rendering works: learned boundaries are drawn as faint cyan lines behind lap trajectories.
- User visual QA on Spa showed two boundary-quality problems:
  1. **Bus Stop chicane:** one side of the outline disappears/collapses midway through the direction change while lap trajectories remain smooth.
  2. **La Source:** boundary data remains very jittery even after Phase 9.2 boundary smoothing.
- Phase 9.2 intentionally kept zero-width points fixed and treated them as barriers. Phase 10 then skips zero-width points in the renderer. This avoids drawing center-path-as-boundary, but it makes one side vanish in one-sided sections.
- The simpler hypothesis for this phase: when exactly one side is zero/missing, the track probably did not physically become zero-width. The car may be near/apex-side relative to the learned path, while the opposite side still gives a reasonable total width clue.
- We will infer the missing side from nearby local total track width instead of importing external geometry.

**Problem analysis:**

Current one-sided bins can look like this:

```text
left_width_m = 0
right_width_m = 11
status = one-sided
```

The current boundary derivation makes the left boundary collapse to the center path (or the renderer skips it). A simple alternative is to estimate the local total track width from nearby complete/high-confidence bins:

```text
local_total_width = median(left_width + right_width) over nearby complete/high-confidence bins
inferred_left_width = max(local_total_width - right_width, 0)
```

This is an approximation and must be marked as inferred/low-confidence. It is intended to improve continuity for short one-sided runs while preserving data-quality visibility for Phase 11.

**Implementation guidance:**

- Add a pure helper, either inside `scripts/compute_boundaries.js` if it stays under the file limit, or in a new small module such as `scripts/boundary_width_inference.js`.
- Keep defaults safe:
  - Existing `computeBoundaries({ ... })` output must not change unless inference is explicitly enabled.
  - CLI inference must be behind an option such as `--infer-missing-widths`.
- Suggested helper shape:

```js
inferMissingWidths(profileSamples, {
  window = 10,
  maxRun = 10,
  minCompleteNeighbors = 2,
} = {})
```

- Use only nearby complete/high-confidence bins to compute local total width. Start simple:
  - complete bin = both left/right widths > 0 and confidence high enough (e.g. `confidence >= 0.75`) or `status === 'complete'`.
  - total width = left + right using smoothed widths when `--smooth` is active, otherwise raw widths.
- Infer only when exactly one side is missing/zero and the other side is positive.
- Do not infer:
  - both sides missing/zero
  - long one-sided runs longer than `maxRun`
  - bins without enough local complete neighbors
  - inferred width would be non-finite or <= 0
- Preserve raw width fields. Add explicit metadata. Keep it minimal, for example boundary points may include:

```json
{
  "width_m": 7.2,
  "status": "inferred-one-sided",
  "confidence": 0.35,
  "inferred": true,
  "inferred_side": "left"
}
```

or equivalent side-specific fields if that is cleaner.

- Boundary output summary should include inferred counts, e.g.:

```json
"summary": {
  "inferred_left_widths": 123,
  "inferred_right_widths": 98
}
```

**Acceptance criteria:**

- Short one-sided gap: missing side is inferred from nearby median total width.
- Existing non-zero/high-confidence widths are not changed.
- Both-missing bins remain missing/zero and do not create invented boundaries.
- Long one-sided runs beyond the documented threshold remain uninferred.
- Inferred boundary points carry explicit low-confidence/inferred metadata.
- `computeBoundaries` without the new option returns the same output as before.
- CLI `--infer-missing-widths` writes output with inferred counts in summary.
- Existing `npm test` remains green.
- `npm run build` succeeds and `dist/compare.html` is current.
- Visual QA on Spa:
  - Regenerate boundaries with width smoothing, boundary smoothing, and missing-width inference.
  - Bus Stop should no longer lose one side through the short direction-change gap.
  - La Source may still show noisy learned data; document whether inference helps or not.

**Suggested tests:**

- Add unit tests near `scripts/test_compute_boundaries.js` or create `scripts/test_boundary_width_inference.js`.
- Include at least:
  - **Short one-sided run:** complete bins around a short run infer the missing side with expected width.
  - **Long one-sided run:** same data but run length > threshold remains zero/uninferred.
  - **Both missing:** no inference.
  - **No local context:** no inference.
  - **High-confidence preserved:** non-zero widths unchanged.
  - **Boundary integration:** `computeBoundaries({ ..., inferMissingWidths: true })` uses inferred width for offset.
  - **Default unchanged:** same fixture without inference matches pre-phase output exactly.
  - **CLI round-trip:** `--infer-missing-widths` exits 0 and reports inferred counts.

**Visual QA commands:**

```bash
node scripts/compute_boundaries.js \
  --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
  --profile data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
  --out data/circuit-de-spa-francorchamps-endurance/default/boundaries-inferred.json \
  --smooth --smooth-boundary 5 --infer-missing-widths --overwrite

node scripts/profile_viewer.js \
  data/circuit-de-spa-francorchamps-endurance/default/width-profile.json \
  --path data/circuit-de-spa-francorchamps-endurance/default/path.json \
  --boundaries data/circuit-de-spa-francorchamps-endurance/default/boundaries-inferred.json \
  data/circuit-de-spa-francorchamps-endurance/default/spa-view-inferred.html
```

Then open `spa-view-inferred.html` and compare against the current `spa-view.html` / browser Phase 10 rendering.

**Out of scope:**

- Importing TUMFTM or any external track data.
- Claiming inferred boundaries are official track limits.
- Phase 11 low-confidence styling in the browser.
- Filled polygons.
- Automatic boundary/profile discovery.
- Large refactors of width profile generation unless required by the tests.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current.
- Visual QA findings are documented.
- `phases_track_outline/09.3-infer-missing-boundary-widths/learnings.md` exists.
- `phases_track_outline/09.3-infer-missing-boundary-widths/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Commit directly on `main`.

**Stop at green.** Do not start TUMFTM import, Phase 11 styling, or other boundary-quality work.