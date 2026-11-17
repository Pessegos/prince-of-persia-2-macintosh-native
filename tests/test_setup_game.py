from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import ANY, patch

from pop2.asset_import import ImportFailed
import pop2.setup_game as setup_game


def hidden_root():
    root = tk.Tk()
    root.withdraw()
    return root


class GameSetupTests(unittest.TestCase):
    """The game-files window, as hidden Tk widgets driven by direct calls."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        self.image = self.project / 'game.hfs'
        self.image.write_bytes(b'image')
        for target, value in (('create_root', hidden_root), ('preflight', lambda _image, _project: None)):
            patcher = patch.object(setup_game, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        remember = patch.object(setup_game, 'remember')
        self.remember = remember.start()
        self.addCleanup(remember.stop)

    def make(self, missing=(), remembered=''):
        prefs = type('Prefs', (), {'game_image': remembered})()
        with patch.object(setup_game, 'load_preferences', return_value=prefs):
            setup = setup_game.GameSetup(self.project, missing)
        self.addCleanup(self.destroy, setup)
        return setup

    @staticmethod
    def destroy(setup):
        try:
            setup.root.destroy()
        except tk.TclError:
            pass

    @staticmethod
    def alive(setup):
        try:
            return bool(setup.root.winfo_exists())
        except tk.TclError:
            return False

    def run_import(self, setup, image, error=None):
        """Choose `image` in the picker; the import runs synchronously."""
        with (
            patch.object(setup_game.filedialog, 'askopenfilename', return_value=str(image)) as picker,
            patch.object(setup_game, 'import_game', side_effect=error) as importer,
            patch.object(setup_game, 'Thread') as thread,
        ):
            thread.return_value.start.side_effect = lambda: setup_game.import_files(
                *thread.call_args.kwargs['args'])
            setup.choose()
            setup.poll_import()
        return picker, importer

    def test_import_uses_the_selected_project_directory(self):
        with patch.object(setup_game, 'AssetImport') as importer:
            setup_game.import_game("game.hfs", self.project)
        importer.assert_called_once_with(self.project)
        importer.return_value.run.assert_called_once_with('game.hfs', ANY, ANY)

    def test_cancelled_file_picker_does_not_import_or_close_setup(self):
        setup = self.make()
        with (
            patch.object(setup_game.filedialog, "askopenfilename", return_value=""),
            patch.object(setup_game, "import_game") as importer,
        ):
            setup.choose()
        importer.assert_not_called()
        self.assertTrue(self.alive(setup))
        self.assertFalse(setup.importing)

    def test_successful_import_closes_setup_remembers_the_image_and_allows_launch(self):
        setup = self.make()
        _picker, importer = self.run_import(setup, self.image)
        importer.assert_called_once_with(str(self.image), self.project, ANY, task=setup.task, steps=ANY)
        self.assertTrue(setup.completed)
        self.assertFalse(self.alive(setup))
        self.remember.assert_called_once_with(game_image=str(self.image.resolve()))

    def test_import_error_keeps_setup_open_explains_it_and_allows_retry(self):
        for error, title in ((ValueError("Wrong game"), 'The import stopped unexpectedly.'),
                             (OSError(28, 'No space left on device'), 'There is not enough free disk space.'),
                             (ImportFailed('pc_only', 'No HFS\nDetails: log', 'log'),
                              'This disc has no Macintosh part.')):
            with self.subTest(error=error):
                setup = self.make()
                self.run_import(setup, self.image, error)
                self.assertFalse(setup.completed)
                self.assertEqual(setup.status.get(), str(error))
                self.assertEqual(setup.problem_title.get(), title)
                self.assertTrue(setup.problem_frame.winfo_manager())
                self.assertFalse(setup.progress_frame.winfo_manager())
                self.assertTrue(setup.import_button.instate(['!disabled']))
                self.assertTrue(self.alive(setup))
                self.remember.assert_not_called()

    def test_retryable_problem_offers_the_same_image_and_others_the_remembered_one(self):
        other = self.project / 'other.iso'
        other.write_bytes(b'cd')
        setup = self.make(remembered=str(self.image))
        setup.show_problem('no_space', str(other))
        self.assertEqual(setup.offered, other)
        self.assertEqual(setup.same_button.cget('text'), 'Try again')
        setup.show_problem('pc_only', str(other))
        self.assertEqual(setup.offered, self.image)
        self.assertEqual(setup.same_button.cget('text'), 'Use this image')
        # The remembered image itself turned out unusable: nothing to offer.
        setup.show_problem('pc_only', str(self.image))
        self.assertIsNone(setup.offered)
        self.assertFalse(setup.same_button.winfo_manager())
        self.assertEqual(setup.import_button.cget('text'), 'Choose game image...')

    def test_failures_from_the_import_link_its_log_and_a_report(self):
        log = self.project / 'rendered' / 'setup.log'
        log.parent.mkdir()
        log.write_text('recovery output')
        setup = self.make()
        self.run_import(setup, self.image, ImportFailed('failed', 'Asset extraction failed: Invalid demo\n'
                                                        f'Details: {log}', log))
        self.assertTrue(setup.log_button.winfo_manager())
        self.assertTrue(setup.report_button.winfo_manager())
        self.assertEqual(setup.problem_detail.get(), 'Invalid demo')
        with patch.object(setup_game, 'open_file') as opened:
            setup.log_button.invoke()
        opened.assert_called_once_with(log)
        # A file rejected before any import ran has no log of its own.
        setup.show_problem('archive', str(self.image))
        self.assertFalse(setup.help_buttons.winfo_manager())
        self.assertEqual(setup.problem_detail.get(), '')

    def test_unusable_file_is_explained_without_starting_an_import(self):
        setup = self.make()
        with (patch.object(setup_game, 'preflight', return_value='archive'),
              patch.object(setup_game.filedialog, 'askopenfilename', return_value=str(self.image)),
              patch.object(setup_game, 'Thread') as thread):
            setup.choose()
        thread.assert_not_called()
        self.assertFalse(setup.importing)
        self.assertEqual(setup.problem_title.get(), 'This file is an archive.')

    def test_cd_iso_and_exported_dmg_can_be_selected_and_imported_directly(self):
        for image in ("CD Collection.iso", "CD Collection.dmg"):
            with self.subTest(image=image):
                setup = self.make()
                picker, importer = self.run_import(setup, image)
                patterns = picker.call_args.kwargs['filetypes'][0][1].split()
                self.assertIn('*' + Path(image).suffix, patterns)
                importer.assert_called_once_with(image, self.project, ANY, task=setup.task, steps=ANY)
                self.assertTrue(setup.completed)
                self.assertFalse(self.alive(setup))

    def test_first_import_and_refresh_say_why_the_window_opened(self):
        setup = self.make(['Prince.rsrc'])
        self.assertEqual(setup.heading.get(), 'Choose your original game image')
        self.assertFalse(setup.refresh)
        (self.project / 'assets').mkdir()
        (self.project / 'assets' / 'Prince.rsrc').write_bytes(b'old import')
        setup = self.make(['ruins_level7.json (needs full level-seven scenery)', 'audio/cue-40.wav'])
        self.assertEqual(setup.heading.get(), 'Your game files need refreshing')
        self.assertIn('the level scenery (level 7) and the audio', setup.intro.get())
        self.assertIn('saved games and settings are kept', setup.intro.get())

    def test_remembered_image_is_offered_and_imported_without_the_picker(self):
        setup = self.make(remembered=str(self.image))
        self.assertEqual(setup.offered, self.image)
        self.assertEqual(setup.offer_name.get(), 'game.hfs')
        self.assertTrue(setup.offer_frame.winfo_manager())
        with (patch.object(setup_game.filedialog, 'askopenfilename') as picker,
              patch.object(setup_game, 'Thread') as thread):
            setup.same_button.invoke()
        picker.assert_not_called()
        thread.assert_called_once_with(target=setup_game.import_files,
                                       args=(self.image, self.project, setup.task, setup.messages), daemon=True)
        self.assertTrue(setup.importing)
        self.assertTrue(setup.progress_frame.winfo_manager())
        self.assertTrue(setup.same_button.instate(['disabled']))
        # The picker starts in the remembered image's folder.
        setup.importing = False
        with patch.object(setup_game.filedialog, 'askopenfilename', return_value='') as picker:
            setup.choose()
        self.assertEqual(picker.call_args.kwargs['initialdir'], str(self.project))

    def test_a_remembered_image_that_is_gone_is_not_offered(self):
        setup = self.make(remembered=str(self.project / 'moved.hfs'))
        self.assertIsNone(setup.offered)
        self.assertFalse(setup.offer_frame.winfo_manager())
        self.assertEqual(setup.import_button.cget('text'), 'Choose game image...')

    def test_stages_drive_the_list_and_a_determinate_progress_bar(self):
        setup = self.make()
        with patch.object(setup_game, 'Thread'):
            setup.start(str(self.image))
        self.assertEqual(setup.stage_state('image'), 'running')
        self.assertEqual(setup.stage_state('scenery'), 'pending')
        for step in (('image', 1, 1), ('scenery', 500, 1000), ('music', 70, 70), ('scenes', 3, 10)):
            setup.messages.put(('step', step))
        setup.started_at -= 10
        setup.poll_import()
        self.assertEqual(setup.stage_state('image'), 'done')
        self.assertEqual(setup.stage_state('scenery'), 'running')
        mark, _name, detail = setup.rows['scenery']
        self.assertEqual((mark.cget('text'), detail.cget('text')), ('●', '50%'))
        self.assertEqual(setup.rows['music'][0].cget('text'), '✓')
        self.assertAlmostEqual(setup.overall(), 3 + 35 + 8 + 3.6)
        self.assertGreater(float(setup.progressbar.cget('value')), 0)
        self.assertLessEqual(float(setup.progressbar.cget('value')), setup.overall())
        self.assertRegex(setup.elapsed.get(), r'^0:1\d elapsed · about \d+ seconds left$')
        for key, *_rest in setup_game.STAGES:
            setup.stages[key] = (1, 1)
        self.assertEqual(setup.overall(), 100)

    def test_time_left_is_rounded_for_reading(self):
        self.assertEqual(setup_game.time_left(4), 'a few seconds left')
        self.assertEqual(setup_game.time_left(21), 'about 25 seconds left')
        self.assertEqual(setup_game.time_left(150), 'about 2 minutes left')

    def test_enter_on_cancel_closes_without_opening_a_file_picker(self):
        setup = self.make()
        with (patch.object(setup.root, 'focus_get', return_value=setup.cancel_button),
              patch.object(setup, "choose") as choose):
            setup.activate(None)
        choose.assert_not_called()
        self.assertFalse(self.alive(setup))

    def test_enter_activates_the_default_choice_unless_busy(self):
        setup = self.make()
        with (patch.object(setup.root, 'focus_get', return_value=None),
              patch.object(setup, "choose") as choose):
            setup.activate(None)
            choose.assert_called_once()
            choose.reset_mock()
            setup.import_button.state(['disabled'])
            setup.activate(None)
            choose.assert_not_called()
        setup = self.make(remembered=str(self.image))
        with (patch.object(setup.root, 'focus_get', return_value=setup.same_button),
              patch.object(setup, 'use_offered') as use, patch.object(setup, 'choose') as choose):
            setup.activate(None)
        use.assert_called_once()
        choose.assert_not_called()

    def test_closed_setup_is_not_marked_complete(self):
        setup = self.make()
        setup.close()
        self.assertFalse(setup.completed)
        self.assertFalse(self.alive(setup))

    def test_progress_keeps_the_ui_responsive_during_import(self):
        setup = self.make()
        setup.importing = True
        setup.messages.put(("progress", "Preparing music: RoofA (3/70)"))
        with patch.object(setup.root, 'after') as after:
            setup.poll_import()
        self.assertEqual(setup.status.get(), "Preparing music: RoofA (3/70)")
        after.assert_called_once_with(50, setup.poll_import)
        self.assertTrue(setup.importing)

    def test_close_cancels_the_process_and_waits_for_staging_cleanup(self):
        setup = self.make()
        with patch.object(setup_game, 'Thread'):
            setup.start(str(self.image))
        with patch.object(setup.task, 'cancel') as cancel:
            setup.close()
        cancel.assert_called_once()
        self.assertTrue(self.alive(setup))
        self.assertTrue(setup.closing)
        self.assertTrue(setup.cancel_button.instate(['disabled']))
        setup.messages.put(('progress', 'Late progress'))
        setup.messages.put(('cancelled', ''))
        setup.poll_import()
        self.assertEqual(setup.status.get(), 'Canceling import...')
        self.assertFalse(self.alive(setup))
        self.assertFalse(setup.completed)

    def test_worker_cancellation_is_not_reported_as_an_import_error(self):
        setup = self.make()
        with patch.object(setup_game, 'import_game', side_effect=setup_game.ImportCancelled):
            setup_game.import_files('game.hfs', self.project, None, setup.messages)
        self.assertEqual(setup.messages.get_nowait(), ('cancelled', ''))

    def test_busy_setup_keeps_cancel_available_and_does_not_set_a_permanent_wait_cursor(self):
        setup = self.make()
        with patch.object(setup_game, 'Thread'):
            setup.start(str(self.image))
        self.assertTrue(setup.cancel_button.instate(['!disabled']))
        self.assertEqual(str(setup.root.cget('cursor')), '')
        self.assertTrue(setup.import_button.instate(['disabled']))


if __name__ == "__main__":
    unittest.main()
