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

async function main(argv) {
  const jsonPath = argv[0];
  if (!jsonPath) {
    throw new Error('usage: generate_outline_module.js <outline.json>');
  }

  const outline = JSON.parse(await fs.readFile(jsonPath, 'utf8'));
  const { moduleName, exportName } = toModuleNames(jsonPath);

  const lines = [
    `// Generated runtime copy of ${jsonPath}.`,
    `// Keep in sync with the schema v1 source artifact; tests compare this value to the source file.`,
    ``,
    `export const ${exportName} = ${JSON.stringify(outline)};`,
    ``
  ].join('\n');

  const outPath = path.join('product', 'web', 'js', `${moduleName}.js`);
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, lines);
  console.log(`Wrote ${outPath} (${(lines.length / 1024).toFixed(0)} KB, export: ${exportName})`);
}

main(process.argv.slice(2)).catch(err => {
  console.error(`generate_outline_module failed: ${err.message}`);
  process.exit(1);
});