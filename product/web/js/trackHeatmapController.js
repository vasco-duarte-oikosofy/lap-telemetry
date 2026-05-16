import { features, devFeatures } from './appState.js';
import { computeTrackBounds } from './pipeline.js';
import { createMapHover } from './mapHover.js';
import { createMapInteraction, setBaseTransform } from './mapInteraction.js';
import { renderWalkingSkeleton, initTrackHeatmapResize, fitToView, getLastTransform, computeSegmentBounds } from './trackHeatmapMap.js';


export function createTrackHeatmapController(getMapState) {
  let trackHeatmapObserver = null;
  let mapInteraction = null;
  let mapHover = null;
  let rendering = false;
  let prevAutoZoomRange = null; // track previous range to detect changes

  function getCssColor(name, fallback) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  }

  function buildLaps(sessionColor, refColor) {
    const {
      currentTrackX, currentTrackZ, currentRefTrackX, currentRefTrackZ,
      currentSessionBins, currentRefBins, currentLapARaw, currentLapBRaw,
    } = getMapState();
    return {
      lapA: {
        x: currentTrackX,
        z: currentTrackZ,
        throttle: currentSessionBins?.throttle_norm,
        brake: currentSessionBins?.brake_norm,
        color: sessionColor,
        raw: currentLapARaw,
      },
      lapB: {
        x: currentRefTrackX,
        z: currentRefTrackZ,
        throttle: currentRefBins?.throttle_norm,
        brake: currentRefBins?.brake_norm,
        color: refColor,
        raw: currentLapBRaw,
      },
    };
  }

  function buildOpts({ respectZoomFlag = true, includeMapSAlignment = true, autoZoomBounds = null } = {}) {
    const { currentZoomRange, currentTrackName } = getMapState();
    const s = (!respectZoomFlag || features.mapZoomPan) && mapInteraction
      ? mapInteraction.getState()
      : { scale: 1, tx: 0, ty: 0 };

    return {
      showHeatmapSingleLap: !!features.mapHeatmapSingleLap,
      showSAlignmentDebug: (includeMapSAlignment && !!features.mapSAlignment) || !!devFeatures.devMapSAlignmentDebug,
      showDualRibbon: !!features.mapDualRibbon,
      showLegend: !!features.mapLegend,
      showHover: !!features.mapHover,
      hoverState: mapHover ? mapHover.getState() : null,
      showLinkedHighlight: !!features.mapLinkedHighlight,
      visibleRange: currentZoomRange,
      ribbonWidthPx: 8,
      ribbonGapPx: 2,
      userScale: s.scale,
      userPanX: s.tx,
      userPanY: s.ty,
      showStaticOutline: true,
      trackName: currentTrackName,
      autoZoomBounds,
    };
  }

  function render() {
    if (rendering) return;
    rendering = true;
    try {
      _render();
    } finally {
      rendering = false;
    }
  }

  function _render() {
    const canvas = document.getElementById('track-heatmap-canvas');
    const svg = document.getElementById('circuit-map-svg');
    if (!canvas || !svg) return;

    const anyMapFeature = features.mapWalkingSkeleton || features.mapHeatmapSingleLap || features.mapSAlignment || features.mapDualRibbon || features.mapZoomPan || features.mapLegend || features.mapHover || features.mapLinkedHighlight || true; // static outline always prefers canvas
    if (!anyMapFeature) {
      canvas.style.display = 'none';
      svg.style.display = '';
      return;
    }

    canvas.style.display = '';
    svg.style.display = 'none';

    if (features.mapZoomPan && !mapInteraction) {
      let indicator = document.getElementById('map-zoom-indicator');
      if (!indicator) {
        indicator = document.createElement('span');
        indicator.id = 'map-zoom-indicator';
        indicator.className = 'map-zoom-indicator';
        indicator.textContent = '1.0×';
        const panel = document.getElementById('circuit-map-panel');
        if (panel) panel.appendChild(indicator);
      }
      mapInteraction = createMapInteraction(canvas, () => render());
    }

    if (features.mapHover && !mapHover) {
      mapHover = createMapHover(canvas, () => {
        const sessionColor = getCssColor('--session', '#4fc3f7');
        const refColor = getCssColor('--ref', '#ff9800');
        return {
          ...buildLaps(sessionColor, refColor),
          transform: getLastTransform(),
        };
      }, () => render());
    }

    const { currentTrackX, currentTrackZ, currentRefTrackX, currentRefTrackZ } = getMapState();
    if (!currentTrackX || !currentTrackZ || !currentRefTrackX || !currentRefTrackZ) return;

    const sessionColor = getCssColor('--session', '#4fc3f7');
    const refColor = getCssColor('--ref', '#ff9800');
    const { lapA, lapB } = buildLaps(sessionColor, refColor);

    // F16: Compute auto-zoom bounds before rendering.
    // When mapAutoZoom is on and a zoom range is selected (not full-track),
    // compute the padded segment bounds so renderWalkingSkeleton zooms into
    // that segment. When no range is selected, autoZoomBounds is null and
    // the map renders the full track as usual.
    //
    // Bug 10 fix: only reset the user pan/zoom transform when the zoom
    // range actually changes, so that manual pan/zoom composes on top
    // of the auto-zoomed view instead of being stomped on every render.
    let autoZoomBounds = null;
    let autoZooming = false;
    const { currentZoomRange } = getMapState();
    const rangeKey = currentZoomRange ? `${currentZoomRange.start}:${currentZoomRange.end}` : null;
    const rangeChanged = rangeKey !== prevAutoZoomRange;
    // Detect transition from auto-zoomed to full-track (user cleared selection)
    const wasAutoZoomed = prevAutoZoomRange !== null;
    const isNowFullTrack = rangeKey === null || rangeKey === '0:4650'; // approximate
    const deactivating = wasAutoZoomed && !autoZooming; // set below after compute
    if (features.mapAutoZoom && lapA && lapA.x) {
      const segBounds = computeSegmentBounds(lapA, currentZoomRange);
      if (segBounds) {
        autoZooming = true;
        const dx = (segBounds.maxX - segBounds.minX) || 1;
        const dz = (segBounds.maxZ - segBounds.minZ) || 1;
        autoZoomBounds = {
          minX: segBounds.minX - dx * 0.1,
          maxX: segBounds.maxX + dx * 0.1,
          minZ: segBounds.minZ - dz * 0.1,
          maxZ: segBounds.maxZ + dz * 0.1,
        };
        // Only reset user transform when the range changes, not every render.
        // This lets the user pan/zoom on top of auto-zoom.
        if (rangeChanged && mapInteraction) mapInteraction.setState({ scale: 1, tx: 0, ty: 0 });
      }
    }
    // When auto-zoom deactivates (range cleared or became full-track),
    // reset user pan/zoom so the map snaps back to full-track.
    if (!autoZooming && wasAutoZoomed && rangeChanged && mapInteraction) {
      mapInteraction.setState({ scale: 1, tx: 0, ty: 0 });
    }
    prevAutoZoomRange = rangeKey;

    renderWalkingSkeleton(canvas, lapA, lapB, buildOpts({ autoZoomBounds }));

    if (mapHover) mapHover.rebuild();

    // Set base transform for user zoom/pan reference.
    // When auto-zoom is active, use the segment bounds so future manual
    // zoom (if any) is relative to the auto-zoomed view. Otherwise use
    // the full-track bounds as usual.
    if (autoZooming) {
      const rect = canvas.getBoundingClientRect();
      const tf = fitToView(autoZoomBounds, autoZoomBounds, rect.width, rect.height, 15);
      setBaseTransform(tf);
    } else if (features.mapZoomPan) {
      const boundsA = computeTrackBounds(Array.from(lapA.x), Array.from(lapA.z));
      const boundsB = computeTrackBounds(Array.from(lapB.x), Array.from(lapB.z));
      const rect = canvas.getBoundingClientRect();
      const tf = fitToView(boundsA, boundsB, rect.width, rect.height, 15);
      setBaseTransform(tf);
    }

    if (!trackHeatmapObserver) {
      trackHeatmapObserver = initTrackHeatmapResize(canvas, () => {
        const { currentTrackX, currentRefTrackX } = getMapState();
        if (!currentTrackX || !currentRefTrackX) return null;
        const sColor = getCssColor('--session', '#4fc3f7');
        const rColor = getCssColor('--ref', '#ff9800');
        return buildLaps(sColor, rColor);
      }, () => buildOpts({ respectZoomFlag: false, includeMapSAlignment: false }));
    }
  }

  return {
    render,
    getMapInteractionState: () => mapInteraction?.getState() ?? null,
    getMapHoverState: () => mapHover?.getState() ?? null,
  };
}