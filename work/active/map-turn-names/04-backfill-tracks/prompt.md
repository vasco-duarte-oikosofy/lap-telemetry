# Slice 04 — Backfill `turns` for every outline we have

Run the slice-02 bake across **all** outlines, not just Silverstone International.

1. `python3 dev/scripts/bake_outline_turns.py --all` — bake every outline whose
   coaching model has at least one curated corner name; report the rest.
2. Curate `short_name` in the coaching models wherever the official name is too
   wide or redundant on a 250 px map (`Turn 3 — Renault` → `Renault`,
   `Curva Alboreto (Parabolica)` → `Parabolica`, …). Display-only: `name` stays
   the official string the coach speaks.
3. Re-bake, regenerate every static ES module, `npm run build`.
4. Measure placement on every backfilled track with the slice-01 harness at
   250 px: zero overlaps, labels adjacent to their apex.
5. Record the per-track table and the skipped tracks (with reasons) in
   `artifacts/BACKFILL.md`; extend `test_outline_turns.js` `KNOWN` to cover all
   backfilled tracks.
