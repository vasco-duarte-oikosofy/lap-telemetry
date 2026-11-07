# Slice 46 — Fuji / Ginetta P3 (DKR LMP3): check today's quali + race for a faster lap

Status: ✅ Complete — **checked, no asset change needed** (see git log)
Trigger: *"check for fastest laps with P3/Fuji combo in the quali and race
sessions I just finished. Update coaching model / reference lap if needed."*

## What was measured

| Session (2026-11-07) | Fastest complete lap |
|---|---|
| 14:18 quali (`session_20261107T141839Z_…_quali`) | **1:36.544 (lap 2)** |
| 14:27 race (`session_20261107T142746Z_…_race`) | 1:36.770 (lap 10) |

Current reference: **1:36.564**. So the quali lap is **20 ms (0.02 %)** faster —
the only lap in either session under the reference (next best 1:36.682).

The earlier Fuji sessions from today (09:41/09:46 practice, 09:48 quali, 09:57
race, 14:04/14:15/14:16 practice) were scanned too: nothing faster than
1:36.544, and no other vehicle ran `fuji-speedway`.

## Verdict: do not refresh

A 20 ms faster lap is not a better geometry source. The dry run (nothing
written) showed:

1. **Same 9 detected events** as the current reference — the lap carries no new
   corner information.
2. **The two "lost" corners are manual markers**, not detector misses:
   `13th Corner` (zone 3100–3161, inside Turn 12's event) and `Netz`
   (3284–3310) have no braking event of their own *on the current reference
   either*. They cannot be refreshed by any lap.
3. **The matcher would corrupt Netz** — bug 29: `Netz` (listed first) steals the
   `Netz Hairpin` event, moving it to 3289/3385/3446 (**+136 m** exit) and
   leaving the hairpin unmatched. This is the third time bug 29 has fired on
   this exact corner.
4. **The refreshes would be noise.** Across the 15 clean laps of these two
   sessions, the `100R` event apex spans 1626–1761 m (135 m) and Panasonic
   3650–3695 m; the lap would have moved 100R by +44 m and Panasonic by −9 m.
   The apex does not converge, so a single lap cannot define it.

This is the Bahrain Outer precedent: keep the reference whose lap the curated
model was built from when a marginally faster lap cannot reproduce it.

Assets unchanged: reference, coaching model, diagnostics, both Fuji outlines,
static modules, `dist/compare.html` (hashes in `artifacts/before-state.json`).

## If the 20 ms is ever wanted

The only safe command (works around bug 29 and the two manual markers):

```bash
python dev/scripts/update_reference_and_coaching_model.py \
  --session sessions/session_20261107T141839Z_fuji-speedway_lmu_quali.parquet \
  --track-id fuji-speedway \
  --allow-unmatched --preserve-geometry netz netz_hairpin 13th_corner
```

Still not recommended at this margin; it would also rewrite 100R from noise.

## Boundaries

- Read-only run: no product file written (verified against `before-state.json`).
- Bug 29 gained the third occurrence as evidence (still open, not fixed here).
