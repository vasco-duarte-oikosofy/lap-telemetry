const REQUIRED_ARRAYS = ['left_boundary', 'right_boundary', 'centerline'];

export function validateStaticOutline(outline) {
  if (!outline || outline.schema_version !== 1) {
    throw new Error('Static track outline must use schema_version 1');
  }
  for (const key of REQUIRED_ARRAYS) {
    const points = outline[key];
    if (!Array.isArray(points) || points.length === 0) {
      throw new Error(`Static track outline missing ${key}`);
    }
    for (const point of points) {
      if (!Number.isFinite(point?.x) || !Number.isFinite(point?.y)) {
        throw new Error(`Static track outline ${key} contains a non-finite point`);
      }
    }
  }
}

export function renderStaticTrackOutlineSvg(outline, trackTransform) {
  if (!outline || !trackTransform) return '';
  validateStaticOutline(outline);
  const left = renderBoundary(outline.left_boundary, trackTransform, 'left_boundary', 'static-track-boundary');
  const right = renderBoundary(outline.right_boundary, trackTransform, 'right_boundary', 'static-track-boundary');
  const center = renderBoundary(outline.centerline, trackTransform, 'centerline', 'static-track-centerline');
  return `<g data-static-track-outline="${outline.sim_track_name || 'unknown'}" class="static-track-outline">${left}${right}${center}</g>`;
}

function renderBoundary(points, trackTransform, part, className) {
  const pts = pointsToSvg(points, trackTransform);
  if (!pts) return '';
  return `<polyline data-static-outline-part="${part}" class="${className}" points="${pts}"/>`;
}

/**
 * Draw a static track outline on a canvas 2D context.
 * Draws boundaries and dashed centerline as faint visual context.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} outline - Schema v1 static outline from findOutlineByTrackName()
 * @param {Object} transform - World-to-screen transform with toScreenX/toScreenY
 */
export function drawStaticTrackOutline(ctx, outline, transform) {
  if (!outline || !transform) return;
  validateStaticOutline(outline);
  const boundaryColor = 'rgba(210, 210, 210, 0.28)';
  const centerColor = 'rgba(210, 210, 210, 0.18)';
  drawPointsPolyline(ctx, outline.left_boundary, transform, boundaryColor, 1);
  drawPointsPolyline(ctx, outline.right_boundary, transform, boundaryColor, 1);
  drawPointsPolyline(ctx, outline.centerline, transform, centerColor, 0.8, [3, 4]);
}

function drawPointsPolyline(ctx, points, transform, color, lineWidth, dash) {
  if (!points || points.length < 2) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  if (dash) ctx.setLineDash(dash); else ctx.setLineDash([]);
  ctx.beginPath();
  let started = false;
  for (const point of points) {
    const sx = transform.toScreenX(point.x);
    const sy = transform.toScreenY(point.y);
    if (!isFinite(sx) || !isFinite(sy)) { started = false; continue; }
    if (!started) { ctx.moveTo(sx, sy); started = true; }
    else { ctx.lineTo(sx, sy); }
  }
  ctx.stroke();
  ctx.setLineDash([]);
}

function pointsToSvg(points, trackTransform) {
  const pts = [];
  for (const point of points) {
    const x = trackTransform.toMapX(point.x);
    const y = trackTransform.toMapZ(point.y);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
  }
  return pts.join(' ');
}