"""Opt-in tests that cost far more than the rest, and the POP2_SLOW_TESTS switch.

A few tests are worth running only when their area changes or before an
integration: the fresh import from the original disk image (about 80 s) and
the frame-cost guard (about 20 s, and timing-sensitive on a loaded machine).
Without POP2_SLOW_TESTS=1 (inherited by subprocesses) they are skipped with an
explicit reason. They are skips, not passes. Run them with

    .venv\\Scripts\\python.exe -m tools.run_tests --slow

or set POP2_SLOW_TESTS=1 for an ordinary unittest run.
"""

import os
import unittest

SLOW_TESTS = os.environ.get("POP2_SLOW_TESTS") == "1"


def slow_test(reason):
    """Mark a test (or class) that runs only with POP2_SLOW_TESTS=1."""
    return unittest.skipUnless(SLOW_TESTS, f"slow test, set POP2_SLOW_TESTS=1 to run it: {reason}")
