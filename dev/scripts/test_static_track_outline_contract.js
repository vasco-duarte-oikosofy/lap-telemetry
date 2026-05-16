#!/usr/bin/env node
'use strict';
// @parallel true

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const outlinePath = path.join(__dirname, '..', '..', 'product', 'data', 'track-outlines', 'spa-francorchamps.json');
const outline = JSON.parse(fs.readFileSync(outlinePath, 'utf8'));

assert.strictEqual(outline.schema_version, 1, 'schema_version is 1');

for (const field of [
  'source',
  'track_name',
  'sim_track_name',
  'layout_name',
  'coordinate_system',
  'units',
  'alignment',
  'visual_qa',
  'caveats',
  'track_name_mapping',
  'centerline',
  'left_boundary',
  'right_boundary'
]) {
  assert.ok(Object.prototype.hasOwnProperty.call(outline, field), `${field} is present`);
}

assert.strictEqual(outline.coordinate_system, 'sim_xy');
assert.strictEqual(outline.units, 'sim_units');
assert.strictEqual(outline.alignment.method, 'manual_similarity_transform');
assert.strictEqual(outline.alignment.scale, 0.998);
assert.strictEqual(outline.alignment.rotation_rad, 0.0004);
assert.strictEqual(outline.alignment.translate_x, -164);
assert.strictEqual(outline.alignment.translate_y, 632);
assert.strictEqual(outline.alignment.reverse_point_order, true);

assert.ok(Array.isArray(outline.track_name_mapping.accepted_sim_track_names));
assert.ok(outline.track_name_mapping.accepted_sim_track_names.includes('circuit-de-spa-francorchamps-endurance'));
assert.ok(outline.track_name_mapping.accepted_lmu_track_names.includes('Circuit de Spa-Francorchamps Endurance'));

function assertPoints(name, points) {
  assert.ok(Array.isArray(points), `${name} is an array`);
  assert.ok(points.length > 0, `${name} is non-empty`);
  for (const point of points) {
    assert.strictEqual(typeof point, 'object', `${name} point is object`);
    assert.ok(Number.isFinite(point.x), `${name} x is finite`);
    assert.ok(Number.isFinite(point.y), `${name} y is finite`);
  }
}

assertPoints('centerline', outline.centerline);
assertPoints('left_boundary', outline.left_boundary);
assertPoints('right_boundary', outline.right_boundary);
assert.strictEqual(outline.left_boundary.length, outline.centerline.length, 'left boundary length matches centerline');
assert.strictEqual(outline.right_boundary.length, outline.centerline.length, 'right boundary length matches centerline');

const caveatText = outline.caveats.join(' ').toLowerCase();
assert.ok(caveatText.includes('approximation') || caveatText.includes('approximate'), 'caveats say widths are approximate');
assert.ok(caveatText.includes('official fia') || caveatText.includes('not official'), 'caveats say geometry is non-official');
assert.ok(caveatText.includes('not authoritative'), 'caveats say not authoritative');

console.log(`static track outline contract ok: ${outline.centerline.length} points`);
