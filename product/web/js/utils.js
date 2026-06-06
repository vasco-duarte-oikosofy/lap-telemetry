// ── Pure utility helpers — leaf module, no internal dependencies ─────────────

// ── Key helpers ───────────────────────────────────────────────────────────────

export function storeKey(file) {
  return `${file.name}::${file.size}`;
}

export function fileStem(name) {
  const i = name.lastIndexOf('.');
  return i > 0 ? name.slice(0, i) : name;
}

// ── Formatting helpers ────────────────────────────────────────────────────────

export function formatDuration(s) {
  const m = Math.floor(s / 60);
  const ss = (s % 60).toFixed(3).padStart(6, '0');
  return `${m}:${ss}`;
}

export function lapStatusBadges(seg) {
  const tags = [];
  if (seg.rolling) tags.push('rolling');
  if (seg.partial) tags.push('partial');
  return tags.length ? ` (${tags.join(', ')})` : '';
}

export function formatPickLabel(entry, segIdx) {
  const seg = entry.segments[segIdx];
  const dur = seg.duration || 0;
  const sc = entry.sidecar;
  const vehicleLabel = entry.isDeltabest ? sc?.vehicle_name : (sc ? shortVehicle(sc.vehicle_name) : null);
  const meta = sc
    ? ` · ${vehicleLabel}${sc.setup_file_guess ? ` · ${shortSetup(sc.setup_file_guess)}` : ''}`
    : '';
  const star = seg.fastest ? ' ★' : '';
  return `${entry.fileName} / Lap ${segIdx + 1} #${seg.lapNum} ${formatDuration(dur)}${lapStatusBadges(seg)}${star}${meta}`;
}

export function shortVehicle(name) {
  if (!name) return 'unknown vehicle';
  // "WTM by Rinaldi Racing 2025 #12:ELMS" → "WTM #12:ELMS" (keep distinguishing parts)
  const colon = name.indexOf(':');
  const tail = colon >= 0 ? name.slice(colon) : '';
  const head = (colon >= 0 ? name.slice(0, colon) : name).trim();
  // Take first word + any "#N" token
  const m = head.match(/^(\S+).*?(\#\d+)?\s*$/);
  return ((m && m[1]) || head.slice(0, 20)) + (m && m[2] ? ` ${m[2]}` : '') + tail;
}

export function shortSetup(name) {
  if (!name) return null;
  return name.replace(/\.svm$/i, '');
}

// ── DOM / error helpers ───────────────────────────────────────────────────────

export function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.classList.add('visible');
}

export function clearError() {
  document.getElementById('error-msg').classList.remove('visible');
}

export function setBadge(el, cls, text) {
  el.className = 'badge' + (cls ? ` ${cls}` : '');
  el.textContent = text;
}

// ── Persistent lap colours (M6) ───────────────────────────────────────────────

export const LAP_COLOUR_DEFAULTS = { session: '#4fc3f7', ref: '#ff9800' };
export const LAP_COLOUR_LS_KEY   = 'lap-telemetry.colours.v1';
export const HEX_RE = /^#[0-9a-fA-F]{6}$/;

export function applyLapColour(slot, value) {
  document.documentElement.style.setProperty(`--${slot}`, value);
}

export function persistLapColours(colours) {
  try {
    if (colours.session === LAP_COLOUR_DEFAULTS.session && colours.ref === LAP_COLOUR_DEFAULTS.ref) {
      localStorage.removeItem(LAP_COLOUR_LS_KEY);
    } else {
      localStorage.setItem(LAP_COLOUR_LS_KEY, JSON.stringify(colours));
    }
  } catch { /* localStorage unavailable */ }
}

export function loadPersistedColours() {
  try {
    const raw = localStorage.getItem(LAP_COLOUR_LS_KEY);
    if (!raw) return null;
    const c = JSON.parse(raw);
    if (!HEX_RE.test(c.session) || !HEX_RE.test(c.ref)) return null;
    return { session: c.session, ref: c.ref };
  } catch { return null; }
}

// ── Persistent zoom (M6) ──────────────────────────────────────────────────────

export const ZOOM_LS_KEY = 'lap-telemetry.zoom.v1';

export function persistZoom(zoom, maxDist) {
  try {
    if (zoom.start === 0 && zoom.end >= maxDist) {
      localStorage.removeItem(ZOOM_LS_KEY);  // full-range = no persisted state
    } else {
      localStorage.setItem(ZOOM_LS_KEY, JSON.stringify({ start: zoom.start, end: zoom.end }));
    }
  } catch { /* localStorage unavailable */ }
}

export function loadPersistedZoom(maxDist) {
  try {
    const raw = localStorage.getItem(ZOOM_LS_KEY);
    if (!raw) return null;
    const z = JSON.parse(raw);
    if (typeof z.start !== 'number' || typeof z.end !== 'number') return null;
    if (z.start < 0 || z.end > maxDist || z.end - z.start < 10) return null;  // out of range / nonsense
    return { start: z.start, end: z.end };
  } catch { return null; }
}
