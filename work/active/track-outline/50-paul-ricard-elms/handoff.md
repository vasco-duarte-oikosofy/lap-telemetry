# Handoff — Slice 50: Paul Ricard - ELMS / Ferrari 296 GT3

## Result

- **Reference** `product/data/reference-laps/paul-ricard---elms_vista-af-corse-2026-21-lm_time_02.07.601.parquet`
  — practice lap **8** of `session_20261110T175322Z_paul-ricard---elms_lmu_practice`
  (Vista AF Corse 2026 #21:LM, catalogued slug `ferrari-296-gt3`), authoritative
  time **127.601 s**, **6361 rows**, single contiguous segment, valid throughout.
  Lap 7 (2:07.813) was faster on the sampled `lap_time_s` clock but the
  authoritative clock ranks lap 8 first — the guarded exporter picked it, and the
  audit reported `1 reference lap changed (added …, superseded: [])`.
- **Model** `product/data/track-coaching/paul-ricard---elms_vista-af-corse-2026-21-lm.json`
  (+ `.diagnostics.txt`) — **16** curated zones, `layout_id: elms`,
  `lap_length_m` **5805.3**. Official names: `S de la Verrerie 1/2`,
  `Virage de l'Hôtel 1/2`, `Virage du Camp`, `Virage de la Sainte-Baume`,
  `Ligne Droite du Mistral`, `Chicane Nord 1/2`, `Courbe de Signes`,
  `Double Droite du Beausset 1/2`, `Virage de Bendor`, `Courbe du Garlaban`,
  `Virage du Lac`, `Virage du Pont`. Spoken/map aliases: `Verrerie 1/2`,
  `Hôtel 1/2`, `Sainte-Baume`, `Mistral`, `Chicane 1/2`, `Signes`,
  `Beausset 1/2`, `Bendor`, `Garlaban`, `Lac`, `Pont`. **Two flat bends** carry
  `target_throttle_pct: 100`: `mistral` (1815/1886/1920) and `garlaban`
  (4900/4949/5170) — both verified WOT, zero brake, across the whole span. The
  Verrerie is a real braking chicane on this layout and is *not* marked flat.
- **Outline** `product/data/track-outlines/paul-ricard---elms.json` — 500
  centreline points, 500 per synthetic ±5 m boundary, 16 turn anchors on the same
  `lap_length_m` axis, compact-formatted (361 lines). Module
  `product/web/js/staticPaulRicardElmsOutlineData.js`, manifest keys
  **`paul-ricard---elms`** and **`paul-ricard-elms`** (the filename fallback
  flattens the dash run, exactly like 1A).
- **TinyPedal** — packaged `tinypedal/data/turn_labels/Paul Ricard - ELMS.turns.json`
  (16 turns, `s_frac = apex / lap_length_m`, `--check` clean). New sibling-repo
  widget test `tinypedal/tests/test_paul_ricard_elms_turn_labels.py`: anchors
  worst **18.3 m**, 16/16 labels at 400 px/90° and both 600 px orientations,
  15/16 at 400 px/0°, zero overlaps, every label changes real widget pixels.
- **Local TinyPedal map fix (not committable)** — `trackmap/Paul Ricard - ELMS.svg`
  was recorded **164.6 m past** the simulator's timing line, so TinyPedal drew its
  start line in the wrong place and every label landed late. It is now rotated to
  start at the timing line (`map`+`dist` rotated, distance axis re-zeroed, `desc`
  sector indices rotated `170,370 → 185,385`). `tinypedal/trackmap/` is gitignored,
  so this exists only on this machine; **re-run the alignment tool after any
  re-recording**:
  `py dev/scripts/align_tinypedal_map_start_line.py --track "Paul Ricard - ELMS" --check`
- **Bundle** rebuilt: `product/dist/compare.html` (≤ 437 lines). File-replay
  evidence `artifacts/compare-outline.png`: all three outline parts paint and all
  16 labels render (`artifacts/`, from `test_paul_ricard_elms_ui.js`).

## Layout identity (why this is not 1A/1A-V2-Short/3A)

Measured against the curated 1A reference line, this lap leaves the 1A path in
exactly two places: max **75 m** around 600–1000 m (tight Verrerie `S`) and max
**67 m** around 2900–3300 m (Chicane Nord), everything else ≤ 4 m. That is the
5.8 km 1C/ELMS configuration LMU records as `Paul Ricard - ELMS`. Simulator
distance axis 5805.3 m vs TinyPedal's recorded 5804.6 m.

## Safe selection

`session_20261110T175322Z_paul-ricard---elms_lmu_practice.parquet` (source
sha256 recorded before/after in `artifacts/before-hashes.txt` /
`artifacts/after-hashes.txt`; unchanged). 12 contiguous segments, no sim restart,
no snapshot shards. Selection is segment-based (`artifacts/session-scan.txt`);
`--print-facts` on lap 7 resolves every corner id and reports
`lap_time_delta_s 0.212` (`artifacts/lap7-facts.json`). Reference validator:
**36 reference laps, 0 failures** (`artifacts/reference-validation.txt`).
`artifacts/scope-audit.txt`: only this slice's four new curated files, the
manifest, the bundle, the coverage doc, the PLAN and the new scripts changed —
139 pre-existing curated assets untouched.

## New helpers worth knowing

- `dev/scripts/create_paul_ricard_elms_assets.py` — **one-shot initializer**, not
  a general tool. Asserts the detector produced exactly the reviewed 11 event
  apexes `[621, 739, 1307, 1411, 1521, 1663, 2960, 3044, 3954, 4831, 5470]`
  (11 events are not 16 corners: the two flat bends are invisible, and the
  compound Beausset is rejected by the detector's local-prominence rule), refuses
  any reference other than the guarded 2:07.601 file, refuses to overwrite
  differing curation, refuses a file above 437 lines. For a future faster
  reference use `update_reference_and_coaching_model.py` instead.
- `dev/scripts/align_tinypedal_map_start_line.py` — **general** TinyPedal map
  guard. Measures how far a recorded map's start sits from the sim timing line
  (from the recorded `dist` axis), rotates `map` + `dist` + `desc` sector indices,
  re-zeroes distances, and refuses to write unless every outline turn anchor lands
  within `--tolerance-m` (default 25 m) and the point set is unchanged. Default
  `--min-offset-m 30` makes every existing map a no-op (measured: 1A 15.2 m,
  Long Beach 20.6 m, Barcelona 21.7 m, Imola 11.7 m, the rest ≤ 3 m).
- `dev/scripts/test_paul_ricard_elms.py/.js` (+ `_ui.js`, `_tinypedal.js`) and
  `dev/scripts/test_tinypedal_map_alignment.py/.js` — all registered in
  `testFeatures.track-outline` and in `npm test`.

## Tests

- `bash scripts/test-summary.sh --feature track-outline --pw`:
  **1135 assertions / 32 scripts — ALL PASS**.
- Full `bash scripts/test-summary.sh --pw`:
  **2195 assertions / 84 scripts — ALL PASS** (`artifacts/full-suite.txt`).

## User action / remaining work

- **Restart the coach** (and reload TinyPedal's map) so the new reference, model
  and label file are picked up.
- **Live by-eye approval is still pending** — `visual_qa.status` is `pending`;
  the automated `file://` render is not human approval.
- Deferred TODOs:
  - real (measured) widths instead of the synthetic ±5 m shell;
  - the ELMS map alignment is local-only (gitignored) — re-check it after any
    re-recording;
  - two pre-existing map anomalies found by the new tool and deliberately not
    touched here: `Silverstone Grand Prix Circuit - ELMS` (2696 m axis offset,
    rotation fails anchor verification at 1510 m) and `Autódromo José Carlos
    Pace` (34.7 m, legacy outline whose axis is the geometric centreline). Both
    are bug candidates, not slice work.

## Untouched on purpose

- Paul Ricard 1A / 1A-V2-Short / 3A references, models, outlines and labels.
- Every other track's reference, model, outline and TinyPedal labels.
- `coach-race.log` at the repository root (live coach runtime artifact).
- `product/web/js/trackOutlineManifest_backup.js` (stale backup flagged in the
  architecture review; reverted after `register_outline.py` rewrote it).
