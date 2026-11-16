"""Worker processes that end with the import that started them."""

import os
from multiprocessing import parent_process
from multiprocessing.connection import wait
import threading


def watch_parent():
    """Pool initializer: exit as soon as the parent process ends.

    A cancelled import is terminated, not shut down, and an orphaned pool
    worker would otherwise wait for work forever.
    """
    parent = parent_process()
    if parent is not None:
        def watch():
            wait([parent.sentinel])
            os._exit(1)

        threading.Thread(target=watch, daemon=True).start()


def background_worker():
    """Pool initializer for bulk work beside a serial chain: watch_parent, and
    run below normal priority so the importer's own (serial) steps keep their
    processor share. The bulk jobs still use every idle processor."""
    watch_parent()
    if os.name == 'nt':
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
    else:
        try:
            os.nice(5)
        except OSError:
            pass
