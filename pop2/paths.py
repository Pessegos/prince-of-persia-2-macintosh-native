"""Local project directories, independent of the working directory."""

import os
from pathlib import Path
import sys


CODE_DIR = Path(__file__).resolve().parent.parent
# The signed interpreter runs ordinary source modules under _internal/worker.
# Its build marker fixes paths without inheriting PYTHONPATH or a user setting.
BUNDLED_WORKER = (CODE_DIR / 'portable-worker.json').is_file()
BUNDLED = bool(getattr(sys, 'frozen', False) or BUNDLED_WORKER)
PROJECT_DIR = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
               else CODE_DIR.parent.parent if BUNDLED_WORKER else CODE_DIR)
ASSET_DIR = PROJECT_DIR / "assets"
OUTPUT_DIR = PROJECT_DIR / "rendered"
# POP2_USER_DATA redirects the player's saves and screenshot preferences (the
# test suite sets it so tests never touch the real ones).
USER_DATA_DIR = Path(os.environ["POP2_USER_DATA"]) if os.environ.get("POP2_USER_DATA") else None
