// ── Text-only apex metrics panel rendering ──────────────────────────────────

import { apexAnnotationsByLayout, features } from './appState.js';
import { computeApexMetricsForSession } from './apexMetrics.js';

function slug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function layoutValue(sidecar) {
  return sidecar?.layout_id || sidecar?.layoutId || sidecar?.layout || 'default';
}

function trackValue(entry) {
  const sidecar = entry?.sidecar || {};
  return sidecar.track_id || sidecar.trackId || sidecar.track || sidecar.track_name || null;
}

function findMatchingAnnotations(entry) {
  const track = trackValue(entry);
  if (!track) return null;
  const layout = layoutValue(entry.sidecar || {});
  const trackSlug = slug(track);
  const layoutSlug = slug(layout);

  for (const annotations of apexAnnotationsByLayout.values()) {
    if (slug(annotations.track_id) === trackSlug && slug(annotations.layout_id) === layoutSlug) {
      return annotations;
    }
  }
  return null;
}

function formatMeters(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)} m` : '—';
}

function formatTiming(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  if (value > 0) return `late ${value.toFixed(2)} m`;
  if (value < 0) return `early ${Math.abs(value).toFixed(2)} m`;
  return 'exact 0.00 m';
}

function valueText(value) {
  if (value == null || value === '') return '—';
  return String(value);
}

function clearPanel(panel) {
  panel.replaceChildren();
}

function renderEmpty(panel, message) {
  clearPanel(panel);
  const label = document.createElement('div');
  label.className = 'panel-label';
  label.textContent = 'Apex metrics';
  const empty = document.createElement('div');
  empty.className = 'apex-metrics-empty';
  empty.textContent = message;
  panel.append(label, empty);
}

function lapLabel(sessionEntry, sessionSegIdx) {
  const seg = sessionEntry?.segments?.[sessionSegIdx];
  if (!seg) return 'Lap —';
  return `Lap ${sessionSegIdx + 1} (lap# ${seg.lapNum})`;
}

function renderTable(panel, metrics, selectedLapLabel) {
  clearPanel(panel);
  const label = document.createElement('div');
  label.className = 'panel-label';
  label.textContent = 'Apex metrics';

  const note = document.createElement('div');
  note.className = 'apex-metrics-note';
  note.textContent = `Showing selected session lap only: ${selectedLapLabel}; reference lap is not included.`;

  const table = document.createElement('table');
  table.className = 'apex-metrics-table';
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Corner</th><th>Lap</th><th>Apex distance</th><th>Timing</th><th>Surface</th><th>Terrain</th></tr>';
  const tbody = document.createElement('tbody');

  for (const metric of metrics) {
    const tr = document.createElement('tr');
    const cells = [
      metric.corner_name || metric.corner_id || '—',
      selectedLapLabel,
      formatMeters(metric.apex_distance_m),
      formatTiming(metric.apex_timing_error_m),
      valueText(metric.surface_type),
      valueText(metric.terrain_name),
    ];
    for (const text of cells) {
      const td = document.createElement('td');
      td.textContent = text;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }

  table.append(thead, tbody);
  panel.append(label, note, table);
}

export function renderApexMetricsPanel(sessionEntry, sessionSegIdx) {
  const panel = document.getElementById('apex-metrics-panel');
  if (!panel) return;
  if (!features.apexMetricsUi) {
    panel.style.display = 'none';
    clearPanel(panel);
    return;
  }

  panel.style.display = 'block';
  const annotations = findMatchingAnnotations(sessionEntry);
  if (!annotations) {
    renderEmpty(panel, 'No apex annotations for this track/layout');
    return;
  }

  const seg = sessionEntry?.segments?.[sessionSegIdx];
  const result = computeApexMetricsForSession({ data: sessionEntry?.data, segments: seg ? [seg] : [] }, annotations);
  if (result.status === 'unavailable') {
    renderEmpty(panel, 'Record a new session to capture track-edge channels');
    return;
  }
  if (result.status !== 'ok' || result.metrics.length === 0) {
    renderEmpty(panel, 'No apex metrics for this lap');
    return;
  }
  renderTable(panel, result.metrics, lapLabel(sessionEntry, sessionSegIdx));
}
