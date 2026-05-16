# Learnings — Phase 09.2 Boundary Smoothing

1. **Absolute moving averages shrink/cut curves.** A plain moving average over `(x_m, z_m)` reduced jitter but displaced curved sections because averaging coordinates directly cuts corners. The final implementation uses a local quadratic fit over `s_m`, which preserves straight lines and circular arcs much better in unit tests.

2. **Zero-width points must be true barriers.** Keeping zero-width points fixed is not enough; smoothing must not see across them. Otherwise points on either side of a collapsed boundary can pull each other around turns. The smoother now splits segments at `width_m === 0` and at discontinuous `s_m` gaps.

3. **Smoothing helps but does not solve boundary quality.** Spa visual QA still shows unacceptable oscillation in some curved sections (notably La Source). The remaining problem appears to be upstream data quality / edge-envelope derivation rather than just output smoothing.

4. **One-sided coverage remains visible.** Many Spa bins have zero width on one side, so one outline collapses to the center path in some turns. Phase 9.2 intentionally preserves those zero-width points instead of inventing track edges.

5. **Window 5 is the committed default artifact.** Window 10 was briefly tested during visual QA and produced more smoothing, but the final regenerated `boundaries.json` uses `--smooth-boundary 5` to match the phase prompt and executable tests.
