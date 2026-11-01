"""Live speech CPU reporting tests with deterministic clocks and no audio hardware."""
import contextlib
import io
import sys
import threading
import types
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'product/python'))
from lap_telemetry.coach import speech_queue, tts_adapter
from lap_telemetry.coach.coach_config import TTSConfig
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.coach.tts_adapter import KokoroAdapter, TTSAdapter

FAILURES = 0


def check(value, label):
    if not value:
        raise AssertionError(label)
    print(f'[PASS] {label}')


def lines(output):
    return [line for line in output.getvalue().splitlines() if '[coach] speech-cpu ' in line]


class FakeAdapter(TTSAdapter):
    def __init__(self, callback=lambda text: None):
        self.callback = callback

    def speak(self, text):
        self.callback(text)


def test_exact_clocks_and_visibility():
    output = io.StringIO()
    adapter = FakeAdapter(lambda text: check(not lines(output), 'report waits until speech returns'))
    adapter.last_synthesis_timing = (2.5, 3.25)
    queue = SpeechQueue(adapter)
    clocks = types.SimpleNamespace(process_time=Mock(side_effect=[10, 13]),
                                   perf_counter=Mock(side_effect=[20, 27]))
    try:
        with contextlib.redirect_stderr(output), patch.object(speech_queue, 'time', clocks):
            queue._speak('Turn Eleven\nnext line')
        records = lines(output)
        check(len(records) == 1, 'one visible stderr record without debug logging')
        line = records[0]
        check('cpu_s=3.000' in line and 'wall_s=7.000' in line, 'CPU work is not playback wall time')
        check('synthesis_cpu_s=2.500' in line and 'synthesis_wall_s=3.250' in line,
              'Kokoro synthesis reported separately from playback')
        check('scope=process' in line and 'status=ok' in line and 'utterance=1' in line,
              'CPU scope, success and sequential utterance identity are explicit')
        check('text="Turn Eleven\\nnext line"' in line and len(output.getvalue().splitlines()) == 1,
              'spoken text is identified without multiline log injection')
    finally:
        queue.shutdown()


def test_failed_speech_continues():
    output = io.StringIO()
    calls = []
    def speak(text):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError('synthetic speech error')
    queue = SpeechQueue(FakeAdapter(speak))
    try:
        with contextlib.redirect_stderr(output):
            queue._speak('first')
            queue._speak('second')
        records = lines(output)
        check(len(records) == 2 and calls == ['first', 'second'], 'failed speech still reports and next attempt runs')
        check('status=error' in records[0] and 'utterance=2 status=ok' in records[1],
              'failure status and IDs cannot be mistaken for successful playback')
        check(all('synthesis_cpu_s=na' in line for line in records),
              'non-Kokoro adapters report unavailable stage timing honestly')
    finally:
        queue.shutdown()


def test_actual_queue_and_stale_drop():
    output = io.StringIO()
    entered, release = threading.Event(), threading.Event()
    spoken = []
    def speak(text):
        spoken.append(text)
        if text == 'first':
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test did not release speech')
    queue = SpeechQueue(FakeAdapter(speak))
    try:
        with contextlib.redirect_stderr(output):
            queue.enqueue('first')
            check(entered.wait(3), 'queue starts synthesis asynchronously')
            check(not lines(output), 'no premature CPU report during active speech')
            queue.enqueue('dropped')
            queue.enqueue('last')
            release.set()
            queue.flush()
        records = lines(output)
        check(spoken == ['first', 'last'] and len(records) == 2,
              'initial and chained pending speech both report; stale drop produces no fake record')
        check('text="first"' in records[0] and 'text="last"' in records[1],
              'reported texts are the utterances actually delivered')
    finally:
        release.set()
        queue.shutdown()


def test_kokoro_stage_boundaries_and_failure():
    adapter = KokoroAdapter(TTSConfig())
    check(getattr(adapter, 'last_synthesis_timing', None) is None, 'synthesis timing initially unavailable')
    clocks = types.SimpleNamespace(process_time=Mock(side_effect=[1, 3, 10, 10.5]),
                                   perf_counter=Mock(side_effect=[5, 9, 20, 21]))
    def load():
        check(clocks.process_time.call_count % 2 == 1, 'synthesis clock starts before lazy model load')
    adapter._ensure_loaded = load
    count = [0]
    def create(text, **kwargs):
        check(adapter.last_synthesis_timing is None, 'new attempt resets old stage timing')
        count[0] += 1
        if count[0] == 2:
            raise RuntimeError('synthesis failed')
        return [0.1, -0.1], 24000
    adapter._kokoro = types.SimpleNamespace(create=create)
    def playback(samples, rate):
        check(adapter.last_synthesis_timing == (2, 4), 'stage snapshot ends before audible playback')
        check(samples == [0.1, -0.1] and rate == 24000, 'instrumentation leaves audio unchanged')
    adapter._play_audio = Mock(side_effect=playback)
    with patch.object(tts_adapter, 'time', clocks):
        adapter.speak('same words')
        failed = False
        try:
            adapter.speak('same words')
        except RuntimeError:
            failed = True
        check(failed and adapter.last_synthesis_timing == (0.5, 1),
              'failed synthesis has fresh partial timing, not previous utterance timing')
        check(adapter._play_audio.call_count == 1, 'failed synthesis does not pretend playback happened')


def test_reporting_failure_cannot_break_speech():
    calls = []
    queue = SpeechQueue(FakeAdapter(calls.append))
    try:
        with patch.object(speech_queue, 'print', side_effect=BrokenPipeError, create=True):
            queue._speak('first')
            queue._speak('second')
        check(calls == ['first', 'second'], 'closed metrics output cannot kill speech delivery')
    finally:
        queue.shutdown()


if __name__ == '__main__':
    for test in [test_exact_clocks_and_visibility, test_failed_speech_continues,
                 test_actual_queue_and_stale_drop, test_kokoro_stage_boundaries_and_failure,
                 test_reporting_failure_cannot_break_speech]:
        try:
            test()
        except Exception as error:
            FAILURES += 1
            print(f'[FAIL] {test.__name__}: {error}')
    sys.exit(bool(FAILURES))
