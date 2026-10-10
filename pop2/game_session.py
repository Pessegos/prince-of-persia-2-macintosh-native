"""Window-independent level loading and mutable gameplay state."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pop2.animation_data import parse_aframe_records, parse_frame_records, sequence_words
from pop2.control_mapping import IDLE_SEQUENCE
from pop2.harbor import Harbor
from pop2.level_data import LevelDefinition
from pop2.level_transition import LevelExit
from pop2.opening_animation import GLASS_POSITIONS, OpeningEscape
from pop2.rebirth import DeathState, RebirthSnapshot
from pop2.render_opening import load_resource_file
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion

if TYPE_CHECKING:
    from pop2.combat import CombatEncounter


@dataclass(frozen=True)
class GameResources:
    prince: dict
    kid: dict
    sequences: dict
    frames: tuple
    attachment_frames: tuple
    first_shape_id: int

    @classmethod
    def load(cls):
        prince = load_resource_file("Prince.rsrc")
        kid = load_resource_file("Kid.rsrc")
        return cls(prince, kid,
                   {key: sequence_words(value["data"]) for key, value in prince["SEQS"].items()},
                   parse_frame_records(kid["FRAM"][25001]["data"]),
                   parse_aframe_records(kid["AFRM"][25001]["data"]),
                   int.from_bytes(kid["SHPL"][25001]["data"][:2], "big"))

    def level(self, number):
        return LevelDefinition.read(self.prince, number)


@dataclass
class GameSession:
    level: LevelDefinition | None = None
    runtime: SequenceRuntime | None = None
    level_map: LevelMap | None = None
    physics: RooftopPhysics | None = None
    motion: TerrainMotion | None = None
    combat: "CombatEncounter | None" = None
    opening: OpeningEscape | None = None
    harbor: Harbor | None = None
    room_id: int = 0
    checkpoint: RebirthSnapshot | None = None
    death: DeathState = field(default_factory=DeathState)
    complete: bool = False
    exit: LevelExit | None = None

    @property
    def entry_active(self):
        return (self.level is not None and self.runtime is not None and self.level.kind == 1
                and self.runtime.state.sequence_id == self.level.entry_sequence)

    @classmethod
    def load(cls, resources, number=1, terrain_enabled=True, encounter_factory=None):
        level = resources.level(number)
        # Validate entry support before constructing any mutable world state.
        level.entry_sequence
        state = SequenceState(IDLE_SEQUENCE, action=15, current_x=level.start_x,
                              target_x=level.start_x, facing=level.facing,
                              actor_type=0, level_kind=level.kind)
        runtime = SequenceRuntime(resources.sequences, state)
        terrain = LevelMap(level.data) if terrain_enabled else None
        combat = None
        if terrain_enabled:
            if encounter_factory is None:
                from pop2.combat import CombatEncounter

                encounter_factory = CombatEncounter
            combat = encounter_factory(runtime, resources.sequences, None,
                                       level.right_platform_edge(), level=level.data)
        session = cls(level, runtime, terrain,
                      RooftopPhysics(terrain, resources.frames) if terrain is not None else None,
                      combat=combat)
        if combat is not None:
            combat.terrain = terrain
            combat.player_frames = resources.frames
        session.restart()
        return session

    def restart(self):
        level, state = self.level, self.runtime.state
        self.checkpoint = None
        self.death = DeathState()
        self.complete = False
        self.exit = None
        self.room_id = level.start_room
        self.harbor = Harbor() if level.kind == 5 else None
        fresh = SequenceState(IDLE_SEQUENCE, action=15, current_x=level.start_x,
                              target_x=level.start_x, facing=level.facing,
                              actor_type=0, level_kind=level.kind)
        state.__dict__.update(fresh.__dict__)
        if self.combat is not None:
            self.combat.reset()
            self.motion = TerrainMotion(self.room_id, level.start_row)
            self.combat.player.terrain_motion = self.motion
            self.combat.player.room, self.combat.player.row = self.room_id, level.start_row
        if level.window_escape:
            self.opening = OpeningEscape(self.runtime, level.start_tile)
        else:
            self.opening = None
            state.select(level.entry_sequence)
            self.runtime.next_frame()

    def place(self, room, row, x, facing, reset_guards=True, preserve_checkpoint=False):
        if (self.level_map is None or not 0 <= room < 32 or not 0 <= row < 3
                or not 0 <= x < 510 or facing not in (0, 1)):
            raise ValueError("Invalid level, room or standing position")
        self.death = DeathState()
        if not preserve_checkpoint:
            self.checkpoint = None
        self.harbor = Harbor() if self.level.kind == 5 else None
        self.complete = False
        self.exit = None
        if self.opening is not None:
            self.opening.active = False
            self.opening.tick = len(GLASS_POSITIONS)
            self.opening.phase = "done"
        state = self.runtime.state
        fresh = SequenceState(IDLE_SEQUENCE, action=15, current_x=x, target_x=x,
                              facing=facing, actor_type=0, level_kind=self.level.kind)
        state.__dict__.update(fresh.__dict__)
        self.room_id = room
        self.motion = TerrainMotion(room, row)
        if reset_guards:
            self.combat.reset()
        self.combat.player.terrain_motion = self.motion
        self.combat.enter_room(room, row)
        if self.harbor is not None:
            self.harbor.enter_room(room, 15)
        self.combat.player.life = self.combat.player.max_life
        self.combat.player.sword_drawn = False
        self.combat.player.targetable = True
        self.combat.player.recovering = False

    def consume_completion(self):
        event = (-16, ())
        if self.complete or self.runtime is None or event not in self.runtime.state.sequence_events:
            return False
        self.runtime.state.sequence_events.remove(event)
        self.complete = True
        return True
