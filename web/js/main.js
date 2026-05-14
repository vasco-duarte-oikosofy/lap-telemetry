// ── Utility helpers ────────────────────────────────────────────────────────────
import { storeKey, fileStem, formatDuration, lapStatusBadges, formatPickLabel,
         shortVehicle, shortSetup, showError, clearError, setBadge,
         applyLapColour, persistLapColours, loadPersistedColours,
         persistZoom, loadPersistedZoom,
         HEX_RE, LAP_COLOUR_DEFAULTS, LAP_COLOUR_LS_KEY, ZOOM_LS_KEY
       } from './utils.js';

// ── Data pipeline ──────────────────────────────────────────────────────────────
import {
  fileToAsyncBuffer, readColumns, buildSegments, annotateSegments,
  interpAt, resample, computeDeltaT, computeKeepIndices, smoothLapTime,
  smoothDt, smoothGear, deriveSectorDistances, niceRange, buildPolylinePts,
  computeTrackBounds, buildTrackTransform, buildTrackPolylinePts,
  computeMedianFrameDistanceDelta, computeNiceYTicks,
  PARTIAL_DIST_FRAC, PARTIAL_DUR_FRAC, ROLLING_DIST_M
} from './pipeline.js';

// ── Application state ─────────────────────────────────────────────────────────
import { store, pendingSidecars, panelOrder, DEFAULT_PANEL_ORDER, PANEL_ORDER_LS_KEY,
         persistPanelOrder, state, getCurrentMapMode, setCurrentMapMode, features, devFeatures, setFeatureFlag, setDevFeatureFlag } from './appState.js';

// ── Circuit map rendering ───────────────────────────────────────────────────────
import { renderCircuitMap, renderHeatmapSegments, renderMapLegend, updateZoomArc,
         HEATMAP_RAMPS, HEATMAP_CHANNELS } from './circuitMap.js';

// ── Track heatmap map (Phase 00.5 walking skeleton) ────────────────────────────
import { renderWalkingSkeleton, initTrackHeatmapResize, fitToView } from './trackHeatmapMap.js';
import { assertStrictlyMonotonic } from './sLookup.js';

// ── Map interaction (Phase 02 zoom/pan) ──────────────────────────────────────
import { createMapInteraction, setBaseTransform } from './mapInteraction.js';

// ── Panel rendering ─────────────────────────────────────────────────────────────
import { renderPanel, renderDtPanel } from './panels.js';

// ── Cursor, tooltip, zoom ───────────────────────────────────────────────────────
import { initCursorAndZoom } from './cursor.js';

// ── Shared constants ────────────────────────────────────────────────────────────
import { SVG_W, PAD, PLOT_W } from './constants.js';

// ── UI interaction ─────────────────────────────────────────────────────────────
import { initUI, rebuildPickers, parsePickerValue, addSessionEntry, refreshSessionListBadges } from './ui.js';

// ── Debug hooks ──────────────────────────────────────────────────────────────
import { installDebugHooks } from './debugHooks.js';

// ── Panel configuration ─────────────────────────────────────────────────────
import { COLUMNS, PANEL_DEFS } from './panelConfig.js';

// ── CDN imports ────────────────────────────────────────────────────────────
import { parquetRead, parquetMetadataAsync } from 'https://cdn.jsdelivr.net/npm/hyparquet@1/+esm';
import { compressors } from 'https://cdn.jsdelivr.net/npm/hyparquet-compressors@1/+esm';

// ── Main render ───────────────────────────────────────────────────────────────

