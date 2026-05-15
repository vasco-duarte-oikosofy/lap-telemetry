#!/usr/bin/env node
'use strict';

const fs = require('fs/promises');
const path = require('path');

function parseCsvTrack(text) {
  const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const headerLine = lines.find(l => l.startsWith('#')) || lines[0] || '';
  const header = headerLine.replace(/^#\s*/, '').split(/[;,]/).map(s => s.trim());
  const data = lines.filter(l => !l.startsWith('#'));
  const points = data.map(line => {
    const values = line.split(/[;,]/).map(Number);
    const row = Object.fromEntries(header.map((h, i) => [h, values[i]]));
    return {
      x: row.x_m ?? values[0],
      y: row.y_m ?? values[1],
      w_right: row.w_tr_right_m ?? values[2],
      w_left: row.w_tr_left_m ?? values[3]
    };
  }).filter(p => Number.isFinite(p.x) && Number.isFinite(p.y));
  return { track_name: 'Spa TUMFTM', points };
}

async function convertTumftmCsv(csvPath, outPath) {
  const track = parseCsvTrack(await fs.readFile(csvPath, 'utf8'));
  await writeJson(outPath, track);
  return track;
}

async function readRows(parquetPath) {
  const { asyncBufferFromFile, parquetMetadataAsync, parquetRead } = await import('hyparquet');
  const { compressors } = await import('hyparquet-compressors');
  const wanted = ['lap_number', 'pos_x_m', 'pos_z_m', 'lap_distance_m', 'raw_lap_distance_m'];
  const file = await asyncBufferFromFile(parquetPath);
  const metadata = await parquetMetadataAsync(file);
  const names = new Set((metadata.schema || []).map(f => f.name));
  const columns = wanted.filter(c => names.has(c));
  const data = Object.fromEntries(wanted.map(c => [c, []]));
  await parquetRead({
    file, compressors, columns,
    onChunk({ columnName, columnData }) {
      if (data[columnName]) for (const v of columnData) data[columnName].push(v);
    }
  });
  const n = Math.max(...columns.map(c => data[c].length), 0);
  return Array.from({ length: n }, (_, i) => ({
    lap_number: data.lap_number[i],
    x: data.pos_x_m[i],
    y: data.pos_z_m[i],
    s_m: data.raw_lap_distance_m[i] ?? data.lap_distance_m[i]
  }));
}

function groupByLap(rows) {
  const laps = new Map();
  for (const row of rows) {
    if (!Number.isFinite(row.x) || !Number.isFinite(row.y)) continue;
    const lap = row.lap_number ?? 'unknown';
    if (!laps.has(lap)) laps.set(lap, []);
    laps.get(lap).push({ x: row.x, y: row.y, s_m: row.s_m });
  }
  return laps;
}

async function exportTrajectories(parquetPaths, outPath, { lap = null, stride = 10 } = {}) {
  const trajectories = [];
  for (const parquetPath of parquetPaths) {
    const laps = groupByLap(await readRows(parquetPath));
    const selected = lap == null ? [...laps.keys()].slice(0, 1) : [Number.isNaN(Number(lap)) ? lap : Number(lap)];
    for (const lapKey of selected) {
      const pts = (laps.get(lapKey) || []).filter((_, i) => i % stride === 0).map(p => ({ x: p.x, y: p.y }));
      if (pts.length) trajectories.push({ name: `${path.basename(parquetPath)} lap ${lapKey}`, points: pts });
    }
  }
  const json = { track_name: 'Spa-Francorchamps', trajectories };
  await writeJson(outPath, json);
  return json;
}

async function writeJson(outPath, obj) {
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, `${JSON.stringify(obj, null, 2)}\n`);
}

function parseArgs(argv) {
  const opts = { parquetPaths: [], stride: 10 };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--tumftm-csv') opts.tumftmCsv = argv[++i];
    else if (arg === '--tumftm-json') opts.tumftmJson = argv[++i];
    else if (arg === '--trajectory-json') opts.trajectoryJson = argv[++i];
    else if (arg === '--lap') opts.lap = argv[++i];
    else if (arg === '--stride') opts.stride = Number(argv[++i]);
    else if (!arg.startsWith('--')) opts.parquetPaths.push(arg);
    else throw new Error(`unknown argument: ${arg}`);
  }
  return opts;
}

async function main(argv) {
  const opts = parseArgs(argv);
  if (opts.tumftmCsv || opts.tumftmJson) {
    if (!opts.tumftmCsv || !opts.tumftmJson) throw new Error('use --tumftm-csv with --tumftm-json');
    const track = await convertTumftmCsv(opts.tumftmCsv, opts.tumftmJson);
    console.log(`wrote ${opts.tumftmJson} (${track.points.length} TUMFTM points)`);
  }
  if (opts.trajectoryJson) {
    if (!opts.parquetPaths.length) throw new Error('provide parquet session path(s) for --trajectory-json');
    const traj = await exportTrajectories(opts.parquetPaths, opts.trajectoryJson, opts);
    console.log(`wrote ${opts.trajectoryJson} (${traj.trajectories.length} trajectories)`);
  }
}

module.exports = { parseCsvTrack, convertTumftmCsv, exportTrajectories };

if (require.main === module) {
  main(process.argv.slice(2)).catch(err => {
    console.error(`manual outline input prep failed: ${err.message}`);
    process.exit(1);
  });
}
