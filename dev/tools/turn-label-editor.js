/* Turn label editor — app code. Loaded after `turn-label-data.js` (generated) from
   `turn-label-editor.html`. Both are classic scripts so the page works from a
   double-clicked `file://` URL; a file:// page cannot fetch, hence the inlining. */
"use strict";
const TRACKS = window.TURN_LABEL_DATA;
const PRESETS = window.TURN_LABEL_PRESETS || {};
const STORAGE_KEY = "turnLabelEditor.v1";
const MIN_LABEL_GAP_FRACTION = 0.03;   // first placement: 3% of the layout diagonal
const canvas = document.getElementById("canvas"), ctx = canvas.getContext("2d"), ui = {};
for (const id of ["track", "rotation", "rotation-number", "rotation-value", "zoom", "zoom-value",
  "label-mode", "font-size", "font-size-value", "leaders", "dots", "status", "json",
  "reset-track", "reset-all", "copy", "download", "import-file", "tab-edit", "tab-preview",
  "tp-size", "tp-dots"]) {
  ui[id] = document.getElementById(id);
}

const blankTrack = () => ({ rotation: 0, zoom: 100, mode: "number-name", fontSize: 13, offsets: {} });
/** Shipped placement for a track (dev/tools/turn-label-presets.json), or null. */
function presetFor(slug) {
  const preset = PRESETS[slug];
  if (!preset) return null;
  return placementFromPayload({ display_orientation: preset.display_orientation, zoom: preset.zoom,
    label_text: preset.label_text, font_px: preset.font_px, labels: preset.labels });
}
/**
 * v1 exports were produced while drag offsets were *drawn* with a flipped Y, so
 * the stored dy is what looked right on screen rather than the map-space truth.
 * Repair it by mirroring Y in the OLD display frame and converting back. The old
 * frame is spelled out here on purpose: it was y-up-then-flip, not the y-down
 * frame this file uses now, and the repair must not follow the new convention.
 */
function repairLegacyOffset(dx, dy, rotation) {
  const rad = (rotation * Math.PI) / 180, c = Math.cos(rad), s = Math.sin(rad);
  const rx = dx * c - dy * s, ry = dx * s + dy * c;         // old y-up rotation
  // What the user saw is (rx, +ry) relative to the corner; the fixed renderer
  // needs (rx, -ry), so store the offset that produces it.
  const ty = -ry;
  return [rx * c + ty * s, -rx * s + ty * c];
}
function placementFromPayload(payload) {
  const version = Number(payload.version) || 1;
  const stored = Math.round(Number(payload.display_orientation) || 0);
  // Before version 3 the editor rotated the map the other way round; the same
  // picture therefore needs the negated angle in TinyPedal's convention.
  const rotation = version < 3 ? -stored : stored;
  const offsets = {};
  for (const [id, offset] of Object.entries(payload.labels || {})) {
    if (!offset || !Number.isFinite(offset.dx_m) || !Number.isFinite(offset.dy_m)) continue;
    offsets[id] = version < 2 ? repairLegacyOffset(offset.dx_m, offset.dy_m, stored)
                              : [offset.dx_m, offset.dy_m];
  }
  return {
    rotation,
    zoom: Number(payload.zoom) || 100,
    mode: ["number-name", "name", "number"].includes(payload.label_text) ? payload.label_text : "number-name",
    fontSize: Number(payload.font_px) || 13,
    offsets,
  };
}
function loadStore() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || { current: null, tracks: {} }; }
  catch (error) { return { current: null, tracks: {} }; }
}
const store = loadStore();
const state = { slug: null, view: null, selected: null, drag: null, placed: [] };
function saveStore() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(store)); } catch (error) { /* file:// may refuse */ }
}
const setting = () => store.tracks[state.slug] ||
  (store.tracks[state.slug] = presetFor(state.slug) || blankTrack());
const outline = () => TRACKS.tracks[state.slug];

