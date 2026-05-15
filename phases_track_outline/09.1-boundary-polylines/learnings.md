# Learnings — Phase 09.1 Boundary Polylines

1. **Normal direction convention is critical.** The left normal when traveling in +z is (-tz, tx) = (-1, 0), which places the left boundary at negative x. This matches LMU's coordinate system where path_lateral_m < 0 means left side. The sign convention was verified with a straight-line fixture traveling +z and +x before tackling the arc test.

2. **Left/right offset formula:** Left boundary = path + normal × leftWidth, Right boundary = path - normal × rightWidth. The asymmetry (plus for left, minus for right) is because the normal always points left; the right side is the opposite of the normal direction.

3. **Arc test validates side consistency.** For a counter-clockwise quarter circle with center at (R,0), the center of curvature (R,0) is to the left of travel. The left boundary should be at larger radius (outside) and the right at smaller radius (inside). This is the natural geometric test beyond straight-line fixtures.

4. **Single-point paths produce zero tangent/normal.** `computeTangentNormal` returns (0,0,0,0) for a single point or coincident neighbors, since there's no direction information. The boundary point sits at the path position with zero offset in this degenerate case. This is acceptable — real tracks always have many points.

5. **Width profile has more samples than path points.** The width profile fills gap bins (all bins between min/max s_m, even if empty), while the path only has bins with actual data. The boundary computation matches by s_m key, so unmatched path points are simply counted and skipped. The typical mismatch for Spa is small (a few unmatched points).

6. **Smoothed widths fall back to raw when missing.** When `useSmooth` is true but `left_width_smooth_m` is null (e.g., long-gap barrier bins), the code falls back to raw `left_width_m`. This avoids producing NaN offset positions. Tests should cover this edge case in later phases when working with real data that has long gaps.

7. **Profile viewer boundaries add valuable visual QA.** Adding red/teal boundary polylines alongside the cyan center path on the 2D track map gives immediate visual feedback for geometry correctness — especially that boundaries don't cross or flip sides on curves.