let currentSessionBins = null; // { col: Float64Array }
let currentRefBins     = null;
let currentMaxDist     = 0;
let currentDtBins      = null;
let currentTrackX      = null; // Resampled track coordinates (session)
let currentTrackZ      = null;
let currentRefTrackX   = null; // Resampled track coordinates (reference)
let currentRefTrackZ   = null;
let trackHeatmapObserver = null; // ResizeObserver for heatmap canvas
let currentZoomRange   = null; // { start, end }
let currentOverlapRange = null; // { start, end } — distance window covered by BOTH laps
let trackTransform     = null; // Updated by renderCircuitMap
let currentLapARaw     = null;   // Phase 01b: raw arrays for s alignment
let currentLapBRaw     = null;   // Phase 01b: raw arrays for s alignment
let mapInteraction     = null;   // Phase 02: zoom/pan interaction controller
function renderAll(sessionEntry, sessionSegIdx, refEntry, refSegIdx) {
  const sSeg = sessionEntry.segments[sessionSegIdx];
  const rSeg = refEntry.segments[refSegIdx];

  // Per-file trackLen for the boundary-artifact heuristic. Use the max maxDist
  // across the file's segments — same convention annotateSegments uses.
  const sTrackLen = sessionEntry.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
  const rTrackLen = refEntry.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);

  // Filter the SHM lap-boundary artifact frame (see computeKeepIndices). All
  // channel resampling uses the same `keep` index list so values stay aligned
  // with distances after the drop.
  const sKeep = computeKeepIndices(sessionEntry.data.lap_time_s, sessionEntry.data.lap_distance_m, sSeg.start, sSeg.end, sTrackLen);
  const rKeep = computeKeepIndices(refEntry.data.lap_time_s,     refEntry.data.lap_distance_m,     rSeg.start, rSeg.end, rTrackLen);

  const sDistRaw  = sKeep.map(i => sessionEntry.data.lap_distance_m[i]);
  const rDistRaw  = rKeep.map(i => refEntry.data.lap_distance_m[i]);

  // Phase 01b: strictly-monotonic guard (dev-only)
  if (devFeatures.devMapSAlignmentDebug) {
    assertStrictlyMonotonic(sDistRaw);
    assertStrictlyMonotonic(rDistRaw);
  }
  const sMaxDist  = Math.ceil(Math.max(...sDistRaw));
  const rMaxDist  = Math.ceil(Math.max(...rDistRaw));
  const sMinDist  = Math.min(...sDistRaw);
  const rMinDist  = Math.min(...rDistRaw);
  const maxDist   = Math.max(sMaxDist, rMaxDist);

  // Overlap window: indices outside this range carry only the resampler's
  // boundary clamping, not real data, and must not be rendered or read from.
  currentOverlapRange = {
    start: Math.max(sMinDist, rMinDist),
    end:   Math.min(sMaxDist, rMaxDist),
  };

  currentMaxDist = maxDist;
  currentSessionBins = {};
  currentRefBins = {};
  // Restore persisted zoom (M6) on first render; preserve across re-renders.
  if (!currentZoomRange) {
    currentZoomRange = loadPersistedZoom(maxDist) || { start: 0, end: maxDist };
  } else {
    currentZoomRange.end = Math.min(currentZoomRange.end, maxDist);
  }

  // Resample all channels. When source data is empty (e.g. deltabest CSV's
  // unused channels), produce a zero-filled bin array; renderPanel then
  // suppresses the polyline so it doesn't draw a misleading flat line at 0.
  for (const def of PANEL_DEFS) {
    if (!def.channels) continue;
    for (const ch of def.channels) {
      const entry = ch.trace === 'session' ? sessionEntry : refEntry;
      const keep  = ch.trace === 'session' ? sKeep : rKeep;
      const raw   = entry.data[ch.col];
      if (!raw || raw.length === 0) {
        const bins = new Float64Array(maxDist + 1);
        if (ch.trace === 'session') currentSessionBins[ch.col] = bins;
        else                        currentRefBins[ch.col]     = bins;
        continue;
      }
      const distSlice = ch.trace === 'session' ? sDistRaw : rDistRaw;
      const valSlice  = ch.col === 'gear'
        ? smoothGear(raw, keep)
        : keep.map(i => raw[i]);
      const bins      = resample(distSlice, valSlice, maxDist);
      // Snap gear back to integer steps — linear interp between adjacent
      // gear samples produces fractional values across one-bin-wide
      // shift transitions, which the step renderer then expands into a
      // stack of micro-steps. Rounding gives a single clean step.
      if (ch.col === 'gear') {
        for (let k = 0; k < bins.length; k++) bins[k] = Math.round(bins[k]);
      }
      if (ch.trace === 'session') currentSessionBins[ch.col] = bins;
      else                        currentRefBins[ch.col]     = bins;
    }
  }

  // Resample session-side activity-strip channels (M6 F2: abs_active / tc_active).
  // Booleans interpolate to 0..1; the strip renderer rounds at >= 0.5 for transitions.
  for (const def of PANEL_DEFS) {
    if (!def.activityStrip) continue;
    const col = def.activityStrip.col;
    if (currentSessionBins[col]) continue;  // already resampled (shouldn't happen)
    const raw = sessionEntry.data[col];
    if (!raw || raw.length === 0) continue;
    const valSlice = sKeep.map(i => raw[i]);
    currentSessionBins[col] = resample(sDistRaw, valSlice, maxDist);
  }

  // Resample track coordinates (F1)
  if (sessionEntry.data.pos_x_m && sessionEntry.data.pos_z_m) {
    const sTrackX = resample(sDistRaw, sKeep.map(i => sessionEntry.data.pos_x_m[i]), maxDist);
    const sTrackZ = resample(sDistRaw, sKeep.map(i => sessionEntry.data.pos_z_m[i]), maxDist);
    currentTrackX = sTrackX;
    currentTrackZ = sTrackZ;
  }

  // Resample reference lap track coordinates (Phase 00.5 walking skeleton)
  if (refEntry.data.pos_x_m && refEntry.data.pos_z_m) {
    const rTrackX = resample(rDistRaw, rKeep.map(i => refEntry.data.pos_x_m[i]), maxDist);
    const rTrackZ = resample(rDistRaw, rKeep.map(i => refEntry.data.pos_z_m[i]), maxDist);
    currentRefTrackX = rTrackX;
    currentRefTrackZ = rTrackZ;
  } else {
    currentRefTrackX = null;
    currentRefTrackZ = null;
    currentLapBRaw = null;
  }

  // Phase 01b: stash raw arrays for sLookup alignment debug
  currentLapARaw = {
    s: new Float64Array(sDistRaw),
    x: new Float64Array(sKeep.map(i => sessionEntry.data.pos_x_m?.[i] ?? NaN)),
    z: new Float64Array(sKeep.map(i => sessionEntry.data.pos_z_m?.[i] ?? NaN)),
    throttle: new Float64Array(sKeep.map(i => sessionEntry.data.throttle_norm?.[i] ?? 0)),
    brake: new Float64Array(sKeep.map(i => sessionEntry.data.brake_norm?.[i] ?? 0)),
  };
  if (currentRefTrackX) {
    currentLapBRaw = {
      s: new Float64Array(rDistRaw),
      x: new Float64Array(rKeep.map(i => refEntry.data.pos_x_m?.[i] ?? NaN)),
      z: new Float64Array(rKeep.map(i => refEntry.data.pos_z_m?.[i] ?? NaN)),
    };
  }

  // Resample lap_time_s (drives the Δt computation; not a rendered panel).
  // Smoothed across scoring-rate plateaus first — see smoothLapTime.
  // Stored on currentSessionBins/currentRefBins so __dtDebug and downstream
  // consumers can read the same arrays renderAll built.
  const sLapTime = sessionEntry.data.lap_time_s;
  const rLapTime = refEntry.data.lap_time_s;
  const sLapTimeBins = (sLapTime && sLapTime.length)
    ? resample(sDistRaw, smoothLapTime(sLapTime, sKeep), maxDist)
    : new Float64Array(maxDist + 1);
  const rLapTimeBins = (rLapTime && rLapTime.length)
    ? resample(rDistRaw, smoothLapTime(rLapTime, rKeep), maxDist)
    : new Float64Array(maxDist + 1);
  // Forward-clamp so lap_time_s is non-decreasing in distance. This is a
  // physical invariant (the sim's lap stopwatch only moves forward), so
  // any drop is a corruption — e.g. a boundary-artifact frame that slipped
  // through computeKeepIndices and got interpolated against a real frame.
  // Defence-in-depth against the end-of-lap Δt blow-up.
  for (let d = 1; d < sLapTimeBins.length; d++) {
    if (sLapTimeBins[d] < sLapTimeBins[d - 1]) sLapTimeBins[d] = sLapTimeBins[d - 1];
  }
  for (let d = 1; d < rLapTimeBins.length; d++) {
    if (rLapTimeBins[d] < rLapTimeBins[d - 1]) rLapTimeBins[d] = rLapTimeBins[d - 1];
  }
  currentSessionBins['lap_time_s'] = sLapTimeBins;
  currentRefBins['lap_time_s']     = rLapTimeBins;

  // Δt — direct lap_time_s difference (see computeDeltaT), then spatially
  // smoothed (see smoothDt) to suppress plateau-alignment jitter.
  currentDtBins = smoothDt(computeDeltaT(sLapTimeBins, rLapTimeBins));

  // Coarse-data warning (Fix 4)
  const medianDelta = computeMedianFrameDistanceDelta(Array.from(sDistRaw));
  const coarseDataWarning = medianDelta > 2;

  // Sector markers from session lap
  const sectorDists = deriveSectorDistances(sessionEntry, sessionSegIdx);

  // Build all panel HTML
  const panelsDiv = document.getElementById('panels');
  panelsDiv.innerHTML = '';

  const hasSlip = sessionEntry.hasSlip || refEntry.hasSlip;
  const hasAbs  = currentSessionBins['abs_active']?.some(v => v >= 0.5) ?? false;
  const hasTc   = currentSessionBins['tc_active']?.some(v => v >= 0.5) ?? false;

  // Determine last visible non-dt panel in the current render order (for showXLabels)
  const visibleIds = panelOrder.filter(id => {
    if (id === 'slip' && !hasSlip) return false;
    if (id === 'abs'  && !hasAbs)  return false;
    if (id === 'tc'   && !hasTc)   return false;
    return true;
  });
  const lastNonDtId = [...visibleIds].reverse().find(id => id !== 'dt');

  for (const panelId of panelOrder) {
    const def = PANEL_DEFS.find(d => d.id === panelId);
    if (!def) continue;

    const wrap = document.createElement('div');
    wrap.className = 'panel-wrap';
    wrap.dataset.panelId = def.id;

    const labelEl = document.createElement('div');
    labelEl.className = 'panel-label';
    let labelText = def.label;
    if (def.id === 'dt' && coarseDataWarning) {
      labelText += ' ⚠ legacy distance resolution';
    }
    labelEl.innerHTML = `<span class="drag-handle">⠿</span>${labelText}`;
    wrap.appendChild(labelEl);

    // Fully absent panels — don't add DOM nodes so legacy tests counting 8 panels still pass
    if (def.id === 'abs' && !hasAbs) continue;
    if (def.id === 'tc'  && !hasTc)  continue;

    // Slip placeholder — kept in DOM (existing behaviour)
    if (def.id === 'slip' && !hasSlip) {
      const note = document.createElement('div');
      note.style.cssText = `height:32px;line-height:32px;color:var(--muted);font-size:11px;padding-left:${PAD.left}px`;
      note.textContent = 'no slip angle data — requires a new recording';
      wrap.appendChild(note);
      panelsDiv.appendChild(wrap);
      continue;
    }

    // Measure container width for responsive rendering
    const containerWidth = panelsDiv.clientWidth || SVG_W;

    let svgHtml;
    if (def.id === 'dt') {
      def.showXLabels = true;
      svgHtml = renderDtPanel(def, currentDtBins, maxDist, sectorDists, currentZoomRange, currentOverlapRange, containerWidth);
    } else {
      def.showXLabels = (def.id === lastNonDtId);
      const binsMap = {};
      for (const ch of def.channels) {
        const srcBins = ch.trace === 'session' ? currentSessionBins : currentRefBins;
        binsMap[`${ch.trace}_${ch.col}`] = srcBins[ch.col];
      }
      if (def.activityStrip && currentSessionBins[def.activityStrip.col]) {
        binsMap[`session_${def.activityStrip.col}`] = currentSessionBins[def.activityStrip.col];
      }
      svgHtml = renderPanel(def, binsMap, maxDist, sectorDists, currentZoomRange, containerWidth);
    }

    wrap.insertAdjacentHTML('beforeend', svgHtml);
    panelsDiv.appendChild(wrap);
  }

  document.getElementById('placeholder').style.display = 'none';

  // Update legend
  const sl = formatPickLabel(sessionEntry, sessionSegIdx);
  const rl = formatPickLabel(refEntry, refSegIdx);
  document.getElementById('legend-session').textContent = sl;
  document.getElementById('legend-ref').textContent     = rl;
  document.getElementById('legend').classList.add('visible');

  // Render circuit map (F1)
  trackTransform = renderCircuitMap(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist, currentSessionBins);

  // Render track heatmap (Phase 00.5 walking skeleton)
  renderTrackHeatmapMap();

  // Reset cursor and zoom state
  state.maxDist = maxDist;
}

