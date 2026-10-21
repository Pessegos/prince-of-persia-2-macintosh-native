from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import run_game
from tests.test_attract import fixture
from tools.extract_audio import CAVERN_SONGS


PREPARED_CUES = tuple(map(str, (10019, 24, 32, 46, 47, 48, 49, 50, 297, *CAVERN_SONGS)))


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
        self.credit_cue = {"file": "credits-10019.wav"}
        (assets / "audio" / "credits-10019.wav").touch()
        (assets / "audio" / "manifest.json").write_text(json.dumps({
            "schema": 1, "cues": dict.fromkeys(
                PREPARED_CUES, self.credit_cue)}))
        (assets / "intro.json").write_text(json.dumps({
            "schema": 1, "audio": {}, "operations": [{"op": "wait", "args": [1]}],
        }))
        (assets / "attract.json").write_text(json.dumps(fixture()))
        (assets / "ending.json").write_bytes((assets / "intro.json").read_bytes())
        (assets / 'discovery.json').write_bytes((assets / 'intro.json').read_bytes())
        (assets / 'caverns_entry.json').write_text(json.dumps({
            'version': 15, 'level': 3, 'rooms': {str(room): [] for room in range(32)},
            'pressure_plates': {'schema': 1, 'rooms': {str(room): [] for room in range(32)}}}))
        (assets / 'caverns_level4.json').write_text(json.dumps({
            'version': 15, 'level': 4, 'rooms': {str(room): [] for room in range(32)},
            'pressure_plates': {'schema': 1, 'rooms': {str(room): [] for room in range(32)}}}))

    def test_complete_installation_has_no_errors(self):
        self.assertEqual(run_game.installation_errors(self.project), [])

    def test_level_four_scenery_cannot_reuse_the_level_three_export(self):
        assets = self.project / 'assets'
        (assets / 'caverns_level4.json').write_bytes((assets / 'caverns_entry.json').read_bytes())
        self.assertIn('caverns_level4.json (needs full level-four scenery)',
                      run_game.missing_assets(self.project))

    def test_missing_level_four_scenery_requests_import(self):
        (self.project / 'assets/caverns_level4.json').unlink()
        self.assertIn('caverns_level4.json', run_game.missing_assets(self.project))

    def test_exports_without_room_link_setup_request_reimport_for_both_levels(self):
        for name, label in (('caverns_entry.json', 'three'), ('caverns_level4.json', 'four')):
            path = self.project / 'assets' / name
            program = json.loads(path.read_text())
            program['version'] = 14
            path.write_text(json.dumps(program))
            self.assertIn(f'{name} (needs full level-{label} scenery)', run_game.missing_assets(self.project))

    def test_missing_asset_is_named_in_the_error(self):
        (self.project / "assets" / "Kid.rsrc").unlink()
        errors = run_game.installation_errors(self.project)
        self.assertIn("Kid.rsrc", "\n".join(errors))

    def test_missing_prepared_audio_and_corrupt_manifest_request_reimport(self):
        manifest = self.project / "assets" / "audio" / "manifest.json"
        manifest.write_text(json.dumps({"schema": 1, "cues": {
            "40": {"file": "cue-40.wav"}, **dict.fromkeys(
                PREPARED_CUES, self.credit_cue)}}))
        self.assertEqual(run_game.missing_assets(self.project), ["audio/cue-40.wav"])
        manifest.write_text("invalid json")
        self.assertIn("needs reimport", " ".join(run_game.missing_assets(self.project)))

    def test_old_installation_requests_demo_import(self):
        (self.project / "assets" / "attract.json").unlink()
        self.assertIn("attract.json", run_game.missing_assets(self.project))

    def test_corrupt_demo_requests_reimport(self):
        (self.project / "assets" / "attract.json").write_text("{}")
        self.assertIn("attract.json (needs reimport)", run_game.missing_assets(self.project))

    def test_old_installation_requests_voyage_import(self):
        (self.project / "assets" / "ending.json").unlink()
        self.assertIn("ending.json", run_game.missing_assets(self.project))

    def test_entrance_only_cavern_export_requests_full_level_reimport(self):
        (self.project / 'assets/caverns_entry.json').write_text(json.dumps({
            'version': 1, 'level': 3, 'room': 0, 'commands': []}))
        self.assertIn('caverns_entry.json (needs full level-three scenery)',
                      run_game.missing_assets(self.project))

    def test_old_full_cavern_export_without_shape_libraries_requests_reimport(self):
        (self.project / 'assets/caverns_entry.json').write_text(json.dumps({
            'version': 2, 'level': 3, 'rooms': {str(room): [] for room in range(32)}}))
        self.assertIn('caverns_entry.json (needs full level-three scenery)',
                      run_game.missing_assets(self.project))

    def test_cell_clipped_cavern_export_requests_clean_cut_reimport(self):
        (self.project / 'assets/caverns_entry.json').write_text(json.dumps({
            'version': 4, 'level': 3, 'rooms': {str(room): [] for room in range(32)}}))
        self.assertIn('caverns_entry.json (needs full level-three scenery)',
                      run_game.missing_assets(self.project))

    def test_missing_desert_music_requests_reimport(self):
        path = self.project / "assets/audio/manifest.json"
        manifest = json.loads(path.read_text())
        for cue in (46, 47, 48, 49, 50):
            with self.subTest(cue=cue):
                incomplete = {**manifest, "cues": {**manifest["cues"], str(cue): {}}}
                path.write_text(json.dumps(incomplete))
                self.assertIn("audio/manifest.json (needs desert music)",
                              run_game.missing_assets(self.project))

    def test_missing_exit_door_music_requests_reimport(self):
        path = self.project / 'assets/audio/manifest.json'
        manifest = json.loads(path.read_text())
        del manifest['cues']['297']
        path.write_text(json.dumps(manifest))
        self.assertIn('audio/manifest.json (needs exit-door music)',
                      run_game.missing_assets(self.project))

    def test_missing_potion_music_requests_reimport(self):
        path = self.project / 'assets/audio/manifest.json'
        manifest = json.loads(path.read_text())
        del manifest['cues']['24']
        path.write_text(json.dumps(manifest))
        self.assertIn('audio/manifest.json (needs potion music)',
                      run_game.missing_assets(self.project))

    def test_cavern_export_without_native_upper_border_requests_reimport(self):
        (self.project / 'assets/caverns_entry.json').write_text(json.dumps({
            'version': 9, 'level': 3, 'rooms': {str(room): [] for room in range(32)}}))
        self.assertIn('caverns_entry.json (needs full level-three scenery)',
                      run_game.missing_assets(self.project))

    def test_cavern_export_without_pressure_bindings_requests_reimport(self):
        for version in (11, 12, 13):
            with self.subTest(version=version):
                (self.project / 'assets/caverns_entry.json').write_text(json.dumps({
                    'version': version, 'level': 3, 'rooms': {str(room): [] for room in range(32)}}))
                self.assertIn('caverns_entry.json (needs full level-three scenery)',
                              run_game.missing_assets(self.project))

    def test_old_pressure_export_without_animated_shooters_requests_reimport(self):
        path = self.project / 'assets/caverns_entry.json'
        data = json.loads(path.read_text())
        data['version'] = 13
        path.write_text(json.dumps(data))
        self.assertIn('caverns_entry.json (needs full level-three scenery)',
                      run_game.missing_assets(self.project))

    def test_corrupt_voyage_requests_reimport(self):
        (self.project / "assets" / "ending.json").write_text("{}")
        self.assertIn("ending.json (needs reimport)", run_game.missing_assets(self.project))

    def test_discovery_checks_banked_audio_and_missing_prepared_files(self):
        assets = self.project / 'assets'
        path = assets / 'discovery.json'
        scene = json.loads(path.read_text())
        scene['audio'] = {'scene-0-29100': {}, 'scene-1-29100': {}}
        path.write_text(json.dumps(scene))
        self.assertIn('discovery.json (needs reimport)', run_game.missing_assets(self.project))
        manifest_path = assets / 'audio/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['scene_cues'] = {key: {'file': f'{key}.wav'} for key in scene['audio']}
        manifest_path.write_text(json.dumps(manifest))
        for key in scene['audio']:
            (assets / 'audio' / f'{key}.wav').touch()
        self.assertEqual(run_game.missing_assets(self.project), [])
        (assets / 'audio/scene-1-29100.wav').unlink()
        self.assertIn('audio/scene-1-29100.wav', run_game.missing_assets(self.project))
        path.unlink()
        self.assertIn('discovery.json', run_game.missing_assets(self.project))

    def test_missing_credits_music_requests_reimport(self):
        (self.project / "assets" / "audio" / "manifest.json").write_text(json.dumps({"schema": 1, "cues": {}}))
        self.assertIn("attract.json (needs reimport)", run_game.missing_assets(self.project))

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
