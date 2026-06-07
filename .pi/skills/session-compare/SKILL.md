---
name: session-compare
description: Compare session laps against a reference lap for a track+car combo. Shows corner-by-corner time loss, delta traces, and ranked zones. Supports side-by-side comparison of two session sets (e.g. two different days). Use when the user asks about lap analysis, time loss, where they're slow, or comparing sessions.
---

# Session Compare

Analyzes your driving session against a reference lap, breaking down where time is lost corner by corner. Can also compare two sessions side-by-side.

## Setup

No setup required. Uses Python packages already installed for the project (`pandas`, `numpy`).

## Usage

### Single session analysis

When the user provides a session (file path, glob, or description) and a track/car combo:

```bash
python .pi/skills/session-compare/scripts/compare_session.py \
  sessions/session_20260607T053252Z_fuji-speedway-classic_lmu_race.parquet \
  --ref product/data/reference-laps/fuji-speedway-classic_vista-af-corsa-2026-54-wec_time_01.38.541.parquet
```

The coaching model JSON is auto-detected from the reference lap filename (matching track+car in `product/data/track-coaching/`).

### Side-by-side comparison of two session sets

When the user wants to compare two days/sessions against the same reference:

```bash
python .pi/skills/session-compare/scripts/compare_session.py \
  sessions/*0606*fuji-speedway-classic*.parquet \
  --ref product/data/reference-laps/fuji-speedway-classic_vista-af-corsa-2026-54-wec_time_01.38.541.parquet \
  --compare sessions/*0607*fuji-speedway-classic*.parquet
```

### JSON output (for further processing)

Add `--json` for machine-readable output.

## How to find the right files

1. **Sessions**: List `sessions/` for `.parquet` files matching the user's track/car/date.

   ```bash
   ls sessions/*fuji-speedway-classic*.parquet
   ```

   Use `python -m lap_telemetry.cli summary <file>` to inspect each session (track, car, lap times).

2. **Reference lap**: Find in `product/data/reference-laps/` matching the track and car.

   ```bash
   ls product/data/reference-laps/*fuji*classic*
   ```

   The reference filename format is `<track>_<car>_time_<MM.SS.mmm>.parquet`.

3. **Coaching model** (corners): Auto-detected, but you can specify with `--coaching`:

   ```bash
   ls product/data/track-coaching/*fuji*classic*
   ```

## Interpreting the output

- **Delta**: Time difference vs reference. Positive = slower than reference.
- **Time lost per corner**: How much delta accumulates from corner entry to exit. Negative = you gained time.
- **Consistency**: Percentage of your laps where time was lost in that zone. Higher = more consistently slow there.
- **Speed diff**: Your apex speed minus reference apex speed. Negative = slower at apex.
- **Zone ranking**: 300m windows where delta consistently grows across your laps.

### Key patterns to look for

- **Delta monotonically increasing**: You never recover time once lost — focus on early corners.
- **Large apex speed deficit**: You're braking too early / over-slowing. Brake later, trail deeper.
- **Exiting slow**: You carry deficit from apex through exit. Rotate the car or get on throttle sooner.
- **Consistent loss (>80%)**: A real driving habit you can target, not traffic or one-off mistakes.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `sessions` | Yes | Primary session parquet file(s) |
| `--ref` | Yes | Reference lap parquet path |
| `--coaching` | No | Coaching model JSON path (auto-detected) |
| `--compare` | No | Comparison session files (side-by-side mode) |
| `--min-time` | No | Min lap time filter (default: 97s) |
| `--max-time` | No | Max lap time filter (default: 110s) |
| `--json` | No | Output raw JSON instead of formatted text |

## Workflow

1. Identify the session files from the user's description (track, car, date).
2. Find the matching reference lap in `product/data/reference-laps/`.
3. If the user wants a comparison (e.g., "today vs yesterday"), identify both session sets.
4. Run the script with appropriate arguments.
5. Present the results in plain language, calling out the top 2-3 areas of consistent time loss and what to do about them.