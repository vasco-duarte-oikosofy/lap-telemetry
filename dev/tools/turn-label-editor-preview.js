/* Turn label editor — "TinyPedal preview" tab.
   A port of the live widget's own drawing rules so a placement can be judged the
   way it will actually look: its recorded map SVG, its `display_orientation`
   rotation, `scale_map` fit, `font_size` rule and `plan_turn_labels` placement.
   Sources: tinypedal/widget/track_map.py, tinypedal/calculation.py (scale_map,
   rotate_coordinate) and tinypedal/turn_labels.py (anchor_turns,
   plan_turn_labels). Qt text metrics become canvas metrics, so widths differ by
   a pixel here and there — that is the only intentional difference. */

const TP = {
  areaMargin: 40,        // wcfg["area_margin"] default
  fontRatio: 0.023, fontScale: 1.6, fontMin: 5, fontMax: 18,  // TURN_LABEL_CONFIG
  gapRatio: 0.75, alongCapFont: 2.4, normalCapMap: 0.04,
  nudgeSteps: [0, 1.2, -1.2, 2.4, -2.4], smallMap: 150,
  startLineLength: 8,
};

/** TinyPedal rotation: its map coordinates are y-down, so this is a plain
    `rotate_coordinate` in that frame (positive angle turns clockwise on screen). */
function tpRotate(x, y, degrees) {
  const rad = (degrees * Math.PI) / 180, c = Math.cos(rad), s = Math.sin(rad);
  return [c * x - s * y, c * y + s * x];
}

/** calc.scale_map: rotate, fit into the square area, centre the shorter axis. */
function tpScaleMap(coords, areaSize, margin, angle) {
  const rotated = coords.map(([x, y]) => tpRotate(x, y, angle));
  const xs = rotated.map((p) => p[0]), ys = rotated.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = maxX - minX, height = maxY - minY;
  const scale = (areaSize - margin * 2) / Math.max(width, height, 1e-6);
  const offset = width > height ? [margin, (areaSize - height * scale) * 0.5]
                                : [(areaSize - width * scale) * 0.5, margin];
  const points = rotated.map(([x, y]) => [(x - minX) * scale + offset[0], (y - minY) * scale + offset[1]]);
  return { points, rotated, minX, minY, scale, offset, angle };
}

/** turn_labels.anchor_from_fraction: walk the polyline by accumulated length. */
function tpAnchorFromFraction(coords, sFrac) {
  const lengths = [0];
  for (let i = 1; i < coords.length; i += 1) {
    lengths.push(lengths[i - 1] + Math.hypot(coords[i][0] - coords[i - 1][0],
                                            coords[i][1] - coords[i - 1][1]));
  }
  const target = lengths[lengths.length - 1] * Math.min(Math.max(sFrac, 0), 1);
  let index = 0;
  while (index < lengths.length - 2 && lengths[index + 1] < target) index += 1;
  const span = lengths[index + 1] - lengths[index];
  const ratio = span <= 0 ? 0 : (target - lengths[index]) / span;
  const a = coords[index], b = coords[index + 1];
  const low = Math.max(index - 2, 0), high = Math.min(index + 3, coords.length - 1);
  const tx = coords[high][0] - coords[low][0], ty = coords[high][1] - coords[low][1];
  const norm = Math.hypot(tx, ty) || 1;
  return { x: a[0] + (b[0] - a[0]) * ratio, y: a[1] + (b[1] - a[1]) * ratio,
           tx: tx / norm, ty: ty / norm, totalLength: lengths[lengths.length - 1] };
}

/** turn_labels.font_size for a map of `mapSize` pixels. */
function tpFontSize(mapSize) {
  const size = mapSize * TP.fontRatio * TP.fontScale;
  return Math.max(TP.fontMin, Math.min(TP.fontMax, size));
}

/** turn_labels.turn_texts: best first, ending at the number alone. */
function tpTurnTexts(number, name, mapSize) {
  const texts = [];
  if (name) {
    texts.push(`T${number} ${name}`);
    if (mapSize < TP.smallMap) texts.push(`${number} ${name}`);
  }
  texts.push(`T${number}`);
  return [...new Set(texts)];
}

/** turn_labels.plan_turn_labels: odd turns outside the loop, even inside; the
    text degrades before the label moves, and it never overlaps a placed one. */
