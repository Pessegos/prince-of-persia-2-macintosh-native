import argparse
import math
import time
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageOps

from pop2.animation_data import (
    shape_id_for_action,
)
from pop2.combat import (
    PLAYER_COMBAT_TURN_SEQUENCE, contact_allowed, guard_frame_index,
)
from pop2.combat_art import GuardArtwork, HealthArtwork, HitArtwork
from pop2.control_mapping import (
    IDLE_SEQUENCE,
    RUN_JUMP_SEQUENCE,
    CROUCH_LOWER_SEQUENCE,
    CROUCH_STANDING_LOWER_SEQUENCE,
    CROUCH_HOLD_SEQUENCE,
    CROUCH_STEP_SEQUENCE,
    CROUCH_RISE_SEQUENCE,
    RUN_START_SEQUENCE,
    RUN_STOP_SEQUENCE,
    RUNNING_DRIFT_SEQUENCE,
    RUNNING_TURN_SEQUENCE,
    JUMP_FORWARD_SEQUENCE,
    SHIFT_STEP_SEQUENCE,
    STANDING_TURN_SEQUENCE,
    JUMP_VERTICAL_SEQUENCE,
    SWORD_DRAW_SEQUENCE,
    SWORD_ADVANCE_SEQUENCE,
    SWORD_RETREAT_SEQUENCE,
    SWORD_GUARD_SEQUENCE,
    SWORD_ATTACK_SEQUENCE,
    SWORD_BLOCK_SEQUENCE,
    SWORD_BLOCK_ATTACK_SEQUENCE,
    SWORD_SHEATHE_SEQUENCE,
    LEDGE_APPROACH_SEQUENCE,
    LEDGE_CLIMB_SEQUENCE,
    LEDGE_HANG_SEQUENCE,
    facing_for_direction,
    jump_sequence_for_input,
)
from pop2.mac_input import plan_cautious_step, plan_step, read_keyboard
from pop2.opening_animation import GLASS_POSITIONS
from pop2.harbor import SHIP_CLIMB_SEQUENCE
from pop2.rebirth import RebirthSnapshot
from pop2.game_session import GameResources, GameSession
from pop2.level_rendering import LevelRenderer
from pop2.render_opening import (
    OPENING_FLOOR_Y,
    ROOF_GLASS_OFFSETS,
    ROOM_ORIGIN_X,
    ROOM_HEIGHT,
    ROOM_WIDTH,
    SCENERY_Y_OFFSET,
    TILE_HEIGHT,
    TILE_WIDTH,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    character_sprite_top,
    decode_ctbl,
    decode_shap,
    kid_palette_for_level,
    load_resource_file,
)
from pop2.terrain import TerrainMotion, floor_y, floor_contact_x
from pop2.game_ui import MacintoshFont
from pop2.window_controls import WindowControls


SCALE = 2
START_FLOOR_Y = OPENING_FLOOR_Y
ANIMATION_FPS = 12
ANIMATION_INTERVAL_MS = 1000 / ANIMATION_FPS
COMBAT_ANIMATION_FPS = 10
COMBAT_ANIMATION_INTERVAL_MS = 1000 / COMBAT_ANIMATION_FPS
RUN_CYCLE_SEQUENCES = {1, 200, 201, 202}
REST_SEQUENCES = {IDLE_SEQUENCE}
CROUCH_SEQUENCES = {
    CROUCH_LOWER_SEQUENCE, CROUCH_STANDING_LOWER_SEQUENCE, CROUCH_HOLD_SEQUENCE,
    CROUCH_STEP_SEQUENCE, CROUCH_RISE_SEQUENCE,
}
JUMP_LANDING_SEQUENCE = 11
RUN_SEGMENT_SEQUENCES = RUN_CYCLE_SEQUENCES | {
    RUNNING_DRIFT_SEQUENCE, RUNNING_TURN_SEQUENCE
}
TAP_RELEASE_SEQUENCE = 201
TAP_RELEASE_ACTION = 8
SWORD_SEQUENCES = {
    "sword_draw": SWORD_DRAW_SEQUENCE,
    "sword_advance": SWORD_ADVANCE_SEQUENCE,
    "sword_retreat": SWORD_RETREAT_SEQUENCE,
    "sword_attack": SWORD_ATTACK_SEQUENCE,
    "sword_block": SWORD_BLOCK_SEQUENCE,
    "sword_sheathe": SWORD_SHEATHE_SEQUENCE,
}
SWORD_STEP_KINDS = {"sword_advance", "sword_retreat"}
SWORD_STEP_SEQUENCES = {SWORD_ADVANCE_SEQUENCE, SWORD_RETREAT_SEQUENCE}
SWORD_COMBAT_SEQUENCES = set(SWORD_SEQUENCES.values()) | {
    SWORD_GUARD_SEQUENCE, SWORD_BLOCK_ATTACK_SEQUENCE, 69, 203, 204, 205, 206,
    PLAYER_COMBAT_TURN_SEQUENCE, 245,
}


def animation_interval_for_frame(sequence_id, action):
    # ResetFrameVars chooses 5/6 ticks before the controller changes sword mode.
    if sequence_id == SWORD_DRAW_SEQUENCE and action == 207:
        return ANIMATION_INTERVAL_MS
    if sequence_id in (SWORD_SHEATHE_SEQUENCE, 93):
        first_pose = 233 if sequence_id == SWORD_SHEATHE_SEQUENCE else 234
        return COMBAT_ANIMATION_INTERVAL_MS if action == first_pose else ANIMATION_INTERVAL_MS
    if sequence_id in SWORD_COMBAT_SEQUENCES:
        return COMBAT_ANIMATION_INTERVAL_MS
    return ANIMATION_INTERVAL_MS


def sword_palette_for_level(prince, level_kind):
    colors = decode_ctbl(prince["CTBL"][1000 + level_kind]["data"])
    palette = {239 + index: color for index, color in colors.items()}
    # A few sword SHAPs use index 250, absent from CTBL:1005; use a capture estimate.
    palette[250] = (150, 69, 0, 255)
    return palette


@dataclass(frozen=True)
class BufferedCommand:
    kind: str
    direction: int = 0
    mode: str = ""
    running: bool = False


def next_animation_deadline(previous_deadline, now, interval_ms=ANIMATION_INTERVAL_MS):
    interval = interval_ms / 1000
    deadline = previous_deadline + interval
    if deadline <= now:
        missed_intervals = int((now - deadline) / interval) + 1
        deadline += missed_intervals * interval
    delay_ms = max(0, round((deadline - now) * 1000))
    return deadline, delay_ms


