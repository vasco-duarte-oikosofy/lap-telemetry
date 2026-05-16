#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Static track outline contract tests.
 *
 * Run: node scripts/test_static_track_outline_contract.js
 *
 * Verifies the Spa-Francorchamps outline JSON has the expected structure,
 * alignment metadata, and point arrays.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const outlinePath = path.join(ROOT, 'product', 'data', 'track-outlines', 'spa-francorchamps.json');

let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
  return cond;
}

const outline = JSON.parse(fs.readFileSync(outlinePath, 'utf8'));

// ── Schema version ──
assert(outline.schema_version === 1, 'schema_version is 1');

// ── Required fields ──
const requiredFields = [
  'source', 'track_name', 'sim_track_name', 'layout_name',
  'coordinate_system', 'units', 'alignment', 'visual_qa',
  'caveats', 'track_name_mapping', 'centerline', 'left_boundary', 'right_boundary'
];
for (const field of requiredFields) {
  assert(Object.prototype.hasOwnProperty.call(outline, field), `${field} is present`);
}

// ── Alignment metadata ──
assert(outline.coordinate_system === 'sim_xy', 'coordinate_system is sim_xy');
assert(outline.units === 'sim_units', 'units is sim_units');
assert(outline.alignment.method === 'manual_similarity_transform', 'alignment method');
assert(outline.alignment.scale === 0.998, 'alignment scale', String(outline.alignment.scale));
assert(outline.alignment.rotation_rad === 0.0004, 'alignment rotation', String(outline.alignment.rotation_rad));
assert(outline.alignment.translate_x === -164, 'alignment translate_x', String(outline.alignment.translate_x));
assert(outline.alignment.translate_y === 632, 'alignment translate_y', String(outline.alignment.translate_y));
assert(outline.alignment.reverse_point_order === true, 'alignment reverse_point_order');

// ── Track name mapping ──
assert(Array.isArray(outline.track_name_mapping.accepted_sim_track_names), 'accepted_sim_track_names is array');
assert(outline.track_name_mapping.accepted_sim_track_names.includes('circuit-de-spa-francorchamps-endurance'), 'sim track name found');
assert(outline.track_name_mapping.accepted_lmu_track_names.includes('Circuit de Spa-Francorchamps Endurance'), 'lmu track name found');

// ── Point arrays ──
function assertPoints(name, points) {
  assert(Array.isArray(points), `${name} is an array`);
  assert(points.length > 0, `${name} is non-empty`);
  // Check a sample of points for correct structure
  for (let i = 0; i < Math.min(points.length, 5); i++) {
    assert(typeof points[i] === 'object', `${name}[${i}] is object`);
    assert(Number.isFinite(points[i].x), `${name}[${i}].x is finite`);
    assert(Number.isFinite(points[i].y), `${name}[${i}].y is finite`);
  }
}

assertPoints('centerline', outline.centerline);
assertPoints('left_boundary', outline.left_boundary);
assertPoints('right_boundary', outline.right_boundary);
assert(outline.left_boundary.length === outline.centerline.length, 'left boundary length matches centerline', `${outline.left_boundary.length} vs ${outline.centerline.length}`);
assert(outline.right_boundary.length === outline.centerline.length, 'right boundary length matches centerline', `${outline.right_boundary.length} vs ${outline.centerline.length}`);

// ── Caveats ──
const caveatText = outline.caveats.join(' ').toLowerCase();
assert(caveatText.includes('approximation') || caveatText.includes('approximate'), 'caveats mention approximate');
assert(caveatText.includes('official fia') || caveatText.includes('not official'), 'caveats mention non-official');
assert(caveatText.includes('not authoritative'), 'caveats say not authoritative');

console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
if (failCount) throw new Error(`${failCount} assertions failed`);