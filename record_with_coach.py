#!/usr/bin/env python3
"""Record with coach — single command, single process, single Ctrl+C.

Starts the recorder with full coaching: fact generation, LLM utterances,
and TTS playback. The recorder writes Parquet normally and the coach
generates spoken coaching after each completed lap.

Usage::

    python3 record_with_coach.py --out-dir sessions
    python3 record_with_coach.py --out-dir sessions --tts-engine kokoro
    python3 record_with_coach.py --out-dir sessions --tts-engine file --tts-output /tmp/coach.txt

PowerShell::

    python record_with_coach.py --out-dir sessions
"""
from __future__ import annotations

import signal
import sys
from pathlib import Path

# Ensure product/python is importable.
_SCRIPT_DIR = Path(__file__).resolve().parent
_PRODUCT_PY = _SCRIPT_DIR / "product" / "python"
if str(_PRODUCT_PY) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_PY))

from lap_telemetry.coach.live_coach import main

if __name__ == "__main__":
    sys.exit(main())