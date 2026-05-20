# Slice 01 Learnings: Offline Fact Generator

## Surprises

1. **Python module execution on Windows** — The `python -m lap_telemetry` pattern requires `__main__.py` in the package root. This wasn't documented anywhere in the existing codebase, but it's the standard Python way to make a package executable. Added `product/python/lap_telemetry/__main__.py`.

2. **Test runner integration** — The repo uses a Node.js parallel test runner (`run-tests-parallel.js`) that discovers tests from `package.json`. Python tests must be wrapped in a `.js` harness that spawns `python3 -c` with embedded code. This pattern is already used by other Python tests like `test_track_outline_recorder_channels.js`.

3. **Resampling is critical** — The existing `pipeline.js` has well-tested resampling logic for the browser. Porting this to Python was straightforward but essential — comparing laps requires both to be on the same distance grid. The 1-meter binning approach works well.

4. **Track model authoring is manual** — Hand-authoring 16 corners for Barcelona took ~20 minutes using trajectory analysis (braking + steering heuristics). For 30+ tracks, we'll need automated generation tools. The validation layer catches mistakes early.

## Context for the next agent

### File locations

- Track coaching models live in: `product/data/track-coaching/<track-slug>.json`
- Reference laps live in: `product/data/reference-laps/<track-slug>_time_*.parquet`
- Coach module is at: `product/python/lap_telemetry/coach/`

### Design decisions

1. **Facts-only architecture** — The `compare_laps()` function returns structured facts, not prose. This keeps the analysis deterministic and testable. The LLM (slice 03+) will only see the facts JSON.

2. **Speed-based losses first** — MVP uses minimum corner speed as the primary metric because:
   - It's easy to compute and explain
   - It correlates strongly with lap time loss
   - It doesn't require precise delta-time integration
   - Drivers understand "you were 5 km/h slower through the corner"

3. **Corner phases** — Each corner has three analysis phases:
   - `minimum_speed` — The slowest point in the corner (apex vicinity)
   - `entry` — Speed 30m before apex (entry technique)
   - `exit` — Speed 30m after apex (exit traction)

4. **Thresholds for reporting** — Only report losses above:
   - 0.5 km/h for minimum speed (high confidence if > 2.0 km/h)
   - 1.0 km/h for entry/exit (medium confidence)

   This prevents noise from cluttering the coaching output.

### Testing pattern

Python tests run inside Node.js test harness:

```javascript
function runPythonCoachTests() {
  const code = `
import sys
sys.path.insert(0, 'product/python')
# ... test code ...
`;
  return spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
}
```

This gives us parallel test execution and unified reporting.

## Gotchas to avoid

1. **Don't mix lap types** — Comparing a qualifying lap to an endurance stint lap will produce misleading deltas. The reference lap should match the session type (practice, qualifying, race).

2. **Track length mismatch** — The track model's `lap_length_m` must match the actual lap distance in the Parquet files. Barcelona's reference lap is 4654m, but the model says 4657m — close enough for MVP, but should be exact.

3. ** PYTHONPATH matters** — Tests must set `PYTHONPATH` to include `product/python`. The test runner does this via `export PYTHONPATH` in `test-summary.sh`.

4. **Don't start slice 02 without fixing the fixture** — The current fixture lap (57.9s) is much faster than the reference (96.5s) because they're from different session types. Slice 02 should use a proper matching reference lap.

5. **Windows path handling** — All file paths use `pathlib.Path` and are passed as strings to subprocess calls. Avoid hardcoded `/tmp` or POSIX assumptions.

## Next steps (Slice 02)

Slice 02 (track coaching model loader) is partially complete — the loader exists and is tested. The next agent should:

1. Verify the Barcelona model corners align with actual track geometry
2. Add visual validation (maybe export corner markers to a JSON for map overlay)
3. Consider automating corner detection from outline data or repeated laps
