# Learnings — U6 Linked Hover

- The reusable unit is `mapHover.js`, not `drawHoverTick()` alone. Reusing only the
  drawing primitive produced a tick but skipped the readout, which was the user-
  visible bug.
- DRY at the feature level means there should be one hover-state/readout pipeline.
  Direct map hover and chart-linked hover now both end in the same
  `mapHover` state shape: `{ s, screenX, screenY, lapASample, lapBSample, nearest }`.
- `trackHeatmapMap.js` should not know where hover came from. Keeping one
  `options.hoverState` branch made the renderer simpler and removed the need for
  `showLinkedHover` / `linkedHoverState` options.
- `state.linkedHoverDist` was unnecessary coupling. A chart hover distance is
  transient interaction input, so it belongs inside the hover controller that owns
  hover UI state.
- `cursor.js` is cleaner when it only reports chart cursor distance. It does not
  need feature-flag checks or map-render knowledge; the map controller decides
  whether the distance has any effect.
- Direct-hover priority is easiest when `mapHover.js` tracks whether the map
  pointer is active. Linked distance can be stored while direct hover is active,
  then applied after pointer leave.
- The regression test needed to assert the readout text, not just hover state or
  pixels. The original failure mode was specifically “tick without the box”.