// ── Cursor and tooltip ────────────────────────────────────────────────────────
// Extracted to cursor.js — initialized via initCursorAndZoom()

// F2: Zoom interaction handlers — extracted to cursor.js

// Heatmap mode change re-renders the circuit map only (no panel re-render needed).
// Extracted to cursor.js

// ── Track heatmap rendering (Phase 00.5+) ───────────────────────────────────
function renderTrackHeatmapMap() {
  const canvas = document.getElementById('track-heatmap-canvas');
  const svg    = document.getElementById('circuit-map-svg');
  if (!canvas || !svg) return;

  // Feature flag: only show when enabled
  const anyMapFeature = features.mapWalkingSkeleton || features.mapTrackOutline || features.mapHeatmapSingleLap || features.mapSAlignment || features.mapDualRibbon || features.mapZoomPan || features.mapLegend;
  if (!anyMapFeature) {
    canvas.style.display = 'none';
    svg.style.display    = '';
    return;
  }

  // Hide old SVG, show canvas
  canvas.style.display = '';
  svg.style.display    = 'none';

  // Phase 02: init interaction once, even before data loads
  if (features.mapZoomPan && !mapInteraction) {
    let indicator = document.getElementById('map-zoom-indicator');
    if (!indicator) {
      indicator = document.createElement('span');
      indicator.id = 'map-zoom-indicator';
      indicator.className = 'map-zoom-indicator';
      indicator.textContent = '1.0×';
      const panel = document.getElementById('circuit-map-panel');
      if (panel) panel.appendChild(indicator);
    }
    mapInteraction = createMapInteraction(canvas, () => renderTrackHeatmapMap());
  }

  // Need both laps' track data
  if (!currentTrackX || !currentTrackZ || !currentRefTrackX || !currentRefTrackZ) return;

  const sessionColor = getComputedStyle(document.documentElement).getPropertyValue('--session').trim() || '#4fc3f7';
  const refColor     = getComputedStyle(document.documentElement).getPropertyValue('--ref').trim() || '#ff9800';

  const lapA = {
    x: currentTrackX,
    z: currentTrackZ,
    throttle: currentSessionBins?.throttle_norm,
    brake: currentSessionBins?.brake_norm,
    color: sessionColor,
    raw: currentLapARaw,
  };
  const lapB = {
    x: currentRefTrackX,
    z: currentRefTrackZ,
    throttle: currentRefBins?.throttle_norm,
    brake: currentRefBins?.brake_norm,
    color: refColor,
    raw: currentLapBRaw,
  };

  // Phase 02: read current zoom/pan state
  let userScale = 1;
  let userPanX = 0;
  let userPanY = 0;
  if (features.mapZoomPan && mapInteraction) {
    const s = mapInteraction.getState();
    userScale = s.scale;
    userPanX = s.tx;
    userPanY = s.ty;
  }

  const showDualRibbon = !!features.mapDualRibbon;
  const showOutline = !!features.mapTrackOutline;
  const showHeatmapSingleLap = !!features.mapHeatmapSingleLap;
  const showSAlignmentDebug = !!features.mapSAlignment || !!devFeatures.devMapSAlignmentDebug;
  const showLegend = !!features.mapLegend;
  const opts = {
    showOutline, showHeatmapSingleLap, showSAlignmentDebug, showDualRibbon, showLegend,
    ribbonWidthPx: 8, ribbonGapPx: 2,
    userScale, userPanX, userPanY,
  };
  renderWalkingSkeleton(canvas, lapA, lapB, opts);

  // Phase 02: notify interaction layer of base transform for cursor-centered zoom
  if (features.mapZoomPan) {
    const boundsA = computeTrackBounds(Array.from(lapA.x), Array.from(lapA.z));
    const boundsB = computeTrackBounds(Array.from(lapB.x), Array.from(lapB.z));
    const rect = canvas.getBoundingClientRect();
    const tf = fitToView(boundsA, boundsB, rect.width, rect.height, 15);
    setBaseTransform(tf);
  }

  // Set up ResizeObserver on first render
  if (!trackHeatmapObserver) {
    trackHeatmapObserver = initTrackHeatmapResize(canvas, () => {
      if (!currentTrackX || !currentRefTrackX) return null;
      const sColor = getComputedStyle(document.documentElement).getPropertyValue('--session').trim() || '#4fc3f7';
      const rColor = getComputedStyle(document.documentElement).getPropertyValue('--ref').trim() || '#ff9800';
      return {
        lapA: {
          x: currentTrackX,
          z: currentTrackZ,
          throttle: currentSessionBins?.throttle_norm,
          brake: currentSessionBins?.brake_norm,
          color: sColor,
          raw: currentLapARaw,
        },
        lapB: {
          x: currentRefTrackX,
          z: currentRefTrackZ,
          throttle: currentRefBins?.throttle_norm,
          brake: currentRefBins?.brake_norm,
          color: rColor,
          raw: currentLapBRaw,
        },
      };
    }, () => {
      const s = mapInteraction ? mapInteraction.getState() : { scale: 1, tx: 0, ty: 0 };
      return {
        showOutline: !!features.mapTrackOutline,
        showHeatmapSingleLap: !!features.mapHeatmapSingleLap,
        showSAlignmentDebug: !!devFeatures.devMapSAlignmentDebug,
        showDualRibbon: !!features.mapDualRibbon,
        showLegend: !!features.mapLegend,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
        userScale: s.scale,
        userPanX: s.tx,
        userPanY: s.ty,
      };
    });
  }
}

// ── App initialization ────────────────────────────────────────────────────────

// Helper to expose current render state to cursor.js
function getRenderState() {
  return {
    currentSessionBins,
    currentRefBins,
    currentZoomRange,
    currentOverlapRange,
    currentTrackX,
    currentTrackZ,
    currentRefTrackX,
    currentRefTrackZ,
    trackTransform,
    currentDtBins,
    maxDist: state.maxDist,
    currentMaxDist,
  };
}

// Initialize UI event handlers
initUI(renderAll);

// Initialize cursor, tooltip, and zoom handlers
initCursorAndZoom(renderAll, getRenderState);

installDebugHooks({
  store,
  features,
  devFeatures,
  resample,
  smoothLapTime,
  smoothDt,
  computeDeltaT,
  computeKeepIndices,
  fitToView,
  setFeatureFlag,
  setDevFeatureFlag,
  renderTrackHeatmapMap,
});
