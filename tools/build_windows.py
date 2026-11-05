"""Build a portable Windows ZIP, without imported game files or user data."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from tools.prepare_windows_bootloader import cfg_enabled
from tools.prepare_windows_runtime import validate_runtime, signatures


ROOT = Path(__file__).resolve().parents[1]
SUPPORT_FILES = ('pop2/cavern_retouch.json', 'pop2/cavern_retouch.png', 'pop2/lava_recess.json',
                 'pop2/save_quill.png', 'pop2/screenshot_lava.png',
                 'pop2/icons/prince.ico', 'pop2/icons/prince.png')
DEPENDENCIES = ('Pillow', 'pygame', 'mido', 'numpy', 'unicorn')
FORBIDDEN_SUFFIXES = {'.rsrc', '.hfs', '.hfv', '.dsk', '.img', '.rom', '.pop2save'}


def validate_version(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', value):
        raise ValueError('Use a version label containing only letters, digits, dots, underscores and hyphens')
    return value


def validate_bundle(directory):
    for path in directory.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if (path.suffix.lower() in FORBIDDEN_SUFFIXES
                or any(part.lower() in ('assets', 'rendered', '.venv', 'saves') for part in relative.parts)):
            raise ValueError(f'Private/imported data must not be distributed: {relative}')
    for name in ('PoP2Mac.exe', '_internal/python/python.exe', '_internal/python/pythonw.exe',
                 '_internal/worker/worker_entry.py', '_internal/worker/portable-worker.json',
                 'LICENSE', 'BUILD-INFO.json', 'README.txt'):
        if not (directory / name).is_file():
            raise ValueError(f'Incomplete portable build: {name}')
    for name in ('PoP2Mac-tools.exe', 'PoP2Mac-worker.exe'):
        if (directory / name).exists():
            raise ValueError(f'Obsolete custom import executable: {name}')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def build_info(version):
    digest = hashlib.sha256()
    names = set(git('ls-files', 'pop2', 'tools', 'run_game.py', 'distribution', 'vendor').splitlines())
    names.update(('requirements-import.txt', 'requirements-build.txt'))
    for folder in ('pop2', 'tools', 'distribution'):
        names.update(str(path.relative_to(ROOT)).replace('\\', '/') for path in (ROOT / folder).rglob('*.py'))
    for name in sorted(names):
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return dict(version=version, commit=git('rev-parse', 'HEAD'),
                dirty=bool(git('status', '--porcelain', '--untracked-files=normal')),
                built_utc=datetime.now(timezone.utc).isoformat(), source_sha256=digest.hexdigest(),
                python=platform.python_version(), architecture=platform.machine(),
                pyinstaller=metadata.version('PyInstaller'),
                dependencies={name: metadata.version(name) for name in DEPENDENCIES})


def copy_notices(bundle):
    licenses = bundle / 'licenses'
    licenses.mkdir()
    for name in (*DEPENDENCIES, 'PyInstaller'):
        dist = metadata.distribution(name)
        for item in dist.files or ():
            if not any('license' in part.lower() or part.lower().startswith('copying') for part in item.parts):
                continue
            source = Path(dist.locate_file(item))
            if not source.is_file() or source.suffix.lower() in ('.py', '.pyc'):
                continue
            target = licenses / name / str(item).replace('..', '_parent_')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for path in (Path(sys.base_prefix) / 'LICENSE.txt',
                 Path(sys.base_prefix) / 'tcl/tcl8.6/license.terms',
                 Path(sys.base_prefix) / 'tcl/tk8.6/license.terms'):
        if path.is_file():
            target = licenses / 'Python-Tcl-Tk' / path.parent.name / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def copy_worker_code(bundle, info_file):
    code = bundle / '_internal/worker'
    code.mkdir(parents=True)
    for folder in ('pop2', 'tools'):
        for source in (ROOT / folder).rglob('*.py'):
            destination = code / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for name in SUPPORT_FILES:
        destination = code / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    shutil.copy2(ROOT / 'run_game.py', code / 'run_game.py')
    shutil.copy2(ROOT / 'distribution/worker_entry.py', code / 'worker_entry.py')
    shutil.copy2(info_file, code / 'build-info.json')
    shutil.copytree(ROOT / 'vendor/smssynth', code / 'vendor/smssynth')
    (code / 'portable-worker.json').write_text('{"schema": 1}\n', encoding='ascii')


def build(version, output):
    if sys.platform != 'win32' or sys.maxsize <= 2**32:
        raise RuntimeError('Build on 64-bit Windows with a 64-bit Python installation')
    if sys.version_info[:3] == (3, 10, 0):
        raise RuntimeError('Python 3.10.0 has a bytecode inspection bug; use Python 3.12 for builds')
    version = validate_version(version)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / 'rendered/windows/runtime'
    runtime_info = validate_runtime(runtime)
    signatures(runtime)
    # Unique work directory: a repeated build never overwrites an installation
    # in which someone might already have imported assets or made saves.
    work = Path(tempfile.mkdtemp(prefix='build-', dir=output))
    info = build_info(version)
    info['import_runtime'] = {key: value for key, value in runtime_info.items() if key != 'files'}
    info_file = work / 'build-info.json'
    info_file.write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    data = [(str(ROOT / name), str(Path(name).parent)) for name in SUPPORT_FILES]
    data.extend([(str(ROOT / 'vendor/smssynth'), 'vendor/smssynth'), (str(info_file), '.')])
    spec = work / 'PoP2Mac.spec'
    spec.write_text(f'''
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata
data = {data!r}
for name in {DEPENDENCIES!r}:
    data += copy_metadata(name, recursive=True)
a = Analysis([{str(ROOT / 'distribution/windows_entry.py')!r}], pathex=[{str(ROOT)!r}],
             datas=data, binaries=collect_dynamic_libs('unicorn'),
             hiddenimports=['pygame.mixer', 'mido', 'numpy', 'unicorn', 'tkinter'],
             excludes=['pytest', 'IPython'])
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PoP2Mac',
          console=False, upx=False, icon={str(ROOT / 'pop2/icons/prince.ico')!r})
COLLECT(gui, a.binaries, a.datas, upx=False, name='PoP2Mac')
''', encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(work / 'dist'),
                    '--workpath', str(work / 'cache'), str(spec)], cwd=ROOT, check=True)
    bundle = work / 'dist/PoP2Mac'
    shutil.copy2(ROOT / 'LICENSE', bundle / 'LICENSE')
    shutil.copy2(ROOT / 'distribution/README.txt', bundle / 'README.txt')
    shutil.copy2(info_file, bundle / 'BUILD-INFO.json')
    copy_notices(bundle)
    shutil.copytree(runtime, bundle / '_internal/python')
    copy_worker_code(bundle, info_file)
    validate_runtime(bundle / '_internal/python')
    if not cfg_enabled(bundle / 'PoP2Mac.exe'):
        raise RuntimeError('Game launcher must retain the stock CFG bootloader')
    validate_bundle(bundle)
    archive = output / f'PoP2Mac-{version}-windows-x64.zip'
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as target:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                target.write(path, Path('PoP2Mac') / path.relative_to(bundle))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='ascii')
    print(json.dumps(dict(archive=str(archive), sha256=checksum, bundle=str(bundle))), flush=True)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='dev')
    parser.add_argument('--output', type=Path, default=ROOT / 'rendered/windows')
    args = parser.parse_args()
    build(args.version, args.output)


if __name__ == '__main__':
    main()
