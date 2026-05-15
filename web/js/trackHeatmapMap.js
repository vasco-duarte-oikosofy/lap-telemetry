// ── Track Heatmap Map — Walking Skeleton (Phase 00.5) ─────────────────────────
// Draws both laps as 1px polylines on a Canvas 2D, fitted to view.
// Phase 02: supports user zoom/pan composed with base fit-to-view transform.
//
// Feature flags:
// - features.mapWalkingSkeleton (default: on)
// - features.mapHeatmapSingleLap (default: off, Phase 01a)

import { computeTrackBounds } from './pipeline.js';
import { drawRibbon, drawHeatmapRibbon, drawDualRibbons } from './ribbon.js';
import { updateMapLegend } from './mapLegend.js';
import {
  drawPolyline, drawHoverTick, drawLinkedHighlight,
  drawStartFinishTick, drawDebugTicks,
} from './trackHeatmapDrawing.js';

import { getSpaStaticOutline, drawStaticTrackOutline } from './staticTrackOutline.js';

let _lastTransform = null;
export function getLastTransform() { return _lastTransform; }
export function setLastTransform(tf) { _lastTransform = tf; }

// ── fitToView ─────────────────────────────────────────────────────────────────
// Given track bounding boxes for both laps, compute a world→screen transform
// that fits both in the canvas with `padding` px of margin on all sides.
// Preserves aspect ratio (no distortion).

export function fitToView(boundsA, boundsB, canvasWidth, canvasHeight, padding) {
  // Union bounding box
  const minX = Math.min(boundsA.minX, boundsB.minX);
  const maxX = Math.max(boundsA.maxX, boundsB.maxX);
  const minZ = Math.min(boundsA.minZ, boundsB.minZ);
  const maxZ = Math.max(boundsA.maxZ, boundsB.maxZ);

  const worldW = (maxX - minX) || 1;
  const worldH = (maxZ - minZ) || 1;

  const availW = canvasWidth  - 2 * padding;
  const availH = canvasHeight - 2 * padding;

  const scale = Math.min(availW / worldW, availH / worldH);

  // Center the track in the canvas
  const drawnW = worldW * scale;
  const drawnH = worldH * scale;
  const offsetX = padding + (availW - drawnW) / 2;
  // Invert Z: world Z up → screen Y down, so we map maxZ to the top
  const offsetY = padding + (availH - drawnH) / 2;

  return {
    scale,
    offsetX,
    offsetY,
    toScreenX: (x) => offsetX + (x - minX) * scale,
    toScreenY: (z) => offsetY + (maxZ - z) * scale,  // Z-up → Y-down
    bounds: { minX, maxX, minZ, maxZ },
  };
}

// ── applyUserTransform ──────────────────────────────────────────────────────
// Compose a base fit-to-view transform with user zoom/pan.
// Returns a new transform object whose toScreenX/Y include the user scale and pan.

export function applyUserTransform(base, userScale, userPanX, userPanY) {
  const mScale = userScale ?? 1;
  const tx = userPanX ?? 0;
  const ty = userPanY ?? 0;
  return {
    scale: base.scale * mScale,
    offsetX: base.offsetX,
    offsetY: base.offsetY,
    toScreenX: (x) => base.offsetX + (x - base.bounds.minX) * base.scale * mScale + tx,
    toScreenY: (z) => base.offsetY + (base.bounds.maxZ - z) * base.scale * mScale + ty,
    bounds: base.bounds,
    userScale: mScale,
    userPanX: tx,
    userPanY: ty,
  };
}


// ── Main render function ──────────────────────────────────────────────────────
// Renders both laps as polylines on the given canvas.
// Phase 00.6: adds track outline background underneath.

