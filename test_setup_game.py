from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import setup_game


class GameSetupTests(unittest.TestCase):
    def setUp(self):
        self.setup = setup_game.GameSetup.__new__(setup_game.GameSetup)
        self.setup.project = Path("test-project")
        self.setup.root = Mock()
        self.setup.status = Mock()
        self.setup.import_button = Mock()
        self.setup.cancel_button = Mock()
        self.setup.completed = False

    def test_import_uses_the_selected_project_directory(self):
        with patch.object(setup_game, "extract_assets") as extract:
            setup_game.import_game("game.hfs", self.setup.project)
        extract.assert_called_once_with("game.hfs", self.setup.project / "assets")

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
        ):
            self.setup.choose()
        importer.assert_called_once_with("game.hfs", self.setup.project)
        self.assertTrue(self.setup.completed)
        self.setup.root.destroy.assert_called_once()

    def test_import_error_keeps_setup_open_and_allows_retry(self):
        for error in (ValueError("Wrong game"), OSError("Disk full")):
            with (
                self.subTest(error=error),
                patch.object(setup_game.filedialog, "askopenfilename", return_value="game.hfs"),
                patch.object(setup_game, "import_game", side_effect=error),
            ):
                self.setup.choose()
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


if __name__ == "__main__":
    unittest.main()
