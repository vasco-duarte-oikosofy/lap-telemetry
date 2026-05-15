/**
 * Width profile interpolation and smoothing.
 *
 * Takes raw samples (from buildProfileFromRows) and produces render-ready
 * smoothed values while preserving raw data in separate fields.
 *
 * Constants:
 *   MAX_INTERPOLATE_GAP = 10  — max consecutive missing bins to interpolate (meters at bin_size=1)
 *   SMOOTH_WINDOW = 5        — moving-average half-window (bins on each side)
 */

'use strict';

const MAX_INTERPOLATE_GAP = 10;
const SMOOTH_WINDOW = 5;

/**
 * Linearly interpolate across short gaps, then apply moving-average smoothing.
 * Returns a new array of samples with `left_width_smooth_m` and
 * `right_width_smooth_m` fields added. Raw fields are untouched.
 *
 * Missing bins in gaps shorter than MAX_INTERPOLATE_GAP get interpolated
 * widths. Missing bins in longer gaps keep width 0 and are not smoothed across.
 */
function interpolateAndSmooth(samples, opts = {}) {
  const maxGap = opts.maxInterpolateGap ?? MAX_INTERPOLATE_GAP;
  const window = opts.smoothWindow ?? SMOOTH_WINDOW;

  if (samples.length === 0) return [];

  // Deep-copy samples so we don't mutate the originals
  const result = samples.map(s => ({
    ...s,
    left_width_interpolated_m: s.left_width_m,
    right_width_interpolated_m: s.right_width_m,
  }));

  // ── Step 1: Interpolate short gaps ──

  // Identify runs of consecutive missing bins
  let i = 0;
  while (i < result.length) {
    if (result[i].status !== 'missing') { i++; continue; }

    // Find end of this missing run
    const gapStart = i;
    while (i < result.length && result[i].status === 'missing') i++;
    const gapEnd = i; // exclusive

    const gapLen = gapEnd - gapStart;
    if (gapLen > maxGap) continue; // long gap — skip interpolation

    // Find bounding non-missing neighbors
    const before = gapStart > 0 ? result[gapStart - 1] : null;
    const after = gapEnd < result.length ? result[gapEnd] : null;

    for (let j = gapStart; j < gapEnd; j++) {
      if (before && after) {
        const t = (j - gapStart + 1) / (gapEnd - gapStart + 1);
        result[j].left_width_interpolated_m = before.left_width_m + t * (after.left_width_m - before.left_width_m);
        result[j].right_width_interpolated_m = before.right_width_m + t * (after.right_width_m - before.right_width_m);
      } else if (before) {
        // Only left neighbor — extend its value
        result[j].left_width_interpolated_m = before.left_width_m;
        result[j].right_width_interpolated_m = before.right_width_m;
      } else if (after) {
        // Only right neighbor — extend its value
        result[j].left_width_interpolated_m = after.left_width_m;
        result[j].right_width_interpolated_m = after.right_width_m;
      }
    }
  }

  // ── Step 2: Moving-average smoothing ──

  // Identify long-gap boundaries so we don't smooth across them.
  // A bin is a "barrier" if it's missing and in a long gap or has no data.
  const isBarrier = result.map(s => s.status === 'missing' && s.left_width_interpolated_m === 0 && s.right_width_interpolated_m === 0);

  for (let idx = 0; idx < result.length; idx++) {
    const sample = result[idx];

    // Skip long-gap missing bins: smoothed = 0
    if (isBarrier[idx]) {
      sample.left_width_smooth_m = 0;
      sample.right_width_smooth_m = 0;
      continue;
    }

    let leftSum = 0, rightSum = 0, count = 0;
    for (let w = -window; w <= window; w++) {
      const ni = idx + w;
      if (ni < 0 || ni >= result.length) continue;
      if (isBarrier[ni]) continue; // don't average across long gaps
      leftSum += result[ni].left_width_interpolated_m;
      rightSum += result[ni].right_width_interpolated_m;
      count++;
    }

    sample.left_width_smooth_m = count > 0 ? leftSum / count : 0;
    sample.right_width_smooth_m = count > 0 ? rightSum / count : 0;
  }

  return result;
}

module.exports = { interpolateAndSmooth, MAX_INTERPOLATE_GAP, SMOOTH_WINDOW };