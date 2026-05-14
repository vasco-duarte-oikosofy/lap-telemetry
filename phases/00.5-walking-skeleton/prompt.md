# Phase 00.5 — Walking Skeleton

**Goal:** Draw both laps as 1px polylines on the same canvas, fitted to view. No heatmap, no ribbons, no interaction.

**Feature flag:** `features.mapWalkingSkeleton`

**Tasks (from spec):**
1. Create a `<TrackHeatmapMap>` component with a canvas sized to its container (use `ResizeObserver`).
2. Implement `fitToView(samples, padding)` that returns a world→screen transform fitting both laps' bounding box with `padding` px of margin.
3. Draw Lap A as a 1px polyline in `lapA.color`.
4. Draw Lap B as a 1px polyline in `lapB.color`.
5. Draw a short white perpendicular tick at `s = 0` on Lap A (start/finish marker).
6. That's it.

**Acceptance criteria:**
- Render test: both polylines appear on the canvas, in the right colors, at the right scale.
- Render test: `fitToView` correctly bounds both laps with the specified padding (assert the transform numerically against a known fixture).
- Resize test: a `ResizeObserver` fires and the canvas re-fits without distortion. Aspect ratio is preserved.
- Visual smoke test: a real lap pair from the fixtures renders recognizably as the correct track shape.