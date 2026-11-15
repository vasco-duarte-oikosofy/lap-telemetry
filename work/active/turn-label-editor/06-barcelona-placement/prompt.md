# Slice 06 — Barcelona placement and TinyPedal update runbook

Status: ✅ Complete — lap-telemetry `6236b3e`, TinyPedal `a5cf854e`.
Automated QA passed; live-driver confirmation pending.

## Goal

Publish the driver's `turn-labels-circuit-de-barcelona (1).json` version 3
placement: Circuit de Barcelona, 0° orientation, all 14 label offsets. Document
the repeatable TinyPedal map-label update process and link it from AGENTS.md
(user explicitly requested that edit).

## Execution

1. Preserve the supplied JSON under artifacts; inspect existing preset/export,
   editor generator and sibling widget tests. Leave unrelated dirty files alone.
2. Test first: pin every supplied offset and orientation through the preset and
   packaged payload; exercise Barcelona with the real widget at 400/600 px.
3. Add only the Barcelona preset, export only `Circuit de Barcelona`, regenerate
   editor data. Do not edit coaching models, references, outline geometry, SVGs,
   other tracks, user settings or label-planner behavior.
4. Create a stable runbook (existing README has partial, outdated instructions),
   covering import/version migration, targeted export, rebuild/freshness checks,
   real-widget review, configuration precedence, reload and two-repo commits.
   Link it from AGENTS.md and the tooling README.
5. Per the user's updated rule, run ONLY focused TinyPedal tests (placement
   wrapper and export regression), plus npm run build/freshness checks; audit
   scope. Do not run lap-telemetry feature/full suites or unrelated tests.
6. Commit this slice only on main (sibling uses master), record commit hashes in
   PLAN.md, write handoff.md/learnings.md and stop.

## Acceptance

- All 14 exact offsets and orientation 0 survive preset → export → widget.
- Real Qt widget renders Barcelona at actual 400 and 600 px with zero dropped
  labels, overlaps or off-canvas labels; save review images.
- Track-only exporter --check and editor generator --check are clean.
- Dedicated TinyPedal update runbook exists and AGENTS.md links to it.
- Other payloads and curated product data are unchanged by this slice.
- Focused TinyPedal tests and build pass; report external blockers honestly.

TinyPedal-only tests:
`bash scripts/test-summary.sh dev/scripts/test_shipped_turn_label_placements.js`
`bash scripts/test-summary.sh dev/scripts/test_tinypedal_turn_label_export.js`

The user explicitly replaced the general feature/full-suite requirement during
this slice. Earlier broad-run results are retained as historical evidence only.
