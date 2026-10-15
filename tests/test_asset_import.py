import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from pop2.asset_import import AssetImport, ImportCancelled
from pop2.paths import PROJECT_DIR


class AssetImportProcessTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        self.task = AssetImport(self.project)
        self.process = Mock()
        self.process.__enter__ = Mock(return_value=self.process)
        self.process.__exit__ = Mock(return_value=False)
        self.process.stdout = [json.dumps({'event': 'progress', 'message': 'Cavern scenery: room 1/32'}) + '\n']
        self.process.wait.return_value = 0
        self.process.poll.return_value = 0

    def start(self, command, **options):
        staging = Path(command[command.index('--output') + 1])
        (staging / 'Prince.rsrc').write_bytes(b'prepared resource')
        (staging / 'audio').mkdir()
        (staging / 'audio' / 'manifest.json').write_text('{}')
        return self.process

    def test_separate_python_process_reports_progress_and_publishes_complete_files(self):
        progress = Mock()
        with patch('pop2.asset_import.subprocess.Popen', side_effect=self.start) as launch:
            self.task.run('game.hfs', progress)
        self.assertEqual(launch.call_args.kwargs['cwd'], PROJECT_DIR)
        self.assertIn('--progress-json', launch.call_args.args[0])
        self.assertIn('Cavern scenery: room 1/32', [call.args[0] for call in progress.call_args_list])
        self.assertEqual((self.project / 'assets/Prince.rsrc').read_bytes(), b'prepared resource')
        self.assertTrue((self.project / 'assets/audio/manifest.json').is_file())
        self.assertFalse(list((self.project / 'assets').glob('.setup-*')))
        self.assertIsNone(self.task.process)

    def test_process_failure_preserves_existing_installation_and_keeps_diagnostics(self):
        assets = self.project / 'assets'
        assets.mkdir()
        (assets / 'Prince.rsrc').write_bytes(b'old resource')
        self.process.stdout = ['Traceback: native recovery failed\n']
        self.process.wait.return_value = 1
        with (patch('pop2.asset_import.subprocess.Popen', side_effect=self.start),
              self.assertRaisesRegex(ValueError, 'native recovery failed')):
            self.task.run('game.hfs')
        self.assertEqual((assets / 'Prince.rsrc').read_bytes(), b'old resource')
        self.assertFalse(list(assets.glob('.setup-*')))
        self.assertIn('native recovery failed', (self.project / 'rendered/setup.log').read_text())

    def test_real_child_reports_invalid_image_and_cleans_up(self):
        image = self.project / 'invalid disk image.hfs'
        image.write_bytes(b'not HFS')
        with self.assertRaisesRegex(ValueError, 'not a supported Macintosh PoP2'):
            self.task.run(image)
        self.assertIsNone(self.task.process)
        self.assertEqual(list((self.project / 'assets').iterdir()), [])
        self.assertIn('Asset extraction failed:', (self.project / 'rendered/setup.log').read_text())

    def test_cancel_before_launch_does_not_create_files_or_start_a_child(self):
        self.task.cancel()
        with (patch('pop2.asset_import.subprocess.Popen') as launch,
              self.assertRaises(ImportCancelled)):
            self.task.run('game.hfs')
        launch.assert_not_called()
        self.assertFalse((self.project / 'assets').exists())

    def test_cancel_while_recovering_terminates_child_and_removes_staged_output(self):
        self.process.poll.return_value = None
        self.process.terminate.side_effect = lambda: setattr(self.process.poll, 'return_value', 1)

        def output():
            self.task.cancel()
            yield 'Terminated\n'

        self.process.stdout = output()
        with (patch('pop2.asset_import.subprocess.Popen', side_effect=self.start),
              self.assertRaises(ImportCancelled)):
            self.task.run('game.hfs')
        self.process.terminate.assert_called_once()
        self.assertEqual(list((self.project / 'assets').iterdir()), [])

    def test_cancel_at_publication_boundary_does_not_install_resources(self):
        def progress(message):
            if message == 'Installing prepared game files...':
                self.task.cancel()

        with (patch('pop2.asset_import.subprocess.Popen', side_effect=self.start),
              self.assertRaises(ImportCancelled)):
            self.task.run('game.hfs', progress)
        self.assertEqual(list((self.project / 'assets').iterdir()), [])

    def test_bad_progress_callback_also_reaps_a_running_child(self):
        self.process.poll.return_value = None
        self.process.terminate.side_effect = lambda: setattr(self.process.poll, 'return_value', 1)
        with (patch('pop2.asset_import.subprocess.Popen', side_effect=self.start),
              self.assertRaisesRegex(ValueError, 'callback')):
            self.task.run('game.hfs', Mock(side_effect=ValueError('callback')))
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called_once()
        self.assertEqual(list((self.project / 'assets').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
