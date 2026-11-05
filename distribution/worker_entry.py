"""Ordinary Python entry for the official signed import/cache runtime."""

import multiprocessing
from pathlib import Path
import sys


if __name__ == '__main__':
    # Native Windows spawn, without PyInstaller's custom executable protocol.
    # pythonw.exe is also unmodified and signed; pool children flash no console.
    multiprocessing.freeze_support()
    multiprocessing.set_executable(str(Path(sys.executable).with_name('pythonw.exe')))
    from pop2.worker_app import main

    main()
