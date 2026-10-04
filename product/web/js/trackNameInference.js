// ── Track name inference from session file names ─────────────────────────────
// Fallback used when a session's sidecar JSON is not loaded. The LMU recorder
// names files session_<UTC>_<track-slug>_lmu.<ext> (older) or
// session_<UTC>_<track-slug>_lmu_<session-type>.<ext> (practice/quali/race).

/**
 * Infer a track name from a session file name.
 * e.g. "session_20260512T140000Z_spa-francorchamps_lmu.parquet"
 *      → "Spa Francorchamps" (capitalized dash-separated parts after the
 *        timestamp, before the `_lmu` suffix).
 * @param {string} fileName
 * @returns {string|null}
 */
export function inferTrackNameFromFileName(fileName) {
  if (!fileName) return null;
  const match = fileName.match(/_\d{8}T\d{6}Z_(.+)_lmu\./i);
  if (!match) return null;
  const slug = match[1]; // e.g. "spa-francorchamps" or "circuit-de-barcelona"
  return slug.split('-').map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');
}
