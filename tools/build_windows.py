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
    for name in ('PoP2Mac.exe', 'PoP2Mac-tools.exe', 'PoP2Mac-worker.exe', 'LICENSE', 'BUILD-INFO.json', 'README.txt'):
        if not (directory / name).is_file():
            raise ValueError(f'Incomplete portable build: {name}')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def build_info(version):
    digest = hashlib.sha256()
    names = set(git('ls-files', 'pop2', 'tools', 'run_game.py', 'distribution', 'vendor').splitlines())
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
    for name in DEPENDENCIES:
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


def build(version, output):
    if sys.platform != 'win32' or sys.maxsize <= 2**32:
        raise RuntimeError('Build on 64-bit Windows with a 64-bit Python installation')
    if sys.version_info[:3] == (3, 10, 0):
        raise RuntimeError('Python 3.10.0 has a bytecode inspection bug; use Python 3.12 for builds')
    version = validate_version(version)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    bootloader = ROOT / 'rendered/windows/bootloader/run.exe'
    if not bootloader.is_file() or cfg_enabled(bootloader):
        raise RuntimeError('Prepare the Unicorn helper first: python -m tools.prepare_windows_bootloader')
    # Unique work directory: a repeated build never overwrites an installation
    # in which someone might already have imported assets or made saves.
    work = Path(tempfile.mkdtemp(prefix='build-', dir=output))
    info = build_info(version)
    info['import_bootloader'] = json.loads(bootloader.with_name('bootloader.json').read_text())
    if hashlib.sha256(bootloader.read_bytes()).hexdigest() != info['import_bootloader']['bootloader_sha256']:
        raise RuntimeError('Import bootloader checksum does not match its build record')
    worker_bootloader = bootloader.with_name('runw.exe')
    if (cfg_enabled(worker_bootloader) or hashlib.sha256(worker_bootloader.read_bytes()).hexdigest()
            != info['import_bootloader']['worker_bootloader_sha256']):
        raise RuntimeError('Worker bootloader does not match its build record')
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
class ImportEXE(EXE):
    def _bootloader_file(self, exe, extension=None):
        return {str(bootloader)!r}
class WorkerEXE(EXE):
    def _bootloader_file(self, exe, extension=None):
        return {str(worker_bootloader)!r}
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PoP2Mac',
          console=False, icon={str(ROOT / 'pop2/icons/prince.ico')!r})
helper = ImportEXE(pyz, a.scripts, [], exclude_binaries=True, name='PoP2Mac-tools',
             console=True, icon={str(ROOT / 'pop2/icons/prince.ico')!r})
worker = WorkerEXE(pyz, a.scripts, [], exclude_binaries=True, name='PoP2Mac-worker',
             console=False, icon={str(ROOT / 'pop2/icons/prince.ico')!r})
COLLECT(gui, helper, worker, a.binaries, a.datas, name='PoP2Mac')
''', encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(work / 'dist'),
                    '--workpath', str(work / 'cache'), str(spec)], cwd=ROOT, check=True)
    bundle = work / 'dist/PoP2Mac'
    shutil.copy2(ROOT / 'LICENSE', bundle / 'LICENSE')
    shutil.copy2(ROOT / 'distribution/README.txt', bundle / 'README.txt')
    shutil.copy2(info_file, bundle / 'BUILD-INFO.json')
    copy_notices(bundle)
    shutil.copy2(bootloader.with_name('COPYING-PyInstaller.txt'), bundle / 'licenses/COPYING-PyInstaller.txt')
    if (not cfg_enabled(bundle / 'PoP2Mac.exe') or cfg_enabled(bundle / 'PoP2Mac-tools.exe')
            or cfg_enabled(bundle / 'PoP2Mac-worker.exe')):
        raise RuntimeError('Unexpected CFG policy in the final executables')
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
