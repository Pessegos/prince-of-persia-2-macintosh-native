"""Load only the tests marked by tests.desktop.exclusive_desktop.

    .venv\\Scripts\\python.exe -m unittest -q tests.desktop_exclusive

Run it at an agreed moment, without POP2_SHARED_DESKTOP, while nobody plays
or runs another GUI suite on this desktop.
"""

import importlib
import unittest

from tests.desktop import EXCLUSIVE

MODULES = ('tests.test_window_controls', 'tests.test_game_menu', 'tests.test_intro_scene',
           'tests.test_bitmap_presenter', 'tests.test_window_aspect', 'tests.test_app_window')


def load_tests(loader, _tests, _pattern):
    for name in MODULES:
        importlib.import_module(name)
    suite = unittest.TestSuite()
    for module, qualified in EXCLUSIVE:
        class_name, test_name = qualified.split('.')
        suite.addTest(getattr(importlib.import_module(module), class_name)(test_name))
    return suite
