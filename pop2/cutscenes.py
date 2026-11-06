"""Player-facing story chapters and a collection independent of campaign saves."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile

from pop2.paths import ASSET_DIR, USER_DATA_DIR


@dataclass(frozen=True)
class CutsceneChapter:
    key: str
    title: str
    program: str
    preview_seconds: float = 6
    after_level: int | None = None


# Complete story programs, with the long opening split at natural boundaries.
# Demo gameplay, credits and
# the recurring tree reminders are deliberately outside the story collection.
CHAPTERS = (
    CutsceneChapter('opening', 'Prologue', 'intro.json', 5),
    CutsceneChapter('opening_titles', 'Title', 'intro.json', 6),
    CutsceneChapter('opening_story', 'The Palace Escape', 'intro.json', 8),
    CutsceneChapter('voyage', 'The Voyage', 'ending.json', 5, 1),
    CutsceneChapter('discovery', 'The Impostor', 'discovery.json', 10, 3),
    CutsceneChapter('carpet', 'The Flying Carpet', 'carpet.json', 5, 5),
    CutsceneChapter('vision', "The Father's Vision", 'throne.json', 20, 8),
    CutsceneChapter('horse', 'The Ride to the Temple', 'temple.json', 5, 9),
    CutsceneChapter('tower', 'The Flight to the Tower', 'tower.json', 6, 13),
)
OPENING_KEYS = frozenset(('opening', 'opening_titles', 'opening_story'))
CHAPTER_KEYS = frozenset(chapter.key for chapter in CHAPTERS)
COLLECTION_PATH = (USER_DATA_DIR if USER_DATA_DIR is not None else
                   Path.home() / 'Saved Games' / 'PoP2 Macintosh Native') / 'cutscenes.json'


def ordered_seen(keys):
    """Story unlocks form a chronological prefix, never isolated debug scenes."""
    seen = set(OPENING_KEYS)
    for chapter in CHAPTERS:
        if chapter.key in OPENING_KEYS:
            continue
        if chapter.key not in keys:
            break
        seen.add(chapter.key)
    return seen


@dataclass
class CutsceneCollection:
    path: Path = COLLECTION_PATH
    seen: set = field(default_factory=lambda: set(OPENING_KEYS))
    error: str = ''

    @classmethod
    def load(cls, path=COLLECTION_PATH):
        collection = cls(Path(path))
        try:
            if collection.path.stat().st_size > 16384:
                return collection
            data = json.loads(collection.path.read_text(encoding='utf-8'))
            if (isinstance(data, dict) and data.get('version') == 1
                    and isinstance(data.get('seen'), list)
                    and all(isinstance(key, str) for key in data['seen'])):
                collection.seen = ordered_seen(CHAPTER_KEYS.intersection(data['seen']))
        except (OSError, ValueError):
            pass
        return collection

    def unlock(self, *keys):
        # A second game instance may have recorded preceding chapters since
        # this one opened. Only merge valid, ordered progress from disk.
        self.seen = ordered_seen(self.seen | self.load(self.path).seen)
        admitted = ordered_seen(self.seen | CHAPTER_KEYS.intersection(keys))
        if admitted == self.seen:
            return
        self.seen = admitted
        self.save()

    def save(self):
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve chapters another instance may have recorded meanwhile.
            self.seen = ordered_seen(self.seen | self.load(self.path).seen)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.cutscenes-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({'version': 1, 'seen': sorted(self.seen)}, stream)
                stream.write('\n')
            temporary.replace(self.path)
            self.error = ''
        except OSError:
            self.error = 'Could not remember unlocked chapters.'
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def admit_saved_progress(self, game):
        """Earlier mandatory scenes in an older save have already been reached.

        This is called only after loading a validated campaign save, never for
        developer room/level jumps or a gallery replay.
        """
        level = game.level.number
        keys = [chapter.key for chapter in CHAPTERS
                if chapter.after_level is not None and level > chapter.after_level]
        if level == 8 and (getattr(game.caverns, 'throne_seen', False)
                           or getattr(game.caverns, 'throne_done', False)):
            keys.append('vision')
        self.unlock(*keys)


def chapter_available(chapter, directory=ASSET_DIR):
    return (Path(directory) / chapter.program).is_file()


def chapter_range(chapter, program):
    """Half-open boundaries from the imported title and story setup operations."""
    if chapter.program != 'intro.json':
        return 0, None
    operations = program['operations']
    title = next(i for i, operation in enumerate(operations) if operation['op'] == 'title')
    setup = next(i for i in range(title + 1, len(operations)) if operations[i]['op'] == 'fill')
    narration = next(i for i in range(setup, len(operations))
                     if operations[i]['op'] == 'text' and operations[i]['args'][1])
    music = next(i for i in range(narration - 1, setup - 1, -1)
                 if operations[i]['op'] == 'sound' and operations[i]['args'][1] == 0)
    # The setup between these chapters waits for the preceding title's music
    # over an empty frame. Reconstruct it silently; start the story with its
    # own song and reveal, retaining all narration and subsequent animation.
    return {'opening': (0, title), 'opening_titles': (title, setup),
            'opening_story': (music, None)}[chapter.key]
