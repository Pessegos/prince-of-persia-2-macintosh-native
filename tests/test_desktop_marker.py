import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import unittest

from pop2.paths import PROJECT_DIR

PROBE = textwrap.dedent('''
    import unittest
    from tests.desktop import exclusive_desktop

    class Probe(unittest.TestCase):
        @exclusive_desktop('probe')
        def test_desktop(self):
            pass

        def test_ordinary(self):
            pass

    result = unittest.TextTestRunner(verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Probe))
    print(len(result.skipped), result.testsRun, [reason for _test, reason in result.skipped])
''')


class DesktopMarkerTests(unittest.TestCase):
    def run_probe(self, shared):
        env = dict(os.environ)
        env.pop('POP2_SHARED_DESKTOP', None)
        if shared:
            env['POP2_SHARED_DESKTOP'] = '1'
        result = subprocess.run([sys.executable, '-c', PROBE], cwd=PROJECT_DIR, env=env,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_shared_mode_skips_only_marked_tests_with_an_explicit_reason(self):
        self.assertTrue(self.run_probe(True).startswith("1 2 ['needs the exclusive desktop: probe"))
        self.assertEqual(self.run_probe(False), '0 2 []')

    def test_the_exclusive_run_lists_every_marked_test(self):
        from tests.desktop import EXCLUSIVE
        from tests.desktop_exclusive import MODULES, load_tests

        marked = {}
        for path in (PROJECT_DIR / 'tests').glob('test_*.py'):
            count = len(re.findall(r'^\s*@exclusive_desktop\(', path.read_text(encoding='utf-8'), re.M))
            if count and path.name != Path(__file__).name:
                marked[f'tests.{path.stem}'] = count
        self.assertEqual(set(MODULES), set(marked))
        suite = load_tests(unittest.defaultTestLoader, None, None)
        self.assertEqual(suite.countTestCases(), sum(marked.values()))
        self.assertEqual(len({entry for entry in EXCLUSIVE if entry[0] != '__main__'}), sum(marked.values()))

    def test_saves_and_screenshot_settings_use_temporary_user_data(self):
        from pop2.save_game import SAVE_DIRECTORY
        from pop2.screenshots import SETTINGS_PATH, ScreenshotSettings

        user_data = Path(os.environ['POP2_USER_DATA'])
        for path in (SAVE_DIRECTORY, SETTINGS_PATH, ScreenshotSettings().folder):
            self.assertTrue(path.is_relative_to(user_data), path)
        self.assertNotIn('Saved Games', str(SAVE_DIRECTORY))


if __name__ == '__main__':
    unittest.main()
