// ── UI interaction module — event handlers, file loading ─────────────────────

// Re-export picker/session-list functions from pickers.js
export { rebuildPickers, updateCompareBtn, parsePickerValue,
         addSessionEntry, refreshSessionListBadges } from './pickers.js';

import { store, pendingSidecars, state, persistPanelOrder, DEFAULT_PANEL_ORDER } from './appState.js';
import { storeKey, fileStem, formatDuration, lapStatusBadges, formatPickLabel,
         shortVehicle, shortSetup, showError, clearError, setBadge,
         persistLapColours, LAP_COLOUR_DEFAULTS, loadPersistedColours, applyLapColour
       } from './utils.js';
import { readColumns, buildSegments, annotateSegments, resample,
         smoothLapTime, computeKeepIndices, PARTIAL_DIST_FRAC, PARTIAL_DUR_FRAC, ROLLING_DIST_M
       } from './pipeline.js';
import { rebuildPickers, updateCompareBtn, parsePickerValue,
         addSessionEntry, refreshSessionListBadges } from './pickers.js';
import { parseDeltabestCsv, buildDeltabestSidecar } from './dataTransforms.js';

// ── File loading ──────────────────────────────────────────────────────────────

// Pending sidecar JSONs keyed by stem (filename without extension).
// When the parquet for the same stem arrives, we attach the metadata.
// pendingSidecars imported from appState.js

async function loadDeltabestCsv(file) {
  const key = storeKey(file);
  if (store.has(key)) return;

  const badge = addSessionEntry(file.name, key, 'parsing…');
  setBadge(badge, 'loading', 'parsing…');

  try {
    const text = await file.text();
    const { data, segments, rowCount } = parseDeltabestCsv(text);
    const sidecar = buildDeltabestSidecar(rowCount);
    annotateSegments(segments, data.lap_distance_m, data.lap_time_s);

    store.set(key, {
      fileName: file.name,
      data,
      segments,
      hasSlip: false,
      hasSectors: false,
      sidecar,
      isDeltabest: true,
    });

    setBadge(badge, 'ok', `${rowCount} rows · TinyPedal deltabest`);
    rebuildPickers();
    document.getElementById('load-status').textContent = `${store.size} file(s) loaded`;
    document.getElementById('load-status').className = 'badge ok';
  } catch (e) {
    setBadge(badge, 'err', `csv: ${e.message.slice(0, 60)}`);
    console.error('deltabest csv error', e);
    showError(`Failed to parse ${file.name}: ${e.message}`);
  }
}

async function loadSidecar(file) {
  try {
    const text = await file.text();
    const sidecar = JSON.parse(text);
    const stem = fileStem(file.name);
    // If parquet already loaded for this stem, attach now.
    let attached = false;
    for (const [key, entry] of store) {
      if (fileStem(entry.fileName) === stem) {
        entry.sidecar = sidecar;
        attached = true;
        break;
      }
    }
    if (!attached) pendingSidecars.set(stem, sidecar);
    rebuildPickers();
    refreshSessionListBadges();
  } catch (e) {
    console.warn(`sidecar parse failed for ${file.name}: ${e.message}`);
  }
}

