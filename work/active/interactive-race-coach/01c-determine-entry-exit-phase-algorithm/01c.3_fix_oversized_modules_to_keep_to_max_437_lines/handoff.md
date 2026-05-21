# Handoff — 01c.3 Fix oversized modules

## What is on disk now

### New files
- **`product/python/lap_telemetry/coach/entry_detection.py`** (78 lines) — `find_entry_point`, `find_brake_point`. Extracted from lap_comparator.py.
- **`product/python/lap_telemetry/coach/exit_detection.py`** (65 lines) — `find_exit_points`. Extracted from lap_comparator.py.
- **`dev/scripts/test_phase_detection.py`** (381 lines) — Phase detection algorithm tests only. Rewritten from 959-line monolith.
- **`dev/scripts/test_delta_time_gains.py`** (375 lines) — Delta-time trace, gain/loss algorithm tests. Extracted from monolith.
- **`dev/scripts/test_js_pipeline_contract.py`** (124 lines) — JS pipeline contract tests. Extracted from monolith.
- **`dev/scripts/test_phase_detection.js`** (33 lines) — Node.js wrapper for Python test.
- **`dev/scripts/test_delta_time_gains.js`** (33 lines) — Node.js wrapper for Python test.
- **`dev/scripts/test_js_pipeline_contract.js`** (33 lines) — Node.js wrapper for Python test.

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** (241 lines, was 436) — Imports `find_entry_point`, `find_brake_point` from `entry_detection`, `find_exit_points` from `exit_detection`. No logic changes.
- **`package.json`** — Added 3 new test scripts to `scripts.test`.

### Renamed
- `01c.3_losses_gains_algorithm_review` → `01c.4_losses_gains_algorithm_review`

## Test suite change
- Before: 47 test scripts, 1102 assertions
- After: 50 test scripts, 1222 assertions (3 new Python test files via Node.js wrappers)

## How to verify
```bash
bash scripts/test-summary.sh                                       # full suite (50 scripts)
python3 dev/scripts/test_phase_detection.py                        # standalone Python
python3 dev/scripts/test_delta_time_gains.py                        # standalone Python
python3 dev/scripts/test_js_pipeline_contract.py                   # standalone Python
npm run build                                                       # build
```

## Known issues
- Pre-existing oversized files still exist (e.g., `test_f8f9f10f11.js` at 549 lines, `register_outline.py` at 558 lines). Not in this slice's scope.