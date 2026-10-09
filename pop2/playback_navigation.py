"""Development navigation derived from the imported scene and demo programs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaybackPart:
    label: str
    stage: str
    index: int


def playback_parts(intro_assets, attract_data, screen_label):
    parts = []
    story = 0
    for index, item in enumerate(intro_assets.program["operations"]):
        if item["op"] == "title":
            parts.append(PlaybackPart("Clouds / titles", "intro", index))
        elif item["op"] == "text" and item["args"][1]:
            story += 1
            parts.append(PlaybackPart(f"Story {story}", "intro", index))
    seen = set()
    for index, frame in enumerate(attract_data["frames"]):
        room = frame["room"] - 1
        if room not in seen:
            parts.append(PlaybackPart(f"Demo: screen {screen_label(room)}", "demo", index))
            seen.add(room)
    for index in range(len(attract_data["credits"]["pages"])):
        parts.append(PlaybackPart(f"Credits: page {index + 1}", "credits", index))
    return tuple(parts)
