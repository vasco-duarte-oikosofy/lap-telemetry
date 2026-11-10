# Slice 07: LLM debrief summary

## Goal

Give the driver a coach's voice on top of the deterministic facts: one opening
debrief and one-shot answers to questions, grounded strictly on the facts, with
the numbers traceable and the voice recognisably a race driver who has coached
before.

## User-visible result

```bash
lap-telemetry debrief <session> --ask "where am I losing the most time?"
lap-telemetry debrief <session> --ask "why was Bretelle so bad?" --no-llm
```

## Scope

### In scope

1. `product/python/lap_telemetry/session_brief.py` — the **grounding**: a compact
   text block (~2–4 KB) built from the facts (session meta, lap table,
   consistency, top priorities, offenders, excluded laps, unmeasurable
   channels), plus `corner_block()` for a named corner and `find_corner()` for
   matching the driver's words ("Bretelle", "corner 2", "turn 12").
2. `product/python/lap_telemetry/coach/debrief_coach.py` — the voice contract,
   message assembly, the model call (via the shared `call_llm`), a deterministic
   template adapter for `--no-llm`, and **number validation** of the reply.
3. `debrief.py` / `cli.py` — `--ask QUESTION` and `--no-llm`.

### Out of scope

- The multi-turn REPL, transcript and plan file (slice 08).

## Grounding rules

- The model **never** receives the raw per-lap-per-corner facts (338 KB for 18
  laps). It receives the grounding plus, when the question names a corner, that
  corner's per-lap block.
- The grounding is capped at **4096 bytes**, the corner block at 1500.
- Every number in the grounding comes from the facts; nothing is recomputed.

## Voice contract (system prompt)

Warm, demanding, credible; a Hypercar/GT3 driver who has sat in the debrief room.

- One real positive first, with a number.
- Then the single biggest recurring loss, with its number and its mechanism.
- One fix at a time; at most three coaching points.
- At most ~120 words. Exactly **one** question back to the driver.
- Direct about pace: never soften a 2 s gap into "a little off".
- No invented numbers: if it is not in the grounding, it does not exist.
- No preamble, no bullet dumps, no motivational filler.

## Validation

The reply is checked against the grounding:

- **Numbers**: every numeric token in the reply (times, seconds, km/h, gears,
  metres, percentages) must appear in the grounding or the corner block. A
  mismatch is a **warning printed to stderr**, not a failure — the coach may
  legitimately say "two" or round.
- **One question**: a reply with zero or more than one `?` warns.
- **Length**: more than 160 words warns.

## Test plan

1. Grounding: contains the track, both baselines, the top three priorities, the
   consistency numbers; is at most 4096 bytes; mentions no raw corner history.
2. `find_corner`: matches names, ids, "corner N", "turn N", case-insensitively;
   returns None for an unknown corner.
3. `corner_block`: per-lap values for that corner, the reference's values, and
   the spread; at most 1500 bytes.
4. Messages: the system prompt carries the voice contract; the user message
   carries the question and, when a corner is named, the corner block.
5. Validation: an invented number warns; a number from the facts does not; two
   questions warn; a 200-word reply warns.
6. Template adapter (`--no-llm`): grounded answer, at most three points, exactly
   one question, and every number in it appears in the facts.
7. CLI: `--ask ... --no-llm` prints an answer and exits 0; `--ask` without a
   usable provider explains itself and exits 1.
