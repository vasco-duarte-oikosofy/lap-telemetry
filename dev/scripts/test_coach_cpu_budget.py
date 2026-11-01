"""Deterministic CPU policy regression tests; no neural model/audio device required."""
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))
from lap_telemetry.coach.coach_config import TTSConfig, load_tts_config
from lap_telemetry.coach.tts_adapter import KokoroAdapter, FileAdapter

FAILURES = 0


def check(value, label):
    if not value:
        raise AssertionError(label)
    print(f'[PASS] {label}')


def run(test):
    global FAILURES
    try:
        test()
    except Exception as error:
        FAILURES += 1
        print(f'[FAIL] {test.__name__}: {error}')


def raises(fn, label, kind=ValueError):
    try:
        fn()
    except kind:
        check(True, label)
        return
    raise AssertionError(label)


def test_configuration():
    check(TTSConfig().kokoro_cpu_threads == 1, 'default Kokoro compute budget is one CPU thread')
    for value in [0, -1, True, 1.5, 'auto']:
        raises(lambda: TTSConfig(kokoro_cpu_threads=value), f'reject unsafe thread budget {value!r}')
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
        path = Path(directory) / 'coach.toml'
        path.write_text('[tts]\nkokoro_cpu_threads = 2\n', encoding='utf-8')
        check(load_tts_config(path).kokoro_cpu_threads == 2, 'TOML explicit positive thread override')
        os.environ['COACH_KOKORO_CPU_THREADS'] = '3'
        check(load_tts_config(path).kokoro_cpu_threads == 3, 'environment overrides TOML thread budget')
        for value in ['0', '-2', 'auto', '1.5']:
            os.environ['COACH_KOKORO_CPU_THREADS'] = value
            raises(lambda: load_tts_config(path), f'reject unsafe environment budget {value!r}')
        del os.environ['COACH_KOKORO_CPU_THREADS']
        for value in ['0', '-1', 'true', '1.5']:
            path.write_text(f'[tts]\nkokoro_cpu_threads = {value}\n', encoding='utf-8')
            raises(lambda: load_tts_config(path), f'reject unsafe TOML budget {value}')


def fake_runtime(directory, threads=1):
    model, voices = Path(directory) / 'model.onnx', Path(directory) / 'voices.bin'
    model.touch()
    voices.touch()
    options = types.SimpleNamespace(add_session_config_entry=Mock())
    session = object()
    rt = types.SimpleNamespace(SessionOptions=Mock(return_value=options),
                               InferenceSession=Mock(return_value=session),
                               ExecutionMode=types.SimpleNamespace(ORT_SEQUENTIAL='sequential'))
    engine = Mock()
    engine.create.return_value = ([0.1, -0.1], 24000)
    kokoro = Mock()
    kokoro.from_session.return_value = engine
    cfg = TTSConfig(kokoro_model=str(model), kokoro_voices=str(voices),
                    kokoro_voice='bm_daniel', kokoro_speed=1.05, kokoro_cpu_threads=threads)
    return cfg, options, session, rt, kokoro, engine


def test_bounded_lazy_session():
    with tempfile.TemporaryDirectory() as directory:
        cfg, options, session, rt, kokoro, engine = fake_runtime(directory)
        before = dict(os.environ)
        with patch.dict(sys.modules, {'onnxruntime': rt, 'kokoro_onnx': types.SimpleNamespace(Kokoro=kokoro)}):
            adapter = KokoroAdapter(cfg)
            rt.InferenceSession.assert_not_called()
            adapter._play_audio = Mock()
            adapter.speak('Same coaching utterance.')
            adapter.speak('Same coaching utterance.')
        check(options.intra_op_num_threads == 1, 'inference cannot auto-expand across CPU cores')
        check(options.inter_op_num_threads == 1 and options.execution_mode == 'sequential',
              'inter-op execution is sequential and bounded')
        entries = dict(call.args for call in options.add_session_config_entry.call_args_list)
        check(entries == {'session.intra_op.allow_spinning': '0', 'session.inter_op.allow_spinning': '0'},
              'inference workers sleep rather than spin between tasks')
        rt.InferenceSession.assert_called_once_with(cfg.kokoro_model, sess_options=options,
                                                   providers=['CPUExecutionProvider'])
        kokoro.from_session.assert_called_once_with(session, cfg.kokoro_voices)
        kokoro.assert_not_called()
        check(True, 'one explicit CPU session is reused; no unbounded constructor fallback')
        check(engine.create.call_count == 2, 'both utterances actually synthesized, not skipped or cached')
        for call in engine.create.call_args_list:
            check(call.args == ('Same coaching utterance.',)
                  and call.kwargs == {'voice': 'bm_daniel', 'speed': 1.05},
                  'text, voice and speed unchanged')
        adapter._play_audio.assert_called_with([0.1, -0.1], 24000)
        check(dict(os.environ) == before, 'no global ORT/BLAS/OMP environment mutation')


def test_explicit_budget_and_retry():
    with tempfile.TemporaryDirectory() as directory:
        cfg, options, session, rt, kokoro, engine = fake_runtime(directory, threads=2)
        rt.InferenceSession.side_effect = [RuntimeError('temporary failure'), session]
        with patch.dict(sys.modules, {'onnxruntime': rt, 'kokoro_onnx': types.SimpleNamespace(Kokoro=kokoro)}):
            adapter = KokoroAdapter(cfg)
            raises(adapter._ensure_loaded, 'session error is visible and not cached', RuntimeError)
            check(adapter._kokoro is None, 'failed initialization cannot poison cached engine')
            adapter._ensure_loaded()
            check(adapter._kokoro is engine and options.intra_op_num_threads == 2,
                  'retry succeeds with explicit user-selected budget')


def test_optional_dependency_failure():
    with patch.dict(sys.modules, {'kokoro_onnx': None}):
        raises(KokoroAdapter(TTSConfig())._ensure_loaded,
               'missing optional Kokoro dependency gives actionable RuntimeError', RuntimeError)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'speech.txt'
            FileAdapter(output).speak('still works')
            check(output.read_text() == 'still works', 'file engine needs no ONNX or Kokoro import')
    with tempfile.TemporaryDirectory() as directory:
        cfg, _, _, rt, _, _ = fake_runtime(directory)
        old_kokoro = types.SimpleNamespace(Kokoro=type('OldKokoro', (), {}))
        with patch.dict(sys.modules, {'kokoro_onnx': old_kokoro, 'onnxruntime': rt}):
            raises(KokoroAdapter(cfg)._ensure_loaded,
                   'old Kokoro API fails clearly instead of silently using unbounded CPU', RuntimeError)


if __name__ == '__main__':
    for test in [test_configuration, test_bounded_lazy_session, test_explicit_budget_and_retry,
                 test_optional_dependency_failure]:
        run(test)
    sys.exit(bool(FAILURES))
