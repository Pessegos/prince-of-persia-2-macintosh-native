"""Local project directories, independent of the working directory."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
ASSET_DIR = PROJECT_DIR / "assets"
OUTPUT_DIR = PROJECT_DIR / "rendered"
