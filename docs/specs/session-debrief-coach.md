# Session Debrief Coach

Status: planned (2026-11). Implementation tracked in
[`work/active/session-debrief/PLAN.md`](../../work/active/session-debrief/PLAN.md).

## Purpose

Turn a **whole recorded session** into a coached conversation.

Today the coach only knows how to compare one lap to one reference and say
one sentence about it. After a stint the driver has 5–25 laps of telemetry,
no way to see which mistake actually repeats, and no way to ask "why was I
slow in turn three?".

The debrief answers that: it analyses every eligible lap of a session, finds
what is *repeatedly* and *inconsistently* costing time, and then a
driver-coach dialogue — grounded strictly on those facts — turns the analysis
into two or three concrete things to change on the next stint.

The user story:

> I finish a 20-lap practice stint. I run one command. The coach tells me one
> thing I did well, the one corner where I am losing the most time and why,
> asks me one question about how the car felt, and after a short back-and-forth
> writes me a plan for the next stint with numbers in it — "brake five metres
> later into Campsa, carry three kilometres per hour more minimum speed".

## Goals

- Analyse **one session** end to end: laps, per-corner phases, consistency,
  and where the time is.
- Work with **one curated reference lap** (absolute target) *and* the
  **session's own best lap** (consistency yardstick). Both matter; losing
  2 s to a reference tells you nothing about repeatability, and being
  consistent at a slow pace tells you nothing about the target.
- Produce a **deterministic report** that is useful with no LLM at all, so
  tests and offline use never depend on a network call.
- Support a **multi-turn conversation** on top of that report, where every
  number the coach states is traceable to the facts.
- Keep the coach's **voice** consistent: warm, demanding, a Hypercar/GT3
  race driver who has coached before.
- Everything runs on the same Windows machine as the sim, from PowerShell,
  with no POSIX-only assumptions.

## Non-goals

- No web/UI work. Terminal first; `dist/compare.html` is untouched.
- No TTS. This is a post-session, text-first product.
- No setup engineering, tyre modelling, weather or track-evolution
  modelling, traffic awareness, or video.
- No automatic reference-lap or coaching-model generation. The guarded
  pipelines in `dev/scripts/` stay the only way those are produced.
- No live/real-time behaviour. The live coach keeps its own pipeline.
- No cross-session memory in this mission (see *Future* below).

## Inputs

### Session source

- A single session Parquet, or a session recorded as rotation shards
  (`session_<utc>_<track>_lmu.part0.parquet`, `.part1.parquet`, …).
- **Shards are merged automatically**, in numeric part order, before any
  analysis. The merged view is in memory only; nothing is written to disk.
- Session metadata (track, vehicle, sample rate, start/end) comes from the
  sidecar `.json`. When the sidecar is missing, `--track` and `--car` must
  be supplied explicitly.

### Reference and coaching model

- Resolved per **(track, car)** exactly as the live coach does today, via
  `reference_resolver` / `track_model_resolver` / `vehicle_catalog.json`.
  Liveries of one car model share a canonical slug (bug 27).
- The reference **duration** is the time the export certified (the
  `<mm>.<ss>.<mmm>` in the filename, or the `authoritative_lap_time_s` metadata
  stamp when present), never a re-derivation: an extracted reference is a single
  segment, so the telemetry-clock method is unavailable and the fallback scorer
  value reads up to a second high. Every lap delta is measured against it.
- A curated reference lap and coaching model are **required**. Missing data
  is an error with an actionable message pointing at
  `docs/HOW_TO_CREATE_A_COACHING_MODEL.md`, never a silent car-blind
  fallback.
- `--reference` and `--track-model` override resolution for experiments.

### Session gate

A session is debriefable only if it yields **at least five eligible laps**.
Fewer than that and the tool exits non-zero, prints the per-lap rejection
reasons, and says what is missing. Five is the minimum for spread and
"recurring" to mean anything.

## Lap eligibility

Lap identity is the **contiguous segment** `(lap_number, start_row, end_row)`
from `build_segments`, never `lap_number` alone: a sim restart mid-session
resets `lap_number` to 0, so filtering a whole file by `lap_number` silently
concatenates two different stints (observed in
`session_20260524T141613Z_paul-ricard---3a_lmu.parquet`).

Each segment is classified as one of:

