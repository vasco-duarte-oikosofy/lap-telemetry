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
         persistPanelOrder, state, getCurrentMapMode, setCurrentMapMode } from './appState.js';

// ── Circuit map rendering ───────────────────────────────────────────────────────
import { renderCircuitMap, renderHeatmapSegments, renderMapLegend, updateZoomArc,
         HEATMAP_RAMPS, HEATMAP_CHANNELS } from './circuitMap.js';

// ── Panel rendering ─────────────────────────────────────────────────────────────
import { renderPanel, renderDtPanel } from './panels.js';

// ── Cursor, tooltip, zoom ───────────────────────────────────────────────────────
import { initCursorAndZoom } from './cursor.js';

// ── Shared constants ────────────────────────────────────────────────────────────
import { SVG_W, PAD, PLOT_W } from './constants.js';

// ── UI interaction ─────────────────────────────────────────────────────────────
import { initUI, rebuildPickers, parsePickerValue, addSessionEntry, refreshSessionListBadges } from './ui.js';

// ── CDN imports ────────────────────────────────────────────────────────────
import { parquetRead, parquetMetadataAsync } from 'https://cdn.jsdelivr.net/npm/hyparquet@1/+esm';
import { compressors } from 'https://cdn.jsdelivr.net/npm/hyparquet-compressors@1/+esm';

// ── Constants ────────────────────────────────────────────────────────────────
const COLUMNS = [
  'lap_number', 'lap_time_s', 'lap_distance_m', 'speed_kph',
  'throttle_norm', 'brake_norm', 'engine_rpm', 'gear',
  'steering_norm', 'slip_angle_fl_deg', 'slip_angle_fr_deg',
  'last_sector_1_s', 'last_sector_2_s',
  'pos_x_m', 'pos_z_m',
  'abs_active', 'tc_active',
];

