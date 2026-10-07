"""Ordinary-guard combat recovered from Macintosh CODE 4/6."""

from contextlib import contextmanager
from dataclasses import dataclass, replace
import struct

from pop2.enemy_profiles import (
    ADVANCE_CHANCE, BLOCK_CHANCE, PARRY_BLOCK_CHANCE, COUNTER_CHANCE,
    STRIKE_CHANCE, HIT_PAUSE, QuickDrawRandom,
)
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.opponent_generation import (
    OpponentGenerationPoint, character_column, tile_kind,
    WALL_TILES, OBSTACLE_TILES, EMPTY_TILES,
)
from pop2.terrain import RooftopPhysics, TerrainMotion, floor_contact_x, floor_edge_distance, floor_y


GUARD_POSES = {158, 170, 171}
STRIKE_POSES = {153, 154}
BLOCK_POSES = {150, 161}
PLAYER_COMBAT_TURN_SEQUENCE = 127
# CheckStab, CODE:6 0x523e-0x5268; these are sequence IDs, not poses.
FATAL_STAB_SEQUENCES = frozenset((10, 16, 28, 14))

@dataclass(frozen=True)
class GuardSpawn:
    room: int
    row: int
    x: int
    facing: int
    skill: int
    sequence_id: int
    life: int
    palette_variant: int = 1
    generation_flags: int = 0
    alternate_row: int | None = None

    @classmethod
    def from_level(cls, level, room):
        spawns = cls.all_from_level(level, room)
        if len(spawns) != 1:
            raise ValueError("This encounter needs exactly one ordinary guard")
        return spawns[0]

    @classmethod
    def all_from_level(cls, level, room):
        # CODE:6 GetGen/SetOppMaxLifePts: one-based room, 38-byte generator.
        if struct.unpack_from(">H", level, 0x21A4)[0] != 0:
            raise ValueError("Special opponent types are not implemented here")
        offset = 0x20E6 + (room + 1) * 0xC0
        count = struct.unpack_from(">H", level, offset)[0]
        if not 0 <= count <= 5:
            raise ValueError("Invalid initial ordinary-guard count")
        spawns = []
        for index in range(count):
            fields = struct.unpack_from(">19h", level, offset + 2 + index * 38)
            skill = fields[3]
            if not 0 <= skill < len(ADVANCE_CHANCE):
                raise ValueError(f"Unsupported guard skill {skill}")
            spawns.append(cls(room, fields[0] // 10, fields[1] - 207,
                              int(fields[2] == 0), skill, fields[4], fields[13] or 3,
                              fields[6] or 1, fields[10], fields[16]))
        return spawns


@dataclass
class Fighter:
    runtime: SequenceRuntime
    life: int
    max_life: int
    room: int
    row: int
    sword_drawn: bool = False
    targetable: bool = True
    recovering: bool = False
    contact_consumed: bool = False
    alert_mode: int = 0
    skill: int = 0
    entry_x: int | None = None
    selected_sequence: int | None = None
    generation_flags: int = 0
    palette_variant: int = 1
    terrain_motion: TerrainMotion | None = None
    pursuing: bool = False
    alternate_row: int | None = None
    death_registered: bool = False

    @property
    def state(self):
        return self.runtime.state

    @property
    def alive(self):
        return self.life > 0

    @property
    def controls_locked(self):
        return self.recovering or not self.alive


@dataclass(frozen=True)
class CombatEvent:
    kind: str
    actor: str
    death_method: int | None = None


@dataclass(frozen=True)
class GuardIntent:
    advance: bool = False
    retreat: bool = False
    block: bool = False
    strike: bool = False


def opponent_distance(attacker, defender):
    # CODE:4 0x49ee: facing anchor correction, not sprite-box overlap.
    if attacker.room != defender.room or attacker.row != defender.row:
        return 999
    distance = defender.state.target_x - attacker.state.target_x
    if not attacker.state.facing:
        distance = -distance
    if distance >= 0 and attacker.state.facing != defender.state.facing:
        distance += 21
    return distance


def strike_range(attacker, defender):
    # CODE:6 0x5b38, ordinary guards (actor type 2), no special-level actors.
    opposed = attacker.state.facing != defender.state.facing
    if attacker.state.actor_type in (0, 1):
        low, high = 61, 99
        # 0x5c18 tests engagement, unlike the NPC branch's sword-flag test.
        if defender.alert_mode == 0:
            low += 22
            high += 22
            if not opposed:
                low -= 37
                high -= 22
        return low, high
    if opposed:
        return (61 if defender.sword_drawn else 35), 99
    return (45, 85) if defender.sword_drawn else (42, 83)


def contact_allowed(attacker, defender):
    # CODE:6 0x5896: living target, same room/row, vertical difference <15.
    return (
        attacker.alive and defender.alive
        and attacker.sword_drawn
        and attacker.targetable and defender.targetable
        and attacker.room == defender.room and attacker.row == defender.row
        and abs(attacker.state.current_y - defender.state.current_y) < 15
        and defender.state.animation_state != 8
    )


