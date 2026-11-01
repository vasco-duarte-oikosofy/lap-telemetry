"""Standalone, serial real coach CPU benchmark (never a parallel timing test).

Requires kokoro-onnx, psutil and local model/voices. Includes exact Python/native
and completed-child CPU; polls only for indicative 200ms CPU peaks/thread counts.
Audio arrays and complete facts remain under --out; copy the concise report to
slice artifacts. Use a fresh output directory for every measurement campaign.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SESSION = ROOT / 'sessions/session_20261101T114510Z_grand-prix-of-long-beach_lmu_practice.parquet'


def sample_worker(proc, directory):
    import psutil  # Optional benchmark dependency, not needed for report math/tests.
    root = psutil.Process(proc.pid)
    maxima, peaks, threads = {}, {}, {}
    start = time.perf_counter()
    window_start, window_cpu, window_stage = start, 0.0, None
    while proc.poll() is None:
        try:
            processes = [root, *root.children(recursive=True)]
        except psutil.NoSuchProcess:
            break
        count = 0
        for p in processes:
            try:
                cpu = p.cpu_times()
                maxima[p.pid] = max(maxima.get(p.pid, 0), cpu.user + cpu.system)
                count += p.num_threads()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        try:
            stage = (directory / 'stage.txt').read_text(encoding='utf-8')
            if stage.partition(':')[2] not in ('facts_text', 'tts', 'idle_tail'):
                stage = window_stage or 'startup'
        except OSError:
            stage = window_stage or 'startup'
        now, cpu = time.perf_counter(), sum(maxima.values())
        threads[stage] = max(threads.get(stage, 0), count)
        if stage != window_stage:
            window_start, window_cpu, window_stage = now, cpu, stage
        elif now - window_start >= 0.2:
            # 100% means one logical CPU, as in psutil; divide by CPU count for machine %.
            peaks[stage] = max(peaks.get(stage, 0), (cpu - window_cpu) / (now - window_start) * 100)
            window_start, window_cpu = now, cpu
        time.sleep(0.01)
    return dict(peak_cpu_percent_one_core_100=peaks, max_tree_threads=threads)


def summarize(results):
    cold, warm, cold_wall, warm_wall = [], [], [], []
    for result in results:
        for event in range(len(result['utterances'])):
            stages = [s for s in result['stages'] if s['event'] == event]
            cpu = sum(s['python_cpu_s'] + s['child_cpu_s'] for s in stages)
            wall = sum(s['wall_s'] for s in stages)
            (cold if event == 0 else warm).append(cpu)
            (cold_wall if event == 0 else warm_wall).append(wall)
    return dict(cold_cpu_s=cold, warm_cpu_s=warm,
                median_cold_cpu_s=statistics.median(cold), median_warm_cpu_s=statistics.median(warm),
                median_cold_wall_s=statistics.median(cold_wall), median_warm_wall_s=statistics.median(warm_wall))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, default=DEFAULT_SESSION)
    parser.add_argument('--lap', type=int, default=11)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--events', type=int, default=4)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.trials < 1 or args.events < 2 or not args.session.exists():
        parser.error('Need an existing real session, >=1 trial and >=2 events')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use an empty/fresh --out directory; benchmark evidence is not overwritten')
    args.out.mkdir(parents=True, exist_ok=True)
    results, observations = [], []
    for trial in range(args.trials):
        directory = args.out / f'trial-{trial}'
        directory.mkdir()
        command = [sys.executable, str(ROOT / 'dev/scripts/coach_cpu_replay.py'),
                   '--session', str(args.session.resolve()), '--lap', str(args.lap),
                   '--events', str(args.events), '--out', str(directory.resolve())]
        with (directory / 'stdout.txt').open('w') as stdout, (directory / 'stderr.txt').open('w') as stderr:
            proc = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=ROOT,
                                    env={**os.environ, 'PYTHONUTF8': '1'})
            observed = sample_worker(proc, directory)
            if proc.wait() != 0:
                raise RuntimeError(f'Replay failed; inspect {directory}/stderr.txt')
        results.append(json.loads((directory / 'result.json').read_text(encoding='utf-8')))
        observations.append(observed)
        print(f'Completed fresh-process trial {trial + 1}/{args.trials}', flush=True)
    report = dict(summary=summarize(results), observations=observations,
                  source_result_files=[str(args.out / f'trial-{i}/result.json') for i in range(args.trials)],
                  measurement='Exact process CPU seconds (all native threads) + completed Node/other child CPU; '
                              'peaks sampled in >=200ms windows, 100%=one logical CPU. Includes 1s idle tail per event.',
                  excluded='Simulator, audible playback, recorder flush, cloud network and external LLM server.',
                  provenance={k: v for k, v in results[0].items()
                              if k not in ('facts', 'stages', 'audio', 'utterances')},
                  utterance=results[0]['utterances'][0],
                  stages=[r['stages'] for r in results])
    # Keep individual raw records compact; human-readable summary remains short.
    (args.out / 'report.json').write_text(json.dumps(report, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