function tpPlanLabels(anchors, mapSize, areaSize, fontPx, measure) {
  const gap = fontPx * TP.gapRatio;
  const alongCap = TP.alongCapFont * fontPx;
  const normalCap = Math.min(TP.alongCapFont * fontPx, TP.normalCapMap * mapSize);
  const placed = [], dropped = [];
  anchors.forEach((anchor, index) => {
    const preferred = index % 2 === 0 ? 1 : -1;
    let best = null, fallback = null;
    for (const text of tpTurnTexts(anchor.number, anchor.shortName || anchor.name, mapSize)) {
      const [width, height] = measure(text, fontPx);
      for (const side of [preferred, -preferred]) {
        const nx = anchor.normalX * side, ny = anchor.normalY * side;
        for (let step = 0; step < TP.nudgeSteps.length; step += 1) {
          const along = step % 2 === 1;
          const cap = along ? alongCap : normalCap;
          const distance = (TP.nudgeSteps[step] / TP.alongCapFont) * cap;
          let ax = anchor.x + nx * gap, ay = anchor.y + ny * gap;
          if (along) { ax += anchor.tangentX * distance; ay += anchor.tangentY * distance; }
          else { ax += nx * distance; ay += ny * distance; }
          const x = nx > 0.35 ? ax : nx < -0.35 ? ax - width : ax - width * 0.5;
          const y = ny > 0.35 ? ay : ny < -0.35 ? ay - height : ay - height * 0.5;
          const label = { text, x, y, width, height, number: anchor.number };
          if (!fallback) fallback = label;
          const inside = x >= 0 && y >= 0 && x + width <= areaSize && y + height <= areaSize;
          const hits = placed.some((other) => x < other.x + other.width && other.x < x + width &&
                                               y < other.y + other.height && other.y < y + height);
          if (inside && !hits) { best = label; break; }
        }
        if (best) break;
      }
      if (best) break;
    }
    if (best) placed.push(best); else if (fallback) dropped.push(fallback);
  });
  return { placed, dropped };
}

/** The map the widget would draw for this track, in its own raw coordinates. */
function tpGeometry(track) {
  if (track.tinypedal && track.tinypedal.map && track.tinypedal.map.length > 2) {
    return { coords: track.tinypedal.map, source: track.tinypedal.source, units: 'tinypedal' };
  }
  // No recorded map on this machine: fall back to the outline (sim y is up there,
  // TinyPedal's maps are y-down, which is the only conversion needed).
  return { coords: track.centerline.map(([x, y]) => [x, -y]), source: 'outline fallback', units: 'sim' };
}

