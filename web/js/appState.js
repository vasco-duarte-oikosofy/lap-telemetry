/**
 * Application state module — owns all mutable runtime state.
 * Other modules import this and read/mutate state directly.
 * No DOM access, no side effects — pure state container.
 */

// ── Session store ─────────────────────────────────────────────────────────────
// Map from storeKey → { fileName, data: {col: Array}, segments, hasSlip, hasSectors }
export const store = new Map();

// Pending sidecar JSONs keyed by stem (filename without extension).
// When the parquet for the same stem arrives, we attach the metadata.
export const pendingSidecars = new Map();

// Validated apex annotation JSONs keyed by track/layout.
export const apexAnnotationsByLayout = new Map();

// ── Panel order (F9) ──────────────────────────────────────────────────────────
export const PANEL_ORDER_LS_KEY = 'lap-telemetry.panel-order.v1';
export const DEFAULT_PANEL_ORDER = [
  'speed', 'throttle', 'tc', 'brake', 'abs', 'rpm', 'gear', 'steering', 'slip', 'dt'
];
export let panelOrder = loadPersistedPanelOrder() || [...DEFAULT_PANEL_ORDER];

function loadPersistedPanelOrder() {
  try {
    const raw = localStorage.getItem(PANEL_ORDER_LS_KEY);
    if (!raw) return null;
    const order = JSON.parse(raw);
    if (!Array.isArray(order)) return null;
    if (order.length !== DEFAULT_PANEL_ORDER.length) return null;
    const known = new Set(DEFAULT_PANEL_ORDER);
    if (!order.every(id => known.has(id))) return null;
    if (new Set(order).size !== order.length) return null;
    return order;
  } catch { return null; }
}

export function persistPanelOrder(order) {
  try {
    if (JSON.stringify(order) === JSON.stringify(DEFAULT_PANEL_ORDER)) {
      localStorage.removeItem(PANEL_ORDER_LS_KEY);
    } else {
      localStorage.setItem(PANEL_ORDER_LS_KEY, JSON.stringify(order));
    }
  } catch {}
}

// ── Interaction state (drag, cursor, render params) ───────────────────────────
export const state = {
  maxDist: 0,
  dragging: false,
  dragStartX: 0,
  dragStartDist: 0,
  dragId: null,
  currentRenderParams: null, // [sEntry, sSegIdx, rEntry, rSegIdx] for re-render after zoom
};

// ── Circuit map state ─────────────────────────────────────────────────────────
let _currentMapMode = 'outline';
export function getCurrentMapMode() { return _currentMapMode; }
export function setCurrentMapMode(mode) { _currentMapMode = mode; }

// ── Feature flags ───────────────────────────────────────────────────────────────
// Each subphase has its own flag. Default off until acceptance is signed off.
export const features = {
  mapWalkingSkeleton: true,      // Phase 00.5 - ON for development
  mapTrackOutline: true,         // Phase 00.6 - ON for testing
  mapHeatmapSingleLap: false,    // Phase 01a - default OFF until accepted
  mapSAlignment: false,          // Phase 01b - s-based cross-lap alignment
  mapDualRibbon: false,          // Phase 01c - side-by-side dual heatmap ribbons
  mapZoomPan: false,             // Phase 02 - zoom and pan interaction
  mapLegend: false,              // Phase 03 - lap legend and identification
  mapHover: false,                // Phase 04 - hover crosshair and per-lap readout
  mapLinkedHighlight: false,       // Phase 05a - linked highlight band from trace charts
  apexAnnotations: false,          // Track outline Phase 03 - apex annotation loading
  apexMetrics: false,              // Track outline Phase 04 - in-memory apex metrics
  apexMetricsUi: false,            // Track outline Phase 05 - text-only apex metrics UI
};

// Dev-only flags (not exposed in production UI)
export const devFeatures = {
  devMapSAlignmentDebug: false,  // Phase 01b - debug tick overlay
};

export function setFeatureFlag(name, value) {
  if (name in features) {
    features[name] = value;
  }
}

export function setDevFeatureFlag(name, value) {
  if (name in devFeatures) {
    devFeatures[name] = value;
  }
}
