# Slice 01: Offline Fact Generator

## Goal

Build a CLI that compares one recorded lap to a reference lap and prints the top corner minimum-speed losses from a hand-authored track coaching model. This validates the deterministic analysis engine without any LLM or TTS complexity.

## Non-goals

- No live telemetry streaming
- No LLM integration
- No TTS integration
- No corner-exit or mid-lap coaching
- No automatic track model generation

## Execution steps

1. **Create a hand-authored track coaching model for Barcelona**
   - File: `product/data/track-coaching/circuit-de-barcelona.json`
   - Include 5-8 corners with: `id`, `name`, `s_start_m`, `apex_s_m`, `s_end_m`, `apex_side`
   - Use existing session data to estimate corner locations from trajectory/braking patterns

2. **Build the offline CLI: `lap-telemetry compare-laps`**
   - Inputs: `--current-lap <path>`, `--reference-lap <path>`, `--track-model <path>`
   - Load both Parquet files
   - Resample/interpolate to common distance grid (reuse/Port from `pipeline.js` concepts)
   - Compute per-corner minimum speed delta
   - Print structured JSON facts to stdout

3. **Write tests**
   - Unit test: corner minimum-speed computation with synthetic data
   - Integration test: compare two fixture laps and assert expected top losses
   - Test the track coaching JSON validator

4. **Create fixture data**
   - Extract one fast lap from an existing Barcelona session as "current"
   - Use the existing reference lap for Barcelona as "reference"
   - Store fixtures in `dev/fixtures/coach/`

5. **Run and validate**
   - Execute the CLI with fixtures
   - Verify the output identifies plausible corner losses
   - Document the Windows smoke command

## Acceptance criteria

- `bash scripts/test-summary.sh` exits 0
- `npm run build` succeeds
- CLI command documented and working:
  ```powershell
  lap-telemetry compare-laps --current-lap .\current.parquet --reference-lap .\reference.parquet --track-model .\circuit-de-barcelona.json
  ```
- Output is structured JSON with top 3 corner losses
- Track coaching JSON validator rejects invalid models

## Definition of done

1. Tests pass (full suite)
2. Build succeeds
3. `handoff.md` updated with CLI usage and fixture locations
4. `learnings.md` documents any surprises about Parquet comparison or corner detection
