# Handoff — Phase 09.3 Missing Boundary Width Inference

State on disk:

- `scripts/boundary_width_inference.js` (new)
  - Exports `inferMissingWidths(profileSamples, { window = 10, maxRun = 10, minCompleteNeighbors = 2, useSmooth = false })`.
  - Infers only exact one-sided bins: one active width is zero/missing and the other is positive.
  - Uses the median of nearby complete/high-confidence total widths.
  - Skips both-missing bins, long one-sided runs, bins without enough local complete neighbors, and non-positive inferred widths.
  - Preserves raw fields and adds `left_width_inferred_m` / `right_width_inferred_m`, side inferred flags, `inferred_status`, and low confidence metadata.

- `scripts/compute_boundaries.js`
  - `computeBoundaries({ ..., inferMissingWidths: true })` applies inferred widths before offsetting boundaries.
  - Default behavior is unchanged when inference is omitted/false.
  - Inferred boundary points have `status: "inferred-one-sided"`, `confidence: 0.35`, `inferred: true`, and `inferred_side`.
  - CLI supports `--infer-missing-widths`.
  - CLI/JSON summary includes `inferred_left_widths` and `inferred_right_widths` only when inference is enabled.

- `scripts/test_boundary_width_inference.js` (new)
  - Covers short one-sided inference, long-run refusal, both-missing refusal, no-local-context refusal, preserving complete widths, `computeBoundaries` integration/default behavior, and CLI round trip.

- `package.json`
  - Adds `node scripts/test_boundary_width_inference.js` to `npm test`.

- `data/circuit-de-spa-francorchamps-endurance/default/`
  - Regenerated local QA artifacts:
    - `boundaries-inferred.json`
    - `spa-view-inferred.html`
  - Current generated summary: 5615 left/right boundary points, 12 inferred left points, 8 inferred right points.

Visual QA notes:

- The heuristic improved only short, well-contextualized one-sided spans. The generated data marks inferred points explicitly for Phase 11 styling.
- La Source remains noisy; inference does not materially solve that because the dominant problem is oscillating learned edge data rather than short one-sided absence.
- Bus Stop should be checked in the generated `spa-view-inferred.html`; the inferred sections are present in data but deliberately conservative.

Verification:

- `npm test` passes.
- `npm run build` passes and rewrote `dist/compare.html`.

Deferred:

- Phase 11 styling for `inferred-one-sided` / low-confidence boundary sections.
- Broader boundary-quality/envelope work for noisy sections like La Source.
- External/official track geometry import remains out of scope.
