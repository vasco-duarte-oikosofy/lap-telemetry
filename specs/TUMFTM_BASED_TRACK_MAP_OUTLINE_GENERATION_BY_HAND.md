# Spec: TUMFTM-Based Track Map Outline Generation By Hand

**Audience:** implementing agent, data-prep agent, frontend telemetry app.
**Goal:** Create static simulator-coordinate track outline templates by manually aligning TUMFTM racetrack database geometry to our existing simulator trajectory data, then automatically load the matching outline by track name and overlay telemetry trajectories on top.

This spec describes a **by hand / offline data-prep workflow**, not an in-app editor. The generated outline is a static artifact checked into the project and consumed by the compare UI.

---

## 1. Problem statement

Our recorded telemetry already contains simulator-space trajectory samples, for example:

```text
sim_x
sim_y
lap
track_name
```

These coordinates are good for drawing the driven line, but they do not provide the full track outline. TUMFTM provides real-world track reference data with:

```text
x_m
y_m
w_tr_right_m
w_tr_left_m
```

The TUMFTM data is in its own meter-based coordinate frame. The simulator data is in the game engine's local coordinate frame. To use TUMFTM as an outline source, we need to manually align TUMFTM coordinates to simulator coordinates and save the transformed result as a static per-track map template.

---

## 2. Non-goals

Out of scope for this spec:

- automatic satellite image processing
- automatic OSM import
- in-browser track outline editor
- perfect official FIA boundary accuracy
- automatic TUMFTM-to-sim matching without human review
- live generation during normal app use
- changing trajectory recording format

The first version should be a simple, auditable offline pipeline.

---

## 3. Source data

### 3.1 TUMFTM racetrack database input

Use the TUMFTM racetrack database files as the external source for centerline and track widths.

Each row is expected to contain:

```text
x_m, y_m, w_tr_right_m, w_tr_left_m
```

Meaning:

- `x_m`, `y_m`: smoothed centerline point in TUMFTM coordinates.
- `w_tr_right_m`: track width to the right of centerline, in direction of travel.
- `w_tr_left_m`: track width to the left of centerline, in direction of travel.

From this we can derive:

```text
centerline
left_boundary
right_boundary
```

### 3.2 Existing simulator trajectory input

Use one or more clean laps from our existing recorded telemetry for the same track layout.

The preferred lap is:

- a complete valid lap
- not an out-lap or in-lap
- no obvious GPS/sim-position discontinuities
- reasonably close to a normal racing line

The simulator trajectory is the coordinate-space anchor. The final outline must be stored in the same coordinate frame as the telemetry samples that the frontend already plots.

---

## 4. Generated artifact

Create one static JSON file per simulator track/layout.

Suggested path:

```text
data/track-outlines/<sim_track_slug>.json
```

Example:

```text
data/track-outlines/spa-francorchamps.json
```

Suggested schema:

```json
{
  "schema_version": 1,
  "source": "TUMFTM manual alignment",
  "track_name": "Circuit de Spa-Francorchamps",
  "sim_track_name": "Spa-Francorchamps",
  "layout_name": "default",
  "coordinate_system": "sim_xy",
  "units": "sim_units",
  "alignment": {
    "method": "manual_similarity_transform",
    "tumftm_track_file": "tracks/Spa.csv",
    "notes": "Aligned using start/finish straight, Eau Rouge/Raidillon, Les Combes, Bus Stop."
  },
  "centerline": [
    { "x": 123.45, "y": -456.78, "s_m": 0.0 }
  ],
  "left_boundary": [
    { "x": 120.1, "y": -460.2, "s_m": 0.0 }
  ],
  "right_boundary": [
    { "x": 126.8, "y": -453.3, "s_m": 0.0 }
  ]
}
```

The frontend should treat this as read-only static geometry.

---

## 5. Offline generation workflow

### 5.1 Load TUMFTM centerline and widths

Read the TUMFTM CSV and parse each row into:

```ts
type TumftmTrackPoint = {
  x_m: number;
  y_m: number;
  w_tr_right_m: number;
  w_tr_left_m: number;
};
```

### 5.2 Derive boundary points in TUMFTM coordinates

For each centerline point:

1. Estimate the tangent from neighboring centerline points.
2. Compute the normal vector perpendicular to the tangent.
3. Offset by width left/right.

Conceptually:

```text
tangent_i = normalize(point[i + 1] - point[i - 1])
normal_i = perpendicular(tangent_i)

right_boundary_i = center_i + normal_i * w_tr_right_m
left_boundary_i  = center_i - normal_i * w_tr_left_m
```

The exact normal sign may need to be flipped during manual review if the left/right sides are visually reversed.

### 5.3 Load simulator trajectory reference lap

Extract a clean lap's trajectory from our existing telemetry:

```text
sim_x, sim_y
```

Optionally resample both the TUMFTM centerline and simulator trajectory to a similar number of points by normalized lap distance. This makes visual comparison easier, but the manual alignment remains the source of truth.

### 5.4 Manually align TUMFTM geometry to simulator coordinates