class ScenePrototype(WindowControls):
    @property
    def room_id(self):
        return self.game.room_id

    @room_id.setter
    def room_id(self, value):
        self.game.room_id = value

    @property
    def terrain_motion(self):
        return self.game.motion

    @terrain_motion.setter
    def terrain_motion(self, value):
        self.game.motion = value

    @property
    def combat(self):
        return self.game.combat

    @combat.setter
    def combat(self, value):
        self.game.combat = value

    @property
    def opening(self):
        return self.game.opening

    @opening.setter
    def opening(self, value):
        self.game.opening = value

    @property
    def harbor(self):
        return self.game.harbor

    @harbor.setter
    def harbor(self, value):
        self.game.harbor = value

    @property
    def death(self):
        return self.game.death

    @death.setter
    def death(self, value):
        self.game.death = value

    @property
    def checkpoint(self):
        return self.game.checkpoint

    @checkpoint.setter
    def checkpoint(self, value):
        self.game.checkpoint = value

    @property
    def level_complete(self):
        return self.game.complete

    @level_complete.setter
    def level_complete(self, value):
        self.game.complete = value

    def __init__(self, with_guard=True, peaceful=False, audio=None, with_intro=False, level_number=1):
        self.with_intro = with_intro
        self.intro = None
        self.intro_assets = None
        self.demo = None
        self.attract_data = self.credits_assets = None
        self.attract_stage = None
        self.live_combat = None
        self.audio = audio
        self.peaceful = peaceful
        self.terrain_enabled = with_guard
        self.resources = GameResources.load()
        self.game = GameSession.load(self.resources, level_number, terrain_enabled=with_guard)
        self.level_renderer = LevelRenderer(self.game.level)
        room = self.level_renderer.room(self.room_id)
        self.background = room.background
        self.foreground = room.foreground
        roof = load_resource_file("Rooftops.rsrc")
        roof_palette = decode_ctbl(roof["CTBL"][3500]["data"])
        self.curtain_sprites = [
            decode_shap(roof["SHAP"][3588 + index]["data"], roof_palette)
            for index in range(9)
        ]
        self.glass_sprites = [
            decode_shap(roof["SHAP"][3597 + index]["data"], roof_palette)
            for index in range(len(GLASS_POSITIONS))
        ]

        self.kid = self.resources.kid
        self.first_shape_id = self.resources.first_shape_id
        self.frames = self.resources.frames
        self.attachment_frames = self.resources.attachment_frames
        prince = self.resources.prince
        self.ui_font = MacintoshFont(prince["NFNT"][23331]["data"])
        # DrawRestartMessage uses palette index 6; match its displayed RGB.
        hud_text_color = (253, 255, 168, 255)
        self.pause_text = self.ui_font.text("Game Paused", hud_text_color)
        self.cutscene_pause_text = self.ui_font.text("Cutscene Paused", hud_text_color)
        self.restart_text = self.ui_font.text("Press key to continue", hud_text_color)
        self.sword_shapes = prince["SHAP"]
        self.first_sword_shape_id = int.from_bytes(
            prince["SHPL"][1000]["data"][:2], "big"
        )
        self.sequences = self.resources.sequences
        self.bind_level(self.game, self.level_renderer)
        self.held_directions = []
        self.pending_action = None
        self.running_jump_controls_cleared = False
        self.run_cycle_boundary_pending = False
        self.horizontal_input = 0
        self.up_held = False
        self.jump_started_for_press = False
        self.jump_repeat_armed = False
        self.run_start_x = None
        self.down_held = False
        self.shift_held = False
        self.step_cautious = True
        self.step_warning_direction = 0
        self.ctrl_held = False
        self.sword_drawn = False
        self.sword_sheathing = False
        self.down_sheathe_consumed = False
        self.ledge_test_active = False
        self.ledge_action_consumed = False
        self.ledge_hanging = False
        self.ledge_climbing = False
        self.ledge_climb_requested = False
        self.native_ledge = False
        self.ledge_grip_delay = 0
        self.run_active = False
        self.run_direction = 0
        self.run_stop_requested = False
        self.sprite_cache = {}
        self.sword_sprite_cache = {}
        self.animation_after_id = None
        self.in_animation_tick = False
        self.paused = False
        self.pause_started_at = None
        self.escape_held = False
        self.pause_resume_keys = set()
        self.window_keys_down = set()
        self.fullscreen = False
        self.windowed_geometry = None
        self.windowed_state = "normal"
        self.dev_menu = None
        self.dev_was_paused = False
        self.dev_toggle_held = False
        self.game_menu = None
        self.game_was_paused = False
        self.native_viewport = None

        self.create_window("Prince of Persia 2 Macintosh Native (WIP)" if with_guard
                           else "Prince of Persia 2 Macintosh Native - Animation Preview (WIP)",
                           scale=SCALE)
        self.action = self.sequence_state.action
        self.player_x = self.sequence_state.target_x
        if with_intro:
            self.start_intro()
        elif self.audio is not None:
            self.audio.add_sound(36)
            self.advance_audio()
        self.render()
        interval = self.current_animation_interval_ms()
        self.next_animation_at = time.perf_counter() + interval / 1000
        self.animation_after_id = self.root.after(
            round(interval), self.advance_animation
        )

    def bind_level(self, game, renderer):
        palette = kid_palette_for_level(self.kid, game.level.kind)
        sword_palette = sword_palette_for_level(self.resources.prince, game.level.kind)
        guard_art = health_art = hit_art = None
        if game.combat is not None:
            guard_art = GuardArtwork(load_resource_file("Guard.rsrc"), self.sword_shapes,
                                     self.first_sword_shape_id, sword_palette)
            health_art = HealthArtwork(self.kid, palette, self.first_shape_id)
            hit_art = HitArtwork(self.kid, palette, self.first_shape_id,
                                 self.frames, guard_art.frames)
            game.combat.guard_art = guard_art
        room = renderer.room(game.room_id)
        self.game, self.level_renderer = game, renderer
        self.palette, self.sword_palette = palette, sword_palette
        self.guard_art, self.health_art, self.hit_art = guard_art, health_art, hit_art
        self.checkpoints = game.level.checkpoints
        self.level_map, self.physics = game.level_map, game.physics
        self.room_cache = renderer.rooms
        self.background, self.foreground = room.background, room.foreground
        self.start_tile = game.level.start_tile
        self.right_platform_edge_x = game.level.right_platform_edge()
        self.sequence_runtime, self.sequence_state = game.runtime, game.runtime.state
        self.action, self.player_x = self.sequence_state.action, self.sequence_state.target_x
        self.sprite_cache, self.sword_sprite_cache = {}, {}

    def load_level(self, number):
        # Prepare the complete destination before replacing a running session.
        game = GameSession.load(self.resources, number, self.terrain_enabled)
        renderer = LevelRenderer(game.level)
        self.bind_level(game, renderer)
        self.demo = self.live_combat = None
        self.attract_stage = self.intro = None
        self.clear_keys(None)
        self.reset_level_controls()
        if self.audio is not None:
            self.audio.reset()
        if self.animation_after_id is not None:
            self.root.after_cancel(self.animation_after_id)
            self.animation_after_id = None
        self.status.set(f"Level {game.level.number}")
        self.render()
        self.next_animation_at = time.perf_counter()
        if not self.in_animation_tick:
            self.schedule_next_animation()

    def set_key_state(self, key, pressed):
        if self.paused or self.dev_menu is not None:
            return "break"
        if self._combat_controls_locked():
            setattr(self, f"{key}_held", pressed)
            return "break"
        if self._opening_active():
            setattr(self, f"{key}_held", pressed)
            return "break"
        if self.native_ledge:
            setattr(self, f"{key}_held", pressed)
            return "break"
        if key == "up":
            if (
                not pressed
                and self.up_held
                and not self.jump_started_for_press
                and not self.ledge_hanging
            ):
                self.start_jump()
            self.up_held = pressed
            if not pressed:
                self.jump_started_for_press = False
        elif key == "down":
            if pressed and self.down_held:
                return "break"
            self.down_held = pressed
            if pressed and self.up_held:
                return "break"
            if self.sword_drawn:
                if pressed:
                    self.down_sheathe_consumed = True
                    self.queue_sword_action("sword_sheathe")
                else:
                    self.down_sheathe_consumed = False
                return "break"
            if not pressed:
                self.down_sheathe_consumed = False
            self.update_ledge_test_state()
            if pressed and not self.ledge_hanging:
                if self._is_resting():
                    if not self.start_native_descent():
                        self.start_crouch_lower()
                elif self.sequence_state.sequence_id not in CROUCH_SEQUENCES:
                    self.pending_action = BufferedCommand("crouch")
                    if self.run_active and self.sequence_state.sequence_id not in RUN_CYCLE_SEQUENCES:
                        self.run_stop_requested = True
        elif key == "shift":
            self.shift_held = pressed
            self.update_ledge_test_state()
        elif key == "ctrl":
            if pressed and not self.ctrl_held:
                self.queue_sword_action(
                    "sword_attack" if self.sword_drawn else "sword_draw"
                )
            self.ctrl_held = pressed
        return "break"

    def queue_sword_action(self, kind):
        if self.sword_sheathing or self._combat_controls_locked():
            return False
        if (kind == "sword_draw" and self._is_resting()) or (
            kind != "sword_draw"
            and self.sword_drawn
            and self.sequence_state.sequence_id == SWORD_GUARD_SEQUENCE
        ):
            self.pending_action = None
            return self.start_sword_action(kind)
        self.pending_action = BufferedCommand(kind)
        return False

    def start_sword_action(self, kind, sequence_id=None):
        if kind == "sword_draw":
            motion = getattr(self, "terrain_motion", None)
            if motion is not None:
                state = self.sequence_state
                offset = self.level_map.combat_draw_offset(
                    motion.room, motion.row, state, self.frames[state.action], self.player_bounds())
                self.player_x += offset * (1 if state.facing else -1)
            self.sword_drawn = True
            self.sequence_state.sound_events.append(14)
        elif kind == "sword_sheathe":
            self.sword_sheathing = True
            # PutSwordAway (6:2594) clears sword mode before the first pose;
            # the animation lock remains until the sheathing sequence ends.
            self.sword_drawn = False
            # PutSwordAway (6:2592) uses the short sequence while OppToFight
            # still finds a living ordinary enemy, not the long idle version.
            if sequence_id is None and self.combat is not None and not getattr(self, "peaceful", False):
                nearby_rooms = {self.combat.player.room}
                if getattr(self, "level_map", None) is not None:
                    nearby_rooms.update(self.level_map.neighbor(self.room_id, side)
                                        for side in ("left", "right"))
                if any(guard.alive and guard.room in nearby_rooms
                       for guard in self.combat.active_guards()):
                    sequence_id = 93
        self.run_active = False
        self.run_stop_requested = False
        self.run_direction = 0
        self.start_sequence(SWORD_SEQUENCES[kind] if sequence_id is None else sequence_id)
        self.status.set({
            "sword_draw": "Drawing sword",
            "sword_advance": "Advancing with sword",
            "sword_retreat": "Retreating with sword",
            "sword_attack": "Attacking",
            "sword_block": "Blocking",
            "sword_sheathe": "Sheathing sword",
        }[kind])
        if not self.in_animation_tick:
            self.advance_animation_now()
        return True

    def resume_sword_attack_after_block(self):
        if (
            self.sword_drawn
            and not self.sword_sheathing
            and self.sequence_state.action in (150, 161)
            and self.pending_action is not None
            and self.pending_action.kind == "sword_attack"
        ):
            # CODE:6 0x27e8 selects SEQS:66 before the block's return to guard.
            self.pending_action = None
            return self.start_sword_action(
                "sword_attack", sequence_id=SWORD_BLOCK_ATTACK_SEQUENCE
            )
        return False

    def queue_sword_step(self, direction):
        kind = (
            "sword_advance"
            if facing_for_direction(direction) == self.sequence_state.facing
            else "sword_retreat"
        )
        return self.queue_sword_action(kind)

    def resume_sword_controls(self):
        if not self.sword_drawn or self.sword_sheathing:
            return False
        state = self.sequence_state
        command = self.pending_action
        if state.sequence_id in SWORD_STEP_SEQUENCES:
            # CODE:6 0x279a and 0x2844 allow these commands on the final step pose.
            if command is not None and (
                (command.kind == "sword_attack" and state.action in (165, 157))
                or (command.kind == "sword_block" and state.action == 165)
            ):
                return self.dispatch_pending_action()
            return False
        # DoAdvance/DoRetreat accept only guard actions 158, 170 and 171.
        if state.sequence_id != SWORD_GUARD_SEQUENCE or state.action not in (158, 170, 171):
            return False
        if command is not None and command.kind in SWORD_SEQUENCES:
            return self.dispatch_pending_action()
        if self.horizontal_input:
            return self.queue_sword_step(self.horizontal_input)
        return False

    def update_ledge_test_state(self):
        requested = self.down_held and self.shift_held
        if not requested:
            self.ledge_test_active = False
            self.ledge_action_consumed = False
            return
        self.ledge_test_active = requested and self._at_rooftop_ledge()
        self._try_start_ledge_hang()

    def horizontal_key(self, _event, direction, pressed):
        if self.paused or self.dev_menu is not None:
            return "break"
        previous_direction = self.horizontal_input
        if pressed:
            if direction in self.held_directions:
                return "break"
            self.held_directions.append(direction)
        elif direction in self.held_directions:
            self.held_directions.remove(direction)
            if getattr(self, "step_warning_direction", 0) == direction:
                self.step_warning_direction = 0
        self.sample_keyboard()

        if self._combat_controls_locked():
            return "break"
        if self._opening_active():
            return "break"
        if self.native_ledge:
            return "break"

        if self.sword_sheathing:
            if pressed and self.horizontal_input != previous_direction and self.horizontal_input:
                self.queue_sampled_horizontal_action(self.horizontal_input)
            return "break"

        if self.sword_drawn:
            if pressed and self.horizontal_input != previous_direction and self.horizontal_input:
                self.queue_sword_step(self.horizontal_input)
            return "break"

        if not pressed and self.run_active and self.run_direction == direction:
            self.run_stop_requested = True

        if self.horizontal_input != previous_direction and self.horizontal_input:
            self.queue_sampled_horizontal_action(self.horizontal_input)
        return "break"

    def sample_keyboard(self):
        frame = read_keyboard(
            self.held_directions, self.up_held, self.down_held, self.shift_held
        )
        self.horizontal_input = frame.horizontal
        return frame

    def queue_sampled_horizontal_action(self, direction):
        if self.sword_drawn and not self.sword_sheathing:
            return False
        if self.up_held:
            if self.jump_started_for_press:
                if self.pending_action is not None and self.pending_action.kind == "jump":
                    self.pending_action = BufferedCommand(
                        "jump", direction, running=self.pending_action.running
                    )
                elif not self._is_resting():
                    self.pending_action = BufferedCommand(
                        "jump", direction,
                        running=(self.sequence_state.sequence_id in RUN_SEGMENT_SEQUENCES
                                 or self.sequence_state.sequence_id == RUN_JUMP_SEQUENCE),
                    )
                return False
            return self.start_jump_if_needed()
        elif (
            self.down_held
            and not self.shift_held
            and self.sequence_state.sequence_id in (
                CROUCH_LOWER_SEQUENCE, CROUCH_STANDING_LOWER_SEQUENCE,
                CROUCH_HOLD_SEQUENCE, CROUCH_STEP_SEQUENCE
            )
            and facing_for_direction(direction) == self.sequence_state.facing
        ):
            # GenCtrl 6:06b4/099a accepts input on the first displayed low pose.
            if self.sequence_state.action == 109 and self.sequence_state.cursor > 0:
                self.pending_action = None
                self.start_crouch_step(direction)
                return True
            self.pending_action = BufferedCommand("crawl", direction)
            return False
        elif self.shift_held:
            return self.queue_horizontal_action(direction, "step")
        elif facing_for_direction(direction) != self.sequence_state.facing:
            return self.queue_horizontal_action(direction, "turn")
        else:
            return self.queue_horizontal_action(direction, "run")

    def up_key(self, _event):
        if self.paused or self.dev_menu is not None:
            return "break"
        if self.up_held:
            return "break"
        self.up_held = True
        if self._combat_controls_locked():
            return "break"
        if self._opening_active():
            return "break"
        if self.sword_drawn:
            self.jump_started_for_press = True
            self.jump_repeat_armed = False
            self.queue_sword_action("sword_block")
            return "break"
        if self.ledge_hanging:
            self.ledge_climb_requested = True
            if self.sequence_state.sequence_id == LEDGE_HANG_SEQUENCE:
                self.start_ledge_climb()
            return "break"
        self.jump_started_for_press = False
        if (
            self.sequence_state.sequence_id == STANDING_TURN_SEQUENCE
            and self.sequence_state.action == 45
            and self.horizontal_input
            and self.pending_action is None
        ):
            # Both keys arrived during the turn's first pose: one reverse chord.
            self.jump_started_for_press = True
            return "break"
        if self.horizontal_input or not self._is_resting():
            self.start_jump_if_needed()
        else:
            self.root.after(35, self.start_jump_if_needed)
        return "break"

    def start_jump_if_needed(self):
        if (not self.paused and self.dev_menu is None and not self.ledge_hanging
                and self.up_held and not self.jump_started_for_press and not self.sword_drawn):
            self.start_jump()

    def start_jump(self):
        self.jump_started_for_press = True
        horizontal = self.horizontal_input
        starting_run = (
            horizontal != 0
            and self.sequence_state.sequence_id == RUN_START_SEQUENCE
            and self.sequence_state.action in (1, 2, 3)
        )
        running = (
            horizontal != 0
            and (self.sequence_state.sequence_id in RUN_SEGMENT_SEQUENCES
                 or self.sequence_state.sequence_id == RUN_JUMP_SEQUENCE)
            and not starting_run
        )
        # A fresh Up during SEQS:4 waits for DoRunJump's next run pose;
        # landing must not turn that buffered command into a standing jump.
        command = BufferedCommand("jump", horizontal, running=running)
        if self._is_resting() or starting_run:
            self.pending_action = None
            self.dispatch_jump(command)
        else:
            self.pending_action = command

    def queue_horizontal_action(self, direction, mode):
        if (
            mode == "run"
            and self._is_running()
            and self.run_direction == direction
        ):
            self.run_stop_requested = False
            return False

        command = BufferedCommand("horizontal", direction, mode)
        if self._is_resting():
            self.pending_action = None
            return self.dispatch_horizontal_action(command)
        else:
            self.pending_action = command
            return False

    def dispatch_jump(self, command):
        if not command.direction and self.sequence_state.sequence_id in RUN_SEGMENT_SEQUENCES:
            # GenCtrl 6:11e4-1242 never calls DoJumpUp from a running pose.
            # Keep the host's buffered Up, but brake before aligning its ledge.
            self.pending_action = command
            self.run_active = self.run_stop_requested = False
            self.run_direction = 0
            self.run_start_x = None
            self.start_sequence(RUN_STOP_SEQUENCE)
            return True
        if not command.direction and self.start_upper_ledge_jump():
            return True
        if (
            not command.running
            and self.sequence_state.sequence_id == RUN_START_SEQUENCE
            and self.sequence_state.action in (1, 2, 3)
            and self.run_start_x is not None
        ):
            self.player_x = self.run_start_x
            self.sequence_state.current_x = self.player_x
            self.sequence_state.target_x = self.player_x
        if (
            command.direction
            and facing_for_direction(command.direction) != self.sequence_state.facing
        ):
            return self.dispatch_horizontal_action(
                BufferedCommand("horizontal", command.direction, "turn"),
                was_running=command.running,
            )
        sequence_id = jump_sequence_for_input(
            command.direction,
            self.sequence_state.facing,
            running=command.running,
        )
        if sequence_id == RUN_JUMP_SEQUENCE and getattr(self, "level_map", None) is not None:
            if not 7 <= self.sequence_state.action <= 14:
                return False
            offset = self.level_map.run_jump_offset(
                self.room_id, self.terrain_motion.row, self.sequence_state)
            if offset is None:
                return False
            self.player_x += offset
        self.jump_repeat_armed = True
        self.run_active = sequence_id == RUN_JUMP_SEQUENCE
        self.run_direction = command.direction if self.run_active else 0
        self.run_stop_requested = (
            self.run_active and command.direction not in self.held_directions
        )
        self.run_start_x = None
        self.start_sequence(sequence_id)
        if sequence_id == RUN_JUMP_SEQUENCE:
            self.status.set("Running jump: original SEQS:4")
        else:
            self.status.set(f"Jump: original SEQS:{sequence_id}")
        if not self.in_animation_tick:
            self.advance_animation_now()
        return True

    def dispatch_horizontal_action(self, command, was_running=False):
        self.jump_repeat_armed = False
        direction = command.direction
        facing = facing_for_direction(direction)

        if command.mode == "turn":
            if facing == self.sequence_state.facing:
                if direction in self.held_directions:
                    return self.dispatch_horizontal_action(
                        BufferedCommand("horizontal", direction, "run"),
                        was_running=was_running,
                    )
                return False
            if was_running:
                self.start_running_drift(direction)
                if direction not in self.held_directions:
                    self.run_stop_requested = True
            else:
                self.start_standing_turn()
            return True

        if command.mode == "step":
            if facing != self.sequence_state.facing:
                self.pending_action = command
                self.start_standing_turn()
                return True
            if getattr(self, "level_map", None) is not None:
                if getattr(self, "step_warning_direction", 0) == direction:
                    return False
                boundary = self.level_map.step_boundary(
                    self.room_id, self.terrain_motion.row, self.sequence_state,
                    self.frames[self.sequence_state.action], self.player_bounds())
                step, self.step_cautious = plan_cautious_step(
                    boundary, getattr(self, "step_cautious", True))
                if step.sequence_id == 44 and direction in self.held_directions:
                    self.step_warning_direction = direction
            else:
                edge_x = self.right_platform_edge_x if direction > 0 else 0
                clearance = (edge_x - self.player_x) * direction
                step = plan_step(clearance)
            if step is None:
                return False
            self.player_x += direction * step.pre_offset
            self.sequence_state.current_x = self.player_x
            self.sequence_state.target_x = self.player_x
            if step.sequence_id is not None:
                self.start_sequence(step.sequence_id)
            self.run_active = False
            self.run_direction = direction
            self.run_stop_requested = False
            if step.sequence_id is None:
                self.status.set("Short step: original sub-frame offset")
            else:
                self.status.set(f"Step: original SEQS:{step.sequence_id}")
            if step.sequence_id is not None and not self.in_animation_tick:
                self.advance_animation_now()
            return True

        if facing != self.sequence_state.facing:
            if was_running:
                self.start_running_drift(direction)
                return True
            self.start_standing_turn()
            return True

        if getattr(self, "level_map", None) is not None:
            boundary = self.level_map.step_boundary(
                self.room_id, self.terrain_motion.row, self.sequence_state,
                self.frames[self.sequence_state.action], self.player_bounds())
            # GenCtrl 6:11a0-11d6: a fresh forward press near a solid
            # barrier calls DoStepFwd, not the running acceleration sequence.
            if boundary.barrier_type == 1 and boundary.clearance < 27:
                return self.dispatch_horizontal_action(
                    BufferedCommand("horizontal", direction, "step"))

        self.run_start_x = self.player_x
        self.start_sequence(RUN_START_SEQUENCE)
        self.run_active = True
        self.run_direction = direction
        self.run_stop_requested = False
        self.status.set("Run: original start, cycle, and stopping animations")
        if not self.in_animation_tick:
            self.advance_animation_now()
        return True

    def start_running(self, direction):
        self.queue_horizontal_action(direction, "run")

    def start_running_turn(self, direction):
        self.run_start_x = None
        self.sequence_state.facing = facing_for_direction(direction)
        self.start_sequence(RUNNING_TURN_SEQUENCE)
        self.run_active = True
        self.run_direction = direction
        self.run_stop_requested = False
        self.status.set("Run after standing turn: original SEQS:43")
        self.advance_animation_now()

    def start_running_drift(self, direction):
        self.run_start_x = None
        self.start_sequence(RUNNING_DRIFT_SEQUENCE)
        self.run_active = True
        self.run_direction = direction
        self.run_stop_requested = False
        self.run_cycle_boundary_pending = False
        self.status.set("Running reversal: original SEQS:6")
        self.advance_animation_now()

    def start_standing_turn(self):
        self.run_active = False
        self.run_direction = 0
        self.run_stop_requested = False
        self.run_start_x = None
        self.start_sequence(STANDING_TURN_SEQUENCE)
        self.status.set("Standing turn: original SEQS:5")
        self.advance_animation_now()

    def resume_run_during_standing_turn(self):
        state = self.sequence_state
        direction = self.horizontal_input
        sheath_stop = self.sword_sheathing and state.sequence_id == SWORD_SHEATHE_SEQUENCE
        if (
            (state.sequence_id != STANDING_TURN_SEQUENCE and not sheath_stop)
            or state.action != 48
            or not direction
            or facing_for_direction(direction) != state.facing
            or self.shift_held
            or self.up_held
            or self.down_held
        ):
            return False
        if self.pending_action is not None and self.pending_action != BufferedCommand(
            "horizontal", direction, "run"
        ):
            return False

        # GenCtrl 6:062c/1014 dispatches by pose, not sequence: both the
        # standing turn and long sheath can resume a held run on pose 48.
        self.pending_action = None
        if sheath_stop:
            self.sword_sheathing = self.sword_drawn = False
        self.start_running_turn(direction)
        return True

    def resume_queued_turn_during_standing_turn(self):
        state = self.sequence_state
        command = self.pending_action
        if (
            state.sequence_id != STANDING_TURN_SEQUENCE
            or state.action not in (50, 51, 52)
            or command is None
        ):
            return False

        if command.kind == "jump":
            if command.direction and facing_for_direction(command.direction) == state.facing:
                return self.dispatch_pending_action()
            return False
        if (
            command.kind == "horizontal"
            and command.mode == "turn"
            and facing_for_direction(command.direction) != state.facing
        ):
            return self.dispatch_pending_action()
        return False

    def resume_drift_during_run(self):
        state = self.sequence_state
        command = self.pending_action
        if (
            state.sequence_id not in RUN_CYCLE_SEQUENCES
            or not 4 <= state.action <= 14
            or command is None
            or not (
                (command.kind == "horizontal" and command.mode == "turn")
                or (command.kind == "jump" and command.running)
            )
            or facing_for_direction(command.direction) == state.facing
        ):
            return False

        # GenCtrl 6:1216 checks backward before Up, including a jump chord.
        # An airborne reversal waits for the first run pose after landing.
        return self.dispatch_pending_action(was_running=True)

    def update_running_jump_controls(self):
        state = self.sequence_state
        if state.sequence_id == RUN_JUMP_SEQUENCE and state.action == 44:
            # GenCtrl 6:074a-0760 -> ClearControls 4:3e3a. Directional
            # requests from the arc do not survive the final landing pose.
            if self.pending_action is not None and self.pending_action.kind in (
                "horizontal", "jump", "crouch", "crawl"
            ):
                self.pending_action = None
            self.running_jump_controls_cleared = True
            return
        if not getattr(self, "running_jump_controls_cleared", False):
            return
        self.running_jump_controls_cleared = False
        if state.sequence_id not in RUN_CYCLE_SEQUENCES:
            return
        # The next ReadKeyboard/GenCtrl pass sees fresh held directions,
        # not an unconditional command saved before ClearControls.
        direction = self.horizontal_input
        self.run_stop_requested = not direction
        if self.pending_action is not None:
            return
        if direction and facing_for_direction(direction) != state.facing:
            self.pending_action = BufferedCommand("horizontal", direction, "turn")
        elif direction and self.up_held:
            self.start_jump()
        elif self.down_held and not self.up_held:
            self.pending_action = BufferedCommand("crouch")

    def resume_queued_running_jump_during_run(self):
        state = self.sequence_state
        command = self.pending_action
        if (
            state.sequence_id not in RUN_CYCLE_SEQUENCES
            or not 7 <= state.action <= 14
            or command is None
            or command.kind != "jump"
            or not command.running
            or not command.direction
            or facing_for_direction(command.direction) != state.facing
        ):
            return False

        # DoRunJump accepts a running jump from run actions 7-14.
        return self.dispatch_pending_action(was_running=True)

    def resume_queued_crouch_during_run(self):
        state = self.sequence_state
        if (
            state.sequence_id not in RUN_CYCLE_SEQUENCES
            or not 4 <= state.action <= 14
            or self.pending_action is None
            or self.pending_action.kind != "crouch"
        ):
            return False

        if state.action in (7, 11) and not self.horizontal_input:
            self.run_active = False
            self.run_stop_requested = False
            self.run_direction = 0
            self.start_sequence(RUN_STOP_SEQUENCE)
            return True

        # GenCtrl's run handler selects SEQS:26 directly for Down.
        return self.dispatch_pending_action()

    def resume_held_running_jump(self):
        state = self.sequence_state
        direction = self.horizontal_input
        if (
            state.sequence_id not in RUN_CYCLE_SEQUENCES
            or not 7 <= state.action <= 14
            or not self.run_active
            or not self.jump_repeat_armed
            or not self.jump_started_for_press
            or not self.up_held
            or not direction
            or direction != self.run_direction
            or direction not in self.held_directions
            or self.run_stop_requested
            or self.pending_action is not None
        ):
            return False

        return self.dispatch_jump(BufferedCommand("jump", direction, running=True))

    def resume_queued_action_during_run_stop(self):
        state = self.sequence_state
        command = self.pending_action
        sheath_stop = self.sword_sheathing and state.sequence_id == 92
        if ((state.sequence_id != RUN_STOP_SEQUENCE and not sheath_stop)
                or state.action not in (50, 51, 52)):
            return False
        if (sheath_stop and command is None and self.horizontal_input
                and not self.up_held and not self.down_held):
            direction = self.horizontal_input
            mode = ("step" if self.shift_held else
                    "run" if facing_for_direction(direction) == state.facing else "turn")
            command = self.pending_action = BufferedCommand("horizontal", direction, mode)
        if (
            command is None
            or not (
                command.kind == "crouch"
                or (command.kind == "horizontal" and command.mode in ("run", "turn", "step"))
            )
        ):
            return False

        # GenCtrl routes stop actions 50-52 through the normal input handler.
        if sheath_stop:
            self.sword_sheathing = self.sword_drawn = False
        return self.dispatch_pending_action()

    def resume_run_stop(self):
        state = self.sequence_state
        command = self.pending_action
        vertical_jump = command is not None and command.kind == "jump" and not command.direction
        if (self.run_stop_requested and state.sequence_id in RUN_CYCLE_SEQUENCES
                and state.action in (7, 11) and (command is None or vertical_jump)):
            # GenCtrl 6:11e4 brakes on either supporting-foot pose. Waiting
            # for the loop's last pose adds an unnecessary half stride.
            self.run_active = False
            self.run_stop_requested = False
            self.run_direction = 0
            self.start_sequence(RUN_STOP_SEQUENCE)
            return True
        return False

    def start_sequence(self, sequence_id):
        self.run_cycle_boundary_pending = False
        if sequence_id != IDLE_SEQUENCE and not 29 <= sequence_id <= 44:
            self.step_cautious = True
            self.step_warning_direction = 0
        if getattr(self, "combat", None) is not None:
            self.combat.notify_player_sequence(sequence_id)
        self.sequence_state.select(sequence_id)
        self.sequence_state.target_x = self.player_x
        self.sequence_state.current_x = self.player_x
        if sequence_id in (JUMP_FORWARD_SEQUENCE, JUMP_VERTICAL_SEQUENCE, RUN_JUMP_SEQUENCE):
            self.sequence_state.current_y = 0

    def start_crouch_lower(self):
        state = self.sequence_state
        # StairClimbing -> 1068 chooses 50; only running GenCtrl 125a uses 26.
        running = state.sequence_id in RUN_CYCLE_SEQUENCES and 4 <= state.action < 15
        self.run_active = False
        self.run_stop_requested = False
        sequence = CROUCH_LOWER_SEQUENCE if running else CROUCH_STANDING_LOWER_SEQUENCE
        self.start_sequence(sequence)
        self.status.set(f"Crouch: original SEQS:{sequence}")
        if not self.in_animation_tick:
            self.advance_animation_now()

    def start_crouch_step(self, direction):
        self.start_sequence(CROUCH_STEP_SEQUENCE)
        self.status.set("Crouch step: original SEQS:79")
        if not self.in_animation_tick:
            self.advance_animation_now()

    def start_crouch_rise(self):
        self.start_sequence(CROUCH_RISE_SEQUENCE)
        self.status.set("Standing up: original SEQS:49")

    def resume_crouch(self):
        state = self.sequence_state
        if (state.sequence_id not in (
                CROUCH_LOWER_SEQUENCE, CROUCH_STANDING_LOWER_SEQUENCE,
                CROUCH_HOLD_SEQUENCE)
                or state.action != 109 or state.cursor == 0):
            return False
        if self.pending_action is not None and self.pending_action.kind == "crawl":
            direction = self.pending_action.direction
            self.pending_action = None
            self.start_crouch_step(direction)
            return True
        if not self.down_held:
            self.start_crouch_rise()
            return True
        direction = self.horizontal_input
        if (
            self.pending_action is None
            and direction
            and not self.shift_held
            and facing_for_direction(direction) == self.sequence_state.facing
        ):
            self.start_crouch_step(direction)
            return True
        return False

    @staticmethod
    def _right_platform_edge(level, room_id, start_x):
        floor_row = 1
        supported_x = []
        for tile_x in range(start_x, 10):
            offset = room_id * 60 + (floor_row * 10 + tile_x) * 2
            if int.from_bytes(level[offset:offset + 2], "big") != 1:
                break
            supported_x.append(tile_x)
        return (supported_x[-1] + 1) * TILE_WIDTH if supported_x else ROOM_WIDTH - 1

    def _at_rooftop_ledge(self):
        if getattr(self, "level_map", None) is not None:
            return self.level_map.ledge(self.room_id, self.terrain_motion.row,
                                        self.player_x, self.sequence_state.facing) is not None
        return self.right_platform_edge_x - 12 <= self.player_x <= self.right_platform_edge_x + 8

    def _clamp_rooftop_x(self, x, sequence_id):
        if getattr(self, "level_map", None) is not None:
            return x
        x = max(0, min(x, ROOM_WIDTH - 1))
        grounded_sequences = RUN_SEGMENT_SEQUENCES | {
            STANDING_TURN_SEQUENCE,
        } | CROUCH_SEQUENCES | set(range(29, SHIFT_STEP_SEQUENCE + 1))
        if getattr(self, "combat", None) is not None:
            grounded_sequences |= SWORD_COMBAT_SEQUENCES | {60, 69, 74, 85, 94, 183, 213}
        return min(x, self.right_platform_edge_x) if sequence_id in grounded_sequences else x

    def start_ledge_hang(self):
        if getattr(self, "level_map", None) is not None:
            return self.start_native_descent()
        if not self._at_rooftop_ledge():
            return False
        self.run_active = False
        self.run_direction = 0
        self.run_stop_requested = False
        self.pending_action = None
        self.jump_repeat_armed = False
        self.ledge_hanging = True
        self.ledge_climbing = False
        self.ledge_climb_requested = False
        self.ledge_action_consumed = True
        self.sequence_state.current_y = 0
        self.start_sequence(LEDGE_APPROACH_SEQUENCE)
        self.status.set("Hanging from the rooftop edge")
        if not self.in_animation_tick:
            self.advance_animation_now()
        return True

    def _try_start_ledge_hang(self):
        if getattr(self, "level_map", None) is not None:
            return (self.down_held and not self.up_held and not self.ledge_hanging
                    and self._is_resting() and self.start_native_descent())
        if (
            not self.down_held
            or not self.shift_held
            or not self._at_rooftop_ledge()
            or self.ledge_action_consumed
            or self.ledge_hanging
        ):
            return False
        self.ledge_test_active = True
        if self.run_active:
            self.run_stop_requested = True
        if not self._is_resting() and self.sequence_state.sequence_id not in CROUCH_SEQUENCES:
            return False
        return self.start_ledge_hang()

    def start_ledge_climb(self):
        if not self.ledge_hanging:
            return False
        if self.native_ledge:
            if self.ledge_grip_delay or self.sequence_state.action not in range(87, 100):
                self.ledge_climb_requested = True
                return False
            self.ledge_climb_requested = False
            self.ledge_climbing = True
            ship = (self.harbor is not None
                    and self.harbor.hanging_from_ship(self.room_id, self.sequence_state))
            self.start_sequence(SHIP_CLIMB_SEQUENCE if ship else 10)
            self.status.set("Boarding the ship" if ship else "Climb: original SEQS:10 / 235")
            if not self.in_animation_tick:
                self.advance_animation_now()
            return True
        self.ledge_climb_requested = False
        self.ledge_climbing = True
        self.start_sequence(LEDGE_CLIMB_SEQUENCE)
        self.status.set("Climbing back onto the rooftop")
        if not self.in_animation_tick:
            self.advance_animation_now()
        return True

    def _begin_native_ledge(self, sequence_id, offset=0):
        self.run_active = self.run_stop_requested = False
        self.run_direction = 0
        self.pending_action = None
        self.jump_repeat_armed = False
        self.native_ledge = self.ledge_hanging = True
        self.ledge_climbing = self.ledge_climb_requested = False
        self.ledge_grip_delay = 12 if sequence_id == 15 else 0
        self.player_x += offset
        self.sequence_state.horizontal_velocity = self.sequence_state.vertical_velocity = 0
        self.sequence_state.sequence_mode = 0
        self.start_sequence(sequence_id)
        if sequence_id == 15:
            if getattr(self, "audio", None) is not None:
                self.audio.stop_sound(8)
            self.sequence_state.sound_events.append(9)
        self.status.set(f"Ledge: original SEQS:{sequence_id}")
        if not self.in_animation_tick:
            self.advance_animation_now()
        return True

    def start_native_descent(self):
        if (getattr(self, "level_map", None) is None or self.sword_drawn
                or self.ledge_hanging or self.terrain_motion.falling or self.terrain_motion.dead):
            return False
        state = self.sequence_state
        offset = self.level_map.descend_ledge(
            self.room_id, self.terrain_motion.row, state, self.frames[state.action])
        return offset is not None and self._begin_native_ledge(68, offset)

    def start_upper_ledge_jump(self):
        if (getattr(self, "level_map", None) is None or self.sword_drawn
                or self.ledge_hanging or self.terrain_motion.falling or self.terrain_motion.dead):
            return False
        state = self.sequence_state
        offset = self.level_map.upper_ledge(
            self.room_id, self.terrain_motion.row, state, self.frames[state.action])
        return offset is not None and self._begin_native_ledge(24, offset)

    def update_native_ledge(self):
        if not self.native_ledge or self.ledge_climbing:
            return
        state = self.sequence_state
        if state.action not in range(87, 100):
            return
        self.ledge_grip_delay = max(0, self.ledge_grip_delay - 1)
        # GenCtrl 6:18f2-1968: climbing takes priority over releasing Shift.
        if (self.up_held or self.ledge_climb_requested) and not self.ledge_grip_delay:
            self.start_ledge_climb()
        elif not self.shift_held or state.sequence_mode == 11:
            sequence, offset = self.level_map.release_ledge(
                self.room_id, self.terrain_motion.row, state, self.frames[state.action])
            self.ledge_hanging = self.native_ledge = False
            self.ledge_climb_requested = False
            self.terrain_motion.falling = sequence == 23
            self.sequence_state.sequence_mode = 0
            self.player_x += offset
            self.start_sequence(sequence)
            self.status.set("Released ledge")
        elif self.level_map.wall_supported_hang(
                self.room_id, self.terrain_motion.row, state, self.frames[state.action]):
            # Ordinary wall support enters SEQS:25 once. Mode 6 bypasses
            # that test so its settling poses can finish at stationary 91.
            self.start_sequence(25)

    def _is_running(self):
        return self.run_active or self.sequence_state.sequence_id in RUN_SEGMENT_SEQUENCES

    def _is_resting(self):
        state = self.sequence_state
        if state.sequence_id in REST_SEQUENCES:
            return True
        if state.sequence_id == JUMP_LANDING_SEQUENCE and state.action == 15:
            return True
        return False

    def clear_keys(self, _event):
        self.pause_resume_keys.clear()
        if _event is not None:
            self.window_keys_down.clear()
            self.escape_held = self.dev_toggle_held = False
        self.held_directions.clear()
        self.step_warning_direction = 0
        self.horizontal_input = 0
        self.up_held = False
        self.jump_started_for_press = False
        self.jump_repeat_armed = False
        self.down_held = False
        self.shift_held = False
        self.ctrl_held = False
        self.down_sheathe_consumed = False
        self.ledge_test_active = False
        self.ledge_action_consumed = False
        if self.run_active:
            self.run_stop_requested = True
        self.pending_action = None
        self.running_jump_controls_cleared = False

    def prepare_next_sequence(self, run_cycle_boundary=False):
        state = self.sequence_state
        # A short tap in the original branches after acceleration pose 8. The
        # remaining run poses (9-14) only play while the direction stays held.
        if (
            not run_cycle_boundary
            and self.run_stop_requested
            and self.pending_action is None
            and state.sequence_id == TAP_RELEASE_SEQUENCE
            and state.action == TAP_RELEASE_ACTION
        ):
            self.run_active = False
            self.run_stop_requested = False
            self.run_direction = 0
            self.start_sequence(RUN_STOP_SEQUENCE)
            return True

        if run_cycle_boundary:
            if self.pending_action is not None and self.dispatch_pending_action(
                was_running=True
            ):
                return True
            if self.run_stop_requested:
                self.run_active = False
                self.run_stop_requested = False
                self.run_direction = 0
                self.start_sequence(RUN_STOP_SEQUENCE)
                return True
            return False

        if self._is_resting():
            if self.pending_action is not None:
                return self.dispatch_pending_action()
            if (self.down_held and not self.up_held
                    and not self.down_sheathe_consumed and not self.ledge_hanging):
                if self._try_start_ledge_hang():
                    return True
                self.start_crouch_lower()
                return True
            if self.up_held and not self.jump_started_for_press and not self.ledge_hanging:
                self.start_jump()
                return True
            if self.horizontal_input and not self.up_held and not self.ledge_hanging:
                return self.queue_sampled_horizontal_action(self.horizontal_input)
        return False

    def dispatch_pending_action(self, was_running=False):
        if self._combat_controls_locked():
            return False
        command = self.pending_action
        if command is None:
            return False
        if command.kind == "crouch" and was_running:
            return False
        self.pending_action = None
        if command.kind in SWORD_SEQUENCES:
            return self.start_sword_action(command.kind)
        if command.kind == "crouch":
            if self.start_native_descent() or (
                    self.down_held and self.shift_held and self._try_start_ledge_hang()):
                return True
            self.start_crouch_lower()
            return True
        if command.kind == "crawl":
            self.start_crouch_step(command.direction)
            return True
        if command.kind == "jump":
            dispatched = self.dispatch_jump(command)
            if not dispatched and self.up_held:
                self.pending_action = command
            return dispatched
        dispatched = self.dispatch_horizontal_action(command, was_running=was_running)
        if (
            dispatched
            and command.mode == "run"
            and command.direction not in self.held_directions
            and self.run_active
            and self.run_direction == command.direction
        ):
            self.run_stop_requested = True
        return dispatched

    def advance_animation(self):
        self.animation_after_id = None
        if self.paused or getattr(self, "level_complete", False):
            return
        self.in_animation_tick = True
        if getattr(self, "intro", None) is not None:
            now = time.perf_counter()
            revision = self.intro.revision
            self.intro.advance(max(0, now - self.last_intro_at))
            self.last_intro_at = now
            if self.intro.done:
                self.finish_attract_stage()
            elif self.intro.revision != revision:
                self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        if getattr(self, "demo", None) is not None:
            now = time.perf_counter()
            self.demo.advance(max(0, now - self.last_demo_at))
            self.last_demo_at = now
            if self.demo.done:
                self.start_credits()
            else:
                self.apply_demo_frame()
            self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        retry_held = ({"space", "Shift_L", "Shift_R", "Control_L", "Control_R"}
                      & self.window_keys_down) - self.pause_resume_keys
        if self.death.can_restart and retry_held:
            self.restart_after_death()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        if self.combat is not None and not self.combat.player.alive:
            self.death.begin(0)
            # PlayerCtrl runs before AnimChar: count the previous dead pose,
            # not the first dead pose that this frame may be about to produce.
            self.death.advance(self.action, self.current_animation_interval_ms() / 1000,
                               getattr(self, "audio", None))
        self.sample_keyboard()
        old_x = self.sequence_state.target_x
        motion = getattr(self, "terrain_motion", None)
        old_bounds = self.player_bounds() if motion is not None else None
        if motion is not None and (motion.falling or motion.dead):
            self.sequence_runtime.next_frame()
            if (not motion.dead and not motion.hit_fall and self.combat.player.alive
                    and self.shift_held and not self.sword_drawn
                    and self.level_map.catch_ledge(motion.room, motion.row,
                        self.sequence_state, self.frames[self.sequence_state.action], self.harbor)):
                motion.falling = False
                self.player_x = self.sequence_state.target_x
                self._begin_native_ledge(15)
                self.sequence_runtime.next_frame()
                # Catch 4:38da-3928 aligns using the first caught pose (80).
                state = self.sequence_state
                self.level_map.align_catch(motion.room, motion.row, state, self.frames[state.action])
            self.advance_terrain(old_x, old_bounds)
            self.advance_combat()
            self.advance_harbor()
            self.advance_level_events()
            self.advance_rebirth()
            self.advance_audio()
            self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        if self._combat_controls_locked():
            # SwordCtrl may turn at a ready pose before the hurt sequence ends.
            self.resume_combat_turn()
            self.combat.advance_player_recovery()
            self.advance_terrain(old_x, old_bounds)
            self.advance_combat()
            self.advance_harbor()
            self.advance_level_events()
            self.advance_rebirth()
            self.advance_audio()
            self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        if self._opening_active():
            phase = self.opening.phase
            self.opening.advance()
            if phase == "fall" and self.opening.phase == "landing":
                self.sequence_state.sound_events.append(296)
            self.action = self.sequence_state.action
            self.player_x = self.sequence_state.target_x
            self.advance_combat()
            self.advance_audio()
            self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        self.update_running_jump_controls()
        if not self.resume_combat_turn():
            self.resume_sword_attack_after_block()
            self.resume_sword_controls()
        self.resume_crouch()
        self.resume_queued_action_during_run_stop()
        self.resume_run_during_standing_turn()
        self.resume_queued_turn_during_standing_turn()
        self.resume_drift_during_run()
        self.resume_queued_running_jump_during_run()
        self.resume_queued_crouch_during_run()
        self.resume_held_running_jump()
        self.resume_run_stop()
        self.update_native_ledge()
        if (
            self.ledge_climb_requested
            and self.sequence_state.sequence_id == LEDGE_HANG_SEQUENCE
        ):
            self.start_ledge_climb()
        sword_step_before_frame = self.sequence_state.sequence_id in SWORD_STEP_SEQUENCES
        if self.run_cycle_boundary_pending:
            self.run_cycle_boundary_pending = False
            frame = self.sequence_runtime.next_frame()
            self.player_x = self._clamp_rooftop_x(frame.target_x, frame.sequence_id)
            self.sequence_state.target_x = self.player_x
            self.sequence_state.current_x = self.player_x
            if self.prepare_next_sequence(run_cycle_boundary=True):
                frame = self.sequence_runtime.next_frame()
        else:
            self.prepare_next_sequence()
            frame = self.sequence_runtime.next_frame()
        if (
            frame.sequence_id == SWORD_GUARD_SEQUENCE
            and frame.action == 158
            and self.pending_action is not None
            and self.pending_action.kind in SWORD_SEQUENCES
            and self.pending_action.kind not in SWORD_STEP_KINDS
            and not sword_step_before_frame
        ):
            self.player_x = frame.target_x
            self.dispatch_pending_action()
            frame = self.sequence_runtime.next_frame()
        if self.sword_sheathing and frame.sequence_id == IDLE_SEQUENCE:
            self.sword_sheathing = False
            self.sword_drawn = False
            self.status.set("Sword sheathed")
            self.player_x = frame.target_x
            if self.prepare_next_sequence():
                frame = self.sequence_runtime.next_frame()
        # Consume one buffered command at the transition, before drawing idle.
        if frame.action == 15 and frame.sequence_id in (
            JUMP_LANDING_SEQUENCE, IDLE_SEQUENCE
        ):
            self.player_x = frame.target_x
            if self.pending_action is not None and self.dispatch_pending_action():
                frame = self.sequence_runtime.next_frame()
            elif (
                self.up_held
                and self.jump_started_for_press
                and self.jump_repeat_armed
                and not self.ledge_hanging
            ):
                self.jump_started_for_press = False
                self.start_jump()
                frame = self.sequence_runtime.next_frame()
        if frame.sequence_id == IDLE_SEQUENCE and self._try_start_ledge_hang():
            frame = self.sequence_runtime.next_frame()
        self.action = frame.action
        self.player_x = self._clamp_rooftop_x(frame.target_x, frame.sequence_id)
        self.sequence_state.target_x = self.player_x
        self.sequence_state.current_x = self.player_x
        if frame.sequence_id == 202 and frame.action == 14:
            self.run_cycle_boundary_pending = True
        if frame.sequence_id == IDLE_SEQUENCE and self.run_active:
            self.run_active = False
            self.run_stop_requested = False
        if (
            frame.action == 15
            and frame.sequence_id in (JUMP_LANDING_SEQUENCE, IDLE_SEQUENCE)
            and not self.up_held
        ):
            self.jump_started_for_press = False
            self.jump_repeat_armed = False
        if self.ledge_climbing and frame.sequence_id == IDLE_SEQUENCE:
            self.ledge_hanging = False
            self.ledge_climbing = False
            self.native_ledge = False
            self.sequence_state.current_y = 0
            self.sequence_state.horizontal_velocity = 0
            self.sequence_state.vertical_velocity = 0
            self.status.set("Back on the rooftop")
        if (motion is not None and self.ledge_hanging and not self.ledge_climbing
                and not self.shift_held and self.sequence_state.sequence_id == LEDGE_HANG_SEQUENCE):
            self.ledge_hanging = False
            self.ledge_climb_requested = False
            motion.falling = True
            motion.row += 1
            self.sequence_state.current_y -= TILE_HEIGHT
            self.physics.select(self.sequence_runtime, 23)
        old_room = motion.room if motion is not None else None
        self.advance_terrain(old_x, old_bounds)
        # A room cut rebases X; it must not be swept as a cross-room jump.
        self.advance_combat(old_x if motion is None or motion.room == old_room else None)
        self.advance_harbor()
        self.advance_level_events()
        self.advance_rebirth()
        self.advance_audio()
        self.render()
        self.in_animation_tick = False
        self.schedule_next_animation()

    def _opening_active(self):
        opening = getattr(self, "opening", None)
        return opening is not None and opening.active

    def _combat_controls_locked(self):
        if getattr(self, "level_complete", False):
            return True
        motion = getattr(self, "terrain_motion", None)
        if motion is not None and (motion.falling or motion.dead):
            return True
        combat = getattr(self, "combat", None)
        return combat is not None and combat.player.controls_locked

    def player_floor_y(self):
        motion = getattr(self, "terrain_motion", None)
        return floor_y(motion.row) if motion is not None else START_FLOOR_Y

    def player_bounds(self):
        action = self.sequence_state.action
        sprite = self.player_sprite(action)
        if sprite is None:
            return (self.player_x, self.player_floor_y(), self.player_x, self.player_floor_y())
        record = self.frames[action]
        anchor = sprite.width - record.offset_x if self.sequence_state.facing else record.offset_x
        left = self.sequence_state.target_x - anchor
        bottom = self.player_floor_y() + self.sequence_state.current_y + record.offset_y
        return left, character_sprite_top(bottom, sprite.height), left + sprite.width - 1, bottom

    def advance_terrain(self, old_x, old_bounds=None):
        motion = getattr(self, "terrain_motion", None)
        if motion is None or self._opening_active():
            return
        if self.native_ledge:
            # SEQS -3/-4 change the native floor row while -6 changes the
            # absolute Y. Preserve that position in our floor-relative model.
            delta = self.sequence_state.engine_counter
            if delta:
                motion.row += delta
                self.sequence_state.current_y -= delta * TILE_HEIGHT
                self.sequence_state.engine_counter = 0
        self.action = self.sequence_state.action
        old_room = self.room_id
        before_x = self.sequence_state.target_x
        command = self.pending_action
        braking_for_jump = (self.sequence_state.sequence_id == RUN_STOP_SEQUENCE
                            and command is not None and command.kind == "jump"
                            and not command.direction)
        events = self.physics.advance(
            motion, self.sequence_runtime, old_x, self.player_bounds(),
            sword_drawn=self.sword_drawn, protected=self.ledge_hanging or self.ledge_climbing,
            frame_record=self.frames[self.action], bounds_for_state=self.player_bounds,
            old_bounds=old_bounds, alive=self.combat.player.alive)
        if motion.room != old_room:
            dx = self.sequence_state.target_x - before_x
            if motion.room not in self.room_cache:
                try:
                    self.level_renderer.room(motion.room)
                except ValueError as error:
                    # Keep the playable section intact at unsupported scenery.
                    motion.room = old_room
                    motion.falling = False
                    self.sequence_state.current_x = self.sequence_state.target_x = old_x
                    self.run_active = False
                    self.run_stop_requested = False
                    self.run_cycle_boundary_pending = False
                    self.pending_action = None
                    self.start_sequence(IDLE_SEQUENCE)
                    self.sequence_runtime.next_frame()
                    self.player_x = self.sequence_state.target_x
                    self.action = self.sequence_state.action
                    self.status.set(str(error))
                    return
            if self.run_start_x is not None:
                self.run_start_x += dx
            self.room_id = motion.room
            room = self.room_cache[self.room_id]
            self.background, self.foreground = room.background, room.foreground
            self.combat.enter_room(self.room_id, motion.row)
            if self.harbor is not None:
                self.harbor.enter_room(self.room_id, self.action)
            self.status.set(f"Screen {self.screen_label(self.room_id)}")
        self.combat.player.row = motion.row
        for event in events:
            if event.kind == "fall":
                # StartFall 4:4ca8-4cb2 puts the drawn sword away immediately.
                self.sword_drawn = self.combat.player.sword_drawn = False
                self.combat.player.recovering = False
            if event.kind in ("land", "death"):
                if getattr(self, "audio", None) is not None:
                    self.audio.stop_sound(8)
            if event.kind in ("fall", "wall", "death"):
                # The collision/fall sequence has interrupted PutSwordAway.
                # Its Python-side lock must not outlive that animation.
                self.sword_sheathing = False
                self.run_active = False
                self.run_stop_requested = False
                self.run_cycle_boundary_pending = False
                # A grounded bump can replace braking without discarding the
                # Up waiting for that brake. An airborne bump still cancels it.
                self.pending_action = (command if event.kind == "wall" and braking_for_jump
                                       and not motion.falling else None)
                self.jump_repeat_armed = False
                # Do not re-arm a consumed Up on wall contact: releasing Up
                # must not queue a second jump after an interrupted jump.
                if event.kind != "wall":
                    self.jump_started_for_press = False
            if event.kind == "death":
                self.combat.player.life = 0
                self.death.begin(3 if not motion.falling else 0)
                self.status.set("Defeated")
            elif event.damage:
                self.combat.player.life = max(0, self.combat.player.life - event.damage)
                if not self.combat.player.alive:
                    motion.dead = True
                    self.death.begin(3)
                    self.physics.select(self.sequence_runtime, 22)
            elif event.kind == "land" and self.sword_drawn:
                self.combat.player.recovering = True
        self.action = self.sequence_state.action
        self.player_x = self.sequence_state.target_x
        self.sequence_state.current_x = self.player_x

    def advance_harbor(self):
        motion = getattr(self, "terrain_motion", None)
        if motion is None or self.harbor is None:
            return
        state = self.sequence_state
        if (state.sequence_id == SHIP_CLIMB_SEQUENCE
                or self.harbor.hanging_from_ship(motion.room, state)):
            state.target_x -= 2
            state.current_x = state.target_x
        self.harbor.advance()
        if not motion.dead and self.harbor.right_exit_is_fatal(motion.room, state):
            self.clear_keys(None)
            motion.dead, motion.falling = True, False
            self.native_ledge = self.ledge_hanging = self.ledge_climbing = False
            state.horizontal_velocity = state.vertical_velocity = 0
            state.sound_events.append(34)
            self.physics.select(self.sequence_runtime, 71)
            self.combat.player.life = 0
            self.death.begin(14)
            self.status.set("Defeated")
        bounds = self.player_bounds()
        if not motion.dead and self.harbor.watch_water(
                0, motion.room, motion.row, state, bounds[2] - bounds[0] + 1):
            self.clear_keys(None)
            self.native_ledge = self.ledge_hanging = self.ledge_climbing = False
            motion.dead = True
            motion.falling = False
            state.horizontal_velocity = state.vertical_velocity = 0
            state.animation_state, state.action = 1, 185
            state.selected_sequence_id = 22
            state.sequence_id, state.cursor = 22, len(self.sequences[22]) - 1
            self.combat.player.life = 0
            self.death.begin(15)
            self.status.set("Defeated")
        if not self.peaceful:
            for guard in self.combat.active_guards():
                if guard.terrain_motion is not None and not guard.terrain_motion.dead:
                    bounds = self.guard_art.bounds(guard.state, floor_y(guard.row))
                    if self.harbor.watch_water(id(guard), guard.room, guard.row, guard.state,
                                               bounds[2] - bounds[0] + 1):
                        guard.life = 0
                        guard.targetable = False
                        guard.terrain_motion.dead = True
                        guard.state.horizontal_velocity = guard.state.vertical_velocity = 0
                        guard.state.action, guard.state.animation_state = 185, 1
                        guard.state.selected_sequence_id = 22
                        guard.state.sequence_id, guard.state.cursor = 22, len(self.sequences[22]) - 1
        self.player_x, self.action = state.target_x, state.action

    def advance_level_events(self):
        if self.game.consume_completion():
            self.clear_keys(None)
            self.status.set(f"Level {self.game.level.number} complete")

    def resume_combat_turn(self):
        combat = getattr(self, "combat", None)
        # A newly selected command still needs its first AnimChar frame.
        if (combat is None or getattr(self, "peaceful", False) or self.sword_sheathing
                or self.sequence_state.cursor == 0):
            return False
        combat.player.sword_drawn = self.sword_drawn
        combat.player.targetable = not (
            self._opening_active() or self.ledge_hanging or self.ledge_climbing
            or (getattr(self, "terrain_motion", None) is not None and self.terrain_motion.falling)
        )
        record = (self.frames[self.sequence_state.action]
                  if getattr(self, "level_map", None) is not None else None)
        if combat.choose_player_turn(record):
            self.status.set("Turning toward opponent")
            return True
        return False

    def advance_combat(self, old_x=None):
        combat = getattr(self, "combat", None)
        if combat is None:
            return
        combat.player.sword_drawn = self.sword_drawn
        combat.player.targetable = not (
            self._opening_active() or self.ledge_hanging or self.ledge_climbing
            or (getattr(self, "terrain_motion", None) is not None and self.terrain_motion.falling)
        )
        if getattr(self, "peaceful", False):
            combat.world_frame += 1
            combat.last_guard_at = time.perf_counter()
            return
        if combat.choose_player_bump(old_x):
            self.run_active = self.run_stop_requested = False
            self.run_cycle_boundary_pending = False
            self.pending_action = None
            self.jump_repeat_armed = False
            self.action = self.sequence_state.action
            self.player_x = self.sequence_state.target_x
            self.status.set("Blocked by opponent")
        events = combat.step(
            time.perf_counter(), self.current_animation_interval_ms() / 1000,
        )
        for event in events:
            self.sequence_state.sound_events.append(
                11 if event.kind == "parry" else 12 if event.actor == "player" else 31)
            if event.actor == "player" and event.kind in ("hit", "death"):
                self.sword_drawn = combat.player.sword_drawn
                self.pending_action = None
                self.run_active = False
                self.run_direction = 0
                self.run_stop_requested = False
                self.run_cycle_boundary_pending = False
                self.sword_sheathing = False
                self.jump_started_for_press = False
                self.jump_repeat_armed = False
                if event.kind == "death":
                    self.clear_keys(None)
                    self.death.begin(event.death_method)
            self.status.set({"hit": "Hit", "death": "Defeated", "parry": "Parried"}[event.kind])
        self.action = self.sequence_state.action
        if not self._opening_active():
            self.sequence_state.target_x = self._clamp_rooftop_x(
                self.sequence_state.target_x, self.sequence_state.sequence_id)
        self.player_x = self.sequence_state.target_x
        self.sequence_state.current_x = self.player_x

    def advance_rebirth(self):
        motion = getattr(self, "terrain_motion", None)
        if self.combat is None or motion is None or self.level_complete:
            return
        if not self.combat.player.alive:
            self.death.begin(0)
            return
        state = self.sequence_state
        contact = floor_contact_x(state.target_x, state.facing, self.frames[state.action])
        for checkpoint in self.checkpoints:
            if checkpoint.matches(motion.room, motion.row, contact,
                                  state.animation_state, self.combat.player.alive,
                                  level_number=self.game.level.number):
                if self.checkpoint is None or self.checkpoint.checkpoint != checkpoint:
                    self.checkpoint = RebirthSnapshot.capture(checkpoint, self.combat)
                break

    def advance_audio(self):
        if getattr(self, "intro", None) is not None:
            return
        audio = getattr(self, "audio", None)
        if audio is None:
            return
        if self.sequence_state.action == 167:
            self.sequence_state.sound_events.append(10)
        elif self.sequence_state.action == 154:
            # TestStrike 6:5876-588a / 5b00-5b1c also sounds an empty swing.
            self.sequence_state.sound_events.append(11)
        audio.drain(self.sequence_state)
        if self.combat is not None:
            for guards, _generators in self.combat.room_encounters.values():
                for guard in guards:
                    if guard.state.action == 167:
                        guard.state.sound_events.append(10)
                    elif guard.state.action == 154 and contact_allowed(guard, self.combat.player):
                        # NPCs use 6:5ab4-5af8, after the valid-target gate.
                        guard.state.sound_events.append(11)
                    audio.drain(guard.state, not self.peaceful and guard.room == self.room_id)
        motion = getattr(self, "terrain_motion", None)
        if motion is not None and not self.level_complete and self.game.level.number == 1:
            fighting = (self.sword_drawn and not self.peaceful
                        and any(guard.alive and guard.row == motion.row
                                for guard in self.combat.active_guards()))
            contact = floor_contact_x(self.sequence_state.target_x,
                                     self.sequence_state.facing, self.frames[self.action])
            audio.ambient(self.room_id, motion.row, max(0, min(9, int(contact // 51))),
                          fighting, self.combat.player.alive)
        audio.flush()

    def restart_after_death(self):
        if not self.death.can_restart:
            return False
        self.restart_level()
        return True

    def restart_level(self):
        held = set(self.window_keys_down)
        snapshot = self.checkpoint
        if snapshot is None:
            max_life = self.combat.player.max_life if self.combat is not None else None
            self.restart_opening()
            if max_life is not None:
                self.combat.player.life = self.combat.player.max_life = max_life
                self.render()
        else:
            if self.animation_after_id is not None:
                self.root.after_cancel(self.animation_after_id)
                self.animation_after_id = None
            snapshot.restore_world(self.combat)
            point = snapshot.checkpoint
            self.jump_to_room(point.room, point.row, point.x, snapshot.facing,
                              reset_guards=False, preserve_checkpoint=True)
            self.next_animation_at = time.perf_counter()
            if not self.in_animation_tick:
                self.schedule_next_animation()
        self.pause_resume_keys.update(held)

    def start_intro(self, part_index=None):
        from pop2.intro import IntroAssets, IntroPlayer

        self.end_demo()
        self.attract_stage = "intro"
        if self.intro_assets is None:
            self.intro_assets = IntroAssets()
        if self.audio is not None:
            self.audio.reset()
        self.clear_keys(None)
        self.level_complete = False
        self.intro = IntroPlayer(self.intro_assets, self.audio if part_index is None else None)
        if part_index is not None:
            self.intro.audio = self.audio
            self.intro.seek_operation(part_index)
        self.last_intro_at = time.perf_counter()
        self.status.set("Introduction")

    def development_parts(self):
        if not self.with_intro:
            return ()
        from pop2.attract import read_attract
        from pop2.paths import ASSET_DIR
        from pop2.playback_navigation import playback_parts

        if self.attract_data is None:
            self.attract_data = read_attract(ASSET_DIR / "attract.json")
        return playback_parts(self.intro_assets, self.attract_data, self.screen_label)

    def current_playback_part(self):
        stage = self.attract_stage
        position = (self.demo.index if stage == "demo" else
                    self.intro.position - 1 if stage == "intro" else
                    self.intro.page_index if stage == "credits" else -1)
        matches = [index for index, part in enumerate(self.development_parts())
                   if part.stage == stage and part.index <= position]
        return matches[-1] if matches else 0

    def seek_playback_part(self, part):
        # Always construct the destination's own state; demo actors never
        # become live combat actors or carry their inputs into gameplay.
        self.intro = None
        if part.stage == "intro":
            self.start_intro(part.index)
        elif part.stage == "demo":
            self.start_demo(part.index)
        elif part.stage == "credits":
            self.start_credits(part.index)
        else:
            raise ValueError("Unknown playback stage")
        self.last_intro_at = self.last_demo_at = time.perf_counter()
        self.clear_keys(None)

    def finish_attract_stage(self):
        if self.attract_stage == "credits":
            self.start_intro()
        else:
            self.start_demo()
        self.render()

    def start_demo(self, part_index=None):
        from pop2.attract import DemoEncounter, DemoPlayer, read_attract
        from pop2.paths import ASSET_DIR

        if self.attract_data is None:
            self.attract_data = read_attract(ASSET_DIR / "attract.json")
        self.restart_opening(play_sound=part_index is None)
        self.attract_stage = "demo"
        self.live_combat = self.combat
        self.combat = DemoEncounter(self.level_map, self.sequence_runtime)
        self.demo = DemoPlayer(self.attract_data, self.audio if part_index is None else None)
        if part_index is not None:
            self.demo.audio = self.audio
            self.demo.seek_frame(part_index)
        self.last_demo_at = time.perf_counter()
        self.apply_demo_frame()
        self.status.set("Demo")

    def apply_demo_frame(self):
        frame = self.demo.frame
        self.combat.apply(frame, self.demo.index)
        self.room_id = frame["room"] - 1
        room = self.level_renderer.room(self.room_id)
        self.background, self.foreground = room.background, room.foreground
        self.terrain_motion = TerrainMotion(self.room_id, self.combat.player.row)
        self.action, self.player_x = self.sequence_state.action, self.sequence_state.target_x
        self.sword_drawn = self.combat.player.sword_drawn
        self.opening.tick = self.demo.index
        self.opening.active = False

    def end_demo(self):
        self.demo = None
        if getattr(self, "live_combat", None) is not None:
            self.combat, self.live_combat = self.live_combat, None

    def start_credits(self, part_index=None):
        from pop2.attract import CreditsAssets, CreditsPlayer

        self.end_demo()
        if self.credits_assets is None:
            self.credits_assets = CreditsAssets(self.attract_data)
        self.attract_stage = "credits"
        self.intro = CreditsPlayer(self.credits_assets, self.audio if part_index is None else None)
        if part_index is not None:
            self.intro.seek_page(part_index, self.audio)
        self.last_intro_at = time.perf_counter()
        self.status.set("Credits")

    def new_game(self):
        if self.game.level.number != 1:
            self.load_level(1)
        self.restart_opening(play_sound=not self.with_intro)
        if self.with_intro:
            self.start_intro()
            self.render()

    def finish_intro(self):
        held = set(self.window_keys_down)
        self.restart_opening()
        self.pause_resume_keys.update(held)

    def restart_opening(self, _event=None, play_sound=True):
        self.end_demo()
        self.attract_stage = None
        self.intro = None
        audio = getattr(self, "audio", None)
        if audio is not None:
            audio.reset()
            if play_sound and self.game.level.window_escape:
                audio.add_sound(36)
        if self.animation_after_id is not None:
            self.root.after_cancel(self.animation_after_id)
            self.animation_after_id = None
        self.clear_keys(None)
        self.game.restart()
        self.reset_level_controls()
        room = self.level_renderer.room(self.room_id) if hasattr(self, "level_renderer") else None
        if room is not None:
            self.background, self.foreground = room.background, room.foreground
        self.action = self.sequence_state.action
        self.player_x = self.sequence_state.target_x
        self.status.set("Window escape" if self._opening_active() else f"Level {self.game.level.number}")
        if play_sound:
            self.advance_audio()
        self.render()
        self.next_animation_at = time.perf_counter()
        if not self.in_animation_tick:
            self.schedule_next_animation()
        return "break"

    def reset_level_controls(self):
        self.run_active = False
        self.run_stop_requested = False
        self.run_direction = 0
        self.run_start_x = None
        self.run_cycle_boundary_pending = False
        self.sword_drawn = False
        self.step_cautious = True
        self.sword_sheathing = False
        self.ledge_hanging = False
        self.ledge_climbing = False
        self.ledge_climb_requested = False
        self.ledge_action_consumed = False
        self.native_ledge = False
        self.ledge_grip_delay = 0
        self.down_sheathe_consumed = False

    def dev_rooms(self):
        if self.level_map is None:
            return []
        return self.level_renderer.supported_rooms()

    def jump_to_room(self, room_id, row=1, x=None, facing=None, reset_guards=True,
                     preserve_checkpoint=False):
        if self.level_map is None or not 0 <= room_id < 32 or not 0 <= row < 3:
            raise ValueError("Invalid level, room or floor")
        room = self.level_renderer.room(room_id)
        if x is None:
            columns = [column for column in range(10)
                       if self.level_map.tile(room_id, column, row).kind == 1]
            if not columns:
                raise ValueError("This floor has no standing position")
            x = columns[len(columns) // 2] * TILE_WIDTH + 14
        if not 0 <= x < ROOM_WIDTH:
            raise ValueError("X must be between 0 and 509")
        self.end_demo()
        self.attract_stage = None
        self.intro = None
        self.clear_keys(None)
        self.game.place(room_id, row, x,
                        self.sequence_state.facing if facing is None else facing,
                        reset_guards, preserve_checkpoint)
        self.reset_level_controls()
        self.background, self.foreground = room.background, room.foreground
        self.player_x, self.action = x, 15
        if getattr(self, "audio", None) is not None:
            self.audio.reset()
            self.advance_audio()
        self.status.set(f"Level {self.game.level.number} / Screen {self.screen_label(room_id)}")
        self.render()

    def dev_screens(self):
        return self.level_renderer.screen_entries() if self.level_map is not None else {}

    def screen_label(self, room):
        return next((label for label, target in self.dev_screens().items() if target == room),
                    f"Room ID {room + 1}")

    def jump_to_screen(self, label):
        screens = self.dev_screens()
        room = screens[label]
        if room == self.level_map.start_room:
            return self.jump_to_room(room, row=1, x=411, facing=1)
        secret = label == "Secret (right)"
        if secret:
            row, column = next((row, column) for row in range(3) for column in range(10)
                               if self.level_map.tile(room, column, row).kind == 1)
            return self.jump_to_room(room, row=row, x=column * TILE_WIDTH + 30, facing=1)
        if label == "8":
            # Entry from screen 7 is the upper roof, not the quay below.
            row, x = 0, 5 * TILE_WIDTH + 14
        else:
            rows = [row for row in range(3)
                    if self.level_map.tile(room, 9, row).kind == 1]
            if not rows:
                raise ValueError("This screen has no supported entry")
            row, x = rows[0], ROOM_WIDTH - 15
        self.jump_to_room(room, row=row, x=x, facing=0)
        # A dev warp simulates progress along the route, including the last
        # LEVL checkpoint it would pass. Normal play still uses the cell gate.
        route = list(screens.values())[:list(screens).index(label) + 1]
        checkpoint = max((point for point in self.checkpoints if point.room in route),
                         key=lambda point: route.index(point.room), default=None)
        if checkpoint is not None:
            self.checkpoint = RebirthSnapshot.capture(checkpoint, self.combat)


    def advance_animation_now(self):
        if not hasattr(self, "root") or self.in_animation_tick:
            return
        if self.animation_after_id is not None:
            self.root.after_cancel(self.animation_after_id)
            self.animation_after_id = None
        self.next_animation_at = time.perf_counter()
        self.advance_animation()

    def current_animation_interval_ms(self):
        if getattr(self, "intro", None) is not None or getattr(self, "demo", None) is not None:
            return 1000 / 60
        interval_ms = animation_interval_for_frame(
            self.sequence_state.sequence_id, self.sequence_state.action)
        if self._combat_controls_locked() and self.sword_drawn:
            interval_ms = COMBAT_ANIMATION_INTERVAL_MS
        return interval_ms

    def schedule_next_animation(self):
        if self.paused or getattr(self, "level_complete", False):
            return
        now = time.perf_counter()
        if getattr(self, "intro", None) is not None:
            # Intro time was sampled before rendering. Do not add render cost
            # to the next script deadline or quantize it to the host's 60 Hz.
            self.next_animation_at = self.last_intro_at + self.intro.next_update_delay()
            # A zero-delay chain starves Tk's idle redraws when fullscreen
            # presentation costs more than the fade/dissolve frame budget.
            delay_ms = max(1, math.ceil((self.next_animation_at - now) * 1000))
        elif getattr(self, "demo", None) is not None:
            self.next_animation_at = self.last_demo_at + self.demo.next_update_delay()
            delay_ms = max(1, math.ceil((self.next_animation_at - now) * 1000))
        else:
            self.next_animation_at, delay_ms = next_animation_deadline(
                self.next_animation_at, now,
                interval_ms=self.current_animation_interval_ms(),
            )
        self.animation_after_id = self.root.after(delay_ms, self.advance_animation)

    def player_sprite(self, action=None):
        shape_id = shape_id_for_action(self.frames, self.first_shape_id,
                                      self.action if action is None else action)
        if shape_id is None:
            return None
        if shape_id not in self.sprite_cache:
            data = self.kid["SHAP"].get(shape_id)
            if data is None:
                return None
            self.sprite_cache[shape_id] = decode_shap(data["data"], self.palette)
        return self.sprite_cache[shape_id]

    def sword_sprite(self):
        attachment_type, shape_index, dx, dy = self.attachment_frames[
            self.frames[self.action].afrm_index
        ]
        if attachment_type != 1 or shape_index < 0:
            return None
        shape_id = self.first_sword_shape_id + shape_index
        if shape_id not in self.sword_sprite_cache:
            self.sword_sprite_cache[shape_id] = decode_shap(
                self.sword_shapes[shape_id]["data"], self.sword_palette
            )
        return self.sword_sprite_cache[shape_id], dx, dy

    def composite_actor(self, frame, layer, row=None, bottom=None, state=None, bounds=None, record=None):
        # An upper roof's foreground must not erase a lower-row fall.
        rooms = getattr(self, "room_cache", {})
        room = rooms.get(getattr(self, "room_id", None))
        mask = (room.actor_mask(row, bottom, state, bounds, record)
                if room is not None and row is not None else self.foreground.getchannel("A"))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), ImageChops.invert(mask)))
        if self.room_id in (15, 18):
            water_y = 354 if state is not None and state.animation_state == 9 else 327
            layer.paste((0, 0, 0, 0), (0, water_y, layer.width, layer.height))
        return Image.alpha_composite(frame, layer)

    def draw_cutscene_pause(self, viewport):
        viewport = Image.alpha_composite(
            viewport, Image.new("RGBA", viewport.size, (0, 0, 0, 100)))
        text = self.cutscene_pause_text
        ink = text.getbbox()
        x = (VIEWPORT_WIDTH - text.width) // 2
        y = (VIEWPORT_HEIGHT - (ink[3] - ink[1])) // 2 - ink[1]
        viewport.paste((0, 0, 0, 255),
                       (x + 1, y + 1, x + 1 + text.width, y + 1 + text.height), text)
        viewport.paste(text, (x, y), text)
        return viewport

    def render(self):
        if getattr(self, "intro", None) is not None:
            viewport = Image.new("RGBA", (VIEWPORT_WIDTH, VIEWPORT_HEIGHT), (0, 0, 0, 255))
            viewport.paste(self.intro.frame().crop((0, 0, ROOM_WIDTH, VIEWPORT_HEIGHT)),
                           (ROOM_ORIGIN_X, 0))
            if self.dev_menu is not None:
                viewport = self.dev_menu.draw(viewport, self.ui_font)
            elif self.game_menu is not None:
                self.refresh_game_menu()
                viewport = self.game_menu.draw(viewport, self.ui_font)
            elif self.paused:
                viewport = self.draw_cutscene_pause(viewport)
            self.native_viewport = viewport
            self.present_viewport()
            return
        frame = self.background.copy()
        frame = self.level_renderer.animated_layer(frame, self.room_id, self.harbor)
        opening = getattr(self, "opening", None)
        show_opening = opening is not None and (
            getattr(self, "level_map", None) is None or self.room_id == self.level_map.start_room)
        if show_opening:
            curtain_index = opening.curtain_frame
            curtain = self.curtain_sprites[curtain_index]
            dx, dy = ROOF_GLASS_OFFSETS[curtain_index]
            frame.paste(curtain, (
                5 * TILE_WIDTH + dx,
                TILE_HEIGHT + SCENERY_Y_OFFSET + dy - curtain.height,
            ), curtain)
        combat = getattr(self, "combat", None)
        frame = Image.alpha_composite(frame, self.foreground)
        hide_guards = getattr(self, "peaceful", False) and getattr(self, "demo", None) is None
        if combat is not None and not hide_guards:
            for guard in combat.visible_guards():
                layer = Image.new("RGBA", frame.size)
                self.guard_art.draw(layer, guard.state, floor_y(guard.row), guard.palette_variant)
                bounds = self.guard_art.bounds(guard.state, floor_y(guard.row))
                record = self.guard_art.frames[guard_frame_index(guard.state.action)]
                frame = self.composite_actor(frame, layer, guard.row, bounds[3],
                                             guard.state, bounds, record)
        player_layer = Image.new("RGBA", frame.size)
        sprite = self.player_sprite()
        if sprite is not None:
            record = self.frames[self.action]
            anchor_x = record.offset_x
            if self.sequence_state.facing:
                sprite = ImageOps.mirror(sprite)
                anchor_x = sprite.width - anchor_x
            x = self.player_x - anchor_x
            y = character_sprite_top(
                self.player_floor_y()
                + record.offset_y
                + self.sequence_state.current_y,
                sprite.height,
            )
            player_layer.paste(sprite, (x, y), sprite)
            attachment = self.sword_sprite()
            if attachment is not None:
                sword, dx, dy = attachment
                if self.sequence_state.facing:
                    sword = ImageOps.mirror(sword)
                    sword_x = x + sprite.width + dx - sword.width
                else:
                    sword_x = x - dx
                sword_y = y + sprite.height + dy - sword.height
                player_layer.paste(sword, (sword_x, sword_y), sword)

        motion = getattr(self, "terrain_motion", None)
        player_bounds = self.player_bounds() if motion is not None else None
        frame = self.composite_actor(frame, player_layer, motion.row if motion is not None else None,
                                     player_bounds[3] if player_bounds is not None else None,
                                     self.sequence_state, player_bounds, self.frames[self.action])

        if combat is not None:
            for guard in (() if hide_guards else combat.visible_guards()):
                layer = Image.new("RGBA", frame.size)
                self.hit_art.draw(layer, guard.state, floor_y(guard.row))
                bounds = self.guard_art.bounds(guard.state, floor_y(guard.row))
                frame = self.composite_actor(frame, layer, guard.row, bounds[3])
            layer = Image.new("RGBA", frame.size)
            self.hit_art.draw(layer, combat.player.state, self.player_floor_y())
            frame = self.composite_actor(frame, layer, motion.row if motion is not None else None,
                                         player_bounds[3] if player_bounds is not None else None,
                                         self.sequence_state, player_bounds, self.frames[self.action])
        if show_opening and opening.glass_frame is not None:
            glass = self.glass_sprites[opening.glass_frame]
            glass_x, glass_y = GLASS_POSITIONS[opening.glass_frame]
            layer = Image.new("RGBA", frame.size)
            layer.paste(glass, (glass_x, character_sprite_top(glass_y, glass.height)), glass)
            frame = self.composite_actor(frame, layer)
        frame = self.level_renderer.animated_layer(frame, self.room_id, self.harbor, front=True)
        viewport = Image.new("RGBA", (VIEWPORT_WIDTH, VIEWPORT_HEIGHT), (0, 0, 0, 255))
        viewport.paste(frame, (ROOM_ORIGIN_X, 0))
        if combat is not None and not self.death.prompt_visible:
            self.health_art.draw(viewport, combat, show_opponent=not hide_guards)
        hud_text = (self.pause_text if self.paused else
                    self.restart_text if self.death.prompt_visible else None)
        demo_paused = self.paused and getattr(self, "demo", None) is not None
        if (hud_text is not None and not demo_paused
                and self.dev_menu is None and self.game_menu is None):
            ink = hud_text.getbbox()
            pause_y = ROOM_HEIGHT + (VIEWPORT_HEIGHT - ROOM_HEIGHT - (ink[3] - ink[1])) // 2 - ink[1]
            viewport.paste(hud_text, ((VIEWPORT_WIDTH - hud_text.width) // 2,
                                      pause_y), hud_text)
        if self.level_complete and self.dev_menu is None and self.game_menu is None:
            text = self.ui_font.text(f"Level {self.game.level.number} Complete")
            viewport.paste(text, ((VIEWPORT_WIDTH - text.width) // 2, ROOM_HEIGHT), text)
        if demo_paused and self.dev_menu is None and self.game_menu is None:
            viewport = self.draw_cutscene_pause(viewport)
        if self.dev_menu is not None:
            viewport = self.dev_menu.draw(viewport, self.ui_font)
        if self.game_menu is not None:
            self.refresh_game_menu()
            viewport = self.game_menu.draw(viewport, self.ui_font)
        self.native_viewport = viewport
        self.present_viewport()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-guard", action="store_true", help="Isolated animation comparison")
    parser.add_argument("--peaceful", action="store_true", help="Rooftop terrain test without guards")
    parser.add_argument("--skip-intro", action="store_true", help="Start directly in level 1")
    args = parser.parse_args()
    from pop2.audio import AudioEngine
    audio = AudioEngine()
    try:
        ScenePrototype(with_guard=not args.no_guard, peaceful=args.peaceful, audio=audio,
                       with_intro=not args.skip_intro and not args.no_guard).run()
    finally:
        audio.close()
