# Learnings — Long Beach / TinyPedal

- The coaching model, compare map and TinyPedal labels are separate artifacts.
  Creating the first two does not populate the sibling's packaged turns folder.
- Enumerating existing *.turns.json files cannot catch an omitted new track.
  A specific Long Beach loader/render regression is needed in addition to the
  all-shipped-tracks suite.
- Apex distances and trace arc length are different axes here: simulator lap
  3185.3 m versus jittered geometry 3400.385 m. The old denominator puts late
  turns far before their physical bends. Explicit same-axis metadata fixes this
  without silently changing any of the 14 legacy track exports.
- The TinyPedal recording has world X/-Z whereas compare stores X/Z; this allowed
  a fixture-specific proximity check. Runtime still shares only normalized lap
  distance, not coordinates, preserving the cross-app distance-only contract.
- All 11 simple numbered labels fit at both 400 and 600px in both tested angles.
  No font/layout compromise or global painter change was needed.
- Native Windows Qt can paint into pixmaps without showing a window. Forcing
  offscreen here can remove the font database and produce tofu, so the real-widget
  test follows existing font checks rather than forcing a nominal headless mode.
- TinyPedal ignores test*.py globally but already tracks the relevant old tests.
  Force-add a new scoped regression once; do not broaden ignore policy for this fix.
- Turn data is cached on map updates. Publishing the missing file requires a
  TinyPedal restart/map reload, not a coach restart or a new reference lap.
