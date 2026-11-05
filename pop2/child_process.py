"""Launch the import/cache workers from source or a portable Windows build."""

import os
import sys

from pop2.paths import PROJECT_DIR, BUNDLED


def runtime_command(*arguments):
    """Use the unmodified, PSF-signed interpreter included in the ZIP."""
    internal = PROJECT_DIR / '_internal'
    return [str(internal / 'python/python.exe'), '-I', '-B', '-u',
            str(internal / 'worker/worker_entry.py'), *map(str, arguments)]


def worker_command(module, *arguments):
    if BUNDLED or getattr(sys, 'frozen', False):
        modes = {'tools.extract_assets': '--import-assets', 'pop2.development_map': '--warm-map-cache'}
        return runtime_command(modes[module], *arguments)
    unbuffered = ['-u'] if module == 'tools.extract_assets' else []
    return [sys.executable, *unbuffered, '-m', module, *map(str, arguments)]


def worker_environment():
    environment = os.environ.copy()
    if BUNDLED or getattr(sys, 'frozen', False):
        # The official interpreter and its native multiprocessing spawn do not
        # participate in PyInstaller's process/temporary-directory protocol.
        for name in tuple(environment):
            if name.startswith(('_PYI_', 'PYINSTALLER_')):
                del environment[name]
    return environment
