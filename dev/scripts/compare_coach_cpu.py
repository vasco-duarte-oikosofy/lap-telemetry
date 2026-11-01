"""Gate two serial benchmark campaigns on real work savings and exact output parity."""
import argparse
import json
from pathlib import Path

import numpy as np

def compare(before_dir, after_dir):
    before = json.loads((before_dir / 'report.json').read_text(encoding='utf-8'))
    after = json.loads((after_dir / 'report.json').read_text(encoding='utf-8'))
    checks = []
    def check(value, label):
        checks.append(dict(passed=bool(value), label=label))
        print(f"{'[PASS]' if value else '[FAIL]'} {label}")
    for key in ['session_sha256', 'model_sha256', 'voices_sha256', 'versions',
                'logical_cpus', 'platform', 'python', 'lap']:
        check(before['provenance'][key] == after['provenance'][key], f'unchanged workload/environment: {key}')
    normalize = lambda cfg: {k: v for k, v in cfg.items() if k != 'kokoro_cpu_threads'}
    check(normalize(before['provenance']['tts_config']) == normalize(after['provenance']['tts_config']),
          'same model, voices, speaking voice and speed')
    check(len(before['source_result_files']) == len(after['source_result_files']) >= 3,
          'at least three matched fresh-process trials')
    audio_equal, facts_equal, text_equal = True, True, True
    max_error = 0.0
    compared = 0
    for trial in range(min(len(before['source_result_files']), len(after['source_result_files']))):
        # Resolve under the supplied campaign directories so evidence can be
        # relocated/archived without editing the original provenance reports.
        old_path = before_dir / f'trial-{trial}/result.json'
        new_path = after_dir / f'trial-{trial}/result.json'
        old = json.loads(old_path.read_text(encoding='utf-8'))
        new = json.loads(new_path.read_text(encoding='utf-8'))
        facts_equal &= old['facts'] == new['facts']
        text_equal &= old['utterances'] == new['utterances']
        audio_equal &= len(old['audio']) == len(new['audio']) >= 2
        for event in range(len(old['audio'])):
            x = np.load(old_path.parent / f'audio-{event}.npy')
            y = np.load(new_path.parent / f'audio-{event}.npy')
            same_shape = x.shape == y.shape
            audio_equal &= same_shape and np.array_equal(x, y)
            audio_equal &= old['audio'][event]['rate'] == new['audio'][event]['rate']
            max_error = max(max_error, float(np.max(np.abs(x - y))) if same_shape else float('inf'))
            compared += 1
    check(facts_equal, 'all completed-lap facts identical')
    check(text_equal, 'all utterances identical (none skipped)')
    check(audio_equal, f'all {compared} real waveforms sample-identical, including duration/rate')
    b, a = before['summary'], after['summary']
    ratios = {mode: a[f'median_{mode}_cpu_s'] / b[f'median_{mode}_cpu_s'] for mode in ['cold', 'warm']}
    for mode, ratio in ratios.items():
        check(ratio <= 0.5, f'{mode} CPU work <=50% of baseline: {ratio * 100:.2f}%')
        check(a[f'median_{mode}_wall_s'] <= b[f'median_{mode}_wall_s'] * 1.25,
              f'{mode} latency does not regress by more than 25%')
    peak = lambda r: max(value for run in r['observations']
                         for stage, value in run['peak_cpu_percent_one_core_100'].items()
                         if stage.endswith(':tts'))
    peak_ratio = peak(after) / peak(before)
    check(peak_ratio <= 0.5, f'sampled TTS burst peak <=50% of baseline: {peak_ratio * 100:.2f}%')
    return dict(passed=all(c['passed'] for c in checks), checks=checks,
                cpu_ratios=ratios, sampled_tts_peak_ratio=peak_ratio,
                max_waveform_absolute_error=max_error, waveforms_compared=compared,
                before=b, after=a)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = compare(args.before, args.after)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
