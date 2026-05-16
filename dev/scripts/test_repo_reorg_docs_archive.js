#!/usr/bin/env node
'use strict';
// @parallel true

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..', '..');

function exists(relativePath) {
  return fs.existsSync(path.join(root, relativePath));
}

function assertExists(relativePath) {
  assert.ok(exists(relativePath), `${relativePath} exists`);
  console.log(`[PASS] ${relativePath} exists`);
}

function assertAbsent(relativePath) {
  assert.ok(!exists(relativePath), `${relativePath} moved from repository root`);
  console.log(`[PASS] ${relativePath} moved from repository root`);
}

const stableDocs = [
  'ARCHITECTURE.md',
  'DESIGN.md',
  'RENDER_DESIGN.md',
  'SETUP.md',
  'TESTING_LESSONS.md',
  'TEST_FIX_STATUS.md',
  'NEXT_STEPS.md',
  'track-heatmap-spec.md',
  'specs/MULTI_TRACK_TUMFTM_OUTLINE_PIPELINE.md',
  'specs/TRACK_OUTLINE_APEX_DISTANCE.md',
  'specs/TUMFTM_BASED_TRACK_MAP_OUTLINE_GENERATION_BY_HAND.md',
];

const archivedPlans = [
  'F1F2-handoff-prompt.md',
  'F1F2-plan.md',
  'F8F9F10F11-handoff-prompt.md',
  'M4-handoff-prompt.md',
  'M6-handoff-prompt.md',
  'm2-plan.md',
  'm3-plan.md',
  'm4-plan.md',
  'm5-plan.md',
  'm6-plan.md',
  'rca-deltat-endoflap-blowup.md',
  'rca-deltat-phantom-error.md',
  'track-heatmap-phase0-handoff.md',
  'web-refactor-plan.md',
  'web-refactor-step6-handoff.md',
  'web-refactor-step6-handoff-improvements.md',
  'web-refactor-step7-handoff.md',
  'web-refactor-step8-handoff.md',
  'web-refactor-step9-handoff.md',
  'web-refactor-step10-handoff.md',
  'archive/M3-handoff-prompt.md',
  'archive/f8-f11-plan.md',
];

for (const doc of stableDocs) {
  const target = doc.startsWith('specs/')
    ? path.join('docs', doc)
    : path.join('docs', doc);
  assertExists(target);
  assertAbsent(doc);
}

for (const doc of archivedPlans) {
  assertExists(path.join('work', 'archived-plans', path.basename(doc)));
  assertAbsent(doc);
}
