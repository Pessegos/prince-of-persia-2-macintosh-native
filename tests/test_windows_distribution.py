"""Portable paths, child routing and exclusion of imported/private files."""

import json
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from pop2.child_process import worker_command, worker_environment
from pop2.paths import PROJECT_DIR
from pop2.preview_cache import preview_fingerprint
from tools.build_windows import validate_bundle, validate_version
from tools.prepare_windows_bootloader import cfg_enabled


class WindowsDistributionTests(unittest.TestCase):
    def test_cfg_check_distinguishes_game_and_import_bootloaders(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'example.exe'
            data = bytearray(512)
            data[:2] = b'MZ'
            struct.pack_into('<I', data, 0x3c, 0x80)
            data[0x80:0x84] = b'PE\0\0'
            struct.pack_into('<H', data, 0x84, 0x8664)
            for flags, expected in ((0x4000, True), (0, False)):
                struct.pack_into('<H', data, 0x80 + 24 + 70, flags)
                path.write_bytes(data)
                self.assertEqual(cfg_enabled(path), expected)

    def test_source_workers_keep_the_real_python_module_entry(self):
        self.assertEqual(worker_command('tools.extract_assets', 'disk.hfs', '--progress-json'),
                         [sys.executable, '-u', '-m', 'tools.extract_assets', 'disk.hfs', '--progress-json'])

    def test_frozen_helpers_reset_the_bootloader_environment_but_keep_user_settings(self):
        with patch.dict('os.environ', {'POP2_USER_DATA': 'test settings'}, clear=True):
            self.assertEqual(worker_environment(), {'POP2_USER_DATA': 'test settings'})
            with patch.object(sys, 'frozen', True, create=True):
                self.assertEqual(worker_environment(), {'POP2_USER_DATA': 'test settings',
                                                       'PYINSTALLER_RESET_ENVIRONMENT': '1'})

    def test_frozen_workers_use_the_bundled_helper_and_named_entry(self):
        executable = str(PROJECT_DIR / 'example portable/PoP2Mac.exe')
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', executable):
            helper = str(Path(executable).with_name('PoP2Mac-tools.exe'))
            self.assertEqual(worker_command('tools.extract_assets', 'disk.hfs'),
                             [helper, '--import-assets', 'disk.hfs'])
            self.assertEqual(worker_command('pop2.development_map', '--warm'),
                             [helper, '--warm-map-cache', '--warm'])
            with self.assertRaises(KeyError):
                worker_command('an.unapproved.module')

    def test_frozen_writable_paths_are_beside_the_executable_not_internal_code(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'portable game/PoP2Mac.exe'
            script = (f'import sys; sys.frozen=True; sys.executable={str(executable)!r}; '
                      'from pop2.paths import PROJECT_DIR, ASSET_DIR, OUTPUT_DIR; '
                      'import run_game, json; '
                      'print(json.dumps(list(map(str, (PROJECT_DIR, ASSET_DIR, OUTPUT_DIR, run_game.PROJECT)))))')
            result = subprocess.run([sys.executable, '-c', script], cwd=PROJECT_DIR,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), list(map(str, (executable.parent,
                             executable.parent / 'assets', executable.parent / 'rendered', executable.parent))))

    def test_build_labels_cannot_be_paths_or_shell_fragments(self):
        for value in ('v0.1.0-alpha', 'dev-a123', 'test_2'):
            self.assertEqual(validate_version(value), value)
        for value in ('../game', 'a/b', 'a\\b', '', 'test;bad', 'x' * 65):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_version(value)

    def test_bundle_audit_rejects_imported_resources_saves_and_user_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            for name in ('PoP2Mac.exe', 'PoP2Mac-tools.exe', 'PoP2Mac-worker.exe', 'LICENSE', 'BUILD-INFO.json', 'README.txt'):
                (bundle / name).touch()
            validate_bundle(bundle)
            for name in ('Prince.rsrc', 'disk.HFS', 'test.pop2save', '_internal/assets/data.json',
                         'rendered/prefs.json', '_internal/saves/state.json'):
                with self.subTest(name=name):
                    path = bundle / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                    with self.assertRaisesRegex(ValueError, 'Private/imported'):
                        validate_bundle(bundle)
                    path.unlink()

    def test_frozen_preview_caches_change_when_the_embedded_build_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            code = bundle / 'pop2'
            code.mkdir()
            info = bundle / 'build-info.json'
            info.write_text('{"commit": "before"}')
            with patch.object(sys, 'frozen', True, create=True):
                before = preview_fingerprint(bundle / 'assets', code)
                info.write_text('{"commit": "after"}')
                self.assertNotEqual(before, preview_fingerprint(bundle / 'assets', code))


if __name__ == '__main__':
    unittest.main()
