"""Speech queue for non-blocking TTS utterance delivery.

Provides queue semantics: non-blocking enqueue, worker thread
synthesis + playback, and stale utterance dropping. The currently
playing utterance finishes; only the queued-but-not-yet-playing
utterance can be replaced.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time

from .tts_adapter import TTSAdapter

log = logging.getLogger(__name__)


class SpeechQueue:
    """Bounded speech queue with stale-utterance dropping.

    - enqueue(text): Non-blocking. Adds utterance to the pending slot.
      If a pending utterance already exists, it is replaced (stale drop).
      The currently playing utterance is not interrupted.
    - flush(): Blocks until no utterance is playing and no utterance
      is pending.
    - shutdown(): Stops the worker thread cleanly.
    """

    def __init__(self, adapter: TTSAdapter) -> None:
        self._adapter = adapter
        self._lock = threading.Lock()
        self._pending: str | None = None
        self._stop_event = threading.Event()
        self._idle_event = threading.Event()
        self._idle_event.set()  # Initially idle
        self._notify = threading.Event()
        self._utterance_id = 0
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def enqueue(self, text: str) -> None:
        """Enqueue an utterance for speaking.

        Non-blocking. If there is already a pending utterance that
        has not started playing, it is replaced (stale drop).
        The currently playing utterance is not interrupted.
        """
        if self._stop_event.is_set():
            log.debug("enqueue after shutdown, ignoring: %s", text[:40])
            return

        with self._lock:
            if self._pending is not None:
                log.debug("Dropped stale utterance: %s", self._pending[:40])
            self._pending = text

        # Clear idle flag — we have work to do
        self._idle_event.clear()

        # Wake the worker
        self._notify.set()

    def flush(self) -> None:
        """Block until no utterance is playing and none is pending."""
        self._idle_event.wait()

    def shutdown(self) -> None:
        """Stop the worker thread cleanly."""
        self._stop_event.set()
        self._notify.set()  # Wake the worker
        self._worker.join(timeout=5)
        self._idle_event.set()  # Unblock any waiting flush

    def _speak(self, text: str) -> None:
        """Speak once and always report process CPU/wall time, including failures."""
        self._utterance_id += 1
        cpu_start, wall_start = time.process_time(), time.perf_counter()
        status = "error"
        try:
            log.debug("Speaking: %s", text[:40])
            self._adapter.speak(text)
            status = "ok"
        except Exception as exc:
            log.error("TTS error: %s", exc)
        finally:
            cpu_s = time.process_time() - cpu_start
            wall_s = time.perf_counter() - wall_start
            stage = getattr(self._adapter, "last_synthesis_timing", None)
            synthesis = "synthesis_cpu_s=na synthesis_wall_s=na"
            if isinstance(stage, tuple) and len(stage) == 2:
                synthesis = f"synthesis_cpu_s={stage[0]:.3f} synthesis_wall_s={stage[1]:.3f}"
            try:
                print(
                    f"lap-telemetry: [coach] speech-cpu utterance={self._utterance_id} "
                    f"status={status} cpu_s={cpu_s:.3f} wall_s={wall_s:.3f} "
                    f"{synthesis} scope=process text={json.dumps(text, ensure_ascii=True)}",
                    file=sys.stderr, flush=True,
                )
            except OSError:
                # Closing a log pipe must not kill delivery or strand flush().
                pass

    def _worker_loop(self) -> None:
        """Worker thread: pick up pending text and speak it."""
        while not self._stop_event.is_set():
            # Wait for something to speak
            self._notify.wait(timeout=0.1)
            self._notify.clear()

            # Grab the pending text atomically
            with self._lock:
                text = self._pending
                self._pending = None

            if text is None:
                continue

            # We are now busy — clear idle flag
            self._idle_event.clear()
            self._speak(text)

            # After speaking, check if more text arrived while we were busy
            while True:
                with self._lock:
                    text = self._pending
                    self._pending = None

                if text is None:
                    break

                self._speak(text)

            # All done — set idle flag
            self._idle_event.set()