export function renderWalkingSkeleton(canvas, lapA, lapB, options = {}) {
  const { showHeatmapSingleLap = false, showSAlignmentDebug = false, showDualRibbon = false, showLegend = false, ribbonWidthPx = 8, ribbonGapPx = 2, userScale = 1, userPanX = 0, userPanY = 0, showStaticOutline = false, cursorBinIdx = null } = options;
  
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  // Size the backing store to match the display size
  canvas.width  = rect.width  * dpr;
  canvas.height = rect.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  // Clear
  ctx.clearRect(0, 0, rect.width, rect.height);
  resetCanvasCursorDotPatch();

  if (!lapA || !lapA.x || !lapA.z || !lapB || !lapB.x || !lapB.z) return;

  // Compute bounding boxes
  const boundsA = computeTrackBounds(Array.from(lapA.x), Array.from(lapA.z));
  const boundsB = computeTrackBounds(Array.from(lapB.x), Array.from(lapB.z));

  const padding = 15;
  const baseTransform = fitToView(boundsA, boundsB, rect.width, rect.height, padding);
  const transform = applyUserTransform(baseTransform, userScale, userPanX, userPanY);

  // Draw background
  ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
  ctx.fillRect(0, 0, rect.width, rect.height);

  // TUMFTM Phase 02: Draw static Spa outline (bottom layer, under trajectories)
  if (showStaticOutline) {
    drawStaticTrackOutline(ctx, getSpaStaticOutline(), transform);
  }


  // Draw order: background → outline → Lap A ribbon → Lap B ribbon → start/finish marker
  if (showDualRibbon) {
    drawDualRibbons(ctx, lapA, lapB, transform, ribbonWidthPx, ribbonGapPx);
  } else {
    // Draw Lap B first (reference — underneath Lap A)
    drawPolyline(ctx, lapB.x, lapB.z, transform, lapB.color);

    // Draw Lap A on top (session — over reference)
    if (showHeatmapSingleLap) {
      drawHeatmapRibbon(ctx, lapA, transform, ribbonWidthPx);
    } else {
      drawPolyline(ctx, lapA.x, lapA.z, transform, lapA.color);
    }
  }

  // Phase 01b: s-alignment debug overlay (dev-only)
  if (showSAlignmentDebug) {
    drawDebugTicks(ctx, lapA, transform, '#ffffff', 'A ');
    drawDebugTicks(ctx, lapB, transform, '#ff9800', 'B ');
  }

  // Start/finish marker on Lap A
  // Find the first valid point
  if (lapA.x.length > 0 && lapA.z.length > 0) {
    drawStartFinishTick(ctx, lapA.x[0], lapA.z[0], transform);
  }

  // Phase 04: draw hover tick across both ribbons
  if (options.showHover && options.hoverState) {
    drawHoverTick(ctx, options.hoverState, transform, ribbonWidthPx, ribbonGapPx);
  }

  // Phase 05a: draw linked highlight band
  if (options.showLinkedHighlight && options.visibleRange) {
    drawLinkedHighlight(ctx, lapA, transform, options.visibleRange, ribbonWidthPx, ribbonGapPx);
  }

  // Phase 03: update legend overlays
  const panel = canvas.parentElement;
  updateMapLegend(panel, lapA, lapB, showLegend);

  // Store transform for hover hit-testing
  setLastTransform(transform);

  // Cursor dot — drawn after full render so it appears on top
  if (cursorBinIdx != null && isFinite(cursorBinIdx)) {
    drawCanvasCursorDot(canvas, lapA, transform, cursorBinIdx);
  }
}

// ── Canvas cursor dot ─────────────────────────────────────────────────────────
// Draws a small filled circle on the canvas at the position corresponding to
// the given bin index. This is an incremental overlay — it saves and restores
// a small patch of the canvas to avoid ghost dots. The next full render
// (renderWalkingSkeleton) will also paint over it cleanly.

let _savedDotPatch = null; // { canvasWidth, data, x, y, w, h } in device pixels

export function drawCanvasCursorDot(canvas, lapA, transform, binIdx) {
  if (!canvas || !lapA || !transform || binIdx == null || !isFinite(binIdx)) return;
  const x = lapA.x[binIdx];
  const z = lapA.z[binIdx];
  if (!isFinite(x) || !isFinite(z)) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  // Restore the previous dot patch if it exists and the canvas size hasn't changed
  if (_savedDotPatch && _savedDotPatch.canvasWidth === canvas.width) {
    ctx.putImageData(_savedDotPatch.data, _savedDotPatch.x, _savedDotPatch.y);
  }
  _savedDotPatch = null;

  ctx.save();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const sx = transform.toScreenX(x);
  const sy = transform.toScreenY(z);
  if (!isFinite(sx) || !isFinite(sy)) { ctx.restore(); return; }

  // Save a small patch around the dot position (in device pixels)
  const radius = 5; // slightly larger than the dot to cover anti-aliasing
  const dpx = Math.round(sx * dpr);
  const dpy = Math.round(sy * dpr);
  const patchX = Math.max(0, dpx - radius);
  const patchY = Math.max(0, dpy - radius);
  const patchW = Math.min(canvas.width - patchX, radius * 2 + 1);
  const patchH = Math.min(canvas.height - patchY, radius * 2 + 1);
  if (patchW > 0 && patchH > 0) {
    ctx.setTransform(1, 0, 0, 1, 0, 0); // identity for putImageData
    _savedDotPatch = {
      canvasWidth: canvas.width,
      data: ctx.getImageData(patchX, patchY, patchW, patchH),
      x: patchX,
      y: patchY,
      w: patchW,
      h: patchH,
    };
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  ctx.fillStyle = '#58a6ff'; // var(--accent)
  ctx.beginPath();
  ctx.arc(sx, sy, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

/** Clear the saved cursor dot patch (call after a full canvas re-render). */
export function resetCanvasCursorDotPatch() {
  _savedDotPatch = null;
}


// ── ResizeObserver setup ──────────────────────────────────────────────────────
// Sets up a ResizeObserver on the canvas container that re-renders on resize.

export function initTrackHeatmapResize(canvas, getLaps, getOptions) {
  const observer = new ResizeObserver(() => {
    const laps = getLaps();
    if (laps) {
      const options = getOptions ? getOptions() : {};
      renderWalkingSkeleton(canvas, laps.lapA, laps.lapB, options);
    }
  });
  observer.observe(canvas.parentElement || canvas);
  return observer;
}