Apply a 2D similarity transform from TUMFTM coordinates into simulator coordinates:

```text
sim_point = scale * rotate(tumftm_point) + translate
```

The manual alignment parameters are:

```json
{
  "scale": 1.0,
  "rotation_rad": 0.0,
  "translate_x": 0.0,
  "translate_y": 0.0,
  "flip_x": false,
  "flip_y": false,
  "reverse_point_order": false
}
```

The by-hand process should use a temporary script or notebook that displays:

- the simulator trajectory as a reference line
- the transformed TUMFTM centerline
- the transformed TUMFTM left/right boundaries

The operator adjusts scale, rotation, translation, optional axis flips, and optional point-order reversal until the TUMFTM centerline and boundaries line up with the simulator trajectory.

Useful alignment landmarks:

- start/finish straight
- hairpins
- chicanes
- long straights
- distinctive corner sequences
- highest-curvature sections

Acceptance for manual alignment is visual, but should be documented in the generated file's `alignment.notes`.

### 5.5 Export static simulator-coordinate outline

Once alignment is acceptable, transform all TUMFTM-derived geometry into simulator coordinates and write the static JSON artifact.

The exported arrays should include:

- transformed centerline
- transformed left boundary
- transformed right boundary
- optional `s_m` distance along the TUMFTM centerline

Do not require the frontend to know about TUMFTM coordinate frames. The frontend should only consume simulator-space `x,y` arrays.

---

## 6. Runtime frontend behavior

### 6.1 Track name lookup

When a telemetry session is loaded, the app already knows or can infer a track name from session metadata.

Add a small manifest mapping simulator track names to static outline files:

```json
{
  "Spa-Francorchamps": "data/track-outlines/spa-francorchamps.json",
  "Monza": "data/track-outlines/monza.json"
}
```

Matching should be conservative:

1. exact normalized track name match
2. known alias match from manifest
3. no fuzzy auto-selection in the first version

If no outline exists, the app continues to render the current trajectory-only view.

### 6.2 Overlay order

Render order:

1. static track outline background
2. optional centerline/reference line
3. telemetry trajectory/racing line
4. markers, hover state, selected sample, etc.

The outline must not alter trajectory coordinates. Both are already in the same simulator coordinate system.

### 6.3 Styling

Initial styling can be simple:

- left/right boundaries: thin muted gray lines
- centerline: optional dashed low-contrast line
- telemetry trajectory: existing colored lap line

The static outline is context. The telemetry trajectory remains the primary data visualization.

---

## 7. Validation checklist for each generated track

Before checking in a generated outline file:

- The static outline loads for the intended simulator track name.
- The existing trajectory overlays without coordinate conversion at runtime.
- Major corners visually align with the driven trajectory.
- Start/finish area is in the correct location.
- Track orientation is correct; not mirrored or reversed.
- Left/right boundary widths look plausible.
- The app still works when the outline file is missing.
- The JSON includes source and alignment notes.

---

## 8. Risks and mitigations

### 8.1 TUMFTM layout differs from simulator layout

Some simulators model different years, layouts, chicanes, or track limits.

Mitigation: keep the mapping per simulator track/layout and document any mismatch in `alignment.notes`.

### 8.2 Coordinate handedness may differ

Simulator `x,y` axes may be mirrored relative to TUMFTM.

Mitigation: support manual `flip_x`, `flip_y`, and point-order reversal during offline alignment.

### 8.3 Widths may not match simulator drivable surface

TUMFTM widths come from satellite/image processing and may not match sim track limits exactly.

Mitigation: treat the outline as approximate visual context, not as a rules/track-limits source.

### 8.4 Manual alignment can drift

A simple scale/rotate/translate transform may not perfectly align if either source has local distortion.

Mitigation: start with similarity transform only. If a later track needs more, add a separate spec for piecewise or control-point warping.

---

## 9. Suggested implementation subphases

### Phase 1: Static outline contract

- Define the JSON schema in documentation.
- Add one hand-authored fixture outline in simulator coordinates.
- Load it by exact track name.
- Render it behind existing trajectory.

### Phase 2: Offline TUMFTM conversion script

- Add a script that reads TUMFTM CSV.
- Derive boundaries from centerline and widths.
- Apply manually supplied transform parameters.
- Export static simulator-coordinate JSON.

### Phase 3: Manual alignment workflow

- Add a temporary/offline visual preview command or notebook.
- Show simulator reference lap plus transformed TUMFTM geometry.
- Let the operator iterate transform parameters outside the app.

### Phase 4: Track manifest and aliases

- Add a manifest for simulator track names and aliases.
- Keep matching explicit and deterministic.
- Fall back gracefully when no outline exists.

---

## 10. Core principle

TUMFTM data is used only during offline preparation. The app should not perform TUMFTM alignment at runtime.

At runtime, the app simply does:

```text
session track name
→ static outline JSON in simulator X/Y coordinates
→ draw outline
→ draw existing trajectory on top
```

This keeps the runtime simple, makes generated outlines reviewable, and lets us add tracks incrementally by hand without destabilizing existing telemetry visualization.
