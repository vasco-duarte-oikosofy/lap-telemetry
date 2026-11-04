# Handoff — Slice 42: faster Road Atlanta P3 reference + model refresh

## Result

- **Reference:** `product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.15.815.parquet`
  replaces `…_time_01.16.304.parquet`. Lap 17 of
  `session_20261104T180435Z_michelin-raceway-road-atlanta_lmu_race` (today,
  ELMS race), authoritative **75.8154 s** (displayed 1:15.658), 3767 rows,
  4083 m, valid throughout. Improvement **0.4886 s**. The exporter's audit
  changed exactly one reference and superseded exactly one.
- **Model:** `product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json`
  re-pointed at the new reference (now a POSIX path — the old file carried
  Windows backslashes) and 7 corner triples refreshed:

  | corner | entry | apex | exit | was |
  |---|---|---|---|---|
  | t1 Turn 1 | 284.0 | 453.0 | 457.0 | 291 / 435 / 438 |
  | t2 Turn 2 | 692.0 | 855.0 | 861.0 | 676 / 823 / 857 |
  | t5 Turn 5 | 1304.0 | 1431.0 | 1438.0 | 1296 / 1422 / 1441 |
  | t6 Turn 6 | 1854.0 | 1988.0 | 1995.0 | 1846 / 1972 / 2030 |
  | t7 Turn 7 | 2054.0 | 2150.0 | 2180.0 | 2057 / 2139 / 2171 |
  | t10a Turn 10A | 3343.0 | 3514.0 | 3534.0 | 3353 / 3517 / 3534 |
  | t10b Turn 10B | 3555.0 | 3585.0 | 3591.0 | 3548 / 3575 / 3620 |

  Six corners keep their curated geometry: `t3 Turn 3`, `t4 Turn 4 (The
  Esses)`, `t8`, `t9`, `t11`, `t12`. All 13 names, short names, IDs,
  `apex_side`s and the five `target_throttle_pct: 100` flat markers are
  byte-identical to before (verified against `HEAD`).
- **Outline:** `product/data/track-outlines/michelin-raceway-road-atlanta.json`
  turn anchors re-baked to match the refreshed model;
  `product/web/js/staticMichelinRacewayRoadAtlantaOutlineData.js` and
  `product/dist/compare.html` regenerated.

## Why 6 of 13 corners were preserved

Evidence is in `artifacts/signal-review.txt` (brake/throttle/steer/speed within
±0.5 s of each curated apex, old lap vs new lap):

- **Flat on both laps**, so no braking event exists to refresh:
  `t4 Turn 4 (The Esses)` (throttle 1.00 / brake 0), `t8` (1.00 / 0),
  `t9` (1.00 / 0), `t11` (1.00 / 0), `t12` (1.00 / 0). These are exactly the
  model's `target_throttle_pct: 100` markers, now confirmed on the new lap.
- **`t3 Turn 3` is the second half of the Turn 2 braking event.** The detector
  yields a single event at ~855 m that the curated `t2` apex claims; `t3`'s
  nearest unclaimed candidate was out of range, so preserving it is what stops
  one braking event from being claimed twice (same rule as slice 41's
  Senna/Ferradura). Brake is still applied at 835 m on the new lap
  (throttle mean 0.009) — Turn 3 is not a separate braking zone on this lap.

With those six preserved, every matched corner moved ≤35 m (guard was 40 m).

## Source handling — read this before re-running anything

The recorder **never finalized this session**. There is no canonical
`.parquet`; the sidecar still says `in_progress: true` with `ended_utc: null`,
the race timer expired (`session_time_remaining_s ≈ -99 s`) and the recorder
keeps appending idle frames.

- 92 closed `partN` shards were frozen **read-only** into the ignored scratch
  dir `var/tmp/road-atlanta-p3/` (concat in numeric order; no duplicate rows
  found, so nothing was collapsed). The higher overlapping `snapN` snapshots
  and the still-open highest shard were excluded.
- Hashes are in `artifacts/source-manifest.json`; the live sidecar is
  deliberately excluded from that hash set because it is still being rewritten.
- `artifacts/verify_source.py` re-checks shard hashes, the frozen hash, that the
  exported reference is the selected segment, that 222 other curated assets are
  untouched, and runs the folder validator with the frozen copy registered on
  `SESSION_DIRS` so the new reference resolves to its source.
- **If the session is ever finalized, re-run the guard.** A faster lap later in
  the race (or in another session today) would supersede this reference; the
  current file stays correct (it is a slice of the closed shards).

## Verification

- `artifacts/reference-validation.txt`: **34 references, 0 failures**; the new
  reference traces to the frozen race session.
- `artifacts/scope-audit.json`: 92/92 source shards unchanged, frozen file
  unchanged, exported ref equals the selected segment, **222 other curated
  assets unchanged** (only this model + diagnostics + outline + static module +
  `dist/compare.html` changed).
- `--print-facts`: reference vs itself → delta 0.000, no losses/gains; lap 13
  (1:17.001) vs new reference → **+1.186 s**, corner IDs resolve (t4 "Esses",
  t3, t10a …). See `artifacts/lap13-facts.txt`.
- `artifacts/update-log.txt`: the guarded updater's full output (preserve list,
  geometry guard, per-corner before/after).
- Full `--pw` suite: **2022 assertions / 80 scripts pass**. Build current.

## User action / remaining work

- **Restart the coach** before using this track: it caches reference/model
  lookups and the superseded `…_time_01.16.304.parquet` no longer exists.
- Live by-eye confirmation of the map is still pending (as with slices 24, 38
  and 39).
- Deferred (not in scope): `bake_outline_turns.py` still fills outline
  `short_name` (map label) from the model's speech alias, so every re-bake needs
  `artifacts/restore_display_labels.py`. Making the bake preserve existing
  display labels is the real fix.
- Deferred (not in scope): `dev/scripts/test_lap_duration_surfaces.py` and
  `dev/scripts/test_compare_reference_duration.js` hardcode the Road Atlanta
  reference filename; they were updated here. A helper that reads the current
  reference from the coaching model would stop this recurring.
