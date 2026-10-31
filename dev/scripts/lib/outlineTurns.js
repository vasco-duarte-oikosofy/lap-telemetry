'use strict';

/**
 * Preserve curated turn labels across outline regeneration.
 *
 * The `turns` block in product/data/track-outlines/<slug>.json is hand-curated
 * data (see docs/specs/MAP_TURN_NAMES.md). Every script that rewrites an
 * outline JSON must carry an existing `turns` block over, exactly like the
 * coaching-model updaters must never drop curated corner names (bug 24).
 *
 * Usage in a writer:
 *
 *   const { withPreservedTurns } = require('./lib/outlineTurns');
 *   await fs.writeFile(outPath, JSON.stringify(withPreservedTurns(outline, outPath), null, 2) + '\n');
 */

const fs = require('fs');

/** Read `turns` from an outline JSON already on disk, or null. */
function readExistingTurns(outlinePath) {
  try {
    const parsed = JSON.parse(fs.readFileSync(outlinePath, 'utf8'));
    if (Array.isArray(parsed.turns) && parsed.turns.length > 0) return parsed.turns;
  } catch (err) {
    // A missing file is normal. A file that is not valid JSON cannot carry
    // curated turns (e.g. a sentinel written by a test, or a half-written
    // file), so there is nothing to preserve: warn, do not fail the write.
    if (err.code !== 'ENOENT') {
      console.warn(`[outline-turns] ${outlinePath} is not readable JSON (${err.message}); nothing to preserve`);
    }
  }
  return null;
}

/**
 * Return `nextOutline` with curated turns carried over from the file it is
 * about to replace. Fresh turns in `nextOutline` win (that is what the bake
 * tool produces).
 */
function withPreservedTurns(nextOutline, outlinePath) {
  if (Array.isArray(nextOutline.turns) && nextOutline.turns.length > 0) return nextOutline;
  const prior = readExistingTurns(outlinePath);
  if (prior) {
    nextOutline.turns = prior;
    console.log(`[outline-turns] preserved ${prior.length} curated turns -> ${outlinePath}`);
  }
  return nextOutline;
}

module.exports = { readExistingTurns, withPreservedTurns };
