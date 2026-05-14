// ── Track Heatmap Map — Walking Skeleton (Phase 00.5) ─────────────────────────
// Draws both laps as 1px polylines on a Canvas 2D, fitted to view.
// No heatmap, no ribbons, no interaction — just proof that we can render two
// laps side by side on one map.
//
// Feature flag: features.mapWalkingSkeleton (default: off)

import { computeTrackBounds } from './pipeline.js';

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


// ── Drawing helpers ───────────────────────────────────────────────────────────

function drawPolyline(ctx, trackX, trackZ, transform, color, lineWidth = 1) {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < trackX.length; i++) {
    const x = trackX[i];
    const z = trackZ[i];
    if (!isFinite(x) || !isFinite(z)) continue;
    const sx = transform.toScreenX(x);
    const sy = transform.toScreenY(z);
    if (!started) {
      ctx.moveTo(sx, sy);
      started = true;
    } else {
      ctx.lineTo(sx, sy);
    }
  }
  ctx.stroke();
}

function drawStartFinishTick(ctx, startX, startZ, transform) {
  // Find the tangent direction at the start to draw a perpendicular tick
  // For the walking skeleton, we just draw a short white tick at s=0
  const sx = transform.toScreenX(startX);
  const sy = transform.toScreenY(startZ);

  // Draw a 10px crosshair at the start point
  const len = 6;
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(sx - len, sy);
  ctx.lineTo(sx + len, sy);
  ctx.moveTo(sx, sy - len);
  ctx.lineTo(sx, sy + len);
  ctx.stroke();
}

// ── Main render function ──────────────────────────────────────────────────────
// Renders both laps as polylines on the given canvas.

export function renderWalkingSkeleton(canvas, lapA, lapB) {
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  // Size the backing store to match the display size
  canvas.width  = rect.width  * dpr;
  canvas.height = rect.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  // Clear
  ctx.clearRect(0, 0, rect.width, rect.height);

  if (!lapA || !lapA.x || !lapA.z || !lapB || !lapB.x || !lapB.z) return;

  // Compute bounding boxes
  const boundsA = computeTrackBounds(Array.from(lapA.x), Array.from(lapA.z));
  const boundsB = computeTrackBounds(Array.from(lapB.x), Array.from(lapB.z));

  const padding = 15;
  const transform = fitToView(boundsA, boundsB, rect.width, rect.height, padding);

  // Draw background
  ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
  ctx.fillRect(0, 0, rect.width, rect.height);

  // Draw Lap B first (reference — underneath)
  drawPolyline(ctx, lapB.x, lapB.z, transform, lapB.color);

  // Draw Lap A on top (session — over reference)
  drawPolyline(ctx, lapA.x, lapA.z, transform, lapA.color);

  // Start/finish marker on Lap A
  // Find the first valid point
  if (lapA.x.length > 0 && lapA.z.length > 0) {
    drawStartFinishTick(ctx, lapA.x[0], lapA.z[0], transform);
  }
}

// ── ResizeObserver setup ──────────────────────────────────────────────────────
// Sets up a ResizeObserver on the canvas container that re-renders on resize.

export function initTrackHeatmapResize(canvas, getLaps) {
  const observer = new ResizeObserver(() => {
    const laps = getLaps();
    if (laps) renderWalkingSkeleton(canvas, laps.lapA, laps.lapB);
  });
  observer.observe(canvas.parentElement || canvas);
  return observer;
}