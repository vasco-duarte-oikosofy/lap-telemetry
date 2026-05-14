// ── Ribbon drawing helpers (extracted from trackHeatmapMap.js) ──────────────
// One file, one job: draw heatmap ribbons (single lap or dual side-by-side).

import { colorForNet } from './colorRamp.js';

function darkenHex(hex) {
  const n = Number.parseInt(hex.slice(1), 16);
  const r = ((n >> 16) & 255) * 0.55;
  const g = ((n >> 8) & 255) * 0.55;
  const b = (n & 255) * 0.55;
  const toHex = (v) => Math.round(v).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function drawRibbonSegment(ctx, a, b, nx, ny, offsetPx, halfWidth, color) {
  const inner = offsetPx - halfWidth;
  const outer = offsetPx + halfWidth;

  const p1 = { x: a.x + nx * inner, y: a.y + ny * inner };
  const p2 = { x: b.x + nx * inner, y: b.y + ny * inner };
  const p3 = { x: b.x + nx * outer, y: b.y + ny * outer };
  const p4 = { x: a.x + nx * outer, y: a.y + ny * outer };

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(p1.x, p1.y);
  ctx.lineTo(p2.x, p2.y);
  ctx.lineTo(p3.x, p3.y);
  ctx.lineTo(p4.x, p4.y);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = darkenHex(color);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(p1.x, p1.y);
  ctx.lineTo(p2.x, p2.y);
  ctx.moveTo(p4.x, p4.y);
  ctx.lineTo(p3.x, p3.y);
  ctx.stroke();
}

export function drawRibbon(ctx, points, offsetPx, widthPx, colorAt) {
  const halfWidth = widthPx / 2;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    if (!a || !b) continue;

    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy);
    if (len < 0.001) continue;

    const nx = -dy / len;
    const ny = dx / len;
    drawRibbonSegment(ctx, a, b, nx, ny, offsetPx, halfWidth, colorAt(i));
  }
}

export function buildScreenPoints(trackX, trackZ, transform) {
  return Array.from(trackX, (x, i) => {
    const z = trackZ[i];
    if (!isFinite(x) || !isFinite(z)) return null;
    return { x: transform.toScreenX(x), y: transform.toScreenY(z) };
  });
}

export function netAt(lap, index) {
  const throttle = lap.throttle?.[index] ?? 0;
  const brake = lap.brake?.[index] ?? 0;
  return throttle - brake;
}

export function drawHeatmapRibbon(ctx, lap, transform, widthPx) {
  const points = buildScreenPoints(lap.x, lap.z, transform);
  drawRibbon(ctx, points, 0, widthPx, (i) => colorForNet((netAt(lap, i) + netAt(lap, i + 1)) / 2));
}

export function drawDualRibbons(ctx, lapA, lapB, transform, widthPx, gapPx) {
  const points = buildScreenPoints(lapA.x, lapA.z, transform);
  const halfWidth = widthPx / 2;
  const offsetA = -(widthPx + gapPx) / 2;
  const offsetB = +(widthPx + gapPx) / 2;

  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    if (!a || !b) continue;

    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy);
    if (len < 0.001) continue;

    const nx = -dy / len;
    const ny = dx / len;

    const colorA = colorForNet((netAt(lapA, i) + netAt(lapA, i + 1)) / 2);
    drawRibbonSegment(ctx, a, b, nx, ny, offsetA, halfWidth, colorA);

    const colorB = colorForNet((netAt(lapB, i) + netAt(lapB, i + 1)) / 2);
    drawRibbonSegment(ctx, a, b, nx, ny, offsetB, halfWidth, colorB);

    // Phase 03: outer-edge accent outline — draw after fill so it sits on top
    // Lap A outer edge = offsetA - halfWidth (more negative, farther from center)
    const outA = offsetA - halfWidth;
    ctx.strokeStyle = lapA.color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(a.x + nx * outA, a.y + ny * outA);
    ctx.lineTo(b.x + nx * outA, b.y + ny * outA);
    ctx.stroke();

    // Lap B outer edge = offsetB + halfWidth (more positive, farther from center)
    const outB = offsetB + halfWidth;
    ctx.strokeStyle = lapB.color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(a.x + nx * outB, a.y + ny * outB);
    ctx.lineTo(b.x + nx * outB, b.y + ny * outB);
    ctx.stroke();
  }
}
