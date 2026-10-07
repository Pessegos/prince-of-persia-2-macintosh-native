from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import ANY, Mock, patch

import pop2.setup_game as setup_game


class GameSetupTests(unittest.TestCase):
    def setUp(self):
        self.setup = setup_game.GameSetup.__new__(setup_game.GameSetup)
        self.setup.project = Path("test-project")
        self.setup.root = Mock()
        self.setup.status = Mock()
        self.setup.import_button = Mock()
        self.setup.cancel_button = Mock()
        self.setup.completed = False
        self.setup.importing = False
        self.setup.messages = Queue()

    def test_import_uses_the_selected_project_directory(self):
        with patch.object(setup_game, "extract_assets") as extract:
            setup_game.import_game("game.hfs", self.setup.project)
        extract.assert_called_once_with("game.hfs", self.setup.project / "assets", ANY)

    def test_cancelled_file_picker_does_not_import_or_close_setup(self):
        with (
            patch.object(setup_game.filedialog, "askopenfilename", return_value=""),
            patch.object(setup_game, "import_game") as importer,
        ):
            self.setup.choose()
        importer.assert_not_called()
        self.setup.root.destroy.assert_not_called()

    def test_successful_import_closes_setup_and_allows_launch(self):
        with (
            patch.object(setup_game.filedialog, "askopenfilename", return_value="game.hfs"),
            patch.object(setup_game, "import_game") as importer,
            patch.object(setup_game, "Thread") as thread,
        ):
            thread.return_value.start.side_effect = lambda: self.setup.import_files("game.hfs")
            self.setup.choose()
            self.setup.poll_import()
        importer.assert_called_once_with("game.hfs", self.setup.project, ANY)
        self.assertTrue(self.setup.completed)
        self.setup.root.destroy.assert_called_once()

    def test_import_error_keeps_setup_open_and_allows_retry(self):
        for error in (ValueError("Wrong game"), OSError("Disk full")):
            with (
                self.subTest(error=error),
                patch.object(setup_game.filedialog, "askopenfilename", return_value="game.hfs"),
                patch.object(setup_game, "import_game", side_effect=error),
                patch.object(setup_game, "Thread") as thread,
            ):
                thread.return_value.start.side_effect = lambda: self.setup.import_files("game.hfs")
                self.setup.choose()
                self.setup.poll_import()
            self.assertFalse(self.setup.completed)
            self.setup.status.set.assert_called_with(str(error))
            self.setup.import_button.state.assert_called_with(["!disabled"])
            self.setup.root.destroy.assert_not_called()

    def test_enter_on_cancel_closes_without_opening_a_file_picker(self):
        self.setup.root.focus_get.return_value = self.setup.cancel_button
        with patch.object(self.setup, "choose") as choose:
            self.setup.activate(None)
        choose.assert_not_called()
        self.setup.root.destroy.assert_called_once()

    def test_enter_on_import_activates_the_file_picker_unless_busy(self):
        self.setup.import_button.instate.return_value = False
        with patch.object(self.setup, "choose") as choose:
            self.setup.activate(None)
        choose.assert_called_once()
        self.setup.import_button.instate.return_value = True
        with patch.object(self.setup, "choose") as choose:
            self.setup.activate(None)
        choose.assert_not_called()

    def test_closed_setup_is_not_marked_complete(self):
        self.setup.close()
        self.assertFalse(self.setup.completed)
        self.assertFalse(self.setup.run())

    def test_progress_and_close_requests_keep_import_worker_safe(self):
        self.setup.importing = True
        self.setup.close()
        self.setup.root.destroy.assert_not_called()
        self.setup.messages.put(("progress", "Preparing music: RoofA"))
        self.setup.poll_import()
        self.setup.status.set.assert_called_with("Preparing music: RoofA")
        self.setup.root.after.assert_called_once_with(50, self.setup.poll_import)
        self.assertTrue(self.setup.importing)


if __name__ == "__main__":
    unittest.main()
