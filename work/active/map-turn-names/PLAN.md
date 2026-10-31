# Mission: Turn names on the circuit map

**Spec:** [`docs/specs/MAP_TURN_NAMES.md`](../../docs/specs/MAP_TURN_NAMES.md)

**Goal:** Every corner of the circuit map in `product/dist/compare.html` shows
its turn number and name (`T1 Abbey`), driven by a `turns` block baked into the
track outline and gated by a feature flag that is ON by default. The label
placement math must stay map-size agnostic so it can be ported to the
`../tinypedal` track map (smaller map, Qt painter).

**Feature tests:** `bash scripts/test-summary.sh --feature map-turn-names`
(seeded with the two infrastructure guards; grows with each slice).

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-turn-label-algorithm` | 🔲 Not started | Offline spike: bake label anchors for two tracks, render a reviewable PNG at 250 px **and** at a small map size, write down the placement/declutter rules. No product code. |
| `02-outline-turns-schema` | 🔲 Not started | `turns` block defined + baked into the Silverstone International outline JSON; validator rejects malformed turns; **every outline writer preserves an existing `turns` block** (guard test). No UI. |
| `03-render-turn-labels` | 🔲 Not started | SVG `<g id="track-turn-labels">` group rendered by the map, `T<n> <name>` / `T<n>`, feature flag ON by default, DOM + Playwright acceptance. |
| `04-backfill-tracks` | 🔲 Not started | Bake `turns` for every outline-covered track that has curated corner names (Monza Curva Grande, Road Atlanta, Daytona, Paul Ricard 3A, Algarve, …); unnamed corners get `T<n>` only. Visual QA per map size. |
| `05-declutter` | 🔲 Not started | Only if slice 01/03 shows real overlap at 250 px: greedy rect suppression + font/gap tuning, validated at small map sizes. |

**Completed:** none yet.
**In progress:** none.
**Deferred / later missions:** label interaction (click-to-zoom, cursor
linking), and the TinyPedal port in the sibling repo.

---

## Ordering rationale

- Slice 01 exists because placement is the only real unknown (label collisions
  on a 250 px map, and how it degrades on a ~100–150 px map like TinyPedal's).
  Per AGENTS.md "spike, then stabilize": the spike is throwaway, and the
  picture it produces is the approval gate before product code.
- Slice 02 before 03 so the renderer never invents data; the preservation guard
  lands in the same slice that starts putting curated content into the outline
  JSON.
- Slice 04 is deliberately last-but-one: it is data work with visual QA, and it
  is the point where the "no name → `T<n>`" rule gets exercised for real.

## Known constraints carried from earlier missions

- `dist/compare.html` must keep working from `file://` — no `fetch()`; all
  label data must arrive through the inlined static outline module.
- Most coaching models are still uncurated placeholders (`turn 1`, `turn 2`, …);
  those corners must render as `T<n>` without a name (spec rule).
- The sim's left/right sign convention is not portable across laps — the
  outward normal must be derived from the outline polygon, not from a sign
  assumption (see `work/active/track-outline/13-monza-curva-grande/learnings.md`).
