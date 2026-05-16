#!/usr/bin/env node
/**
 * Optional apex metrics sidecar export.
 *
 * Usage:
 *   node scripts/export_apex_metrics.js --session <session.parquet> \
 *     --annotations <apex-annotations.json> --out <metrics.json> [--overwrite]
 */

'use strict';

const fs = require('fs/promises');
const path = require('path');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..', '..');
const SCHEMA_VERSION = 1;
const SESSION_COLUMNS = [
  'lap_number',
  'raw_lap_distance_m',
  'path_lateral_m',
  'track_edge_m',
  'distance_to_track_edge_m',
  'surface_type_fl',
  'surface_type_fr',
  'surface_type_rl',
  'surface_type_rr',
  'terrain_name_fl',
  'terrain_name_fr',
  'terrain_name_rl',
  'terrain_name_rr',
];

function moduleUrl(relativePath) {
  return pathToFileURL(path.join(ROOT, relativePath)).href;
}

async function loadProjectModules() {
  const [annotations, metrics, pipeline] = await Promise.all([
    import(moduleUrl('web/js/apexAnnotations.js')),
    import(moduleUrl('web/js/apexMetrics.js')),
    import(moduleUrl('web/js/pipeline.js')),
  ]);
  return {
    loadApexAnnotationsFile: annotations.loadApexAnnotationsFile,
    computeApexMetricsForSession: metrics.computeApexMetricsForSession,
    buildSegments: pipeline.buildSegments,
  };
}

function schemaNames(metadata) {
  return new Set((metadata.schema || []).map(field => field.name).filter(Boolean));
}

async function loadSessionEntry(sessionPath, buildSegments) {
  const { asyncBufferFromFile, parquetMetadataAsync, parquetRead } = await import('hyparquet');
  const { compressors } = await import('hyparquet-compressors');
  const file = await asyncBufferFromFile(sessionPath);
  const metadata = await parquetMetadataAsync(file);
  const available = SESSION_COLUMNS.filter(column => schemaNames(metadata).has(column));
  const data = Object.fromEntries(SESSION_COLUMNS.map(column => [column, []]));

  await parquetRead({
    file,
    compressors,
    columns: available,
    onChunk({ columnName, columnData }) {
      if (!Object.prototype.hasOwnProperty.call(data, columnName)) return;
      for (let i = 0; i < columnData.length; i++) data[columnName].push(columnData[i]);
    },
  });

  return {
    fileName: path.basename(sessionPath),
    data,
    segments: buildSegments(data.lap_number),
  };
}

function assertConfiguredAnnotations(loaderResult, annotationsPath) {
  if (loaderResult.status === 'ok') return;
  if (loaderResult.status === 'invalid') {
    throw new Error(`invalid annotations ${annotationsPath}: ${loaderResult.errors.join('; ')}`);
  }
  throw new Error(`annotations not configured: ${annotationsPath}`);
}

function buildSidecar({ sessionPath, annotationsPath, annotations, result }) {
  return {
    schema_version: SCHEMA_VERSION,
    source_session: sessionPath,
    source_annotations: annotationsPath,
    annotation_track_id: annotations.track_id,
    annotation_layout_id: annotations.layout_id,
    status: result.status,
    reason: result.reason,
    metrics: result.metrics,
  };
}

async function writeSidecar(outPath, sidecar, overwrite) {
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  try {
    await fs.writeFile(outPath, `${JSON.stringify(sidecar, null, 2)}\n`, { flag: overwrite ? 'w' : 'wx' });
  } catch (err) {
    if (err && err.code === 'EEXIST') {
      throw new Error(`output exists: ${outPath} (pass --overwrite to replace)`);
    }
    throw err;
  }
}

async function exportApexMetricsSidecar({ sessionPath, annotationsPath, outPath, overwrite = false } = {}) {
  if (!sessionPath) throw new Error('missing required --session path');
  if (!annotationsPath) throw new Error('missing required --annotations path');
  if (!outPath) throw new Error('missing required --out path');

  const { loadApexAnnotationsFile, computeApexMetricsForSession, buildSegments } = await loadProjectModules();
  const loadedAnnotations = await loadApexAnnotationsFile(annotationsPath);
  assertConfiguredAnnotations(loadedAnnotations, annotationsPath);

  const entry = await loadSessionEntry(sessionPath, buildSegments);
  const result = computeApexMetricsForSession(entry, loadedAnnotations);
  const sidecar = buildSidecar({
    sessionPath,
    annotationsPath,
    annotations: loadedAnnotations.annotations,
    result,
  });
  await writeSidecar(outPath, sidecar, overwrite);
  return sidecar;
}

function parseArgs(argv) {
  const opts = { overwrite: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--overwrite') {
      opts.overwrite = true;
    } else if (arg === '--session' || arg === '--annotations' || arg === '--out') {
      const value = argv[++i];
      if (!value) throw new Error(`missing value for ${arg}`);
      opts[arg.slice(2) + (arg === '--session' ? 'Path' : '')] = value;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return {
    sessionPath: opts.sessionPath,
    annotationsPath: opts.annotations,
    outPath: opts.out,
    overwrite: opts.overwrite,
  };
}

async function main(argv) {
  const opts = parseArgs(argv);
  const sidecar = await exportApexMetricsSidecar(opts);
  console.log(`wrote ${opts.outPath} (${sidecar.status})`);
}

module.exports = { exportApexMetricsSidecar, loadSessionEntry };

if (require.main === module) {
  main(process.argv.slice(2)).catch(err => {
    console.error(`apex metrics export failed: ${err.message}`);
    process.exit(1);
  });
}
