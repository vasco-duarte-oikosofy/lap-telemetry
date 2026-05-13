// ── Circuit map rendering module ──────────────────────────────────────────────
// Extracted from main.js (Step 7). Pure SVG generation + DOM access for circuit
// map outline, heatmap modes, legend, and zoom arc indicator.

import { getCurrentMapMode } from './appState.js';
import { computeTrackBounds, buildTrackTransform, buildTrackPolylinePts } from './pipeline.js';
import { SVG_W, PAD } from './constants.js';

// SVG layout constants
const MAP_SIZE = 250;
const MAP_PAD  = 20;

// Heatmap colour ramps: each takes a normalised v in [0,1] and returns a CSS colour.
export const HEATMAP_RAMPS = {
  // speed: cool (slow) → warm (fast). HSL hue 220 (blue) → 0 (red), high saturation.
  speed:    v => `hsl(${(220 - 220 * v).toFixed(0)}, 85%, 55%)`,
  // brake: faint grey (no brake) → bright red (full brake).
  brake:    v => `rgba(244, 67, 54, ${(0.15 + 0.85 * v).toFixed(2)})`,
  // throttle: faint grey (off) → bright green (full).
  throttle: v => `rgba(76, 175, 80, ${(0.15 + 0.85 * v).toFixed(2)})`,
};
export const HEATMAP_CHANNELS = { speed: 'speed_kph', brake: 'brake_norm', throttle: 'throttle_norm' };

/**
 * Render the circuit map (outline or heatmap mode).
 * @param {Float64Array} currentTrackX - Resampled X coordinates
 * @param {Float64Array} currentTrackZ - Resampled Z coordinates
 * @param {Object} trackTransform - Transform object from buildTrackTransform (mutable state)
 * @param {Object} currentZoomRange - { start, end } for zoom arc
 * @param {number} currentMaxDist - Maximum distance for the lap
 * @param {Object} currentSessionBins - Binned session data for heatmap
 * @returns {Object|null} - Updated trackTransform or null if no data
 */
export function renderCircuitMap(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist, currentSessionBins) {
  if (!currentTrackX || !currentTrackZ) return null;

  const trackOutline = document.getElementById('track-outline');
  const segGroup = document.getElementById('track-segments');
  const mapPanel = document.getElementById('circuit-map-panel');
  if (!trackOutline) return null;

  const bounds = computeTrackBounds(Array.from(currentTrackX), Array.from(currentTrackZ));
  trackTransform = buildTrackTransform(bounds);
  const pts = buildTrackPolylinePts(Array.from(currentTrackX), Array.from(currentTrackZ), trackTransform.toMapX, trackTransform.toMapZ);

  if (getCurrentMapMode() === 'outline') {
    trackOutline.setAttribute('points', pts);
    trackOutline.style.display = '';
    segGroup.innerHTML = '';
  } else {
    // Heatmap: draw per-bin coloured segments instead of the single polyline.
    trackOutline.style.display = 'none';
    segGroup.innerHTML = renderHeatmapSegments(getCurrentMapMode(), currentTrackX, currentTrackZ, trackTransform, currentSessionBins);
  }

  renderMapLegend(getCurrentMapMode(), currentTrackX, currentSessionBins);
  mapPanel.style.display = 'block';
  updateZoomArc(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist);
  return trackTransform;
}

/**
 * Render heatmap segments for the circuit map.
 * @param {string} mode - Heatmap mode ('speed', 'brake', 'throttle')
 * @param {Float64Array} currentTrackX - Resampled X coordinates
 * @param {Float64Array} currentTrackZ - Resampled Z coordinates
 * @param {Object} trackTransform - Transform from buildTrackTransform
 * @param {Object} currentSessionBins - Binned session data
 * @returns {string} - SVG content for heatmap segments
 */
