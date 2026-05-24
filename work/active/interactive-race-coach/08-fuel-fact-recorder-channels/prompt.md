# Slice 08: Fuel Fact Recorder Channels

## Goal

Extend `Frame` with fuel and race-state fields from LMU shared memory, and produce deterministic fuel-to-end facts that can feed a future engineer call. This slice delivers a **data channel** — no LLM, no TTS, no new voice call. It validates that LMU exposes enough race state through shared memory to compute "fuel laps remaining vs race laps remaining."

## User-visible result

A new CLI command prints fuel facts for a recorded session:

```bash
# Analyze fuel consumption from a recorded session:
python3 -m lap_telemetry.coach.fuel_facts sessions/session_2024-01-15_session1.parquet

# Sample output:
# Track: circuit-de-barcelona
# Session type: race
# Race laps remaining: 42
# Fuel at start: 95.0 L
# Fuel at end: 12.3 L
# Total fuel used: 82.7 L
# Laps completed: 8
# Fuel per lap: 10.3 L
# Estimated laps of fuel remaining: 1.2
# Fuel status: CRITICAL — must pit now
```

The `Frame` dataclass gains nullable fuel/race-state fields. The Parquet writer stores them. A `FuelFacts` dataclass and `compute_fuel_facts()` function produce the deterministic output above from a Parquet file or a list of frames.

## Architecture risk validated

Can we compute actionable fuel-to-end facts from the fields LMU actually exposes through shared memory? The answer must be yes: `mFuel` (current fuel), `mFuelCapacity` (tank size), `mTotalLaps` (total race laps), `mFuelFraction` (0–100 percentage), plus `mMaxLaps` / `mSession` from the scoring info give us everything we need to compute fuel-per-lap, laps-of-fuel-remaining, and race-laps-remaining. No estimation or guessing required.

## Scope

### In scope

1. **Extend `Frame` with fuel/race-state fields** (`product/python/lap_telemetry/recorder/connect.py`)
   - `fuel_l: float | None = None` — current fuel in litres (from `mFuel`)
   - `fuel_capacity_l: float | None = None` — tank capacity in litres (from `mFuelCapacity`)
   - `session_type: int | None = None` — session type code (from `mSession` on scoring info: 0=practice, 2=qualifying, 3=race, etc.)
   - `session_time_remaining_s: float | None = None` — time remaining in session (from `mSessionTimeRemaining`)
   - `race_laps_total: int | None = None` — total race laps if applicable (from `mMaxLaps` on scoring info)
   - All new fields are nullable (`| None = None`) and default to `None`. Existing `Frame` fields are unchanged. This is backward compatible: old code ignores new fields, old Parquet files simply lack the columns.

2. **Populate new fields in LMU connection** (`connect.py`)
   - Read `mFuel` from telemetry → `fuel_l`
   - Read `mFuelCapacity` from telemetry → `fuel_capacity_l`
   - Read `mSession` from scoring → `session_type`
   - Read `mSessionTimeRemaining` from scoring → `session_time_remaining_s`
   - Read `mMaxLaps` from scoring → `race_laps_total`
   - Only populate when values are plausible (> 0 for fuel, > 0 for capacity, valid session type). Use `None` for invalid or missing values.

3. **Add new columns to Parquet schema** (`writer.py`)
   - Add nullable columns for all new fields: `fuel_l`, `fuel_capacity_l`, `session_type`, `session_time_remaining_s`, `race_laps_total`.
   - Add them to `frames_to_parquet()` as well (`coach/frames_to_parquet.py`).
   - Existing Parquet files without these columns still load fine (PyArrow fills missing columns with null).

