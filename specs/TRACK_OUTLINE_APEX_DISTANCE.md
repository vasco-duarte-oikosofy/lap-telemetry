# Spec: Track Outline and Apex Distance

**Audience:** implementing agent (recorder, analysis tools, frontend telemetry app).
**Goal:** Use LMU/rF2 telemetry to (1) report how close each lap gets to configured apexes and (2) learn an approximate full-width track outline from recorded sessions.
**Method:** ship in small **subphases**. Each subphase is an independent delivery: one subphase, one acceptance run, committed directly on `main`. Do not bundle subphases. Every behavior change starts with a failing test, then the smallest code that makes it pass.

Subphases are independently shippable. A later stalled subphase must never make earlier work unusable. Old sessions without the new channels remain loadable throughout.

---

## XP working agreements

Follow the standing project rules in `AGENTS.md` and the working pattern from `track-heatmap-spec.md`:

1. **One subphase at a time.** Do not combine recorder, analysis, and UI work in one delivery.
2. **Test-first.** Turn every acceptance bullet below into an executable test before implementation.
3. **Small and green.** Each commit on `main` passes `npm test` and, when frontend output changes, `npm run build`.
4. **Refactors are separate commits.** Refactor first, prove green, then change behavior.
5. **YAGNI.** Implement only the current subphase. No generic track database, no editor UI, no official boundary import until a later spec asks for it.
6. **Always working.** Old Parquet files and current compare UI must continue to work after every subphase.
7. **Stop at green.** When the subphase acceptance passes, write `phases_track_outline/<phase>/learnings.md` and `handoff.md`, commit, and stop.

Before changing or adding tests, read `TESTING_LESSONS.md`.

---

## 0. Shared definitions

### 0.1 Raw recorder channels

Add these raw or near-raw fields when available from shared memory:

```text
raw_lap_distance_m
path_lateral_m
track_edge_m
distance_to_track_edge_m
surface_type_fl
surface_type_fr
surface_type_rl
surface_type_rr
terrain_name_fl
terrain_name_fr
terrain_name_rl
terrain_name_rr
```

Derived field:

```text
distance_to_track_edge_m = track_edge_m - abs(path_lateral_m)
```

Keep both distance channels:

- `lap_distance_m` — existing speed-integrated recorder distance, useful for smooth charts.
- `raw_lap_distance_m` — sim scoring distance, useful for joins with lateral/edge data.

Compatibility rule: if a source session lacks any new field, analysis and UI code must degrade to “not available”, not crash.

### 0.2 Apex annotation contract

One JSON file per track layout:

```json
{
  "track_id": "circuit-de-spa-francorchamps",
  "layout_id": "default",
  "corners": [
    {
      "id": "t1",
      "name": "La Source",
      "s_start_m": 200,
      "s_end_m": 360,
      "apex_s_m": 285,
      "apex_side": "right"
    }
  ]
}
```

Initial annotations are manual. Visual editing is explicitly out of scope.

### 0.3 Apex metric contract

For each configured corner and lap, compute:

```ts
type ApexMetric = {
  corner_id: string;
  corner_name: string;
  lap: number | string;
  apex_distance_m: number | null;
  apex_timing_error_m: number | null;
  surface_type: string | null;
  terrain_name: string | null;
  sample_s_m: number | null;
};
```

Rules:

1. Select samples whose `raw_lap_distance_m` is between `s_start_m` and `s_end_m`.
2. Find the sample closest to `apex_s_m`.
3. Report inside-edge distance near that apex sample.
4. `apex_timing_error_m = sample_s_m - apex_s_m`; positive means late, negative means early.
5. Surface/terrain uses the wheel(s) on the apex side if available.

### 0.4 Width profile contract

The learned profile is approximate, sim-derived, and not official boundary geometry:

