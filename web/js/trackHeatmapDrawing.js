import { sLookup } from './sLookup.js';

export function drawPolyline(ctx, trackX, trackZ, transform, color, lineWidth = 1) {
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

export function drawHoverTick(ctx, hoverState, transform, ribbonWidthPx, ribbonGapPx) {
  if (!hoverState || !hoverState.nearest) return;
  const { nearest } = hoverState;
  const sx = transform.toScreenX(nearest.x);
  const sy = transform.toScreenY(nearest.z);
  const sx2 = transform.toScreenX(nearest.x + 0.5);
  const sy2 = transform.toScreenY(nearest.z);
  const tx = sx2 - sx;
  const ty = sy2 - sy;
  const tlen = Math.hypot(tx, ty) || 1;
  const nx = -ty / tlen;
  const ny = tx / tlen;
  const halfSpan = ribbonWidthPx + ribbonGapPx / 2 + 4;

  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(sx + nx * -halfSpan, sy + ny * -halfSpan);
  ctx.lineTo(sx + nx * halfSpan, sy + ny * halfSpan);
  ctx.stroke();
}

export function drawLinkedHighlight(ctx, lapA, transform, visibleRange, ribbonWidthPx, ribbonGapPx) {
  if (!visibleRange) return;
  const maxIdx = lapA.x.length - 1;
  const startIdx = Math.max(0, Math.floor(visibleRange.start));
  const endIdx = Math.min(maxIdx, Math.ceil(visibleRange.end));
  if (startIdx === 0 && endIdx >= maxIdx) return;
  if (startIdx >= endIdx) return;

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

  ctx.globalCompositeOperation = 'lighten';
  ctx.strokeStyle = 'rgba(255,255,255,0.18)';
  ctx.lineWidth = ribbonWidthPx + 10;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();
  ctx.globalCompositeOperation = 'source-over';

  const halfSpan = ribbonWidthPx / 2 + ribbonGapPx / 2 + 6;
  [startIdx, endIdx].forEach(idx => drawHighlightTick(ctx, lapA, transform, idx, maxIdx, halfSpan));
  ctx.restore();
}

function drawHighlightTick(ctx, lapA, transform, idx, maxIdx, halfSpan) {
  const x = lapA.x[idx];
  const z = lapA.z[idx];
  if (!isFinite(x) || !isFinite(z)) return;

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
}

export function drawStartFinishTick(ctx, startX, startZ, transform) {
  const sx = transform.toScreenX(startX);
  const sy = transform.toScreenY(startZ);
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

export function drawDebugTicks(ctx, lap, transform, color, labelPrefix) {
  if (!lap || !lap.raw || !lap.raw.s || lap.raw.s.length < 2) return;

  const maxS = lap.raw.s[lap.raw.s.length - 1];
  for (let tickS = 100; tickS < maxS; tickS += 100) {
    const pt = sLookup(lap.raw, tickS);
    if (!pt || !isFinite(pt.x) || !isFinite(pt.z)) continue;

    const sx = transform.toScreenX(pt.x);
    const sy = transform.toScreenY(pt.z);
    const tickLen = 4;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(sx - tickLen, sy - tickLen);
    ctx.lineTo(sx + tickLen, sy + tickLen);
    ctx.moveTo(sx - tickLen, sy + tickLen);
    ctx.lineTo(sx + tickLen, sy - tickLen);
    ctx.stroke();

    ctx.fillStyle = color;
    ctx.font = '9px sans-serif';
    ctx.fillText(`${labelPrefix}${Math.round(tickS)}`, sx + 6, sy - 4);
  }
}
