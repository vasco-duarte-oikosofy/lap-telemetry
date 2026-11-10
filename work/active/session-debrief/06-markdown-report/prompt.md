# Slice 06: Markdown report

## Goal

A driver runs one command after a stint and gets a file they can read on a phone
in the paddock: what the session was, how consistent it was, the three things to
change, the corner-by-corner evidence, and what was excluded. Deterministic —
no model, no network.

## User-visible result

```text
lap-telemetry debrief sessions/session_..._lmu.parquet --report-only
→ sessions/session_..._lmu_debrief.md
```

The report is ~120 lines of Markdown with these sections, always in this order:

1. **Title** — track, car, date, lap count.
2. **Headline** — three computed sentences: the best lap and the gap to the
   reference, the repeatability prize (envelope), and the top priority.
3. **Lap table** — every eligible lap: time, delta to the reference, delta to
   the session best, clean/not.
4. **Consistency** — best/median/worst, spread, standard deviation, envelope and
   time available, with the optimism caveat stated.
5. **Top priorities** — the first three, with kind, seconds, share of the gap and
   the computed suggestion.
6. **Corners** — the appendix table: apex distance, your minimum speed vs the
   reference, your gear vs the reference, lateral offset, and the priority
   verdict per corner.
7. **Excluded laps** — every segment that was not analysed, with its status and
   the reason.
8. **Not measurable** — channels this recording cannot support, with the reason.
9. **How to read this** — the two baselines, what the envelope is, what the
   numbers mean. No advice that is not in the facts.

## Scope

### In scope

1. `product/python/lap_telemetry/session_report.py` — `render_session_report()`,
   pure function from facts to Markdown.
2. `debrief.py` — `--report-only` and `--out DIR`; writes
   `<stem>_debrief.md` next to the session (or into `--out`), prints the path.
3. Gate unchanged: fewer than five eligible laps still exits 1 and writes
   nothing.

### Out of scope

- The conversation (slice 07), the transcript and the plan file (slice 08).
- Any chart, image or HTML.

## Rules

- **Deterministic**: rendering the same facts twice yields byte-identical text.
  No timestamps, no locale-dependent formatting, no dict ordering surprises.
- **No new analysis.** Every number in the report comes from the facts payload;
  the renderer may format, sort and group, never compute.
- **Times** are `m:ss.mmm`; deltas are signed seconds with three decimals;
  percentages are whole numbers.
- **Excluded laps are never hidden**: if a lap was dropped, the section exists
  and names the reason.
- **Unmeasurable channels are named**, not silently omitted (slice 04 refuses
  rear slip and ABS on these recordings).

## Test plan

1. Sections: every heading present, in order, on the real Paul Ricard session.
2. Content: the best lap, the reference time, the top corner name and its
   suggestion all appear; the excluded `short` lap appears with its reason.
3. Determinism: `render(facts) == render(facts)` exactly.
4. Refusals: a session whose `abs_active`/slip channels are unusable lists them;
   no `rear slip` number appears anywhere in the text.
5. CLI: `--report-only --out <tmp>` writes the file, prints its path, exits 0;
   without `--out` it writes next to the session (checked with a temp copy);
   the gate still exits 1 and writes nothing.
