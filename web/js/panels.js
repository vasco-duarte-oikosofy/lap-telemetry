// ── Panel rendering module ────────────────────────────────────────────────────
// Extracted from main.js (Step 8). Renders telemetry panel SVGs including
// Speed, Throttle, TC, Brake, ABS, RPM, Gear, Steering, Slip, and Δt panels.

import { SVG_W, PAD, PLOT_W } from './constants.js';
import { niceRange, buildPolylinePts, computeNiceYTicks } from './pipeline.js';

/**
 * Render a standard telemetry panel (Speed, Throttle, Brake, etc.).
 * @param {Object} def - Panel definition from PANEL_DEFS
 * @param {Object} bins - Map of channel key to Float64Array bins
 * @param {number} maxDist - Maximum distance for the lap
 * @param {Object} sectorDists - { s1dist, s2dist } sector distances
 * @param {Object} zoomRange - { start, end } zoom range
 * @returns {string} - SVG content for the panel
 */
export function renderPanel(def, bins, maxDist, sectorDists, zoomRange) {
  const H = Math.round(def.height * (def.heightMultiplier ?? 1.0));
  const plotH = H - PAD.top - PAD.bottom;

  // Collect all values WITHIN ZOOM RANGE to determine y range
  const allVals = [];
  const zoomStart = Math.ceil(zoomRange.start);
  const zoomEnd = Math.floor(zoomRange.end);
  for (const { key } of Object.values(bins)) {
    if (key) {
      for (let i = zoomStart; i <= zoomEnd && i < key.length; i++) {
        const v = key[i];
        if (isFinite(v)) allVals.push(v);
      }
    }
  }

  const toX = d => {
    const zRange = zoomRange.end - zoomRange.start;
    if (zRange <= 0) return PAD.left;
    const fracD = (d - zoomRange.start) / zRange;
    return PAD.left + fracD * PLOT_W;
  };
  const toY = (s, yMin, yMax) => PAD.top + plotH - ((s - yMin) / (yMax - yMin)) * plotH;

  const distBins = Array.from({ length: maxDist + 1 }, (_, i) => i);

  let svgContent = `<defs><clipPath id="clip-${def.id}"><rect x="${PAD.left}" y="${PAD.top}" width="${PLOT_W}" height="${plotH}"/></clipPath></defs>`;

  // Grid lines and ticks — adjusted for zoom
  const zRange = zoomRange.end - zoomRange.start;
  const distStep = Math.max(100, Math.ceil(zRange / 6 / 100) * 100);
  const xTicks = [];
  const startTick = Math.ceil(zoomRange.start / distStep) * distStep;
  for (let d = startTick; d <= zoomRange.end; d += distStep) xTicks.push(d);
  svgContent += xTicks.map(d =>
    `<line x1="${toX(d)}" y1="${PAD.top}" x2="${toX(d)}" y2="${PAD.top + plotH}" stroke="var(--border)" stroke-width="0.5" stroke-dasharray="3 3"/>`
  ).join('');

  // Axes
  svgContent += `<line x1="${PAD.left}" y1="${PAD.top}" x2="${PAD.left}" y2="${PAD.top + plotH}" stroke="var(--border)" stroke-width="1"/>`;
  svgContent += `<line x1="${PAD.left}" y1="${PAD.top + plotH}" x2="${PAD.left + PLOT_W}" y2="${PAD.top + plotH}" stroke="var(--border)" stroke-width="1"/>`;

  // X tick labels (only on bottom panel — checked by caller adding class)
  if (def.showXLabels) {
    svgContent += xTicks.map(d => {
      const x = toX(d);
      if (x < PAD.left || x > PAD.left + PLOT_W) return '';
      return `<text x="${x}" y="${PAD.top + plotH + 16}" text-anchor="middle" fill="var(--muted)" font-size="9" font-family="monospace">${d >= 1000 ? (d / 1000).toFixed(1) + 'k' : d}</text>`;
    }).join('');
    svgContent += `<text x="${PAD.left + PLOT_W / 2}" y="${H - 2}" text-anchor="middle" fill="var(--muted)" font-size="9" font-family="monospace">Distance (m)</text>`;
  }

  // Render per-channel bins
  for (const ch of def.channels || []) {
    const key = `${ch.trace}_${ch.col}`;
    const binArr = bins[key];
    if (!binArr) continue;

    // Compute y range from this channel's data (and others in same panel) WITHIN ZOOM RANGE
    const allChVals = [];
    for (const ch2 of def.channels) {
      const k2 = `${ch2.trace}_${ch2.col}`;
      if (bins[k2]) {
        for (let i = zoomStart; i <= zoomEnd && i < bins[k2].length; i++) {
          const v = bins[k2][i];
          if (isFinite(v)) allChVals.push(v);
        }
      }
    }
    const [yMin, yMax] = niceRange(allChVals.filter(isFinite), def.yFixed);
    const toYp = s => toY(s, yMin, yMax);

    // Y ticks (once, same for all channels in panel)
    if (ch === def.channels[0]) {
      const yTicks = def.niceSteps
        ? computeNiceYTicks(yMin, yMax, plotH, def.niceSteps)
        : (() => {
            const t = [], step = def.yStep;
            for (let y = Math.ceil(yMin / step) * step; y <= yMax; y += step) t.push(y);
            return t;
          })();
      svgContent += yTicks.map(y =>
        `<text x="${PAD.left - 5}" y="${toYp(y) + 3}" text-anchor="end" fill="var(--muted)" font-size="9" font-family="monospace">${Number.isInteger(y) ? y : y.toFixed(1)}</text>`
      ).join('');
      svgContent += yTicks.map(y =>
        `<line x1="${PAD.left}" y1="${toYp(y)}" x2="${PAD.left + PLOT_W}" y2="${toYp(y)}" stroke="var(--border)" stroke-width="0.4" stroke-dasharray="3 3"/>`
      ).join('');
      if (def.zeroline) {
        svgContent += `<line x1="${PAD.left}" y1="${toYp(0)}" x2="${PAD.left + PLOT_W}" y2="${toYp(0)}" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>`;
      }
      if (def.midline != null) {
        svgContent += `<line x1="${PAD.left}" y1="${toYp(def.midline)}" x2="${PAD.left + PLOT_W}" y2="${toYp(def.midline)}" stroke="rgba(255,255,255,0.15)" stroke-width="1" stroke-dasharray="4 4"/>`;
      }
      // Store range for cursor tooltip
      def._yMin = yMin; def._yMax = yMax;
    }

    // Suppress all-zero traces — these are placeholders for channels missing
    // from the source (e.g. deltabest CSV's unused throttle/brake/etc.), and
    // drawing them as flat lines at y=0 is misleading. A real racing lap
    // always has at least one nonzero finite sample in any populated channel.
    const hasData = binArr.some && binArr.some(v => v !== 0 && isFinite(v));
    if (hasData) {
      const pts = buildPolylinePts(distBins, Array.from(binArr), toX, toYp, ch.step);
      const strokeDash = ch.dash ? 'stroke-dasharray="6 3"' : '';
      svgContent += `<polyline points="${pts}" fill="none" stroke="${ch.color}" stroke-width="0.9" stroke-linejoin="round" ${strokeDash} clip-path="url(#clip-${def.id})"/>`;
    }
  }

  // Sector markers
  if (sectorDists) {
    for (const [dist, label] of [[sectorDists.s1dist, 'S2'], [sectorDists.s2dist, 'S3']]) {
      if (dist == null || dist < 0 || dist > maxDist) continue;
      const x = toX(dist);
      // Get y range from first channel pair
      const yMin = def._yMin ?? 0, yMax = def._yMax ?? 1;
      svgContent += `<line x1="${x}" y1="${PAD.top}" x2="${x}" y2="${PAD.top + plotH}" stroke="var(--sector-clr)" stroke-width="1" stroke-dasharray="4 4" clip-path="url(#clip-${def.id})"/>`;
      svgContent += `<text x="${x + 3}" y="${PAD.top + 11}" fill="var(--sector-clr)" font-size="9" font-family="monospace">${label}</text>`;
    }
  }

  // Activity strip (M6 F2: ABS on brake panel, TC on throttle panel).
  // Bool channel resampled to 0..1 → rounded at 0.5 → emit one <rect> per
  // contiguous "on" run, clipped to the panel's plot area.
  if (def.activityStrip) {
    const stripBins = bins[`session_${def.activityStrip.col}`];
    if (stripBins && stripBins.length) {
      const stripH = 4;
      const stripY = PAD.top + plotH - stripH;
      let runStart = -1;
      for (let i = 0; i <= stripBins.length; i++) {
        const on = i < stripBins.length && (stripBins[i] >= 0.5);
        if (on && runStart < 0) runStart = i;
        else if (!on && runStart >= 0) {
          const x1 = toX(runStart), x2 = toX(i);
          if (x2 > x1) {
            svgContent += `<rect x="${x1.toFixed(1)}" y="${stripY}" width="${(x2 - x1).toFixed(1)}" height="${stripH}" fill="${def.activityStrip.color}" fill-opacity="0.85" clip-path="url(#clip-${def.id})"/>`;
          }
          runStart = -1;
        }
      }
    }
  }

  return `<svg class="panel-svg" viewBox="0 0 ${SVG_W} ${H}" data-panel-id="${def.id}">${svgContent}</svg>`;
}