```json
{
  "track_id": "circuit-de-spa-francorchamps",
  "layout_id": "default",
  "bin_size_m": 1,
  "samples": [
    {
      "s_m": 0,
      "left_width_m": 7.4,
      "right_width_m": 6.8,
      "left_sample_count": 12,
      "right_sample_count": 9,
      "confidence": 0.92
    }
  ]
}
```

Binning rule for raw samples:

```text
if path_lateral_m < 0:
  left_width[s_bin] = max(left_width[s_bin], track_edge_m)
else:
  right_width[s_bin] = max(right_width[s_bin], track_edge_m)
```

### 0.5 Feature flags / delivery switches

Use the smallest existing feature-flag or configuration mechanism available in the codebase. Planned switches:

```text
features.recordTrackEdgeChannels      // Phase 1
features.apexAnnotations              // Phase 3
features.apexMetrics                  // Phase 4
features.apexMetricsUi                // Phase 5
features.trackWidthProfileCli         // Phase 7
features.trackCenterPathCli           // Phase 9
features.learnedTrackOutline          // Phase 10
features.trackProfileDiagnostics      // Phase 12
```

CLI-only phases may use hidden commands instead of UI flags, but they still need safe defaults and rollback by not invoking the new command.

---

## Phase 0 — Schema compatibility safety net

**Why this exists:** Before adding fields, prove the app can keep loading old sessions and can tolerate optional future fields. This keeps every later recorder change reversible.

**Independence:** stands alone. No visible behavior change.

**Goal:** tests define the compatibility contract for old and new Parquet/session rows.

**Tasks:**
1. Add fixtures or fixture builders for a legacy row and a future row containing the new fields.
2. Add tests for the reader/summary/frontend data path that loads both shapes.
3. Ensure missing new fields are represented as `null`/`undefined` consistently at the boundary.
4. Do not change recorder output yet.

**Acceptance (executable tests):**
- Legacy session fixture loads without errors.
- Future-shaped session fixture with all new fields loads without errors.
- Missing `raw_lap_distance_m` falls back to existing distance only where a feature explicitly allows fallback.
- No rendered UI changes compared with the pre-phase baseline.

**Out of scope:** recording new channels, apex calculations, track profiles.

---

## Phase 1 — Recorder writes track-edge channels

**Why this exists:** All apex and width work depends on these raw channels existing in newly recorded sessions.

**Independence:** depends on Phase 0 safety tests. Feature flag `features.recordTrackEdgeChannels`.

**Goal:** new Parquet files include the raw lateral/edge/surface/terrain columns while old recording flow remains intact.

**Tasks:**
1. Add failing writer tests that assert the new columns and derived `distance_to_track_edge_m` are present.
2. Extend `lap_telemetry/recorder/connect.py` to read the scoring/wheel fields if present.
3. Extend `lap_telemetry/recorder/writer.py` to write the new columns.
4. Bump sidecar/schema version and document backward compatibility.
5. If a shared-memory field is unavailable, write null rather than inventing data.

**Acceptance (executable tests):**
- Writer fixture produces a Parquet row containing every field in §0.1.
- `distance_to_track_edge_m` equals `track_edge_m - abs(path_lateral_m)` for positive and negative lateral fixtures.
- A fixture with missing shared-memory fields records successfully with nulls.
- Existing recorder tests still pass.

**Out of scope:** interpreting apexes or building width profiles.

---

## Phase 2 — Frontend/session loader exposes new channels read-only

**Why this exists:** We need a thin vertical slice from Parquet to browser memory before computing user-facing metrics.

**Independence:** depends on Phase 1, but it is read-only and should not alter existing charts.

**Goal:** loaded lap samples can carry the new fields without showing anything new in the UI.

**Tasks:**
1. Add a frontend fixture with the new columns.
2. Map the fields into the existing lap/sample objects or a small adjacent metadata structure.
3. Add dev-only assertions/logging for invalid numeric values (`NaN`, negative `track_edge_m`, etc.).
4. Keep all existing panels visually unchanged.

