import { features, devFeatures } from './appState.js';
import { computeTrackBounds } from './pipeline.js';
import { createMapHover } from './mapHover.js';
import { createMapInteraction, setBaseTransform } from './mapInteraction.js';
import { renderWalkingSkeleton, initTrackHeatmapResize, fitToView, getLastTransform } from './trackHeatmapMap.js';

export function createTrackHeatmapController(getMapState) {
  let trackHeatmapObserver = null;
  let mapInteraction = null;
  let mapHover = null;

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

  function buildOpts({ respectZoomFlag = true, includeMapSAlignment = true } = {}) {
    const { currentZoomRange } = getMapState();
    const s = (!respectZoomFlag || features.mapZoomPan) && mapInteraction
      ? mapInteraction.getState()
      : { scale: 1, tx: 0, ty: 0 };
    return {
      showOutline: !!features.mapTrackOutline,
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
    };
  }

  function render() {
    const canvas = document.getElementById('track-heatmap-canvas');
    const svg = document.getElementById('circuit-map-svg');
    if (!canvas || !svg) return;

    const anyMapFeature = features.mapWalkingSkeleton || features.mapTrackOutline || features.mapHeatmapSingleLap || features.mapSAlignment || features.mapDualRibbon || features.mapZoomPan || features.mapLegend || features.mapHover || features.mapLinkedHighlight;
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
    renderWalkingSkeleton(canvas, lapA, lapB, buildOpts());

    if (mapHover) mapHover.rebuild();

    if (features.mapZoomPan) {
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
