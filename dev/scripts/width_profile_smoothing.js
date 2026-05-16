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
 *
 * Smoothing is per-side: a bin's left smooth only averages over neighbors
 * that have left-side data (original or interpolated). One-sided bins with
 * no data on a side do not pull that side's average toward zero.
 */
function interpolateAndSmooth(samples, opts = {}) {
  const maxGap = opts.maxInterpolateGap ?? MAX_INTERPOLATE_GAP;
  const window = opts.smoothWindow ?? SMOOTH_WINDOW;

  if (samples.length === 0) return [];

  // Deep-copy samples so we don't mutate the originals.
  // Use null for sides that have no data, so the smoother can skip them.
  const result = samples.map(s => ({
    ...s,
    has_left: s.left_sample_count > 0,
    has_right: s.right_sample_count > 0,
    left_width_interpolated_m: s.left_sample_count > 0 ? s.left_width_m : null,
    right_width_interpolated_m: s.right_sample_count > 0 ? s.right_width_m : null,
  }));

  // ── Step 1: Interpolate short gaps (missing bins) ──

  let i = 0;
  while (i < result.length) {
    if (result[i].status !== 'missing') { i++; continue; }

    const gapStart = i;
    while (i < result.length && result[i].status === 'missing') i++;
    const gapEnd = i; // exclusive

    if (gapEnd - gapStart > maxGap) continue; // long gap — skip

    // Find bounding non-missing neighbors that have data on each side
    const beforeLeft = gapStart > 0 && result[gapStart - 1].has_left ? result[gapStart - 1].left_width_m : null;
    const beforeRight = gapStart > 0 && result[gapStart - 1].has_right ? result[gapStart - 1].right_width_m : null;
    const afterLeft = gapEnd < result.length && result[gapEnd].has_left ? result[gapEnd].left_width_m : null;
    const afterRight = gapEnd < result.length && result[gapEnd].has_right ? result[gapEnd].right_width_m : null;

    for (let j = gapStart; j < gapEnd; j++) {
      // Left side
      if (beforeLeft != null && afterLeft != null) {
        const t = (j - gapStart + 1) / (gapEnd - gapStart + 1);
        result[j].left_width_interpolated_m = beforeLeft + t * (afterLeft - beforeLeft);
        result[j].has_left = true;
      } else if (beforeLeft != null) {
        result[j].left_width_interpolated_m = beforeLeft;
        result[j].has_left = true;
      } else if (afterLeft != null) {
        result[j].left_width_interpolated_m = afterLeft;
        result[j].has_left = true;
      }
      // Right side (same logic)
      if (beforeRight != null && afterRight != null) {
        const t = (j - gapStart + 1) / (gapEnd - gapStart + 1);
        result[j].right_width_interpolated_m = beforeRight + t * (afterRight - beforeRight);
        result[j].has_right = true;
      } else if (beforeRight != null) {
        result[j].right_width_interpolated_m = beforeRight;
        result[j].has_right = true;
      } else if (afterRight != null) {
        result[j].right_width_interpolated_m = afterRight;
        result[j].has_right = true;
      }
    }
  }

  // ── Step 2: Per-side moving-average smoothing ──

  // Long-gap missing bins with no interpolated data on either side are barriers.
  const isBarrier = result.map(s =>
    s.status === 'missing' && s.left_width_interpolated_m == null && s.right_width_interpolated_m == null
  );

  // Build per-side validity arrays: a bin participates in left smoothing
  // only if it has left data (original or interpolated), and similarly for right.
  const hasLeftData = result.map(s => s.has_left);
  const hasRightData = result.map(s => s.has_right);

  // Collect left-side and right-side interpolated values for efficient averaging
  const leftValues = result.map(s => s.left_width_interpolated_m ?? 0);
  const rightValues = result.map(s => s.right_width_interpolated_m ?? 0);

  for (let idx = 0; idx < result.length; idx++) {
    const sample = result[idx];

    if (isBarrier[idx]) {
      sample.left_width_smooth_m = 0;
      sample.right_width_smooth_m = 0;
      continue;
    }

    // Left side: only average over bins that have left data
    let leftSum = 0, leftCount = 0;
    for (let w = -window; w <= window; w++) {
      const ni = idx + w;
      if (ni < 0 || ni >= result.length) continue;
      if (isBarrier[ni] || !hasLeftData[ni]) continue;
      leftSum += leftValues[ni];
      leftCount++;
    }
    sample.left_width_smooth_m = leftCount > 0 ? leftSum / leftCount : 0;

    // Right side: only average over bins that have right data
    let rightSum = 0, rightCount = 0;
    for (let w = -window; w <= window; w++) {
      const ni = idx + w;
      if (ni < 0 || ni >= result.length) continue;
      if (isBarrier[ni] || !hasRightData[ni]) continue;
      rightSum += rightValues[ni];
      rightCount++;
    }
    sample.right_width_smooth_m = rightCount > 0 ? rightSum / rightCount : 0;
  }

  // Clean up internal fields before returning
  for (const s of result) {
    delete s.has_left;
    delete s.has_right;
    delete s.left_width_interpolated_m;
    delete s.right_width_interpolated_m;
  }

  return result;
}

module.exports = { interpolateAndSmooth, MAX_INTERPOLATE_GAP, SMOOTH_WINDOW };