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
    if (err.code !== 'ENOENT') {
      // A corrupt existing file must not silently lose curated turns.
      throw new Error(`cannot read existing outline ${outlinePath}: ${err.message}`);
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
