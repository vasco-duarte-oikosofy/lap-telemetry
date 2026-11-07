# Handoff — Slice 44 (Imola / F296 faster reference)

## What happened

A second Imola practice today (12:55–13:08Z) in the same car gave a faster lap.
Same combo as slice 43, so this is a plain Pipeline B refresh.

| Session (2026-11-07) | Fastest complete lap |
|---|---|
| 07:50Z practice (slice 43) | 1:46.173 ← old reference |
| 08:23Z quali | no complete lap (2:33.975 segment) |
| 08:25Z race | no complete lap |
| 08:31Z race | no complete lap |
| **12:55Z practice** | **1:45.534 (lap 6)** ← new reference |

Session laps: 1:52.610 / 1:47.566 / 1:47.086 / 1:45.756 / 1:46.142 / **1:45.534**
(laps 7–8 incomplete). Four of the six are faster than the old reference, which
is a good sign the improvement is real driving, not a single fluke lap.

## Files written

| File | Change |
|---|---|
| `product/data/reference-laps/autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm_time_01.45.534.parquet` | **new** (5263 rows, segment-sliced lap 6) |
| `…_time_01.46.173.parquet` | **deleted** (superseded; audit reported add 1 / supersede 1) |
| `product/data/track-coaching/…_vista-af-corse-2026-21-lm.json` | reference block + 7 corner zones refreshed |
| `product/data/track-coaching/…_vista-af-corse-2026-21-lm.diagnostics.txt` | 8 detected events for the new lap |

`product/data/track-outlines/autodromo-enzo-e-dino-ferrari.json` is
**byte-identical** (`artifacts/outline-check.txt`).

## Corner geometry (was → now)

| Corner | Entry | Apex | Exit |
|---|---|---|---|
| Tamburello *(preserved)* | 513 | 699 | 710 |
| Variante Villeneuve 1 | 1223→1229 | 1413→1427 | 1427→1433 |
| Variante Villeneuve 2 *(kept)* | 1404 | 1417 | 1420 |
| Tosa | 1604→1604 | 1707→1705 | 1747→1727 |
| Piratella | 2203→2200 | 2333→2325 | 2361→2351 |
| Acque Minerali 1 | 2652→2638 | 2849→2847 | 2853→2854 |
| Acque Minerali 2 *(kept)* | 2836 | 2858 | 2861 |
| Variante Alta 1 | 3251→3235 | 3383→3389 | 3393→3396 |
| Variante Alta 2 *(kept)* | 3374 | 3396 | 3398 |
| Rivazza 1 | 3990→3996 | 4119→4122 | 4144→4141 |
| Rivazza 2 | 4196→4201 | 4249→4262 | 4291→4298 |

Largest apex move: 14 m (Villeneuve 1). All within the 40 m guard.

## Why Tamburello (t1) is preserved, not refreshed

The detector's Tamburello **exit** is where throttle climbs back above 0.90 after
the apex — driver behaviour, not a corner edge. Across the six laps of this
session it lands at 717, 790, 789, 759, 716, 774 m (spread 74 m). Entry is nearly
as noisy (522–549 m). Refreshing from one lap would bake that lap's
partial-throttle modulation into the model, so the reviewed zone stays. The apex
699 vs the new lap's 704 is 5 m — inside the noise. Evidence (per-corner zones
for every lap): `artifacts/signal-review.txt`.

The other corners are stable lap to lap (Tosa apex 1691–1715, Rivazza 2 apex
4258–4281), so their refresh is meaningful.

## Verified

- Curation byte-identical to `artifacts/model-before.json` — names, IDs, short
  names, apex sides, flat markers (`artifacts/curation-check.txt`, exit 0).
- Reference validator: 35 refs, 0 failures; the new file traces to the 12:55
  session (`artifacts/reference-validation.txt`).
- `--print-facts` cross-session: the old reference lap (1:46.173) reports
  `lap_time_delta_s 0.639`; lap 4 of the new session (1:45.756) reports `0.222`.
  Both exact; corner names resolve (`Tamburello`, `Tosa`, `Rivazza 2`, `Alta 2`).
- Updater re-run is a no-op; every 296 GT3 livery resolves to the new pair while
  499P and Ginetta still resolve to their own (`artifacts/resolution-check.txt`).
- Feature suite 950 assertions; full `--pw` suite 2027 assertions / 80 scripts.
- `npm run build` leaves `dist/compare.html` unchanged.
- Scope: only the reference (1 add + 1 delete), the model and its diagnostics
  changed. No other track touched.

## Not done / next

- 1:45.534 is still a practice lap; four laps of this session were under the old
  reference, so there is likely more. Re-running the updater with the new session
  is the entire procedure.
- The three compound second halves still carry Ginetta-derived zones; they will
  refresh only if a lap brakes separately inside the complex.
- TinyPedal labels for Imola still not exported (needs the sibling map); slice 33
  (Imola ELMS alias) remains open.
