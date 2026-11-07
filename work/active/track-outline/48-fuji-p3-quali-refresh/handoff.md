# Handoff — Slice 48 (Fuji P3 refresh + bug 29 live validation)

## State on disk

| File | Change |
|---|---|
| `product/data/reference-laps/fuji-speedway_dkr-engineering-4-elms25_time_01.36.544.parquet` | **new** reference (4760 rows) |
| `…_time_01.36.564.parquet` | **deleted** (superseded) |
| `product/data/track-coaching/fuji-speedway_dkr-engineering-4-elms25.json` (+ `.diagnostics.txt`) | 9 corners refreshed; `13th Corner`, `Netz` kept |
| `product/data/track-outlines/fuji-speedway_outline.json` | `turns` re-baked to the new apexes |
| `product/web/js/staticFujiSpeedway_outlineOutlineData.js`, `product/dist/compare.html` | regenerated |
| `../tinypedal/tinypedal/data/turn_labels/Fuji Speedway.turns.json` | re-exported (11 turns, new `s_frac`) |

`product/data/track-outlines/fuji-speedway-classic.json` and its labels are
untouched (scope audit in `artifacts/scope-audit.txt`).

## Bug 29 — live result

The fixed matcher gave the Netz Hairpin event to **Netz Hairpin** (19 m away) and
left **Netz** unmatched with its curated zone intact. Under the old matcher the
same lap produced `Netz` at 3289/3404/3439 (+129 m of exit) and reported the
hairpin unmatched. `13th Corner` is unmatched on both, correctly.

The bug folder is still in `work/active/bugs/29-…`; move it to
`work/completed/bugs/` once you have seen this on your side (map/coach) and say
so — AGENTS.md requires your confirmation, not mine.

## Reference provenance nuance (worth knowing)

`validate_reference_laps.py` prints `source: session_20261025T070440Z_…` for the
new file. That is a heuristic: it takes the **first** session on the same
track+car whose lap time is within `TIME_TOL_S` of the filename time, and the
2026-10-25 race has a 1:36.564 lap (20 ms away). The real source is today's
quali:

- exported file is **row-for-row identical** to lap 2 of
  `session_20261107T141839Z_fuji-speedway_lmu_quali.parquet` (4760 rows) apart
  from the `authoritative_lap_time_s` schema metadata;
- the 10-25 race has no 1:36.544 lap at all (its best is 1:36.564, lap 10, 4811
  rows).

Improvement candidate (not done, out of slice scope): make the validator pick
the session lap **closest** to the filename time instead of the first within
tolerance. One-line change, would make provenance exact here.

## What to expect in the car/map

- Lap delta baseline is now 1:36.544. The coaching model's corner zones moved by
  −9…+45 m (100R the largest, which slice 46 flagged as a noisy corner: its
  event apex spans 135 m across today's clean laps).
- TinyPedal labels moved with the apexes (100R 0.3743 → 0.3840 is the biggest
  shift); restart TinyPedal or reload the map to see them.
- `Netz` (T9) deliberately still points at 3310 m and `13th Corner` at 3151 m —
  they are curated markers, not detector output. Do not "fix" them.

## Verified

- Curation byte-identical for all 11 corners except geometry
  (`artifacts/curation-and-fix-check.txt`).
- `--print-facts` against the old reference lap: delta exactly 0.020 s.
- Reference validator 35/0; feature suite 960 assertions; full `--pw` 2037
  assertions / 80 scripts; `npm run build` rebuilt module + bundle.
- Updater re-run would be a no-op (same ref, same lap).

## Not done / next

- Slice 46's warning stands: 100R is a noisy anchor at this margin. If you want
  a steadier Fuji model, the next useful step is more laps (the event apex
  should converge), not another single-lap refresh.
- Fuji `Netz`/`13th Corner` remain manual markers with no braking event; any
  future refresh needs `--allow-unmatched` (as here) and will warn about them.
