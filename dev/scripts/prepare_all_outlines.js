#!/usr/bin/env node
'use strict';

/**
 * Prepare alignment inputs and run auto-alignment for all tracks
 * where we have both session data and TUMFTM source data.
 *
 * Usage:
 *   node scripts/prepare_all_outlines.js
 *
 * This will:
 * 1. Convert TUMFTM CSVs to JSON
 * 2. Extract reference laps from session parquets
 * 3. Run auto-alignment (ICP)
 * 4. Write outline JSON files to data/track-outlines/
 */

const fs = require('fs/promises');
const path = require('path');
const { exportTrajectories, parseCsvTrack } = require('./prepare_manual_outline_inputs');
const { runICP, generateOutline, transformPoint } = require('./auto_align_outline');

const TUMFTM_DIR = '/private/tmp/tumftm';
const SESSIONS_DIR = 'sessions';
const OUTLINES_DIR = 'data/track-outlines';
const ARTIFACTS_DIR = 'data/track-outlines/alignment-artifacts';

// Track mappings: sim track slug → { tumftmCsvName, tumftmTrackName, simTrackName, sessionFile }
// Only entries where TUMFTM data exists
const TRACKS = {
  'circuit-de-barcelona': {
    tumftmCsvName: 'Catalunya',
    tumftmTrackName: 'Circuit de Barcelona-Catalunya',
    simTrackName: 'Circuit de Barcelona',
    sessionFile: 'session_20260514T141305Z_circuit-de-barcelona_lmu',
    lap: null,
  },
};

async function convertTumftmCsv(csvName) {
  const csvPath = path.join(TUMFTM_DIR, `${csvName}.csv`);
  const text = await fs.readFile(csvPath, 'utf8');
  return parseCsvTrack(text);
}

async function prepareTrajectory(sessionFile, opts = {}) {
  const parquetPath = path.join(SESSIONS_DIR, `${sessionFile}.parquet`);
  const json = await exportTrajectories([parquetPath], '/dev/null', {
    lap: opts.lap ?? null,
    stride: opts.stride ?? 5,
  });
  return json;
}

