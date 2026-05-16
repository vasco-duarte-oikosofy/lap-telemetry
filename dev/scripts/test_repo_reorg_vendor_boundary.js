#!/usr/bin/env node
'use strict';
// @parallel true

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..', '..');

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

function exists(relativePath) {
  return fs.existsSync(path.join(root, relativePath));
}

function pass(message) {
  console.log(`[PASS] ${message}`);
}

for (const name of ['pyLMUSharedMemory', 'pyRfactor2SharedMemory']) {
  assert.ok(exists(path.join('vendor', name)), `vendor/${name} exists`);
  pass(`vendor/${name} exists`);

  assert.ok(!exists(name), `${name} moved from repository root`);
  pass(`${name} moved from repository root`);
}

const gitmodules = read('.gitmodules');
for (const name of ['pyLMUSharedMemory', 'pyRfactor2SharedMemory']) {
  assert.match(gitmodules, new RegExp(`path = vendor/${name}`), `.gitmodules points ${name} at vendor/`);
  pass(`.gitmodules points ${name} at vendor/`);

  assert.doesNotMatch(gitmodules, new RegExp(`path = ${name}(\\n|$)`), `.gitmodules has no root path for ${name}`);
  pass(`.gitmodules has no root path for ${name}`);
}

const connectSource = read('product/python/lap_telemetry/recorder/connect.py');
assert.match(connectSource, /vendor/, 'recorder source checkout import path includes vendor/');
pass('recorder source checkout import path includes vendor/');

const vendorReadme = read('vendor/README.md');
for (const name of ['pyLMUSharedMemory', 'pyRfactor2SharedMemory']) {
  assert.match(vendorReadme, new RegExp(`vendor/${name}`), `vendor README names vendor/${name}`);
  pass(`vendor README names vendor/${name}`);
}