/**
 * Render the Δt panel with overlap clipping.
 * @param {Object} def - Panel definition for Δt panel
 * @param {Float64Array} dtBins - Δt bins array
 * @param {number} maxDist - Maximum distance for the lap
 * @param {Object} sectorDists - { s1dist, s2dist } sector distances
 * @param {Object} zoomRange - { start, end } zoom range
 * @param {Object} overlapRange - { start, end } overlap window
 * @returns {string} - SVG content for the Δt panel
 */
export function renderDtPanel(def, dtBins, maxDist, sectorDists, zoomRange, overlapRange) {
  const H = def.height;
  const plotH = H - PAD.top - PAD.bottom;
  // Render only the [overlapStart..overlapEnd] window — bins outside that range
  // carry the resampler's boundary-clamping of lap_time_s, not real data, and
  // would visually swamp the plot if drawn (see rca-deltat-phantom-error.md §7).
  const overlapStart = overlapRange ? Math.max(0, Math.ceil(overlapRange.start)) : 0;
  const overlapEnd   = overlapRange ? Math.min(maxDist, Math.floor(overlapRange.end)) : maxDist;
  
  // Y-axis range is computed from values within BOTH the overlap AND zoom ranges
  const zoomStart = Math.ceil(zoomRange.start);
  const zoomEnd = Math.floor(zoomRange.end);
  const rangeStart = Math.max(overlapStart, zoomStart);
  const rangeEnd = Math.min(overlapEnd, zoomEnd);
  
  const inRangeVals = [];
  for (let i = rangeStart; i <= rangeEnd; i++) {
    if (isFinite(dtBins[i])) inRangeVals.push(dtBins[i]);
  }
  const [yMin, yMax] = niceRange(inRangeVals, def.yFixed);
  def._yMin = yMin; def._yMax = yMax;

  const toX  = d => {
    const zRange = zoomRange.end - zoomRange.start;
    if (zRange <= 0) return PAD.left;
    const fracD = (d - zoomRange.start) / zRange;
    return PAD.left + fracD * PLOT_W;
  };
  const toY  = s => PAD.top + plotH - ((s - yMin) / (yMax - yMin)) * plotH;
  const distBins = Array.from({ length: maxDist + 1 }, (_, i) => i);

  let svg = `<defs><clipPath id="clip-dt"><rect x="${PAD.left}" y="${PAD.top}" width="${PLOT_W}" height="${plotH}"/></clipPath></defs>`;

  const zRange = zoomRange.end - zoomRange.start;
  const distStep = Math.max(100, Math.ceil(zRange / 6 / 100) * 100);
  const xTicks = [];
  const startTick = Math.ceil(zoomRange.start / distStep) * distStep;
  for (let d = startTick; d <= zoomRange.end; d += distStep) xTicks.push(d);
  svg += xTicks.map(d =>
    `<line x1="${toX(d)}" y1="${PAD.top}" x2="${toX(d)}" y2="${PAD.top + plotH}" stroke="var(--border)" stroke-width="0.5" stroke-dasharray="3 3"/>`
  ).join('');
  svg += `<line x1="${PAD.left}" y1="${PAD.top}" x2="${PAD.left}" y2="${PAD.top + plotH}" stroke="var(--border)" stroke-width="1"/>`;
  svg += `<line x1="${PAD.left}" y1="${PAD.top + plotH}" x2="${PAD.left + PLOT_W}" y2="${PAD.top + plotH}" stroke="var(--border)" stroke-width="1"/>`;

  // X labels (this is the last panel)
  svg += xTicks.map(d => {
    const x = toX(d);
    if (x < PAD.left || x > PAD.left + PLOT_W) return '';
    return `<text x="${x}" y="${PAD.top + plotH + 16}" text-anchor="middle" fill="var(--muted)" font-size="9" font-family="monospace">${d >= 1000 ? (d / 1000).toFixed(1) + 'k' : d}</text>`;
  }).join('');
  svg += `<text x="${PAD.left + PLOT_W / 2}" y="${H - 2}" text-anchor="middle" fill="var(--muted)" font-size="9" font-family="monospace">Distance (m)</text>`;

  const yTicks = def.niceSteps
    ? computeNiceYTicks(yMin, yMax, plotH, def.niceSteps)
    : (() => {
        const t = [], step = def.yStep;
        for (let y = Math.ceil(yMin / step) * step; y <= yMax; y += step) t.push(y);
        return t;
      })();
  svg += yTicks.map(y =>
    `<text x="${PAD.left - 5}" y="${toY(y) + 3}" text-anchor="end" fill="var(--muted)" font-size="9" font-family="monospace">${y > 0 ? '+' : ''}${y}</text>`
  ).join('');
  svg += yTicks.map(y =>
    `<line x1="${PAD.left}" y1="${toY(y)}" x2="${PAD.left + PLOT_W}" y2="${toY(y)}" stroke="var(--border)" stroke-width="0.4" stroke-dasharray="3 3"/>`
  ).join('');
  // Reference lap baseline at y=0 (orange dashed, same style as other panels)
  const zeroY = toY(Math.max(yMin, Math.min(yMax, 0)));
  svg += `<polyline points="${PAD.left},${zeroY} ${PAD.left + PLOT_W},${zeroY}" fill="none" stroke="var(--ref)" stroke-width="0.9" stroke-dasharray="6 3" clip-path="url(#clip-dt)"/>`;

  // Δt polyline — session delta vs reference (blue solid). Clipped to overlap.
  const ptsArr = [];
  for (let i = overlapStart; i <= overlapEnd; i++) {
    ptsArr.push(`${toX(i).toFixed(1)},${toY(dtBins[i]).toFixed(1)}`);
  }
  svg += `<polyline points="${ptsArr.join(' ')}" fill="none" stroke="var(--session)" stroke-width="0.9" stroke-linejoin="round" clip-path="url(#clip-dt)"/>`;

  // Sector markers + per-sector Δt readouts (instantaneous Δt at each
  // sector boundary, plus the lap-end value pinned to the right edge).
  const dtAt = (dist) => {
    if (dist == null || dist < overlapStart || dist > overlapEnd) return null;
    const i = Math.max(0, Math.min(Math.round(dist), dtBins.length - 1));
    return dtBins[i];
  };
  const fmtMs = v => `${v >= 0 ? '+' : ''}${v.toFixed(0)} ms`;
  const dtColor = v => v > 5 ? 'var(--dt-pos)' : v < -5 ? 'var(--dt-neg)' : 'var(--muted)';

  if (sectorDists) {
    for (const [dist, label] of [[sectorDists.s1dist, 'S2'], [sectorDists.s2dist, 'S3']]) {
      if (dist == null || dist < 0 || dist > maxDist) continue;
      const x = toX(dist);
      svg += `<line x1="${x}" y1="${PAD.top}" x2="${x}" y2="${PAD.top + plotH}" stroke="var(--sector-clr)" stroke-width="1" stroke-dasharray="4 4" clip-path="url(#clip-dt)"/>`;
      svg += `<text x="${x + 3}" y="${PAD.top + 11}" fill="var(--sector-clr)" font-size="9" font-family="monospace">${label}</text>`;
      const v = dtAt(dist);
      if (v != null && isFinite(v)) {
        svg += `<text x="${x + 3}" y="${PAD.top + 22}" fill="${dtColor(v)}" font-size="9" font-family="monospace" font-weight="600">${fmtMs(v)}</text>`;
      }
    }
  }
  // Lap-end Δt readout pinned to the right of the plot. Use the overlap-end
  // bin — the rightmost bin where BOTH laps still have real data. Reading
  // dtBins[dtBins.length - 1] would land in the clamp region for whichever
  // lap was shorter and produce the (now-fixed) phantom-error symptom.
  const lastDt = dtBins[overlapEnd];
  if (isFinite(lastDt)) {
    svg += `<text x="${PAD.left + PLOT_W - 4}" y="${PAD.top + 11}" text-anchor="end" fill="${dtColor(lastDt)}" font-size="10" font-family="monospace" font-weight="600">end ${fmtMs(lastDt)}</text>`;
  }

  return `<svg class="panel-svg" viewBox="0 0 ${SVG_W} ${H}" data-panel-id="dt">${svg}</svg>`;
}
