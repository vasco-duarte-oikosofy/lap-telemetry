# Learnings — Phase 02 Runtime Static Outline Rendering

1. The compare page's development test server serves only `web/`, while `dist/compare.html` must keep working as a standalone `file://` bundle. To satisfy both, the runtime uses a generated JS module (`web/js/staticSpaOutlineData.js`) that mirrors `data/track-outlines/spa-francorchamps.json`; the new runtime test verifies the copy is byte-for-byte equivalent after parsing.

2. The existing circuit-map SVG already has the right draw stack. Adding `<g id="static-track-outline">` as the first SVG child keeps the static outline behind heatmap segments, the trajectory polyline, zoom arc, and cursor dot.

3. The static outline is projected with the existing trajectory-derived `trackTransform`. This preserves current map framing/zoom behavior and avoids letting the larger static boundary corridor change the viewport.

4. The artifact uses simulator `x/y` coordinates, and the current map transform expects simulator `x/z` coordinates. For this artifact, `point.y` maps through `toMapZ`, matching the Phase 01 coordinate-system contract.
