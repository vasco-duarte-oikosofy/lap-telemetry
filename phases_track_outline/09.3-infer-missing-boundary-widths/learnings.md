# Learnings — Phase 09.3 Missing Boundary Width Inference

1. **Inference should use the active width representation.** When `--smooth` is enabled, the helper uses smoothed widths to decide whether a side is actually missing and to compute the local total width. This keeps the CLI behavior aligned with the geometry that will be rendered.

2. **Default output must stay byte-shape compatible.** The new summary fields and `infer_missing_widths` marker are only present when inference is explicitly enabled, so existing `computeBoundaries` and CLI output shapes remain unchanged by default.

3. **Boundary summary counts should reflect emitted boundary points.** The pure profile helper can infer samples that do not have matching path points; `computeBoundaries` reports only inferred boundary points that are actually emitted.

4. **Spa inference is conservative with current data.** With the default heuristic, Spa produced 12 inferred left boundary points and 8 inferred right boundary points after width smoothing and boundary smoothing. La Source remains primarily a noisy learned-data problem rather than a missing-one-side problem.
