# Learnings — U3c TC panel

- The TC panel was the only multi-lap panel still using a non-identity colour (`var(--throttle)`) instead of lane-identity colours (`var(--session)`/`var(--ref)`). The ABS panel has the same pattern — single session trace with `var(--brake)` — and likely needs the same treatment in a future slice.
- `step: true` is correct for binary signals (TC, ABS). No interpolation between 0 and 1.
- No downstream code changes needed; the renderer already handles arrays of channels with `trace: 'ref'` and `dash: true`.