async function alignTrack(slug, config) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Processing: ${slug}`);
  console.log(`${'='.repeat(60)}`);

  // 1. Convert TUMFTM CSV
  console.log(`Converting TUMFTM ${config.tumftmCsvName}.csv...`);
  const tumftmTrack = await convertTumftmCsv(config.tumftmCsvName);
  tumftmTrack.track_name = config.tumftmTrackName;
  console.log(`  TUMFTM points: ${tumftmTrack.points.length}`);

  // 2. Extract sim trajectory
  console.log(`Extracting trajectory from ${config.sessionFile}...`);
  const trajectory = await prepareTrajectory(config.sessionFile, { lap: config.lap });
  const simPointCount = trajectory.trajectories.reduce((n, t) => n + t.points.length, 0);
  console.log(`  Sim points: ${simPointCount}`);

  // 3. Write intermediate files for manual tool (no dot prefix!)
  const artifactsDir = path.join(ARTIFACTS_DIR, slug);
  await fs.mkdir(artifactsDir, { recursive: true });
  const tumftmJsonPath = path.join(artifactsDir, `tumftm-${slug}.json`);
  const trajJsonPath = path.join(artifactsDir, `trajectory-${slug}.json`);
  await fs.writeFile(tumftmJsonPath, JSON.stringify(tumftmTrack, null, 2) + '\n');
  await fs.writeFile(trajJsonPath, JSON.stringify(trajectory, null, 2) + '\n');
  console.log(`  Wrote ${tumftmJsonPath}`);
  console.log(`  Wrote ${trajJsonPath}`);

  // 4. Run auto-alignment with all flip combinations
  console.log(`Running ICP auto-alignment...`);
  const source = tumftmTrack.points;
  const target = [];
  for (const t of trajectory.trajectories) {
    for (const p of t.points) {
      if (Number.isFinite(p.x) && Number.isFinite(p.y)) target.push(p);
    }
  }

  const flipConfigs = [
    { flip_x: false, flip_y: false, label: 'none' },
    { flip_x: true,  flip_y: false, label: 'flip_x' },
    { flip_x: false, flip_y: true,  label: 'flip_y' },
    { flip_x: true,  flip_y: true,  label: 'both' }
  ];

  // Also try reversed point order for each
  const allConfigs = [];
  for (const fc of flipConfigs) {
    allConfigs.push({ ...fc, reverse: false });
    allConfigs.push({ ...fc, reverse: true });
  }

  let bestResult = null, bestError = Infinity, bestConfig = null;

  for (const cfg of allConfigs) {
    const src = cfg.reverse ? [...source].reverse() : source;
    const result = runICP(src, target, { flip_x: cfg.flip_x, flip_y: cfg.flip_y, iterations: 100 });

    // Compute alignment error
    const flipped = src.map(p => ({
      x: p.x * (cfg.flip_x ? -1 : 1),
      y: p.y * (cfg.flip_y ? -1 : 1),
    }));
    const transformed = flipped.map(p => transformPoint(p, result));
    let totalError = 0;
    for (const p of transformed) {
      let minDist = Infinity;
      for (const q of target) {
        const d = Math.hypot(p.x - q.x, p.y - q.y);
        if (d < minDist) minDist = d;
      }
      totalError += minDist;
    }
    const meanError = totalError / transformed.length;
    console.log(`  ${cfg.label}${cfg.reverse ? '+rev' : ''}: scale=${result.scale.toFixed(4)} rot=${(result.rotation_rad*180/Math.PI).toFixed(1)}° tx=${result.translate_x.toFixed(1)} ty=${result.translate_y.toFixed(1)} err=${meanError.toFixed(1)}`);

    if (meanError < bestError) {
      bestError = meanError;
      bestResult = { ...result, reverse_point_order: cfg.reverse };
      bestConfig = cfg;
    }
  }

  console.log(`\nBest: ${bestConfig.label}${bestConfig.reverse ? '+rev' : ''} meanError=${bestError.toFixed(1)}`);

  // 5. Generate and write outline
  const outline = generateOutline(
    { ...tumftmTrack, points: bestResult.reverse_point_order ? [...tumftmTrack.points].reverse() : tumftmTrack.points },
    bestResult,
    config.simTrackName,
    `Auto-aligned via ICP (best of ${allConfigs.length} flip/reverse combos). ${bestConfig.label}${bestConfig.reverse ? '+reverse' : ''}. Visual verification needed using tools/manual_outline_align.html.`
  );

  const outPath = path.join(OUTLINES_DIR, `${slug}.json`);
  await fs.writeFile(outPath, JSON.stringify(outline, null, 2) + '\n');
  console.log(`\nWrote ${outPath}`);
  console.log(`  centerline: ${outline.centerline.length} pts`);
  console.log(`  left_boundary: ${outline.left_boundary.length} pts`);
  console.log(`  right_boundary: ${outline.right_boundary.length} pts`);

  return outline;
}

async function main() {
  // Ensure TUMFTM CSVs are downloaded
  for (const slug of Object.keys(TRACKS)) {
    const csvPath = path.join(TUMFTM_DIR, `${TRACKS[slug].tumftmCsvName}.csv`);
    try {
      await fs.access(csvPath);
    } catch {
      throw new Error(`TUMFTM CSV not found: ${csvPath}. Download from https://github.com/TUMFTM/racetrack-database`);
    }
  }

  const results = {};
  for (const [slug, config] of Object.entries(TRACKS)) {
    try {
      results[slug] = await alignTrack(slug, config);
    } catch (err) {
      console.error(`Failed to align ${slug}: ${err.message}`);
      results[slug] = { error: err.message };
    }
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log('Summary');
  console.log(`${'='.repeat(60)}`);
  for (const [slug, result] of Object.entries(results)) {
    if (result.error) {
      console.log(`  ${slug}: FAILED - ${result.error}`);
    } else {
      const a = result.alignment;
      console.log(`  ${slug}: scale=${a.scale.toFixed(4)} rot=${(a.rotation_rad*180/Math.PI).toFixed(1)}° tx=${a.translate_x.toFixed(0)} ty=${a.translate_y.toFixed(0)} flip=(${a.flip_x},${a.flip_y}) rev=${a.reverse_point_order} [${result.centerline.length} pts]`);
    }
  }

  // Also report tracks we CANNOT align (no TUMFTM data)
  const allSessionTracks = new Set();
  const files = await fs.readdir(SESSIONS_DIR);
  for (const f of files) {
    if (!f.endsWith('.json') || f.includes('apex-annotations')) continue;
    try {
      const d = JSON.parse(await fs.readFile(path.join(SESSIONS_DIR, f), 'utf8'));
      const track = d.track;
      if (track) allSessionTracks.add(track);
    } catch {}
  }

  console.log(`\nTracks without TUMFTM data (cannot auto-align):`);
  const alreadyDone = new Set(Object.keys(TRACKS).concat(['circuit-de-spa-francorchamps', 'circuit-de-spa-francorchamps-endurance', 'spa-francorchamps']));
  for (const track of allSessionTracks) {
    const slug = track.toLowerCase().replace(/\s+/g, '-');
    if (!alreadyDone.has(slug)) {
      console.log(`  ${track} (${slug})`);
    }
  }
}

main().catch(err => {
  console.error(`prepare_all_outlines failed: ${err.message}`);
  process.exit(1);
});