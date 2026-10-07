"""Prepare a local Python environment and launch the port."""

from pathlib import Path
import subprocess
import sys


PROJECT = Path(__file__).resolve().parent
DEPENDENCY_CHECK = (
    "from importlib.metadata import version; from PIL import Image; import tkinter; "
    "import pygame.mixer, mido, numpy; "
    "v=tuple(int(p) for p in version('Pillow').split('.')[:2]); "
    "assert (10, 4) <= v < (13, 0); assert hasattr(Image, 'Resampling')"
)


def prepare_environment(project):
    project = Path(project)
    python = project / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        print("Preparing a local Python environment...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(project / ".venv")], check=True)
    result = subprocess.run(
        [str(python), "-c", DEPENDENCY_CHECK],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        print("Installing dependencies (internet access required)...", flush=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(project / "requirements.txt")],
            check=True,
        )
    return python


def main(argv=None):
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required. Download it from https://www.python.org/.")
        return 1
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("Python needs Tcl/Tk support. Enable it in the Python installer.")
        return 1
    try:
        python = prepare_environment(PROJECT)
        return subprocess.call(
            [str(python), str(PROJECT / "run_game.py"),
             *(sys.argv[1:] if argv is None else argv)],
            cwd=PROJECT,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}")
        print("Check internet access and that this folder is writable, then try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
