"""Validate the local installation and launch the rooftop prototype."""

import argparse
from importlib import import_module
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parent
REQUIRED_ASSETS = (
    "Prince.rsrc",
    "Kid.rsrc",
    "Guard.rsrc",
    "Rooftops.rsrc",
    "enemy_profiles.json",
)


def dependency_errors(project=PROJECT):
    errors = []
    install_command = f'"{sys.executable}" -m pip install -r "{project / "requirements.txt"}"'
    if sys.version_info < (3, 10):
        errors.append("Python 3.10 or newer is required.")
    try:
        from PIL import Image

        if not hasattr(Image, "Resampling"):
            errors.append(f"Update Pillow: {install_command}")
    except ImportError:
        errors.append(f"Install Pillow: {install_command}")
    try:
        import_module("tkinter")
    except ImportError:
        errors.append(
            "Python needs Tk support. On Windows, include Tcl/Tk in the Python installer."
        )
    return errors


def missing_assets(project=PROJECT):
    return [
        name for name in REQUIRED_ASSETS if not (project / "assets" / name).is_file()
    ]


def installation_errors(project=PROJECT):
    errors = dependency_errors(project)
    missing = missing_assets(project)
    if missing:
        errors.append("Missing files in assets/: " + ", ".join(missing))
        errors.append(
            "Run Launch.cmd to import the game files, or use: "
            "python -m tools.extract_assets PATH_TO_IMAGE.hfs"
        )
    return errors


def launch_game(peaceful):
    from pop2.scene_prototype import ScenePrototype

    ScenePrototype(peaceful=peaceful).run()


def setup_game(project):
    from pop2.setup_game import setup_game as import_game_files

    return import_game_files(project)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--peaceful", action="store_true", help="Disable guards for terrain testing"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check dependencies and asset files without opening a window",
    )
    parser.add_argument(
        "--check-dependencies", action="store_true",
        help="Check Python dependencies without requiring original game files",
    )
    args = parser.parse_args(argv)
    errors = installation_errors() if args.check else dependency_errors()
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    if args.check or args.check_dependencies:
        print("Dependencies are present." if args.check_dependencies
              else "Dependencies and asset files are present.")
        return
    if missing_assets() and not setup_game(PROJECT):
        return
    errors = installation_errors()
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    launch_game(args.peaceful)


if __name__ == "__main__":
    main()
