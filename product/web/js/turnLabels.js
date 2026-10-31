// ── Turn label layout (pure) ────────────────────────────────────────────────
// Places "T1 Abbey"-style labels beside their corners on the circuit map.
// Spec: docs/specs/MAP_TURN_NAMES.md. Pure functions only: text metrics are
// injected by the caller, so the whole rule is testable without a browser and
// portable to other renderers (tinypedal draws with QPainter + QFontMetrics).

export const TURN_LABEL_CONFIG = {
  fontRatio: 0.023,   // fontSize = clamp(mapSize * fontRatio, fontMin, fontMax)
  fontMin: 5,         // 5.75 px at the 250 px map
  // The ceiling only stops absurd type on a giant panel; it must NOT bind in the
  // compare app. A ceiling of 8 px (the 250 px spike's size) froze the type at
  // 8 px on a 910 px map — that is what "the font is too small in compare.html"
  // was. At 18 px the ratio stops scaling above ~783 px mapSize.
  fontMax: 18,
  gapRatio: 0.75,     // label gap from the track: fontSize * gapRatio
  alongCapFont: 2.4,  // max slide ALONG the track, in font sizes
  normalCapMap: 0.04, // max move AWAY from the track, as a fraction of map size
  nudgeSteps: [0, 1.2, -1.2, 2.4, -2.4], // in units of the cap
  smallMapPx: 150,    // below this, also try "<n> <name>" (drops the "T")
};

export function fontSizeFor(mapSize, cfg = TURN_LABEL_CONFIG) {
  return Math.max(cfg.fontMin, Math.min(cfg.fontMax, mapSize * cfg.fontRatio));
}

/** Text variants for one turn, best first. */
export function turnLabelTexts(turn, mapSize, cfg = TURN_LABEL_CONFIG) {
  const name = turn.short_name || turn.name;
  const out = [];
  if (name) {
    out.push(`T${turn.number} ${name}`);
    if (mapSize < cfg.smallMapPx) out.push(`${turn.number} ${name}`);
  }
  out.push(`T${turn.number}`);
  return [...new Set(out)];
}

/**
 * Place every turn label.
 *
 * @param {object}   args
 * @param {Array}    args.turns     baked `turns` from the outline (world coords)
 * @param {Function} args.toMapX    world x -> map px (pipeline buildTrackTransform)
 * @param {Function} args.toMapZ    world y/z -> map px
 * @param {number}   args.mapSize   reference map size in px (sizes the text)
 * @param {number}   [args.mapWidth]  viewport width in px (bounds checks)
 * @param {number}   [args.mapHeight] viewport height in px (bounds checks)
 * @param {Function} args.measure   (text, fontSize) -> { w, h }
 * @param {object}   [args.cfg]
 * @returns {{labels: Array, dropped: Array, fontSize: number}}
 *   labels: [{ turn, text, x, y, w, h, side, apexX, apexY }] in map pixels
 */
export function planTurnLabels({
  turns, toMapX, toMapZ, mapSize, measure,
  mapWidth = mapSize, mapHeight = mapSize, cfg = TURN_LABEL_CONFIG,
}) {
  const fontSize = fontSizeFor(mapSize, cfg);
  const gapPx = fontSize * cfg.gapRatio;
  // Sliding beside a corner still reads as attached; moving away from the track
  // does not, so the two caps differ.
  const alongCap = cfg.alongCapFont * fontSize;
  const normalCap = Math.min(cfg.alongCapFont * fontSize, cfg.normalCapMap * mapSize);

  const placed = [];
  const dropped = [];

  turns.forEach((turn, index) => {
    const ax = toMapX(turn.x);
    const ay = toMapZ(turn.z ?? turn.y);
    // Odd turns sit outside the loop, even turns inside; the other side is the
    // first fallback before a label gives up its name.
    const preferred = index % 2 === 0 ? 1 : -1;
    const sides = [preferred, -preferred];
    // Screen space: toMapZ inverts the world Y axis.
    const nScreen = { x: turn.outward[0], y: -turn.outward[1] };
    const tScreen = { x: turn.tangent[0], y: -turn.tangent[1] };

    const candidates = [];
    // Order matters: keep the name before changing side, change side before
    // sliding further from the corner.
    turnLabelTexts(turn, mapSize, cfg).forEach((text, textIdx) => {
      const { w, h } = measure(text, fontSize);
      sides.forEach((side, sideIdx) => {
        const nx = nScreen.x * side;
        const ny = nScreen.y * side;
        cfg.nudgeSteps.forEach((step, nudgeIdx) => {
          const along = nudgeIdx % 2 === 1;
          const cap = along ? alongCap : normalCap;
          const d = (step / cfg.alongCapFont) * cap;
          const anchorX = ax + nx * gapPx + (along ? tScreen.x * d : nx * d);
          const anchorY = ay + ny * gapPx + (along ? tScreen.y * d : ny * d);
          candidates.push({
            turn: index, number: turn.number, text, textIdx, sideIdx, nudgeIdx, side,
            apexX: ax, apexY: ay,
            // Grow the box away from the track, on the side the label sits.
            x: nx > 0.35 ? anchorX : nx < -0.35 ? anchorX - w : anchorX - w / 2,
            y: ny > 0.35 ? anchorY : ny < -0.35 ? anchorY - h : anchorY - h / 2,
            w, h,
          });
        });
      });
    });

    const fit = candidates.find(c =>
      c.x >= 0 && c.y >= 0 && c.x + c.w <= mapWidth && c.y + c.h <= mapHeight &&
      !placed.some(p => overlaps(c, p)));

    if (fit) {
      placed.push(fit);
      return;
    }
    dropped.push({ number: turn.number, text: candidates.length ? candidates[0].text : `T${turn.number}` });
  });

  return { labels: placed, dropped, fontSize };
}

function overlaps(a, b) {
  const x = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const y = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return x > 0 && y > 0;
}