**Acceptance (executable tests):**
- Loader test: a fixture row with new channels appears in browser-side sample data with exact values.
- Loader test: legacy rows load with the new properties absent/null.
- Screenshot/pixel smoke test: existing compare page is unchanged for a legacy fixture.

**Out of scope:** apex annotations, apex table, track outline rendering.

---

## Phase 3 — Apex annotation files and validator

**Why this exists:** Manual corner definitions are the smallest useful source of truth for apex coaching.

**Independence:** depends only on Phase 0. Feature flag `features.apexAnnotations`.

**Goal:** the project can load and validate per-layout apex annotation JSON files.

**Tasks:**
1. Create the smallest annotation fixture with one track, one layout, one corner.
2. Implement a validator for required fields, numeric ordering, unique corner IDs, and valid `apex_side` values.
3. Add a loader that returns validated annotations or a clear “not configured” result.
4. Do not wire it into the UI yet.

**Acceptance (executable tests):**
- Valid one-corner annotation loads successfully.
- Invalid `s_start_m >= apex_s_m`, `apex_s_m >= s_end_m`, duplicate IDs, and bad `apex_side` each fail with useful messages.
- Missing annotation file returns “not configured” without throwing in production code.

**Out of scope:** metric computation and annotation editing UI.

---

## Phase 4 — Apex metrics for one lap, one configured corner

**Why this exists:** This is the smallest user-valuable apex calculation and proves the math before rendering UI around it.

**Independence:** depends on Phases 2 and 3. Feature flag `features.apexMetrics`.

**Goal:** compute apex distance/timing for one lap against one configured corner.

**Tasks:**
1. Add a synthetic lap fixture with `raw_lap_distance_m`, lateral/edge fields, and deterministic apex sample.
2. Implement a pure function that computes the §0.3 metric for one lap and one corner.
3. Handle missing channels by returning null metric fields with a reason useful for logs/tests.
4. Keep output in memory only.

**Acceptance (executable tests):**
- Metric test: closest sample to `apex_s_m` is selected correctly.
- Metric test: `apex_timing_error_m` is positive for late and negative for early fixtures.
- Metric test: inside-edge distance uses the correct side and expected numeric value.
- Missing `raw_lap_distance_m`, `path_lateral_m`, or `track_edge_m` returns nulls instead of throwing.

**Out of scope:** multiple corners, surface/terrain, persistence, UI.

---

## Phase 4.1 — Apex metrics for all laps and corners

**Why this exists:** Expand the proven single-corner function without changing presentation.

**Independence:** depends on Phase 4.

**Goal:** compute apex metrics for every configured corner on every loaded lap.

**Tasks:**
1. Add a multi-lap, multi-corner fixture.
2. Implement a small aggregator that calls the Phase 4 pure function.
3. Preserve stable ordering: lap order, then annotation file corner order.
4. Add clear empty states for no annotations and no compatible telemetry.

**Acceptance (executable tests):**
- Aggregator returns one metric per `(lap, corner)` pair.
- Output ordering is stable and matches the fixture expectation.
- No annotation file returns an empty result with a `not_configured` status.
- Legacy telemetry returns an empty/unavailable result without breaking the compare page.

**Out of scope:** display and sidecar persistence.

---

## Phase 4.2 — Surface and terrain at apex

**Why this exists:** Surface at apex is useful, but it should not complicate the first metric slice.

**Independence:** depends on Phase 4.1.

**Goal:** include surface type and terrain name for the apex-side wheel(s).

**Tasks:**
1. Add fixtures for left and right apexes with distinct wheel surface/terrain values.
2. Map `apex_side: "left"` to left wheels and `"right"` to right wheels.
3. Pick a simple deterministic rule: prefer front wheel, fall back to rear wheel if front is missing.
4. Return null when no relevant wheel data exists.

**Acceptance (executable tests):**
- Right apex reports `surface_type_fr`/`terrain_name_fr` when available.
- Left apex reports `surface_type_fl`/`terrain_name_fl` when available.
- Missing front value falls back to rear on the same side.
- Missing side data returns nulls without changing distance/timing metrics.