function drawTinypedalPreview() {
  const track = outline();
  const area = Number(ui["tp-size"].value) || 400;
  const angle = setting().rotation;
  const geometry = tpGeometry(track);
  const { width, height } = state.view;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#080a0d";
  ctx.fillRect(0, 0, width, height);

  const margin = Math.min(Math.max(TP.areaMargin, 0), Math.floor(area / 4));
  const mapSize = area - margin * 2;
  const scaled = tpScaleMap(geometry.coords, area, margin, angle);
  const originX = (width - area) / 2, originY = (height - area) / 2;

  // The widget's frame, so the driver can judge how the map fills it.
  ctx.strokeStyle = "#2b3542";
  ctx.lineWidth = 1;
  ctx.strokeRect(originX, originY, area, area);
  ctx.save();
  ctx.translate(originX, originY);
  ctx.strokeStyle = "#cfd8e3";
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.beginPath();
  scaled.points.forEach(([x, y], index) => (index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.stroke();

  // Start/finish tick, laid across the track at the first recorded point.
  const start = scaled.points[0], next = scaled.points[1];
  const dx = next[0] - start[0], dy = next[1] - start[1];
  const norm = Math.hypot(dx, dy) || 1;
  ctx.strokeStyle = "#ff7f7f";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(start[0] - (dy / norm) * TP.startLineLength, start[1] + (dx / norm) * TP.startLineLength);
  ctx.lineTo(start[0] + (dy / norm) * TP.startLineLength, start[1] - (dx / norm) * TP.startLineLength);
  ctx.stroke();

  const fontPx = Math.min(tpFontSize(mapSize), Math.max(setting().fontSize, 5));
  ctx.font = fontPx + "px system-ui, sans-serif";
  const measure = (text) => [ctx.measureText(text).width, fontPx * 1.25];

  // Anchors exactly like turn_labels.anchor_turns: s_frac on the raw polyline,
  // outward normal from the map centroid, then the map's rotate/scale/offset.
  const centroid = geometry.coords.reduce((acc, [x, y]) => [acc[0] + x / geometry.coords.length,
    acc[1] + y / geometry.coords.length], [0, 0]);
  const anchors = track.turns.map((turn, index) => {
    const frac = (track.tinypedal && track.tinypedal.s_frac && track.tinypedal.s_frac[index]) ??
      (track.lap_length_m > 0 ? turn.apex_s_m / track.lap_length_m : 0);
    const anchor = tpAnchorFromFraction(geometry.coords, frac);
    let nx = -anchor.ty, ny = anchor.tx;
    const away = [anchor.x - centroid[0], anchor.y - centroid[1]];
    if (nx * away[0] + ny * away[1] < 0) { nx = -nx; ny = -ny; }
    const [rx, ry] = tpRotate(anchor.x, anchor.y, angle);
    const [rnx, rny] = tpRotate(nx, ny, angle);
    const [rtx, rty] = tpRotate(anchor.tx, anchor.ty, angle);
    return {
      number: turn.number, name: turn.name, shortName: turn.short_name, id: turn.id, frac,
      x: (rx - scaled.minX) * scaled.scale + scaled.offset[0],
      y: (ry - scaled.minY) * scaled.scale + scaled.offset[1],
      normalX: rnx, normalY: rny, tangentX: rtx, tangentY: rty,
    };
  });

  const { placed, dropped } = tpPlanLabels(anchors, mapSize, area, fontPx, measure);
  const byNumber = new Map(placed.map((label) => [label.number, label]));
  // Offsets are sim metres; the widget's map is in its own units. Both describe
  // the same lap, so their lengths give the conversion factor.
  const metresToMapUnits = track.lap_length_m > 0 && track.tinypedal && track.tinypedal.length > 0
    ? track.tinypedal.length / track.lap_length_m : 1;

  let overridden = 0;
  const drawn = [];
  for (const anchor of anchors) {
    const offset = setting().offsets[anchor.id];
    let label = byNumber.get(anchor.number);
    if (Array.isArray(offset)) {
      // A placement is metres in sim space (y up); TinyPedal's frame is y-down.
      const [ux, uy] = [offset[0] * metresToMapUnits, -offset[1] * metresToMapUnits];
      const [rx, ry] = tpRotate(ux, uy, angle);
      const text = tpTurnTexts(anchor.number, anchor.shortName || anchor.name, mapSize)[0];
      const [w, h] = measure(text);
      label = { text, x: anchor.x + rx * scaled.scale - w / 2, y: anchor.y + ry * scaled.scale - h / 2,
                width: w, height: h };
      overridden += 1;
    }
    if (!label) continue;
    if (ui["tp-dots"].checked) {
      ctx.fillStyle = "#7fd4a0";
      ctx.beginPath(); ctx.arc(anchor.x, anchor.y, 1.6, 0, Math.PI * 2); ctx.fill();
    }
    ctx.font = fontPx + "px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(2, fontPx * 0.22);
    ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
    ctx.strokeText(label.text, label.x, label.y);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label.text, label.x, label.y);
    drawn.push({ id: anchor.id, text: label.text, x: label.x + originX + label.width / 2,
                 y: label.y + originY + label.height / 2, anchorX: anchor.x + originX,
                 anchorY: anchor.y + originY, placed: overridden > 0 && Array.isArray(offset) });
  }
  ctx.restore();
  // Exposed for the tests (and for anyone poking at the console).
  state.preview = { area, margin, fontPx, angle, source: geometry.source, anchors: anchors.length,
                    placed: placed.length, dropped: dropped.length, drawn };

  const unnamed = placed.filter((label) => !/^T?\d+ \S/.test(label.text)).length;
  ui.status.textContent = [
    "TinyPedal preview · " + track.track_name,
    "map: " + geometry.source + " · widget " + area + " px · margin " + margin +
      " · font " + fontPx.toFixed(1) + " px",
    "rotation " + angle + "° · " + anchors.length + " corners · " +
      placed.length + " labels placed, " + dropped.length + " dropped" + (unnamed ? `, ${unnamed} number-only` : ""),
    "from your placement: " + overridden + " · from TinyPedal's own rule: " + (anchors.length - overridden),
  ].join("\n");
  ui.json.value = JSON.stringify(exportPayload(), null, 2);
}