export function renderHeatmapSegments(mode, currentTrackX, currentTrackZ, trackTransform, currentSessionBins) {
  const col = HEATMAP_CHANNELS[mode];
  const bins = currentSessionBins?.[col];
  if (!bins) return '';
  // Range for normalisation: brake/throttle are [0,1]; speed uses session min/max.
  let lo = 0, hi = 1;
  if (mode === 'speed') {
    lo = Infinity; hi = -Infinity;
    for (const v of bins) { if (isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } }
    if (!isFinite(lo) || hi <= lo) { lo = 0; hi = 1; }
  }
  const ramp = HEATMAP_RAMPS[mode];
  const out = [];
  // 2 m chunks keep the SVG count low (~2.3 k segments for a 4.6 km lap) while still smooth.
  const STEP = 2;
  for (let i = 0; i + STEP < currentTrackX.length; i += STEP) {
    const x1 = currentTrackX[i], z1 = currentTrackZ[i];
    const x2 = currentTrackX[i + STEP], z2 = currentTrackZ[i + STEP];
    if (!isFinite(x1) || !isFinite(z1) || !isFinite(x2) || !isFinite(z2)) continue;
    const v = bins[i + Math.floor(STEP / 2)];
    if (!isFinite(v)) continue;
    const norm = Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1)));
    const colour = ramp(norm);
    const X1 = trackTransform.toMapX(x1).toFixed(1);
    const Y1 = trackTransform.toMapZ(z1).toFixed(1);
    const X2 = trackTransform.toMapX(x2).toFixed(1);
    const Y2 = trackTransform.toMapZ(z2).toFixed(1);
    out.push(`<line x1="${X1}" y1="${Y1}" x2="${X2}" y2="${Y2}" stroke="${colour}" stroke-width="2.5" stroke-linecap="round"/>`);
  }
  return out.join('');
}

/**
 * Render the map legend for heatmap modes.
 * @param {string} mode - Current map mode
 * @param {Float64Array} currentTrackX - Track X coordinates (for speed range)
 * @param {Object} currentSessionBins - Binned session data
 */
export function renderMapLegend(mode, currentTrackX, currentSessionBins) {
  const el = document.getElementById('map-legend');
  if (!el) return;
  if (mode === 'outline') { el.innerHTML = ''; return; }
  const col = HEATMAP_CHANNELS[mode];
  const bins = currentSessionBins?.[col];
  let lo = 0, hi = 1, unit = '';
  if (mode === 'speed' && bins) {
    lo = Infinity; hi = -Infinity;
    for (const v of bins) { if (isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } }
    if (!isFinite(lo) || hi <= lo) { lo = 0; hi = 1; }
    unit = ' km/h';
  } else if (mode === 'brake' || mode === 'throttle') {
    lo = 0; hi = 1; unit = '';
  }
  const ramp = HEATMAP_RAMPS[mode];
  const stops = [];
  for (let i = 0; i <= 10; i++) stops.push(`${ramp(i / 10)} ${i * 10}%`);
  const fmt = mode === 'speed' ? v => v.toFixed(0) : v => v.toFixed(1);
  el.innerHTML = `<span>${fmt(lo)}${unit}</span><div class="map-legend-bar" style="background:linear-gradient(to right, ${stops.join(',')})"></div><span>${fmt(hi)}${unit}</span>`;
}

/**
 * Update the zoom arc indicator on the circuit map.
 * @param {Float64Array} currentTrackX - Resampled X coordinates
 * @param {Float64Array} currentTrackZ - Resampled Z coordinates
 * @param {Object} trackTransform - Transform from buildTrackTransform
 * @param {Object|null} currentZoomRange - { start, end } or null
 * @param {number} currentMaxDist - Maximum distance for the lap
 */
export function updateZoomArc(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist) {
  const zoomArc = document.getElementById('zoom-arc');
  if (!currentTrackX || !currentTrackZ || !trackTransform || !currentZoomRange) {
    if (zoomArc) zoomArc.style.display = 'none';
    return;
  }

  const isZoomed = currentZoomRange.start > 0 || currentZoomRange.end < currentMaxDist;
  if (!isZoomed) {
    zoomArc.style.display = 'none';
    return;
  }

  const startIdx = Math.max(0, Math.floor(currentZoomRange.start));
  const endIdx = Math.min(currentMaxDist, Math.ceil(currentZoomRange.end));
  const pts = [];

  for (let i = startIdx; i <= endIdx && i < currentTrackX.length; i++) {
    if (isFinite(currentTrackX[i]) && isFinite(currentTrackZ[i])) {
      pts.push(`${trackTransform.toMapX(currentTrackX[i]).toFixed(1)},${trackTransform.toMapZ(currentTrackZ[i]).toFixed(1)}`);
    }
  }

  if (pts.length > 0) {
    zoomArc.setAttribute('points', pts.join(' '));
    zoomArc.style.display = 'block';
  } else {
    zoomArc.style.display = 'none';
  }
}
