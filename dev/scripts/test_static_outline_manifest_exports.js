#!/usr/bin/env node
'use strict';
// @parallel true

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const manifestPath = path.join(ROOT, 'product', 'web', 'js', 'trackOutlineManifest.js');
const WEB_JS_DIR = path.join(ROOT, 'product', 'web', 'js');

let pass = 0;
let fail = 0;

function ok(condition, label, detail = '') {
  if (condition) {
    pass++;
    console.log(`  PASS ${label}${detail ? ` — ${detail}` : ''}`);
  } else {
    fail++;
    console.log(`  FAIL ${label}${detail ? ` — ${detail}` : ''}`);
  }
}

const manifest = fs.readFileSync(manifestPath, 'utf8');
const importRe = /import\s*\{\s*([A-Za-z0-9_]+)\s*\}\s*from\s*['"]\.\/(static[^'"]+\.js)['"]/g;
const imports = [...manifest.matchAll(importRe)].map(match => ({
  exportName: match[1],
  moduleFile: match[2],
}));

ok(imports.length > 0, 'track outline manifest imports static modules', `${imports.length} imports`);

for (const { exportName, moduleFile } of imports) {
  const modulePath = path.join(WEB_JS_DIR, moduleFile);
  ok(fs.existsSync(modulePath), `static outline module exists for ${exportName}`, moduleFile);
  if (!fs.existsSync(modulePath)) continue;

  const moduleText = fs.readFileSync(modulePath, 'utf8');
  const exportRe = new RegExp(`export\\s+const\\s+${exportName}\\s*=`);
  ok(exportRe.test(moduleText), `static outline module exports manifest symbol`, `${moduleFile} → ${exportName}`);
}

console.log(`\n  ${pass}/${pass + fail} assertions passed`);
if (fail > 0) process.exit(1);
