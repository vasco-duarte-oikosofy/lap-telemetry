# Handoff — Slice 53: Silverstone National / F296 debrief (quali + race)

## Result

The slice-52 assets coach these sessions correctly. Both runs resolve the
reference and the model **by (track, car)** — nothing passed by path — so this
is also the live proof of bug-27 resolution for
`(silverstone-national-circuit, ferrari-296-gt3)`.

| Session | Eligible / clean | Best | vs reference | Top priority |
|---|---|---|---|---|
| 06:52 quali | 9 / 9 | 0:54.295 | ±0.000 (the reference lap is in it) | Copse 0.216 s/lap |
| 07:04 race | 32 / 31 | 0:54.696 | +0.401 | Becketts 0.223 s/lap |

Artifacts per session in `artifacts/quali/` and `artifacts/race/`:
`facts.json` (`--json`), `report/*.md` (`--report-only --no-llm`),
`conversation.txt` (scripted REPL transcript, inputs in `inputs.txt`),
`*_plan.md`, `*_debrief.json` (transcript), plus the `--list` inventories at the
top level.

## What the coach said

**Race (31 clean laps, mean gap 0.888 s, spread 1.282 s, sd 0.320 s):**

1. **Becketts** 0.223 s/lap (25% of the gap) — brake release 94.2 km/h vs the
   reference's 98.7 in the same gear: *brake 29 m later and hold the pedal 31 m
   longer*. Also the least repeatable corner (0.697 s spread).
2. **Luffield** 0.243 s/lap (27%) — minimum speed 83.9 vs 86.1 km/h.
3. **Brooklands** 0.199 s/lap (22%) — brake release 96.0 vs 103.2 km/h.

Brake-peak data cleared "too hard on the pedal": peaks 0.51–0.75 against the
reference's 0.67, trail 0 m like the reference — the loss is *when*, not *how
hard*.

**Quali (9 clean laps, mean gap 0.688 s, spread 2.115 s):** Copse 0.216 s/lap
(31%), then Luffield 0.216 and Becketts 0.184. Copse's mechanism is exit speed
(161.8 vs 166.4 km/h onto the straight) — the coach asked whether the driver
was easing off to keep the car settled.

**Cross-session agreement** (`artifacts/cross-session-summary.txt`): the same
three corners own most of the gap in both sessions (Becketts + Luffield always
top-3, Brooklands 3rd in the race, Copse 1st in quali where the laps are more
erratic). The two flat bends behave exactly as modelled — **Maggots** ranks last
in both (0.025 / 0.026 s per lap, no braking recorded, gear 5 identical to the
reference, "purely a carry-speed corner"), and Woodcote's loss is spread-only.

That is the strongest signal that the seeded model is right: the corners it
*couldn't* detect are the ones that cost nothing, and the four it refreshed are
the whole gap.

## Two findings for a later slice (not fixed here)

1. **Quali envelope is pessimistic.** `consistency.pace` reports
   `envelope_lap_s 54.676` while the same session's best lap is 0:54.295, so
   `time_available_s` clamps to **0.000** and the report says "0.000 s is
   sitting in repeatability alone" next to a 2.115 s spread. The race session is
   fine (envelope 54.540 < best 54.696). Suspect: when the session's best lap
   *is* the reference, the envelope can land slower than the best; worth a
   `min(envelope, best)` guard (session-debrief mission, not this one).
2. **Copse's exit window is 4 m wide** (368→372), the deferred item from slice
   52's handoff, now with live evidence: in quali the coach made Copse its #1
   fix on an `exit_brake` fact backed by only **3 laps**, and the phase is
   measured across the throttle-onset point. The advice ("carry 6 km/h onto the
   straight") is sensible and the exit-speed number is real, but a 4 m exit
   means little averaging room. If Copse notes feel jumpy lap to lap, curate the
   exit from a multi-lap spread — do **not** re-run the updater.

## Verified

- `--feature session-debrief` **806 assertions / 25 scripts**, `--feature
  track-outline` **1334 / 31**, full `--pw` suite **2800 assertions / 97
  scripts — ALL PASS**.
- `npm run build` succeeded; `dist/compare.html` reverted to the committed copy
  (content identical — this slice changes no product file).
- `sessions/` untouched: the REPL writes `<session>_plan.md` and
  `<session>_debrief.json` next to its input, so both were produced in
  `sessions/` and immediately moved into the slice artifacts (the race copies
  came from the frozen `var/tmp` copy).

## Commands, as run

```bash
lap-telemetry debrief <session> --list
lap-telemetry debrief <session> --json            > facts.json
lap-telemetry debrief <session> --report-only --no-llm --out report/
lap-telemetry debrief <session>                   < inputs.txt > conversation.txt
```

Race input is the frozen closed-shard copy
`var/tmp/silverstone-national-f296-quali-race/session_20261114T070413Z_…_race.parquet`
(slice 52) — the live recording is still unfinalized.

## Untouched on purpose

Reference, coaching model, diagnostics, outline, web assets, bundle, every other
track. No product file changed in this slice; the commit is artifacts + docs
only.