// Panel definitions: { id, label, height, channels, yFixed, yStep, zeroline }
const PANEL_DEFS = [
  { id: 'speed',    label: 'Speed (km/h)',         height: 140,
    channels: [
      { col: 'speed_kph', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'speed_kph', trace: 'ref',     color: 'var(--ref)',     dash: true  },
    ],
    yFixed: null, yStep: 50, zeroline: false },

  { id: 'throttle', label: 'Throttle',               height: 60,
    channels: [
      { col: 'throttle_norm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'throttle_norm', trace: 'ref',     color: 'var(--ref)',     dash: true  },
    ],
    yFixed: [0, 1], yStep: 0.5, zeroline: false,
    activityStrip: { col: 'tc_active',  color: 'var(--throttle)' } },

  { id: 'tc',  label: 'TC active',                   height: 50,
    channels: [
      { col: 'tc_active', trace: 'session', color: 'var(--throttle)', dash: false, step: true },
    ],
    yFixed: [0, 1], yStep: 1, midline: 0.5, zeroline: false },

  { id: 'brake', label: 'Brake',                     height: 60,
    channels: [
      { col: 'brake_norm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'brake_norm', trace: 'ref',     color: 'var(--ref)',     dash: true  },
    ],
    yFixed: [0, 1], yStep: 0.5, zeroline: false,
    activityStrip: { col: 'abs_active', color: 'var(--brake)' } },

  { id: 'abs', label: 'ABS active',                  height: 50,
    channels: [
      { col: 'abs_active', trace: 'session', color: 'var(--brake)', dash: false, step: true },
    ],
    yFixed: [0, 1], yStep: 1, midline: 0.5, zeroline: false },

  { id: 'rpm', label: 'RPM',                         height: 80,
    channels: [
      { col: 'engine_rpm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'engine_rpm', trace: 'ref',     color: 'var(--ref)',     dash: true  },
    ],
    yFixed: null, yStep: 2000, zeroline: false },

  { id: 'gear', label: 'Gear',                        height: 60, heightMultiplier: 1.3,
    channels: [
      { col: 'gear', trace: 'session', color: 'var(--session)', dash: false, step: true },
      { col: 'gear', trace: 'ref',     color: 'var(--ref)',     dash: true,  step: true },
    ],
    yFixed: null, yStep: 1, zeroline: false },

  { id: 'steering', label: 'Steering',               height: 80,
    channels: [
      { col: 'steering_norm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'steering_norm', trace: 'ref',     color: 'var(--ref)',     dash: true  },
    ],
    yFixed: [-1, 1], yStep: 0.5, zeroline: true },

  { id: 'slip', label: 'Slip angle FL / FR (deg)',   height: 80,
    channels: [
      { col: 'slip_angle_fl_deg', trace: 'session', color: 'var(--slip-fl)', dash: false },
      { col: 'slip_angle_fl_deg', trace: 'ref',     color: 'var(--slip-fl)', dash: true  },
      { col: 'slip_angle_fr_deg', trace: 'session', color: 'var(--slip-fr)', dash: false },
      { col: 'slip_angle_fr_deg', trace: 'ref',     color: 'var(--slip-fr)', dash: true  },
    ],
    yFixed: null, yStep: 2, zeroline: false, niceSteps: [0.5, 1, 2, 5] },

  { id: 'dt', label: 'Δt (ms, +session slower)',    height: 100,
    channels: null,  // special: computed from speed traces
    yFixed: null, yStep: 100, zeroline: true, niceSteps: [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000] },
];

// ── Main render ───────────────────────────────────────────────────────────────

let currentSessionBins = null; // { col: Float64Array }
let currentRefBins     = null;
let currentMaxDist     = 0;
let currentDtBins      = null;
let currentTrackX      = null; // Resampled track coordinates
let currentTrackZ      = null;
let currentZoomRange   = null; // { start, end }
let currentOverlapRange = null; // { start, end } — distance window covered by BOTH laps
let trackTransform     = null; // Updated by renderCircuitMap

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

  // Reset cursor and zoom state
  state.maxDist = maxDist;
}

// ── Cursor and tooltip ────────────────────────────────────────────────────────
// Extracted to cursor.js — initialized via initCursorAndZoom()

// F2: Zoom interaction handlers — extracted to cursor.js

// Heatmap mode change re-renders the circuit map only (no panel re-render needed).
// Extracted to cursor.js

// ── Debug hooks for Playwright ────────────────────────────────────────────────

window.__getSessionKeys = () => [...store.keys()];

window.__resamplerDebug = function(storeKeyStr, segIdx) {
  const entry = store.get(storeKeyStr);
  if (!entry) throw new Error(`store key not found: ${storeKeyStr}`);
  const seg    = entry.segments[segIdx];
  const dists  = Array.from(entry.data.lap_distance_m.slice(seg.start, seg.end));
  const speeds = Array.from(entry.data.speed_kph.slice(seg.start, seg.end));
  const maxD   = Math.ceil(Math.max(...dists));
  return Array.from(resample(dists, speeds, maxD));
};

window.__refResamplerDebug = function(storeKeyStr, segIdx) {
  return window.__resamplerDebug(storeKeyStr, segIdx);
};

window.__dtDebug = function(sessionKey, sessionSeg, refKey, refSeg) {
  const se   = store.get(sessionKey);
  const re   = store.get(refKey);
  if (!se || !re) throw new Error('store keys not found');
  const sSeg = se.segments[sessionSeg];
  const rSeg = re.segments[refSeg];
  const sTrackLen = se.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
  const rTrackLen = re.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
  const sKeep = computeKeepIndices(se.data.lap_time_s, se.data.lap_distance_m, sSeg.start, sSeg.end, sTrackLen);
  const rKeep = computeKeepIndices(re.data.lap_time_s, re.data.lap_distance_m, rSeg.start, rSeg.end, rTrackLen);
  const sDist = sKeep.map(i => se.data.lap_distance_m[i]);
  const rDist = rKeep.map(i => re.data.lap_distance_m[i]);
  const maxD  = Math.max(Math.ceil(Math.max(...sDist)), Math.ceil(Math.max(...rDist)));
  const sBins = resample(sDist, smoothLapTime(se.data.lap_time_s, sKeep), maxD);
  const rBins = resample(rDist, smoothLapTime(re.data.lap_time_s, rKeep), maxD);
  return Array.from(smoothDt(computeDeltaT(sBins, rBins)));
};

// Overlap window for the in-page Δt cross-check (lets tests trim to the
// rendered range rather than the full bin grid).
window.__dtDebugOverlap = function(sessionKey, sessionSeg, refKey, refSeg) {
  const se   = store.get(sessionKey);
  const re   = store.get(refKey);
  if (!se || !re) throw new Error('store keys not found');
  const sSeg = se.segments[sessionSeg];
  const rSeg = re.segments[refSeg];
  const sTrackLen = se.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
  const rTrackLen = re.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
  const sKeep = computeKeepIndices(se.data.lap_time_s, se.data.lap_distance_m, sSeg.start, sSeg.end, sTrackLen);
  const rKeep = computeKeepIndices(re.data.lap_time_s, re.data.lap_distance_m, rSeg.start, rSeg.end, rTrackLen);
  const sDist = sKeep.map(i => se.data.lap_distance_m[i]);
  const rDist = rKeep.map(i => re.data.lap_distance_m[i]);
  return {
    start: Math.max(Math.min(...sDist), Math.min(...rDist)),
    end:   Math.min(Math.ceil(Math.max(...sDist)), Math.ceil(Math.max(...rDist))),
  };
};

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
