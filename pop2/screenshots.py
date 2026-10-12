"""Clean viewport PNGs and local capture preferences."""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from PIL import Image

from pop2.game_ui import VISIBLE_SIZE, VISIBLE_VIEWPORT
from pop2.paths import OUTPUT_DIR


SETTINGS_PATH = OUTPUT_DIR / "screenshot-settings.json"


@dataclass
class ScreenshotSettings:
    folder: Path = OUTPUT_DIR / "screenshots"
    scale: int = 3

    @classmethod
    def load(cls, path=SETTINGS_PATH):
        settings = cls()
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return settings
            folder = data.get("folder")
            if isinstance(folder, str) and folder and Path(folder).is_absolute():
                settings.folder = Path(folder)
            scale = data.get("scale")
            if type(scale) is int and 1 <= scale <= 4:
                settings.scale = scale
        except (OSError, ValueError):
            pass
        return settings

    def save(self, path=SETTINGS_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"folder": str(self.folder.resolve()),
                                         "scale": self.scale}, indent=2), encoding="utf-8")
        temporary.replace(path)


def save_screenshot(viewport, settings):
    if viewport.size != (512, 384):
        raise ValueError("Screenshot requires the native composition buffer")
    if type(settings.scale) is not int or not 1 <= settings.scale <= 4:
        raise ValueError("Screenshot scale must be between 1 and 4")
    image = viewport.crop(VISIBLE_VIEWPORT).convert("RGB")
    if settings.scale != 1:
        image = image.resize(tuple(value * settings.scale for value in VISIBLE_SIZE),
                             Image.Resampling.NEAREST)
    folder = Path(settings.folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    stem = "pop2_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    for index in range(1000):
        path = folder / (stem + (f"_{index}" if index else "") + ".png")
        try:
            stream = path.open("xb")
        except FileExistsError:
            continue
        try:
            with stream:
                image.save(stream, format="PNG")
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path
    raise OSError("Could not create a unique screenshot filename")
