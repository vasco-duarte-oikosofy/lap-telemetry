#!/usr/bin/env node
/**
 * Full telemetry pipeline — identical to the web UI's processing.
 *
 * Takes JSON on stdin, outputs resampled grids + delta-t on stdout.
 * Every channel goes through the SAME computeKeepIndices → resample
 * path that the web JS uses, so the Python coaching engine gets
 * exactly the same values the user sees on screen.
 *
 * Pipeline (matches product/web/js/main.js + pipeline.js):
 *   1. computeKeepIndices  — drop boundary-artifact frames
 *   2. smoothLapTime        — interpolate scoring-rate plateaus (lap_time_s only)
 *   3. resample             — onto 1 m grid (ALL channels)
 *   4. forward-clamp         — non-decreasing (lap_time_s only)
 *   5. computeDeltaT         — session − reference
 *   6. smoothDt              — spatial moving average (±20 m)
 *
 * Input format:
 *   {
 *     "driver": {
 *       "lap_time_s": [...], "lap_distance_m": [...],
 *       "speed_kph": [...],
 *       "throttle_norm": [...] | null,
 *       "brake_norm": [...] | null
 *     },
 *     "reference": {
 *       "lap_time_s": [...], "lap_distance_m": [...],
 *       "speed_kph": [...]
 *     },
 *     "trackLength": 4680
 *   }
 *
 * Output format:
 *   {
 *     "delta_t_ms": [...],
 *     "driver_speed_kph": [...],
 *     "ref_speed_kph": [...],
 *     "driver_throttle_norm": [...] | null,
 *     "driver_brake_norm": [...] | null,
 *     "track_length": <int>
 *   }
 *
 * Run:
 *   echo '...' | node dev/scripts/compute_delta_t.mjs
 */
import {
  computeKeepIndices,
  smoothLapTime,
  resample,
  computeDeltaT,
  smoothDt,
} from '../../product/web/js/pipeline.js';

import { readFileSync } from 'fs';

// ── Helpers ──────────────────────────────────────────────────────────────────

function isFiniteArray(arr) {
  return arr && Array.isArray(arr) && arr.length > 0;
}

// ── Parse input ──────────────────────────────────────────────────────────────

const input = JSON.parse(readFileSync('/dev/stdin', 'utf8'));
const { driver, reference, trackLength } = input;

// ── Step 1: computeKeepIndices ───────────────────────────────────────────────

const sKeep = computeKeepIndices(
  driver.lap_time_s, driver.lap_distance_m,
  0, driver.lap_time_s.length, trackLength,
);
const rKeep = computeKeepIndices(
  reference.lap_time_s, reference.lap_distance_m,
  0, reference.lap_time_s.length, trackLength,
);

// Build filtered distance arrays (same as web JS sDistRaw / rDistRaw)
const sDistRaw = sKeep.map(i => driver.lap_distance_m[i]);
const rDistRaw = rKeep.map(i => reference.lap_distance_m[i]);

const sMax = sDistRaw.length ? Math.ceil(Math.max(...sDistRaw)) : 0;
const rMax = rDistRaw.length ? Math.ceil(Math.max(...rDistRaw)) : 0;
const maxDist = Math.max(sMax, rMax);

// ── Step 2: smoothLapTime (lap_time_s only) ───────────────────────────────────

const sSmoothed = smoothLapTime(driver.lap_time_s, sKeep);
const rSmoothed = smoothLapTime(reference.lap_time_s, rKeep);

// ── Step 3: resample ALL channels onto 1 m grid ───────────────────────────────

const sLapTimeBins = resample(sDistRaw, sSmoothed, maxDist);
const rLapTimeBins = resample(rDistRaw, rSmoothed, maxDist);

// Speed (both driver and reference)
const sSpeedBins = isFiniteArray(driver.speed_kph)
  ? resample(sDistRaw, sKeep.map(i => driver.speed_kph[i]), maxDist)
  : new Float64Array(maxDist + 1);
const rSpeedBins = isFiniteArray(reference.speed_kph)
  ? resample(rDistRaw, rKeep.map(i => reference.speed_kph[i]), maxDist)
  : new Float64Array(maxDist + 1);

// Driver pedal channels (optional)
const sThrottleBins = isFiniteArray(driver.throttle_norm)
  ? resample(sDistRaw, sKeep.map(i => driver.throttle_norm[i]), maxDist)
  : null;
const sBrakeBins = isFiniteArray(driver.brake_norm)
  ? resample(sDistRaw, sKeep.map(i => driver.brake_norm[i]), maxDist)
  : null;

// ── Step 4: forward-clamp (lap_time_s only) ───────────────────────────────────

for (let d = 1; d < sLapTimeBins.length; d++) {
  if (sLapTimeBins[d] < sLapTimeBins[d - 1]) sLapTimeBins[d] = sLapTimeBins[d - 1];
}
for (let d = 1; d < rLapTimeBins.length; d++) {
  if (rLapTimeBins[d] < rLapTimeBins[d - 1]) rLapTimeBins[d] = rLapTimeBins[d - 1];
}

// ── Step 5: computeDeltaT ─────────────────────────────────────────────────────

const dtRaw = computeDeltaT(sLapTimeBins, rLapTimeBins);

// ── Step 6: smoothDt ──────────────────────────────────────────────────────────

const dtSmoothed = smoothDt(dtRaw, 20);

// ── Output ────────────────────────────────────────────────────────────────────

const output = {
  delta_t_ms: Array.from(dtSmoothed),
  driver_speed_kph: Array.from(sSpeedBins),
  ref_speed_kph: Array.from(rSpeedBins),
  driver_throttle_norm: sThrottleBins ? Array.from(sThrottleBins) : null,
  driver_brake_norm: sBrakeBins ? Array.from(sBrakeBins) : null,
  track_length: maxDist,
};
process.stdout.write(JSON.stringify(output) + '\n');