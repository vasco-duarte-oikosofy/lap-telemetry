#!/usr/bin/env node
/**
 * Center/path polyline CLI — generates binned averaged world positions
 * from one or more recorded sessions.
 *
 * Usage:
 *   node scripts/export_center_path.js --out <path.json> \
 *     --track-id <track> --layout-id <layout> <session1.parquet> [session2.parquet ...]
 *
 * Options:
 *   --overwrite    Replace existing output file (default: refuse)
 */

'use strict';

const fs = require('fs/promises');
const path = require('path');

const REQUIRED_COLUMNS = ['raw_lap_distance_m', 'pos_x_m', 'pos_z_m'];
const COLUMN_LIST = ['lap_number', ...REQUIRED_COLUMNS];

function schemaNames(metadata) {
  return new Set((metadata.schema || []).map(field => field.name).filter(Boolean));
}

function binKey(rawLapDistM, binSizeM) {
  return Math.floor(rawLapDistM / binSizeM) * binSizeM;
}

function isValidRow(row) {
  return (
    Number.isFinite(row.raw_lap_distance_m) &&
    Number.isFinite(row.pos_x_m) &&
    Number.isFinite(row.pos_z_m)
  );
}

function buildPathFromRows(rows, binSizeM) {
  const bins = new Map();
  let skipped = 0;

  for (const row of rows) {
    if (!isValidRow(row)) {
      skipped++;
      continue;
    }
    const key = binKey(row.raw_lap_distance_m, binSizeM);
    if (!bins.has(key)) {
      bins.set(key, { s_m: key, sum_x: 0, sum_z: 0, sample_count: 0 });
    }
    const bin = bins.get(key);
    bin.sum_x += row.pos_x_m;
    bin.sum_z += row.pos_z_m;
    bin.sample_count++;
  }

  // Convert bins to points
  const points = [...bins.values()]
    .sort((a, b) => a.s_m - b.s_m)
    .map(b => ({
      s_m: b.s_m,
      x_m: b.sum_x / b.sample_count,
      z_m: b.sum_z / b.sample_count,
      sample_count: b.sample_count,
    }));

  return { points, skipped };
}

async function readPathRows(sessionPath) {
  const { asyncBufferFromFile, parquetMetadataAsync, parquetRead } = await import('hyparquet');
  const { compressors } = await import('hyparquet-compressors');

  const file = await asyncBufferFromFile(sessionPath);
  const metadata = await parquetMetadataAsync(file);
  const available = schemaNames(metadata);
  const columns = COLUMN_LIST.filter(c => available.has(c));

  const data = Object.fromEntries(COLUMN_LIST.map(c => [c, []]));
  await parquetRead({
    file,
    compressors,
    columns,
    onChunk({ columnName, columnData }) {
      if (!Object.prototype.hasOwnProperty.call(data, columnName)) return;
      for (let i = 0; i < columnData.length; i++) data[columnName].push(columnData[i]);
    },
  });

  const n = Math.max(...columns.map(c => data[c].length), 0);
  const rows = [];
  for (let i = 0; i < n; i++) {
    rows.push({
      raw_lap_distance_m: data.raw_lap_distance_m[i],
      pos_x_m: data.pos_x_m[i],
      pos_z_m: data.pos_z_m[i],
    });
  }
  return rows;
}

async function exportCenterPath({ sessionPaths, trackId, layoutId, outPath, binSizeM = 1, overwrite = false } = {}) {
  if (!sessionPaths || sessionPaths.length === 0) throw new Error('no session paths provided');
  if (!trackId) throw new Error('missing --track-id');
  if (!layoutId) throw new Error('missing --layout-id');
  if (!outPath) throw new Error('missing --out path');

  let allRows = [];
  for (const sp of sessionPaths) {
    const rows = await readPathRows(sp);
    allRows = allRows.concat(rows);
  }

  const { points, skipped } = buildPathFromRows(allRows, binSizeM);

  const profile = {
    track_id: trackId,
    layout_id: layoutId,
    bin_size_m: binSizeM,
    points,
    summary: {
      input_rows: allRows.length,
      skipped_rows: skipped,
    },
  };

  await fs.mkdir(path.dirname(outPath), { recursive: true });
  try {
    await fs.writeFile(outPath, `${JSON.stringify(profile, null, 2)}\n`, { flag: overwrite ? 'w' : 'wx' });
  } catch (err) {
    if (err && err.code === 'EEXIST') {
      throw new Error(`output exists: ${outPath} (pass --overwrite to replace)`);
    }
    throw err;
  }

  return profile;
}

function parseArgs(argv) {
  const opts = { overwrite: false, sessionPaths: [] };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--overwrite') {
      opts.overwrite = true;
    } else if (arg === '--out' || arg === '--track-id' || arg === '--layout-id') {
      const value = argv[++i];
      if (!value) throw new Error(`missing value for ${arg}`);
      const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      opts[key] = value;
    } else if (!arg.startsWith('--')) {
      opts.sessionPaths.push(arg);
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return {
    sessionPaths: opts.sessionPaths,
    trackId: opts.trackId,
    layoutId: opts.layoutId,
    outPath: opts.out,
    overwrite: opts.overwrite,
  };
}

async function main(argv) {
  const opts = parseArgs(argv);
  const profile = await exportCenterPath(opts);
  const s = profile.summary;
  console.log(`wrote ${opts.outPath} (${profile.points.length} points, ${s.skipped_rows} skipped)`);
}

module.exports = { exportCenterPath, buildPathFromRows, readPathRows };

if (require.main === module) {
  main(process.argv.slice(2)).catch(err => {
    console.error(`center path export failed: ${err.message}`);
    process.exit(1);
  });
}