4. **`FuelFacts` dataclass** (`lap_telemetry/coach/fuel_facts.py`)
   - `track_name: str`
   - `session_type: str` — human-readable: "practice", "qualifying", "race", "unknown"
   - `race_laps_total: int | None` — total laps in the race (None if not a race)
   - `race_laps_remaining: int | None` — laps still to go (None if not a race or unknown)
   - `fuel_at_start_l: float | None` — fuel level in the first valid frame
   - `fuel_at_end_l: float | None` — fuel level in the last valid frame
   - `fuel_used_l: float | None` — total fuel consumed
   - `laps_completed: int` — number of fully or partially completed laps
   - `fuel_per_lap_l: float | None` — average fuel consumption per lap
   - `laps_of_fuel_remaining: float | None` — estimated laps before fuel exhaustion
   - `fuel_status: str` — one of: "OK", "WARNING", "CRITICAL", "UNKNOWN"

5. **`compute_fuel_facts()` function** (`lap_telemetry/coach/fuel_facts.py`)
   - Accepts either a Parquet file path or a list of `Frame` objects.
   - Extracts fuel data from frames, excludes invalid frames (fuel_l ≤ 0 or fuel_l > fuel_capacity_l).
   - Computes fuel-per-lap from first-to-last fuel delta divided by laps completed.
   - Estimates laps of fuel remaining = current fuel / fuel_per_lap.
   - Determines fuel_status: "OK" (>5 laps), "WARNING" (2–5 laps), "CRITICAL" (<2 laps), "UNKNOWN" (insufficient data).
   - For race sessions: computes race_laps_remaining = race_laps_total - laps_completed.
   - Returns a `FuelFacts` dataclass.
   - All computation is deterministic — no LLM involved.

6. **`fuel_facts` CLI command** (`lap_telemetry/coach/fuel_facts.py`)
   - `python3 -m lap_telemetry.coach.fuel_facts <parquet_path>` prints human-readable fuel facts.
   - `--json` flag outputs the `FuelFacts` as JSON.

7. **Unit tests** (`dev/scripts/test_fuel_facts.py` + `.js` wrapper)
   - `FuelFacts` dataclass construction and field defaults.
   - `compute_fuel_facts()` from a synthetic Parquet file with known fuel values.
   - `compute_fuel_facts()` from a list of `Frame` objects.
   - Fuel-per-lap calculation.
   - Laps-of-fuel-remaining estimation.
   - Fuel status thresholds (OK > 5, WARNING 2–5, CRITICAL < 2).
   - Race session type detection.
   - Handling of None/missing fuel data (returns "UNKNOWN" status).
   - CLI invocation produces expected output format.
   - Parquet round-trip: write frames with new fields, read them back, compute facts.
   - Backward compatibility: old Parquet files without fuel columns load without error.

### Out of scope

- LLM prompt or voice call for fuel engineer (slice 09).
- Tire data, weather, traffic gaps, pit strategy (later slices).
- Modifying the coaching pipeline to use fuel facts (slice 09).
- New `CoachMode` for fuel calls.
- Fuel estimation from speed/throttle (we use direct LMU fuel readings).
- Session type mapping beyond the basic codes (0, 2, 3, etc.).

## Design decisions

### New Frame fields are nullable and optional

All new fields default to `None`. Old frames (without fuel data) continue to work. Old Parquet files without these columns load fine — PyArrow fills missing columns with null. The recorder populates them from LMU shared memory; if LMU doesn't provide a value (e.g., practice mode without fuel info), the field stays `None`.

### Deterministic analysis only

`compute_fuel_facts()` is pure math — no LLM, no heuristics beyond the fuel-per-lap average. It produces facts that a future slice can hand to an LLM for phrasing.

### Session type codes

LMU uses numeric session types. We map:
- 0 → "practice"
- 1 → "test" (single player test day)
- 2 → "qualifying"
- 3 → "race"
- 4–8 → "other" (warmup, etc.)
- Anything else → "unknown"

### Fuel status thresholds

The thresholds are simple and configurable (future slices may adjust):
- **OK**: more than 5 laps of fuel remaining
- **WARNING**: 2–5 laps of fuel remaining
- **CRITICAL**: less than 2 laps of fuel remaining
- **UNKNOWN**: insufficient data to compute

