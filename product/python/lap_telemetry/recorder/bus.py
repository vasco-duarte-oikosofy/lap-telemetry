"""Live telemetry bus — in-process frame pub/sub for coach subscribers.

Two implementations:

- ``LiveBus`` — synchronous callback bus. Callbacks run on the publisher's
  thread. Simple but risky: a slow callback blocks the recorder loop.
- ``QueuedBus`` — threaded bounded queue. A worker thread drains the queue
  and calls subscribers. Non-blocking for the publisher; oldest frames are
  dropped when the queue is full.

Both are thread-safe for subscribe/unsubscribe and publish.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

from .connect import Frame

logger = logging.getLogger(__name__)

FrameCallback = Callable[[Frame], None]
Unsubscribe = Callable[[], None]


class LiveBus:
    """Synchronous in-process callback bus.

    ``publish(frame)`` calls every subscribed callback on the caller's thread.
    If a callback raises, the exception is logged and remaining callbacks
    still execute — a subscriber crash never kills the recorder.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._callbacks: list[FrameCallback] = []

    def subscribe(self, callback: FrameCallback) -> Unsubscribe:
        """Register *callback* to receive every published frame.

        Returns an unsubscribe handle — call it to remove the callback.
        """
        with self._lock:
            self._callbacks.append(callback)
        removed = False

        def _unsubscribe() -> None:
            nonlocal removed
            if removed:
                return
            with self._lock:
                try:
                    self._callbacks.remove(callback)
                except ValueError:
                    pass
            removed = True

        return _unsubscribe

    def publish(self, frame: Frame) -> None:
        """Call every subscribed callback with *frame*.

        Exceptions are caught and logged per-callback; remaining callbacks
        still execute.
        """
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(frame)
            except Exception:  # noqa: BLE001
                logger.exception("LiveBus subscriber %r raised", cb)


class QueuedBus:
    """Threaded bounded-queue bus.

    ``publish(frame)`` pushes into a ``queue.Queue(maxsize=N)`` without
    blocking. If the queue is full, the oldest frame is dropped to make
    room. A worker thread drains the queue and calls subscribers.
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._lock = threading.Lock()
        self._callbacks: list[FrameCallback] = []
        self._queue: queue.Queue[Frame] = queue.Queue(maxsize=maxsize)
        self._worker: Optional[threading.Thread] = None
        self._stopping = threading.Event()

    def subscribe(self, callback: FrameCallback) -> Unsubscribe:
        """Register *callback* to receive frames from the worker thread."""
        with self._lock:
            self._callbacks.append(callback)
        removed = False

        def _unsubscribe() -> None:
            nonlocal removed
            if removed:
                return
            with self._lock:
                try:
                    self._callbacks.remove(callback)
                except ValueError:
                    pass
            removed = True

        return _unsubscribe

    def start(self) -> None:
        """Start the worker thread (daemon)."""
        if self._worker is not None:
            return
        self._stopping.clear()
        self._worker = threading.Thread(target=self._drain, daemon=True)
        self._worker.start()

    def publish(self, frame: Frame) -> None:
        """Push *frame* into the bounded queue.

        If the queue is full, the oldest item is removed first (drop Policy:
        oldest-first drop) so the publisher is never blocked.
        """
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            # Oldest-first drop: remove the oldest, then put the new one.
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                pass  # extremely unlikely race; just drop

    def shutdown(self) -> None:
        """Signal the worker thread to stop and wait for it."""
        self._stopping.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None

    def _drain(self) -> None:
        """Worker loop: pull frames from the queue and call subscribers."""
        while not self._stopping.is_set():
            try:
                frame = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            with self._lock:
                callbacks = list(self._callbacks)
            for cb in callbacks:
                try:
                    cb(frame)
                except Exception:  # noqa: BLE001
                    logger.exception("QueuedBus subscriber %r raised", cb)
        # Drain remaining items after stop signal.
        while True:
            try:
                frame = self._queue.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                callbacks = list(self._callbacks)
            for cb in callbacks:
                try:
                    cb(frame)
                except Exception:  # noqa: BLE001
                    logger.exception("QueuedBus subscriber %r raised", cb)