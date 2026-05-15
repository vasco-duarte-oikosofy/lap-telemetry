// ── Learned Outline Rendering ──────────────────────────────────────────────
// Draws learned left/right boundary polylines underneath current lap
// trajectories/ribbons on the canvas-based track map.
//
// Feature flag: features.learnedTrackOutline
// Data source: learnedBoundariesByLayout map in appState.js

/**
 * Check whether a parsed JSON object looks like boundary data.
 * Boundary JSON has track_id, layout_id, and left/right arrays.
 */
export function isBoundaryData(obj) {
  return !!(
    obj &&
    typeof obj === 'object' &&
    !Array.isArray(obj) &&
    'track_id' in obj &&
    'layout_id' in obj &&
    Array.isArray(obj.left) &&
    Array.isArray(obj.right)
  );
}

/**
 * Build a key for matching boundary data to session track/layout.
 * Uses the same slug logic as apexMetricsUi for matching.
 */
export function boundaryKey(trackId, layoutId) {
  const slug = (s) => String(s || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `${slug(trackId)}::${slug(layoutId || 'default')}`;
}

/**
 * Draw learned boundary polylines on the canvas.
 *
 * Boundaries are drawn as faint lines BELOW the lap轨迹 (the caller is
 * responsible for draw order: boundaries first, then lap traces).
 *
 * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
 * @param {Object} boundaries - { left: [{x_m, z_m, ...}], right: [{x_m, z_m, ...}] }
 * @param {Object|null} transform - World-to-screen transform with toScreenX, toScreenY methods
 * @param {Object} [style] - Optional style overrides
 * @param {string} [style.leftColor] - CSS color for left boundary (default faint cyan)
 * @param {string} [style.rightColor] - CSS color for right boundary (default faint cyan)
 * @param {number} [style.lineWidth] - Line width in pixels (default 1)
 * @param {number} [style.alpha] - Alpha transparency 0-1 (default 0.35)
 */
export function drawLearnedBoundaries(ctx, boundaries, transform, style = {}) {
  if (!boundaries || !transform) return;

  const leftColor = style.leftColor || 'rgba(0, 255, 255, 0.35)';
  const rightColor = style.rightColor || 'rgba(0, 255, 255, 0.35)';
  const lineWidth = style.lineWidth ?? 1;

  drawBoundaryPolyline(ctx, boundaries.left, transform, leftColor, lineWidth);
  drawBoundaryPolyline(ctx, boundaries.right, transform, rightColor, lineWidth);
}

/**
 * Draw a single boundary polyline (left or right).
 * Skips points with width_m === 0 (one-sided or missing coverage).
 */
function drawBoundaryPolyline(ctx, points, transform, color, lineWidth) {
  if (!points || points.length < 2) return;

  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();

  let started = false;
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    // Skip zero-width points — they are at the center path, not a real boundary
    if (p.width_m === 0) {
      started = false;
      continue;
    }
    if (!isFinite(p.x_m) || !isFinite(p.z_m)) {
      started = false;
      continue;
    }
    const sx = transform.toScreenX(p.x_m);
    const sy = transform.toScreenY(p.z_m);
    if (!started) {
      ctx.moveTo(sx, sy);
      started = true;
    } else {
      ctx.lineTo(sx, sy);
    }
  }
  ctx.stroke();
}

/**
 * Find boundary data matching the session's track/layout.
 * Searches the learnedBoundariesByLayout map using slug-matched keys.
 *
 * @param {Map} boundariesMap - Map from "track::layout" key to boundary data
 * @param {string} track - Track name from sidecar
 * @param {string} layout - Layout name from sidecar
 * @returns {Object|null} - Matching boundary data or null
 */
export function findBoundaryData(boundariesMap, track, layout) {
  if (!boundariesMap || !track) return null;
  const key = boundaryKey(track, layout);
  return boundariesMap.get(key) || null;
}