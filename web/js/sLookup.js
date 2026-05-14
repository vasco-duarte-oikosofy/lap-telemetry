/**
 * s-lookup helper — cross-lap alignment by distance.
 *
 * Given a lap's distance-sampled arrays, binary-search for the nearest
 * samples around target `s` and linearly interpolate all channels.
 *
 * Lap shape: { s: number[], [key: string]: number[] }
 */

/**
 * Look up an interpolated sample at distance `targetS`.
 * Returns an object with all numeric channels interpolated, or `null`
 * when the lap has no sample data.
 */
export function sLookup(lap, targetS) {
  const sArr = lap.s;
  if (!sArr || sArr.length === 0) return null;
  const len = sArr.length;

  if (len === 1) {
    const r = {};
    for (const key of Object.keys(lap)) r[key] = lap[key][0];
    return r;
  }

  // Clamp to bounds
  if (targetS <= sArr[0]) {
    const r = {};
    for (const key of Object.keys(lap)) r[key] = lap[key][0];
    return r;
  }
  if (targetS >= sArr[len - 1]) {
    const r = {};
    for (const key of Object.keys(lap)) r[key] = lap[key][len - 1];
    return r;
  }

  // Binary search for the right bracket [lo, hi]
  let lo = 0, hi = len - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >>> 1;
    if (sArr[mid] < targetS) lo = mid;
    else hi = mid;
  }

  const s0 = sArr[lo];
  const s1 = sArr[hi];
  const denom = s1 - s0;
  const frac = denom > 0 ? (targetS - s0) / denom : 0;

  const result = {};
  for (const key of Object.keys(lap)) {
    const arr = lap[key];
    if (!Array.isArray(arr) && !(arr instanceof Float64Array) && !(arr instanceof Float32Array)) {
      continue;
    }
    if (arr.length <= hi) continue;
    const v0 = arr[lo];
    const v1 = arr[hi];
    if (!isFinite(v0) || !isFinite(v1)) {
      result[key] = v0;
      continue;
    }
    result[key] = v0 + (v1 - v0) * frac;
  }
  return result;
}

/**
 * Hard-fail when `distances` is not strictly monotonic.
 * Use behind a dev-only guard so production data never crashes the app.
 */
export function assertStrictlyMonotonic(distances, label = 's') {
  for (let i = 1; i < distances.length; i++) {
    if (distances[i] <= distances[i - 1]) {
      const msg = `[sAlignment] ${label} is NOT strictly monotonic at index ${i}: ${distances[i - 1]} → ${distances[i]}`;
      console.error(msg);
      throw new Error(msg);
    }
  }
}
