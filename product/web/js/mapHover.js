/**
 * Map hover helper — spatial index, pointer hit-testing, and readout DOM.
 * One file, one job: everything the user sees when hovering over the track map.
 */

import { sLookup } from './sLookup.js';

const CELL_SIZE = 20; // meters — uniform grid cell size

// ── Spatial index ─────────────────────────────────────────────────────────────
// Simple uniform grid keyed by integer world-cell coordinates.

function buildGrid(lapARaw) {
  if (!lapARaw || !lapARaw.x || !lapARaw.z) return null;
  const grid = new Map();
  for (let i = 0; i < lapARaw.x.length; i++) {
    const x = lapARaw.x[i];
    const z = lapARaw.z[i];
    if (!isFinite(x) || !isFinite(z)) continue;
    const cx = Math.floor(x / CELL_SIZE);
    const cz = Math.floor(z / CELL_SIZE);
    const key = `${cx},${cz}`;
    if (!grid.has(key)) grid.set(key, []);
    grid.get(key).push({ x, z, s: lapARaw.s[i], i });
  }
  return grid;
}

function findNearest(grid, worldX, worldZ) {
  if (!grid) return null;
  const cx = Math.floor(worldX / CELL_SIZE);
  const cz = Math.floor(worldZ / CELL_SIZE);
  let best = null;
  let bestDist = Infinity;
  for (let dx = -1; dx <= 1; dx++) {
    for (let dz = -1; dz <= 1; dz++) {
      const key = `${cx + dx},${cz + dz}`;
      const pts = grid.get(key);
      if (!pts) continue;
      for (const pt of pts) {
        const d2 = (pt.x - worldX) ** 2 + (pt.z - worldZ) ** 2;
        if (d2 < bestDist) {
          bestDist = d2;
          best = pt;
        }
      }
    }
  }
  return best;
}

// ── Screen ↔ world conversion ───────────────────────────────────────────────

function worldFromScreen(sx, sy, transform) {
  const x = (sx - transform.offsetX - (transform.userPanX || 0)) / transform.scale + transform.bounds.minX;
  const z = transform.bounds.maxZ - (sy - transform.offsetY - (transform.userPanY || 0)) / transform.scale;
  return { x, z };
}

// ── Readout DOM ───────────────────────────────────────────────────────────────

function ensureReadout(panel) {
  let el = document.getElementById('map-hover-readout');
  if (!el) {
    el = document.createElement('div');
    el.id = 'map-hover-readout';
    el.className = 'map-hover-readout';
    el.style.display = 'none';
    el.innerHTML = `
      <div class="readout-dist"></div>
      <div class="readout-row" id="readout-row-a"></div>
      <div class="readout-row" id="readout-row-b"></div>
    `;
    panel.appendChild(el);
  }
  return el;
}

function updateReadout(el, state, lapA, lapB) {
  if (!state || !el) {
    if (el) el.style.display = 'none';
    return;
  }

  const distEl = el.querySelector('.readout-dist');
  const rowA = el.querySelector('#readout-row-a');
  const rowB = el.querySelector('#readout-row-b');

  const s = Math.round(state.s);
  distEl.textContent = `Distance: ${s} m`;

  const ta = state.lapASample?.throttle ?? 0;
  const ba = state.lapASample?.brake ?? 0;
  rowA.innerHTML = `
    <span style="color:${lapA.color}">Lap A</span>
    — Throttle <span style="color:#4caf50">${Math.round(ta * 100)}%</span>
    / Brake <span style="color:#2196f3">${Math.round(ba * 100)}%</span>
  `;

  const tb = state.lapBSample?.throttle ?? 0;
  const bb = state.lapBSample?.brake ?? 0;
  rowB.innerHTML = `
    <span style="color:${lapB.color}">Lap B</span>
    — Throttle <span style="color:#4caf50">${Math.round(tb * 100)}%</span>
    / Brake <span style="color:#2196f3">${Math.round(bb * 100)}%</span>
  `;

  el.style.display = 'block';
}

function positionReadout(el, sx, sy, canvasWidth, canvasHeight) {
  if (!el || el.style.display === 'none') return;
  const rect = el.getBoundingClientRect();
  const w = rect.width || 180;
  const h = rect.height || 60;
  const offset = 12;

  let left = sx + offset;
  let top = sy + offset;

  // Flip horizontally if near right edge
  if (left + w > canvasWidth) {
    left = sx - w - offset;
  }
  // Flip vertically if near bottom edge
  if (top + h > canvasHeight) {
    top = sy - h - offset;
  }

  el.style.left = `${Math.round(left)}px`;
  el.style.top = `${Math.round(top)}px`;
}