def guard_frame_index(action):
    # CODE:4 0x2b0e, LoadFrame for actor type 2.
    if 102 <= action <= 106:
        return action - 149 + 70
    return action - 149


def select_sequence(fighter, sequence_id, offset=0):
    fighter.selected_sequence = sequence_id
    state = fighter.state
    state.target_x += offset if state.facing else -offset
    state.current_x = state.target_x
    state.sequence_id = sequence_id
    state.cursor = 0


class CombatEncounter:
    def __init__(self, player_runtime, sequences, spawn, platform_edge, rng=None, level=None):
        self.player_runtime = player_runtime
        self.sequences = sequences
        self.spawn = spawn
        self.platform_edge = platform_edge
        self.rng = rng if rng is not None else QuickDrawRandom()
        self.level = level
        self.reset()

    def reset(self):
        self.player = Fighter(self.player_runtime, 3, 3,
                              self.spawn.room, self.spawn.row)
        state = SequenceState(
            sequence_id=self.spawn.sequence_id, current_x=self.spawn.x,
            target_x=self.spawn.x, facing=self.spawn.facing,
            actor_type=2, level_kind=5,
        )
        self.guard = Fighter(SequenceRuntime(self.sequences, state),
                             self.spawn.life, self.spawn.life,
                             self.spawn.room, self.spawn.row, skill=self.spawn.skill,
                             selected_sequence=self.spawn.sequence_id,
                             palette_variant=self.spawn.palette_variant,
                             generation_flags=self.spawn.generation_flags,
                             alternate_row=self.spawn.alternate_row)
        self.guard.runtime.next_frame()
        self.guards = [self.guard]
        self.generation_points = (OpponentGenerationPoint.from_level(self.level, self.spawn.room)
                                  if self.level is not None else [])
        self.world_frame = 0
        self.parry_timer = 0
        self.advance_pause = 0
        self.attack_pause = 0
        self.last_guard_at = None
        self.room_encounters = {self.spawn.room: (self.guards, self.generation_points)}

    def _load_room(self, room):
        if self.level is None:
            raise ValueError("Room changes require LEVL data")
        if room not in self.room_encounters:
            guards = []
            for spawn in GuardSpawn.all_from_level(self.level, room):
                state = SequenceState(spawn.sequence_id, current_x=spawn.x,
                                      target_x=spawn.x, facing=spawn.facing,
                                      actor_type=2, level_kind=5)
                fighter = Fighter(SequenceRuntime(self.sequences, state),
                                  spawn.life, spawn.life, room, spawn.row,
                                  skill=spawn.skill, selected_sequence=spawn.sequence_id,
                                  palette_variant=spawn.palette_variant,
                                  generation_flags=spawn.generation_flags,
                                  alternate_row=spawn.alternate_row)
                fighter.runtime.next_frame()
                guards.append(fighter)
            self.room_encounters[room] = (guards, OpponentGenerationPoint.from_level(self.level, room))

    def enter_room(self, room, row):
        """Keep the Prince and the visited room's NPC/generator objects intact."""
        self._load_room(room)
        self.player.room, self.player.row = room, row
        self.guards, self.generation_points = self.room_encounters[room]
        self.guard = self._nearest_guard() or (self.guards[0] if self.guards else None)

    def active_guards(self):
        terrain = getattr(self, "terrain", None)
        if terrain is None:
            return list(self.guards)
        rooms = {self.player.room}
        rooms.update(terrain.neighbor(self.player.room, direction)
                     for direction in ("left", "right"))
        return [guard for room, (guards, _points) in self.room_encounters.items()
                for guard in guards if room in rooms or guard.alive and guard.pursuing]

    def _room_offset(self, source, destination):
        if source == destination:
            return 0
        terrain = getattr(self, "terrain", None)
        if terrain is not None:
            if terrain.neighbor(destination, "left") == source:
                return -510
            if terrain.neighbor(destination, "right") == source:
                return 510
            pending, visited = [(destination, 0)], {destination}
            for room, offset in pending:
                for direction, delta in (("left", -510), ("right", 510)):
                    neighbor = terrain.neighbor(room, direction)
                    if neighbor == source:
                        return offset + delta
                    if neighbor in self.room_encounters and neighbor not in visited:
                        visited.add(neighbor)
                        pending.append((neighbor, offset + delta))
        return None

    def _project_fighter(self, fighter, room):
        offset = self._room_offset(fighter.room, room)
        if offset is None:
            return None
        if offset == 0:
            return fighter
        state = replace(fighter.state, current_x=fighter.state.current_x + offset,
                        target_x=fighter.state.target_x + offset)
        return replace(fighter, room=room, runtime=SequenceRuntime(self.sequences, state))

    def visible_guards(self):
        return [view for guard in self.active_guards()
                if (view := self._project_fighter(guard, self.player.room)) is not None]

    @contextmanager
    def _local_opponents(self, guard):
        # Side-room actors use a rebased coordinate view, never a teleport or
        # a replacement NPC. Restore the ownership lists even on an error.
        player, guards = self.player, self.guards
        active = self.active_guards()
        try:
            self.player = self._project_fighter(player, guard.room) or player
            self.guards = [view for other in active
                           if (view := self._project_fighter(other, guard.room)) is not None]
            yield
        finally:
            self.player, self.guards = player, guards

    def _chance(self, table, guard=None):
        # Rnd(255) includes 255; even a table entry of 255 can fail.
        return self.rng.randrange(256) < table[(guard or self.guard).skill]

    def notify_player_sequence(self, sequence_id):
        # CODE:6 0x2522/0x25ae: these timers belong to the encounter, not poses.
        if sequence_id in (75, 66):
            self.advance_pause = 15
        elif sequence_id in (92, 93):
            self.attack_pause = 9

    def decide_guard_intent(self, guard=None):
        """EnGarde's ordinary, single-opponent, supported-rooftop branches."""
        guard, player = guard or self.guard, self.player
        state, other = guard.state, player.state
        distance = opponent_distance(guard, player)
        low, high = strike_range(guard, player)
        if state.action < 150 or state.action == 166:
            return GuardIntent()
        if distance >= 39 and 102 <= other.action < 118 and other.animation_state == 5:
            return GuardIntent()
        if distance < low:
            # EnGarde 4:0a82-0b1a: ready pose, front cell first, then the
            # cell behind. DoRetreat itself does not make an edge safe.
            if state.action != 171:
                return GuardIntent()
            if self.level is not None:
                if state.sequence_id not in (57, 104) and self._guard_floor_clear(guard, 1, 1):
                    return GuardIntent(advance=True)
                return GuardIntent(retreat=self._guard_floor_clear(guard, -1, 1))
            return GuardIntent(retreat=True)
        if distance >= high + 18:
            if self.attack_pause:
                return GuardIntent()
            # CODE:4 0x0c2a: attacks against an approaching run or jump need
            # neither a normal in-range check nor a probability-table roll.
            if state.facing != other.facing:
                if (7 <= other.action < 15 and distance < 150
                        or 34 <= other.action < 44 and distance < 186):
                    return GuardIntent(strike=True)
            return self._close_intent(guard)
        if not player.sword_drawn or state.facing == other.facing:
            # InRange 0x048a: an unarmed/back-facing opponent is handled
            # directly, without consulting the normal strike table.
            if self.attack_pause:
                return GuardIntent()
            return GuardIntent(strike=distance < high, advance=distance >= high)
        if distance >= high:
            return self._close_intent(guard)
        # Defence and Strike both write inputs. GenCtrl then gives an attack
        # input priority over block, even if that attack pose cannot execute it.
        block = False
        if other.action in (152, 153, 162):
            table = PARRY_BLOCK_CHANCE if self.parry_timer else BLOCK_CHANCE
            block = self._chance(table, guard)
        strike = False
        if not self.attack_pause and other.action not in (169, 151):
            table = COUNTER_CHANCE if state.action in BLOCK_POSES else STRIKE_CHANCE
            strike = self._chance(table, guard)
        return GuardIntent(block=block, strike=strike)

    def _close_intent(self, guard=None):
        guard = guard or self.guard
        # OpponentClose 0x11a2: profile zero ignores the 15-frame advance pause.
        if guard.skill and self.advance_pause:
            return GuardIntent()
        return GuardIntent(advance=self._chance(ADVANCE_CHANCE, guard))

    def apply_guard_intent(self, intent, guard=None):
        """Original ordinary-NPC DoStrike/DoBlock/DoAdvance/DoRetreat gates."""
        guard = guard or self.guard
        state = guard.state
        if state.animation_state >= 2:
            return
        if intent.strike:
            if state.action in (157, 158, 170, 171, 165):
                select_sequence(guard, 58)
            elif state.action in BLOCK_POSES:
                select_sequence(guard, 66)
            return
        # CODE:6 0x24da: a parried block without a counter cancels into retreat.
        if state.action == 161:
            select_sequence(guard, 57)
            return
        if intent.block:
            if state.action in (158, 170, 171, 168, 165):
                # NPCs retreat at >=74; only pose 152 enables close SEQS:246.
                if opponent_distance(guard, self.player) >= 74:
                    if state.action in GUARD_POSES:
                        select_sequence(guard, 57)
                elif self.player.state.action == 152:
                    select_sequence(guard, 246)
            elif state.action == 167:
                select_sequence(guard, 61)
            return
        if state.action in GUARD_POSES:
            if intent.advance:
                select_sequence(guard, 86)
            elif intent.retreat:
                select_sequence(guard, 57)

    def choose_player_turn(self, frame_record=None):
        player, guard = self.player, self.guard
        state = player.state
        if (guard is None or not player.alive or not guard.alive or player.controls_locked
                or not player.sword_drawn or not player.targetable
                or not guard.targetable or guard.alert_mode < 2
                or state.animation_state >= 2
                or player.room != guard.room or player.row != guard.row):
            return False
        # CODE:6 0x2258-0x22ea: -15..330 stays in ordinary sword control.
        # A farther target behind selects the Prince's turn at 0x2770.
        if opponent_distance(player, guard) >= -15:
            return False
        terrain = getattr(self, "terrain", None)
        offset = (terrain.combat_turn_offset(player.room, player.row, state, frame_record)
                  if terrain is not None and frame_record is not None else 0)
        select_sequence(player, PLAYER_COMBAT_TURN_SEQUENCE, offset=offset)
        return True

    def choose_player_bump(self, old_x=None):
        # FrameAdv 2:6c64-6daa interrupts unarmed overlap with an engaged,
        # opposing, grounded ordinary NPC. Running jumps reserve 63 pixels.
        player, guard = self.player, self.guard
        state = player.state
        if (guard is None or not player.alive or not guard.alive
                or not player.targetable or player.sword_drawn
                or state.actor_type == 1
                or guard.alert_mode < 2 or guard.state.animation_state >= 2
                or player.room != guard.room or player.row != guard.row
                or state.facing == guard.state.facing or state.vertical_velocity >= 59
                or guard.selected_sequence == 110 or player.controls_locked
                or state.sequence_id in (46, 47)):
            return False
        distance = abs(opponent_distance(player, guard))
        if distance > 24 and (state.sequence_id != 4 or distance >= 63):
            if old_x is None or state.sequence_id not in (3, 4):
                return False
            direction = 1 if state.facing else -1
            if (state.target_x - old_x) * direction <= 0:
                return False
            # Native distance adds 21 ahead of an opposing NPC. Preserve
            # that contact interval, but sweep a port frame's displacement:
            # SEQS:3 can advance 49 pixels and skip the whole interval.
            near, far = (41, -62) if state.sequence_id == 4 else (3, -24)
            start = (guard.state.target_x - old_x) * direction
            end = (guard.state.target_x - state.target_x) * direction
            if end > near or start < far:
                return False
            state.target_x = guard.state.target_x - min(near, start) * direction
        state.current_y = 0
        state.horizontal_velocity = state.vertical_velocity = 0
        if 246 <= state.action <= 261:
            state.target_x += -10 if state.facing else 10
        else:
            airborne = (state.action in (24, 25) or 40 <= state.action < 43
                        or 102 <= state.action <= 106)
            select_sequence(player, 46 if airborne else 47)
            player.runtime.next_frame()
            state.target_x += (10 if airborne else -10) * (1 if state.facing else -1)
        state.current_x = state.target_x
        return True

    def choose_guard_action(self, guard=None):
        guard, player = guard or self.guard, self.player
        state = guard.state
        if not guard.alive:
            # 4:3d64-3d6c registers life zero before AnimChar. A newly
            # stabbed actor is not counted in the previous NPC bank yet.
            guard.death_registered = True
            return
        if guard.recovering:
            return
        if self.level is not None and not guard.sword_drawn:
            self._choose_unarmed_guard_action(guard)
            return
        if not player.alive:
            guard.alert_mode = 0
            if state.action in GUARD_POSES and state.animation_state < 2:
                # EnGarde 4:09c0-09e2 -> OnAlert 6:2536-254c ->
                # 6:2592/25ee: lower the sword only at a ready pose.
                guard.sword_drawn = False
                select_sequence(guard, 77)
            return
        if guard.room != player.room or guard.row != player.row:
            return
        if state.action == 166 and state.sequence_id == 77:
            guard.sword_drawn = True
            # CODE:6 0x3ce0-0x3cf2: drawn sword and alert/engaged mode 3.
            guard.alert_mode = 3
            select_sequence(guard, 90)
            return
        if self.level is not None and guard.alert_mode in (1, 2):
            self._choose_waiting_guard_action(guard)
            return
        if guard.alert_mode != 3:
            return
        if not player.targetable:
            return
        if opponent_distance(guard, player) < -15:
            # The combat turn has its own facing opcode; never flip mid-step.
            if state.action == 171 and state.animation_state < 2:
                select_sequence(guard, 60)
            return
        if (self.level is not None and state.action in GUARD_POSES
                and opponent_distance(guard, player) >= strike_range(guard, player)[1]):
            other = player.state
            moving = 1 <= other.action <= 14 or 49 <= other.action <= 56 or 34 <= other.action <= 44
            # CODE:4 0fb8-1056: an eligible pursuer runs after a same-facing
            # moving Kid while the two tiles ahead remain traversable.
            if (guard.generation_flags and moving and state.facing == other.facing
                    and other.animation_state != 7 and self._guard_floor_clear(guard, 1, 2)):
                self._resume_guard_run(guard)
                return
        self.apply_guard_intent(self.decide_guard_intent(guard), guard)

    def _nearest_guard(self, side=None):
        # GetOppIdxClosestToKid 0x36f2: ordinary same-floor candidates.
        candidates = [g for g in self.guards if g.alive and g.room == self.player.room
                      and g.row == self.player.row and (side is None or
                      (g.state.target_x <= self.player.state.target_x if side < 0 else
                       g.state.target_x > self.player.state.target_x))]
        return min(candidates, key=lambda g: abs(g.state.target_x - self.player.state.target_x),
                   default=None)

    def refresh_target(self):
        # Main CODE:2 0x6300-0x633c retains an opposing-facing target;
        # otherwise GetOppIdxClosestToKid supplies the nearest living NPC.
        if (self.guard is None or not self.guard.alive or self.guard.room != self.player.room
                or self.guard.state.facing == self.player.state.facing):
            self.guard = self._nearest_guard() or self.guard

    def update_guard_alerts(self):
        for guard in self.active_guards():
            with self._local_opponents(guard):
                self._update_guard_alert(guard)

    def _update_guard_alert(self, guard):
        # CODE:2 0x6e7e: nearest living enemy on either side can engage (3).
        # Other enemies wait (2); a wall blocks sight, a gap limits pursuit (1).
        primary = (self._nearest_guard(-1), self._nearest_guard(1))
        if (not guard.alive or not self.player.alive or guard.room != self.player.room
                or guard.row != self.player.row
                or self.player.state.action == 0 or 217 <= self.player.state.action < 226
                or self.player.state.actor_type == 1):
            guard.alert_mode = 0
            return
        low, high = sorted((character_column(guard.state.target_x),
                            character_column(self.player.state.target_x)))
        # CODE:2 0x6fce skips the scan for actors in the same column.
        terrain = ([tile_kind(self.level, guard.room, col, self.player.row)
                    for col in range(low, high + 1)] if low < high else [])
        guard.alert_mode = 3
        for kind in terrain:
            if kind in WALL_TILES:
                guard.alert_mode = 0
                break
            if kind in EMPTY_TILES or kind in OBSTACLE_TILES:
                guard.alert_mode = 1
                break
        if guard.alert_mode == 3 and not any(g is guard for g in primary):
            guard.alert_mode = 2
        if guard.alert_mode:
            guard.pursuing = True

    def _choose_unarmed_guard_action(self, guard):
        state, other = guard.state, self.player.state
        if guard.generation_flags >= 1 and state.action in (192, 196):
            self._choose_guard_jump(guard)
            return
        if state.action == 166:
            distance = opponent_distance(guard, self.player)
            # AutoCtrl 0x04fc / GenCtrl 0x4996, supported floor only.
            if distance < -27:
                if guard.alert_mode >= 2:
                    select_sequence(guard, 80)
            elif (distance < 0 and guard.alert_mode >= 2
                  or 0 <= distance <= 663 and guard.alert_mode > 0):
                guard.sword_drawn = True
                select_sequence(guard, 90)
            return
        # CODE:4 057c tests odd running poses and the final jump pose 212.
        if not (194 <= state.action <= 199 and state.action & 1 or state.action == 212):
            return
        # AutoCtrl 4:0674-06d0 runs even when the Kid is on another floor.
        # Losing that floor selects the existing brake, not a frozen run loop.
        if (guard.room != self.player.room
                or self.player.row not in (guard.row, guard.alternate_row)):
            guard.alert_mode = 0
            select_sequence(guard, 101)
            return
        # 4:06da-06e2 skips same-floor spacing while +0x20 permits pursuit
        # on another row; poses 192/196 still select the native gap jump.
        if guard.row != self.player.row:
            return
        distance = abs(state.target_x - other.target_x)
        moving = 1 <= other.action <= 14 or 49 <= other.action <= 56 or 34 <= other.action <= 44
        if moving:
            distance += 51 if state.facing == other.facing else -51
        elif not self.player.sword_drawn:
            distance += 51
        nearest = self._nearest_guard(-1 if state.facing else 1)
        crowd_distance = (127 if nearest is guard else
                          abs(state.target_x - nearest.state.target_x) if nearest else 0)
        same_direction_run = moving and state.facing == other.facing and other.animation_state != 7
        # CODE:4 0x071e-0x0722 bypasses the spacing brake at >=102 while
        # chasing a same-facing run, but still checks passing/death below.
        spacing_brake = (not (same_direction_run and distance >= 102)
                         and (crowd_distance <= 126 or distance <= 178))
        passed_player = (character_column(state.target_x) > character_column(other.target_x)
                         if state.facing else
                         character_column(state.target_x) < character_column(other.target_x))
        if spacing_brake or passed_player or not self.player.alive:
            guard.alert_mode = 2 if self.player.alive else 0
            select_sequence(guard, 101)

    def _choose_guard_jump(self, guard):
        # AutoCtrl 4:0834 and DoRunJump 6:1c14, ordinary rooftop gaps.
        art = getattr(self, "guard_art", None)
        if art is None or not self.player.alive:
            return
        state = guard.state
        record = art.frames[guard_frame_index(state.action)]
        contact = floor_contact_x(state.target_x, state.facing, record)
        column, direction = character_column(contact), 1 if state.facing else -1
        kind = lambda n: self.terrain.tile(guard.room, column + direction * n, guard.row).kind
        if kind(3) not in EMPTY_TILES:
            return
        first = next(n for n in (1, 2, 3) if kind(n) in EMPTY_TILES)
        width = 1
        while width <= 4 and kind(first + width) in EMPTY_TILES:
            width += 1
        allowed = width < 4 or (width == 4 and self.rng.randrange(guard.generation_flags) == 0)
        # 4:093a-0948 permits a wider drop when +0x20 names another row.
        allowed |= guard.alternate_row is not None and guard.alternate_row != guard.row
        if not allowed:
            guard.alert_mode = 2
            select_sequence(guard, 101)
            return
        # Scan the 13-pixel look-ahead anchor; reserve 75 pixels for the NPC
        # takeoff (the Prince's equivalent reserves 48).
        look = state.target_x + 13 * direction
        col = character_column(look)
        clear = 0
        for n in range(1, 3):
            tile = self.terrain.tile(guard.room, col + direction * n, guard.row)
            if tile.kind in EMPTY_TILES | WALL_TILES | OBSTACLE_TILES | {4}:
                break
            clear += 1
        if clear < 2:
            adjustment = floor_edge_distance(look, state.facing) + clear * 51 - 75
            if not -31 <= adjustment < 15:
                adjustment = -13
            state.target_x += (13 + adjustment) * direction
            state.current_x = state.target_x
        select_sequence(guard, 100)

    def _choose_waiting_guard_action(self, guard):
        # WaitingEngarde 0x0c7e, ordinary first-rooftop unobstructed floor.
        front = self._nearest_guard(-1 if guard.state.facing else 1)
        if front is None:
            front = self._nearest_guard()
        if front is None or front is guard:
            return
        distance = abs(front.state.target_x - guard.state.target_x)
        # GenFight 0x0f28 includes later NPC records, even corpses.
        index = next(i for i, g in enumerate(self.guards) if g is guard)
        clearance = 102 + 36 * sum(abs(g.state.target_x - guard.state.target_x) < 36
                                   for g in self.guards[index + 1:])
        close = (distance <= clearance + 24
                 and (front.state.facing != guard.state.facing or front.selected_sequence != 84))
        other = self.player.state
        moving = (1 <= other.action <= 14 or 49 <= other.action <= 56
                  or 34 <= other.action <= 44)
        same_direction_run = (moving and guard.state.facing == other.facing
                              and other.animation_state != 7)
        if close:
            passed_player = (guard.state.target_x < other.target_x if other.facing else
                             guard.state.target_x > other.target_x)
            if (same_direction_run and passed_player and guard.generation_flags
                    and self._guard_floor_clear(guard, 1, 3)):
                self._resume_guard_run(guard)
                return
            if distance < clearance and self._guard_floor_clear(guard, -1, 1):
                self.apply_guard_intent(GuardIntent(retreat=True), guard)
        elif guard.selected_sequence != 84 and self._guard_floor_clear(guard, 1, 3):
            if (guard.generation_flags and (same_direction_run
                    or front.selected_sequence == 84 and front.state.facing == guard.state.facing)):
                self._resume_guard_run(guard)
            else:
                self.apply_guard_intent(GuardIntent(advance=True), guard)

    def _resume_guard_run(self, guard):
        # CODE:4 0x011e does not run across alert-mode-1 obstacles.
        if guard.alert_mode != 1:
            select_sequence(guard, 84)
            guard.sword_drawn = False
            guard.alert_mode = 0

    def _guard_floor_clear(self, guard, direction, count):
        # DoOppInput 6:2c90-2ca0 indexes the anchor before EnGarde/GenCtrl.
        # LoadFrame 4:2a7c updates the supporting-foot cell later, for physics.
        column = character_column(guard.state.target_x)
        step = direction if guard.state.facing else -direction
        # CODE:6 0x5eca, supported flat rooftop (no gate modifiers here).
        return all(tile_kind(self.level, guard.room, column + step * n, guard.row)
                   not in WALL_TILES | OBSTACLE_TILES | EMPTY_TILES | {4}
                   for n in range(1, count + 1))

    def generate_opponents(self):
        # Count living NPCs in the generator's corridor, including offscreen
        # reinforcements that have not entered their owner room or seen Kid yet.
        blockers = list(self.guards)
        blockers.extend(view for guard in self.active_guards()
                        if guard.room != self.player.room and guard.alive
                        and (view := self._project_fighter(guard, self.player.room)) is not None)
        for point in self.generation_points:
            if not point.advance(self.player, blockers, self.world_frame, self.level):
                continue
            armed = abs(point.column - character_column(self.player.state.target_x)) <= 3 and point.life >= 6
            state = SequenceState(90 if armed else 84, current_x=point.x,
                                  target_x=point.x, facing=point.facing,
                                  actor_type=2, level_kind=5)
            guard = Fighter(SequenceRuntime(self.sequences, state), point.life, point.life,
                            point.room, point.row, sword_drawn=armed, skill=point.skill,
                            alert_mode=3 if armed else 0, entry_x=point.x,
                            selected_sequence=state.sequence_id, generation_flags=point.flags,
                            alternate_row=point.alternate_row)
            guard.runtime.next_frame()
            self.guards.append(guard)
            blockers.append(guard)
        self.refresh_target()

    def advance_guard(self):
        self.parry_timer = max(0, self.parry_timer - 1)
        self.advance_pause = max(0, self.advance_pause - 1)
        self.attack_pause = max(0, self.attack_pause - 1)
        for guard in self.active_guards():
            old_x = guard.state.target_x
            art = getattr(self, "guard_art", None)
            old_bounds = art.bounds(guard.state, floor_y(guard.row)) if art is not None else None
            with self._local_opponents(guard):
                self.choose_guard_action(guard)
            guard.runtime.next_frame()
            self._select_guard_corpse_pose(guard)
            # Allow native offscreen entry; each room has its own floor extent.
            entry = guard.entry_x or 0
            low, high = min(0, entry), max(self.platform_edge, entry)
            terrain = getattr(self, "terrain", None)
            if terrain is not None and getattr(self, "guard_art", None) is not None:
                self._advance_guard_terrain(guard, old_x, old_bounds)
            else:
                guard.state.target_x = max(low, min(high, guard.state.target_x))
            guard.state.current_x = guard.state.target_x
            if 0 <= guard.state.target_x < 510:
                guard.entry_x = None
            if guard.recovering and guard.state.sequence_id == 227:
                guard.recovering = False

    def _advance_guard_terrain(self, guard, old_x, old_bounds=None):
        if guard.terrain_motion is None:
            guard.terrain_motion = TerrainMotion(guard.room, guard.row)
        motion = guard.terrain_motion
        motion.room, motion.row = guard.room, guard.row
        old_room = guard.room
        if not hasattr(self, "guard_physics"):
            frames = {action: self.guard_art.frames[guard_frame_index(action)]
                      for action in (*range(149, 255), *range(102, 107))}
            self.guard_physics = RooftopPhysics(self.terrain, frames)
        bounds = lambda: self.guard_art.bounds(guard.state, floor_y(motion.row))
        events = self.guard_physics.advance(
            motion, guard.runtime, old_x, bounds(), sword_drawn=guard.sword_drawn,
            bounds_for_state=bounds, cut_enabled=guard.entry_x is None, alive=guard.alive,
            old_bounds=old_bounds)
        guard.room, guard.row = motion.room, motion.row
        guard.targetable = not motion.falling and not motion.dead
        for event in events:
            if event.kind == "death":
                guard.life = 0
            elif event.kind == "land":
                guard.life = max(0, guard.life - event.damage)
                guard.sword_drawn = True
        if guard.room != old_room:
            # TransferOppInfo keeps the actor's life, palette and sequence.
            self._load_room(guard.room)
            self.room_encounters[old_room][0].remove(guard)
            self.room_encounters[guard.room][0].append(guard)

    def _select_guard_corpse_pose(self, guard):
        if (guard.state.action != 185 or self.level is None
                or guard.state.level_kind == 6):
            return
        # GetOppDeadSeq 4:0074-010a / FrameAdv 2:6544: ordinary corpse
        # variant follows slot parity, not a random choice.
        guards = self.room_encounters[guard.room][0]
        index = next(i for i, other in enumerate(guards) if other is guard)
        if index % 2:
            select_sequence(guard, 195)
            guard.runtime.next_frame()

    def _opponent_tumble(self, target):
        terrain, art = getattr(self, "terrain", None), getattr(self, "guard_art", None)
        if terrain is None or art is None:
            return False
        state = target.state
        record = art.frames[guard_frame_index(state.action)]
        if state.level_kind == 5 and terrain.forced_opponent_tumble(
                target.room, target.row, state, record):
            return True
        if self.level is None:
            return False
        guards, points = self.room_encounters[target.room]
        if not any(point.tumble_enabled for point in points):
            return False
        # DoOppTumbleSeq 4:03f4 counts the bank's death-state word at
        # +0x1c, not life or slot occupancy. Rnd(3) includes zero and three.
        dead_count = sum(other.death_registered for other in guards if other is not target)
        candidate = self.rng.randrange(4) <= dead_count
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        if not candidate and dead_count:
            candidate = any(
                other is not target and other.row == target.row
                and other.state.action in (185, 228)
                and character_column(floor_contact_x(
                    other.state.target_x, other.state.facing,
                    art.frames[guard_frame_index(other.state.action)])) == column
                for other in guards
            )
        if not candidate or state.facing == self.player.state.facing:
            return False
        direction = 1 if state.facing else -1
        return (terrain.tile(target.room, column, target.row).kind not in (3, 8, 4)
                and terrain.tile(target.room, column - direction, target.row).kind not in (3, 8))

    def _hurt(self, name, target, attacker):
        fatal_sequence = target.state.sequence_id in FATAL_STAB_SEQUENCES
        target.life = 0 if fatal_sequence else max(0, target.life - 1)
        if target.state.actor_type == 0 and not fatal_sequence:
            # CODE:6 0x53f8-0x5406 arms the Prince without replaying SEQS:55.
            target.sword_drawn = True
        target.contact_consumed = True
        target.recovering = target.alive
        if name == "guard":
            # CODE:6 0x513e-0x5152 uses the struck generator's skill.
            self.attack_pause = HIT_PAUSE[target.skill]
        if not target.alive:
            sequence, offset = 85, -17 if target.state.actor_type == 2 else 0
            if name == "guard" and self._opponent_tumble(target):
                # CheckStab 6:56ba-56d4 selects the native tumble, not 85.
                sequence, offset = 185, -12
        elif target.state.facing == attacker.state.facing:
            sequence, offset = 94, 0
        else:
            sequence = 74 if target.state.actor_type == 0 else 183
            offset = -10 if target.state.actor_type == 2 else 0
        # SetCharFloor/clear fall velocity, CODE:6 0x5478-0x547e.
        target.state.current_y = 0
        target.state.vertical_velocity = 0
        if sequence == 185:
            # Mode 9 passes in front of the roof, not onto the next floor.
            if target.terrain_motion is None:
                target.terrain_motion = TerrainMotion(target.room, target.row)
            target.terrain_motion.row = target.row
            target.terrain_motion.falling = True
            target.targetable = False
        select_sequence(target, sequence, offset)
        target.runtime.next_frame()
        if sequence == 85 and getattr(self, "terrain", None) is not None:
            record = None
            if name == "guard" and getattr(self, "guard_art", None) is not None:
                record = self.guard_art.frames[guard_frame_index(target.state.action)]
            elif name == "player" and getattr(self, "player_frames", None) is not None:
                record = self.player_frames[target.state.action]
            if record is not None:
                self.terrain.align_flat_death(target.room, target.row, target.state, record)
        target.state.current_x = target.state.target_x
        death_method = None
        if name == "player" and not target.alive:
            # CheckStab 6:5704-5748: ordinary type-2 guards on supported
            # levels (LEVL 21a4 == 0) select 14, not skeleton method 2.
            death_method = 14 if attacker.state.actor_type == 2 else 2
        return CombatEvent("hit" if target.alive else "death", name, death_method)

    def resolve_contacts(self):
        events, hits = [], {}
        # CODE:6 0x581c/0x5856 tests NPC contact first, then Prince contact;
        # both wound marks are collected before CheckStab changes hurt poses.
        pairs = [("guard", g, "player", self.player, "player") for g in self.guards]
        pairs.extend(("player", self.player, "guard", g, index)
                     for index, g in enumerate(self.guards))
        for fighter in (self.player, *self.guards):
            if fighter.state.action not in STRIKE_POSES:
                fighter.contact_consumed = False
        consumed = {id(f): f.contact_consumed for f in (self.player, *self.guards)}
        for name, attacker, target_name, defender, target_id in pairs:
            if (attacker.state.action not in STRIKE_POSES or consumed[id(attacker)]
                    or not contact_allowed(attacker, defender)):
                continue
            distance = opponent_distance(attacker, defender)
            if (attacker.state.facing != defender.state.facing
                    and 61 <= distance <= 99
                    and defender.sword_drawn and defender.state.action in BLOCK_POSES):
                # CODE:6 0x5a3c: blocked attacker SEQS:69, defender action 161.
                attacker.contact_consumed = True
                select_sequence(attacker, 69)
                attacker.runtime.next_frame()
                attacker.state.current_x = attacker.state.target_x
                defender.state.action = 161
                if name == "guard":
                    self.parry_timer = 4
                events.append(CombatEvent("parry", target_name))
            elif attacker.state.action == 154:
                attacker.contact_consumed = True
                low, high = strike_range(attacker, defender)
                if low <= distance <= high:
                    hits.setdefault(target_id, (target_name, defender, attacker))
        # CheckStab 0x50ec-0x50f6 clears the Prince's pending wound when an
        # NPC is wounded in the same cycle, including a fatal NPC hit.
        if any(key != "player" for key in hits):
            hits.pop("player", None)
        events.extend(self._hurt(*hit) for hit in hits.values())
        self.refresh_target()
        return events

    def step(self, now, interval_seconds):
        # Key events can advance the Prince immediately, but not speed up AI.
        # Tk rounds to whole milliseconds; preserve phase rather than missing
        # every other tick when an 83 ms callback is just short of 83.333 ms.
        if self.last_guard_at is None or now - self.last_guard_at >= interval_seconds - 0.002:
            self.generate_opponents()
            if self.level is not None:
                self.update_guard_alerts()
            self.advance_guard()
            self.world_frame += 1
            if self.last_guard_at is None or now - self.last_guard_at >= interval_seconds * 2:
                self.last_guard_at = now
            else:
                self.last_guard_at += interval_seconds
        return self.resolve_contacts()

    def advance_player_recovery(self):
        player = self.player
        player.runtime.next_frame()
        if player.recovering and player.state.sequence_id == 227:
            player.recovering = False
