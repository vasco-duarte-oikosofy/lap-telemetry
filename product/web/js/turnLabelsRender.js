// ── Turn label rendering (canvas) ───────────────────────────────────────────
// The circuit map is drawn on <canvas id="track-heatmap-canvas"> (the SVG twin
// is hidden — "static outline always prefers canvas"), so labels are painted on
// the canvas too. The placement rule itself lives in turnLabels.js (pure,
// testable) and text metrics come from canvas, so this file only paints.

import { planTurnLabels, fontSizeFor } from './turnLabels.js';

const FONT_WEIGHT = 600;
const FONT_STACK = 'Inter, "Segoe UI", Arial, sans-serif';
const LETTER_SPACING_PX = -0.1;
const LINE_HEIGHT_EM = 1.15;
const HALO_PX = 1.6;

/** Canvas-backed `measure(text, fontSize)` used by the planner. */
export function canvasMeasure(ctx) {
  const cache = new Map();
  return (text, fontSize) => {
    const key = `${fontSize}|${text}`;
    const hit = cache.get(key);
    if (hit) return hit;
    ctx.font = `${FONT_WEIGHT} ${fontSize}px ${FONT_STACK}`;
    const base = ctx.measureText(text).width;
    const result = {
      w: Math.max(0, base + LETTER_SPACING_PX * Math.max(0, text.length - 1)),
      h: fontSize * LINE_HEIGHT_EM,
    };
    cache.set(key, result);
    return result;
  };
}

// Last labels drawn, for the debug hook and the tests.
let lastLabels = [];
let lastDropped = [];

export function getLastTurnLabels() {
  return lastLabels.map(l => ({ ...l }));
}

export function getLastDroppedTurns() {
  return lastDropped.map(d => ({ ...d }));
}

export function clearTurnLabels() {
  lastLabels = [];
  lastDropped = [];
}

/**
 * Paint the turn labels for an outline.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {object} outline  schema v1 outline, may carry `turns`
 * @param {object} transform  fitToView result ({ toScreenX, toScreenY, scale })
 * @param {{width:number, height:number, color?:string, haloColor?:string}} view
 * @returns {{labels:number, dropped:number}}
 */
export function drawTurnLabels(ctx, outline, transform, view) {
  const turns = outline?.turns;
  if (!Array.isArray(turns) || turns.length === 0 || !transform) {
    clearTurnLabels();
    return { labels: 0, dropped: 0 };
  }

  const mapSize = Math.min(view.width, view.height);
  const plan = planTurnLabels({
    turns,
    toMapX: transform.toScreenX,
    toMapZ: transform.toScreenY,
    mapSize,
    mapWidth: view.width,
    mapHeight: view.height,
    measure: canvasMeasure(ctx),
  });

  ctx.save();
  ctx.font = `${FONT_WEIGHT} ${plan.fontSize}px ${FONT_STACK}`;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.lineJoin = 'round';
  ctx.lineWidth = HALO_PX;
  ctx.strokeStyle = view.haloColor || 'rgba(13, 17, 23, 0.9)';
  ctx.fillStyle = view.color || '#c9d1d9';

  for (const label of plan.labels) {
    // Halo first, so text stays readable where it crosses the track ribbon.
    ctx.strokeText(label.text, label.x, label.y);
    ctx.fillText(label.text, label.x, label.y);
  }
  ctx.restore();

  lastLabels = plan.labels;
  lastDropped = plan.dropped;
  return { labels: plan.labels.length, dropped: plan.dropped.length };
}

export { fontSizeFor };
