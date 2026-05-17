// ── Cursor, tooltip, and zoom interaction ─────────────────────────────────────

import { state, features, getCurrentMapMode, setCurrentMapMode } from './appState.js';
import { PAD, SVG_W, PLOT_W } from './constants.js';
import { renderCircuitMap } from './circuitMap.js';
import { persistZoom } from './utils.js';

/**
 * Set up cursor, tooltip, and zoom handlers on the plot area.
 * Called once at app initialization.
 *
 * @param {Function} renderAll — callback to re-render all panels on zoom
 * @param {Function} getRenderState — callback returning current render state:
 *   { currentSessionBins, currentRefBins, currentZoomRange, currentOverlapRange,
 *     currentTrackX, currentTrackZ, trackTransform, currentDtBins, maxDist }
 */
export function initCursorAndZoom(renderAll, getRenderState, renderMap) {
  const plotArea = document.getElementById('plot-area');
  const cursorLine = document.getElementById('cursor-line');
  const tooltip = document.getElementById('tooltip');
  let linkedHoverRafId = null;
  let lastLinkedHoverDist = null;

  function clearLinkedHover() {
    if (state.linkedHoverDist !== null) {
      state.linkedHoverDist = null;
      lastLinkedHoverDist = null;
      if (renderMap) renderMap();
    }
  }

  function updateCursorDot(binIdx) {
    const { currentTrackX, currentTrackZ, trackTransform } = getRenderState();
    const cursorDot = document.getElementById('cursor-dot');
    if (!cursorDot || !currentTrackX || !currentTrackZ || !trackTransform) {
      if (cursorDot) cursorDot.style.display = 'none';
      return;
    }

    if (binIdx === null || !isFinite(currentTrackX[binIdx]) || !isFinite(currentTrackZ[binIdx])) {
      cursorDot.style.display = 'none';
      return;
    }

    const mapX = trackTransform.toMapX(currentTrackX[binIdx]);
    const mapZ = trackTransform.toMapZ(currentTrackZ[binIdx]);
    cursorDot.setAttribute('cx', mapX.toFixed(1));
    cursorDot.setAttribute('cy', mapZ.toFixed(1));
    cursorDot.style.display = 'block';
  }

  function updateCursorPosition(e) {
    const { currentSessionBins, currentRefBins, currentZoomRange, currentOverlapRange, currentDtBins } = getRenderState();
    if (!currentSessionBins) return;
    const rect = plotArea.getBoundingClientRect();
    const mx = e.clientX - rect.left;

    // Find the SVG plot left edge (PAD.left px into each SVG)
    const firstSvg = plotArea.querySelector('.panel-svg');
    if (!firstSvg) return;
    const svgRect = firstSvg.getBoundingClientRect();
    const svgLeft = svgRect.left - rect.left;
    const svgWidth = svgRect.width;
    const plotLeft = svgLeft + PAD.left * (svgWidth / SVG_W);
    const plotRight = svgLeft + (PAD.left + PLOT_W) * (svgWidth / SVG_W);

    if (mx < plotLeft || mx > plotRight) {
      cursorLine.style.transform = 'translateX(-9999px)';
      tooltip.style.display = 'none';
      updateCursorDot(null);
      clearLinkedHover();
      return;
    }

    cursorLine.style.transform = `translateX(${mx}px)`;

    const zRange = currentZoomRange.end - currentZoomRange.start;
    const fracX = (mx - plotLeft) / (plotRight - plotLeft);
    const dist = currentZoomRange.start + fracX * zRange;
    const binIdx = Math.max(0, Math.min(Math.round(dist), state.maxDist));

    // Update cursor dot on circuit map
    updateCursorDot(binIdx);

    // Linked hover: update map tick at chart cursor distance
    if (features.mapHover && features.mapLinkedHover && binIdx !== lastLinkedHoverDist) {
      state.linkedHoverDist = binIdx;
      lastLinkedHoverDist = binIdx;
      if (!linkedHoverRafId && renderMap) {
        linkedHoverRafId = requestAnimationFrame(() => {
          linkedHoverRafId = null;
          renderMap();
        });
      }
    }

    // Tooltip
    const sSpeed = currentSessionBins.speed_kph?.[binIdx];
    const rSpeed = currentRefBins.speed_kph?.[binIdx];
    // Mask Δt outside the overlap: bins beyond the data range of either lap
    // carry only the lap_time_s clamp value, not a real comparison.
    const inOverlap = currentOverlapRange
      && binIdx >= Math.ceil(currentOverlapRange.start)
      && binIdx <= Math.floor(currentOverlapRange.end);
    const sDt = inOverlap ? currentDtBins?.[binIdx] : null;
    const sThrottle = currentSessionBins.throttle_norm?.[binIdx];
    const sBrake = currentSessionBins.brake_norm?.[binIdx];

    const sAbs = currentSessionBins.abs_active?.[binIdx];
    const sTc = currentSessionBins.tc_active?.[binIdx];
    const flags = [
      (sAbs != null && sAbs >= 0.5) ? 'ABS' : null,
      (sTc != null && sTc >= 0.5) ? 'TC' : null,
    ].filter(Boolean);

    const lines = [
      `dist: ${binIdx} m`,
      sSpeed != null ? `speed: ${sSpeed.toFixed(1)} / ${rSpeed?.toFixed(1) ?? '—'} km/h` : '',
      sThrottle != null ? `thr:   ${(sThrottle * 100).toFixed(0)}%   brk: ${((sBrake ?? 0) * 100).toFixed(0)}%` : '',
      sDt != null ? `Δt:   ${sDt > 0 ? '+' : ''}${sDt.toFixed(0)} ms` : '',
      flags.length ? `active: ${flags.join(', ')}` : '',
    ].filter(Boolean);

    tooltip.textContent = lines.join('\n');
    tooltip.style.display = 'block';
    const tx = Math.min(mx + 14, rect.width - 180);
    // Tooltip Y position follows cursor vertically, clamped inside plot-area
    const ty = Math.max(8, Math.min(e.clientY - rect.top - 30, rect.height - 130));
    tooltip.style.left = `${tx}px`;
    tooltip.style.top = `${ty}px`;
  }

  function getPlotGeometry() {
    const firstSvg = plotArea.querySelector('.panel-svg');
    if (!firstSvg) return null;
    const rect = plotArea.getBoundingClientRect();
    const svgRect = firstSvg.getBoundingClientRect();
    const svgLeft = svgRect.left - rect.left;
    const svgWidth = svgRect.width;
    const plotLeft = svgLeft + PAD.left * (svgWidth / SVG_W);
    const plotRight = svgLeft + (PAD.left + PLOT_W) * (svgWidth / SVG_W);
    return { rect, plotLeft, plotRight };
  }

  function distFromMx(mx, plotLeft, plotRight, zoomRange) {
    const zRange = zoomRange.end - zoomRange.start;
    const fracX = (mx - plotLeft) / (plotRight - plotLeft);
    return zoomRange.start + fracX * zRange;
  }

  // Mousedown — start drag selection
  plotArea.addEventListener('mousedown', e => {
    const { currentZoomRange } = getRenderState();
    if (!currentZoomRange) return;
    const geo = getPlotGeometry();
    if (!geo) return;
    if (e.clientX - geo.rect.left < geo.plotLeft || e.clientX - geo.rect.left > geo.plotRight) return;

    state.dragging = true;
    state.dragStartX = e.clientX - geo.rect.left;
    state.dragStartDist = distFromMx(state.dragStartX, geo.plotLeft, geo.plotRight, currentZoomRange);
    clearLinkedHover();
  });

  // Mousemove — update selection rect or cursor
  plotArea.addEventListener('mousemove', e => {
    const { currentSessionBins, currentZoomRange } = getRenderState();
    if (state.dragging && currentSessionBins && currentZoomRange) {
      const geo = getPlotGeometry();
      if (!geo) {
        updateCursorPosition(e);
        return;
      }

      const mx = e.clientX - geo.rect.left;
      // Update selection rect
      const selRect = document.getElementById('zoom-selection-rect');
      const x1 = Math.max(geo.plotLeft, Math.min(state.dragStartX, mx));
      const x2 = Math.max(geo.plotLeft, Math.min(Math.max(state.dragStartX, mx), geo.plotRight));
      selRect.style.left = `${x1}px`;
      selRect.style.width = `${x2 - x1}px`;
      selRect.classList.add('active');
    } else {
      updateCursorPosition(e);
    }
  });

  // Mouseup — apply zoom or clear selection
  plotArea.addEventListener('mouseup', e => {
    if (!state.dragging) return;
    state.dragging = false;

    const selRect = document.getElementById('zoom-selection-rect');
    selRect.classList.remove('active');
    selRect.style.left = '0';
    selRect.style.width = '0';

    const { currentSessionBins, currentZoomRange, maxDist } = getRenderState();
    if (!currentSessionBins || !currentZoomRange) return;

    const geo = getPlotGeometry();
    if (!geo) return;

    const mx = e.clientX - geo.rect.left;
    const dist2 = distFromMx(mx, geo.plotLeft, geo.plotRight, currentZoomRange);

    const d1 = Math.max(0, Math.min(state.dragStartDist, dist2));
    const d2 = Math.min(maxDist, Math.max(state.dragStartDist, dist2));

    if (d2 - d1 > 10) {  // Only zoom if selection is large enough
      currentZoomRange.start = d1;
      currentZoomRange.end = d2;
      persistZoom(currentZoomRange, maxDist);
      renderAll(...state.currentRenderParams);
    }
  });

  // Double-click — reset zoom
  plotArea.addEventListener('dblclick', e => {
    const { currentSessionBins, currentZoomRange, maxDist } = getRenderState();
    if (!currentSessionBins || !currentZoomRange) return;
    currentZoomRange.start = 0;
    currentZoomRange.end = maxDist;
    persistZoom(currentZoomRange, maxDist);
    renderAll(...state.currentRenderParams);
  });

  // Mouseleave — hide cursor/tooltip
  plotArea.addEventListener('mouseleave', () => {
    if (!state.dragging) {
      cursorLine.style.transform = 'translateX(-9999px)';
      tooltip.style.display = 'none';
      updateCursorDot(null);
      clearLinkedHover();
    }
  });

  // Keyboard shortcut — Escape to reset zoom
  document.addEventListener('keydown', e => {
    const { currentSessionBins, currentZoomRange, maxDist } = getRenderState();
    if (e.key === 'Escape' && currentSessionBins && currentZoomRange) {
      currentZoomRange.start = 0;
      currentZoomRange.end = maxDist;
      persistZoom(currentZoomRange, maxDist);
      renderAll(...state.currentRenderParams);
    }
  });

  // Heatmap mode change — re-render circuit map only
  document.getElementById('map-mode').addEventListener('change', e => {
    setCurrentMapMode(e.target.value);
    const { currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist, currentSessionBins } = getRenderState();
    if (currentSessionBins) {
      renderCircuitMap(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist, currentSessionBins);
    }
  });
}
