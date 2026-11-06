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


# One complete imported story program per chapter. Demo gameplay, credits and
# the recurring tree reminders are deliberately outside the story collection.
CHAPTERS = (
    CutsceneChapter('opening', 'The Story Begins', 'intro.json'),
    CutsceneChapter('voyage', 'The Voyage', 'ending.json', 5, 1),
    CutsceneChapter('discovery', 'The Impostor', 'discovery.json', 10, 3),
    CutsceneChapter('carpet', 'The Flying Carpet', 'carpet.json', 5, 5),
    CutsceneChapter('vision', "The Father's Vision", 'throne.json', 20, 8),
    CutsceneChapter('horse', 'The Ride to the Temple', 'temple.json', 5, 9),
    CutsceneChapter('tower', 'The Flight to the Tower', 'tower.json', 6, 13),
)
CHAPTER_KEYS = frozenset(chapter.key for chapter in CHAPTERS)
COLLECTION_PATH = (USER_DATA_DIR if USER_DATA_DIR is not None else
                   Path.home() / 'Saved Games' / 'PoP2 Macintosh Native') / 'cutscenes.json'


@dataclass
class CutsceneCollection:
    path: Path = COLLECTION_PATH
    seen: set = field(default_factory=lambda: {'opening'})
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
                collection.seen.update(CHAPTER_KEYS.intersection(data['seen']))
        except (OSError, ValueError):
            pass
        return collection

    def unlock(self, *keys):
        new = CHAPTER_KEYS.intersection(keys) - self.seen
        if not new:
            return
        self.seen.update(new)
        self.save()

    def save(self):
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve chapters another instance may have recorded meanwhile.
            self.seen.update(self.load(self.path).seen)
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