**Out of scope:** surface overlays or quality diagnostics.

---

## Phase 5 — Apex metrics UI, text-only

**Why this exists:** Ship user-visible apex coaching before any map overlay or persistence. Text is the simplest useful UI.

**Independence:** depends on Phase 4.1; benefits from Phase 4.2 if present. Feature flag `features.apexMetricsUi`.

**Goal:** show an apex metrics panel/table for configured tracks.

**Tasks:**
1. Add a small panel in the existing compare page architecture following current UI conventions.
2. Display corner name, lap label, apex distance, early/late timing, and surface/terrain if available.
3. Show “No apex annotations for this track/layout” when not configured.
4. Show “Record a new session to capture track-edge channels” for legacy telemetry.

**Acceptance (executable tests):**
- Render test: configured fixture displays expected corner rows and formatted values.
- Render test: late values are labeled “late”; early values are labeled “early”.
- Render test: unconfigured track shows the no-annotation empty state.
- Render test: legacy fixture shows the missing-channel empty state and the rest of compare UI still works.

**Out of scope:** charts, map markers, editing annotations.

---

## Phase 6 — Optional apex metrics sidecar export

**Why this exists:** Persisting derived metrics is useful only after in-memory metrics prove valuable. Keep it optional and separate.

**Independence:** depends on Phase 4.1. It does not affect the UI.

**Goal:** add a command or helper that writes apex metrics JSON next to a session on demand.

**Tasks:**
1. Define the sidecar JSON shape using the §0.3 contract.
2. Add a CLI option or small command that reads a session and annotation file and writes metrics JSON.
3. Refuse to overwrite an existing sidecar unless an explicit overwrite option is passed.

**Acceptance (executable tests):**
- CLI test: fixture session + fixture annotations produce expected JSON.
- CLI test: existing output file is not overwritten by default.
- CLI test: legacy session produces JSON with unavailable/null metrics and a clear status.

**Out of scope:** automatic sidecar generation during recording.

---

## Phase 7 — Width profile CLI walking skeleton

**Why this exists:** A command-line profile generator is the smallest safe way to learn track width without touching the UI.

**Independence:** depends on Phase 1 for real data but can be built from fixtures. Feature flag/command `features.trackWidthProfileCli`.

**Goal:** generate unsmoothed left/right width bins from one or more sessions.

**Tasks:**
1. Add a fixture session with known `raw_lap_distance_m`, `path_lateral_m`, and `track_edge_m` values.
2. Add a CLI command such as `lap-telemetry track-profile sessions/*.parquet`.
3. Bucket by `raw_lap_distance_m` using a default `bin_size_m = 1`.
4. Apply the raw binning rule from §0.4.
5. Write JSON to an explicit output path first; default `tracks/<track-id>/<layout-id>/width-profile.json` can come later if needed.

**Acceptance (executable tests):**
- CLI fixture produces expected left/right max widths per bin.
- Multiple input sessions accumulate max widths and sample counts.
- Rows missing required fields are skipped and counted in a warning summary.
- Output JSON includes `track_id`, `layout_id`, `bin_size_m`, and `samples`.

**Out of scope:** smoothing, interpolation, confidence scoring beyond raw counts, center path.

---

## Phase 8 — Width profile confidence and gap flags

**Why this exists:** Consumers need to know which learned sections are trustworthy before rendering or coaching from them.

**Independence:** depends on Phase 7.

**Goal:** mark missing, one-sided, and low-sample bins explicitly.

**Tasks:**
1. Add fixture bins for complete, missing, left-only, right-only, and low-sample cases.
2. Add `confidence` and/or status fields using a simple documented rule.
3. Include aggregate summary counts in CLI output/logs.
4. Do not fill or smooth gaps yet.

