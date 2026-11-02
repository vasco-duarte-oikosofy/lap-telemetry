# Handoff — Slice 41: faster Interlagos P3 reference + model refresh

## Result

- **Reference:** `product/data/reference-laps/autodromo-jose-carlos-pace_dkr-engineering-4-elms25_time_01.30.062.parquet`
  replaces `…_time_01.30.354.parquet`. Lap 10 of
  `session_20261102T174436Z_autodromo-jose-carlos-pace_lmu_race`, authoritative
  **90.0625 s** (displayed 1:30.062), 4482 rows, complete and valid throughout.
  Improvement **0.2915 s**. The exporter's audit changed exactly one reference
  and superseded exactly one.
- **Model:** `product/data/track-coaching/autodromo-jose-carlos-pace_dkr-engineering-4-elms25.json`
  re-pointed at the new reference (now a POSIX path — the old file still carried
  Windows backslashes) and 5 corner triples refreshed:
  t1 Senna S 1 (entry −12 m), t4 Descida do Lago 1 (apex −8 m, entry +14 m),
  t9 Pinheirinho (apex +5 m), t10 Bico de Pato (apex −6 m), t12 Junção (apex −4 m).
  All 15 names, short names, IDs, `apex_side`s and `target_throttle_pct` markers
  are byte-identical to before.
- **Outline:** `product/data/track-outlines/autodromo-jose-carlos-pace.json` turn
  anchors re-baked so they match the refreshed model (contract in
  `dev/scripts/test_outline_turns.js`). Curated *display* labels (`Lago 1`,
  `Lago 2`, and the four `null`s) were restored afterwards — see learnings: the
  bake takes display labels from the model's speech aliases and would otherwise
  overwrite them. `product/web/js/staticAutodromoJoseCarlosPaceOutlineData.js`
  and `product/dist/compare.html` regenerated and verified in sync.

## Why 10 of 15 corners were preserved, not refreshed

The new lap is faster *because* the driver changed braking behaviour, so the
detector finds only 7 events instead of ~10. Evidence per corner is in
`artifacts/signal-review.txt` (brake/throttle/steer/speed within ±0.5 s of each
curated apex, old lap vs new lap):

- Genuinely flat on both laps (kept, marked `target_throttle_pct: 100`):
  `t3 Curva do Sol`, `t5 Descida do Lago 2`, `t13 Café`, `t14 Subida das Boxes`,
  `t15 Arquibancadas`.
- `t11 Mergulho` was a lift (throttle min 0.45) and is now flat (1.00) — no event.
- `t2 Senna S 2` and `t7 Ferradura 2` are compound second apices: the Senna and
  Ferradura events are claimed once and must not be double-claimed.
- `t6 Ferradura 1` had a light brake on the old lap and none now; the detected
  "Ferradura" event lands at 2151 m, i.e. exactly on curated `t7`'s apex (2152 m).
  Refreshing it would have made t6 and t7 overlap, which is why the first
  attempt with `--max-geometry-delta-m 25` aborted (t6 apex +62 m, t8 entry −68 m).
- `t8 Laranjinha`: its detected *entry* extended 68 m back into Ferradura for the
  same merged-event reason.

With those ten preserved, the remaining five matched corners all moved ≤14 m
(guard at 25 m passed).

## Source handling — read this before re-running anything

The recorder **never finalized this session**. There is no canonical
`.parquet`, the sidecar still says `in_progress: true` with no `ended_utc`, and
the recorder process kept appending idle frames while this slice ran (94 closed
`partN` shards at freeze → 131 by the end).

Therefore:

- The 94 closed `partN` shards were frozen **read-only** into the ignored
  scratch dir `var/tmp/interlagos-p3/` (concat in numeric order, then collapse
  exact-duplicate consecutive rows: 107 584 → 103 382 rows). The 21 `snapN`
  overlapping snapshots were excluded.
- Their hashes are recorded in `artifacts/source-manifest.json`; the sidecar is
  deliberately excluded from that hash set because it is live and still changing.
- `artifacts/verify_source.py` re-checks shard hashes, the frozen hash, that the
  exported reference is byte-equal to the selected segment, that 148 other
  curated assets are untouched, and runs the folder validator with the frozen
  copy on `SESSION_DIRS` so the new reference resolves to its source.
- **If the session is ever finalized with a faster lap, re-run the guard.** The
  canonical file will supersede the frozen one; the current reference stays
  correct (it is a slice of the closed shards) but may no longer be the fastest.

## Verification

- `artifacts/reference-validation.txt`: 34 references, 0 failures, new ref traced
  to `session_20261102T174436Z_autodromo-jose-carlos-pace_lmu_race.parquet`.
- `artifacts/scope-audit.json`: 94/94 source shards unchanged, frozen file
  unchanged, exported ref equals the selected segment, **148 other curated
  assets unchanged** (only this model, its diagnostics, and this outline/module
  changed).
- `--print-facts`: reference vs itself → delta 0.000, no losses/gains; lap 9
  (1:31.783) vs new reference → **+1.721 s** with resolved IDs t6/t9/t10/t12 and
  correct names.
- `artifacts/update-idempotency.txt`: a second updater run reports
  "Coaching model already up to date … nothing written".
- Full `--pw` suite: **2022 assertions / 80 scripts pass**. Build current
  (`dist/compare.html` 140 lines, rebuilt from the changed outline).

## Bug found and fixed on the way (important)

`update_reference_and_coaching_model.py` read the curated model with
`read_text()` and wrote it with `json.dumps(..., ensure_ascii=True)`. On Windows
the read used cp1252, so the first refresh wrote **mangled** names
(`Jun\u00c3\u00a7\u00c3\u00a3o` instead of `Junção`). The model was restored from
git and re-written with the fix; the current file is verified UTF-8-clean.

Fixed in this slice: explicit `encoding="utf-8"` on the model read/compare and
`ensure_ascii=False` on write, plus the same encoding on the sidecar/outline
reads in `export_fastest_reference_laps.py`, `validate_reference_laps.py`,
`explore_and_export_laps.py`, `trajectory_to_outline.py`,
`average_trajectory_outline.py`. Guard: new
`dev/scripts/test_curated_utf8_names.js` (registered in the full suite and every
feature list) fails if any curated JSON contains mojibake or if a guarded
pipeline script does text I/O without an explicit encoding. It was red-tested by
re-introducing the old read.

The Python-level round-trip test in `test_update_coaching_model.py` cannot catch
this class on its own: the wrapper forces `PYTHONUTF8=1`, which removes the
cp1252 default. The static rule is the real guard.

## User action / remaining work

- **Restart the coach** before using this track: it caches reference/model
  lookups, and the superseded `…_time_01.30.354.parquet` no longer exists.
- Optional follow-ups (not started, not in scope):
  - `bake_outline_turns.py` overwrites curated outline **display** labels with
    the model's speech aliases; `test_outline_turns.js` pins the labels, so any
    future re-bake needs the same manual restore. Consider making the bake
    preserve existing display labels.
  - No Interlagos map exists in the sibling TinyPedal repo, so no turn labels
    were published (and none were needed).
