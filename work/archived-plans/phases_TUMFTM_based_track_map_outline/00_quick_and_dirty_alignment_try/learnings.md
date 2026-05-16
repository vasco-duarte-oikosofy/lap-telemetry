# Learnings — Phase 00 Quick TUMFTM Alignment Try

1. **A plain global transform is enough for the first Spa check.** The rough alignment that visually fits the simulator lap is scale `0.998`, rotation `-0.0116` rad, translate `(-154, 634)`, with no flips and no reversed point order.

2. **TUMFTM Spa geometry is much cleaner than the learned outline in the known problem areas.** In the overview artifact, La Source and Bus Stop render as smooth continuous corridors instead of jagged/collapsed learned-boundary fragments.

3. **Reloading exported geometry needs identity semantics.** The tool treats an exported `centerline`/`left_boundary`/`right_boundary` JSON as already-aligned fixed geometry, so reloading `aligned-outline-spike.json` reproduces the same visual placement without applying the saved transform a second time.

4. **The smoke test caught parse/export regressions but not rendering validity.** A manual/visual pass was still necessary; during validation prep, a canvas-rendering bug from passing `transformPoint` directly to `Array.map()` was found and fixed.

5. **The spike should stay offline.** Nothing was wired into the compare UI; the artifact is only evidence for the Phase 00 gate and a possible input to later static-outline work.