/**
 * Rotation in *display* space, matching TinyPedal's `rotate_coordinate`: its map
 * coordinates are y-down, so a positive angle turns the map clockwise on screen.
 * Sim coordinates are y-up, so every conversion to display negates Y first. That
 * keeps the editor and the TinyPedal preview rotating identically and makes the
 * exported `display_orientation` usable by the widget verbatim.
 */
function rotate(x, y, degrees) {
  const rad = (degrees * Math.PI) / 180, c = Math.cos(rad), s = Math.sin(rad);
  return [x * c - y * s, x * s + y * c];
}
const toDisplay = (x, y) => [x, -y];
function bounds(points) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of points) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  }
  return { minX, maxX, minY, maxY };
}
function buildView() {
  const rot = setting().rotation, zoom = setting().zoom / 100;
  const rotated = outline().centerline.map(([x, y]) => rotate(...toDisplay(x, y), rot));
  const { minX, maxX, minY, maxY } = bounds(rotated);
  // Placement spacing uses the UNROTATED bounds, so a label's default offset in
  // metres cannot drift when the map is rotated.
  const base = bounds(outline().centerline.map(([x, y]) => toDisplay(x, y)));
  const width = canvas.clientWidth || 800, height = canvas.clientHeight || 600;
  const margin = Math.max(28, Math.min(width, height) * 0.06);
  const spanX = Math.max(maxX - minX, 1e-6), spanY = Math.max(maxY - minY, 1e-6);
  state.view = {
    rot, width, height,
    scale: Math.min((width - margin * 2) / spanX, (height - margin * 2) / spanY) * zoom,
    cx: (minX + maxX) / 2, cy: (minY + maxY) / 2,
    diagonal: Math.hypot(base.maxX - base.minX, base.maxY - base.minY),
  };
}
function toScreen(x, y) {
  const view = state.view;
  const [rx, ry] = rotate(...toDisplay(x, y), view.rot);
  return [view.width / 2 + (rx - view.cx) * view.scale, view.height / 2 + (ry - view.cy) * view.scale];
}
/** Screen-space delta -> map-space delta: undo the Y flip, then undo the rotation. */
function screenToMapDelta(dxPixels, dyPixels) {
  const view = state.view;
  const [dx, dy] = rotate(dxPixels / view.scale, dyPixels / view.scale, -view.rot);
  return [dx, -dy];
}
let autoLayout = { key: null, offsets: {} };
function unrotatedView() {
  const box = bounds(outline().centerline);
  const width = canvas.clientWidth || 800, height = canvas.clientHeight || 600;
  const margin = Math.max(28, Math.min(width, height) * 0.06);
  const spanX = Math.max(box.maxX - box.minX, 1e-6), spanY = Math.max(box.maxY - box.minY, 1e-6);
  const scale = Math.min((width - margin * 2) / spanX, (height - margin * 2) / spanY) * (setting().zoom / 100);
  return { width, height, scale, diagonal: Math.hypot(spanX, spanY),
           cx: (box.minX + box.maxX) / 2, cy: (box.minY + box.maxY) / 2 };
}
/** Auto-place a label the user has not moved: first candidate that collides with nothing. */
function computeAutoLayout() {
  const key = [state.slug, setting().mode, setting().fontSize, setting().zoom,
               Math.round(state.view.width), Math.round(state.view.height)].join("|");
  if (autoLayout.key === key) return autoLayout.offsets;
  const view = unrotatedView();
  const fontPx = setting().fontSize, previousFont = ctx.font;
  ctx.font = fontPx + "px system-ui, sans-serif";
  const boxes = [], offsets = {};
  for (const turn of outline().turns) {
    const w = ctx.measureText(labelText(turn)).width + 8, h = fontPx + 6;
    const outward = turn.outward || [0, 0];
    // An outline without a baked tangent still gets along-track candidates.
    const tangent = turn.tangent || [-outward[1], outward[0]];
    const ax = view.width / 2 + (turn.x - view.cx) * view.scale;
    const ay = view.height / 2 + (-turn.y - view.cy) * view.scale;
    let fallback = null, hit = null;
    // One "row" away from the corner is a label height; one step along the track
    // is a label width, so stacking works the same on a 1.6 km and a 13 km layout.
    const stepOut = Math.max((h * 1.15) / view.scale, MIN_LABEL_GAP_FRACTION * view.diagonal);
    const stepAlong = (w + 6) / view.scale;
    candidates:
    for (const distance of [1, 2, 3, 4, 5, 6, 8, 10])
      for (const side of [1, -1])
        for (const slide of [0, 1, -1, 2, -2, 3, -3, 4, -4]) {
          const dx = outward[0] * side * distance * stepOut + tangent[0] * slide * stepAlong;
          const dy = -(outward[1] * side * distance * stepOut + tangent[1] * slide * stepAlong);
          const box = { x: ax + dx * view.scale - w / 2, y: ay - dy * view.scale - h / 2, w, h };
          const candidate = { dx, dy, box };
          if (!fallback) fallback = candidate;
          // Off-canvas counts as a collision: a label the user cannot see is worse
          // than one that sits a row further out.
          const hits = box.x < 0 || box.y < 0 || box.x + box.w > view.width ||
                       box.y + box.h > view.height ||
                       boxes.some((o) => box.x < o.x + o.w && o.x < box.x + box.w &&
                                         box.y < o.y + o.h && o.y < box.y + box.h);
          if (!hits) { hit = candidate; break candidates; }
        }
    const chosen = hit || fallback;
    offsets[turn.id] = [chosen.dx, chosen.dy];
    boxes.push(chosen.box);
  }
  ctx.font = previousFont;
  autoLayout = { key, offsets };
  return offsets;
}
function offsetOf(turn) {
  const stored = setting().offsets[turn.id];
  return Array.isArray(stored) && stored.length === 2 ? [stored[0], stored[1]]
                                                     : (computeAutoLayout()[turn.id] || [0, 0]);
}

