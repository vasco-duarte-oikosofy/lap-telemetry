#!/usr/bin/env node
'use strict';

const assert = require('assert');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..', '..');

function gitTrackedFiles() {
  const out = execFileSync('git', ['ls-files'], { cwd: root, encoding: 'utf8' });
  return out.trim().split('\n').filter(Boolean);
}

function pass(message) {
  console.log(`[PASS] ${message}`);
}

const allowedRootDirs = new Set([
  'dev',
  'docs',
  'product',
  'scripts',
  'var',
  'vendor',
  'work',
]);

const tracked = gitTrackedFiles();
const trackedRootDirs = new Set(
  tracked
    .filter((file) => file.includes('/'))
    .map((file) => file.split('/')[0])
);

const unexpected = [...trackedRootDirs].filter((dir) => !allowedRootDirs.has(dir));
assert.deepStrictEqual(unexpected, [], `unexpected tracked root directories: ${unexpected.join(', ')}`);
pass('tracked root directories are limited to documented L1 folders and compatibility scripts');

for (const legacyDir of [
  'phases_TUMFTM_based_track_map_outline',
  'phases_track_heatmap',
  'phases_track_outline',
]) {
  assert.ok(!fs.existsSync(path.join(root, legacyDir)), `${legacyDir} moved out of root`);
  pass(`${legacyDir} moved out of root`);

  assert.ok(
    fs.existsSync(path.join(root, 'work', 'archived-plans', legacyDir)),
    `work/archived-plans/${legacyDir} exists`
  );
  pass(`work/archived-plans/${legacyDir} exists`);
}
