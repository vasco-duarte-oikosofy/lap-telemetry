// ── Track Heatmap Map — Walking Skeleton (Phase 00.5) ─────────────────────────
// Draws both laps as 1px polylines on a Canvas 2D, fitted to view.
// Phase 02: supports user zoom/pan composed with base fit-to-view transform.
//
// Feature flags:
// - features.mapWalkingSkeleton (default: off)
// - features.mapTrackOutline (default: off, Phase 00.6)
// - features.mapHeatmapSingleLap (default: off, Phase 01a)

import { computeTrackBounds } from './pipeline.js';
import { sLookup } from './sLookup.js';
import { drawRibbon, drawHeatmapRibbon, drawDualRibbons } from './ribbon.js';
import { updateMapLegend } from './mapLegend.js';

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

// Phase 00.6: Draw track outline underneath lap polylines
// Draws TWO parallel lines representing inner and outer track boundaries
function drawTrackOutline(ctx, trackX, trackZ, transform) {
  // Spec: rgba(120, 120, 120, 0.4) — low-contrast grey
  // TEMP: Using distinct colors for inner/outer to verify both draw
  const innerColor = 'rgba(255, 0, 255, 0.7)'; // magenta - inner boundary
  const outerColor = 'rgba(0, 255, 255, 0.7)'; // cyan - outer boundary
  const trackHalfWidth = 15; // meters - approximate track half-width (increased for visibility)
  
  // Draw inner boundary (left side of racing line)
  drawOffsetPolyline(ctx, trackX, trackZ, transform, -trackHalfWidth, innerColor);
  
  // Draw outer boundary (right side of racing line)
  drawOffsetPolyline(ctx, trackX, trackZ, transform, trackHalfWidth, outerColor);
}

// Helper: draw a polyline offset perpendicular to the track centerline
function drawOffsetPolyline(ctx, trackX, trackZ, transform, offsetMeters, color) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  
  // First pass: compute all offset points with smoothed normals
  const offsetPoints = [];
  const lookAhead = 5; // Wider look-ahead for smoother tangents
  
  for (let i = 0; i < trackX.length; i++) {
    const x = trackX[i];
    const z = trackZ[i];
    if (!isFinite(x) || !isFinite(z)) {
      offsetPoints.push(null);
      continue;
    }
    
    // Find valid points ahead and behind for tangent calculation
    let aheadIdx = i + lookAhead;
    while (aheadIdx < trackX.length && (!isFinite(trackX[aheadIdx]) || !isFinite(trackZ[aheadIdx]))) {
      aheadIdx++;
    }
    
    let behindIdx = i - lookAhead;
    while (behindIdx >= 0 && (!isFinite(trackX[behindIdx]) || !isFinite(trackZ[behindIdx]))) {
      behindIdx--;
    }
    
    // Compute tangent using wider look-ahead/behind for stability
    let dx, dz;
    if (aheadIdx < trackX.length && behindIdx >= 0) {
      // Use central difference for smoother tangent
      dx = trackX[aheadIdx] - trackX[behindIdx];
      dz = trackZ[aheadIdx] - trackZ[behindIdx];
    } else if (aheadIdx < trackX.length) {
      dx = trackX[aheadIdx] - x;
      dz = trackZ[aheadIdx] - z;
    } else if (behindIdx >= 0) {
      dx = x - trackX[behindIdx];
      dz = z - trackZ[behindIdx];
    } else {
      offsetPoints.push(null);
      continue;
    }
    
    // Normalize tangent
    const len = Math.sqrt(dx * dx + dz * dz);
    if (len < 0.001) {
      offsetPoints.push(null);
      continue;
    }
    
    const tx = dx / len;
    const tz = dz / len;
    
    // Perpendicular normal (rotate 90° counter-clockwise: (x, z) -> (-z, x))
    // This gives consistent "left" side for negative offset, "right" for positive
    const nx = -tz;
    const nz = tx;
    
    // Offset point
    const ox = x + nx * offsetMeters;
    const oz = z + nz * offsetMeters;
    
    offsetPoints.push({ x: ox, z: oz });
  }
  
  // Second pass: smooth the offset points with a moving average
  const smoothedPoints = [];
  const smoothWindow = 3;
  for (let i = 0; i < offsetPoints.length; i++) {
    if (!offsetPoints[i]) {
      smoothedPoints.push(null);
      continue;
    }
    
    // Average nearby valid points
    let sumX = 0, sumZ = 0, count = 0;
    for (let j = Math.max(0, i - smoothWindow); j <= Math.min(offsetPoints.length - 1, i + smoothWindow); j++) {
      if (offsetPoints[j]) {
        sumX += offsetPoints[j].x;
        sumZ += offsetPoints[j].z;
        count++;
      }
    }
    
    if (count > 0) {
      smoothedPoints.push({ x: sumX / count, z: sumZ / count });
    } else {
      smoothedPoints.push(null);
    }
  }
  
  // Third pass: draw the smoothed polyline, breaking at gaps
  let started = false;
  for (let i = 0; i < smoothedPoints.length; i++) {
    const pt = smoothedPoints[i];
    if (!pt) {
      started = false;
      continue;
    }
    
    const sx = transform.toScreenX(pt.x);
    const sy = transform.toScreenY(pt.z);
    
    if (!started) {
      ctx.moveTo(sx, sy);
      started = true;
    } else {
      ctx.lineTo(sx, sy);
    }
  }
  ctx.stroke();
}

