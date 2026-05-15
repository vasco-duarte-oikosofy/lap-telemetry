#!/usr/bin/env node
/**
 * Optional width profile CLI — generates raw unsmoothed left/right width bins
 * from one or more recorded sessions.
 *
 * Usage:
 *   node scripts/export_width_profile.js --out <profile.json> \
 *     --track-id <track> --layout-id <layout> <session1.parquet> [session2.parquet ...]
 *
 * Options:
 *   --overwrite    Replace existing output file (default: refuse)
 */

'use strict';

const fs = require('fs/promises');
const path = require('path');

const REQUIRED_COLUMNS = ['raw_lap_distance_m', 'path_lateral_m', 'track_edge_m'];
const MIN_SAMPLES = 3;
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
    Number.isFinite(row.path_lateral_m) &&
    Number.isFinite(row.track_edge_m)
  );
}

function classifyBin(bin) {
  if (bin.left_sample_count === 0 && bin.right_sample_count === 0) {
    return { status: 'missing', confidence: 0 };
  }
  if (bin.left_sample_count === 0 || bin.right_sample_count === 0) {
    return { status: 'one-sided', confidence: 0.5 };
  }
  if (bin.left_sample_count < MIN_SAMPLES || bin.right_sample_count < MIN_SAMPLES) {
    return { status: 'low-sample', confidence: 0.75 };
  }
  return { status: 'complete', confidence: 1 };
}

function buildProfileFromRows(rows, binSizeM) {
  const bins = new Map();
  let skipped = 0;

  for (const row of rows) {
    if (!isValidRow(row)) {
      skipped++;
      continue;
    }
    const key = binKey(row.raw_lap_distance_m, binSizeM);
    if (!bins.has(key)) {
      bins.set(key, { s_m: key, left_width_m: 0, right_width_m: 0, left_sample_count: 0, right_sample_count: 0 });
    }
    const bin = bins.get(key);
    if (row.path_lateral_m < 0) {
      bin.left_width_m = Math.max(bin.left_width_m, Math.abs(row.track_edge_m));
      bin.left_sample_count++;
    } else {
      bin.right_width_m = Math.max(bin.right_width_m, Math.abs(row.track_edge_m));
      bin.right_sample_count++;
    }
  }

  // Fill gap bins between min and max s_m so missing bins are explicit
  if (bins.size > 0) {
    const keys = [...bins.keys()].sort((a, b) => a - b);
    const minKey = keys[0];
    const maxKey = keys[keys.length - 1];
    for (let s = minKey; s <= maxKey; s += binSizeM) {
      if (!bins.has(s)) {
        bins.set(s, { s_m: s, left_width_m: 0, right_width_m: 0, left_sample_count: 0, right_sample_count: 0 });
      }
    }
  }

  // Add confidence and status to each bin
  const counts = { missing_bins: 0, one_sided_bins: 0, low_sample_bins: 0, complete_bins: 0 };
  const samples = [...bins.values()].sort((a, b) => a.s_m - b.s_m);
  for (const bin of samples) {
    const { status, confidence } = classifyBin(bin);
    bin.status = status;
    bin.confidence = confidence;
    counts[status.replace('-', '_') + '_bins']++;
  }

  return { samples, skipped, ...counts };
}

async function readSessionRows(sessionPath) {
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
      path_lateral_m: data.path_lateral_m[i],
      track_edge_m: data.track_edge_m[i],
    });
  }
  return rows;
}

async function exportWidthProfile({ sessionPaths, trackId, layoutId, outPath, binSizeM = 1, overwrite = false } = {}) {
  if (!sessionPaths || sessionPaths.length === 0) throw new Error('no session paths provided');
  if (!trackId) throw new Error('missing --track-id');
  if (!layoutId) throw new Error('missing --layout-id');
  if (!outPath) throw new Error('missing --out path');

  let allRows = [];
  for (const sp of sessionPaths) {
    const rows = await readSessionRows(sp);
    allRows = allRows.concat(rows);
  }

  const { samples, skipped, missing_bins, one_sided_bins, low_sample_bins, complete_bins } = buildProfileFromRows(allRows, binSizeM);

  const profile = {
    track_id: trackId,
    layout_id: layoutId,
    bin_size_m: binSizeM,
    samples,
    summary: {
      input_rows: allRows.length,
      skipped_rows: skipped,
      missing_bins,
      one_sided_bins,
      low_sample_bins,
      complete_bins,
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
  const profile = await exportWidthProfile(opts);
  const s = profile.summary;
  console.log(`wrote ${opts.outPath} (${profile.samples.length} bins, ${s.skipped_rows} skipped)`);
  console.log(`  complete=${s.complete_bins} one-sided=${s.one_sided_bins} low-sample=${s.low_sample_bins} missing=${s.missing_bins}`);
}

module.exports = { exportWidthProfile, buildProfileFromRows, readSessionRows };

if (require.main === module) {
  main(process.argv.slice(2)).catch(err => {
    console.error(`width profile export failed: ${err.message}`);
    process.exit(1);
  });
}