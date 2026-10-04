#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Unit tests for inferTrackNameFromFileName — the fallback that resolves a
 * session's track when no sidecar JSON is loaded (and therefore the static
 * track outline lookup).
 *
 * Run: node dev/scripts/test_track_name_inference.js
 */

const path = require('path');
const { pathToFileURL } = require('url');

let pass = 0, fail = 0;
function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

const ROOT = path.resolve(__dirname, '..', '..');
const moduleUrl = pathToFileURL(path.join(ROOT, 'product', 'web', 'js', 'trackNameInference.js')).href;

(async () => {
  const { inferTrackNameFromFileName } = await import(moduleUrl);

  // Legacy recorder names: session_<UTC>_<track>_lmu.parquet
  ok(inferTrackNameFromFileName('session_20260512T140000Z_spa-francorchamps_lmu.parquet') === 'Spa Francorchamps',
    'legacy _lmu.parquet name resolves');
  ok(inferTrackNameFromFileName('session_20260521T175211Z_circuit-of-the-americas_lmu.parquet') === 'Circuit Of The Americas',
    'legacy multi-word name resolves');

  // Non-matching inputs
  ok(inferTrackNameFromFileName(null) === null, 'null filename returns null');
  ok(inferTrackNameFromFileName('random.parquet') === null, 'non-session filename returns null');

  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) process.exit(1);
  console.log('  ✔ All assertions passed');
})().catch(err => { console.error(err); process.exit(1); });