function labelText(turn) {
  const name = turn.short_name || turn.name;
  return setting().mode === "number" ? String(turn.number)
    : setting().mode === "name" ? name : turn.number + " " + name;
}

function draw() {
  const track = outline();
  if (!track) return;
  buildView();
  const dpr = window.devicePixelRatio || 1, { width, height } = state.view;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#080a0d";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#3f6f9e";
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.beginPath();
  track.centerline.forEach(([x, y], index) => {
    const [sx, sy] = toScreen(x, y);
    if (index === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
  });
  ctx.stroke();

  const [fx, fy] = toScreen(track.centerline[0][0], track.centerline[0][1]);
  ctx.fillStyle = "#f3f7ff";
  ctx.beginPath(); ctx.arc(fx, fy, 4, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = "#6b7f96";
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.fillText("start", fx + 7, fy);

  const fontPx = setting().fontSize;
  ctx.font = fontPx + "px system-ui, sans-serif";
  state.placed = [];
  for (const turn of track.turns) {
    const [ax, ay] = toScreen(turn.x, turn.y);
    const [ox, oy] = rotate(offsetOf(turn)[0], -offsetOf(turn)[1], state.view.rot);
    const lx = ax + ox * state.view.scale, ly = ay + oy * state.view.scale;
    if (ui.dots.checked) {
      ctx.fillStyle = "#7fd4a0";
      ctx.beginPath(); ctx.arc(ax, ay, 2.5, 0, Math.PI * 2); ctx.fill();
    }
    const text = labelText(turn);
    const boxWidth = ctx.measureText(text).width + 8, boxHeight = fontPx + 6;
    const [tx, ty] = [lx - boxWidth / 2, ly - boxHeight / 2];
    if (ui.leaders.checked) {
      ctx.strokeStyle = "rgba(160, 190, 220, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(lx, ly); ctx.stroke();
    }
    const selected = state.selected === turn.id;
    ctx.fillStyle = selected ? "rgba(90, 150, 220, 0.85)" : "rgba(16, 22, 30, 0.72)";
    ctx.strokeStyle = selected ? "#cfe3ff" : "rgba(120, 150, 185, 0.55)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.rect(tx, ty, boxWidth, boxHeight);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = selected ? "#ffffff" : "#e8ecf2";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, lx, ly + 0.5);
    state.placed.push({ id: turn.id, x: tx, y: ty, w: boxWidth, h: boxHeight });
  }
  updateStatus();
  ui.json.value = JSON.stringify(exportPayload(), null, 2);
}

function hitTest(sx, sy) {
  for (let index = state.placed.length - 1; index >= 0; index -= 1) {
    const l = state.placed[index];
    if (sx >= l.x && sx <= l.x + l.w && sy >= l.y && sy <= l.y + l.h) return l;
  }
  return null;
}
const pointerPosition = (event) => {
  const rect = canvas.getBoundingClientRect();
  return [event.clientX - rect.left, event.clientY - rect.top];
};
canvas.addEventListener("pointerdown", (event) => {
  const [sx, sy] = pointerPosition(event);
  const label = hitTest(sx, sy);
  if (!label) return;
  const turn = outline().turns.find((item) => item.id === label.id);
  state.selected = label.id;
  state.drag = { id: label.id, startX: sx, startY: sy, base: offsetOf(turn) };
  canvas.setPointerCapture(event.pointerId);
  canvas.style.cursor = "grabbing";
  draw();
});
canvas.addEventListener("pointermove", (event) => {
  const [sx, sy] = pointerPosition(event);
  if (!state.drag) {
    canvas.style.cursor = hitTest(sx, sy) ? "grab" : "default";
    return;
  }
  const [dmx, dmy] = screenToMapDelta(sx - state.drag.startX, sy - state.drag.startY);
  setting().offsets[state.drag.id] = [state.drag.base[0] + dmx, state.drag.base[1] + dmy];
  draw();
});
function endDrag() {
  if (!state.drag) return;
  state.drag = null;
  canvas.style.cursor = "default";
  saveStore();
}
canvas.addEventListener("pointerup", endDrag);
canvas.addEventListener("pointercancel", endDrag);
window.addEventListener("keydown", (event) => {
  const keys = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
  if (!state.selected || !keys.includes(event.key)) return;
  event.preventDefault();
  const step = event.shiftKey ? 10 : 1;
  const base = offsetOf(outline().turns.find((item) => item.id === state.selected));
  const [dmx, dmy] = screenToMapDelta(
    (event.key === "ArrowRight" ? step : 0) - (event.key === "ArrowLeft" ? step : 0),
    (event.key === "ArrowDown" ? step : 0) - (event.key === "ArrowUp" ? step : 0));
  setting().offsets[state.selected] = [base[0] + dmx, base[1] + dmy];
  draw();
  saveStore();
});

function exportPayload() {
  const track = outline(), labels = {};
  for (const turn of track.turns) {
    const [dx, dy] = offsetOf(turn);
    labels[turn.id] = { dx_m: Math.round(dx * 10) / 10, dy_m: Math.round(dy * 10) / 10 };
  }
  return {
    tool: "turn-label-editor", version: 3,
    track: state.slug, track_name: track.track_name, layout: track.layout,
    lap_length_m: track.lap_length_m, display_orientation: setting().rotation,
    label_text: setting().mode, font_px: setting().fontSize, labels,
  };
}
function updateStatus() {
  const track = outline();
  const selected = track.turns.find((item) => item.id === state.selected);
  const lines = [track.track_name + (track.layout ? " (" + track.layout + ")" : "") + " · " +
                 track.turns.length + " corners · " + track.lap_length_m + " m"];
  if (selected) {
    const [dx, dy] = offsetOf(selected);
    lines.push("selected: " + labelText(selected) + " — " + dx.toFixed(1) + " / " + dy.toFixed(1) + " m");
  } else lines.push("drag a name, or click one and use the arrow keys");
  ui.status.textContent = lines.join("\n");
}
