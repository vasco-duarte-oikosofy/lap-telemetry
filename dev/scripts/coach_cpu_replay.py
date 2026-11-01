"""One fresh-process real lap-to-audio replay for benchmark_coach_cpu.py."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))
from coach_cpu_metrics import child_cpu_seconds, track_child_cpu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--lap', required=True, type=int)
    parser.add_argument('--events', type=int, default=4)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.events < 2:
        parser.error('At least two events are needed for separate cold/warm measurements')
    args.out.mkdir(parents=True, exist_ok=True)
    track_child_cpu()
    # Imports occur as they do in the live coach, before the first lap event.
    import numpy as np
    from lap_telemetry.coach.coach_config import load_tts_config
    from lap_telemetry.coach.live_fact_generator import LiveFactGenerator
    from lap_telemetry.coach.template_adapter import TemplateAdapter
    from lap_telemetry.coach.tts_adapter import KokoroAdapter

    facts_log = []
    def utterance_fn(facts):
        facts_log.append(facts.to_dict())
        return TemplateAdapter.generate(facts)

    gen = LiveFactGenerator(utterance_fn=utterance_fn)
    cfg = load_tts_config()
    adapter = KokoroAdapter(cfg)
    audio_log = []
    def capture_audio(samples, rate):
        audio = np.asarray(samples, dtype=np.float32)
        if rate != 24000 or not len(audio) or not np.isfinite(audio).all():
            raise RuntimeError('Invalid synthesized audio')
        np.save(args.out / f'audio-{len(audio_log)}.npy', audio)
        audio_log.append(dict(samples=len(audio), rate=rate, duration_s=len(audio) / rate,
                              rms=float(np.sqrt(np.mean(audio ** 2)))))
    adapter._play_audio = capture_audio  # real synthesis; no speakers or playback sleep
    stages = []
    def measure(event, name, fn):
        marker = args.out / 'stage.txt'
        # A sampler may hold the marker open on Windows: replacing it atomically
        # then fails with sharing violation. Partial reads are harmless metadata.
        marker.write_text(f'{event}:{name}', encoding='utf-8')
        cpu, child, wall = time.process_time(), child_cpu_seconds(), time.perf_counter()
        result = fn()
        stages.append(dict(event=event, stage=name, python_cpu_s=time.process_time() - cpu,
                           child_cpu_s=child_cpu_seconds() - child,
                           wall_s=time.perf_counter() - wall))
        return result

    utterances = []
    for event in range(args.events):
        text = measure(event, 'facts_text', lambda: gen.generate_from_parquet(
            args.session, args.lap, 'Grand Prix of Long Beach',
            vehicle_name='Ferrari AF Corse 2026 #50:LM'))
        if not text:
            raise RuntimeError('Replay produced no utterance; cannot count skipped work as a saving')
        utterances.append(text)
        measure(event, 'tts', lambda: adapter.speak(text))
        measure(event, 'idle_tail', lambda: time.sleep(1.0))
    # Metadata/validation outside the measured lap events.
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    versions = {p: importlib.metadata.version(p) for p in
                ['kokoro-onnx', 'onnxruntime', 'numpy', 'pyarrow', 'psutil']}
    import subprocess
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    data = dict(python=sys.version, platform=platform.platform(), logical_cpus=os.cpu_count(),
                versions=versions, revision=revision, session=str(args.session), lap=args.lap,
                session_sha256=sha(args.session),
                adapter_sha256=sha(ROOT / 'product/python/lap_telemetry/coach/tts_adapter.py'),
                model_sha256=sha(cfg.kokoro_model), voices_sha256=sha(cfg.kokoro_voices),
                tts_config=vars(cfg), text_mode='template (cloud network excluded, config unchanged)',
                playback='real synthesis captured to numpy; no audible playback',
                stages=stages, utterances=utterances, facts=facts_log, audio=audio_log)
    (args.out / 'result.json').write_text(json.dumps(data, separators=(',', ':')) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
