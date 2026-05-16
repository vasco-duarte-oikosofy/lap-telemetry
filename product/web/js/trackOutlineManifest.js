// ── Track outline manifest ────────────────────────────────────────────────
// Maps canonical sim track name slugs to their static outline data modules.
// The outline lookup uses the session sidecar's `track` field,
// slugified to match keys here.
//
// Adding a new track:
// 1. Generate the outline JSON via scripts/auto_align_outline.js or prepare_all_outlines.js
// 2. Visual QA with tools/manual_outline_align.html
// 3. Run: node scripts/generate_outline_module.js data/track-outlines/<slug>.json
// 4. Import the new module here and add entries to OUTLINES map

import { SPA_STATIC_OUTLINE } from './staticSpaOutlineData.js';
import { CIRCUIT_BARCELONA_STATIC_OUTLINE } from './staticCircuitBarcelonaOutlineData.js';
import { BAHRAIN_OUTLINE_STATIC_OUTLINE } from './staticBahrain_outlineOutlineData.js';
import { FUJI_SPEEDWAY_OUTLINE_STATIC_OUTLINE } from './staticFujiSpeedway_outlineOutlineData.js';

// slug normalization: lowercase, collapse whitespace to single dash, strip non-alnum/dash
function slugify(name) {
  return String(name || '').toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

const OUTLINES = new Map([
  // Spa (works for both regular and endurance layouts in LMU)
  ['circuit-de-spa-francorchamps', SPA_STATIC_OUTLINE],
  ['circuit-de-spa-francorchamps-endurance', SPA_STATIC_OUTLINE],
  ['spa-francorchamps', SPA_STATIC_OUTLINE],
  // Barcelona-Catalunya
  ['circuit-de-barcelona', CIRCUIT_BARCELONA_STATIC_OUTLINE],
  ['barcelona-catalunya', CIRCUIT_BARCELONA_STATIC_OUTLINE],
  ['catalunya', CIRCUIT_BARCELONA_STATIC_OUTLINE],
  // Bahrain International Circuit
  ['bahrain-international-circuit', BAHRAIN_OUTLINE_STATIC_OUTLINE],
  ['bahrain', BAHRAIN_OUTLINE_STATIC_OUTLINE],
  // Fuji Speedway
  ['fuji-speedway', FUJI_SPEEDWAY_OUTLINE_STATIC_OUTLINE],
  ['fuji', FUJI_SPEEDWAY_OUTLINE_STATIC_OUTLINE],
]);

/**
 * Look up a static track outline by sim session track name.
 * Returns null if no outline is available for the given track.
 * @param {string} trackName - session sidecar `track` field (e.g. "Circuit de Barcelona")
 * @returns {Object|null} schema v1 outline or null
 */
export function findOutlineByTrackName(trackName) {
  if (!trackName) return null;
  const slug = slugify(trackName);
  return OUTLINES.get(slug) || null;
}

/**
 * Return all track slugs that have outlines.
 * Useful for UI display or debugging.
 */
export function availableOutlineTracks() {
  return [...new Set(OUTLINES.values())].map(o => o.sim_track_name || o.track_name);
}

export { validateStaticOutline, drawStaticTrackOutline, renderStaticTrackOutlineSvg } from './staticTrackOutline.js';