**Acceptance (executable tests):**
- Complete bins receive higher confidence than one-sided or low-sample bins.
- Missing bins are present or reported explicitly; they are not silently omitted.
- CLI summary reports counts for missing, one-sided, and low-confidence bins.

**Out of scope:** interpolation/smoothing and rendering.

---

## Phase 8.1 — Interpolate and smooth width profile

**Why this exists:** Rendering needs continuous widths, but smoothing should not hide raw confidence problems.

**Independence:** depends on Phase 8.

**Goal:** produce render-ready left/right widths while preserving raw confidence/status.

**Tasks:**
1. Implement simple linear interpolation across short gaps.
2. Implement a small moving-average smoother with fixed window size.
3. Preserve raw sample counts and confidence separately from smoothed width values.
4. Refuse or flag interpolation across gaps larger than a documented threshold.

**Acceptance (executable tests):**
- Short missing gaps are linearly interpolated with expected values.
- Long gaps remain flagged low-confidence and are not silently bridged.
- Smoothing changes width values but does not change raw sample counts.

**Out of scope:** center path and boundary polygon generation.

---

## Phase 9 — Center/path polyline CLI

**Why this exists:** Width alone cannot draw an outline; we need a path in world coordinates.

**Independence:** depends on Phase 7 for command shape. Feature flag/command `features.trackCenterPathCli`.

**Goal:** generate a binned center/path polyline from recorded world positions and `raw_lap_distance_m`.

**Tasks:**
1. Add a fixture with known `pos_x_m`/`pos_z_m` (or current project-equivalent world coordinate names) and `raw_lap_distance_m`.
2. Bucket samples by distance and average world positions per bin.
3. Output a path JSON that can be paired with width profile JSON.
4. Keep smoothing minimal or absent in this phase.

**Acceptance (executable tests):**
- CLI fixture produces expected averaged points by bin.
- Missing position rows are skipped and counted in warnings.
- Output points are ordered by increasing `s_m`.
- Existing width-profile command behavior is unchanged.

**Out of scope:** normals, boundaries, UI rendering.

**Dev tool:** `scripts/profile_viewer.js` generates a standalone HTML viewer for visual QA of width profiles and center paths. Usage:

```bash
# Width profile only
node scripts/profile_viewer.js <profile.json>

# Width profile + 2D track map from path JSON
node scripts/profile_viewer.js <profile.json> --path <path.json> [output.html]
```

The viewer inlines all data and opens in any browser. The track map shows the center path as a cyan polyline; hovering a bin on the width chart highlights the corresponding point on the map with a yellow dot. Both panels support scroll-to-zoom and drag-to-pan.

---

## Phase 9.1 — Derive boundary polylines from path + widths

**Why this exists:** Boundary derivation is pure geometry and should be proven before canvas rendering.

**Independence:** depends on Phases 8.1 and 9.

**Goal:** compute left and right boundary polylines from a center/path polyline and width profile.

**Tasks:**
1. Add a simple straight-line fixture where expected normals are obvious.
2. Add a corner fixture to catch normal direction mistakes.
3. Implement tangent/normal calculation and width offsetting.
4. Keep output as data only.

**Acceptance (executable tests):**
- Straight-line fixture offsets left/right boundaries by exact expected distances.
- Curved fixture keeps left/right on consistent sides of travel.
- Low-confidence width bins propagate to boundary point status.

**Out of scope:** drawing the outline in the browser.

---

## Phase 9.2 — Smooth boundary polylines

**Why this exists:** Raw boundary polylines exhibit visible jitter caused by unsmoothed per-bin position noise in the center path and by per-bin normal oscillation. Smoothing the boundaries before rendering produces clean, usable track outlines.

**Independence:** depends on Phase 9.1.

**Goal:** apply smoothing to boundary polylines so the rendered outline is visually clean without losing geometric accuracy.

