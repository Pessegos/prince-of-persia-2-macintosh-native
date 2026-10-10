"""Development navigation derived from the imported scene and demo programs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaybackPart:
    label: str
    stage: str
    index: int
    group: str = ""


@dataclass(frozen=True)
class PlaybackGroup:
    label: str
    part_indices: tuple


def playback_groups(parts):
    groups = {}
    for index, part in enumerate(parts):
        label = part.group or part.stage.title()
        groups.setdefault(label, []).append(index)
    return tuple(PlaybackGroup(label, tuple(indices)) for label, indices in groups.items())


def playback_parts(intro_assets, attract_data, screen_label):
    parts = []
    story = 0
    group = "Prologue"
    for index, item in enumerate(intro_assets.program["operations"]):
        if item["op"] == "title":
            parts.append(PlaybackPart("Clouds / titles", "intro", index, "Titles"))
            group = "Opening story"
            story = 0
        elif item["op"] == "text" and item["args"][1]:
            story += 1
            parts.append(PlaybackPart(f"Story {story}", "intro", index, group))
    seen = set()
    for index, frame in enumerate(attract_data["frames"]):
        room = frame["room"] - 1
        if room not in seen:
            parts.append(PlaybackPart(f"Demo: screen {screen_label(room)}", "demo", index,
                                      "Level 1 demo"))
            seen.add(room)
    for index in range(len(attract_data["credits"]["pages"])):
        parts.append(PlaybackPart(f"Credits: page {index + 1}", "credits", index, "Credits"))
    return tuple(parts)


def ending_parts(assets):
    parts = [PlaybackPart("Voyage: departure", "ending", 0, "After Level 1")]
    names = {28002: "Stowaway", 28004: "Dream", 28008: "Storm"}
    for index, item in enumerate(assets.program["operations"]):
        if item["op"] == "palette" and item["args"][0] in names:
            parts.append(PlaybackPart("Voyage: " + names[item["args"][0]], "ending", index,
                                      "After Level 1"))
            names.pop(item["args"][0])
    parts.append(PlaybackPart("Level 2: arrival", "level", 2, "After Level 1"))
    return tuple(parts)
