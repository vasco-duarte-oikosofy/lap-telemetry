#!/usr/bin/env node
'use strict';

/**
 * Generate a static outline ES module from a product/data/track-outlines/*.json file.
 * The output module exports the outline as a named const so it can be imported
 * by the track outline manifest at build time.
 *
 * Usage:
 *   node dev/scripts/generate_outline_module.js product/data/track-outlines/circuit-de-barcelona.json
 */

const fs = require('fs/promises');
const path = require('path');

function toModuleNames(fileName) {
  // circuit-de-barcelona.json → { moduleName: 'staticCircuitBarcelonaOutlineData', exportName: 'CIRCUIT_BARCELONA_STATIC_OUTLINE' }
  // spa-francorchamps.json → { moduleName: 'staticSpaFrancorchampsOutlineData', exportName: 'SPA_FRANCORCHAMPS_STATIC_OUTLINE' }
  const base = path.basename(fileName, '.json');
  const skipWords = new Set(['de', 'e', 'enzo', 'din']);
  const parts = base.split('-').filter(p => !skipWords.has(p));
  const pascal = parts.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join('');
  const screaming = parts.map(p => p.toUpperCase()).join('_');
  return {
    moduleName: `static${pascal}OutlineData`,
    exportName: `${screaming}_STATIC_OUTLINE`
  };
}

async function findManifestImportName(moduleName) {
  const manifestPath = path.join('product', 'web', 'js', 'trackOutlineManifest.js');
  try {
    const manifest = await fs.readFile(manifestPath, 'utf8');
    const moduleFile = `./${moduleName}.js`.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const importRe = new RegExp(`import\\s*\\{\\s*([A-Za-z0-9_]+)\\s*\\}\\s*from\\s*['\"]${moduleFile}['\"]`);
    return manifest.match(importRe)?.[1] || null;
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err;
  }
}

async function findExistingExportName(outPath) {
  try {
    const text = await fs.readFile(outPath, 'utf8');
    return text.match(/export\s+const\s+([A-Za-z0-9_]+)\s*=/)?.[1] || null;
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err;
  }
}

async function resolveModuleNames(jsonPath) {
  const names = toModuleNames(jsonPath);
  const outPath = path.join('product', 'web', 'js', `${names.moduleName}.js`);
  const manifestExportName = await findManifestImportName(names.moduleName);
  const existingExportName = await findExistingExportName(outPath);
  return {
    ...names,
    exportName: manifestExportName || existingExportName || names.exportName,
    outPath,
    manifestExportName,
    existingExportName,
  };
}

async function main(argv) {
  const jsonPath = argv[0];
  if (!jsonPath) {
    throw new Error('usage: generate_outline_module.js <outline.json>');
  }

  const outline = JSON.parse(await fs.readFile(jsonPath, 'utf8'));
  const { exportName, outPath, manifestExportName } = await resolveModuleNames(jsonPath);

  const lines = [
    `// Generated runtime copy of ${jsonPath}.`,
    `// Keep in sync with the schema v1 source artifact; tests compare this value to the source file.`,
    ``,
    `export const ${exportName} = ${JSON.stringify(outline)};`,
    ``
  ].join('\n');

  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, lines);

  if (manifestExportName && manifestExportName !== exportName) {
    throw new Error(`internal error: generated ${exportName}, but manifest imports ${manifestExportName}`);
  }

  console.log(`Wrote ${outPath} (${(lines.length / 1024).toFixed(0)} KB, export: ${exportName})`);
}

main(process.argv.slice(2)).catch(err => {
  console.error(`generate_outline_module failed: ${err.message}`);
  process.exit(1);
});