export async function loadFile(file, renderAll) {
  const lname = file.name.toLowerCase();
  if (lname.endsWith('.json')) {
    return loadSidecar(file);
  }
  if (lname.endsWith('.csv')) {
    return loadDeltabestCsv(file);
  }
  const key = storeKey(file);
  if (store.has(key)) return; // already loaded

  const badge = addSessionEntry(file.name, key, 'loading…');
  setBadge(badge, 'loading', 'loading…');

  try {
    const { data, missingCols } = await readColumns(file, [
      'lap_number', 'lap_time_s', 'lap_distance_m', 'speed_kph',
      'throttle_norm', 'brake_norm', 'engine_rpm', 'gear',
      'steering_norm', 'slip_angle_fl_deg', 'slip_angle_fr_deg',
      'last_sector_1_s', 'last_sector_2_s',
      'pos_x_m', 'pos_z_m',
      'abs_active', 'tc_active',
    ]);
    const segments = buildSegments(data.lap_number);
    annotateSegments(segments, data.lap_distance_m, data.lap_time_s);

    const hasSlip    = data.slip_angle_fl_deg.length > 0;
    const hasSectors = data.last_sector_1_s.length > 0;

    // If a sidecar for this parquet was loaded earlier, attach it now.
    const stem = fileStem(file.name);
    const sidecar = pendingSidecars.get(stem) || null;
    if (sidecar) pendingSidecars.delete(stem);

    store.set(key, {
      fileName: file.name,
      data,
      segments,
      hasSlip,
      hasSectors,
      sidecar,
    });

    const expectedOptional = new Set([
      'last_sector_1_s', 'last_sector_2_s',
      'slip_angle_fl_deg', 'slip_angle_fr_deg',
      'abs_active', 'tc_active',
    ]);
    const missing = missingCols.filter(c => !expectedOptional.has(c));
    const metaSuffix = sidecar ? ` · ${shortVehicle(sidecar.vehicle_name)}` : '';
    if (missing.length) {
      setBadge(badge, 'ok', `${data.lap_number.length} rows · ${segments.length} laps${metaSuffix} (⚠ missing: ${missing.join(',')})`);
    } else {
      setBadge(badge, 'ok', `${data.lap_number.length} rows · ${segments.length} laps${metaSuffix}`);
    }

    rebuildPickers();
    document.getElementById('load-status').textContent = `${store.size} file(s) loaded`;
    document.getElementById('load-status').className = 'badge ok';
  } catch (e) {
    setBadge(badge, 'err', `error: ${e.message.slice(0, 60)}`);
    console.error('load error', e);
    showError(`Failed to load ${file.name}: ${e.message}`);
  }
}

// ── F9: drag reorder — event delegation on #panels ───────────────────────────

export function disarmAllPanels() {
  document.querySelectorAll('#panels .panel-wrap[draggable="true"]').forEach(el => el.removeAttribute('draggable'));
}

export function setupPanelDragHandlers(renderAll) {
  const panelsEl = document.getElementById('panels');

  // Panels are non-draggable by default so click-drag on the plot area falls
  // through to the F2 zoom handler. Gripping the ⠿ handle arms the panel for
  // HTML5 drag; dragend / mouseup (no-drag click) disarms it.
  panelsEl.addEventListener('mousedown', e => {
    const handle = e.target.closest('.drag-handle');
    if (!handle) return;
    const wrap = handle.closest('.panel-wrap');
    if (wrap) wrap.setAttribute('draggable', 'true');
  });

  panelsEl.addEventListener('mouseup', () => {
    // Catches the case where the user clicked the handle but didn't drag.
    disarmAllPanels();
  });

  panelsEl.addEventListener('dragstart', e => {
    const wrap = e.target.closest('.panel-wrap[draggable="true"]');
    if (!wrap) return;
    state.dragId = wrap.dataset.panelId;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', state.dragId);
  });

  panelsEl.addEventListener('dragover', e => {
    if (!state.dragId) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const wrap = e.target.closest('.panel-wrap');
    if (!wrap) return;
    document.querySelectorAll('#panels .panel-wrap.drag-over').forEach(el => el.classList.remove('drag-over'));
    wrap.classList.add('drag-over');
  });

  panelsEl.addEventListener('dragleave', e => {
    const wrap = e.target.closest('.panel-wrap.drag-over');
    if (wrap && !wrap.contains(e.relatedTarget)) wrap.classList.remove('drag-over');
  });

  panelsEl.addEventListener('drop', e => {
    if (!state.dragId) return;
    e.preventDefault();
    document.querySelectorAll('#panels .panel-wrap.drag-over').forEach(el => el.classList.remove('drag-over'));
    const targetWrap = e.target.closest('.panel-wrap');
    if (!targetWrap) return;
    const targetId = targetWrap.dataset.panelId;
    if (targetId === state.dragId) return;
    
    // Import panelOrder from appState dynamically to avoid circular ref
    import('./appState.js').then(({ panelOrder }) => {
      const from = panelOrder.indexOf(state.dragId);
      const to   = panelOrder.indexOf(targetId);
      if (from < 0 || to < 0) return;
      panelOrder.splice(from, 1);
      panelOrder.splice(to, 0, state.dragId);
      persistPanelOrder([...panelOrder]);
      if (state.currentRenderParams && renderAll) renderAll(...state.currentRenderParams);
      state.dragId = null;
    });
  });

  panelsEl.addEventListener('dragend', () => {
    document.querySelectorAll('#panels .panel-wrap.drag-over').forEach(el => el.classList.remove('drag-over'));
    disarmAllPanels();
    state.dragId = null;
  });

  // Order reset button
  const orderReset = document.getElementById('order-reset');
  if (orderReset) {
    orderReset.addEventListener('click', () => {
      import('./appState.js').then(({ panelOrder, DEFAULT_PANEL_ORDER }) => {
        panelOrder.splice(0, panelOrder.length, ...DEFAULT_PANEL_ORDER);
        persistPanelOrder([...panelOrder]);
        if (state.currentRenderParams && renderAll) renderAll(...state.currentRenderParams);
      });
    });
  }
}

