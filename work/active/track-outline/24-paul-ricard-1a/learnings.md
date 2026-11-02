# Learnings — Slice 24 (Paul Ricard 1A / Ginetta P3)

- **Detector events are not corners.** The race lap produces six brake/lift
  events, but 1A has thirteen layout bends. The four flat bends (both Verrerie
  segments, the Mistral entry bend, Garlaban) are invisible to a brake/throttle
  detector, and Hotel/Camp, the double Beausset and Lac/Pont collapse into single
  events. Curating from the event list alone would have produced a six-corner
  model for a thirteen-corner layout. Restore flat bends and subdivide compound
  corners from the steering/pedal traces, then re-check the official plan.
- **"Lap N" is not a lap.** The race file contains a sim restart, so the segment
  scan reports 18 segments for 18 claimed lap numbers with segment 1 and the last
  segment invalid. Selecting by `lap_number` would have picked the wrong rows.
  Select by segment and assert the exported rows equal the reference.
- **Layout identity matters more than track name.** Paul Ricard 1A, 1A-V2-Short
  and 3A share a name prefix, so the regression tests must assert *inequality*
  against the other two outlines, not just presence. The filename-driven replay
  path also rewrites `paul-ricard---1a` into `Paul Ricard 1A` (whitespace instead
  of dashes), so both the slug and the inferred name must resolve to the same
  outline — that was the red test before the manifest entries existed.
- **The official plan's names differ from older models.** The final left bend is
  `Virage du Lac` (an older curated model said Tour) and `Garlaban` is
  `Courbe du Garlaban`. Read the circuit's own diagram
  (`artifacts/official-corner-plan.png`) rather than inheriting names from a
  neighbouring layout's model — but do **not** edit those neighbouring models.
- **Two name spaces.** Spoken aliases (`short_name` for the coach, e.g.
  `Sainte-Baume`) and map labels (e.g. `Ste-Baume` so it fits a 400 px widget) are
  different consumers of the same corner. Change one, assert the other.
- **The build had its own line ceiling.** Regenerating `dist/compare.html` for a
  new track exposed a pre-existing 4640-line artifact, over the 437-line rule.
  Fixing that is a *format-only* refactor commit with byte-identical render proof
  (`artifacts/build-format-parity.json`), kept separate from the data commit.
- **This workstation cannot run the whole native suite green.** `python3` only
  resolved to the WindowsApps stub (exit 9009) and six older tests `import()`
  raw `C:\...` paths, which Node 22 rejects. Both reproduce on a clean HEAD
  worktree, so they are host/toolchain rot, not slice regressions; record the
  reproduction instead of silently "fixing" out-of-scope tests.
- **Unicode + Windows console.** Python child processes need `PYTHONUTF8=1` or
  they die on `cp1252` when printing corner names with accents (Hôtel,
  Sainte-Baume). The per-test `PYTHONUTF8` env in the new TinyPedal test is not
  enough for the older wrappers.
