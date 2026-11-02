// @parallel true
'use strict';
/**
 * Guard: curated names must stay valid UTF-8, and the guarded pipeline must
 * never read curated JSON with the platform's default encoding.
 *
 * Real failure this prevents (2026-11-02, slice 41): on Windows the model
 * updater called `read_text()` with no encoding, so Python decoded the UTF-8
 * model as cp1252. Refreshing Interlagos rewrote "Junção" as the mojibake
 * "\u00c3\u00a7"... and the file was committed-ready with corrupted curation.
 * macOS/Linux default to UTF-8, so the same code is silently fine there — a
 * static rule is the only guard that holds on every platform.
 *
 * Note: the Python test wrappers force PYTHONUTF8=1 (docs/TESTING_LESSONS L17),
 * which also hides this class of bug, so round-trip tests cannot catch it.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
let pass = 0;
let fail = 0;
function ok(condition, label, detail = '') {
  if (condition) {
    pass += 1;
    console.log(`  [PASS] ${label}`);
  } else {
    fail += 1;
    console.log(`  [FAIL] ${label}${detail ? ` — ${detail}` : ''}`);
  }
}

const MOJIBAKE = ['\u00c3\u00a7', '\u00c3\u00a9', '\u00e2\u0080\u0099', '\ufffd'];
const CURATED_DIRS = [
  'product/data/track-coaching',
  'product/data/track-outlines',
];

function curatedFiles() {
  const files = ['product/data/vehicle_catalog.json'];
  for (const dir of CURATED_DIRS) {
    for (const name of fs.readdirSync(path.join(ROOT, dir))) {
      if (name.endsWith('.json')) files.push(path.join(dir, name));
    }
  }
  return files;
}

const files = curatedFiles();
const corrupted = [];
const undecodable = [];
let nonAscii = 0;
for (const rel of files) {
  const raw = fs.readFileSync(path.join(ROOT, rel));
  let text;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(raw);
  } catch {
    undecodable.push(rel);
    continue;
  }
  if (Buffer.from(text, 'utf8').compare(raw) !== 0) undecodable.push(rel);
  if (MOJIBAKE.some((marker) => text.includes(marker))) corrupted.push(rel);
  if (/[^\x00-\x7f]/.test(text)) nonAscii += 1;
}

ok(undecodable.length === 0, `${files.length} curated JSON files decode as strict UTF-8`, undecodable.join(', '));
ok(corrupted.length === 0, 'no curated file contains double-encoded UTF-8 mojibake', corrupted.join(', '));
ok(nonAscii > 0, `curated accents exist and stay intact (${nonAscii} files with non-ASCII names)`);

// Static rule: guarded pipeline scripts must name their encoding on text I/O.
const GUARDED = [
  'dev/scripts/update_reference_and_coaching_model.py',
  'dev/scripts/generate_track_coaching_model_from_reference.py',
  'dev/scripts/export_fastest_reference_laps.py',
  'dev/scripts/validate_reference_laps.py',
  'dev/scripts/bake_outline_turns.py',
  'dev/scripts/register_outline.py',
  'dev/scripts/export_turn_labels_for_tinypedal.py',
  'dev/scripts/trajectory_to_outline.py',
  'dev/scripts/average_trajectory_outline.py',
];
const BINARY = /['"][rw]b['"]/;
const offenders = [];
for (const rel of GUARDED) {
  const file = path.join(ROOT, rel);
  if (!fs.existsSync(file)) continue;
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, index) => {
    const code = line.split('#')[0];
    const bad =
      /\.read_text\(\s*\)/.test(code) ||
      /\.write_text\([^)]*\)/.test(code) && !/encoding=/.test(code) ||
      /\bopen\(/.test(code) && !/encoding=/.test(code) && !BINARY.test(code);
    if (bad) offenders.push(`${rel}:${index + 1}`);
  });
}
ok(offenders.length === 0,
  'guarded pipeline scripts pass an explicit encoding on text I/O',
  offenders.join(', '));

console.log(`\n  ${pass}/${pass + fail} assertions passed`);
if (fail > 0) process.exitCode = 1;
