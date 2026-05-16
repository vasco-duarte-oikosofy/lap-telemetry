/**
 * Infer short one-sided missing boundary widths from nearby total track width.
 */

'use strict';

const DEFAULT_CONFIDENCE = 0.35;

function activeWidth(sample, side, useSmooth) {
  const rawKey = `${side}_width_m`;
  const smoothKey = `${side}_width_smooth_m`;
  return useSmooth ? (sample[smoothKey] ?? sample[rawKey] ?? 0) : (sample[rawKey] ?? 0);
}

function isPositiveFinite(value) {
  return Number.isFinite(value) && value > 0;
}

function isCompleteHighConfidence(sample, useSmooth) {
  const left = activeWidth(sample, 'left', useSmooth);
  const right = activeWidth(sample, 'right', useSmooth);
  if (!isPositiveFinite(left) || !isPositiveFinite(right)) return false;
  return sample.status === 'complete' || (sample.confidence ?? 0) >= 0.75;
}

function median(values) {
  if (values.length === 0) return null;
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function oneSidedMissing(sample, useSmooth) {
  const left = activeWidth(sample, 'left', useSmooth);
  const right = activeWidth(sample, 'right', useSmooth);
  if (!isPositiveFinite(left) && isPositiveFinite(right)) return 'left';
  if (!isPositiveFinite(right) && isPositiveFinite(left)) return 'right';
  return null;
}

function localCompleteTotals(samples, index, window, useSmooth) {
  const totals = [];
  for (let offset = -window; offset <= window; offset++) {
    if (offset === 0) continue;
    const ni = index + offset;
    if (ni < 0 || ni >= samples.length) continue;
    const sample = samples[ni];
    if (!isCompleteHighConfidence(sample, useSmooth)) continue;
    totals.push(activeWidth(sample, 'left', useSmooth) + activeWidth(sample, 'right', useSmooth));
  }
  return totals;
}

function inferRun(result, start, end, side, opts, summary) {
  if (end - start > opts.maxRun) return;

  for (let index = start; index < end; index++) {
    const sample = result[index];
    const totals = localCompleteTotals(result, index, opts.window, opts.useSmooth);
    if (totals.length < opts.minCompleteNeighbors) continue;

    const localTotalWidth = median(totals);
    const otherSide = side === 'left' ? 'right' : 'left';
    const otherWidth = activeWidth(sample, otherSide, opts.useSmooth);
    const inferredWidth = localTotalWidth - otherWidth;
    if (!isPositiveFinite(inferredWidth)) continue;

    sample[`${side}_width_inferred_m`] = inferredWidth;
    sample[`${side}_inferred`] = true;
    sample.inferred = true;
    sample.inferred_status = 'inferred-one-sided';
    sample.inferred_confidence = DEFAULT_CONFIDENCE;
    summary[`inferred_${side}_widths`]++;
  }
}

function inferMissingWidths(profileSamples, options = {}) {
  const opts = {
    window: options.window ?? 10,
    maxRun: options.maxRun ?? 10,
    minCompleteNeighbors: options.minCompleteNeighbors ?? 2,
    useSmooth: options.useSmooth ?? false,
  };

  const result = profileSamples.map(s => ({ ...s }));
  const summary = { inferred_left_widths: 0, inferred_right_widths: 0 };

  let i = 0;
  while (i < result.length) {
    const side = oneSidedMissing(result[i], opts.useSmooth);
    if (!side) { i++; continue; }

    const start = i;
    while (i < result.length && oneSidedMissing(result[i], opts.useSmooth) === side) i++;
    inferRun(result, start, i, side, opts, summary);
  }

  return { samples: result, summary };
}

module.exports = { inferMissingWidths, DEFAULT_INFERRED_CONFIDENCE: DEFAULT_CONFIDENCE };