| Class | Rule |
|---|---|
| `eligible` | Full distance coverage, duration within a plausible band of the reference, not the first segment of a stint, not the final segment of the session |
| `out-lap` | First segment of a stint that starts in the pits (low speed at the start, full-ish duration) |
| `in-lap` | Duration far below the reference band (e.g. 21.9 s vs a 79.5 s reference) |
| `pit-lap` | Duration above the band |
| `incomplete` | Distance coverage fails (existing `PartialLapError` guard), or the segment is the last of the session |
| `short` | Far fewer or far more frames than the duration implies (broken segment) |
| `invalid` | `lap_valid` discriminates in this session and any frame of the segment is `False` |

Default rules, all overridable:

- Duration band `[0.85, 1.20] × reference lap time`. The existing live guard
  (1.15×) is too loose: a 90.7 s pit-stop lap against a 79.5 s reference is
  1.14× and slips through.
- `lap_valid` is honoured **only when it discriminates**: if every frame in
  the session has the same value, the column is treated as unreliable
  (observed both all-`False` on valid laps and all-`True` including a
  8896 s pit segment), the session is debriefed, and a warning is printed.
- Out/in/pit/incomplete laps are **excluded** from the analysis and listed in
  the report with the reason. They are never silently dropped.

## Analysis layers

### 1. Per-lap facts

For every eligible lap, the existing comparison engine
(`lap_comparator.compare_laps`, extended to accept a segment range) produces
per-corner, per-phase facts against the curated reference, **without the
live `top_n=3` cap** — the debrief needs every corner, not the top three.

### 2. Consistency

Computed against the **session's own best eligible lap** (a lap cannot be
unreliable against itself):

- **Optimal lap** from best sector times, when the session has sectors
  (`last_sector_1_s` / `last_sector_2_s`); older recordings without the
  columns fall back to a per-corner minimum-speed proxy and say so.
- Lap-time spread: best, median, and each lap's delta to best.
- Per corner and phase: spread of minimum speed, entry distance, exit
  distance, apex offset, and apex offset drift. Spread — not mean — is the
  consistency signal.
- A ranked list of the corners that cost the most time through
  **inconsistency** (big spread, high corner weight), separate from corners
  that cost time **every lap** (big mean loss).

Both matter and must stay separate: "you are slow here" and "you are
inconsistent here" need different coaching.

### 3. Extended corner facts

All channels below already exist in the recorder schema for current
sessions; older sessions that lack a column degrade gracefully (the fact is
omitted, never zero-filled).

- **Gear**: minimum gear in the corner, gear at apex, gear at exit.
- **Braking**: peak brake pressure, brake area (integral of pressure from
  entry to apex), and **trail-braking depth** — how far past the apex brake
  pressure is still applied.
- **Steering**: steering reversals and rate variance inside the corner
  (mid-corner correction proxy).
- **Rear slip**: maximum rear slip angle in the corner and at exit
  (oversteer / stability proxy).
- **Electronics**: `tc_active` / `abs_active` duty in the corner.
- **Line**: lateral path offset at apex versus the reference, when
  `path_lateral_m` exists.

### 4. Improvement priorities

A ranked, deduplicated list of opportunities. Ranking combines:

1. mean time lost per lap in that corner/phase (recurring),
2. consistency spread in the same corner/phase (fixable),
3. the corner's share of the total gap.

Each priority carries a deterministic **suggested change**, derived from the
reference's own phase distances, e.g. "brake 6 m later", "back on throttle
9 m earlier", "carry 4 km/h more minimum speed", "one gear lower at the
apex", "release the brake 3 m past the apex". The suggestion is computed,
not invented by the model.

## Conversation model

- The model receives a **compact report** (~2–4 KB: session meta, lap table,
  optimal lap, top priorities, consistency offenders) in the system prompt.
  The raw per-corner-per-lap history (~100 KB for 20 laps) is **never**
  injected wholesale.
- Drill-down facts are injected on demand:
  - automatically, when the driver's message names a corner (matched against
    `name`, `short_name`, and `corner_id`);
  - explicitly, via `/corner <name>` and `/laps <list>`.
