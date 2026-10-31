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


def smoke(archive, image=None):
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
        env = os.environ.copy()
        for name in ('PYTHONHOME', 'PYTHONPATH'):
            env.pop(name, None)
        windows = Path(env.get('SystemRoot', 'C:/Windows'))
        env.update(PATH=os.pathsep.join(map(str, (windows / 'System32', windows))),
                   POP2_USER_DATA=str(directory / 'userdata'), SDL_AUDIODRIVER='dummy',
                   PYGAME_HIDE_SUPPORT_PROMPT='1')

        def run(executable, *arguments, timeout=120):
            result = subprocess.run([str(bundle / executable), *map(str, arguments)], cwd=directory,
                                    env=env, capture_output=True, text=True, encoding='utf-8',
                                    stdin=subprocess.DEVNULL, timeout=timeout,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                diagnostics = '\n'.join(path.read_text(encoding='utf-8', errors='replace')[-4000:]
                                        for path in (bundle / 'rendered').glob('*.log'))
                raise RuntimeError(f'{executable} {arguments}: {result.returncode}\n'
                                   f'{result.stdout}\n{result.stderr}\n{diagnostics}')
            checks.append([executable, arguments[0]])
            return result.stdout

        run('PoP2Mac-tools.exe', '--check-dependencies')
        run('PoP2Mac-tools.exe', '--smoke-pool')
        run('PoP2Mac-tools.exe', '--smoke-native')
        fresh = json.loads(run('PoP2Mac-tools.exe', '--smoke-test').strip().splitlines()[-1])
        if Path(fresh['project']) != bundle or fresh['levels']:
            raise RuntimeError('Fresh ZIP unexpectedly uses another installation')
        if image:
            run('PoP2Mac-tools.exe', '--smoke-import', Path(image).resolve(), timeout=900)
            run('PoP2Mac-tools.exe', '--check')
            prepared = json.loads(run('PoP2Mac-tools.exe', '--smoke-test').strip().splitlines()[-1])
            if prepared['levels'] != list(range(1, 14)):
                raise RuntimeError('Imported build did not render every currently supported level')
            run('PoP2Mac-tools.exe', '--warm-map-cache')
        run('PoP2Mac.exe', '--smoke-test')
        info = json.loads((bundle / 'BUILD-INFO.json').read_text())
    return dict(archive=Path(archive).name, sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
                build=info, checks=checks, fresh_import=bool(image),
                elapsed_seconds=round(monotonic() - started, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = smoke(args.archive, args.image)
    text = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