// ── Public API ────────────────────────────────────────────────────────────────

export function createMapHover(canvas, getLapData, onUpdate) {
  let hoverState = null;
  let rafId = null;
  let pendingEvent = null;
  let isDragging = false;
  let directPointerActive = false;
  let linkedDistance = null;
  let grid = null;
  let readoutEl = null;

  function build() {
    const { lapA } = getLapData();
    grid = buildGrid(lapA?.raw);
  }

  function makeHoverState(nearest, sx, sy, lapA, lapB) {
    const s = nearest.s;
    return {
      s,
      screenX: sx,
      screenY: sy,
      lapASample: sLookup(lapA.raw, s),
      lapBSample: lapB?.raw ? sLookup(lapB.raw, s) : null,
      nearest,
    };
  }

  function hideHover() {
    const wasActive = hoverState !== null || (readoutEl && readoutEl.style.display !== 'none');
    hoverState = null;
    if (readoutEl) readoutEl.style.display = 'none';
    if (wasActive) onUpdate?.(null);
  }

  function applyHoverState(nextState) {
    if (!nextState) {
      hideHover();
      return;
    }

    const { lapA, lapB } = getLapData();
    if (!lapA || !lapB) {
      hideHover();
      return;
    }

    hoverState = nextState;
    const rect = canvas.getBoundingClientRect();
    readoutEl = ensureReadout(canvas.parentElement);
    updateReadout(readoutEl, hoverState, lapA, lapB);
    positionReadout(readoutEl, hoverState.screenX, hoverState.screenY, rect.width, rect.height);
    onUpdate?.(hoverState);
  }

  function buildLinkedHoverState() {
    if (linkedDistance == null) return null;
    const { lapA, lapB, transform } = getLapData();
    if (!lapA?.raw || !transform) return null;

    const nearest = sLookup(lapA.raw, linkedDistance);
    if (!nearest || !isFinite(nearest.x) || !isFinite(nearest.z)) return null;

    const sx = transform.toScreenX(nearest.x);
    const sy = transform.toScreenY(nearest.z);
    return makeHoverState(nearest, sx, sy, lapA, lapB);
  }

  function applyLinkedHoverIfIdle() {
    if (directPointerActive || isDragging) return;
    applyHoverState(buildLinkedHoverState());
  }

  function doUpdate() {
    if (!pendingEvent || isDragging) {
      hideHover();
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const sx = pendingEvent.clientX - rect.left;
    const sy = pendingEvent.clientY - rect.top;

    const { lapA, lapB, transform } = getLapData();
    if (!lapA || !transform) {
      hideHover();
      return;
    }

    const world = worldFromScreen(sx, sy, transform);
    const nearest = findNearest(grid, world.x, world.z);
    if (!nearest) {
      hideHover();
      return;
    }

    applyHoverState(makeHoverState(nearest, sx, sy, lapA, lapB));
  }

  function onPointerMove(e) {
    directPointerActive = true;
    if (isDragging) {
      hideHover();
      return;
    }
    pendingEvent = e;
    if (!rafId) {
      rafId = requestAnimationFrame(() => {
        rafId = null;
        doUpdate();
      });
    }
  }

  function onPointerLeave() {
    directPointerActive = false;
    pendingEvent = null;
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    applyLinkedHoverIfIdle();
  }

  function onPointerDown() {
    isDragging = true;
    directPointerActive = true;
    pendingEvent = null;
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    hideHover();
  }

  function onPointerUp() {
    isDragging = false;
  }

  function setLinkedDistance(s) {
    linkedDistance = s;
    applyLinkedHoverIfIdle();
  }

  function clearLinkedDistance() {
    linkedDistance = null;
    if (!directPointerActive) hideHover();
  }

  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerleave', onPointerLeave);
  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointerup', onPointerUp);
  canvas.addEventListener('pointercancel', onPointerUp);

  return {
    getState: () => hoverState,
    rebuild: build,
    setLinkedDistance,
    clearLinkedDistance,
    destroy: () => {
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerleave', onPointerLeave);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      if (rafId) cancelAnimationFrame(rafId);
      if (readoutEl) readoutEl.remove();
    },
  };
}
