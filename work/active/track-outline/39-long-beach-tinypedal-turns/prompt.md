# Slice 39 — Long Beach turn labels visible in TinyPedal

**Status:** ✅ Implemented in lap-telemetry `406aec9` and TinyPedal `2d8d5a65`.
All 11 labels verified in the real widget; user live in-game confirmation pending.

## Goal / diagnosed causes

The Long Beach SVG exists, but its packaged TinyPedal .turns.json is missing.
The default exporter would also normalize lap-distance apices by the outline's
3400.385 m geometric trace rather than their 3185.3 m simulator distance axis,
placing later labels up to ~180 m too early. Export all 11 official numbered
turns with correct distance fractions and verify actual Qt-widget rendering.

## Scope

- lap-telemetry: targeted --track export, optional authoritative lap_length_m
  metadata with legacy fallback, Long Beach metadata/builder/generated module,
  regression tests, documentation and build.
- Sibling ../tinypedal: generated Long Beach packaged label file and a focused
  real-widget regression test only. Respect existing master branch and preserve
  local .venv/var/settings/recorded maps. No generic widget/layout changes.
- Official names/numbers, all coaching geometry (especially flat T3/T7), ref,
  all outline coordinates and every other track's shipped labels stay unchanged.
- Do not inspect/change/stage the user's coach-race.log.

## Execution

1. Register track-outline feature tests (guards, exporter, Long Beach data/UI,
   shared label contracts/parity and focused TinyPedal integration).
2. Red first: missing shipped Long Beach labels, missing distance-axis metadata,
   unsupported track-only export; test source/export fractions and real Qt paint.
3. Add validated optional lap_length_m preference; preserve all legacy outline
   behavior. Carry model lap length into this outline and its guarded creator.
4. Add --track selection, export ONLY Grand Prix of Long Beach, regenerate its
   ES module via the existing generator, build. Prove no other label/data change.
5. Test the actual TinyPedal loader/widget with its recorded map at 400/600 px
   and 0/90 degrees: all 11 labels, no overlap/off-canvas, real changed pixels.
   Use native Windows Qt fonts, not the empty-font offscreen plugin. Save images.
6. Run feature/full --pw suites, TinyPedal label regressions and build; commit
   each repository's scoped changes on its native branch. Handoff/learnings,
   update PLAN with hashes, stop. User live visual confirmation remains pending.
