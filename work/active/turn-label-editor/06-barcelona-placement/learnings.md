# Learnings — Barcelona TinyPedal placement

- The supplied placement explicitly requests 0°; do not infer a different
  orientation from the previous conversation about the P3 reference lap.
  Placements are shared by track/layout, not by coaching-model car.
- Barcelona already has 14 baked turns while the car-specific coaching model
  has its own corner set and distance axis. A label-placement request does not
  justify rebaking anchors or altering either lap length.
- The old shipped-placement test loop said 600 px but reused the 400 px widget.
  Create a new widget per size and assert pixmap dimensions as well as labels.
- Barcelona used to be the browser test's no-preset example. Once it ships a
  preset, select a genuinely unplaced track dynamically for blank-reset tests.
- TinyPedal globally ignores `test*.py`; the existing local placement test was
  not tracked. Force-added it so the regression now ships with the payload.
- The tooling README mixed working export instructions with an obsolete
  'not wired yet' note and a version-2 example. A dedicated runbook now describes
  the v3 import/preset/export/rebuild/widget/reload path without that ambiguity.
- The user explicitly changed policy during this slice: TinyPedal updates run
  ONLY TinyPedal tests, not feature/full suites or infrastructure guards.
  AGENTS.md's exception also covers related presets, payloads and documentation;
  build/freshness checks still apply.
