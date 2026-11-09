# Learnings — Slice 49 (Imola / F296 quali + race)

## The chicane halves fight each other, and the winner flips

The old model had the **first** half of each chicane (Villeneuve 1, Acque 1,
Alta 1) owning the single braking event and the second half unmatched. On
lap 14 the detector's apex landed a few metres closer to the *second* half, so
the matcher (bug 29's nearest-first rule working exactly as designed) handed the
event to the second half and reported the **first** half unmatched.

Nothing was corrupted — unmatched corners keep their geometry — but the model
would silently have ended up with Villeneuve 1 on Ginetta-era coordinates while
Villeneuve 2 jumped onto Villeneuve 1's apex. `--preserve-geometry` on the
*second* halves is what keeps the pairing stable, because they are the halves
that genuinely have no braking event of their own.

**Generalisation for the next agent:** bug 29's fix made matching *correct*, not
*stable*. For multi-apex complexes where two curated corners sit inside one
detected event, decide ownership once (by signal evidence across many laps) and
freeze it with `--preserve-geometry`. Never rely on the matcher to re-derive it
per lap — the nearest corner can flip by 3 m of apex noise.

## `--allow-unmatched` is not a substitute for `--preserve-geometry`

Both let the run proceed, but they mean opposite things:
`--allow-unmatched` waits to see which corners fail (fine for a *dry* run),
while `--preserve-geometry` decides *up front* which corners must never claim an
event. For a known compound chicane, only the second one produces a stable
model.

## The "STALE outline" was a short_name-only diff

`bake_outline_turns.py --check` reports Imola as STALE, before and after this
slice. Running the bake in a scratch copy showed all 11 anchors move **0.00 m**;
the only diff is that the baker fills `short_name` on Rivazza 1/2 from the model
while the committed outline keeps `null`. So "STALE" here does not mean the map
is wrong — it means the outline predates the short-name pass. Don't panic, and
don't "just re-bake" a track whose map labels were visually approved earlier.

## An unfinalized session can still grow *during* your own slice

The first scan found 93 `partN` shards; the freeze a minute later found 94. The
freeze logic (all but the highest, dedupe exact consecutive rows) handled it, but
the manifest must be written **from the shard list the freeze actually used**, not
from a list captured earlier — otherwise the "shards unchanged" audit compares
the wrong set.

## `track_slug_from_path` + sidecar is the whole contract

The frozen file has no real sidecar, so a file named `race_merged.parquet` in a
scratch dir parses as track `race_merged` and `read_vehicle_name` returns `""`.
Naming the frozen copy with the **canonical session basename** and writing a
two-field sidecar next to it makes the exporter and the reference validator
accept it with zero new code paths. Cheaper than teaching the tools about
scratch directories.

## The updater's dry run is `--max-geometry-delta-m 0.5`

There is no `--dry-run`. A geometry guard tighter than any real move aborts
before writing *and* prints the full per-corner before/after table — the fastest
way to review a refresh without touching product data. Do that first, then run
the real thing with a human-scale guard (40 m here).
