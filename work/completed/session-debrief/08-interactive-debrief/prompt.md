# Slice 08: Interactive debrief

## Goal

The point of the mission: a driver finishes a stint, runs one command, and has a
conversation that ends with two or three measurable targets for the next stint —
with the transcript and the plan on disk next to the session.

## User-visible result

```text
$ lap-telemetry debrief sessions/session_..._lmu.parquet
Coach: Your best lap was 1:19.135, 1.969 seconds off the reference…
       What does the car feel like at corner 2?
You:   it felt like it wouldn't rotate on entry
Coach: …
You:   /corner Bretelle
Coach: …
You:   /plan
→ sessions/session_..._lmu_plan.md
You:   /quit
→ sessions/session_..._lmu_debrief.json
```

Commands: `/corner <name>`, `/laps [3,4,5]`, `/plan`, `/save`, `/help`, `/quit`.
Anything else is a question for the coach.

## Scope

### In scope

1. `product/python/lap_telemetry/session_conversation.py`:
   - `Conversation` — history, command handling, the coach call per turn.
   - `run_repl()` — reads input, prints answers, saves on exit.
   - `build_targets()` — two or three measurable targets from the priorities.
   - `write_transcript()` / `write_plan()` — the two artifacts.
2. `debrief.py` / `cli.py` — the default (no flag) starts the conversation;
   `--no-llm` gives the template coach in the REPL too.
3. `SessionDebriefFacts.to_dict()` gains `session_id` (the session stem) for the
   future cross-session profile.

### Out of scope

- Anything the spec lists as future work (cross-session memory, setup
  hypotheses, TTS).

## Artifacts

| File | Content |
|---|---|
| `<stem>_debrief.json` | the facts payload + `transcript` (driver and coach turns, with warnings) + `targets` |
| `<stem>_plan.md` | two or three numbered targets, each with the number to hit and the loss it addresses |

Both land in the same directory as the report: next to the session, or `--out`.

## Targets

Built from the top priorities, deterministically (the coach does not invent
them):

```text
1. Corner 2 — carry 27 km/h more minimum speed and one gear higher at the apex
   (3rd, not 2nd).
   Measured now: 0.702 s lost per lap, 23% of your gap.
   Target: 136.3 km/h at the apex, against 108.9 today.
```

Two targets when the third costs less than 0.1 s per lap; never more than three.

## Test plan

1. `/laps` prints the lap table; `/laps 4,5` restricts it; a bad list is handled.
2. `/corner Bretelle` answers about that corner and records both turns; an
   unknown corner says so.
3. `/plan` produces 2–3 numbered targets with numbers, writes `_plan.md`, and the
   file content matches what was printed.
4. `/save` writes `_debrief.json` with `session_id`, `schema_version`, the facts
   and the transcript so far.
5. `run_repl` over piped stdin: questions are answered, `/quit` ends it, and the
   transcript is saved on exit.
6. The CLI with no flags and piped stdin runs the REPL and exits 0.
