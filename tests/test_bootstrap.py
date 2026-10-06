from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import call, patch

import bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name) / "Game folder & files"
        self.project.mkdir()
        self.python = self.project / ".venv" / "Scripts" / "python.exe"

    def existing_environment(self):
        self.python.parent.mkdir(parents=True)
        self.python.touch()

    def test_existing_ready_environment_does_not_create_or_install_anything(self):
        self.existing_environment()
        with patch.object(bootstrap.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(bootstrap.prepare_environment(self.project), self.python)
        run.assert_called_once_with(
            [str(self.python), "-c", bootstrap.DEPENDENCY_CHECK],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def test_missing_environment_is_created_with_the_current_python(self):
        with (
            patch.object(bootstrap.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run,
            patch("builtins.print"),
        ):
            bootstrap.prepare_environment(self.project)
        self.assertEqual(run.call_args_list[0], call(
            [bootstrap.sys.executable, "-m", "venv", str(self.project / ".venv")], check=True,
        ))
        self.assertEqual(run.call_count, 2)

    def test_missing_dependencies_install_only_in_the_local_environment(self):
        self.existing_environment()
        with (
            patch.object(bootstrap.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as run,
            patch("builtins.print"),
        ):
            bootstrap.prepare_environment(self.project)
        self.assertEqual(run.call_args_list[-1], call(
            [str(self.python), "-m", "pip", "install", "-r", str(self.project / "requirements.txt")],
            check=True,
        ))
        self.assertEqual(run.call_count, 2)

    def test_launcher_propagates_arguments_and_exit_status(self):
        with (
            patch.object(bootstrap, "prepare_environment", return_value=self.python),
            patch.object(bootstrap.subprocess, "call", return_value=7) as launch,
        ):
            self.assertEqual(bootstrap.main(["--peaceful"]), 7)
        launch.assert_called_once_with(
            [str(self.python), str(bootstrap.PROJECT / "run_game.py"), "--peaceful"],
            cwd=bootstrap.PROJECT,
        )

    def test_failed_installation_does_not_launch_the_game(self):
        with (
            patch.object(bootstrap, "prepare_environment",
                         side_effect=subprocess.CalledProcessError(1, ["pip"])),
            patch.object(bootstrap.subprocess, "call") as launch,
            patch("builtins.print"),
        ):
            self.assertEqual(bootstrap.main([]), 1)
        launch.assert_not_called()

    def test_old_python_is_rejected_before_creating_an_environment(self):
        with (
            patch.object(bootstrap.sys, "version_info", (3, 9)),
            patch.object(bootstrap, "prepare_environment") as prepare,
            patch("builtins.print"),
        ):
            self.assertEqual(bootstrap.main([]), 1)
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
