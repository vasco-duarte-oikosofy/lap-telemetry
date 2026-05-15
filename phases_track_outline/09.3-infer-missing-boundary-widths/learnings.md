# Learnings — Phase 09.3 Missing Boundary Width Inference

1. **Inference should use the active width representation.** When `--smooth` is enabled, the helper uses smoothed widths to decide whether a side is actually missing and to compute the local total width. This keeps the CLI behavior aligned with the geometry that will be rendered.

2. **Default output must stay byte-shape compatible.** The new summary fields and `infer_missing_widths` marker are only present when inference is explicitly enabled, so existing `computeBoundaries` and CLI output shapes remain unchanged by default.

3. **Boundary summary counts should reflect emitted boundary points.** The pure profile helper can infer samples that do not have matching path points; `computeBoundaries` reports only inferred boundary points that are actually emitted.

4. **Spa inference is conservative with current data.** With the default heuristic, Spa produced 12 inferred left boundary points and 8 inferred right boundary points after width smoothing and boundary smoothing. La Source remains primarily a noisy learned-data problem rather than a missing-one-side problem.

5. **Visual QA says 9.3 is not a useful Bus Stop improvement.** Comparing `spa-view-inferred.html` against the previous best Bus Stop screenshot showed that 9.3 did not restore a believable continuous track corridor. The previous best remains visually better: imperfect and bulgy, but more coherent. The 9.3 artifact still shows collapsed/jagged boundary fragments through the chicane because the heuristic only fills a tiny number of short one-sided gaps. Treat this phase as a narrow data-contract improvement, not as the solution to Bus Stop boundary quality.

6. **Next boundary-quality work should not just tune 9.3.** The likely fix is a broader local left/right width envelope or robust edge reconstruction over the affected section, rather than increasing `maxRun` or blindly inferring more one-sided bins. Phase 11 can style inferred data, but styling will not solve the underlying Bus Stop geometry.
