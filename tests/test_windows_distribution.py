"""Portable paths, child routing and exclusion of imported/private files."""

import json
import hashlib
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
from tools.prepare_windows_runtime import (ARCHIVE_SHA256, MANIFEST, SIGNED_FILES, VERSION,
                                          development_file, signatures, trim_runtime, validate_runtime)


class WindowsDistributionTests(unittest.TestCase):
    def test_runtime_trimming_preserves_runtime_code_signatures_and_notices(self):
        from tools.prepare_windows_runtime import ROOT
        import shutil

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = root / 'prepared'
            preserved = [*SIGNED_FILES, 'python313.zip',
                         'Lib/site-packages/unicorn/lib/unicorn.dll',
                         'Lib/site-packages/numpy/__init__.py',
                         'Lib/site-packages/numpy/testing/__init__.py',
                         'Lib/site-packages/pygame/freesansbold.ttf',
                         'Lib/site-packages/numpy/tests/LICENSE.txt',
                         'Lib/site-packages/numpy-1.dist-info/METADATA',
                         'Lib/site-packages/numpy-1.dist-info/licenses/LICENSE.txt']
            omitted = ['Lib/site-packages/unicorn/lib/unicorn.lib',
                       'Lib/site-packages/numpy/tests/test_example.py',
                       'Lib/site-packages/pygame/examples/sample.py',
                       'Lib/site-packages/pygame/docs/index.html',
                       'Lib/site-packages/numpy/include/example.h']
            for name in preserved + omitted:
                path = prepared / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            files = {name: hashlib.sha256((prepared / name).read_bytes()).hexdigest()
                     for name in preserved + omitted}
            info = dict(version=VERSION, archive_sha256=ARCHIVE_SHA256,
                        dependencies=dict(line.strip().lower().split('==')
                                          for line in (ROOT / 'requirements-import.txt').read_text().splitlines()
                                          if line.strip() and not line.startswith('#')), files=files)
            (prepared / MANIFEST).write_text(json.dumps(info))
            packaged = root / 'packaged'
            shutil.copytree(prepared, packaged)
            result = trim_runtime(packaged)
            self.assertEqual(set(result['files']), set(preserved))
            self.assertEqual(result['distribution']['omitted_files'], len(omitted))
            for name in preserved:
                self.assertEqual((packaged / name).read_bytes(), (prepared / name).read_bytes())
            for name in omitted:
                self.assertTrue((prepared / name).is_file())
                self.assertFalse((packaged / name).exists())
            self.assertEqual(validate_runtime(prepared)['files'], files)
            self.assertTrue(development_file('unicorn/lib/unicorn.lib'))
            self.assertFalse(development_file('unicorn/lib/unicorn.dll'))

    def test_cfg_check_detects_the_launcher_mitigation(self):
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

    def test_runtime_manifest_rejects_modified_extra_or_stale_dependencies(self):
        from tools.prepare_windows_runtime import ROOT

        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            for name in SIGNED_FILES:
                (runtime / name).write_bytes(b'signed file fixture')
            info = dict(version=VERSION, archive_sha256=ARCHIVE_SHA256,
                        dependencies=dict(line.strip().lower().split('==')
                                          for line in (ROOT / 'requirements-import.txt').read_text().splitlines()
                                          if line.strip() and not line.startswith('#')),
                        files={name: hashlib.sha256((runtime / name).read_bytes()).hexdigest()
                               for name in SIGNED_FILES})
            manifest = runtime / MANIFEST
            manifest.write_text(json.dumps(info))
            validate_runtime(runtime)
            changed = runtime / SIGNED_FILES[0]
            changed.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                validate_runtime(runtime)
            changed.write_bytes(b'signed file fixture')
            extra = runtime / 'unexpected.exe'
            extra.touch()
            with self.assertRaisesRegex(ValueError, 'file list'):
                validate_runtime(runtime)
            extra.unlink()
            info['dependencies']['unicorn'] = '0.0'
            manifest.write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError, 'dependencies'):
                validate_runtime(runtime)

    def test_authenticode_requires_all_four_valid_psf_signatures(self):
        records = [dict(file=name, status='Valid', signer='CN=Python Software Foundation, '
                        'O=Python Software Foundation, C=US') for name in SIGNED_FILES]
        with patch('tools.prepare_windows_runtime.subprocess.run') as run:
            run.return_value.stdout = json.dumps(records)
            self.assertEqual(signatures('.'), records)
            for change in ({'status': 'HashMismatch'}, {'signer': 'O=Other Company,'}, {'signer': None}):
                with self.subTest(change=change):
                    altered = [dict(record) for record in records]
                    altered[0].update(change)
                    run.return_value.stdout = json.dumps(altered)
                    with self.assertRaisesRegex(ValueError, 'Authenticode'):
                        signatures('.')
            run.return_value.stdout = json.dumps(records[:-1])
            with self.assertRaisesRegex(ValueError, 'Authenticode'):
                signatures('.')

    def test_source_workers_keep_the_real_python_module_entry(self):
        self.assertEqual(worker_command('tools.extract_assets', 'disk.hfs', '--progress-json'),
                         [sys.executable, '-u', '-m', 'tools.extract_assets', 'disk.hfs', '--progress-json'])

    def test_signed_helpers_drop_bootloader_protocol_but_keep_user_settings(self):
        with patch.dict('os.environ', {'POP2_USER_DATA': 'test settings'}, clear=True):
            self.assertEqual(worker_environment(), {'POP2_USER_DATA': 'test settings'})
            with patch.object(sys, 'frozen', True, create=True):
                with patch.dict('os.environ', {'_PYI_ARCHIVE_FILE': 'old.exe',
                                              'PYINSTALLER_RESET_ENVIRONMENT': '1'}):
                    self.assertEqual(worker_environment(), {'POP2_USER_DATA': 'test settings'})

    def test_frozen_workers_use_the_official_interpreter_and_named_entry(self):
        executable = str(PROJECT_DIR / 'example portable/PoP2Mac.exe')
        with patch.object(sys, 'frozen', True, create=True), \
                patch('pop2.child_process.PROJECT_DIR', Path(executable).parent):
            internal = Path(executable).parent / '_internal'
            helper = [str(internal / 'python/python.exe'), '-I', '-B', '-u',
                      str(internal / 'worker/worker_entry.py')]
            self.assertEqual(worker_command('tools.extract_assets', 'disk.hfs'),
                             [*helper, '--import-assets', 'disk.hfs'])
            self.assertEqual(worker_command('pop2.development_map', '--warm'),
                             [*helper, '--warm-map-cache', '--warm'])
            with self.assertRaises(KeyError):
                worker_command('an.unapproved.module')

    def test_frozen_writable_paths_are_beside_the_executable_not_internal_code(self):
        with tempfile.TemporaryDirectory() as directory:
            # Actions may supply an 8.3 TEMP alias (RUNNER~1). The production
            # path deliberately resolves it to the long name before use.
            executable = (Path(directory) / 'portable game/PoP2Mac.exe').resolve()
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
            for name in ('PoP2Mac.exe', '_internal/python/python.exe', '_internal/python/pythonw.exe',
                         '_internal/worker/worker_entry.py', '_internal/worker/portable-worker.json',
                         'LICENSE', 'BUILD-INFO.json', 'README.txt'):
                path = bundle / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
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
            (bundle / 'PoP2Mac-tools.exe').touch()
            with self.assertRaisesRegex(ValueError, 'Obsolete custom'):
                validate_bundle(bundle)

    def test_signed_worker_paths_point_to_the_portable_root(self):
        import shutil
        import pop2.paths

        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory).resolve()
            code = bundle / '_internal/worker'
            (code / 'pop2').mkdir(parents=True)
            shutil.copy2(pop2.paths.__file__, code / 'pop2/paths.py')
            (code / 'portable-worker.json').write_text('{"schema":1}')
            script = (f'import sys; sys.path.insert(0,{str(code)!r}); '
                      'from pop2.paths import PROJECT_DIR,BUNDLED; '
                      'import json;print(json.dumps([str(PROJECT_DIR),BUNDLED]))')
            result = subprocess.run([sys.executable, '-I', '-c', script], cwd=directory,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), [str(bundle), True])

    def test_gui_and_signed_worker_share_the_same_preview_cache_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codes = [root / name / 'pop2' for name in ('gui', 'worker')]
            for code in codes:
                code.mkdir(parents=True)
                (code.parent / 'build-info.json').write_text('{"commit":"same"}')
                (code / 'cavern_retouch.json').write_text('{"same":"art"}')
            (codes[1] / 'renderer.py').write_text('ordinary_source = True')
            with patch('pop2.preview_cache.BUNDLED', True):
                self.assertEqual(preview_fingerprint(root / 'assets', codes[0]),
                                 preview_fingerprint(root / 'assets', codes[1]))

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
