# Slice 17 — learnings

## A curated track can be missing only its outline

Algarve already had two reference laps and two coaching models in
`product/data/`, and still rendered a blank map: the outline is a separate,
independently-owned artifact. That is why "coverage" has to be measured against
`product/data/track-outlines/` + `trackOutlineManifest.js`, not against the
reference-lap or coaching-model folders.

## The plan table was stale in both directions

Checking before generating anything was worth it. `PLAN.md` marks COTA GP, Le
Mans, Lusail and Sebring as `🔲 Not started`, but `circuit-of-the-americas.json`,
`circuit-de-la-sarthe.json`, `lusail-international-circuit.json` and
`sebring-international-raceway.json` all exist, are wired into the manifest and
have static modules. Conversely the rows that really are missing (Bahrain
Endurance/Paddock, COTA National, Le Mans no-chicanes) need sessions that are not
on this machine. Algarve was the first row that was both genuinely missing and
completable from committed data.

## `register_outline.py` does the whole wiring

Validate → `static<Name>OutlineData.js` → import + `OUTLINES` entry → `npm run
build`. It also rewrites `trackOutlineManifest_backup.js` (a tracked file, so it
appears in the diff) — that is normal, the previous outlines' commits carry the
same change.

## The distance axis wraps in reference laps too

The reference parquet's `lap_distance_m` runs 4633.1 → wrap → 1.0, so the
trajectory must be read in **distance order**, not file order (same root cause
as bug 36, next door in `session_corner_extras`). Sorting by `lap_distance_m`
before resampling is the whole fix; no rotation needed.

## A 12 m seam at the start/finish line is normal

The reference lap is cut at the timing line and the axis wraps there, so the
first and last sampled points differ by ~11.7 m — the loop is not exactly
closed. Every committed trajectory outline has such a gap (0–10 m, TUMFTM ones
5 m from the boundary offset), so it is not a defect to chase: at map scale
(≈0.23 px/m) it is under three pixels. Recorded here so the next agent does not
"fix" it and shift every outline.

## Two references, one centreline: choose the faster, measure the other

Median-of-two is just the midpoint and blurs two different cars' lines. The
faster lap (LMP3, 1:40.706) gives the tighter line; the second reference is more
useful as *evidence* — mean 3.28 m / p95 5.46 m / max 6.43 m from the centreline,
which is what the `alignment.notes` and caveats now state instead of an unqualified
"±5 m is fine".

## No turn anchors, on purpose

Both Algarve coaching models carry auto-generated names (`Turn 1…15`, and a
legacy 9-corner model whose every apex is `right`). Baking those as map labels
would decorate the map with noise and then have to be re-baked the moment the
model gets curated. Portimão's official corner names are a model slice, not an
outline slice.