**Tasks:**
1. Add a fixture with known jitter to prove smoothing removes oscillation while preserving overall shape.
2. Implement a boundary smoothing function that operates on the output of `computeBoundaries`.
3. Integrate smoothing as an option (`--smooth-boundary`) in the `compute_boundaries` CLI.
4. Visual QA: regenerated boundaries with smoothing should show smooth, non-oscillating lines in the profile viewer.

**Acceptance (executable tests):**
- Straight-line fixture: smoothing a straight boundary returns the same straight line (no shape distortion).
- Jittered fixture: a boundary with artificial high-frequency oscillation is smoothed to a recognizable shape; the smoothed line has smaller max-per-point deviation from the true shape than the raw line.
- Curved fixture: smoothing a circular-arc boundary does not shrink the arc radius significantly (geometric accuracy preserved).
- Zero-width bins: points with zero width (one-sided or missing) are handled gracefully — they are not smoothed into non-zero positions.
- Gap handling: gaps in the path (missing s_m bins) do not cause smoothing to bridge across discontinuities.
- Window parameter: larger window = more smoothing; window=1 returns the original boundary.
- CLI: `--smooth-boundary N` accepts a non-negative integer, default 0; `--smooth-boundary 1` is identity.
- Existing tests remain green; `computeBoundaries` with no smoothing option returns the same output as before.

**Out of scope:** rendering, low-confidence styling, diagnostics, gap-filling.

**Deferred improvements from Phase 9.2/9.3 visual QA:**

1. **Curved-section boundary oscillation remains too high.** Spa/La Source still shows unacceptable boundary oscillation in some curved sections after positional smoothing. The observed jitter amplitude can approach the inferred track width, which suggests the boundary derivation is mixing per-bin extremes rather than tracing a stable physical edge. A future improvement should experiment with reconstructing a local left/right width envelope instead of only smoothing final `(x_m, z_m)` points: e.g. compute robust local maxima for left and right widths over short windows (roughly 3–5m to start), reject outlier edge hits, interpolate those maxima along `s_m`, and then derive boundaries from the stable envelope.
2. **One side of the outline disappears in some curves.** Visual QA shows that in some turns the left outline collapses/disappears, while in other turns the right outline collapses/disappears. This is the one-sided/zero-width data-coverage limitation: if the source bins have no observations for one side, Phase 9.2 preserves those zero-width points at the center path instead of inventing a boundary. Phase 9.3's short-gap local-total-width inference was too conservative to materially improve Spa Bus Stop: it inferred only a small number of emitted boundary points and the previous best visual output remained more coherent. A future boundary-quality phase should recover missing-side outlines from a stable local width envelope, symmetric track-width assumptions, or calibrated max-left/max-right interpolation before rendering treats the outline as complete.
3. **Do not invest further in presentation until geometry improves.** Phase 10 rendering proves the data path, but Spa visual QA shows the learned outline is not yet reliable track-boundary geometry. Phase 11 low-confidence styling can make uncertainty visible, but it will not fix the Bus Stop/La Source shape problems. Continue the original plan only where it gives a large expected benefit; otherwise prioritize robust boundary reconstruction or stop treating learned boundaries as user-facing track limits.

These should be treated as boundary-quality/calibration enhancements, separate from Phase 10 rendering.

---

## Phase 9.3 — Infer missing one-sided boundary widths from local total width

**Why this exists:** Visual QA after Phase 10 shows that one boundary side can disappear midway through turns such as Bus Stop, even when the other side is plausible and the lap trajectories are smooth. Collapsing zero-width one-sided bins to the center path makes the outline misleading and visually broken. A simple local-width assumption is a smaller step than importing external track geometry.

**Independence:** depends on Phases 8.1, 9.1, and 9.2. It improves the boundary JSON used by Phase 10 rendering but does not change rendering behavior directly.

**Goal:** when exactly one side of a boundary bin has zero/missing width, infer the missing side from nearby stable total track width, mark it low-confidence/inferred, and keep long unknown regions blank.

**Simple heuristic:**

