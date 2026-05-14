// ── Debug hooks for Playwright and browser-console verification ──────────────

function syncFeatureFlagMenuLabels(features) {
  const menu = document.getElementById('feature-flag-menu');
  if (!menu) return;
  for (const option of menu.options) {
    if (option.value && features[option.value] !== undefined) {
      option.textContent = `${features[option.value] ? '✓' : '○'} ${option.value}`;
    }
  }
}

export function installDebugHooks(deps) {
  const {
    store, features, devFeatures, resample, smoothLapTime, smoothDt, computeDeltaT,
    computeKeepIndices, fitToView, setFeatureFlag, setDevFeatureFlag, renderTrackHeatmapMap,
  } = deps;

  window.__features = features;
  window.__devFeatures = devFeatures;
  window.__getSessionKeys = () => [...store.keys()];

  window.__resamplerDebug = function(storeKeyStr, segIdx) {
    const entry = store.get(storeKeyStr);
    if (!entry) throw new Error(`store key not found: ${storeKeyStr}`);
    const seg = entry.segments[segIdx];
    const dists = Array.from(entry.data.lap_distance_m.slice(seg.start, seg.end));
    const speeds = Array.from(entry.data.speed_kph.slice(seg.start, seg.end));
    const maxD = Math.ceil(Math.max(...dists));
    return Array.from(resample(dists, speeds, maxD));
  };

  window.__refResamplerDebug = function(storeKeyStr, segIdx) {
    return window.__resamplerDebug(storeKeyStr, segIdx);
  };

  window.__dtDebug = function(sessionKey, sessionSeg, refKey, refSeg) {
    const se = store.get(sessionKey);
    const re = store.get(refKey);
    if (!se || !re) throw new Error('store keys not found');
    const sSeg = se.segments[sessionSeg];
    const rSeg = re.segments[refSeg];
    const sTrackLen = se.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
    const rTrackLen = re.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
    const sKeep = computeKeepIndices(se.data.lap_time_s, se.data.lap_distance_m, sSeg.start, sSeg.end, sTrackLen);
    const rKeep = computeKeepIndices(re.data.lap_time_s, re.data.lap_distance_m, rSeg.start, rSeg.end, rTrackLen);
    const sDist = sKeep.map(i => se.data.lap_distance_m[i]);
    const rDist = rKeep.map(i => re.data.lap_distance_m[i]);
    const maxD = Math.max(Math.ceil(Math.max(...sDist)), Math.ceil(Math.max(...rDist)));
    const sBins = resample(sDist, smoothLapTime(se.data.lap_time_s, sKeep), maxD);
    const rBins = resample(rDist, smoothLapTime(re.data.lap_time_s, rKeep), maxD);
    return Array.from(smoothDt(computeDeltaT(sBins, rBins)));
  };

  window.__dtDebugOverlap = function(sessionKey, sessionSeg, refKey, refSeg) {
    const se = store.get(sessionKey);
    const re = store.get(refKey);
    if (!se || !re) throw new Error('store keys not found');
    const sSeg = se.segments[sessionSeg];
    const rSeg = re.segments[refSeg];
    const sTrackLen = se.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
    const rTrackLen = re.segments.reduce((m, s) => Math.max(m, s.maxDist || 0), 0);
    const sKeep = computeKeepIndices(se.data.lap_time_s, se.data.lap_distance_m, sSeg.start, sSeg.end, sTrackLen);
    const rKeep = computeKeepIndices(re.data.lap_time_s, re.data.lap_distance_m, rSeg.start, rSeg.end, rTrackLen);
    const sDist = sKeep.map(i => se.data.lap_distance_m[i]);
    const rDist = rKeep.map(i => re.data.lap_distance_m[i]);
    return {
      start: Math.max(Math.min(...sDist), Math.min(...rDist)),
      end: Math.min(Math.ceil(Math.max(...sDist)), Math.ceil(Math.max(...rDist))),
    };
  };

  window.__setFeatureFlag = (name, value) => {
    setFeatureFlag(name, value);
    syncFeatureFlagMenuLabels(features);
    if (name === 'mapWalkingSkeleton' || name === 'mapTrackOutline' || name === 'mapHeatmapSingleLap' || name === 'mapSAlignment') {
      renderTrackHeatmapMap();
    }
  };

  window.__setDevFeatureFlag = (name, value) => {
    setDevFeatureFlag(name, value);
    if (name === 'devMapSAlignmentDebug') {
      renderTrackHeatmapMap();
    }
  };

  window.__fitToView = function(bounds, w, h, padding) {
    const r = fitToView(bounds, bounds, w, h, padding);
    return { scale: r.scale, offsetX: r.offsetX, offsetY: r.offsetY };
  };

  window.__setFeatureFlagMenuEnabled = function(enabled) {
    const menu = document.getElementById('feature-flag-menu');
    if (menu) menu.style.display = enabled ? '' : 'none';
  };
}