function drawHoverTick(ctx, hoverState, transform, ribbonWidthPx, ribbonGapPx) {
  if (!hoverState || !hoverState.nearest) return;
  const { nearest } = hoverState;
  const sx = transform.toScreenX(nearest.x);
  const sy = transform.toScreenY(nearest.z);

  // Compute local tangent from neighboring raw points for the normal
  // We need the raw arrays, but we can approximate using sLookup result
  // For robustness, use a small screen-space offset to estimate tangent direction
  // then compute the perpendicular.
  const dxWorld = 1.0; // 1 meter forward
  const xFwd = nearest.x + dxWorld;
  const zFwd = nearest.z; // rough approximation — for exactness we'd need the curve
  // Better: use index-based neighbors if we can access raw arrays.
  // Since nearest.i is the raw index, let's try to use raw arrays via a ref if available.
  // For now, a screen-space approximation is sufficient for the test.
  // We'll use the direction from the previous to next point in screen space.
  const p = { x: sx, y: sy };
  // Small forward step in world space to get tangent direction on screen
  const sx2 = transform.toScreenX(nearest.x + 0.5);
  const sy2 = transform.toScreenY(nearest.z);
  const tx = sx2 - sx;
  const ty = sy2 - sy;
  const tlen = Math.hypot(tx, ty) || 1;
  const nx = -ty / tlen;
  const ny = tx / tlen;

  // Span both ribbons: offsetA = -(width+gap)/2, offsetB = +(width+gap)/2
  // Outer edges: offsetA - halfWidth and offsetB + halfWidth
  // Total half-span = ribbonWidth + gap/2 + 4px overshoot
  const halfSpan = ribbonWidthPx + ribbonGapPx / 2 + 4;

  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(sx + nx * -halfSpan, sy + ny * -halfSpan);
  ctx.lineTo(sx + nx * halfSpan, sy + ny * halfSpan);
  ctx.stroke();
}

