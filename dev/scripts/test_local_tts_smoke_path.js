/**
 * Local TTS smoke path tests.
 *
 * Tests TTS adapters, speech queue, config, and CLI — all without
 * audio hardware. Uses FileAdapter and mock adapters for validation.
 *
 * Run: node dev/scripts/test_local_tts_smoke_path.js
 */
// @parallel true

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

const PYTHON_CODE = `
import json, os, sys, tempfile, time, subprocess
from pathlib import Path
sys.path.insert(0, r"""${path.join(ROOT, 'product', 'python')}""")

from lap_telemetry.coach.coach_config import TTSConfig, load_tts_config, _read_toml
from lap_telemetry.coach.tts_adapter import TTSAdapter, FileAdapter, PiperAdapter
from lap_telemetry.coach.speech_queue import SpeechQueue

# ─── TTSConfig tests ───

def test_tts_config_defaults():
    cfg = TTSConfig()
    assert cfg.engine == "piper", f"Expected piper, got {cfg.engine}"
    assert cfg.piper_binary == "python3 -m piper", f"Expected python3 -m piper, got {cfg.piper_binary}"
    assert cfg.piper_model is None, f"Expected None, got {cfg.piper_model}"
    assert cfg.output_file == "coach_output.wav", f"Got {cfg.output_file}"
    print("  tts_config_defaults: OK")

def test_tts_config_env_overrides():
    env_backup = {}
    for key in ["COACH_TTS_ENGINE", "COACH_PIPER_BINARY", "COACH_PIPER_MODEL", "COACH_CONFIG"]:
        env_backup[key] = os.environ.pop(key, None)
    try:
        os.environ["COACH_TTS_ENGINE"] = "file"
        os.environ["COACH_PIPER_BINARY"] = "/custom/piper"
        os.environ["COACH_PIPER_MODEL"] = "/custom/voice.onnx"
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.toml"
            cfg_path.write_text('[tts]\\nengine = "piper"\\n')
            cfg = load_tts_config(cfg_path)
        assert cfg.engine == "file", f"Expected file, got {cfg.engine}"
        assert cfg.piper_binary == "/custom/piper", f"Got {cfg.piper_binary}"
        assert cfg.piper_model == "/custom/voice.onnx", f"Got {cfg.piper_model}"
    finally:
        for key in ["COACH_TTS_ENGINE", "COACH_PIPER_BINARY", "COACH_PIPER_MODEL"]:
            os.environ.pop(key, None)
        for k, v in env_backup.items():
            if v is not None:
                os.environ[k] = v
    print("  tts_config_env_overrides: OK")

def test_load_tts_config_from_toml():
    env_backup = {}
    for key in ["COACH_TTS_ENGINE", "COACH_PIPER_BINARY", "COACH_PIPER_MODEL", "COACH_CONFIG"]:
        env_backup[key] = os.environ.pop(key, None)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[tts]\\nengine = "file"\\noutput_file = "test_out.wav"\\n')
            f.flush()
            cfg = load_tts_config(Path(f.name))
        assert cfg.engine == "file", f"Expected file, got {cfg.engine}"
        assert cfg.output_file == "test_out.wav", f"Got {cfg.output_file}"
    finally:
        for k, v in env_backup.items():
            if v is not None:
                os.environ[k] = v
    print("  load_tts_config_from_toml: OK")

def test_load_tts_config_env_overrides_toml():
    env_backup = {}
    for key in ["COACH_TTS_ENGINE", "COACH_PIPER_BINARY", "COACH_PIPER_MODEL", "COACH_CONFIG"]:
        env_backup[key] = os.environ.pop(key, None)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[tts]\\nengine = "piper"\\n')
            f.flush()
        os.environ["COACH_TTS_ENGINE"] = "file"
        cfg = load_tts_config(Path(f.name))
        assert cfg.engine == "file", f"Expected file override, got {cfg.engine}"
    finally:
        os.environ.pop("COACH_TTS_ENGINE", None)
        for k, v in env_backup.items():
            if v is not None:
                os.environ[k] = v
    print("  load_tts_config_env_overrides_toml: OK")

# ─── TTSAdapter tests ───

def test_tts_adapter_is_abstract():
    try:
        TTSAdapter()
        assert False, "Should not be able to instantiate TTSAdapter directly"
    except TypeError:
        pass
    print("  tts_adapter_is_abstract: OK")

def test_file_adapter_writes_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "test_output.wav"
        adapter = FileAdapter(output_path=out)
        adapter.speak("Hello world")
        assert out.exists(), "Output file was not created"
    print("  file_adapter_writes_file: OK")

def test_file_adapter_contains_text():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "test_output.wav"
        adapter = FileAdapter(output_path=out)
        adapter.speak("Lost time in turn 3")
        content = out.read_text(encoding="utf-8")
        assert "Lost time in turn 3" in content, f"Text not in output"
    print("  file_adapter_contains_text: OK")

def test_piper_adapter_instantiation():
    cfg = TTSConfig(piper_binary="piper", piper_model="/fake/voice.onnx")
    adapter = PiperAdapter(config=cfg)
    assert adapter is not None
    print("  piper_adapter_instantiation: OK")

# ─── SpeechQueue tests ───

def test_speech_queue_enqueue_flush():
    calls = []
    class MockAdapter(TTSAdapter):
        def speak(self, text):
            calls.append(text)
    q = SpeechQueue(adapter=MockAdapter())
    q.enqueue("Hello world")
    q.flush()
    assert "Hello world" in calls, f"Expected Hello world in {calls}"
    q.shutdown()
    print("  speech_queue_enqueue_flush: OK")

def test_speech_queue_stale_drop():
    calls = []
    class SlowAdapter(TTSAdapter):
        def speak(self, text):
            time.sleep(0.05)
            calls.append(text)
    q = SpeechQueue(adapter=SlowAdapter())
    q.enqueue("first")
    time.sleep(0.02)
    q.enqueue("second")
    q.enqueue("third")
    q.flush()
    assert "first" in calls, f"Expected first in {calls}"
    assert "third" in calls, f"Expected third in {calls}"
    assert "second" not in calls, f"second should have been dropped, {calls}"
    q.shutdown()
    print("  speech_queue_stale_drop: OK")

def test_speech_queue_flush_waits():
    calls = []
    class SlowAdapter2(TTSAdapter):
        def speak(self, text):
            time.sleep(0.1)
            calls.append(text)
    q = SpeechQueue(adapter=SlowAdapter2())
    q.enqueue("playing")
    q.flush()
    assert "playing" in calls, f"Expected playing in {calls}"
    q.shutdown()
    print("  speech_queue_flush_waits: OK")

def test_speech_queue_shutdown():
    class MockAdapter2(TTSAdapter):
        def speak(self, text):
            pass
    q = SpeechQueue(adapter=MockAdapter2())
    q.shutdown()
    time.sleep(0.05)
    print("  speech_queue_shutdown: OK")

def test_speech_queue_multiple_items():
    calls = []
    class MockAdapter3(TTSAdapter):
        def speak(self, text):
            calls.append(text)
    q = SpeechQueue(adapter=MockAdapter3())
    q.enqueue("one")
    q.flush()
    q.enqueue("two")
    q.flush()
    assert "one" in calls, f"Expected one in {calls}"
    assert "two" in calls, f"Expected two in {calls}"
    q.shutdown()
    print("  speech_queue_multiple_items: OK")

# ─── CLI tests ───

def test_speak_cli_with_file_adapter():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "cli_test.wav"
        env = os.environ.copy()
        env["PYTHONPATH"] = r"""${path.join(ROOT, 'product', 'python')}"""
        for key in ["COACH_CONFIG", "COACH_TTS_ENGINE", "COACH_PIPER_BINARY",
                     "COACH_PIPER_MODEL", "COACH_TTS_OUTPUT_FILE"]:
            env.pop(key, None)
        result = subprocess.run(
            [sys.executable, "-m", "lap_telemetry.coach.speak",
             "--text", "Test utterance", "--engine", "file",
             "--output", str(out)],
            capture_output=True, text=True, timeout=10,
            env=env,
            cwd=r"""${path.join(ROOT)}""",
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert out.exists(), f"Output file not created at {out}"
        content = out.read_text(encoding="utf-8")
        assert "Test utterance" in content, f"Text not in output"
    print("  speak_cli_with_file_adapter: OK")

def test_speak_cli_no_text_fails():
    result = subprocess.run(
        [sys.executable, "-m", "lap_telemetry.coach.speak"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0, "Should fail without --text"
    print("  speak_cli_no_text_fails: OK")

# ─── Run all tests ───

test_tts_config_defaults()
test_tts_config_env_overrides()
test_load_tts_config_from_toml()
test_load_tts_config_env_overrides_toml()
test_tts_adapter_is_abstract()
test_file_adapter_writes_file()
test_file_adapter_contains_text()
test_piper_adapter_instantiation()
test_speech_queue_enqueue_flush()
test_speech_queue_stale_drop()
test_speech_queue_flush_waits()
test_speech_queue_shutdown()
test_speech_queue_multiple_items()
test_speak_cli_with_file_adapter()
test_speak_cli_no_text_fails()
print("ALL OK")
`;

function runPythonTests() {
  return spawnSync('python3', ['-c', PYTHON_CODE], { encoding: 'utf8', timeout: 60000 });
}

function main() {
  console.log('═══ Local TTS Smoke Path Tests ═══\n');
  const res = runPythonTests();
  assert(!res.error, 'python tts tests spawned', res.error?.message || '');
  assert(res.status === 0, 'local tts smoke path tests', res.status === 0 ? res.stdout.trim() : res.stderr.trim());
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) process.exit(1);
}

main();