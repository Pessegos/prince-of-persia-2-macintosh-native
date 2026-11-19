import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pop2.asset_import import STAGES, ImportFailed
import pop2.packaged_app as packaged_app
import pop2.prepare_game as prepare_game


class FakeImport:
    """Reports every stage as tools.extract_assets and AssetImport do."""

    def __init__(self, failure=None):
        self.failure = failure
        self.images = []

    def run(self, image, progress, steps):
        self.images.append(image)
        for stage, _label, _weight in STAGES:
            steps(stage, 0, 4)
            progress(f'{stage} work')
            if self.failure is not None and stage == 'scenery':
                raise self.failure
            for done in range(1, 5):
                steps(stage, done, 4)


def progress_lines(text):
    lines = [line.split(' ', 2) for line in text.splitlines()]
    return [(float(fraction), message) for word, fraction, message in lines if word == 'progress']


class PrepareTests(unittest.TestCase):
    """The launcher's windowless import (--prepare --game=IMAGE)."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        self.image = self.project / 'game.dsk'
        self.image.write_bytes(b'image')
        for target, value in (('preflight', lambda _image, _project: None),):
            patcher = patch.object(prepare_game, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        remember = patch.object(prepare_game, 'remember')
        self.remember = remember.start()
        self.addCleanup(remember.stop)

    def prepare(self, argv, task=None):
        output = io.StringIO()
        code = prepare_game.prepare(argv, self.project, output, task or FakeImport())
        return code, output.getvalue()

    def test_both_spellings_of_the_image_argument(self):
        for argv in ([f'--game={self.image}'], ['--game', str(self.image)]):
            with self.subTest(argv=argv):
                task = FakeImport()
                code, _text = self.prepare(argv, task)
                self.assertEqual(code, 0)
                self.assertEqual(task.images, [str(self.image)])

    def test_progress_lines_rise_to_one_and_the_image_is_remembered(self):
        code, text = self.prepare([f'--game={self.image}'])
        self.assertEqual(code, 0)
        lines = progress_lines(text)
        self.assertEqual(len(lines), len(text.splitlines()), text)
        fractions = [fraction for fraction, _message in lines]
        self.assertEqual(fractions, sorted(fractions))
        self.assertEqual(fractions[0], 0)
        self.assertEqual(lines[-1], (1.0, 'Game files ready'))
        messages = [message for _fraction, message in lines]
        self.assertIn('Drawing the level scenery', messages)
        self.assertIn('scenery work', messages)
        # Unchanged lines are not repeated.
        self.assertEqual(len(set(text.splitlines())), len(text.splitlines()))
        self.remember.assert_called_once_with(game_image=str(self.image.resolve()))

    def test_a_missing_image_argument_imports_nothing(self):
        for argv in ([], ['--game'], ['--game=']):
            with self.subTest(argv=argv):
                task = FakeImport()
                code, text = self.prepare(argv, task)
                self.assertEqual(code, 2)
                self.assertTrue(text.startswith('error '))
                self.assertEqual(task.images, [])
        self.remember.assert_not_called()

    def test_an_unusable_image_is_explained_as_the_window_would(self):
        task = FakeImport()
        with patch.object(prepare_game, 'preflight', return_value='compressed_dmg'):
            code, text = self.prepare([f'--game={self.image}'], task)
        self.assertEqual(code, 1)
        self.assertEqual(task.images, [])
        self.assertIn(prepare_game.problem('compressed_dmg').title, text)
        self.remember.assert_not_called()

    def test_a_failed_import_exits_with_its_problem(self):
        failure = ImportFailed('unsupported', 'Missing PRINCE.rsrc', self.project / 'setup.log')
        with patch('sys.stderr', io.StringIO()) as detail:
            code, text = self.prepare([f'--game={self.image}'], FakeImport(failure))
        self.assertEqual(code, 1)
        self.assertEqual(text.splitlines()[-1],
                         'error ' + ' '.join(vars(prepare_game.problem('unsupported'))[key]
                                              for key in ('title', 'advice')))
        self.assertIn('Missing PRINCE.rsrc', detail.getvalue())
        self.remember.assert_not_called()


class PackagedDispatchTests(unittest.TestCase):
    def test_prepare_runs_without_starting_the_game(self):
        with patch('pop2.prepare_game.prepare', return_value=0) as prepare, \
                patch('run_game.main') as game:
            packaged_app.main(['--prepare', '--game=x.dsk'])
        prepare.assert_called_once_with(['--game=x.dsk'])
        game.assert_not_called()

    def test_a_failed_prepare_sets_the_exit_code(self):
        with patch('pop2.prepare_game.prepare', return_value=1), patch('run_game.main') as game:
            with self.assertRaises(SystemExit) as stop:
                packaged_app.main(['--prepare', '--game=x.dsk'])
        self.assertEqual(stop.exception.code, 1)
        game.assert_not_called()

    def test_without_prepare_the_game_starts_as_before(self):
        with patch('pop2.prepare_game.prepare') as prepare, patch('run_game.main') as game:
            packaged_app.main([])
        game.assert_called_once_with([])
        prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
