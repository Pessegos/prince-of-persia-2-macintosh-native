"""Launch the import/cache workers from source or a portable Windows build."""

from pathlib import Path
import os
import sys


def worker_command(module, *arguments):
    if getattr(sys, 'frozen', False):
        modes = {'tools.extract_assets': '--import-assets', 'pop2.development_map': '--warm-map-cache'}
        return [str(Path(sys.executable).with_name('PoP2Mac-tools.exe')), modes[module], *map(str, arguments)]
    unbuffered = ['-u'] if module == 'tools.extract_assets' else []
    return [sys.executable, *unbuffered, '-m', module, *map(str, arguments)]


def worker_environment():
    environment = os.environ.copy()
    if getattr(sys, 'frozen', False):
        # Import/cache helpers are independent app processes, not multiprocessing
        # children. Their own pools inherit the environment after bootloader reset.
        environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return environment
