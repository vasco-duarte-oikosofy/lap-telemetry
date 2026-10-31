# Handoff — Slice 01 (turn label placement spike)

**Status: v2 on disk, awaiting review.** No product code touched.

## v2 rules (from the review of v1)

- Type **30 % smaller**: `fontSize = clamp(mapSize * 0.023, 5, 8)` → 5.75 px at
  250 px (was 8.25 px).
- **Labels stay on their corner**: max displacement `2.4 × fontSize` (≈14 px),
  along-track nudges preferred over pushing away from the track; the
  ribbon-clearance constraint is gone, so labels may cross the track.
- **Strings never overlap**: 10 candidate positions per label (5 nudges × full
  text / number only), first non-overlapping and fully-visible candidate wins;
  drop only if all fail. Nothing was dropped in either probe track.
- **`short_name`** added to the schema (`docs/specs/MAP_TURN_NAMES.md`) —
  display-only, curated, `name` untouched for the coach.

## Review set (`artifacts/`)

| File | What to look at |
|---|---|
| `labels-monza-curva-grande-circuit-250.png` | 10/10 labels, short names, 0 overlaps, all within ~4 px of the apex |
| `labels-silverstone-international-circuit-250.png` | 8/8 labels, 0 overlaps |
| `labels-monza-curva-grande-circuit-120.png` | TinyPedal-sized map, still 10/10 |
| `labels-silverstone-international-circuit-120.png` | 8/8 |
| `labels-*-120-nofloor.png` | same with the 5 px font floor off (2.76 px) — this is what a 120 px map really has room for |

Orange dots mark the apexes; hairlines join a dot to its label so adjacency is
visible. `placement-report.json` has per-label text, nudge index and
apex→box distance; `ALGORITHM.md` has the tables and every constant.

## Decisions still open

1. **Chained sub-turns** (Roggia 1/2, Ascari 1/2/3): v2 shows all of them by
   nudging, so the `chain_id` / one-label-per-chain idea from v1 is no longer
   needed — confirm that reading.
2. **120 px behaviour**: names do fit now (10/10 at font 5), but the min gap
   between labels drops to 0.2 px. Prefer `T<n>`-only below ~150 px as a safety
   margin?
3. Font at 250 px (5.75) — smaller still, or keep?

## Not done

- Slices 02–05 (schema + preservation guard, renderer + flag, backfill).
- Anchors are static per layout; no per-lap positions, no rotation, no heatmap
  specifics.