- Every turn: **at most three coaching points, at most ~120 words**, and
  **exactly one question** back to the driver. The driver's answer is kept in
  the transcript and is available to later turns (so "it felt nervous on
  entry" can be reconciled with the telemetry).
- Numbers in the reply must exist in the injected facts. The prompt forbids
  invented values and the reply is validated against the fact numbers where
  cheaply possible (a warning, not a hard failure, on mismatch).

### Coach voice contract

Warm, demanding, credible. A Hypercar/GT3 driver who has sat in the debrief
room and knows how to say hard things without deflating anyone.

- Open with one **real** positive, with a number. Praise is earned, never
  generic; if there is nothing good to say, say the one thing that is
  objectively true (e.g. "you completed all nineteen laps").
- Then the single biggest recurring loss, with its number and its mechanism
  ("you are losing it on entry, not on exit").
- One fix at a time. A demanding coach does not hand out five homework
  items.
- Be direct about pace: never soften a 2 s gap into "a little off".
- Ask one concrete question and wait for the answer.
- When the driver reports progress, say whether the numbers agree.
- No lectures, no bullet-point dumps in conversation, no motivational filler.

## Outputs

All three land next to the session, in the gitignored `sessions/` directory:

| File | Content |
|---|---|
| `<session>_debrief.md` | Deterministic human report: session summary, clean-lap table, optimal lap, top priorities with numbers, per-corner appendix |
| `<session>_debrief.json` | Machine-readable facts + transcript, forward-compatible with a future cross-session profile (`session_id`, `track`, `car_slug`, `schema_version`) |
| `<session>_plan.md` | Two or three measurable targets for the next stint, written by the coach at `/plan` |

`--out <dir>` relocates them. `--report-only` writes the report and does not
start the conversation. `--ask "<question>"` runs one question non-interactively
and prints the answer (used by tests and scripting).

## CLI

```text
lap-telemetry debrief <session.parquet|dir>
    [--list]                 # print the lap inventory and exit
    [--json]                 # print the facts JSON and exit
    [--report-only]          # write the report, no conversation
    [--ask QUESTION]         # one-shot question
    [--laps 3,4,5]           # restrict to these lap numbers
    [--track NAME] [--car NAME]
    [--reference PATH] [--track-model PATH]
    [--out DIR] [--config coach_config.toml] [--no-llm]
```

`--no-llm` produces the full deterministic report with the template adapter
path; the conversation is the only feature that requires a model.

## LLM configuration

Reuses `coach_config.toml` and the existing `LLMConfig` loader. The debrief
runs against **Ollama** (local or `ollama.com`), configured by
`[llm] provider = "ollama"` plus `OLLAMA_API_KEY` in the environment. No new
provider plumbing and no credentials in files. Only the derived facts
(a few KB) leave the machine — never raw 50 Hz telemetry.

## Known limitations

- **Fuel load** changes lap time within a stint (lighter later laps are
  faster). The debrief does not correct for it; it reports fuel level per lap
  so the driver can see the trend, and the report says when the correlation
  between fuel and lap time is strong enough to muddy consistency.
- **Track evolution / weather** are not modelled; the report notes when
  `session_time_s` vs lap time trends suggest a changing track.
- **Traffic and off-track excursions** are not classified; moderately slow
  laps stay in the analysis but are excluded from the clean-lap consistency
  set, and counted.
- **`lap_valid`** is unreliable in older recordings (see above).
- **Sectors** are absent from older recordings; the optimal-lap number is
  then a proxy and is labelled as such.
- **Multi-apex corners** inherit the existing ambiguity in the coaching
  models (chicanes and double-apex sweepers are one corner with one apex).
- **Setup changes** between stints are invisible; a session with a setup
  change in the middle will look like an inconsistency.

## Success criteria

For a real session with at least five eligible laps:

1. `lap-telemetry debrief <session> --report-only --no-llm` exits 0 and writes
   a report whose priorities point at corners that a human watching the laps
   would recognise.
2. The report separates "slow every lap" from "inconsistent", and the optimal
   lap is within a plausible margin of the best lap.
3. The conversation answers a follow-up about a named corner using that
   corner's per-lap numbers, and every number it states is present in the
   facts.
4. `/plan` produces two or three targets a driver can act on without opening
   the telemetry.
5. No out-lap, in-lap, pit-stop lap or incomplete lap appears in the analysis,
   and every excluded lap is listed with its reason.

## Open questions (future work, not this mission)

- **Cross-session memory**: "this is the third session you have lost time in
  turn 3 entry" is the real multiplier. Needs a per-(track, car) profile
  accumulated across debriefs. The JSON schema is designed so this can be
  added without changing the analysis layer.
- **Setup hypotheses**: once consistency is understood, recommending a
  setup direction (more front wing, softer rear) needs modelling that does
  not exist here.
- **Voice**: speaking the debrief through the existing TTS path is cheap and
  possibly pleasant, but it is not the problem this mission solves.
- **Wet/dry and temperature** require session-type and weather channels the
  recorder does not yet store.
