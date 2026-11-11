# Learnings — Slice 51: Silverstone National Circuit / Ginetta P3

## 1. A 2.64 km circuit is shorter than the pipeline's minimum lap

`MIN_LAP_TIME_S = 60.0` in `export_fastest_reference_laps.py` silently rejected
*every* lap of this track: the National loop is ~51 s in LMP3. The symptom is
`No complete laps found` on a session whose `summary` shows ten valid laps — not
an error message about the floor. If a new combo produces "no complete laps" but
the lap times look sane, check that floor first.

The fix is an explicit `--min-lap-time-s` on both the exporter and the updater
(the updater delegates the export, so it must forward the flag or the track
becomes un-updatable forever). Don't lower the default: the floor exists to
reject lag/bogus samples on every other track.

## 2. Short-circuit laps also fool the row-count sanity rule

`validate_reference_laps.py` compares `num_rows` against `lap_time × 50 Hz`
within 10 %. A 50.4 s lap is ~2520 rows, so a lap-time/row mismatch of 40 rows is
already 1.6 % — fine. But the same rule means a *slow* pit lap on a short circuit
(86 s, 4303 rows) still passes. It is not a validity signal on short tracks.

## 3. The National's "Maggots" is a flat LEFT and "Becketts" is the braked RIGHT

The official National corner list (Silverstone / oversteer48) is Copse, Maggots,
Becketts, Brooklands, Luffield, Woodcote. Signals on the curated reference:

- **Maggots** — steering −0.07, throttle 1.00, brake 0.00 (a flat left flick;
  invisible to a brake/lift detector, curated by hand, `target_throttle_pct: 100`).
- **Becketts** — the braked right (peak brake 0.71, min speed 202 km/h→114) that
  peels off the GP tarmac onto the Wellington Straight. On the National the car
  never turns left through the GP's Becketts complex, so this single right *is*
  the National's Becketts; the "short left-right flick" is Maggots→Becketts.

The repo's curated **GP-ELMS** model calls the GP's right-at-1050 apex "Maggots"
and the left at 1194 "Becketts Entry". That's the GP's own numbering, which does
not transfer: don't copy names across layouts by distance, only by corner.

## 4. Copse's exit is throttle modulation, not a corner boundary

Across 21 clean laps the detector's Copse exit spreads **113 m** (363–476 m).
On the onboarding lap (0:50.859) the driver braked to 0.73 and held
partial throttle 0.57–0.76 for ~100 m, so the detector's exit was 435 m. On the
faster lap (0:50.446) the driver brakes only to 0.38 and is at full throttle from
370 m, so the exit collapses to **369 m — 4 m after the apex**.

The geometry guard (`--max-geometry-delta-m 40`) caught it as `dExit 66 m`. Treat
a "zone that ends within a handful of metres of its apex" as a detector artifact
and use `--preserve-geometry`. This is the Tamburello rule (slice 44) again.

## 5. Preserving a corner can create a chained-zone overlap with a refreshed neighbour

Preserving Maggots at `[790, 836, 860]` while Becketts refreshed to entry **854**
overlapped the two zones by 6 m — the updater's `prevent_zone_overlap` only runs
on detected candidates, so it cannot see preserved corners. The runbook's Step 6
("fix any zone boundaries that the detector got wrong") covers this: Maggots'
exit moved 860 → 850 m, and the flat contract still holds (throttle 1.00 with
zero brake through 851 m on the reference lap). **Always re-check
`a.s_end_m <= b.s_start_m` after a refresh that mixes preserved and matched
corners.**

## 6. Keeping the outline compact

`bake_outline_turns.py` rewrites the whole outline with `json.dumps(indent=2)`,
turning a 351-line compact outline into ~6000 lines (Road Atlanta's refresh
diff was that big). The one-shot creator's `compact_outline()` writes the same
data in 351 lines; reuse it for re-bakes of this track. The 437-line ceiling in
`AGENTS.md` is about source files — outline JSONs legitimately run to thousands
of lines — but churn is still a review cost.

## 7. The newest recording is not always the fastest one

Session order today: practice 17:22 (best 50.859) → practice 17:32 (best
**50.446**) → garage stint 17:49 (no complete lap) → quali 17:52 (best 50.673) →
race 18:03 in progress (best 50.638). The winning lap was in the *second* stint,
and the last two sessions were slower. Always scan every session of the combo
with the 30 s floor before concluding "the new session is faster".

Also: a session that looks "new" can be worthless — the 17:49 recording is
192 s of the car sitting in the garage on lap 28, 9599 rows, zero complete laps.

## 8. In-progress race recordings write `snapN`, not `partN`

The 18:03 race produced one `snapN.parquet` per completed lap (sequential, not
cumulative), plus a sidecar with `in_progress: true` and no canonical `.parquet`.
Concat in numeric order to read it (slice 42's `freeze_source.py` pattern, but
each snapshot is *one lap*, so there are no boundary-duplicate rows to collapse).
Don't feed the live highest snapshot to the updater — it is still being written.
