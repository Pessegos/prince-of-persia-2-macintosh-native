"""Build only the Unicorn import helper's bootloader without CFG, from pinned source."""

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
VERSION = '6.22.3'
SOURCE_SHA256 = '05eb2f5615503e72939a7224d68b4aff572c6b0438ee4a17d0a4b481f399362d'


def cfg_enabled(path):
    data = Path(path).read_bytes()
    if data[:2] != b'MZ':
        raise ValueError('Not a Windows executable')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', data, pe + 4)[0] != 0x8664:
        raise ValueError('Not an x64 Windows executable')
    return bool(struct.unpack_from('<H', data, pe + 24 + 70)[0] & 0x4000)


def prepare(output, compiler_directory=None):
    if sys.platform != 'win32' or sys.version_info < (3, 12):
        raise RuntimeError('Prepare with 64-bit Python 3.12 on Windows')
    if metadata.version('PyInstaller') != VERSION:
        raise RuntimeError(f'Expected PyInstaller {VERSION}')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f'https://pypi.org/pypi/pyinstaller/{VERSION}/json') as response:
        release = json.load(response)
    source = next(item for item in release['urls'] if item['packagetype'] == 'sdist')
    with tempfile.TemporaryDirectory(prefix='compile-', dir=output) as temporary:
        temporary = Path(temporary)
        archive = temporary / 'pyinstaller.tar.gz'
        urllib.request.urlretrieve(source['url'], archive)
        source_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        if source_hash != SOURCE_SHA256 or source_hash != source['digests']['sha256']:
            raise ValueError('PyInstaller source checksum mismatch')
        with tarfile.open(archive) as package:
            package.extractall(temporary, filter='data')
        source_root = temporary / f'pyinstaller-{VERSION}'
        environment = os.environ.copy()
        if compiler_directory:
            compiler_directory = Path(compiler_directory).resolve()
            environment['PATH'] = str(compiler_directory) + os.pathsep + environment['PATH']
            environment['CC'] = str(compiler_directory / 'x86_64-w64-mingw32-gcc.exe')
        subprocess.run([sys.executable, 'waf', 'all', '--no-cfg'], cwd=source_root / 'bootloader',
                       env=environment, check=True)
        bootloader = source_root / 'PyInstaller/bootloader/Windows-64bit-intel/run.exe'
        if cfg_enabled(bootloader):
            raise RuntimeError('Custom import bootloader still has CFG enabled')
        shutil.copy2(bootloader, output / 'run.exe')
        windowed = bootloader.with_name('runw.exe')
        if cfg_enabled(windowed):
            raise RuntimeError('Custom worker bootloader still has CFG enabled')
        shutil.copy2(windowed, output / 'runw.exe')
        shutil.copy2(source_root / 'COPYING.txt', output / 'COPYING-PyInstaller.txt')
        info = dict(pyinstaller=VERSION, source_url=source['url'], source_sha256=source_hash,
                    bootloader_sha256=hashlib.sha256(bootloader.read_bytes()).hexdigest(), cfg=False,
                    worker_bootloader_sha256=hashlib.sha256(windowed.read_bytes()).hexdigest(),
                    build_flags=['all', '--no-cfg'], compiler='llvm-mingw' if compiler_directory else 'auto (MSVC on Actions)',
                    purpose='Unicorn import helper only; windowed game keeps the stock CFG bootloader')
        (output / 'bootloader.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(info), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'rendered/windows/bootloader')
    parser.add_argument('--compiler-directory', type=Path)
    args = parser.parse_args()
    prepare(args.output, args.compiler_directory)


if __name__ == '__main__':
    main()
