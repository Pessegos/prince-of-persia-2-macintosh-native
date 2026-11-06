"""The genie of level twelve's flask, opponent set 9 (Jinnee.rsrc).

The one flask of type 6 in the game, 23:24, gives no potion. 4:46b2 plays sound
12 and selects SEQS 111, whose -14 event 3 calls TriggerJinnee 4:1d7e: a cloud
85 pixels ahead of the Prince, from which a tiny Prince runs out to the right.
He is actor type 12, the only one that ignores a gate (4:6046, 6:3190), and
CheckPress 5:127e treats him as anyone else. So he passes under gate 23:28,
which has no link, and treads on plate 23:29 behind it. 4:1d64 removes him
outside columns -1..10. See docs/research/temple-jinnee.md.
"""

from dataclasses import dataclass
from types import SimpleNamespace

from pop2.opponent_generation import character_column
from pop2.potions import FLASK_KIND, PROMPT_SOUND, RELEASE_EVENT  # noqa: F401
from pop2.sequence_runtime import SequenceState
from pop2.terrain import TerrainMotion, floor_contact_x

ACTOR_TYPE = 12
PRINCE_SEQUENCE = 111
SEQUENCE = 180
SONG = 244
REACH = 85                # 4:1da8: DATA -4b98 by facing, times 85
FIRST_POSE = 149          # LoadFrame's opponent base, as for the guards
SHAPE_LIST = 750
# FRAM 750's flags for the running poses: 0x40 is a foot on the floor, the low
# six bits its offset. They are rules, so they stay without the artwork.
RUNNING_FLAGS = {163: 70, 164: 66, 165: 69, 166: 71}


@dataclass
class Jinnee:
    state: SequenceState
    motion: TerrainMotion

    @classmethod
    def released(cls, kid, motion):
        """4:1e48-1eb4: the Kid's row and room, facing left whichever way the
        Kid faces, and X 85 pixels ahead of the Kid."""
        x = kid.target_x + (REACH if kid.facing else -REACH)
        state = SequenceState(SEQUENCE, action=kid.action, current_x=x, target_x=x, facing=0,
                              actor_type=ACTOR_TYPE, level_kind=kid.level_kind)
        return cls(state, TerrainMotion(motion.room, motion.row))

    @property
    def record(self):
        return SimpleNamespace(offset_x=0, aux=RUNNING_FLAGS.get(self.state.action, 0))

    @property
    def column(self):
        return character_column(floor_contact_x(self.state.target_x, self.state.facing, self.record))

    @property
    def gone(self):
        # 4:1d64: the column outside -1..10.
        return not -1 <= self.column <= 10