### Fuel per lap

Average fuel per lap = (fuel_at_start − fuel_at_end) / laps_completed. This is a simple average that smooths over in-lap/out-lap variation. A future slice may use per-lap fuel consumption for a more precise model.

### No new Frame fields for pit status yet

`mPitState`, `mInPits`, and `mPitLimiter` exist in LMU but are deferred to a later slice that adds pit-window calls. This slice focuses on fuel facts only.

## CLI usage

```bash
# Analyze fuel from a recorded session
python3 -m lap_telemetry.coach.fuel_facts sessions/session_2024-01-15_session1.parquet

# With JSON output
python3 -m lap_telemetry.coach.fuel_facts --json sessions/session_2024-01-15_session1.parquet

# From a Parquet file with no fuel data (graceful degradation)
python3 -m lap_telemetry.coach.fuel_facts sessions/old_session_without_fuel.parquet
# → "Fuel status: UNKNOWN — no fuel data available"
```

## Testing

### Unit tests (no sim needed)

1. **FuelFacts construction** — fields default correctly, `fuel_status` computed.
2. **Session type mapping** — numeric codes map to human-readable strings.
3. **Fuel per lap** — known start/end fuel + known laps → correct average.
4. **Laps of fuel remaining** — current fuel / fuel per lap.
5. **Fuel status thresholds** — OK (>5), WARNING (2–5), CRITICAL (<2), UNKNOWN.
6. **Missing fuel data** — all `None` → "UNKNOWN" status, `None` for numeric fields.
7. **Parquet round-trip** — write frames with fuel fields, read back, compute facts.
8. **Backward compatibility** — old Parquet without fuel columns loads without error.
9. **CLI invocation** — `python3 -m lap_telemetry.coach.fuel_facts <path>` exits 0 with expected output.
10. **CLI --json** — outputs valid JSON.

### Integration tests (manual)

11. **End-to-end with recorder** — Record a session with LMU, verify Parquet has fuel columns, then run `fuel_facts` on it.

## Acceptance criteria

- [ ] `Frame` gains 5 new nullable fields: `fuel_l`, `fuel_capacity_l`, `session_type`, `session_time_remaining_s`, `race_laps_total`.
- [ ] LMU connection populates these from shared memory.
- [ ] Parquet schema includes 5 new nullable columns.
- [ ] `frames_to_parquet()` includes new columns.
- [ ] `FuelFacts` dataclass defined with all fields.
- [ ] `compute_fuel_facts()` produces deterministic facts from a Parquet file or frame list.
- [ ] `fuel_facts` CLI command works with `--json` flag.
- [ ] Fuel status thresholds correct (OK > 5, WARNING 2–5, CRITICAL < 2, UNKNOWN).
- [ ] Old Parquet files without fuel columns load without error.
- [ ] Unit tests pass (`bash scripts/test-summary.sh`).
- [ ] `npm run build` succeeds.
- [ ] Feature test list updated in `package.json`.
- [ ] `handoff.md` and `learnings.md` created.

## Definition of Done

- [ ] 5 new `Frame` fields, populated from LMU shared memory
- [ ] Parquet schema updated, `frames_to_parquet()` updated
- [ ] `FuelFacts` dataclass and `compute_fuel_facts()` function
- [ ] `fuel_facts` CLI with `--json` flag
- [ ] Unit tests pass
- [ ] `npm run build` succeeds (no JS changes expected, but verify no regression)
- [ ] Feature tests added to `package.json` under `interactive-race-coach`
- [ ] `handoff.md` and `learnings.md` written

## Non-goals

- No LLM or TTS integration (slice 09).
- No tire, weather, gap, or pit-window data (later slices).
- No `CoachMode` changes for fuel.
- No dynamic pit strategy or tire stint planning.
- No modification to existing coaching pipeline.