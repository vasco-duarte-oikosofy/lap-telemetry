// ── Picker population and session list DOM projection ─────────────────────────

import { store } from './appState.js';
import { storeKey, fileStem, formatDuration, lapStatusBadges, formatPickLabel,
         shortVehicle, shortSetup, setBadge } from './utils.js';

export function rebuildPickers() {
  const sessionPicker = document.getElementById('session-picker');
  const refPicker     = document.getElementById('ref-picker');
  const prevSession   = sessionPicker.value;
  const prevRef       = refPicker.value;

  const optHtml = [];
  let hasOptions = false;
  for (const [key, entry] of store) {
    const total = entry.segments.length;
    // ★ assignment is precomputed by annotateSegments() at load time, after
    // partial/rolling have been resolved. Read the flag rather than recomputing.

    const sc = entry.sidecar;
    const vehicleLabel = entry.isDeltabest ? sc?.vehicle_name : (sc ? shortVehicle(sc.vehicle_name) : '');
    const groupMeta = sc
      ? ` — ${vehicleLabel}${sc.setup_file_guess ? ` (${shortSetup(sc.setup_file_guess)})` : ''}`
      : '';
    const groupLabel = `${entry.fileName}${groupMeta}`;
    let groupHtml = `<optgroup label="${groupLabel}">`;
    for (let i = 0; i < total; i++) {
      const seg = entry.segments[i];
      const lapTimes = entry.data.lap_time_s;
      const sliceTimes = lapTimes.slice(seg.start, seg.end);
      const dur = sliceTimes.length ? sliceTimes.reduce((a, b) => b > a ? b : a, -Infinity) : 0;

      let label = `  Lap ${i + 1}  (lap# ${seg.lapNum})  ${formatDuration(dur)}`;
      label += lapStatusBadges(seg);
      if (seg.fastest) label += '  ★';

      const valStr = `${key}::${i}`;
      groupHtml += `<option value="${valStr}">${label}</option>`;
      hasOptions = true;
    }
    groupHtml += '</optgroup>';
    optHtml.push(groupHtml);
  }

  const placeholder = '<option value="">— load a session file —</option>';
  const inner = hasOptions ? optHtml.join('') : placeholder;
  sessionPicker.innerHTML = inner;
  refPicker.innerHTML     = inner;

  if (hasOptions) {
    sessionPicker.disabled = false;
    refPicker.disabled     = false;
    // Restore previous selection if still valid
    if (prevSession && sessionPicker.querySelector(`option[value="${prevSession}"]`))
      sessionPicker.value = prevSession;
    if (prevRef && refPicker.querySelector(`option[value="${prevRef}"]`))
      refPicker.value = prevRef;
  } else {
    sessionPicker.disabled = true;
    refPicker.disabled     = true;
  }
  updateCompareBtn();
}

export function updateCompareBtn() {
  const sp = document.getElementById('session-picker');
  const rp = document.getElementById('ref-picker');
  document.getElementById('compare-btn').disabled = !sp.value || !rp.value;
}

export function parsePickerValue(val) {
  if (!val) return null;
  const lastSep = val.lastIndexOf('::');
  if (lastSep < 0) return null;
  const key    = val.slice(0, lastSep);
  const segIdx = parseInt(val.slice(lastSep + 2), 10);
  return { key, segIdx };
}

export function addSessionEntry(name, key, statusText) {
  const list = document.getElementById('session-list');
  const entry = document.createElement('div');
  entry.className = 'session-entry';
  entry.dataset.key = key;
  entry.innerHTML = `
    <span class="fname" title="${name}">${name}</span>
    <span class="badge loading" id="badge-${CSS.escape(key)}">${statusText}</span>
    <button class="remove-btn" title="Remove" aria-label="Remove">×</button>
  `;
  entry.querySelector('.remove-btn').addEventListener('click', () => {
    store.delete(key);
    entry.remove();
    rebuildPickers();
    const count = store.size;
    const ls = document.getElementById('load-status');
    ls.textContent = count ? `${count} file(s) loaded` : 'no files loaded';
    ls.className = count ? 'badge ok' : 'badge';
  });
  list.appendChild(entry);
  return document.getElementById(`badge-${CSS.escape(key)}`);
}

export function refreshSessionListBadges() {
  for (const [key, entry] of store) {
    const badge = document.getElementById(`badge-${CSS.escape(key)}`);
    if (!badge) continue;
    const meta = entry.sidecar ? ` · ${shortVehicle(entry.sidecar.vehicle_name)}` : '';
    const text = `${entry.data.lap_number.length} rows · ${entry.segments.length} laps${meta}`;
    setBadge(badge, 'ok', text);
  }
}
