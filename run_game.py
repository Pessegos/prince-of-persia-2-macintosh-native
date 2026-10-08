"""Validate the local installation and launch the rooftop prototype."""

import argparse
from importlib import import_module
import json
import os
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parent
REQUIRED_ASSETS = (
    "Prince.rsrc",
    "Kid.rsrc",
    "Guard.rsrc",
    "Rooftops.rsrc",
    "NIS.rsrc",
    "Title.rsrc",
    "intro.json",
    "enemy_profiles.json",
    "audio/manifest.json",
)


def dependency_errors(project=PROJECT):
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
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
    for name in ("pygame.mixer", "mido", "numpy", "unicorn"):
        try:
            import_module(name)
        except ImportError:
            errors.append(f"Install game dependencies: {install_command}")
            break
    return errors


def missing_assets(project=PROJECT):
    missing = [
        name for name in REQUIRED_ASSETS if not (project / "assets" / name).is_file()
    ]
    manifest_path = project / "assets" / "audio" / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="ascii"))
            if manifest["schema"] != 1 or not isinstance(manifest["cues"], dict):
                raise ValueError("Unsupported audio schema")
            for item in manifest["cues"].values():
                if item.get("file") and not (manifest_path.parent / item["file"]).is_file():
                    missing.append("audio/" + item["file"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            missing.append("audio/manifest.json (needs reimport)")
    intro_path = project / "assets" / "intro.json"
    if intro_path.is_file():
        from pop2.intro import read_program

        try:
            intro = read_program(intro_path)
            if manifest_path.is_file():
                cues = json.loads(manifest_path.read_text(encoding="ascii"))["cues"]
                if any(not cues.get(key, {}).get("file") for key in intro["audio"]):
                    raise ValueError("Intro audio is incomplete")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            missing.append("intro.json (needs reimport)")
    return missing


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
    from pop2.audio import AudioEngine
    from pop2.scene_prototype import ScenePrototype

    audio = AudioEngine()
    try:
        ScenePrototype(peaceful=peaceful, audio=audio, with_intro=True).run()
    finally:
        audio.close()


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
    try:
        launch_game(args.peaceful)
    except RuntimeError as error:
        parser.exit(1, f"Could not start the game: {error}\n")


if __name__ == "__main__":
    main()
