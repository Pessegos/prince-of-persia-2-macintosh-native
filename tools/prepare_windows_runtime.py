"""Vendor an official PSF-signed Python and pinned wheels for import workers."""

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.13.17'
ARCHIVE_SHA256 = '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
URL = f'https://www.python.org/ftp/python/{VERSION}/python-{VERSION}-embed-amd64.zip'
SIGNED_FILES = ('python.exe', 'pythonw.exe', 'python3.dll', 'python313.dll')
MANIFEST = 'runtime-info.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def development_file(relative):
    """Wheel files used to develop/test dependencies, rather than run the app."""
    relative = Path(relative)
    parts = tuple(part.lower() for part in relative.parts)
    # Keep package metadata and notices, even inside an omitted documentation
    # directory. This does not trim any of the official interpreter's files.
    if (any(part.endswith('.dist-info') for part in parts)
            or any(word in relative.name.lower() for word in ('license', 'copying', 'notice', 'copyright'))):
        return False
    return (relative.suffix.lower() in ('.lib', '.a')
            or any(part in ('tests', 'test', 'examples', 'docs', 'include', '__pycache__') for part in parts))


def trim_runtime(directory):
    """Trim only a private packaging copy; preserve signed bytes and notices."""
    directory = Path(directory).resolve()
    info = validate_runtime(directory)
    site = (directory / 'Lib/site-packages').resolve()
    removed = {}
    for path in site.rglob('*'):
        if not path.is_file() or not development_file(path.relative_to(site)):
            continue
        if not path.resolve().is_relative_to(site):
            raise ValueError('Runtime development file escapes the packaging copy')
        removed[path.relative_to(directory).as_posix()] = path.stat().st_size
        path.unlink()
    info['distribution'] = dict(policy='runtime-only-v1', omitted_files=len(removed),
                                omitted_bytes=sum(removed.values()))
    info['files'] = {name: checksum for name, checksum in info['files'].items() if name not in removed}
    (directory / MANIFEST).write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    return validate_runtime(directory)


def signatures(directory):
    """Validate the existing Authenticode chains, without modifying binaries."""
    script = r'''
$ErrorActionPreference = 'Stop'
@('python.exe','pythonw.exe','python3.dll','python313.dll') | ForEach-Object {
    $item = Get-AuthenticodeSignature -LiteralPath (Join-Path $env:POP2_VERIFY_RUNTIME $_)
    [pscustomobject]@{file=$_; status=[string]$item.Status; signer=$item.SignerCertificate.Subject}
} | ConvertTo-Json -Compress
'''
    env = os.environ.copy()
    # A PowerShell 7 parent may export its Core-only module directories.
    # Let Windows PowerShell discover its own built-in security module.
    env = {name: value for name, value in env.items() if name.upper() != 'PSMODULEPATH'}
    env['POP2_VERIFY_RUNTIME'] = str(Path(directory).resolve())
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            env=env, check=True, capture_output=True, text=True)
    records = json.loads(result.stdout)
    if ({item['file'] for item in records} != set(SIGNED_FILES)
            or any(item['status'] != 'Valid' or 'O=Python Software Foundation,' not in (item['signer'] or '')
                   for item in records)):
        raise ValueError('Official Python Authenticode validation failed')
    return records


def validate_runtime(directory):
    directory = Path(directory)
    info = json.loads((directory / MANIFEST).read_text(encoding='utf-8'))
    if info['version'] != VERSION or info['archive_sha256'] != ARCHIVE_SHA256:
        raise ValueError('Unexpected bundled interpreter')
    expected = dict(line.strip().lower().split('==')
                    for line in (ROOT / 'requirements-import.txt').read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith('#'))
    if {name.lower(): version for name, version in info['dependencies'].items()} != expected:
        raise ValueError('Bundled interpreter dependencies need preparing again')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*')
              if path.is_file() and path != directory / MANIFEST}
    if actual != info['files'].keys():
        raise ValueError('Runtime file list differs from its build record')
    for name, expected in info['files'].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or digest(path) != expected:
            raise ValueError(f'Runtime file checksum mismatch: {name}')
    if not set(SIGNED_FILES) <= info['files'].keys():
        raise ValueError('Runtime record lacks signed executables/libraries')
    return info


def prepare(output):
    if sys.platform != 'win32' or sys.maxsize <= 2**32:
        raise RuntimeError('Prepare on 64-bit Windows')
    output = Path(output).resolve()
    if output.exists():
        info = validate_runtime(output)
        signatures(output)
        return info
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='runtime-', dir=output.parent) as temporary:
        temporary = Path(temporary).resolve()
        archive = temporary / 'python.zip'
        urllib.request.urlretrieve(URL, archive)
        if digest(archive) != ARCHIVE_SHA256:
            raise ValueError('Official interpreter archive checksum mismatch')
        runtime = temporary / 'python'
        with ZipFile(archive) as zipped:
            if any(not (runtime / name).resolve().is_relative_to(runtime.resolve())
                   for name in zipped.namelist()):
                raise ValueError('Unsafe interpreter archive member')
            zipped.extractall(runtime)
        signed = signatures(runtime)
        site = runtime / 'Lib/site-packages'
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                        '--target', str(site), '--platform', 'win_amd64', '--python-version', '3.13',
                        '--implementation', 'cp', '--abi', 'cp313', '--only-binary=:all:', '--no-compile',
                        '-r', str(ROOT / 'requirements-import.txt')], check=True)
        # _pth + -I exclude the user's PATH/registry/site packages. No pip is
        # shipped and no installation/download happens on the player's PC.
        (runtime / 'python313._pth').write_text(
            'python313.zip\n.\nLib/site-packages\n../worker\n', encoding='ascii')
        info = dict(version=VERSION, url=URL, archive_sha256=ARCHIVE_SHA256, signatures=signed,
                    dependencies={dist.metadata['Name']: dist.version
                                  for dist in metadata.distributions(path=[str(site)])},
                    files={str(path.relative_to(runtime)).replace('\\', '/'): digest(path)
                           for path in sorted(runtime.rglob('*')) if path.is_file()})
        (runtime / MANIFEST).write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
        shutil.move(str(runtime), str(output))
    return validate_runtime(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'rendered/windows/runtime')
    args = parser.parse_args()
    info = prepare(args.output)
    print(json.dumps({key: value for key, value in info.items() if key != 'files'}, indent=2))


if __name__ == '__main__':
    main()