```text
local_total_width = median(left_width + right_width) over nearby complete/high-confidence bins

if left_width == 0 and right_width > 0:
  inferred_left_width = max(local_total_width - right_width, 0)

if right_width == 0 and left_width > 0:
  inferred_right_width = max(local_total_width - left_width, 0)
```

Inference must be explicit in data, never silent. Preserve raw widths/counts/status and add fields such as `left_width_inferred_m`, `right_width_inferred_m`, `left_inferred`, `right_inferred`, or an equivalent small shape. Boundary points produced from inferred widths should carry a low-confidence status such as `inferred` / `inferred-one-sided` so Phase 11 can style them differently.

**Tasks:**
1. Add fixtures with complete bins, short one-sided gaps, long one-sided gaps, and changing track width.
2. Implement a pure helper that computes local median total width from nearby complete/high-confidence bins.
3. Infer the missing side only across short one-sided runs with enough local context.
4. Do not infer across long gaps or where both sides are missing.
5. Integrate inferred widths into `compute_boundaries.js` behind an explicit CLI option such as `--infer-missing-widths`.
6. Ensure existing default boundary output remains unchanged unless the option is enabled.
7. Regenerate Spa visual QA artifacts with `--smooth --smooth-boundary 5 --infer-missing-widths` and inspect Bus Stop and La Source.

**Acceptance (executable tests):**
- A one-sided bin inside a short run gets the missing side inferred from nearby median total width.
- Existing non-zero/high-confidence widths are not changed.
- Both-missing bins remain missing/zero and do not produce invented boundaries.
- Long one-sided runs beyond a documented threshold remain blank or uninferred.
- Inferred boundary points are marked with explicit low-confidence/inferred metadata.
- `computeBoundaries` without the new option returns the same output as before.
- CLI output includes a summary count for inferred left and right widths.
- Visual QA follow-up: Bus Stop did **not** materially improve with the conservative heuristic. The data contract is useful, but this phase should not be considered a successful boundary-quality fix for Spa.

**Out of scope:** importing TUMFTM or any external track data, official boundary claims, renderer styling changes, filled polygons, and automatic profile discovery.

---

## Phase 10 — Render learned track outline behind existing map

**Why this exists:** This is the first user-visible width-profile result. It should be a background context layer only, so it cannot break lap comparison.

**Independence:** depends on Phase 9.1 and the existing track map component. Feature flag `features.learnedTrackOutline`.

**Goal:** render left/right learned boundaries underneath current lap trajectories/ribbons.

**Tasks:**
1. Add a small fixture profile/path available to frontend tests.
2. Load the render-ready boundary data into the map layer.
3. Draw boundaries as faint low-contrast lines below trajectories/ribbons.
4. If no profile exists, render exactly as before.

**Acceptance (executable tests):**
- Render test: learned left/right boundaries appear under the lap trace for a fixture profile.
- Pixel/screenshot test: with no profile, map rendering matches the pre-phase baseline.
- Render test: lap trajectory/ribbons remain above and visually stronger than boundaries.
- Resize/zoom smoke test: boundaries transform with the same world-to-screen transform as lap data.

**Out of scope:** filled polygons, low-confidence styling, automatic profile discovery.

---

## Phase 11 — Low-confidence outline styling

**Why this exists:** Users must be able to distinguish learned-good sections from guessed or sparse sections.

**Independence:** depends on Phase 10.

**Goal:** visually distinguish low-confidence boundary segments.

**Tasks:**
1. Add fixture boundary segments with high and low confidence.
2. Draw low-confidence segments dashed or lower opacity.
3. Add a tiny legend entry only if low-confidence segments are present.

**Acceptance (executable tests):**
- Render test: low-confidence segments have a distinct style from high-confidence segments.
- Render test: legend appears only when low-confidence segments exist.
- Pixel/screenshot test: high-confidence rendering is unchanged from Phase 10 when all segments are high confidence.

**Out of scope:** diagnostics reports and surface overlays.

---

