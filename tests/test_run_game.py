from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import run_game


class InstallationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        assets = self.project / "assets"
        assets.mkdir()
        for name in run_game.REQUIRED_ASSETS:
            (assets / name).parent.mkdir(parents=True, exist_ok=True)
            (assets / name).touch()
        (assets / "audio" / "manifest.json").write_text(json.dumps({"schema": 1, "cues": {}}))
        (assets / "intro.json").write_text(json.dumps({
            "schema": 1, "audio": {}, "operations": [{"op": "wait", "args": [1]}],
        }))

    def test_complete_installation_has_no_errors(self):
        self.assertEqual(run_game.installation_errors(self.project), [])

    def test_missing_asset_is_named_in_the_error(self):
        (self.project / "assets" / "Kid.rsrc").unlink()
        errors = run_game.installation_errors(self.project)
        self.assertIn("Kid.rsrc", "\n".join(errors))

    def test_missing_prepared_audio_and_corrupt_manifest_request_reimport(self):
        manifest = self.project / "assets" / "audio" / "manifest.json"
        manifest.write_text(json.dumps({"schema": 1, "cues": {"40": {"file": "cue-40.wav"}}}))
        self.assertEqual(run_game.missing_assets(self.project), ["audio/cue-40.wav"])
        manifest.write_text("invalid json")
        self.assertIn("needs reimport", " ".join(run_game.missing_assets(self.project)))

    def test_old_python_is_rejected_before_opening_a_window(self):
        with patch.object(run_game.sys, "version_info", (3, 9)):
            self.assertIn(
                "Python 3.10", "\n".join(run_game.installation_errors(self.project))
            )

    def test_check_mode_does_not_create_a_game_window(self):
        with (
            patch.object(run_game, "installation_errors", return_value=[]),
            patch.object(run_game, "launch_game") as launch,
            patch("builtins.print"),
        ):
            run_game.main(["--check"])
        launch.assert_not_called()

    def test_installation_error_returns_a_nonzero_exit_code(self):
        with (
            patch.object(
                run_game, "dependency_errors", return_value=["Missing Pillow"]
            ),
            patch.object(run_game.sys, "stderr"),
            self.assertRaises(SystemExit) as error,
        ):
            run_game.main([])
        self.assertEqual(error.exception.code, 1)

    def test_missing_pillow_reports_the_current_interpreter(self):
        with patch.dict("sys.modules", {"PIL": None}):
            errors = run_game.installation_errors(self.project)
        self.assertIn(run_game.sys.executable, "\n".join(errors))
        self.assertIn("requirements.txt", "\n".join(errors))

    def test_missing_tk_reports_the_windows_installer_option(self):
        with patch.object(run_game, "import_module", side_effect=ImportError):
            errors = run_game.installation_errors(self.project)
        self.assertIn("Tcl/Tk", "\n".join(errors))

    def test_missing_ai_data_can_be_regenerated_from_the_image(self):
        (self.project / "assets" / "enemy_profiles.json").unlink()
        errors = "\n".join(run_game.installation_errors(self.project))
        self.assertIn("enemy_profiles.json", errors)
        self.assertIn("tools.extract_assets", errors)

    def test_peaceful_option_is_passed_to_the_scene(self):
        with (
            patch.object(run_game, "dependency_errors", return_value=[]),
            patch.object(run_game, "installation_errors", return_value=[]),
            patch.object(run_game, "missing_assets", return_value=[]),
            patch.object(run_game, "launch_game") as launch,
        ):
            run_game.main(["--peaceful"])
        launch.assert_called_once_with(True)

    def test_missing_assets_open_setup_before_launching(self):
        with (
            patch.object(run_game, "dependency_errors", return_value=[]),
            patch.object(run_game, "installation_errors", return_value=[]),
            patch.object(run_game, "missing_assets", return_value=["Kid.rsrc"]),
            patch.object(run_game, "setup_game", return_value=True) as setup,
            patch.object(run_game, "launch_game") as launch,
        ):
            run_game.main([])
        setup.assert_called_once_with(run_game.PROJECT)
        launch.assert_called_once_with(False)

    def test_cancelled_setup_does_not_launch_or_exit_with_an_error(self):
        with (
            patch.object(run_game, "dependency_errors", return_value=[]),
            patch.object(run_game, "missing_assets", return_value=["Kid.rsrc"]),
            patch.object(run_game, "setup_game", return_value=False),
            patch.object(run_game, "launch_game") as launch,
        ):
            run_game.main([])
        launch.assert_not_called()

    def test_check_mode_reports_missing_assets_without_opening_setup(self):
        with (
            patch.object(run_game, "installation_errors", return_value=["Missing game files"]),
            patch.object(run_game, "setup_game") as setup,
            patch.object(run_game.sys, "stderr"),
            self.assertRaises(SystemExit) as error,
        ):
            run_game.main(["--check"])
        self.assertEqual(error.exception.code, 1)
        setup.assert_not_called()

    def test_dependency_check_does_not_require_assets_or_open_windows(self):
        with (
            patch.object(run_game, "dependency_errors", return_value=[]),
            patch.object(run_game, "installation_errors") as installation,
            patch.object(run_game, "setup_game") as setup,
            patch("builtins.print"),
        ):
            run_game.main(["--check-dependencies"])
        installation.assert_not_called()
        setup.assert_not_called()

    def test_setup_must_produce_a_complete_installation_before_launch(self):
        with (
            patch.object(run_game, "dependency_errors", return_value=[]),
            patch.object(run_game, "missing_assets", return_value=["Kid.rsrc"]),
            patch.object(run_game, "setup_game", return_value=True),
            patch.object(run_game, "installation_errors", return_value=["Missing Kid.rsrc"]),
            patch.object(run_game, "launch_game") as launch,
            patch.object(run_game.sys, "stderr"),
            self.assertRaises(SystemExit),
        ):
            run_game.main([])
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
