#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const sourcePath = path.join(ROOT, 'product', 'data', 'track-outlines', 'spa-francorchamps.json');
const runtimePath = path.join(ROOT, 'product', 'web', 'js', 'staticSpaOutlineData.js');

(async () => {
  const source = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
  const { SPA_STATIC_OUTLINE } = await import(`${runtimePath}?t=${Date.now()}`);
  assert.deepStrictEqual(SPA_STATIC_OUTLINE, source, 'runtime Spa outline data matches product/data/track-outlines source artifact');

  const modulePath = path.join(ROOT, 'product', 'web', 'js', 'staticTrackOutline.js');
  const { getSpaStaticOutline, renderStaticTrackOutlineSvg } = await import(`${modulePath}?t=${Date.now()}`);
  const outline = getSpaStaticOutline();
  assert.strictEqual(outline.schema_version, 1, 'runtime outline exposes schema v1');

  const transform = { toMapX: x => x / 10, toMapZ: y => 250 - y / 10 };
  const svg = renderStaticTrackOutlineSvg(outline, transform);
  assert(svg.includes('data-static-track-outline="spa-francorchamps"'), 'static outline group is identifiable');
  assert(svg.includes('data-static-outline-part="left_boundary"'), 'left boundary is rendered');
  assert(svg.includes('data-static-outline-part="right_boundary"'), 'right boundary is rendered');
  assert(svg.includes('data-static-outline-part="centerline"'), 'centerline is rendered');
  assert(svg.indexOf('left_boundary') < svg.indexOf('centerline'), 'boundaries render before centerline in the static group');

  console.log('static outline runtime rendering test passed');
})().catch(err => {
  console.error(err);
  process.exit(1);
});
