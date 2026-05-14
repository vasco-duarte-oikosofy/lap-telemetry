# Phase 01a — Heatmap Ribbon, Single Lap

**Your task:** Implement Phase 01a from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 1a — Heatmap ribbon, single lap"
2. Read `phases/00.6-track-outline/handoff.md` to understand the current state
3. Implement the heatmap ribbon feature per the spec
4. Write tests first (following TESTING_LESSONS.md)
5. Follow XP working agreements in AGENTS.md

**Key requirements:**
- Implement `colorForNet(net: number): string` function with the spec'd color ramp:
  - `-1` (full brake) → `#0a3d91` (dark blue)
  - `0` (coasting) → `#2a3340` (neutral mid)
  - `+1` (full throttle) → `#0f7a2e` (dark green)
- Implement 256-entry LUT for fast lookup
- Implement `drawRibbon()` that draws filled quads per segment (NOT a single path)
- Lap A upgrades to heatmap ribbon; Lap B remains 1px polyline
- Add 1px darker stroke on each side of ribbon for legibility
- Feature flag: `features.mapHeatmapSingleLap`

**Color ramp interpolation:**
- Interpolate in OKLCh (or HSL as fallback) for perceptually smooth transitions
- Brake side: light blue → dark blue as brake increases
- Throttle side: light green → dark green as throttle increases
- Never pass through muddy brown

**Acceptance criteria (from spec):**
- Unit test: `colorForNet(-1) === '#0a3d91'`, `colorForNet(0) === '#2a3340'`, `colorForNet(1) === '#0f7a2e'` (exact match)
- Unit test: `colorForNet(-0.5)` is closer in OKLCh distance to brake endpoint than neutral
- Unit test: `colorForNet(0.5)` is closer in OKLCh distance to throttle endpoint than neutral
- Unit test: 256-entry LUT matches `colorForNet` to within rounding at integer positions
- Render test: braking-zone positions show brake-blue colors
- Render test: throttle-zone positions show throttle-green colors
- Visual: brake zones unmistakably blue, throttle zones unmistakably green

**Out of scope:**
- Lap B as a ribbon (Phase 1c)
- The `s`-based lookup (Phase 1b)
- Side-by-side offset (Phase 1c)
- Zoom/pan (Phase 2)

**When done:**
- `npm test` passes (all existing tests + new 01a tests)
- `phases/01a-heatmap-single-lap/learnings.md` exists
- `phases/01a-heatmap-single-lap/handoff.md` exists
- Commit on branch `phase/01a-heatmap-single-lap`
- Update `phases/PLAN` to mark 01a as DONE

**Stop at green:** When acceptance passes, commit and stop. Don't start Phase 1b.

---

## Implementation Notes

### Ribbon Geometry
Each segment between sample `i` and `i+1` should be rendered as a filled quad:
1. Compute unit normal perpendicular to segment direction
2. Extrude by `±ribbonWidth/2` along the normal
3. Fill the quad with `colorForNet(avg(net_i, net_{i+1}))`
4. Use `ctx.beginPath()` + `lineTo()` per quad, fill per quad
5. Do NOT try to do a single path with one fill — every segment has its own color

### Net Pedal Input
`net = throttle - brake`, range `[-1, +1]`
- Full brake, no throttle: `net = -1`
- Coasting (neither): `net = 0`
- Full throttle, no brake: `net = +1`
- Overlap (trail braking): resolves by net value

### File Organization
Follow existing file architecture:
- Create new module(s) for color ramp (`colorRamp.js` or similar)
- Keep files under 200 lines (hard ceiling: 437 lines like `main.js`)
- One file, one job

### Known Limitation from Phase 00.6
The offset polyline jitter in high-curvature corners (Eau Rouge) is documented in `phases/00.6-track-outline/learnings.md`. The ribbon rendering approach should be more stable since it computes normals per-segment rather than per-point offset.
