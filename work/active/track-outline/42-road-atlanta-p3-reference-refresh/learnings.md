# Learnings — Slice 42 (Road Atlanta P3 reference + model refresh)

- **"P3" here means the DKR Engineering LMP3 car, not "practice 3".** The
  project's shorthand for `dkr-engineering-4-elms25` is P3 (see commit
  `fe29da7` "Interlagos Ginetta P3"), so "the P3 / Road Atlanta session" is
  simply any Road Atlanta recording in that car. Today there were two practice
  sessions, one qualifying and one race; the **race** held the fastest lap.
  Resolve the session from lap times, not from the session-type label:
  practice best 1:17.224, quali best 1:17.419, race lap 17 **1:15.815**.
- **The fastest lap came from the last stint, not the first.** Laps 12-17 of
  the race trend 1:18.66 → 1:15.66 as fuel burned off. A `groupby(lap_number)`
  scan would have found it, but only segment-based `find_complete_laps` gives
  the *authoritative* time (75.815) that differs from `lap_time_s` (75.658) by
  0.16 s on this lap — the scorer's value is systematically early here.
- **A faster lap mostly moves apexes forward, and that is information.** Every
  matched corner's apex moved *later* by 3-32 m and every minimum speed went
  up. The old model was not wrong; the driver now brakes later and carries more
  speed. Only Turn 2's apex moved as much as +32 m (min speed +10.9 km/h), which
  is the one worth eyeballing in the app.
- **The five curated flat markers are exactly the corners the detector cannot
  reproduce** — `t4`, `t8`, `t9`, `t11`, `t12` run at throttle 1.00 with zero
  brake pressure on both laps. So "unmatched" is the *expected* outcome for
  them, not a failure. The `signal-review.txt` receipt makes that provable in
  one table instead of an argument.
- **Turn 3 is a compound-corner trap on this track.** It sits inside the Turn 2
  braking zone (apex 835 m vs Turn 2's 855 m), so the detector emits one event
  and the curated `t2` claims it. Preserve `t3` or the same braking event gets
  claimed twice.
- **`--max-geometry-delta-m 1` is the cheapest way to get a read-only diff.**
  One run prints every matched corner's before/after and writes nothing. Same
  trick as slice 41: probe first, then decide the real threshold (40 m here).
- **The re-bake trap is still live.** `bake_outline_turns.py` writes the model's
  *speech* `short_name` into the outline's *map label* field, so a bake turned
  Road Atlanta's deliberately label-free map into `1`…`12` pills.
  `test_outline_turns.js` (BAKED_SHORT_NAMES) catches it; the fix here is
  `artifacts/restore_display_labels.py`, which copies `name`/`short_name` back
  from the pre-bake outline while keeping the new anchors. This is the second
  slice to hit it — the bake should preserve existing labels.
- **Changing the reference breaks tests that pin its filename.** Two bug-28
  guards (`test_lap_duration_surfaces.py`, `test_compare_reference_duration.js`)
  hardcode `…_time_01.16.304.parquet`; one of them also pins a coaching delta
  (+0.113 s) that shifts with the reference (+0.602 s). Budget for it: the
  reference refresh is never a data-only change.
- **A race that has finished is not a finalized session.** The timer showed
  `session_time_remaining_s ≈ -99` and the car sat on lap 21, but the sidecar
  stayed `in_progress: true` and the recorder kept writing idle shards. Freeze
  the closed shards and record the source hashes; do not wait for a canonical
  file that may never appear.