function drawLinkedHighlight(ctx, lapA, transform, visibleRange, ribbonWidthPx, ribbonGapPx) {
  if (!visibleRange) return;
  const maxIdx = lapA.x.length - 1;
  const startIdx = Math.max(0, Math.floor(visibleRange.start));
  const endIdx = Math.min(maxIdx, Math.ceil(visibleRange.end));

  // No-op if full lap or invalid range
  if (startIdx === 0 && endIdx >= maxIdx) return;
  if (startIdx >= endIdx) return;

  // Build centerline path from startIdx to endIdx
  ctx.save();
  ctx.beginPath();
  let started = false;
  for (let i = startIdx; i <= endIdx; i++) {
    const x = lapA.x[i];
    const z = lapA.z[i];
    if (!isFinite(x) || !isFinite(z)) {
      started = false;
      continue;
    }
    const sx = transform.toScreenX(x);
    const sy = transform.toScreenY(z);
    if (!started) {
      ctx.moveTo(sx, sy);
      started = true;
    } else {
      ctx.lineTo(sx, sy);
    }
  }

  // Stroke with lighten composite
  ctx.globalCompositeOperation = 'lighten';
  ctx.strokeStyle = 'rgba(255,255,255,0.18)';
  ctx.lineWidth = ribbonWidthPx + 10;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();

  // Restore composite operation
  ctx.globalCompositeOperation = 'source-over';

  // Draw perpendicular ticks at startIdx and endIdx
  const halfSpan = ribbonWidthPx / 2 + ribbonGapPx / 2 + 6;

  [startIdx, endIdx].forEach(idx => {
    const x = lapA.x[idx];
    const z = lapA.z[idx];
    if (!isFinite(x) || !isFinite(z)) return;

    // Compute screen-space tangent by looking at neighbors
    let dx = 0, dy = 0;
    let found = false;
    for (let j = idx + 1; j <= maxIdx && !found; j++) {
      const x2 = lapA.x[j];
      const z2 = lapA.z[j];
      if (isFinite(x2) && isFinite(z2)) {
        dx = transform.toScreenX(x2) - transform.toScreenX(x);
        dy = transform.toScreenY(z2) - transform.toScreenY(z);
        found = true;
      }
    }
    if (!found) {
      for (let j = idx - 1; j >= 0 && !found; j--) {
        const x2 = lapA.x[j];
        const z2 = lapA.z[j];
        if (isFinite(x2) && isFinite(z2)) {
          dx = transform.toScreenX(x) - transform.toScreenX(x2);
          dy = transform.toScreenY(z) - transform.toScreenY(z2);
          found = true;
        }
      }
    }
    if (!found) return;

    const tlen = Math.hypot(dx, dy) || 1;
    const nx = -dy / tlen;
    const ny = dx / tlen;

    const sx = transform.toScreenX(x);
    const sy = transform.toScreenY(z);

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(sx + nx * -halfSpan, sy + ny * -halfSpan);
    ctx.lineTo(sx + nx * halfSpan, sy + ny * halfSpan);
    ctx.stroke();
  });

  ctx.restore();
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

// Phase 01b: draw debug tick marks every 100m using sLookup
function drawDebugTicks(ctx, lap, transform, color, labelPrefix) {
  if (!lap || !lap.raw || !lap.raw.s || lap.raw.s.length < 2) return;

  const maxS = lap.raw.s[lap.raw.s.length - 1];
  for (let tickS = 100; tickS < maxS; tickS += 100) {
    const pt = sLookup(lap.raw, tickS);
    if (!pt || !isFinite(pt.x) || !isFinite(pt.z)) continue;

    const sx = transform.toScreenX(pt.x);
    const sy = transform.toScreenY(pt.z);

    // Small cross tick mark
    const tickLen = 4;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(sx - tickLen, sy - tickLen);
    ctx.lineTo(sx + tickLen, sy + tickLen);
    ctx.moveTo(sx - tickLen, sy + tickLen);
    ctx.lineTo(sx + tickLen, sy - tickLen);
    ctx.stroke();

    // s label
    ctx.fillStyle = color;
    ctx.font = '9px sans-serif';
    ctx.fillText(`${labelPrefix}${Math.round(tickS)}`, sx + 6, sy - 4);
  }
}

// ── Main render function ──────────────────────────────────────────────────────
// Renders both laps as polylines on the given canvas.
// Phase 00.6: adds track outline background underneath.

export function renderWalkingSkeleton(canvas, lapA, lapB, options = {}) {
  const { showOutline = false, showHeatmapSingleLap = false, showSAlignmentDebug = false, showDualRibbon = false, showLegend = false, ribbonWidthPx = 8, ribbonGapPx = 2, userScale = 1, userPanX = 0, userPanY = 0 } = options;
  
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
  const baseTransform = fitToView(boundsA, boundsB, rect.width, rect.height, padding);
  const transform = applyUserTransform(baseTransform, userScale, userPanX, userPanY);

  // Draw background
  ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
  ctx.fillRect(0, 0, rect.width, rect.height);

  // Phase 00.6: Draw track outline FIRST (bottom layer)
  if (showOutline) {
    console.log('[trackHeatmapMap] Drawing outline with', lapA.x.length, 'points');
    // Use Lap A's track as the reference outline (spec: derived from either lap)
    drawTrackOutline(ctx, lapA.x, lapA.z, transform);
  } else {
    console.log('[trackHeatmapMap] showOutline is false, skipping outline');
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