# Slice 37 — Monza Curva Grande / Ferrari 296 GT3 combo

The newest Monza Curva Grande sessions are Ferrari 296 GT3 (F296,
`Vista AF Corse 2026 #54:WEC`), but the combo has **no** reference lap and **no**
coaching model — the only Monza Curva Grande pair on disk is the Ginetta LMP3
(`dkr-engineering-4-elms25`, 1:35.182).

Deliverables:
1. Export the fastest clean F296 lap as the combo's reference (guarded export,
   one combo, audit clean).
2. Build the coaching model for the combo **without losing the curated content**:
   seed it from the existing Ginetta model (official turn names, IDs, apex sides
   and the `target_throttle_pct: 100` markers on the two flat corners — Curva
   Grande and Curva del Serraglio), then refresh its geometry from the new
   reference through the guarded updater.
3. Prove the names and the flat-turn markers survive, and that the model works
   in the coach (`--print-facts`).
