"""Check an extracted Windows ZIP with no Python/dependency directories on PATH."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from time import monotonic
from zipfile import ZipFile

from tools.build_windows import validate_bundle
from tools.prepare_windows_runtime import validate_runtime, signatures


def smoke(archive, image=None, defender=False, reference=None):
    started = monotonic()
    checks = []
    with tempfile.TemporaryDirectory(prefix='pop2 portable smoke ') as directory:
        directory = Path(directory).resolve()
        with ZipFile(archive) as zipped:
            if any(not (directory / name).resolve().is_relative_to(directory) for name in zipped.namelist()):
                raise ValueError('Unsafe archive member')
            zipped.extractall(directory)
        bundle = directory / 'PoP2Mac'
        validate_bundle(bundle)
        validate_runtime(bundle / '_internal/python')
        signatures(bundle / '_internal/python')
        protection = {}
        matching_exports = []
        if defender:
            from tools.check_windows_defender import check

            protection['before'] = check(bundle)
        env = os.environ.copy()
        for name in ('PYTHONHOME', 'PYTHONPATH'):
            env.pop(name, None)
        windows = Path(env.get('SystemRoot', 'C:/Windows'))
        env.update(PATH=os.pathsep.join(map(str, (windows / 'System32', windows))),
                   POP2_USER_DATA=str(directory / 'userdata'), SDL_AUDIODRIVER='dummy',
                   PYGAME_HIDE_SUPPORT_PROMPT='1')

        def run(executable, *arguments, timeout=120):
            command = ([str(bundle / '_internal/python/python.exe'), '-I', '-B', '-u',
                        str(bundle / '_internal/worker/worker_entry.py')]
                       if executable == 'worker' else [str(bundle / executable)])
            result = subprocess.run([*command, *map(str, arguments)], cwd=directory,
                                    env=env, capture_output=True, text=True, encoding='utf-8',
                                    stdin=subprocess.DEVNULL, timeout=timeout,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                diagnostics = '\n'.join(path.read_text(encoding='utf-8', errors='replace')[-4000:]
                                        for path in (bundle / 'rendered').glob('*.log'))
                raise RuntimeError(f'{executable} {arguments}: {result.returncode}\n'
                                   f'{result.stdout}\n{result.stderr}\n{diagnostics}')
            checks.append([executable, arguments[0]])
            if result.stdout.strip():
                return result.stdout
            log = bundle / 'rendered/game.log'
            return log.read_text(encoding='utf-8') if log.is_file() else ''

        runtime = json.loads(run('worker', '--smoke-runtime').strip().splitlines()[-1])
        if Path(runtime['project']) != bundle:
            raise RuntimeError('Signed worker uses another installation')
        run('worker', '--smoke-pool')
        run('worker', '--smoke-native')
        fresh = json.loads(run('PoP2Mac.exe', '--smoke-test').strip().splitlines()[-1])
        if Path(fresh['project']) != bundle or fresh['levels']:
            raise RuntimeError('Fresh ZIP unexpectedly uses another installation')
        if image:
            run('PoP2Mac.exe', '--smoke-import', Path(image).resolve(), timeout=900)
            run('PoP2Mac.exe', '--check')
            prepared = json.loads(run('PoP2Mac.exe', '--smoke-test').strip().splitlines()[-1])
            if prepared['levels'] != list(range(1, 14)):
                raise RuntimeError('Imported build did not render every currently supported level')
            if reference:
                for name in ('caverns_entry.json', 'caverns_level4.json', 'caverns_level5.json',
                             'ruins_level6.json', 'ruins_level7.json', 'ruins_level8.json', 'ruins_level9.json',
                             'intro.json', 'ending.json', 'enemy_profiles.json', 'attract.json'):
                    expected = json.loads((Path(reference) / name).read_text())
                    actual = json.loads((bundle / 'assets' / name).read_text())
                    if actual != expected:
                        raise RuntimeError(f'Packaged import differs from the source export: {name}')
                    matching_exports.append(name)
            run('worker', '--warm-map-cache')
        run('PoP2Mac.exe', '--smoke-test')
        if defender:
            protection['after'] = check(bundle, scan=True)
        info = json.loads((bundle / 'BUILD-INFO.json').read_text())
    return dict(archive=Path(archive).name, sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
                build=info, checks=checks, fresh_import=bool(image),
                defender=protection, matching_exports=matching_exports,
                elapsed_seconds=round(monotonic() - started, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--defender', action='store_true', help='Require active protection, check exclusions and scan')
    parser.add_argument('--reference-assets', type=Path, help='Local original-image comparison only; never uploaded')
    args = parser.parse_args()
    report = smoke(args.archive, args.image, args.defender, args.reference_assets)
    text = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
