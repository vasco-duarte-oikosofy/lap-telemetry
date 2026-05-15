# Learnings — Phase 01 Static Outline Contract

1. The accepted Phase 01 alignment differs from the earlier Phase 00 handoff values. The reviewed transform is scale `0.998`, rotation `0.0004`, translate `(-164, 632)`, no flips, and `reverse_point_order: true`.

2. The production JSON is intentionally minified to one line so the large 1401-point outline stays within the repository line-count rule.

3. Spa needs explicit name metadata now, even before runtime lookup. Current known names include `Circuit de Spa-Francorchamps`, `Circuit de Spa-Francorchamps Endurance`, `circuit-de-spa-francorchamps`, `circuit-de-spa-francorchamps-endurance`, and `spa-francorchamps`.

4. The static artifact preserves the user-provided accepted aligned centerline/left/right arrays, then wraps them in the production schema v1 metadata contract.
