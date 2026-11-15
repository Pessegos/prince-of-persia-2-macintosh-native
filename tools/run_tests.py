"""Run the unittest suite in parallel worker processes.

    .venv\\Scripts\\python.exe -m tools.run_tests              # everything but slow tests
    .venv\\Scripts\\python.exe -m tools.run_tests --slow       # also tests.slow (before integration)
    .venv\\Scripts\\python.exe -m tools.run_tests tests.test_lava tests.test_harbor
    .venv\\Scripts\\python.exe -m tools.run_tests --desktop    # then the exclusive desktop tests

Test modules are shared out between --jobs processes, longest first, using the
module times of the previous run (kept in rendered/test-timings.json; without
it every module counts the same). Each worker is an ordinary unittest process
with its own temporary POP2_USER_DATA, so saves and preferences never collide.
Workers always run with POP2_SHARED_DESKTOP=1: the tests that need the physical
desktop are skipped there and, with --desktop, run afterwards on their own,
one process, without that switch. A skip is reported as a skip, not a pass.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TIMINGS = ROOT / 'rendered' / 'test-timings.json'


def discover_modules():
    return sorted(f'tests.{path.stem}' for path in (ROOT / 'tests').glob('test_*.py'))


def share_out(modules, weights, jobs):
    """Longest-first greedy split into at most `jobs` bins of similar total time."""
    default = sorted(weights.values())[len(weights) // 2] if weights else 1.0
    bins = [[0.0, []] for _ in range(min(jobs, len(modules)))]
    for module in sorted(modules, key=lambda name: (-weights.get(name, default), name)):
        lightest = min(bins, key=lambda item: item[0])
        lightest[0] += weights.get(module, default)
        lightest[1].append(module)
    return [names for _total, names in bins if names]


class TimedResult(unittest.TextTestResult):
    """Records the wall time of each module, its class fixtures included."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modules = {}
        self.mark = time.perf_counter()

    def stopTest(self, test):
        now = time.perf_counter()
        module = type(test).__module__
        self.modules[module] = self.modules.get(module, 0.0) + now - self.mark
        self.mark = now
        super().stopTest(test)


def worker(report, modules):
    """Run `modules` in this process and write a JSON report."""
    with open(os.devnull, 'w') as quiet:
        suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
        result = unittest.TextTestRunner(stream=quiet, resultclass=TimedResult, verbosity=0).run(suite)
    Path(report).write_text(json.dumps({
        'run': result.testsRun,
        'failures': [[test.id(), text] for test, text in result.failures],
        'errors': [[test.id(), text] for test, text in result.errors],
        'unexpected': [test.id() for test in result.unexpectedSuccesses],
        'skipped': [[test.id(), reason] for test, reason in result.skipped],
        'expected_failures': len(result.expectedFailures),
        'modules': result.modules,
    }), encoding='utf-8')
    return 0


def run_parallel(modules, jobs, slow):
    weights = {}
    try:
        weights = json.loads(TIMINGS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    groups = share_out(modules, weights, jobs)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='pop2-run-tests-') as scratch:
        processes = []
        for index, group in enumerate(groups):
            env = os.environ.copy()
            env.pop('POP2_USER_DATA', None)      # each worker makes its own (tests/__init__.py)
            env['POP2_SHARED_DESKTOP'] = '1'
            env['POP2_SLOW_TESTS'] = '1' if slow else ''
            report = Path(scratch) / f'worker-{index}.json'
            log = open(Path(scratch) / f'worker-{index}.log', 'w', encoding='utf-8')
            process = subprocess.Popen(
                [sys.executable, '-m', 'tools.run_tests', '--worker', str(report), *group],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            processes.append((process, report, log, group))
        reports = []
        for process, report, log, group in processes:
            process.wait()
            log.close()
            if report.is_file():
                reports.append(json.loads(report.read_text(encoding='utf-8')))
            else:
                # The worker died before reporting (an import error, a crash).
                text = Path(log.name).read_text(encoding='utf-8', errors='replace')
                reports.append({'run': 0, 'failures': [], 'unexpected': [], 'skipped': [],
                                'expected_failures': 0, 'modules': {},
                                'errors': [[f'worker {", ".join(group)}', text[-4000:]]]})
    elapsed = time.perf_counter() - started
    return reports, elapsed, len(groups)


def summarise(reports, elapsed, workers):
    run = sum(item['run'] for item in reports)
    failures = [entry for item in reports for entry in item['failures']]
    errors = [entry for item in reports for entry in item['errors']]
    unexpected = [name for item in reports for name in item['unexpected']]
    skipped = [entry for item in reports for entry in item['skipped']]
    expected = sum(item['expected_failures'] for item in reports)
    for kind, entries in (('FAIL', failures), ('ERROR', errors)):
        for name, text in entries:
            print('=' * 70)
            print(f'{kind}: {name}')
            print('-' * 70)
            print(text.rstrip())
    for name in unexpected:
        print(f'UNEXPECTED SUCCESS: {name}')
    reasons = {}
    for _name, reason in skipped:
        key = ('needs the exclusive desktop' if 'exclusive desktop' in reason else
               'slow test (POP2_SLOW_TESTS=1)' if reason.startswith('slow test') else 'other')
        reasons[key] = reasons.get(key, 0) + 1
    print('-' * 70)
    print(f'Ran {run} tests in {elapsed:.0f} s on {workers} workers')
    details = ', '.join(f'{count} {key}' for key, count in sorted(reasons.items()))
    status = 'OK' if not (failures or errors or unexpected) else 'FAILED'
    extra = [f'failures={len(failures)}'] if failures else []
    extra += [f'errors={len(errors)}'] if errors else []
    extra += [f'unexpected successes={len(unexpected)}'] if unexpected else []
    extra += [f'skipped={len(skipped)} ({details})'] if skipped else []
    extra += [f'expected failures={expected}'] if expected else []
    print(f'{status} ({", ".join(extra)})' if extra else status)
    return status == 'OK'


def save_timings(reports):
    timings = {}
    try:
        timings = json.loads(TIMINGS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    measured = {}
    for item in reports:
        for name, seconds in item['modules'].items():
            measured[name] = measured.get(name, 0.0) + seconds
    timings.update({name: round(seconds, 2) for name, seconds in measured.items()})
    try:
        TIMINGS.parent.mkdir(exist_ok=True)
        TIMINGS.write_text(json.dumps(timings, indent=1, sort_keys=True), encoding='utf-8')
    except OSError:
        pass  # Balancing only; the next run splits evenly.


def run_desktop():
    print('\nExclusive desktop tests (one process, no POP2_SHARED_DESKTOP):')
    env = os.environ.copy()
    env.pop('POP2_SHARED_DESKTOP', None)
    env.pop('POP2_USER_DATA', None)
    return subprocess.call([sys.executable, '-m', 'unittest', '-q', 'tests.desktop_exclusive'],
                           cwd=ROOT, env=env) == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('modules', nargs='*', help='test modules (default: every tests/test_*.py)')
    parser.add_argument('--jobs', '-j', type=int, default=min(6, os.cpu_count() or 1))
    parser.add_argument('--slow', action='store_true', help='also run tests marked by tests.slow')
    parser.add_argument('--desktop', action='store_true',
                        help='afterwards run the exclusive desktop tests (nobody may use the desktop)')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.worker, args.modules)
    modules = args.modules or discover_modules()
    reports, elapsed, workers = run_parallel(modules, max(1, args.jobs), args.slow)
    save_timings(reports)
    ok = summarise(reports, elapsed, workers)
    if args.desktop:
        ok = run_desktop() and ok
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
