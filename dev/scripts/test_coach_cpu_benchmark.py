"""Test accounting and acceptance gates with tiny deterministic report fixtures."""
import contextlib
import io
import json
import tempfile
from pathlib import Path

import numpy as np
from benchmark_coach_cpu import summarize
from compare_coach_cpu import compare


def check(value, label):
    print(f"{'[PASS]' if value else '[FAIL]'} {label}")
    if not value:
        raise AssertionError(label)


def fixture(directory, cpu):
    directory.mkdir()
    files = []
    for trial in range(3):
        run = directory / f'trial-{trial}'
        run.mkdir()
        data = dict(facts=[{'loss': 0.4}, {'loss': 0.4}], utterances=['same words'] * 2,
                    audio=[{'rate': 24000}] * 2)
        path = run / 'result.json'
        path.write_text(json.dumps(data))
        files.append(str(path))
        for event in range(2):
            np.save(run / f'audio-{event}.npy', np.arange(10, dtype=np.float32))
    provenance = {key: 'same' for key in ['session_sha256', 'model_sha256', 'voices_sha256',
                                        'versions', 'logical_cpus', 'platform', 'python', 'lap']}
    provenance['tts_config'] = {'kokoro_voice': 'bm_daniel', 'kokoro_speed': 1.05}
    summary = {f'median_{mode}_{unit}_s': cpu if unit == 'cpu' else 5
               for mode in ['cold', 'warm'] for unit in ['cpu', 'wall']}
    report = dict(provenance=provenance, source_result_files=files, summary=summary,
                  observations=[{'peak_cpu_percent_one_core_100': {'0:tts': cpu * 100}}])
    (directory / 'report.json').write_text(json.dumps(report))
    return report


def main():
    result = summarize([{'utterances': ['cold', 'warm'], 'stages': [
        {'event': 0, 'python_cpu_s': 2, 'child_cpu_s': 3, 'wall_s': 4},
        {'event': 0, 'python_cpu_s': 1, 'child_cpu_s': 0, 'wall_s': 1},
        {'event': 1, 'python_cpu_s': 3, 'child_cpu_s': 4, 'wall_s': 5},
        {'event': 1, 'python_cpu_s': 1, 'child_cpu_s': 0, 'wall_s': 1},
    ]}])
    check(result['median_cold_cpu_s'] == 6 and result['median_warm_cpu_s'] == 8,
          'CPU accounting includes child processes and idle-tail work, separates cold/warm')
    check(result['median_warm_wall_s'] == 6, 'CPU work is never confused with wall latency')
    with tempfile.TemporaryDirectory() as temporary:
        before, after = Path(temporary) / 'before', Path(temporary) / 'after'
        fixture(before, 10)
        changed = fixture(after, 4)
        def evaluate():
            with contextlib.redirect_stdout(io.StringIO()):
                return compare(before, after)
        check(evaluate()['passed'], 'matched output plus 60% CPU reduction passes gate')
        changed['summary']['median_warm_cpu_s'] = 8
        (after / 'report.json').write_text(json.dumps(changed))
        check(not evaluate()['passed'], 'less than 50% CPU reduction cannot pass gate')
        changed['summary']['median_warm_cpu_s'] = 4
        changed['provenance']['model_sha256'] = 'different model'
        (after / 'report.json').write_text(json.dumps(changed))
        check(not evaluate()['passed'], 'changing the neural model cannot fake a comparable workload')
        changed['provenance']['model_sha256'] = 'same'
        (after / 'report.json').write_text(json.dumps(changed))
        audio_path = Path(changed['source_result_files'][0]).parent / 'audio-0.npy'
        np.save(audio_path, np.zeros(10, dtype=np.float32))
        check(not evaluate()['passed'], 'changed waveform cannot pass the CPU gate')
        np.save(audio_path, np.arange(10, dtype=np.float32))
        data_path = Path(changed['source_result_files'][0])
        data = json.loads(data_path.read_text())
        data['facts'][0]['loss'] = 0.5
        data_path.write_text(json.dumps(data))
        check(not evaluate()['passed'], 'changed coaching facts cannot pass the CPU gate')
        data['facts'][0]['loss'] = 0.4
        data['utterances'][0] = 'different words'
        data_path.write_text(json.dumps(data))
        check(not evaluate()['passed'], 'changed or skipped utterances cannot pass the CPU gate')


if __name__ == '__main__':
    main()
