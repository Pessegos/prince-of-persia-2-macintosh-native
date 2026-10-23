"""Tests that need the physical Windows desktop, and the shared-desktop mode.

Worktrees isolate files, not the desktop. A few tests map real windows, take
keyboard focus or deliver real Tk key events; the user's keys or another
suite's windows can disturb them, and they can take focus from a running game.

With POP2_SHARED_DESKTOP=1 (inherited by subprocesses) those tests are
skipped with an explicit reason, so the rest of the suite can run alongside
playtesting or another agent. They are skips, not passes: run the exclusive
group at an agreed moment with

    set POP2_SHARED_DESKTOP=
    .venv\\Scripts\\python.exe -m unittest -q tests.desktop_exclusive

Hidden Tk widgets driven by synthetic calls (most scene tests) do not need
the desktop and are not marked. Slow work, such as the fresh GUI import,
is a resource cost, not a desktop requirement, and is not marked either.
"""

import os
import unittest

SHARED_DESKTOP = os.environ.get("POP2_SHARED_DESKTOP") == "1"

# (module, class, test) of every test marked below, for the exclusive run.
EXCLUSIVE = []


def exclusive_desktop(reason):
    """Mark a test that needs the physical desktop (focus, mapped windows)."""
    def decorate(test):
        EXCLUSIVE.append((test.__module__, test.__qualname__))
        return unittest.skipIf(SHARED_DESKTOP, f"needs the exclusive desktop: {reason} "
                               "(POP2_SHARED_DESKTOP=1)")(test)
    return decorate
