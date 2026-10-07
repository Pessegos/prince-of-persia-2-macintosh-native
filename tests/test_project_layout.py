from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import bootstrap
from pop2.paths import ASSET_DIR, OUTPUT_DIR, PROJECT_DIR
import run_game
from tools import extract_assets, extract_enemy_profiles, recovery_catalog


class ProjectLayoutTests(unittest.TestCase):
    def test_launchers_and_tools_use_the_same_project_root(self):
        self.assertEqual(PROJECT_DIR, Path(__file__).resolve().parent.parent)
        self.assertEqual(bootstrap.PROJECT, PROJECT_DIR)
        self.assertEqual(run_game.PROJECT, PROJECT_DIR)
        self.assertEqual(ASSET_DIR, PROJECT_DIR / "assets")
        self.assertEqual(OUTPUT_DIR, PROJECT_DIR / "rendered")
        self.assertEqual(extract_assets.ASSET_DIR, ASSET_DIR)
        self.assertEqual(extract_enemy_profiles.ASSET_DIR, ASSET_DIR)
        self.assertEqual(recovery_catalog.CATALOG, PROJECT_DIR / "docs" / "RECOVERY_CATALOG.csv")

    def test_tools_run_as_modules_without_importing_gameplay(self):
        for module in ("tools.extract_assets", "tools.extract_enemy_profiles", "tools.recovery_catalog"):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-m", module, "--help"],
                    cwd=PROJECT_DIR, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_launcher_dependency_check_works_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(PROJECT_DIR / "run_game.py"), "--check-dependencies"],
                cwd=directory, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Dependencies are present.", result.stdout)

    def test_catalog_owner_paths_exist_in_the_new_layout(self):
        for row in recovery_catalog.catalog_rows():
            for owner in filter(None, row["prototype_owner"].split(";")):
                with self.subTest(owner=owner):
                    self.assertTrue((PROJECT_DIR / owner).is_file())

    def test_death_and_column_rules_import_without_original_game_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(PROJECT_DIR / "pop2", project / "pop2",
                            ignore=shutil.ignore_patterns("__pycache__"))
            script = (
                "import sys; sys.path.insert(0, '.'); "
                "from pop2.rebirth import Checkpoint, DeathState; "
                "from pop2.opponent_generation import character_column; "
                "assert DeathState().counter == -1; "
                "assert character_column(51) == 0; "
                "assert Checkpoint(1, 0, 0).matches(0, 0, 51, 0, True)"
            )
            result = subprocess.run([sys.executable, "-I", "-c", script],
                                    cwd=project, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((project / "assets").exists())


if __name__ == "__main__":
    unittest.main()
