# Handoff — Slice 06: Markdown report

## State on disk

| File | Job |
|---|---|
| `product/python/lap_telemetry/session_report.py` | `render_session_report(facts)`, `report_filename(stem)`, `format_lap_time` |
| `product/python/lap_telemetry/debrief.py` | `--report-only`, `--out`, `_write_report` |
| `product/python/lap_telemetry/cli.py` | the two new flags |
| `product/python/lap_telemetry/session_consistency.py` | `LapPace.mean_gap_s` (the one denominator) |

## Usage

```bash
lap-telemetry debrief <session.parquet> --report-only            # next to the session
lap-telemetry debrief <session.parquet> --report-only --out DIR  # elsewhere
```

Prints the written path on stdout, exits 0. Under the five-lap gate it exits 1
and writes nothing.

## Report shape

`# Session debrief — <track> / <car slug>` then: Headline (three computed
sentences) · Lap by lap · Consistency · What to change (top 3) · Corners ·
Excluded laps · Not measurable · How to read this.

Verified on Paul Ricard (18/16 laps) and COTA (13 clean). Both render in ~0.1 s
after the facts are built (the facts are the slow part: ~4 s for 18 laps).

## Rules

- The renderer formats only. If a number is missing from the facts, add it to the
  facts — do not compute it here.
- Every `kind` is currently `both` for these sessions (spread ≥ 0.20 s is
  common across 13–16 laps). That is honest, not a bug; the ranking still
  separates the corners.
- The unmeasurable-channel labels live in `_CHANNEL_TEXT`; add an entry when a
  new channel can be refused (slice 04's rules).

## Tests

`dev/scripts/test_session_report.py` (+ `.js`), 30 assertions: sections and
their order, content, byte-identical determinism, refusals, the two baselines,
CLI with `--out`, CLI default location (temp copy), and the gate writing nothing.
Full suite: **1958 passed, 4 pre-existing failures**.

## Next

Slice 07 puts the coach on top: a compact 2–4 KB grounding from these facts, the
voice contract, and `--ask`. The report is the source of truth for wording;
do not build a second summary path.
