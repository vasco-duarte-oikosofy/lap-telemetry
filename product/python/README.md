# product/python/

Python product package source lives here.

The installable `lap_telemetry` package is under this folder. `pyproject.toml` points setuptools at this directory while keeping the package import name unchanged.

---

## Quick Start

### Run Slice 01 Demo (Offline Lap Comparison)

The fastest way to see the Interactive Race Coach working:

```bash
cd product/python
python3 demo_coach_slice01.py
```

This compares a test lap against the reference and outputs structured coaching facts as JSON.

**With verbose output:**
```bash
python3 demo_coach_slice01.py --verbose
```

**With custom files:**
```bash
python3 demo_coach_slice01.py \
  --current-lap /path/to/current.parquet \
  --reference-lap /path/to/reference.parquet \
  --track-model /path/to/track-model.json
```

---

## Package Structure

```
product/python/
├── lap_telemetry/          # Main package
│   ├── __init__.py
│   ├── __main__.py         # CLI entry point (python -m lap_telemetry)
│   ├── cli.py              # CLI argument parsing
│   ├── summary.py          # Session summary command
│   ├── recorder/           # LMU/rF2 shared-memory recorder
│   └── coach/              # Interactive Race Coach module
│       ├── __init__.py
│       ├── cli.py          # compare-laps command
│       ├── track_model.py  # Track coaching model loader
│       └── lap_comparator.py  # Lap comparison engine
├── demo_coach_slice01.py   # Demo script (no PYTHONPATH needed)
└── README.md
```

---

## Installation (Optional)

For development, install in editable mode:

```bash
cd product/python
pip install -e .
```

This allows running `lap-telemetry` from anywhere without setting `PYTHONPATH`.

---

## CLI Usage

### Record telemetry from LMU/rF2

```bash
python -m lap_telemetry record --out-dir ./sessions
```

### Session summary

```bash
python -m lap_telemetry summary ./sessions/session_*.parquet
```

### Compare laps (Slice 01)

```bash
python -m lap_telemetry compare-laps \
  --current-lap ./current.parquet \
  --reference-lap ./reference.parquet \
  --track-model ./track-model.json
```

**Note:** When using `python -m lap_telemetry`, you must either:
1. Set `PYTHONPATH=/path/to/product/python`, or
2. Run from the `product/python` directory, or
3. Use the demo script: `python3 demo_coach_slice01.py` (no setup needed)

---

## Testing

Run the full test suite from the repo root:

```bash
bash scripts/test-summary.sh
```

Run only the coach tests:

```bash
bash scripts/test-summary.sh dev/scripts/test_coach_lap_comparison.js
```

---

## Interactive Race Coach — Slice 01

**Status:** ✅ Complete

**What it does:** Compares a recorded lap against a reference lap and outputs structured coaching facts identifying the top 3 corner losses (minimum speed, entry, exit phases).

**Demo:**
```bash
cd product/python
python3 demo_coach_slice01.py --verbose
```

**Example output:**
```json
{
  "type": "lap_coaching_summary",
  "track_id": "circuit-de-barcelona",
  "lap_number": 2,
  "lap_time_delta_s": -38.516,
  "top_losses": [
    {
      "corner_id": "t4",
      "corner_name": "turn 4",
      "phase": "minimum_speed",
      "loss_s": 0.045,
      "driver_value": 104.2,
      "reference_value": 108.7,
      "unit": "km/h",
      "confidence": "medium"
    }
  ],
  "top_gains": [],
  "constraints": {
    "max_words": 35,
    "style": "calm_concise_engineer"
  }
}
```

**Next slice:** Slice 02 — Track coaching model loader (validate corners align with track geometry)

---

## Data Directories

- `product/data/reference-laps/` — Reference laps by track
- `product/data/track-coaching/` — Track coaching models (corners, straight zones)
- `dev/fixtures/coach/` — Test fixtures for development

---

## Requirements

- Python 3.10+
- pyarrow
- numpy

Install dependencies:
```bash
pip install pyarrow numpy
```
