"""Local project directories, independent of the working directory."""

import os
from pathlib import Path
import sys


PROJECT_DIR = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
               else Path(__file__).resolve().parent.parent)
ASSET_DIR = PROJECT_DIR / "assets"
OUTPUT_DIR = PROJECT_DIR / "rendered"
# POP2_USER_DATA redirects the player's saves and screenshot preferences (the
# test suite sets it so tests never touch the real ones).
USER_DATA_DIR = Path(os.environ["POP2_USER_DATA"]) if os.environ.get("POP2_USER_DATA") else None
