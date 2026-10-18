"""Development navigation derived from the imported scene and demo programs."""

from dataclasses import dataclass


# Developer labels for the original TEXT:27000 entries, not official scene titles.
OPENING_TITLES = (
    'Ancient Persia', 'The Sultan', 'The Princess', 'The Sultan Leaves',
    'A Foreign War', 'Secret Romance', 'The Palace Wall', "Jaffar's Ambition",
    'A Rival Suitor', 'The Dungeon', 'Jaffar Defeated', 'Treachery Revealed',
    "The Sultan's Reward", 'One Wish', 'The Wedding', 'Eleven Days Later',
    'One Morning', 'The Throne Room', 'A Passing Shadow', 'Before the Throne',
    'The Court Watches', 'Unfamiliar Faces', 'The Prince Speaks', 'An Intruder',
    'Seize Him!', 'A Plea for Mercy', 'A Mad Beggar', 'The Chase',
    'False Reassurance', "He Won't Get Far",
)


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
    labels = [label for label in groups if label != 'Extras']
    if 'Extras' in groups:
        labels.append('Extras')
    return tuple(PlaybackGroup(label, tuple(groups[label])) for label in labels)


def playback_parts(intro_program, attract_data, screen_label):
    parts = []
    story = 0
    for index, item in enumerate(intro_program["operations"]):
        if item["op"] == "title":
            parts.append(PlaybackPart('Titles', 'intro', index, 'Opening'))
        elif item["op"] == "text" and item["args"][1]:
            story += 1
            resource, entry = item['args'][:2]
            label = (OPENING_TITLES[entry - 1] if resource == 27000 and 1 <= entry <= len(OPENING_TITLES)
                     else f'Scene {story}')
            parts.append(PlaybackPart(label, 'intro', index, 'Opening'))
    seen = set()
    for index, frame in enumerate(attract_data["frames"]):
        room = frame["room"] - 1
        if room not in seen:
            parts.append(PlaybackPart(f'Demo - Screen {screen_label(room)}', 'demo', index, 'Extras'))
            seen.add(room)
    for index in range(len(attract_data["credits"]["pages"])):
        parts.append(PlaybackPart(f'Credits - Page {index + 1}', 'credits', index, 'Extras'))
    return tuple(parts)


def ending_parts(program):
    parts = [PlaybackPart('Departure', 'ending', 0, 'After Level 1')]
    names = {28002: "Stowaway", 28004: "Dream", 28008: "Storm"}
    for index, item in enumerate(program["operations"]):
        if item["op"] == "palette" and item["args"][0] in names:
            parts.append(PlaybackPart(names[item["args"][0]], "ending", index,
                                      "After Level 1"))
            names.pop(item["args"][0])
    parts.append(PlaybackPart('Arrival', 'level', 2, 'After Level 1'))
    return tuple(parts)
