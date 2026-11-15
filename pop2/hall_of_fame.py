"""The Hall of Fame: the five best times left when Jaffar falls.

Recovered from CODE 2 (HallOfFameDialog 2:1f2c, InitHallOfFame 2:275c,
HOFAddPlayer 2:260c, GetHallOfFameName 2:2220, ShowHallOfFame 2:28c2):

- The table holds at most five entries (2:27ec-27f0, 2:26fc). Each is a
  Pascal name and a word: the minutes still left on the clock (a5-0x4fce,
  counted down by KeepTime), so a higher number is better.
- A new score goes before the first entry it equals or beats (2:2674-26aa).
  When the table is full a score below all five still takes fifth place
  (2:2706-270c).
- The name is typed into the new row; '<', '>' and NUL are refused and a
  name stays below 24 characters (2:2416-245e). Return asks whether this
  is the name to insert (2:235e-237e); an empty name is not written
  (2:254c-2560, 2:1f88).

The port keeps the table as JSON beside the player's saves instead of the
Macintosh Hall of Fame file (2:29de, creator 'PRNc').
"""

from dataclasses import dataclass, field
import json
from pathlib import Path

from pop2.paths import USER_DATA_DIR


HALL_PATH = (USER_DATA_DIR if USER_DATA_DIR is not None else
             Path.home() / 'Saved Games' / 'PoP2 Macintosh Native') / 'hall_of_fame.json'
MAX_ENTRIES = 5
NAME_LIMIT = 23
REFUSED = frozenset('<>\0')


@dataclass(frozen=True)
class Entry:
    name: str
    minutes: int


def load_hall(path=None):
    """The saved table, or an empty one when it is missing or unreadable."""
    path = Path(path or HALL_PATH)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    rows = data.get('entries') if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) > MAX_ENTRIES:
        # InitHallOfFame 2:27e8-27f8 discards a table with a bad count.
        return []
    entries = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('name'), str)
                or not isinstance(row.get('minutes'), int) or isinstance(row.get('minutes'), bool)):
            return []
        entries.append(Entry(clean_name(row['name']), row['minutes']))
    return entries


def save_hall(entries, path=None):
    path = Path(path or HALL_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {'schema': 1, 'entries': [{'name': entry.name, 'minutes': entry.minutes}
                                         for entry in entries[:MAX_ENTRIES]]}
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def clean_name(name):
    return ''.join(char for char in name if char not in REFUSED and char.isprintable())[:NAME_LIMIT]


def add_player(entries, minutes):
    """HOFAddPlayer 2:260c: (new table, row of the new, unnamed entry)."""
    entries = list(entries)
    position = 0
    while position < len(entries) and minutes < entries[position].minutes:
        position += 1
    if len(entries) >= MAX_ENTRIES:
        position = min(position, MAX_ENTRIES - 1)
        entries = entries[:MAX_ENTRIES - 1]
    entries.insert(position, Entry('', minutes))
    return entries, position


@dataclass
class HallOfFamePage:
    """The menu page. `position` is the row being named after a victory."""
    entries: list = field(default_factory=list)
    position: int | None = None
    draft: str = ''
    caret: int = 0
    confirming: bool = False
    focus: int = 1          # confirmation buttons: 0 No, 1 Yes
    saved: bool = False

    @classmethod
    def after_victory(cls, minutes, path=None):
        entries, position = add_player(load_hall(path), minutes)
        return cls(entries, position)

    @property
    def editing(self):
        return self.position is not None and not self.confirming and not self.saved

    def rows(self):
        """(name, minutes, being named) for each row on show."""
        return [(self.draft if index == self.position and not self.saved else entry.name,
                 entry.minutes, index == self.position and not self.saved)
                for index, entry in enumerate(self.entries)]

    def edit_text(self, key, char=''):
        if key in ('Left', 'Right', 'Home', 'End'):
            self.caret = (0 if key == 'Home' else len(self.draft) if key == 'End' else
                          max(0, self.caret - 1) if key == 'Left' else min(len(self.draft), self.caret + 1))
            return
        if key == 'BackSpace':
            if self.caret:
                self.draft = self.draft[:self.caret - 1] + self.draft[self.caret:]
                self.caret -= 1
            return
        if key == 'Delete':
            self.draft = self.draft[:self.caret] + self.draft[self.caret + 1:]
            return
        for char in clean_name(char):
            if len(self.draft) >= NAME_LIMIT:
                break
            self.draft = self.draft[:self.caret] + char + self.draft[self.caret:]
            self.caret += 1

    def key(self, key, char=''):
        """'changed', 'hall_saved' (write the table) or 'hall_close'."""
        if self.saved or self.position is None:
            return 'hall_close' if key in ('Escape', 'Return', 'KP_Enter', 'space') else 'changed'
        if self.confirming:
            if key in ('Left', 'Right', 'Tab', 'Up', 'Down'):
                self.focus = 1 - self.focus
            elif key == 'Escape':
                self.confirming = False
            elif key in ('Return', 'KP_Enter', 'space'):
                return self.activate()
            return 'changed'
        if key == 'Escape':
            # Port choice: leave without a name, as an empty name does.
            return 'hall_close'
        if key in ('Return', 'KP_Enter'):
            if not self.draft.strip():
                return 'hall_close'
            self.confirming, self.focus = True, 1
            return 'changed'
        self.edit_text(key, char)
        return 'changed'

    def activate(self):
        if not self.confirming:
            return self.key('Return')
        self.confirming = False
        if self.focus == 0:
            return 'changed'
        name = clean_name(self.draft.strip())
        self.entries[self.position] = Entry(name, self.entries[self.position].minutes)
        self.saved = True
        return 'hall_saved'

    def table(self):
        """The entries to write, without an unnamed row."""
        return [entry for entry in self.entries if entry.name]
