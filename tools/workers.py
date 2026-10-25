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
