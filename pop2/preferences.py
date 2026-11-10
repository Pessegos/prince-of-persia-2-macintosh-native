"""Menu choices the player expects to find as they left them."""

from dataclasses import MISSING, asdict, dataclass, field, fields, replace
import json
from pathlib import Path

from pop2.paths import USER_DATA_DIR

PREFERENCES_PATH = (USER_DATA_DIR if USER_DATA_DIR is not None else
                    Path.home() / 'Saved Games' / 'PoP2 Macintosh Native') / 'preferences.json'


@dataclass(frozen=True)
class Preferences:
    cave_ambience: bool = False
    copy_protection: bool = True
    fullscreen: bool = False
    # Port-only Controls page; an empty table means the default keys/buttons.
    keyboard_bindings: dict = field(default_factory=dict)
    controller_bindings: dict = field(default_factory=dict)
    controller_enabled: bool = True


def load_preferences():
    """What was chosen last time. A missing or damaged file means the defaults."""
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return Preferences()
    if not isinstance(data, dict):
        return Preferences()
    def default(item):
        return item.default_factory() if item.default is MISSING else item.default

    kept = {item.name: data[item.name] for item in fields(Preferences)
            if isinstance(data.get(item.name), type(default(item)))}
    return Preferences(**kept)


def remember(**choices):
    """Keep a change. The game carries on if the disk will not take it."""
    preferences = replace(load_preferences(), **choices)
    temporary = PREFERENCES_PATH.with_suffix('.tmp')
    try:
        PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(asdict(preferences), indent=2) + '\n', encoding='utf-8')
        temporary.replace(PREFERENCES_PATH)
    except OSError:
        pass