// ── Event wiring ──────────────────────────────────────────────────────────────

export function initUI(renderAll) {
  // Load button
  document.getElementById('load-btn').addEventListener('click', () => {
    document.getElementById('file-input').click();
  });

  // File input - load all files in parallel (sidecar+parquet may arrive together)
  document.getElementById('file-input').addEventListener('change', async e => {
    clearError();
    const files = Array.from(e.target.files || []);
    await Promise.all(files.map(f => loadFile(f, renderAll)));
    e.target.value = '';
  });

  // Compare button
  document.getElementById('compare-btn').addEventListener('click', () => {
    clearError();
    const sp = parsePickerValue(document.getElementById('session-picker').value);
    const rp = parsePickerValue(document.getElementById('ref-picker').value);
    if (!sp || !rp) return;

    const sEntry = store.get(sp.key);
    const rEntry = store.get(rp.key);
    if (!sEntry || !rEntry) return;

    state.currentRenderParams = [sEntry, sp.segIdx, rEntry, rp.segIdx];
    renderAll(sEntry, sp.segIdx, rEntry, rp.segIdx);
  });

  // Auto-compare on picker change if both are selected
  ['session-picker', 'ref-picker'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
      updateCompareBtn();
      const sp = parsePickerValue(document.getElementById('session-picker').value);
      const rp = parsePickerValue(document.getElementById('ref-picker').value);
      if (sp && rp) {
        const sEntry = store.get(sp.key);
        const rEntry = store.get(rp.key);
        if (sEntry && rEntry) {
          state.currentRenderParams = [sEntry, sp.segIdx, rEntry, rp.segIdx];
          renderAll(sEntry, sp.segIdx, rEntry, rp.segIdx);
        }
      }
    });
  });

  // Heatmap mode change - state update only (caller handles re-render)
  document.getElementById('map-mode').addEventListener('change', e => {
    import('./appState.js').then(({ setCurrentMapMode }) => {
      setCurrentMapMode(e.target.value);
    });
  });

  // Lap colour pickers (M6 F1) - state changes only, caller handles visual update
  const colourSessionInput = document.getElementById('colour-session');
  const colourRefInput     = document.getElementById('colour-ref');
  const colourResetBtn     = document.getElementById('colour-reset');

  function syncColourInputs(colours) {
    colourSessionInput.value = colours.session;
    colourRefInput.value     = colours.ref;
  }

  colourSessionInput.addEventListener('input', e => {
    const colours = { session: e.target.value, ref: colourRefInput.value };
    applyLapColour('session', colours.session);
    applyLapColour('ref',     colours.ref);
    persistLapColours(colours);
  });
  colourRefInput.addEventListener('input', e => {
    const colours = { session: colourSessionInput.value, ref: e.target.value };
    applyLapColour('session', colours.session);
    applyLapColour('ref',     colours.ref);
    persistLapColours(colours);
  });
  colourResetBtn.addEventListener('click', () => {
    applyLapColour('session', LAP_COLOUR_DEFAULTS.session);
    applyLapColour('ref',     LAP_COLOUR_DEFAULTS.ref);
    syncColourInputs(LAP_COLOUR_DEFAULTS);
    persistLapColours(LAP_COLOUR_DEFAULTS);
  });

  // Load persisted colours and sync inputs
  const initialColours = loadPersistedColours() || { ...LAP_COLOUR_DEFAULTS };
  applyLapColour('session', initialColours.session);
  applyLapColour('ref',     initialColours.ref);
  syncColourInputs(initialColours);

  // Panel drag handlers
  setupPanelDragHandlers(renderAll);
}
