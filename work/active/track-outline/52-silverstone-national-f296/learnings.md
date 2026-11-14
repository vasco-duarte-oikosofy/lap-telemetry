# Learnings — Slice 52 (Silverstone National / Ferrari 296 GT3)

## An "unfinalized" race can be a finished race

`part100..part105` of the 07:04 session all carry `session_time_s = 2010.8` and
a single repeated `lap_distance_m` (62.81 m) — the car was parked and the
recorder kept sampling. The freeze procedure ("take the closed shards below the
highest one, collapse exact-duplicate consecutive rows") turned that tail into
nothing at all, while the real race data (parts 0–99, 34 laps) came through
intact. Before concluding "the race is still running, come back later", check
the **session_time of the last few shards**: a flat tail means finished-but-
unfinalized, which is freezable today. Slices 41/42/49 needed this too; it is
now three-for-three on LMU race recordings.

## A flat bend is unmatched on *every* lap, for every car

The updater's corner-reproduction guard aborted on exactly `Maggots` and
`Woodcote` — the two bends carrying `target_throttle_pct: 100`. That is not a
defect in the lap: a flat bend produces no braking event, so `throttle_brake_v1`
can never yield a candidate for it, on any lap, in any car. Consequences:

- When onboarding a **new car** on a track whose curated model has flat bends,
  the seed is preserved verbatim and the correct invocation is
  `--preserve-geometry <flat ids>` — *not* `--allow-unmatched`, which would keep
  the geometry but silently leave the door open for other corners to go unmatched.
- `--preserve-geometry` needs no `--allow-unmatched`; passing both is redundant
  and hides which corners were expected to be odd.

## Seeding curation from another car is the cheap path — but check the exit gaps

`seed_model_from_curated.py` (copy corners, repoint `reference_lap`) plus one
`--ref` run is all a new car on an existing track needs (same shape as slice 43).
The interesting judgement is which corners to let the detector refresh:

- The P3 model's `Copse` exit (435 m) is 76 m past its apex — a **hand-reviewed
  outlier**. Across the corpus, exit gaps of 0–14 m past the apex are the norm
  (checked: ~150 corners). So refreshing Copse from the F296 lap to
  `206/368/372` is consistent with the repo, and preserving the P3's 435 would
  have imported *another car's* hand-tuning into a fresh model.
- Rule of thumb that came out of this: preserve a zone only when the **detector
  is blind to it** (flat/no braking event), not merely because its geometry
  "looked hand-tuned" on the donor model. Otherwise you keep stale geometry for
  a new car.

## `lap_length_m` is per track, not per car

Two models on one track must share the `lap_length_m` axis (2639.1 here) because
the baked outline normalises turn anchors by it. The seed copies it from the
donor model instead of recomputing `max(lap_distance_m)` from the new reference
(2632.97 on this lap — 6 m shorter). Recomputing would have quietly desynced the
model from the outline and the TinyPedal `s_frac` denominators.

## Test the outline contract, not the outline file

The trigger said "we already have the outline, no need for outline now". The
outline is selected by "alphabetically-first model with named corners", so the
new `…_vista-af-corse-2026-21-lm.json` does **not** become the baking source and
nothing had to change. That is fragile enough to pin: the slice's test asserts

- outline anchors == the **P3** model's apices (still the baking source), and
- outline anchors != the **F296** model's apices,

so an accidental re-bake in a later slice fails loudly instead of silently
moving map labels on a track whose visual QA predates this work.

## Small mechanics worth reusing

- `glob.glob(...)` returns `str` even when built from a `Path` — `p.name` blows
  up (`freeze_source.py` first run). Use `Path(p).name`.
- `load_track_coaching_model()` returns `Corner` dataclasses with **no**
  `apex_side_source` field. To assert curated-field parity (including that
  field), compare the raw JSON of both models, not the loaded objects.
- The reference validator prints `legacy-time delta 0.1xs vs lap_time_s` for
  every pre-authoritative export; it is informational, not a failure — the new
  reference shows the same line as the P3 one.