## Phase 12 — Profile diagnostics report

**Why this exists:** Before trusting a profile for coaching, we need an explicit quality report.

**Independence:** depends on Phases 8 and 9. Feature flag/command `features.trackProfileDiagnostics`.

**Goal:** generate a human-readable diagnostics report for a profile.

**Tasks:**
1. Add a CLI command or option that reads profile/path JSON and prints diagnostics.
2. Report missing bins, one-sided bins, low sample counts, long interpolated gaps, and total coverage.
3. Return non-zero only for malformed input, not for low confidence; low confidence is data, not a crash.

**Acceptance (executable tests):**
- Diagnostics fixture reports exact counts for missing/one-sided/low-confidence bins.
- Malformed JSON exits non-zero with a useful error.
- Valid-but-low-confidence profile exits zero and prints warnings.

**Out of scope:** improving the profile and UI overlays.

---

## Phase 13 — Calibration session workflow documentation

**Why this exists:** Better profiles require intentional data collection, but documentation can ship independently of code.

**Independence:** depends on Phase 7 existing, but does not change behavior.

**Goal:** document how to record calibration laps and run the profile tools.

**Tasks:**
1. Add a short guide describing left-edge, right-edge, kerb, and racing-line laps.
2. Document command examples for width profile, center path, boundaries, and diagnostics.
3. Include caveats about `mPathLateral`/`mTrackEdge` being approximate sim path data.

**Acceptance:**
- Documentation includes a complete command sequence from recording to diagnostics.
- Documentation explicitly says the outline is approximate and not official track limits.
- No code or rendered output changes.

**Out of scope:** automation or UI wizards.

---

## Polish backlog — each item is its own future subphase

Do not start these until the core phase they depend on is green. Each item needs its own tests, flag/switch, handoff, and commit.

1. **Apex metrics closeable drawer** *(depends on Phase 5)* — present the apex metrics UI as a drawer the user can open and close without disabling the feature flag.
2. **Apex markers on map** *(depends on Phase 5 + current map)* — draw apex points and small labels on the track map.
3. **Annotation editor UI** *(depends on Phase 3 + map interaction)* — drag apex markers and save JSON. Manual file editing remains enough until this is explicitly prioritized.
4. **Surface-type overlay** *(depends on Phase 4.2 + Phase 10)* — show kerb/grass/dirt near apex or along the outline.
5. **Filled track polygon** *(depends on Phase 10)* — fill between boundaries with subtle opacity. Keep boundaries visible.
6. **Profile auto-discovery** *(depends on Phase 10)* — find `tracks/<track>/<layout>/...` automatically instead of explicit profile input.
7. **Cross-session profile merge command** *(depends on Phase 8.1)* — merge existing profile JSON files without rereading raw Parquet.
8. **Official track data research/import** *(depends on diagnostics proving sim-derived limits are insufficient)* — investigate whether official or community boundary geometry is available and legally usable.

---

## What an agent should not do

- Do not modify `track-heatmap-spec.md` or `AGENTS.md` without explicit permission.
- Do not make apex metrics depend on learned width profiles; manual apex annotations plus recorder edge distance are enough for the first slices.
- Do not render learned outlines before the CLI/profile data is tested.
- Do not silently treat `lap_distance_m` as `raw_lap_distance_m` for apex/width calculations unless a phase explicitly defines that fallback.
- Do not hide profile uncertainty. Missing and low-confidence bins must remain visible in data and, once rendered, visible in UI.
- Do not introduce a database or server process. JSON sidecars/files are enough for these phases.
- Do not build annotation editing, minimaps, official FIA geometry, or smoothing knobs during the core phases.
- Do not let old sessions stop loading.

---

## Caveats

`mPathLateral` and `mTrackEdge` are rF2-style fields relative to an approximate sim path. LMU may expose useful values, but they must be validated empirically with recorded data. Treat the learned outline as approximate and sim-derived, never as official survey geometry or a definitive track-limits judge.
