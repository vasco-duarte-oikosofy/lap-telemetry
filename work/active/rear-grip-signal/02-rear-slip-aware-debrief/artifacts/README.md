# Slice 02 artifacts — real-session verification

Both directories were produced by this slice's code on committed sessions. The
saved debriefs under `var/debrief/` were **not** overwritten.

| file | how it was produced |
|---|---|
| `*_debrief.md` | `python -m lap_telemetry debrief <session> --report-only --out <dir>` |
| `grounding.txt` | `build_grounding(facts)` — exactly what the model is allowed to read |
| `opening-no-llm.txt` | `DebriefCoach(model=None).ask("give me the debrief", facts)` |
| `becketts-answer.txt` | `python -m lap_telemetry debrief <session> --ask "what am I losing at Becketts?" --no-llm` |
| `plan.md` | `render_plan(facts, build_targets(facts))` — the sheet the driver takes away |
| `rear-stability.json` | `rear_stability.assess_session(facts)`, all corners, with the grip-channel refusal |

## Silverstone National P3 race, 2026-11-14 19:04 (the session that triggered the mission)

The old debrief said, unconditionally, "hold the brake 20 m longer" at Becketts.
The measured rear slip on that lap is **13.78°** at the apex (5.61° with the brake
still applied) against a **1.71°** clean-lap baseline, so the advice is now:

> the rear was measured sliding under braking (segment 14, lap 14) … release the
> brake a little earlier and get the car settled before asking for more brake or
> speed, then re-measure

and the plan target is a stability number, not a higher speed.

## Barcelona / Ginetta P3 race, 2026-11-15 18:44 (the slide the driver described)

Repsol, segment 6: **6.51°** at the apex, **4.87°** with the brake applied,
against a 1.74° baseline. Repsol ranks #4, so it is not one of the three plan
targets — the plan therefore carries a separate "Also measured" line, which is
the case that a naive top-3-only implementation would have dropped.
