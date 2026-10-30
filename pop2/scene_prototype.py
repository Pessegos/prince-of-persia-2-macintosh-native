import argparse
import math
import time
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

from pop2.animation_data import (
    character_collision_bounds,
    shape_id_for_action,
)
from pop2.combat import (
    PLAYER_COMBAT_TURN_SEQUENCE, actor_frame_index, contact_allowed,
)
from pop2.combat_art import (
    GuardArtwork, HealthArtwork, HitArtwork, actor_draw_order, slab_crush_draw_state,
    sword_palette_for_level,
)
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
from pop2.mac_input import plan_cautious_step, plan_step, read_keyboard, sample_modifier
from pop2.opening_animation import GLASS_POSITIONS
from pop2.harbor import SHIP_CLIMB_SEQUENCE
from pop2.rebirth import RebirthSnapshot
from pop2.story_progress import MESSAGE_FRAMES, StoryProgress
from pop2.game_session import GameResources, GameSession
from pop2.level_rendering import LevelRenderer
from pop2.environments import environment_for
from pop2.carpet import carpet_room
from pop2.caverns import cavern_clip_top, cavern_exit_clip
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
from pop2.opponent_generation import character_column
from pop2.coordinates import column_left
from pop2.terrain import TerrainMotion, floor_y, floor_contact_x
from pop2.crevices import (
    CREVICE_TILE,
    LIE_DOWN_SEQUENCE,
)
from pop2.game_ui import MacintoshFont
from pop2.window_controls import WindowControls, PAUSE_GAMEPLAY_KEYS, RESUME_COMMAND_KEYS
from pop2.running_controls import RUN_INPUT_SEQUENCES
from pop2.airborne_controls import AIRBORNE_TAKEOFF_SEQUENCES
from pop2.low_controls import LowControls, LOW_INPUT_SEQUENCES
from pop2.armed_controls import ArmedControls
from pop2.sword_controls import advance_sequence


SCALE = 2
START_FLOOR_Y = OPENING_FLOOR_Y
ANIMATION_FPS = 12
ANIMATION_INTERVAL_MS = 1000 / ANIMATION_FPS
COMBAT_ANIMATION_FPS = 10
COMBAT_ANIMATION_INTERVAL_MS = 1000 / COMBAT_ANIMATION_FPS
QUEUE_GRACE_MS = 300
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
# DoStrike 6:27d8 selects SEQS 96 when the Prince's opponent is a serpent.
SERPENT_ATTACK_SEQUENCE = 96
SWORD_ATTACK_START_SEQUENCES = {SWORD_ATTACK_SEQUENCE, SWORD_BLOCK_ATTACK_SEQUENCE, 203,
                                SERPENT_ATTACK_SEQUENCE}
SWORD_ATTACK_START_POSES = {151, 152, 153, 162}
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


class ScenePrototype(WindowControls, ArmedControls, LowControls):
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
        self.ending_assets = None
        self.discovery_assets = None
        self.demo = None
        self.attract_data = self.credits_assets = None
        self.attract_stage = None
        self.live_combat = None
        self.audio = audio
        self.peaceful = peaceful
        self.god_mode = False
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
        self.ordinary_attachment_frames = self.resources.attachment_frames
        prince = self.resources.prince
        self.ui_font = MacintoshFont(prince["NFNT"][23331]["data"])
        # DrawRestartMessage uses palette index 6; match its displayed RGB.
        hud_text_color = self.hud_text_color = (253, 255, 168, 255)
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
        self.shift_turn_direction = 0
        self.pending_potion_pickup = None
        self.queue_grace_remaining_ms = 0
        self.queue_grace_command = None
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
        self.modifier_input = 0
        self.sword_drawn = False
        self.paused_ctrl_request = False
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
        self.active_save_path = None
        self.game_was_paused = False
        self.native_viewport = None
        self.copy_protection_enabled = True
        self.copy_verified = False
        self.copy_challenge = None

        # Prepare menu metadata before the animation clock starts, not on F3.
        self.development_levels()
        self.development_parts()
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

    def bind_level(self, game, renderer, initialize_world=True):
        if self.audio is not None and hasattr(self.audio, 'configure_level'):
            self.audio.configure_level(game.level.data)
        palette = kid_palette_for_level(self.kid, game.level.kind)
        sword_palette = sword_palette_for_level(self.resources.prince, game.level.kind)
        guard_art = health_art = hit_art = None
        if game.combat is not None:
            artwork = ("Head.rsrc" if getattr(game.combat, 'ruins', None) is not None
                       else "Skeleton.rsrc" if game.level.kind == 3 else "Guard.rsrc")
            guard_art = GuardArtwork(load_resource_file(artwork), self.sword_shapes,
                                     self.first_sword_shape_id, sword_palette)
            health_art = HealthArtwork(self.kid, palette, self.first_shape_id)
            hit_art = HitArtwork(self.kid, palette, self.first_shape_id,
                                 self.frames, guard_art.frames)
            game.combat.guard_art = guard_art
        if game.caverns is not None and initialize_world:
            game.caverns.configure_level_entry(renderer.cavern_program, game)
            game.caverns.configure_torches(renderer.cavern_program.get('torches', {}))
            game.caverns.configure_lava(renderer.cavern_program.get('lava'))
        room = renderer.enter_room(game.room_id, game.caverns)
        if game.checkpoint is not None and game.caverns is not None and game.checkpoint.caverns is None:
            # Older progress saves loaded fresh mechanisms but never stored
            # them in the checkpoint. Keep that initialized baseline for retries.
            game.checkpoint.caverns = deepcopy(game.caverns)
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

    def can_save_game(self):
        return (self.combat is not None and self.combat.player.alive
                and self.intro is None and self.demo is None and self.copy_challenge is None
                and not self.level_complete and self.game.exit is None)

    def save_game_to(self, path, name=None):
        from pop2.save_game import SaveGameError, capture, encode_preview, save_name, write_save

        if not self.can_save_game():
            raise SaveGameError('Save is unavailable during this scene')
        document = capture(self.game, copy_verified=self.copy_verified)
        document['name'] = save_name(f'Level {document["level"]}' if name is None else name)
        document['preview'] = encode_preview(self.resume_preview(document))
        document['preview_at_resume'] = True
        document['preview_version'] = 2
        write_save(path, document)
        self.active_save_path = Path(path).absolute()
        self.status.set(f'Game saved: {path}')

    def resume_preview(self, document):
        from copy import copy
        import hashlib
        import json
        import random
        from pop2.save_game import restore_progress

        key = hashlib.sha256(json.dumps({name: document.get(name) for name in
            ('level', 'level_sha256', 'resume')}, sort_keys=True).encode()).hexdigest()
        cache = getattr(self, 'save_preview_cache', None)
        if cache is None:
            cache = self.save_preview_cache = {}
        if key not in cache:
            before = random.getstate()
            try:
                game, _saved = restore_progress(document, self.resources)
                preview = copy(self)
                preview.audio = None
                preview.game = game
                preview.intro = preview.demo = preview.attract_stage = None
                preview.game_menu = preview.dev_menu = preview.copy_challenge = None
                preview.screenshot_toast = None
                preview.paused = False
                preview.present_viewport = lambda: None
                preview.bind_level(game, LevelRenderer(game.level, preload_room=False))
                preview.settle_save_preview_entry()
                preview.render()
                if len(cache) >= 12:
                    del cache[next(iter(cache))]
                cache[key] = preview.screenshot_viewport.copy()
            finally:
                random.setstate(before)
        return cache[key]

    def settle_save_preview_entry(self):
        # Only finish the scripted door entry in the isolated preview. No
        # combat, hazards, world clock or live-session controls are advanced.
        game = self.game
        cavern = game.caverns
        if game.checkpoint is not None or cavern is None or not cavern.entry_frames:
            return
        if game.room_id != cavern.entry_room:
            return
        for _ in range(120):
            if (game.runtime.state.sequence_id == IDLE_SEQUENCE
                    and cavern.entry_frame == len(cavern.entry_frames) - 1):
                break
            if game.runtime.state.sequence_id != IDLE_SEQUENCE:
                game.runtime.next_frame()
            cavern.advance()
        else:
            raise ValueError('Door-entry preview did not reach idle')
        state = game.runtime.state
        state.current_x = state.target_x
        state.sound_events.clear()
        state.sequence_events.clear()
        self.action, self.player_x = state.action, state.target_x
        room = self.level_renderer.enter_room(game.room_id, cavern)
        self.background, self.foreground = room.background, room.foreground

    def save_slot_preview(self, slot):
        if slot.document['version'] == 1:
            from pop2.save_game import capture, read_save

            cache = getattr(self, 'legacy_save_previews', None)
            if cache is None:
                cache = self.legacy_save_previews = {}
            key = slot.path, slot.modified
            if key not in cache:
                game, _saved = read_save(slot.path, self.resources)
                if len(cache) >= 12:
                    del cache[next(iter(cache))]
                cache[key] = self.resume_preview(capture(game)).crop((1, 0, 511, 365)).convert('RGB')
            return cache[key]
        return self.resume_preview(slot.document).crop((1, 0, 511, 365)).convert('RGB')

    def load_game_from(self, path):
        from pop2.save_game import SaveGameError, read_save

        game, saved = read_save(path, self.resources)
        # Decode and render the destination before replacing the live session.
        try:
            renderer = LevelRenderer(game.level, preload_room=False)
            if game.caverns is not None:
                game.caverns.configure_level_entry(renderer.cavern_program, game)
                game.caverns.configure_torches(renderer.cavern_program.get('torches', {}))
                game.caverns.configure_lava(renderer.cavern_program.get('lava'))
            room = renderer.enter_room(game.room_id, game.caverns)
            frame = renderer.animated_layer(room.background.copy(), game.room_id, game.harbor,
                desert=game.desert, caverns=game.caverns)
            renderer.animated_layer(Image.alpha_composite(frame, room.foreground), game.room_id,
                game.harbor, front=True, desert=game.desert, caverns=game.caverns)
            artwork = GuardArtwork(load_resource_file(
                'Skeleton.rsrc' if game.level.kind == 3 else 'Guard.rsrc'), self.sword_shapes,
                self.first_sword_shape_id, sword_palette_for_level(self.resources.prince, game.level.kind))
            for guard in game.combat.visible_guards():
                artwork.bounds(guard.state, floor_y(guard.row))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            raise SaveGameError(f'Save cannot be rendered: {error}') from error
        if self.animation_after_id is not None:
            self.root.after_cancel(self.animation_after_id)
            self.animation_after_id = None
        self.cancel_gate_presentation()
        self.demo = self.live_combat = self.intro = self.attract_stage = None
        self.copy_challenge = None
        self.clear_keys(None)
        self.reset_level_controls()
        self.bind_level(game, renderer, initialize_world=False)
        self.terrain_enabled = True
        self.pause_resume_keys.update(self.window_keys_down)
        self.copy_verified = saved['copy_verified']
        if self.audio is not None:
            self.audio.reset()
        self.next_animation_at = time.perf_counter()
        self.pause_started_at = self.next_animation_at if self.paused else None
        self.active_save_path = Path(path).absolute()
        self.status.set(f'Game loaded: {path}')
        self.render()
        if not self.in_animation_tick:
            self.schedule_next_animation()

    def load_level(self, number, keep_music=False):
        # Prepare the complete destination before replacing a running session.
        previous = getattr(self, 'game', None)
        # Only the level-six exit chooses level seven's entrance.
        entry = (previous.ruins_entry if previous is not None and previous.level.number == 6
                 and number == 7 else 1)
        game = GameSession.load(self.resources, number, self.terrain_enabled, ruins_entry=entry)
        if previous is not None:
            # The campaign clock and tree stage survive level changes (2:5af2).
            game.story = previous.story
            if previous.caverns is not None and game.caverns is not None:
                # So does an upside-down world (a5-0x4fa8).
                game.caverns.potions.flip_timer = previous.caverns.potions.flip_timer
        renderer = LevelRenderer(game.level)
        self.time_message, self.time_message_frames = None, 0
        self.bind_level(game, renderer)
        self.copy_challenge = None
        self.demo = self.live_combat = None
        self.attract_stage = self.intro = None
        self.clear_keys(None)
        self.reset_level_controls()
        if self.audio is not None:
            self.audio.reset(keep_music=keep_music)
        if self.animation_after_id is not None:
            self.root.after_cancel(self.animation_after_id)
            self.animation_after_id = None
        self.status.set(f"Level {game.level.number}")
        self.render()
        self.next_animation_at = time.perf_counter()
        if not self.in_animation_tick:
            self.schedule_next_animation()

    def set_key_state(self, key, pressed):
        if key in ('up', 'down') and getattr(self, 'controls_flipped', False):
            key = 'down' if key == 'up' else 'up'  # GenCtrl 4:3e1c, upside down.
        self.ensure_run_stop_controls()
        if self.paused:
            if self.gameplay_controls_available():
                previous = getattr(self, f"{key}_held")
                setattr(self, f"{key}_held", pressed)
                if key == "up" and (not pressed or not previous):
                    self.jump_started_for_press = False
                    self.jump_repeat_armed = False
                elif key == "ctrl":
                    if not pressed:
                        self.paused_ctrl_request = False
                    elif not previous:
                        self.paused_ctrl_request = True
                elif key == "down" and not pressed:
                    self.down_sheathe_consumed = False
            return "break"
        if self.dev_menu is not None:
            return "break"
        if self._combat_controls_locked():
            setattr(self, f"{key}_held", pressed)
            if self.sword_drawn and not pressed:
                self.sample_armed_controls()
            return "break"
        if self._opening_active():
            setattr(self, f"{key}_held", pressed)
            return "break"
        if key == 'up' and pressed:
            # Physical Down becomes logical Up in the inverted world. Use
            # the same press handler as upright Up, including deferred jumps.
            return self.press_up()
        if self.waiting_key(key, pressed):
            return "break"
        if self.native_ledge:
            setattr(self, f"{key}_held", pressed)
            return "break"
        if key == "up":
            # With the sword drawn Up belongs to the armed bank (DoBlock);
            # its release must not leave a jump for after sheathing.
            if (
                not pressed
                and self.up_held
                and not self.jump_started_for_press
                and not self.ledge_hanging
                and not self.sword_drawn
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
                self.down_sheathe_consumed = pressed
                if not self.sword_sheathing:
                    self.sample_armed_controls()
                    if pressed:
                        self.dispatch_armed_at_guard("sword_sheathe")
                return "break"
            if not pressed:
                self.down_sheathe_consumed = False
            self.update_ledge_test_state()
            if pressed and not self.ledge_hanging and self._is_resting():
                if not self.start_native_descent():
                    self.start_crouch_lower()
        elif key == "shift":
            if pressed and not self.shift_held:
                self.queue_potion_pickup()
            self.shift_held = pressed
            self.update_ledge_test_state()
        elif key == "ctrl":
            fresh = pressed and not self.ctrl_held
            self.ctrl_held = pressed
            self.sample_keyboard()
            if self.sword_drawn:
                if fresh:
                    self.queue_sword_action("sword_attack")
                else:
                    self.sample_armed_controls()
            elif fresh:
                self.queue_sword_action("sword_draw")
        if self.sword_drawn and not pressed:
            # A release reaches the bank: a consumed word becomes 0 (4:3e84),
            # so the next press is fresh even between two animation ticks.
            self.sample_armed_controls()
        return "break"

    def sword_lost(self):
        combat = getattr(self, "combat", None)
        return combat is not None and combat.player.sword_lost

    def queue_sword_action(self, kind):
        if self.sword_sheathing or self._combat_controls_locked():
            return False
        if kind == "sword_draw":
            self.pending_potion_pickup = None
            return self.try_draw_sword()
        if not self.armed_controls_available() or kind not in SWORD_SEQUENCES:
            return False
        if kind == "sword_attack":
            # The armed attack request survives releasing Ctrl (host
            # extension); the rapid-repeat filter runs first.
            return self.armed_press_ctrl()
        # A scripted request latches its word, as a key press would.
        self.latch_armed_request(kind)
        return self.dispatch_armed_at_guard(kind)

    def try_draw_sword(self):
        """Standing Ctrl gate; a released tap is never a future draw command."""
        self.sample_keyboard()
        state = self.sequence_state
        motion = getattr(self, 'terrain_motion', None)
        if (self.modifier_input != -2 or self.sword_drawn or self.sword_sheathing
                or self.sword_lost() or self._combat_controls_locked()
                or not (self._is_resting() or state.action in (50, 51, 52))
                or self.ledge_hanging or self.ledge_climbing
                or state.animation_state in (4, 5, 9) or state.sequence_id in (27, 110)
                or self.horizontal_input or self.up_held or self.down_held
                or motion is not None and (motion.falling or motion.dead)):
            return False
        # GenCtrl6:0c90-0cba accepts only fresh Ctrl with no directions;
        # running6:11e4 does not consume it or request a sword animation.
        return self.start_sword_action('sword_draw')

    def latch_request(self, command):
        """Latch a scripted request into the bank that owns the pose.

        There is no host buffer: where no bank owns the pose (the throne
        collapse/wake, the prototype rooftop without a level map) the request
        is not kept. Held keys are still read at rest.
        """
        if command.kind in SWORD_SEQUENCES:
            if not self.armed_controls_available():
                return False
            if command.kind == "sword_attack":
                self.armed_attack_requested = True
            else:
                self.latch_armed_request(command.kind)
            return True
        if self.waiting_controls_available():
            self.latch_waiting_command(command)
            return True
        return False

    def start_queue_grace(self, command):
        self.queue_grace_command = command
        self.queue_grace_remaining_ms = QUEUE_GRACE_MS

    def start_sword_action(self, kind, sequence_id=None):
        fast_block = False
        if kind == "sword_block":
            # DoBlock 6:2844-28e6: a parried swing can recover through 61;
            # against pose 153, skip the unprotected block-start pose 169.
            state = self.sequence_state
            if state.animation_state >= 2:
                return False
            if state.action == 167:
                sequence_id = 61
            elif state.action in (158, 170, 171, 168, 165):
                combat = getattr(self, "combat", None)
                other = (combat.guard.state.action
                         if combat is not None and combat.guard is not None else None)
                if other == 168:
                    return False
                fast_block = other == 153
            else:
                return False
        if kind in ("sword_draw", "sword_attack"):
            # GenCtrl6:0cb2 / DoStrike6:280c consume accepted Ctrl. A hold
            # used to attack must not become a fresh draw after sheathing.
            self.modifier_input = 2
        if kind == "sword_draw":
            motion = getattr(self, "terrain_motion", None)
            if motion is not None:
                state = self.sequence_state
                offset = self.level_map.combat_draw_offset(
                    motion.room, motion.row, state, self.frames[state.action], self.player_bounds())
                self.player_x += offset * (1 if state.facing else -1)
            self.sword_drawn = True
            # The drawn sword's bank starts with the holds consumed (6:0cb6).
            self.armed_input = None
            self.armed_attack_requested = False
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
        if kind == "sword_advance" and sequence_id is None and self.combat is not None:
            # DoAdvance 6:1e28-1e46: in level five, with the opponent in
            # native room 19 at column 5, the Prince advances with SEQS 86.
            guard = self.combat.guard
            if guard is not None:
                sequence_id = advance_sequence(self.game.level.number, guard.room,
                                               self.combat._supporting_column(guard))
        if kind == "sword_attack" and sequence_id is None and self.combat is not None:
            # 6:27d0-27da: against a serpent the Prince's strike is the low
            # strike SEQS 96, the only one its strike ranges accept.
            opponent = getattr(self.combat, "ruins_opponent", lambda: None)()
            if opponent is not None and opponent.state.actor_type == 11:
                sequence_id = SERPENT_ATTACK_SEQUENCE
        self.run_active = False
        self.run_stop_requested = False
        self.run_direction = 0
        self.start_sequence(SWORD_SEQUENCES[kind] if sequence_id is None else sequence_id)
        if kind == "sword_sheathe":
            self.begin_sheathe_controls()
        if fast_block:
            self.sequence_runtime.next_frame()
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
        self.start_queue_grace(BufferedCommand(kind))
        return True

    def armed_attack_pending(self):
        relative = self.armed_relative_input()
        return relative is not None and relative.modifier == -2

    def resume_sword_attack_after_block(self):
        if (
            self.armed_controls_available()
            and self.sequence_state.action in (150, 161)
            and self.armed_attack_pending()
        ):
            # CODE:6 0x27e8 selects SEQS:66 before the block's return to guard.
            started = self.start_sword_action(
                "sword_attack", sequence_id=SWORD_BLOCK_ATTACK_SEQUENCE
            )
            if started:
                self.accept_armed_request("sword_attack")
            return started
        return False

    def resume_sword_parry_recoil(self):
        if (not self.sword_drawn or self.sword_sheathing
                or self.sequence_state.action != 161
                or self.armed_attack_pending()):
            return False
        # GenCtrl 6:24da-2506: a parried block without a counter selects
        # SEQS:57 and AddCharX(-9). This forced retreat has no floor veto.
        state = self.sequence_state
        self.player_x = state.target_x - 9 * (1 if state.facing else -1)
        return self.start_sword_action("sword_retreat")

    def latch_armed_request(self, kind):
        """Bridge a scripted armed request into its native word."""
        bank = self.sample_armed_controls()
        if bank is None:
            return
        word = {"sword_block": "up", "sword_sheathe": "down", "sword_advance": "left",
                "sword_retreat": "right"}[kind]
        relative = bank.remap(facing_right=bool(self.sequence_state.facing))
        self.armed_input = replace(relative, **{word: -1}).remap(
            facing_right=bool(self.sequence_state.facing))

    def queue_sword_step(self, direction):
        """A fresh horizontal press with the sword drawn."""
        bank = self.sample_armed_controls()
        if bank is None:
            return False
        if facing_for_direction(direction) != self.sequence_state.facing and self.shift_held:
            # SwordCtrl 6:22f2-2312: fresh Backward with Shift requests the
            # voluntary turn; DoRetreat requires a zero modifier (6:256e).
            self.voluntary_turn_requested = True
            return False
        return self.dispatch_armed_at_guard(
            "sword_advance" if facing_for_direction(direction) == self.sequence_state.facing
            else "sword_retreat")

    def resume_sword_controls(self):
        if not self.armed_controls_available():
            return False
        state = self.sequence_state
        if state.animation_state >= 2 or state.cursor == 0:
            self.sample_armed_controls()
            return False
        # OnAlert 6:24bc: the bank's highest pending request; a refused one
        # stays pending (an inadmissible strike or Down also holds back the
        # lower requests). Consumed holds do not repeat.
        return self.dispatch_armed_request()

    def update_ledge_test_state(self):
        requested = self.down_held and self.shift_held
        if not requested:
            self.ledge_test_active = False
            self.ledge_action_consumed = False
            return
        self.ledge_test_active = requested and self._at_rooftop_ledge()
        self._try_start_ledge_hang()

    def horizontal_key(self, _event, direction, pressed):
        if self.paused:
            if self.gameplay_controls_available():
                previous_direction = self.horizontal_input
                if pressed and direction not in self.held_directions:
                    self.held_directions.append(direction)
                elif not pressed and direction in self.held_directions:
                    self.held_directions.remove(direction)
                    if getattr(self, "shift_turn_direction", 0) == direction:
                        self.shift_turn_direction = 0
                if not pressed and getattr(self, "step_warning_direction", 0) == direction:
                    self.step_warning_direction = 0
                self.sample_keyboard()
                if (not pressed and self.up_held and not self.horizontal_input
                        and self.waiting_controls_available()):
                    # The family's release rule latches without moving.
                    self.sample_waiting_controls()
                    self.latch_released_chord()
                if self.run_active:
                    self.run_stop_requested = self.horizontal_input != self.run_direction
            return "break"
        if self.dev_menu is not None:
            return "break"
        self.ensure_run_stop_controls()
        previous_direction = self.horizontal_input
        if pressed:
            if direction in self.held_directions:
                return "break"
            self.held_directions.append(direction)
        elif direction in self.held_directions:
            self.held_directions.remove(direction)
            if getattr(self, "shift_turn_direction", 0) == direction:
                self.shift_turn_direction = 0
            if getattr(self, "step_warning_direction", 0) == direction:
                self.step_warning_direction = 0
        self.sample_keyboard()

        if self._combat_controls_locked():
            return "break"
        if self._opening_active():
            return "break"
        if self.waiting_controls_available():
            self.waiting_horizontal(direction, pressed)
            return "break"

        if self.native_ledge and not self.ledge_climbing:
            return "break"

        if self.sword_sheathing:
            if pressed and self.horizontal_input != previous_direction and self.horizontal_input:
                self.queue_sampled_horizontal_action(self.horizontal_input)
            return "break"

        if self.sword_drawn:
            if pressed and self.horizontal_input != previous_direction and self.horizontal_input:
                self.queue_sword_step(self.horizontal_input)
            else:
                self.sample_armed_controls()
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
        self.modifier_input = sample_modifier(
            getattr(self, 'modifier_input', 0), self.shift_held, self.ctrl_held)
        return frame

    def resume_pause_controls(self):
        self.sample_keyboard()
        if (getattr(self, "paused_ctrl_request", False) and self.ctrl_held
                and not self._combat_controls_locked() and not self.sword_sheathing
                and (self.sword_drawn or not self.sword_lost())):
            if self.sword_drawn:
                self.armed_attack_requested = True
                self.modifier_input = 2
            else:
                self.try_draw_sword()
        self.paused_ctrl_request = False

    def queue_sampled_horizontal_action(self, direction):
        if self.sword_drawn and not self.sword_sheathing:
            return False
        if self.shift_held and self._is_resting() and self.update_potion_controls():
            return True
        if self.up_held:
            if self.jump_started_for_press:
                return False
            return self.start_jump_if_needed()
        elif self.shift_held:
            if getattr(self, "shift_turn_direction", 0) == direction:
                return False
            return self.queue_horizontal_action(direction, "step")
        elif facing_for_direction(direction) != self.sequence_state.facing:
            return self.queue_horizontal_action(direction, "turn")
        else:
            return self.queue_horizontal_action(direction, "run")

    def up_key(self, _event):
        if getattr(self, 'controls_flipped', False):
            # Physical Up is logical Down under GenCtrl's 4:3e1c swap.
            # Its dedicated binding must use the same mapping as key release.
            return self.set_key_state('up', True)
        return self.press_up()

    def press_up(self):
        if self.paused or self.dev_menu is not None:
            return "break"
        if self.up_held:
            return "break"
        self.ensure_run_stop_controls()
        if self.waiting_key('up', True):
            return "break"
        self.up_held = True
        if self._combat_controls_locked():
            return "break"
        if self._opening_active():
            return "break"
        if self.sword_drawn:
            self.jump_started_for_press = True
            self.jump_repeat_armed = False
            if not self.sword_sheathing:
                self.sample_armed_controls()
                self.dispatch_armed_at_guard("sword_block")
            return "break"
        if self.ledge_hanging:
            if self.ledge_climbing:
                self.start_jump()
                return "break"
            self.ledge_climb_requested = True
            if self.sequence_state.sequence_id == LEDGE_HANG_SEQUENCE:
                self.start_ledge_climb()
            return "break"
        self.jump_started_for_press = False
        if (
            self.sequence_state.sequence_id == STANDING_TURN_SEQUENCE
            and self.sequence_state.action == 45
            and self.horizontal_input
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
            if self.waiting_controls_available():
                self.update_waiting_controls()
                return
            self.start_jump()

    def start_jump(self):
        if self.sequence_state.sequence_id in RUN_INPUT_SEQUENCES and self.waiting_controls_available():
            self.request_running_jump()
            return
        self.jump_started_for_press = True
        horizontal = self.horizontal_input
        starting_chord = (
            horizontal != 0
            and self.sequence_state.sequence_id == RUN_START_SEQUENCE
            and self.sequence_state.action == 1
        )
        starting_reverse = (
            horizontal != 0
            and self.sequence_state.sequence_id == RUN_START_SEQUENCE
            and self.sequence_state.action in (1, 2, 3)
            and facing_for_direction(horizontal) != self.sequence_state.facing
        )
        running = (
            horizontal != 0
            and (self.sequence_state.sequence_id in RUN_SEGMENT_SEQUENCES
                 or self.sequence_state.sequence_id == RUN_JUMP_SEQUENCE)
            and not (starting_chord or starting_reverse)
        )
        # A fresh Up during SEQS:4 waits for DoRunJump's next run pose;
        # landing must not turn that buffered command into a standing jump.
        command = BufferedCommand("jump", horizontal, running=running)
        # The first run pose allows a near-simultaneous Forward + Up chord.
        # Later startup poses preserve the run and wait for legal takeoff.
        if self._is_resting() or starting_chord or starting_reverse:
            self.dispatch_jump(command)
        else:
            self.latch_request(command)

    def queue_horizontal_action(self, direction, mode):
        if (
            mode in ("run", "turn")
            and self._is_running()
            and self.run_direction == direction
        ):
            # SEQS:6 flips facing only after pose 65. Repressing its chosen
            # direction resumes the held run, not another queued turn/start.
            self.run_stop_requested = False
            return False

        command = BufferedCommand("horizontal", direction, mode)
        if self._is_resting():
            dispatched = self.dispatch_horizontal_action(command)
            if dispatched:
                self.start_queue_grace(command)
            return dispatched
        return False

    def dispatch_jump(self, command):
        if not command.direction and self.sequence_state.sequence_id in RUN_SEGMENT_SEQUENCES:
            # GenCtrl 6:11e4-1242 never calls DoJumpUp from a running pose.
            # Keep the Up pending in the bank, but brake before aligning its ledge.
            self.run_active = self.run_stop_requested = False
            self.run_direction = 0
            self.run_start_x = None
            self.start_sequence(RUN_STOP_SEQUENCE)
            if self.waiting_controls_available():
                self.latch_waiting_command(command)
            return True
        if not command.direction and self.start_cavern_exit():
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
        if sequence_id == JUMP_VERTICAL_SEQUENCE and getattr(self, "level_map", None) is not None:
            sequence_id, offset = self.level_map.vertical_jump(
                self.room_id, self.terrain_motion.row, self.sequence_state,
                self.frames[self.sequence_state.action], self.player_collision_bounds())
            self.player_x += offset
        if sequence_id == RUN_JUMP_SEQUENCE:
            if not 7 <= self.sequence_state.action <= 14:
                return False
        if sequence_id == RUN_JUMP_SEQUENCE and getattr(self, "level_map", None) is not None:
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
        self.start_queue_grace(command)
        return True

    def start_cavern_exit(self):
        if (self.game.caverns is None or self.terrain_motion is None
                or self.sword_drawn or not self.combat.player.alive):
            return False
        state = self.sequence_state
        tile = self.level_map.exit_door(self.room_id, self.terrain_motion.row,
                                        state, self.frames[state.action])
        if tile is None:
            return False
        self.clear_keys(None)
        self.run_active = self.run_stop_requested = False
        self.run_direction = 0
        # 6:0f58 aligns to the exit's column, faces left, then selects SEQS:70.
        self.player_x = tile.column * TILE_WIDTH - 3
        state.facing = 0
        self.start_sequence(70)
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
                # StairClimbing 6:0d4c/10e8 consumes Backward on the turn;
                # that same Shift+direction press is not a forward step.
                self.shift_turn_direction = direction if direction in self.held_directions else 0
                self.start_standing_turn()
                return True
            if getattr(self, "level_map", None) is not None:
                if getattr(self, "step_warning_direction", 0) == direction:
                    return False
                boundary = self.level_map.step_boundary(
                    self.room_id, self.terrain_motion.row, self.sequence_state,
                    self.frames[self.sequence_state.action], self.player_bounds(), cautious=True)
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
            self.begin_waiting_controls(direction)
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
        self.begin_running_controls(direction)
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
        self.begin_running_controls(direction)
        self.run_start_x = None
        self.start_sequence(RUNNING_DRIFT_SEQUENCE)
        self.run_active = True
        self.run_direction = direction
        self.run_stop_requested = False
        self.run_cycle_boundary_pending = False
        self.status.set("Running reversal: original SEQS:6")
        self.advance_animation_now()

    def start_standing_turn(self):
        self.begin_waiting_controls(-1 if self.sequence_state.facing else 1, turning=True)
        self.run_active = False
        self.run_direction = 0
        self.run_stop_requested = False
        self.run_start_x = None
        if getattr(self, 'level_map', None) is not None:
            state = self.sequence_state
            offset = self.level_map.standing_turn_offset(
                self.room_id, self.terrain_motion.row, state,
                self.frames[state.action], self.player_bounds())
            self.player_x += offset
            state.current_x = state.target_x = self.player_x
        self.start_sequence(STANDING_TURN_SEQUENCE)
        self.status.set("Standing turn: original SEQS:5")
        self.advance_animation_now()

    def update_armed_input_boundaries(self):
        state = self.sequence_state
        if (getattr(self, 'armed_attack_requested', False) and not self.ctrl_held
                and (state.sequence_id in (61, SWORD_BLOCK_SEQUENCE)
                     or state.action in (150, 161, 169))):
            # 4:3f38 cancels a released Ctrl before a legal counter gate.
            # Already-started attacks and the port's queued-swing extension
            # during an attack/draw are separate from this block request.
            self.armed_attack_requested = False

    def resume_queued_crouch_during_run(self):
        # Compatibility entry point; the directional bank is the sole dispatcher.
        return self.update_waiting_controls()

    def resume_run_stop(self):
        # Compatibility entry point; the directional bank is the sole dispatcher.
        return self.update_waiting_controls()

    def start_sequence(self, sequence_id):
        if sequence_id in LOW_INPUT_SEQUENCES:
            self.begin_low_controls(sequence_id)
        if sequence_id in AIRBORNE_TAKEOFF_SEQUENCES:
            self.begin_airborne_controls(sequence_id)
        if sequence_id in RUN_INPUT_SEQUENCES:
            self.waiting_step_direction = 0
        if not self.waiting_sequence(sequence_id):
            self.clear_waiting_controls()
        self.run_cycle_boundary_pending = False
        if sequence_id != IDLE_SEQUENCE and not 29 <= sequence_id <= 44:
            self.step_cautious = True
            self.step_warning_direction = 0
        if getattr(self, "combat", None) is not None:
            self.combat.notify_player_sequence(sequence_id)
        self.sequence_state.select(sequence_id)
        self.sequence_state.target_x = self.player_x
        self.sequence_state.current_x = self.player_x
        if sequence_id in (JUMP_FORWARD_SEQUENCE, JUMP_VERTICAL_SEQUENCE, RUN_JUMP_SEQUENCE, 14):
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
        self.start_queue_grace(BufferedCommand("crouch"))

    def crawl_cell(self, offset):
        """GetCellsInFront 4:39fc (offset > 0) or the cell behind (4:3a48).

        Returns the room-relative column and its tile, from the stored column
        a5-0x504a: GetCharCol of the supporting foot (GetFCharX 4:3a72), as
        LoadFrame's reload 4:2a72 computes it.
        """
        state, motion = self.sequence_state, self.terrain_motion
        foot = floor_contact_x(state.target_x, state.facing, self.frames[state.action])
        column = character_column(foot) + offset * (1 if state.facing else -1)
        return column, self.level_map.tile(motion.room, column, motion.row)

    def start_crawl(self, *, down_active=None):
        # GenCtrl 6:0a4e-0b28: with Down still held, forward into a crevice
        # (tile 7 whose low bits are not 3) or a scythe (12/13) lies down.
        if not (self.down_held if down_active is None else down_active) or getattr(self, 'terrain_motion', None) is None:
            return False
        column, tile = self.crawl_cell(1)
        if not (tile.kind in (12, 13) or tile.kind == CREVICE_TILE and tile.foreground & 3 != 3):
            return False
        state = self.sequence_state
        # 6:0a92-0b24: actor X against the column table a5-0x4b88: at most
        # 10 into that column facing right, at least 34 past its right edge
        # facing left.
        offset = state.target_x - column_left(column + (0 if state.facing else 1))
        if state.facing and offset > 10:
            state.target_x += 10 - offset
        elif not state.facing and offset < 34:
            state.target_x += 34 - offset
        state.current_x = self.player_x = state.target_x
        self.start_sequence(LIE_DOWN_SEQUENCE)
        self.status.set("Lying down to crawl: original SEQS:125")
        if not self.in_animation_tick:
            self.advance_animation_now()
        return True

    def start_crouch_step(self, direction, *, try_crawl=True):
        if try_crawl and self.start_crawl():
            return
        self.start_sequence(CROUCH_STEP_SEQUENCE)
        self.status.set("Crouch step: original SEQS:79")
        if not self.in_animation_tick:
            self.advance_animation_now()
        self.start_queue_grace(BufferedCommand("crawl", direction))

    def start_crouch_rise(self):
        self.start_sequence(CROUCH_RISE_SEQUENCE)
        self.status.set("Standing up: original SEQS:49")

    def gate_blocks_crouch_rise(self):
        state = self.sequence_state
        return (getattr(self, "level_map", None) is not None
                and self.level_map.gate_blocks_rise(
                    self.room_id, self.terrain_motion.row, state, self.frames[state.action]))

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
                self.waiting_controls_available()
                self.latch_waiting_command(BufferedCommand("jump"))
                return False
            self.ledge_climb_requested = False
            self.ledge_climbing = True
            ship = (self.harbor is not None
                    and self.harbor.hanging_from_ship(self.room_id, self.sequence_state))
            sequence = (SHIP_CLIMB_SEQUENCE if ship else self.level_map.climb_sequence(
                self.room_id, self.terrain_motion.row, self.sequence_state, self.frames[self.action]))
            player = self.combat.player
            if (not ship and self.game.level.number == 5 and self.room_id == 9
                    and not player.sword_lost):
                # DoClimbUp 6:19aa-19c4: climbing out in level five's room 10
                # drops the sword (SEQS:236, a5-0x503c = -1); a low gate above
                # still selects the failed climb afterwards.
                player.sword_lost = True
                if sequence == 10:
                    sequence = 236
            self.consume_ledge_input("climb")
            self.start_sequence(sequence)
            self.status.set("Boarding the ship" if ship else
                            "Blocked climb: original SEQS:73" if sequence == 73 else
                            "Climb: original SEQS:10 / 235")
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
        self.jump_repeat_armed = False
        self.native_ledge = self.ledge_hanging = True
        self.ledge_climbing = self.ledge_climb_requested = False
        self.ledge_grip_delay = 12 if sequence_id == 15 else 0
        self.player_x += offset
        self.sequence_state.horizontal_velocity = self.sequence_state.vertical_velocity = 0
        self.sequence_state.sequence_mode = 0
        self.begin_ledge_controls(sequence_id)
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
        if offset is not None:
            return self._begin_native_ledge(24, offset)
        backward = self.level_map.back_ledge_jump(
            self.room_id, self.terrain_motion.row, state, self.frames[state.action])
        return backward is not None and self._begin_native_ledge(*backward)

    def update_native_ledge(self):
        if not self.native_ledge or self.ledge_climbing:
            return
        state = self.sequence_state
        if state.action not in range(87, 100):
            return
        self.ledge_grip_delay = max(0, self.ledge_grip_delay - 1)
        # GenCtrl6:18e0-191e reads the same bank before terrain/support.
        request = self.native_ledge_request()
        if request == "climb":
            self.start_ledge_climb()
        elif request == "release":
            sequence, offset = self.level_map.release_ledge(
                self.room_id, self.terrain_motion.row, state, self.frames[state.action],
                next_action=self.sequence_runtime.peek_frame().action)
            self.consume_ledge_input("release")
            self.ledge_hanging = self.native_ledge = False
            self.ledge_climb_requested = False
            self.terrain_motion.falling = sequence in (23, 99)
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
        if (state.sequence_id == STANDING_TURN_SEQUENCE and state.cursor > 0
                and state.action in (50, 51, 52)):
            return True
        if state.sequence_id == JUMP_LANDING_SEQUENCE and state.action == 15:
            return True
        return False

    def clear_keys(self, _event):
        self.clear_waiting_controls()
        self.pause_resume_keys.clear()
        if _event is not None:
            self.window_keys_down.clear()
            self.escape_held = self.dev_toggle_held = False
        self.held_directions.clear()
        self.shift_turn_direction = 0
        self.voluntary_turn_requested = False
        self.armed_input = None
        self.armed_attack_requested = False
        self.step_warning_direction = 0
        self.horizontal_input = 0
        self.up_held = False
        self.jump_started_for_press = False
        self.jump_repeat_armed = False
        self.down_held = False
        self.shift_held = False
        self.ctrl_held = False
        self.modifier_input = 0
        self.paused_ctrl_request = False
        self.down_sheathe_consumed = False
        self.ledge_test_active = False
        self.ledge_action_consumed = False
        if self.run_active:
            self.run_stop_requested = True
        self.pending_potion_pickup = None

    def prepare_next_sequence(self, run_cycle_boundary=False):
        if self.waiting_controls_available():
            return self.update_waiting_controls()
        if run_cycle_boundary:
            if self.run_stop_requested:
                self.run_active = False
                self.run_stop_requested = False
                self.run_direction = 0
                self.start_sequence(RUN_STOP_SEQUENCE)
                return True
            return False

        if self.try_draw_sword():
            return True
        if self._is_resting():
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

    def advance_animation(self):
        self.animation_after_id = None
        if self.paused:
            return
        self.in_animation_tick = True
        self.queue_grace_remaining_ms = max(
            0, getattr(self, "queue_grace_remaining_ms", 0)
            - self.current_animation_interval_ms()
        )
        if getattr(self, "copy_challenge", None) is not None:
            now = time.perf_counter()
            last = getattr(self, 'last_copy_at', None)
            self.copy_challenge.advance(1 / 60 if last is None else max(0, now - last))
            self.last_copy_at = now
            if self.copy_challenge.closed:
                self.resolve_copy_challenge()
            self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        if getattr(self, "level_complete", False):
            if self.game.exit is not None:
                environment = environment_for(self)
                environment.exit_scenery()
                if self.game.exit.advance(self.current_animation_interval_ms() / 1000, self.audio):
                    environment.finish_exit()
                self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
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
        if self.game.entry_active:
            frame = self.sequence_runtime.next_frame()
            self.action, self.player_x = frame.action, frame.target_x
            if self.combat is not None:
                self.combat.world_frame += 1
            self.advance_audio()
            self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        retry_held = ({"space"} & self.window_keys_down) - self.pause_resume_keys
        if RESUME_COMMAND_KEYS.intersection(self.window_keys_down):
            retry_held.clear()
        if self.death.can_restart and retry_held:
            self.restart_after_death(preserve_controls=True)
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        environment_for(self).frame_start()
        if self.advance_story_clock():
            self.render()
            self.in_animation_tick = False
            self.schedule_next_animation()
            return
        if self.combat is not None and not self.combat.player.alive:
            self.death.begin(0)
            # PlayerCtrl runs before AnimChar: count the previous dead pose,
            # not the first dead pose that this frame may be about to produce.
            self.death.advance(self.action, self.current_animation_interval_ms() / 1000,
                               getattr(self, "audio", None), dead_pose=self.carpet_dead_pose())
        self.sample_keyboard()
        old_x = self.sequence_state.target_x
        motion = getattr(self, "terrain_motion", None)
        old_bounds = self.player_collision_bounds() if motion is not None else None
        environment_for(self).controls()
        if self.update_potion_controls():
            frame = self.sequence_runtime.next_frame()
            self.action, self.player_x = frame.action, frame.target_x
            self.sequence_state.current_x = self.player_x
            self.run_world_phases('potion', old_x, old_bounds)
            return
        if motion is not None and (motion.falling or motion.sinking or motion.dead):
            self.sequence_runtime.next_frame()
            self.run_world_phases('falling', old_x, old_bounds)
            return
        if self._combat_controls_locked():
            # SwordCtrl may turn at a ready pose before the hurt sequence ends.
            self.resume_combat_turn()
            self.combat.advance_player_recovery()
            self.run_world_phases('locked', old_x, old_bounds)
            return
        if self._opening_active():
            phase = self.opening.phase
            self.opening.advance()
            if phase == "fall" and self.opening.phase == "landing":
                self.sequence_state.sound_events.append(296)
            self.action = self.sequence_state.action
            self.player_x = self.sequence_state.target_x
            self.run_world_phases('opening', old_x, old_bounds)
            return
        self.update_armed_input_boundaries()
        self.update_airborne_controls()
        if not self.resume_combat_turn():
            if not self.resume_sword_attack_after_block():
                self.resume_sword_parry_recoil()
            self.resume_sword_controls()
        if self.waiting_controls_available():
            self.update_waiting_controls()
        self.update_native_ledge()
        if (
            self.ledge_climb_requested and not self.native_ledge
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
            and not sword_step_before_frame
            and self.armed_request() in SWORD_SEQUENCES.keys() - SWORD_STEP_KINDS
        ):
            self.player_x = frame.target_x
            if self.dispatch_armed_request(SWORD_SEQUENCES.keys() - SWORD_STEP_KINDS):
                frame = self.sequence_runtime.next_frame()
        if self.sword_sheathing and frame.sequence_id == IDLE_SEQUENCE:
            self.sword_sheathing = False
            self.sword_drawn = False
            self.status.set("Sword sheathed")
            self.player_x = frame.target_x
            if self.prepare_next_sequence():
                frame = self.sequence_runtime.next_frame()
        climb_completed = self.ledge_climbing and frame.sequence_id == IDLE_SEQUENCE
        if climb_completed:
            native_climb = self.native_ledge
            if native_climb:
                self.finish_native_ledge_controls()
            self.ledge_hanging = self.ledge_climbing = self.native_ledge = False
            self.sequence_state.current_y = 0
            self.sequence_state.horizontal_velocity = self.sequence_state.vertical_velocity = 0
            # Finish the protected climb before dispatching its queued input.
            self.jump_started_for_press = self.up_held
            self.jump_repeat_armed = self.up_held
            self.status.set("Back on the rooftop")
        # Consume one buffered command at the transition, before drawing idle.
        if frame.action == 15 and frame.sequence_id in (
            JUMP_LANDING_SEQUENCE, IDLE_SEQUENCE
        ):
            self.player_x = frame.target_x
            if self.waiting_controls_available() and self.update_waiting_controls(repeat=False):
                frame = self.sequence_runtime.next_frame()
            elif (
                self.up_held
                and self.jump_started_for_press
                and self.jump_repeat_armed
                and not self.ledge_hanging
                and not climb_completed
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
        if (motion is not None and self.ledge_hanging and not self.ledge_climbing
                and not self.shift_held and self.sequence_state.sequence_id == LEDGE_HANG_SEQUENCE):
            self.ledge_hanging = False
            self.ledge_climb_requested = False
            motion.falling = True
            motion.row += 1
            self.sequence_state.current_y -= TILE_HEIGHT
            self.physics.select(self.sequence_runtime, 23)
        self.run_world_phases('ordinary', old_x, old_bounds, sweep_combat=True)

    def run_world_phases(self, mode, old_x, old_bounds, sweep_combat=False):
        """Run one tick's world phases (pop2.frame_phases) and end the tick."""
        from pop2.frame_phases import WORLD_PHASES

        motion = getattr(self, "terrain_motion", None)
        old_room = motion.room if motion is not None else None
        trace = getattr(self, "frame_trace", None)
        for phase in WORLD_PHASES[mode]:
            if trace is not None:
                trace.append((mode, phase))
            if phase == 'terrain':
                self.advance_terrain(old_x, old_bounds)
            elif phase == 'combat':
                # A room cut rebases X; it must not be swept as a cross-room jump.
                swept = sweep_combat and (motion is None or motion.room == old_room)
                self.advance_combat(old_x if swept else None)
            elif phase == 'environment':
                self.advance_environment()
            elif phase == 'harbor':
                environment_for(self).harbor_phase()
            elif phase == 'level_events':
                self.advance_level_events()
            elif phase == 'rebirth':
                self.advance_rebirth()
            elif phase == 'audio':
                self.advance_audio()
            elif phase == 'render':
                self.render()
        self.retire_waiting_controls()
        self.in_animation_tick = False
        self.schedule_next_animation()

    def _opening_active(self):
        opening = getattr(self, "opening", None)
        return opening is not None and opening.active

    def queue_potion_pickup(self):
        state, motion = self.sequence_state, self.terrain_motion
        if (self.game.caverns is None or motion is None or self.sword_drawn
                or self._combat_controls_locked() or self.native_ledge
                or self.horizontal_input or self.up_held or self.down_held
                or not (self._is_resting() or state.sequence_id == RUN_STOP_SEQUENCE
                        or self.run_stop_requested and state.sequence_id in RUN_CYCLE_SEQUENCES)):
            return
        # The remaining skid can bring the flask into reach. Try once at the
        # first standing-control pose, without retaining Shift as a modifier.
        self.pending_potion_pickup = motion.room, motion.row, state.facing

    def carpet_dead_pose(self):
        # IsDeadPos 4:4814-4842: level five room 3 counts a dead Prince in
        # mode 10, the hidden carpet-crash pose.
        game = getattr(self, "game", None)
        return (getattr(game, "caverns", None) is not None
                and carpet_room(game.level.number, self.room_id)
                and not self.combat.player.alive and self.sequence_state.sequence_mode == 10)

    def update_potion_controls(self):
        caverns = self.game.caverns
        if caverns is None:
            return False
        from pop2.potions import SWORD_PICKUP_TOLERANCE, SWORD_TILE, pickup_target

        potions, state, motion = caverns.potions, self.sequence_state, self.terrain_motion
        if not self.shift_held:
            potions.shift_was_held = False
        if (motion is None or motion.falling or motion.dead or self.sword_drawn
                or not self.combat.player.alive or self.ledge_hanging):
            self.pending_potion_pickup = None
            potions.picking = None
            potions.drinking = potions.effect_pending = False
            return False
        if potions.drinking:
            if state.sequence_id == 78:
                return True
            potions.drinking = False
            potions.held_kind = 0
        queued = self.pending_potion_pickup
        if queued is not None and (
                self._combat_controls_locked() or self.horizontal_input or self.up_held or self.down_held
                or (motion.room, motion.row, state.facing) != queued
                or not (self._is_resting() or state.sequence_id in RUN_CYCLE_SEQUENCES
                        or state.sequence_id == RUN_STOP_SEQUENCE)):
            self.pending_potion_pickup = queued = None
        # StandingCtrl 6:0c50/0c58 tests held Shift every eligible frame.
        # A failed try must not consume a still-held key: later eligible
        # poses retry. Released taps retain their single queued attempt.
        requested = self.shift_held or queued is not None
        # PickItUp 6:1466-1482 permits the ordinary landing crouch, but
        # explicitly excludes SEQS:20's protected hard-fall recovery.
        crouched = (state.action == 109 and state.source_sequence_id != 20
                    and not self._combat_controls_locked())
        if potions.picking is not None and not crouched:
            if state.sequence_id in (50, 117):
                return True
            potions.picking = None
        # GenCtrl also dispatches standing controls at braking poses 50-52.
        stopping = state.sequence_id == RUN_STOP_SEQUENCE and state.action in (50, 51, 52)
        if not (crouched and (potions.picking is not None or requested
                             or state.source_sequence_id == 50)
                or requested and (self._is_resting() or stopping) and not self._combat_controls_locked()):
            return False
        # GenCtrl 6:0c50/0a0c reaches TryPickUp only at an eligible pose.
        # A held Shift pressed in the air must survive until that handler.
        potions.shift_was_held = self.shift_held
        target = pickup_target(self.level_map, motion, state, self.frames[state.action],
                               sword_tolerance=SWORD_PICKUP_TOLERANCE)
        self.pending_potion_pickup = None
        if target is None:
            potions.picking = None
            return False
        tile, delta = target
        self.player_x = state.target_x + delta
        if crouched and self.waiting_controls_available():
            # GenCtrl6:0b4c: successful pickup clears low directions and
            # consumes the modifier before handing off to the item action.
            self.directional_input = self.directional_input.consume(clear=True, modifier=1)
            self.modifier_input = 1
        self.run_active = self.run_stop_requested = self.run_cycle_boundary_pending = False
        # 6:14d6-14ea: the Prince in level eight's room 9 (the throne).
        throne = self.game.level.number == 8 and motion.room == 8
        if crouched and tile.kind == SWORD_TILE and throne and not caverns.throne_done:
            # 6:14ec-152a: the first touch of the father's sword in level
            # eight's throne room: shifted 23 back (4 forward facing left),
            # the Prince collapses (SEQS 237) to song 181; the item stays.
            direction = 1 if state.facing else -1
            self.player_x = state.target_x = state.target_x - 23 * direction
            if not state.facing:
                self.player_x = state.target_x = state.target_x + 4 * direction
            state.current_x = state.target_x
            caverns.plates.songs.append(181)
            self.start_sequence(237)
        elif crouched and tile.kind == SWORD_TILE:
            self.game.sword_type = potions.take_sword(tile)
            # 6:1530-1572: the Prince has a sword again (a5-0x500a), with
            # FindSwd (song 183), except in level eight's throne room.
            self.combat.player.sword_lost = False
            if not throne:
                caverns.plates.songs.append(183)
            self.start_sequence(91)
        elif crouched:
            potions.take(tile)
            self.start_sequence(78)
        else:
            potions.picking = tile.room, tile.row * 10 + tile.column
            self.start_sequence(50)
        return True

    def _combat_controls_locked(self):
        if getattr(self, "level_complete", False):
            return True
        if self.game.entry_active:
            return True
        if self.sequence_state.source_sequence_id == 70:
            return True
        motion = getattr(self, "terrain_motion", None)
        if motion is not None and (motion.falling or motion.sinking or motion.dead):
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

    def player_collision_bounds(self):
        state = self.sequence_state
        attachment = self.attachment_frames[self.frames[state.action].afrm_index]
        return character_collision_bounds(state, self.player_bounds(), attachment, self.sword_drawn)

    def catch_falling_ledge(self):
        motion, state = self.terrain_motion, self.sequence_state
        if (motion.dead or motion.hit_fall or motion.void_fall or not self.combat.player.alive
                or not self.shift_held or self.sword_drawn
                or not self.level_map.catch_ledge(motion.room, motion.row,
                    state, self.frames[state.action], self.harbor)):
            return False
        motion.falling = False
        self.player_x = state.target_x
        self._begin_native_ledge(15)
        self.sequence_runtime.next_frame()
        # Catch 4:38da-3928 aligns using the first caught pose (80).
        self.level_map.align_catch(motion.room, motion.row, state, self.frames[state.action])
        return True

    def advance_terrain(self, old_x, old_bounds=None):
        self.jump_descent_frame = None
        motion = getattr(self, "terrain_motion", None)
        if motion is None or self._opening_active():
            return
        # StartFall reads the held left/right inputs (a5-0x3488/-0x3486).
        self.physics.held_direction = getattr(self, "horizontal_input", 0)
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
        from pop2.jump_descent import capture_jump_end, descent_drawing

        jump_end = capture_jump_end(motion, self.sequence_state)
        events = self.physics.advance(
            motion, self.sequence_runtime, old_x, self.player_bounds(),
            sword_drawn=self.sword_drawn, protected=self.ledge_hanging or self.ledge_climbing,
            frame_record=self.frames[self.action], bounds_for_state=self.player_bounds,
            old_bounds=old_bounds, alive=self.combat.player.alive,
            collision_bounds_for_state=self.player_collision_bounds,
            catch_ledge=self.catch_falling_ledge, invulnerable=getattr(self, 'god_mode', False))
        if getattr(self, 'god_mode', False) and any(event.kind == 'death' for event in events):
            # A bottomless fall has no safe floor: return to this room's F3 entry.
            life, capacity = self.combat.player.life, self.combat.player.max_life
            destination = self.screen_label(motion.room)
            if destination not in self.dev_screens():
                destination = self.screen_label(self.room_id)
            self.jump_to_screen(destination)
            self.combat.player.life, self.combat.player.max_life = life, capacity
            return
        if environment_for(self).room_crossed(old_room, motion.room):
            return
        if motion.room != old_room:
            dx = self.sequence_state.target_x - before_x
            if motion.room not in self.room_cache:
                try:
                    self.level_renderer.room(motion.room, self.game.caverns)
                except ValueError as error:
                    # Keep the playable section intact at unsupported scenery.
                    motion.room = old_room
                    motion.falling = False
                    self.sequence_state.current_x = self.sequence_state.target_x = old_x
                    self.run_active = False
                    self.run_stop_requested = False
                    self.run_cycle_boundary_pending = False
                    self.start_sequence(IDLE_SEQUENCE)
                    self.sequence_runtime.next_frame()
                    self.player_x = self.sequence_state.target_x
                    self.action = self.sequence_state.action
                    self.status.set(str(error))
                    return
            if self.run_start_x is not None:
                self.run_start_x += dx
            self.room_id = motion.room
            room = self.level_renderer.enter_room(self.room_id, self.game.caverns)
            self.background, self.foreground = room.background, room.foreground
            self.combat.enter_room(self.room_id, motion.row)
            environment_for(self).entered_room()
            self.status.set(f"Screen {self.screen_label(self.room_id)}")
        self.combat.player.row = motion.row
        for event in events:
            if event.kind == "fall":
                self.native_ledge = self.ledge_hanging = self.ledge_climbing = False
                self.ledge_climb_requested = False
                # StartFall 4:4ca8-4cb2 puts the drawn sword away immediately.
                self.sword_drawn = self.combat.player.sword_drawn = False
                self.combat.player.recovering = False
            if event.kind in ("land", "lava") or event.kind == "death" and event.impact:
                if getattr(self, "audio", None) is not None:
                    self.audio.stop_sound(8)
            if event.kind in ("fall", "wall", "gate", "death"):
                self.clear_waiting_controls()
                if event.kind in ("gate", "death"):
                    self.native_ledge = self.ledge_hanging = self.ledge_climbing = False
                    self.ledge_climb_requested = False
                # The collision/fall sequence has interrupted PutSwordAway.
                # Its Python-side lock must not outlive that animation.
                self.sword_sheathing = False
                self.run_active = False
                self.run_stop_requested = False
                self.run_cycle_boundary_pending = False
                self.jump_repeat_armed = False
                # Do not re-arm a consumed Up on wall contact: releasing Up
                # must not queue a second jump after an interrupted jump.
                if event.kind != "wall":
                    self.jump_started_for_press = False
            if event.kind == "death":
                environment_for(self).player_died()
                self.combat.player.life = 0
                self.death.begin(event.death_method if event.death_method is not None
                                 else 3 if not motion.falling else 0)
                self.status.set("Defeated")
            elif event.damage and not getattr(self, 'god_mode', False):
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
        self.jump_descent_frame = descent_drawing(jump_end, motion, self.sequence_state)

    def advance_environment(self):
        environment_for(self).frame_hook()

    def world_flipped(self):
        caverns = getattr(getattr(self, 'game', None), 'caverns', None)
        return caverns is not None and caverns.potions.flipped

    def sync_flipped_controls(self):
        # GenCtrl 4:3da6-3dcc (4:3e1c) swaps Up and Down while the world is
        # upside down; swap the held keys when it turns or rights itself.
        flipped = self.world_flipped()
        if flipped != getattr(self, 'controls_flipped', False):
            self.controls_flipped = flipped
            self.up_held, self.down_held = self.down_held, self.up_held

    def advance_level_events(self):
        if environment_for(self).level_events():
            return
        if self.game.consume_completion():
            if self.game.level.number == 6:
                self.game.ruins_entry = environment_for(self).exit_entry()
            if self.game.level.number in (1, 3, 4, 5, 6, 7):
                import json
                from pop2.level_transition import LevelExit
                from pop2.paths import ASSET_DIR

                song = environment_for(self).exit_song()
                if song is None:
                    self.game.exit = LevelExit(None, 0)
                else:
                    cues = (self.audio.cues if self.audio is not None else
                            {int(key): item for key, item in json.loads(
                                (ASSET_DIR / "audio/manifest.json").read_text(encoding="ascii"))["cues"].items()})
                    self.game.exit = LevelExit(song, cues[song]["duration"])
                    if self.audio is not None:
                        self.audio.add_song(song)
            self.clear_keys(None)
            self.status.set(f"Level {self.game.level.number} complete")

    def resolve_copy_challenge(self):
        challenge = self.copy_challenge
        if not challenge.closed:
            return
        if challenge.accepted:
            self.copy_verified = True
            self.copy_challenge = None
        elif challenge.failed:
            self.copy_challenge = None
            self.restart_level()
        self.update_cursor_visibility()
        self.clear_keys(None)
        self.pause_resume_keys.update(self.window_keys_down)
        if challenge.accepted:
            max_life = self.combat.player.max_life
            self.load_level(3)
            self.combat.player.life = self.combat.player.max_life = max_life

    def resume_combat_turn(self):
        combat = getattr(self, "combat", None)
        # A newly selected command still needs its first AnimChar frame.
        if (combat is None or getattr(self, "peaceful", False) or self.sword_sheathing
                or self.sequence_state.cursor == 0):
            return False
        combat.player.sword_drawn = self.sword_drawn
        combat.player.targetable = not self._opening_active()
        record = (self.frames[self.sequence_state.action]
                  if getattr(self, "level_map", None) is not None else None)
        if not self.sword_drawn:
            self.voluntary_turn_requested = False
        game = getattr(self, "game", None)
        caverns = getattr(game, "caverns", None)
        if caverns is not None and caverns.bridge.blocks_turn(game.level.number, combat.player.room):
            # DoTurn 6:26c0-26d8 and SwordCtrl 6:2314-2330 refuse both turns
            # in room 10 while the bridge is breaking.
            self.voluntary_turn_requested = False
            return False
        bounds = self.player_bounds() if record is not None else None
        turned = combat.choose_player_turn(record, bounds)
        if turned:
            self.status.set("Turning toward opponent")
        # SwordCtrl reaches the voluntary branch after its automatic part.
        facing_before = bool(self.sequence_state.facing)
        if (getattr(self, "voluntary_turn_requested", False)
                and combat.choose_voluntary_turn(record, bounds)):
            self.voluntary_turn_requested = False
            self.consume_voluntary_turn(facing_before)
            self.status.set("Turning with sword")
            return True
        return turned

    def advance_combat(self, old_x=None):
        combat = getattr(self, "combat", None)
        if combat is None:
            return
        combat.player_death_counter = self.death.counter
        combat.god_mode = getattr(self, 'god_mode', False)
        combat.sword_type = getattr(self.game, 'sword_type', 1)
        combat.player.sword_drawn = self.sword_drawn
        # CheckStrikes 6:58aa-592c uses row, height and actor/mode exclusions;
        # beginning a grab, climb or fall does not confer invulnerability.
        combat.player.targetable = not self._opening_active()
        harbor = getattr(self, 'harbor', None)
        if (harbor is not None and self.room_id == 18
                and (harbor.hanging_from_ship(self.room_id, self.sequence_state)
                     or self.sequence_state.sequence_id == SHIP_CLIMB_SEQUENCE)):
            combat.rooftop_escape = True
        if getattr(self, "peaceful", False):
            combat.world_frame += 1
            combat.last_guard_at = time.perf_counter()
            return
        if combat.choose_player_bump(old_x):
            self.run_active = self.run_stop_requested = False
            self.run_cycle_boundary_pending = False
            self.jump_repeat_armed = False
            self.action = self.sequence_state.action
            self.player_x = self.sequence_state.target_x
            self.status.set("Blocked by opponent")
        events = combat.step(
            time.perf_counter(), self.current_animation_interval_ms() / 1000,
        )
        for event in events:
            sound = (event.sound if event.sound is not None else
                     11 if event.kind == "parry" else 12 if event.actor == "player" else
                     59 if self.game.level.kind == 3 else 31)
            if sound:
                self.sequence_state.sound_events.append(sound)
            if event.actor == "player" and event.kind in ("hit", "death"):
                self.sword_drawn = combat.player.sword_drawn
                self.run_active = False
                self.run_direction = 0
                self.run_stop_requested = False
                self.run_cycle_boundary_pending = False
                self.sword_sheathing = False
                self.jump_started_for_press = False
                self.jump_repeat_armed = False
                self.native_ledge = self.ledge_hanging = self.ledge_climbing = False
                self.ledge_climb_requested = False
                self.sequence_state.engine_counter = 0
                if (getattr(self, "terrain_motion", None) is not None
                        and self.sequence_state.source_sequence_id != 81):
                    self.terrain_motion.falling = False
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
                                  level_number=self.game.level.number,
                                  story_flag=self.game.sword_type):
                if self.checkpoint is None or self.checkpoint.checkpoint != checkpoint:
                    self.checkpoint = RebirthSnapshot.capture(checkpoint, self.combat)
                break

    def advance_audio(self):
        if getattr(self, "intro", None) is not None:
            return
        audio = getattr(self, "audio", None)
        environment = environment_for(self)
        environment.queue_songs(audio)
        if audio is None:
            return
        if self.sequence_state.action == 167:
            self.sequence_state.sound_events.append(10)
        elif self.sequence_state.action == 154:
            # TestStrike 6:5876-588a / 5b00-5b1c also sounds an empty swing.
            self.sequence_state.sound_events.append(11)
        audio.drain(self.sequence_state, gate_events=environment.gate_audio())
        if self.combat is not None:
            for guards, _generators in self.combat.room_encounters.values():
                for guard in guards:
                    if guard.state.action == 167:
                        guard.state.sound_events.append(10)
                    elif guard.state.action == 154 and contact_allowed(guard, self.combat.player):
                        # NPCs use 6:5ab4-5af8, after the valid-target gate.
                        guard.state.sound_events.append(11)
                    audio.drain(guard.state, not self.peaceful and guard.room == self.room_id)
            for actor in self.combat.visible_ruins():
                audio.drain(actor.state, not self.peaceful)
        motion = getattr(self, "terrain_motion", None)
        if motion is not None:
            environment.ambient_audio(audio, motion)
        audio.flush()

    def restart_after_death(self, *, preserve_controls=False):
        if not self.death.can_restart:
            return False
        held = ((self.window_keys_down - self.pause_resume_keys) & PAUSE_GAMEPLAY_KEYS
                if preserve_controls else set())
        self.restart_level()
        self.restore_held_gameplay_controls(held)
        return True

    def restart_level(self):
        level = self.game.level.number
        # RestartGame 2:5b66 asks CheckPlayNIS (2:0180) before every restart;
        # from level four it may select a tree scene (20..27 -> variants 1..8).
        scene = self.game.story.select_scene(level, level) if level >= 4 else None
        tree_due = scene is not None and 20 <= scene <= 28
        # Reset the world without flashing its entry frame before the NIS.
        self.restart_level_now(redraw=not tree_due)
        if tree_due:
            self.start_tree(scene - 19)
            self.render()

    def restart_level_now(self, *, redraw=True):
        # FirstFrame 2:601e-6024 removes a time message at every level start;
        # the Prince initializer 2:5e9c also clears the float timer.
        self.time_message, self.time_message_frames = None, 0
        if self.game.caverns is not None:
            self.game.caverns.potions.float_timer = 0
        self.remember_development_room()
        held = set(self.window_keys_down)
        snapshot = self.checkpoint
        if snapshot is None:
            max_life = self.combat.player.max_life if self.combat is not None else None
            if self.game.caverns is not None:
                initial = self.game.caverns.potions.starting_max_life
                if initial is not None:
                    max_life = initial
            self.restart_opening(redraw=redraw)
            if max_life is not None:
                self.combat.player.life = self.combat.player.max_life = max_life
                if redraw:
                    self.render()
        else:
            if self.animation_after_id is not None:
                self.root.after_cancel(self.animation_after_id)
                self.animation_after_id = None
            snapshot.restore_world(self.combat)
            self.game.arm_prince()
            point = snapshot.checkpoint
            self.jump_to_room(point.room, point.row, point.x, snapshot.facing,
                              reset_guards=False, preserve_checkpoint=True, redraw=redraw)
            self.next_animation_at = time.perf_counter()
            if not self.in_animation_tick:
                self.schedule_next_animation()
        self.pause_resume_keys.update(held)

    def remember_development_room(self):
        if not self.level_navigation_available():
            return
        if not hasattr(self, 'development_return_screens'):
            self.development_return_screens = {}
        self.development_return_screens[self.game.level.number] = self.screen_label(self.room_id)

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
        cached = getattr(self, "development_playback_parts", None)
        if cached is not None:
            return cached
        from pop2.attract import read_attract
        from pop2.intro import read_program
        from pop2.paths import ASSET_DIR
        from pop2.playback_navigation import playback_parts, ending_parts, discovery_parts

        if self.attract_data is None:
            self.attract_data = read_attract(ASSET_DIR / "attract.json")
        intro_program = (self.intro_assets.program if self.intro_assets is not None else
                         read_program(ASSET_DIR / "intro.json"))
        ending_program = (self.ending_assets.program if self.ending_assets is not None else
                          read_program(ASSET_DIR / "ending.json"))
        discovery_program = (self.discovery_assets.program if self.discovery_assets is not None else
                             read_program(ASSET_DIR / "discovery.json"))
        if self.game.level.number == 1:
            screen_label = self.screen_label
        else:
            from pop2.level_data import LevelDefinition
            entries = LevelRenderer(LevelDefinition.read(self.resources.prince, 1),
                                    preload_room=False).screen_entries()
            labels = {room: label for label, room in entries.items()}
            screen_label = lambda room: labels.get(room, f"Room ID {room + 1}")
        self.development_playback_parts = (playback_parts(intro_program, self.attract_data, screen_label)
                                           + ending_parts(ending_program) + discovery_parts(discovery_program))
        return self.development_playback_parts

    def current_playback_part(self):
        stage = self.attract_stage
        if stage is None and self.game.level.number in (2, 4):
            return next((index for index, part in enumerate(self.development_parts())
                         if part.stage == "level" and part.index == self.game.level.number), 0)
        position = (self.demo.index if stage == "demo" else
                    self.intro.position - 1 if stage in ("intro", "ending", "discovery") else
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
        elif part.stage == "ending":
            self.start_ending(part.index)
        elif part.stage == "discovery":
            self.start_discovery(part.index)
        elif part.stage == "level":
            self.load_level(part.index)
        else:
            raise ValueError("Unknown playback stage")
        self.last_intro_at = self.last_demo_at = time.perf_counter()
        self.clear_keys(None)

    def finish_attract_stage(self):
        if self.attract_stage == "ending":
            self.finish_ending()
        elif self.attract_stage == "discovery":
            self.finish_discovery()
        elif self.attract_stage == "tree":
            self.finish_tree()
        elif self.attract_stage == "credits":
            self.start_intro()
        else:
            self.start_demo()
        self.render()

    def start_demo(self, part_index=None):
        from pop2.attract import DemoEncounter, DemoPlayer, read_attract
        from pop2.paths import ASSET_DIR

        if self.attract_data is None:
            self.attract_data = read_attract(ASSET_DIR / "attract.json")
        if self.game.level.number != 1:
            self.load_level(1)
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
        self.active_save_path = None
        self.copy_verified = False
        self.copy_challenge = None
        if self.game.level.number != 1:
            self.load_level(1)
        self.game.story = StoryProgress()
        self.restart_opening(play_sound=not self.with_intro)
        if self.with_intro:
            self.start_intro()
            self.render()

    def finish_intro(self):
        held = set(self.window_keys_down)
        if self.attract_stage == "ending":
            self.finish_ending()
        elif self.attract_stage == "discovery":
            self.finish_discovery()
        elif self.attract_stage == "tree":
            self.finish_tree(skipped=True)
        else:
            if self.game.level.number != 1:
                self.load_level(1)
            self.restart_opening()
        self.pause_resume_keys.update(held)

    def load_ending_assets(self):
        if self.ending_assets is None:
            from pop2.intro import IntroAssets
            self.ending_assets = IntroAssets(program_name="ending.json")

    def start_ending(self, part_index=None):
        from pop2.intro import IntroPlayer

        self.end_demo()
        self.load_ending_assets()
        self.clear_keys(None)
        self.game.exit = None
        self.level_complete = False
        self.attract_stage = "ending"
        if self.audio is not None:
            self.audio.reset()
        self.intro = IntroPlayer(self.ending_assets, self.audio if part_index is None else None)
        if part_index is not None:
            self.intro.audio = self.audio
            self.intro.seek_operation(part_index)
        self.last_intro_at = time.perf_counter()
        self.status.set("Voyage")

    def finish_ending(self):
        max_life = self.combat.player.max_life if self.combat is not None else None
        self.load_level(2)
        if max_life is not None:
            self.combat.player.life = self.combat.player.max_life = max_life
            self.render()

    def start_discovery(self, part_index=None):
        from pop2.intro import IntroAssets, IntroPlayer

        self.end_demo()
        if self.discovery_assets is None:
            self.discovery_assets = IntroAssets(program_name='discovery.json')
        self.clear_keys(None)
        self.game.exit = None
        self.level_complete = False
        self.attract_stage = 'discovery'
        if self.audio is not None:
            self.audio.reset()
        self.intro = IntroPlayer(self.discovery_assets, self.audio if part_index is None else None)
        if part_index is not None:
            self.intro.audio = self.audio
            self.intro.seek_operation(part_index)
        self.last_intro_at = time.perf_counter()
        self.status.set('Discovery')

    def start_tree(self, variant):
        from pop2.intro import IntroAssets, IntroPlayer

        cache = getattr(self, 'tree_assets', None)
        if cache is None:
            cache = self.tree_assets = {}
        if variant not in cache:
            cache[variant] = IntroAssets(program_name=f'tree-{variant}.json')
        self.end_demo()
        self.clear_keys(None)
        self.attract_stage = 'tree'
        self.tree_variant = variant
        if self.audio is not None:
            self.audio.reset()
        self.intro = IntroPlayer(cache[variant], self.audio)
        self.last_intro_at = time.perf_counter()
        self.status.set('Tree')

    def start_carpet(self):
        # NISCarpet (15:1630): the flight from level five's caverns to the
        # ruins' cliff. It ends like a tree scene, loading the next level.
        from pop2.intro import IntroAssets, IntroPlayer

        from pop2.carpet import OPEN_SONG
        from pop2.intro import game_song

        if getattr(self, 'carpet_assets', None) is None:
            self.carpet_assets = IntroAssets(program_name='carpet.json')
        music = None
        if self.audio is not None:
            played = self.audio.music_elapsed()
            if (self.game.level.number == 5 and self.audio.current_music == OPEN_SONG
                    and played is not None):
                # 2:61ce-61ea skips ResetSoundItem after levels five and nine:
                # FlyinRug, started when the Prince sat down, plays on and
                # the scene's cue operations wait for its markers a and c.
                music = OPEN_SONG, played, game_song(OPEN_SONG)
        self.end_demo()
        self.clear_keys(None)
        self.attract_stage = 'tree'
        self.tree_variant = None
        if self.audio is not None and music is None:
            self.audio.reset()
        self.intro = IntroPlayer(self.carpet_assets, self.audio, music)
        self.last_intro_at = time.perf_counter()
        self.status.set('Carpet')

    def start_vision(self, wake):
        """PlayNIS(6) from 7:38ca: the vision at the throne in level eight.
        Returns False when the scene is not imported; `wake` runs after it."""
        from pop2.intro import IntroAssets, IntroPlayer, game_song
        from pop2.paths import ASSET_DIR
        from pop2.terrain import floor_y

        if not (ASSET_DIR / 'throne.json').is_file():
            return False
        if getattr(self, 'throne_assets', None) is None:
            self.throne_assets = IntroAssets(program_name='throne.json')
        state = self.sequence_state
        music = None
        if self.audio is not None and self.audio.current_music == 181:
            played = self.audio.music_elapsed()
            if played is not None:
                # Throne2, added at the collapse, plays on: the scene waits
                # for its end (15:67f2) before the vision's own music.
                music = 181, played, game_song(181)
        self.clear_keys(None)
        self.attract_stage = 'tree'
        self.tree_variant = None
        self.after_vision = wake
        if self.audio is not None and music is None:
            self.audio.reset()
        # The Prince's native X (207 origin), facing (0 right, -1 left) and Y.
        self.intro = IntroPlayer(self.throne_assets, self.audio, music,
                                 variant=0 if state.facing else -1,
                                 prince=(state.target_x + 207, floor_y(self.terrain_motion.row) + state.current_y),
                                 status=self.native_viewport.crop((0, 365, 512, 384)))
        self.last_intro_at = time.perf_counter()
        self.status.set('Vision')
        return True

    def start_temple_ride(self, finish):
        """NISTemple (15:5fd4) after level nine; `finish` runs after it.
        Returns False when the scene is not imported."""
        from pop2.intro import IntroAssets, IntroPlayer
        from pop2.paths import ASSET_DIR

        if not (ASSET_DIR / 'temple.json').is_file():
            return False
        if getattr(self, 'temple_assets', None) is None:
            self.temple_assets = IntroAssets(program_name='temple.json')
        self.clear_keys(None)
        self.attract_stage = 'tree'
        self.tree_variant = None
        self.after_vision = finish
        if self.audio is not None:
            self.audio.reset()
        self.intro = IntroPlayer(self.temple_assets, self.audio)
        self.last_intro_at = time.perf_counter()
        self.status.set('The ride to the temple')
        return True

    def finish_level_four(self):
        # CheckPlayNIS(4, 5) (2:0180) shows the first tree scene here when no
        # level-four restart has, then RestartGame loads level five.
        self.finish_level_via_story(4, 5)

    def finish_level_via_story(self, previous, following):
        # CheckPlayNIS (2:0180) may select a tree scene (20..27) before
        # RestartGame loads the next level.
        from pop2.paths import ASSET_DIR

        self.game.exit = None
        scene = self.game.story.select_scene(previous, following)
        if scene is not None and 20 <= scene <= 27:
            self.game.complete = False
            self.next_level_after_tree = following
            self.start_tree(scene - 19)
        elif scene == 1 and (ASSET_DIR / 'carpet.json').is_file():
            self.game.complete = False
            self.next_level_after_tree = following
            self.start_carpet()
        else:
            self.enter_next_level(following)

    def enter_next_level(self, number, keep_music=False):
        max_life = self.combat.player.max_life if self.combat is not None else None
        self.load_level(number, keep_music=keep_music)
        if max_life is not None:
            self.combat.player.life = self.combat.player.max_life = max_life
            self.render()

    def finish_tree(self, *, skipped=False):
        held = set(self.window_keys_down)
        wake = getattr(self, 'after_vision', None)
        if wake is not None:
            # NIS 6 returns to the throne room; its last song plays on.
            self.after_vision = None
            self.intro = self.attract_stage = None
            wake()
            self.pause_resume_keys.update(held)
            self.next_animation_at = time.perf_counter()
            self.render()
            return
        following = getattr(self, 'next_level_after_tree', None)
        self.next_level_after_tree = None
        if following is not None:
            # FlyinRug, carried into the carpet scene, also plays on into
            # level six (no ResetSoundItem after level five, 2:61ce-61ea).
            keep_music = (not skipped and self.intro is not None
                          and 0 in getattr(self.intro, 'carried_music', {}))
            self.intro = self.attract_stage = None
            self.enter_next_level(following, keep_music=keep_music)
            self.pause_resume_keys.update(held)
            return
        self.intro = self.attract_stage = None
        if self.audio is not None:
            self.audio.reset()
        if getattr(self, 'tree_variant', None) == 9:
            # TimeUp 2:7194: after NIS 20 FrameAdv returns -1 (2:62ba-62c0),
            # ending RestartGame's loop: the campaign is over.
            self.new_game()
            return
        self.clear_keys(None)
        self.pause_resume_keys.update(held)
        self.next_animation_at = time.perf_counter()
        self.render()

    def show_remaining_time(self):
        # ReadKeyboard 2:4850-485e: Space requests KeepTime's HUD message;
        # it does not start or rewind the deferred campaign clock.
        if not self.game.story.clock_started:
            return
        self.time_message = self.game.story.message_text()
        self.time_message_frames = MESSAGE_FRAMES
        self.render()

    def advance_story_clock(self):
        # KeepTime 2:51f4 runs once per FrameAdv for a living Prince; at zero
        # FrameAdv calls TimeUp 2:7194 (PlayNIS 28 -> tree variant 9).
        story = self.game.story
        if story.advance_frame(self.combat is not None and self.combat.player.alive) and story.expired:
            story.tree_stage = -1
            self.time_message = None
            self.start_tree(9)
            return True
        frames = getattr(self, 'time_message_frames', 0)
        if story.message_pending == 'seconds':
            frames = 0
        if story.message_pending and not frames:
            self.time_message = story.message_text()
            frames = MESSAGE_FRAMES
            story.message_pending = None
        elif frames:
            # FrameAdv 2:6834 counts the message down; at 1 it is erased (67e8).
            frames -= 1
            if frames <= 1:
                frames, self.time_message = 0, None
        self.time_message_frames = frames
        return False

    def finish_discovery(self):
        max_life = self.combat.player.max_life if self.combat is not None else None
        self.load_level(4)
        if max_life is not None:
            self.combat.player.life = self.combat.player.max_life = max_life
            self.render()

    def restart_opening(self, _event=None, play_sound=True, *, redraw=True):
        self.copy_challenge = None
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
        if self.game.caverns is not None:
            self.game.caverns.configure_level_entry(self.level_renderer.cavern_program, self.game)
            self.game.caverns.configure_torches(self.level_renderer.cavern_program.get('torches', {}))
            self.game.caverns.configure_lava(self.level_renderer.cavern_program.get('lava'))
        self.reset_level_controls()
        room = (self.level_renderer.enter_room(self.room_id, self.game.caverns)
                if hasattr(self, "level_renderer") else None)
        if room is not None:
            self.background, self.foreground = room.background, room.foreground
        self.action = self.sequence_state.action
        self.player_x = self.sequence_state.target_x
        self.status.set("Window escape" if self._opening_active() else f"Level {self.game.level.number}")
        if play_sound:
            self.advance_audio()
        if redraw:
            self.render()
        self.next_animation_at = time.perf_counter()
        if not self.in_animation_tick:
            self.schedule_next_animation()
        return "break"

    def reset_level_controls(self):
        self.jump_descent_frame = None
        self.cancel_gate_presentation()
        self.pending_potion_pickup = None
        self.queue_grace_remaining_ms = 0
        self.queue_grace_command = None
        self.run_active = False
        self.run_stop_requested = False
        self.run_direction = 0
        self.run_start_x = None
        self.run_cycle_boundary_pending = False
        self.sword_drawn = False
        self.step_cautious = True
        self.shift_turn_direction = 0
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
                     preserve_checkpoint=False, *, redraw=True):
        if self.level_map is None or not 0 <= room_id < 32 or not 0 <= row < 3:
            raise ValueError("Invalid level, room or floor")
        self.level_renderer.room(room_id, self.game.caverns)
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
        room = self.level_renderer.enter_room(room_id, self.game.caverns)
        self.background, self.foreground = room.background, room.foreground
        self.player_x, self.action = x, 15
        if getattr(self, "audio", None) is not None:
            self.audio.reset()
            self.advance_audio()
        self.status.set(f"Level {self.game.level.number} / Screen {self.screen_label(room_id)}")
        if redraw:
            self.render()

    def dev_screens(self):
        return self.level_renderer.screen_entries() if self.level_map is not None else {}

    def development_levels(self):
        cached = getattr(self, "development_level_options", None)
        if cached is not None:
            return cached
        from pop2.level_data import LevelDefinition

        options = []
        from pop2.caverns import scenery_available

        for number in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            if number >= 6 and not scenery_available(number):
                continue
            renderer = (self.level_renderer if self.game.level.number == number else
                        LevelRenderer(LevelDefinition.read(self.resources.prince, number),
                                      preload_room=False))
            screens = tuple(renderer.screen_entries())
            if screens:
                options.append((number, f"Level {number}", screens))
        self.development_level_options = tuple(options)
        return self.development_level_options

    def development_map(self, number):
        from pop2.development_map import cached_development_map

        cache = getattr(self, 'development_maps', None)
        if cache is None:
            self.development_maps = cache = {}
        if number not in cache:
            cache[number] = cached_development_map(self.resources.level(number), self.preview_fingerprint())
        return cache[number]

    def preview_fingerprint(self):
        from pop2.preview_cache import preview_fingerprint

        if not hasattr(self, 'development_preview_fingerprint'):
            self.development_preview_fingerprint = preview_fingerprint()
        return self.development_preview_fingerprint

    def development_playback_preview(self, indices):
        from pop2.playback_preview import PlaybackPreviews

        if not hasattr(self, 'development_playback_previews'):
            self.development_playback_previews = PlaybackPreviews(
                self.resources, self.development_parts(), self.attract_data, self.preview_fingerprint())
        return self.development_playback_previews.group(indices)

    def screen_label(self, room):
        return next((label for label, target in self.dev_screens().items() if target == room),
                    f"Room ID {room + 1}")

    def jump_to_screen(self, label):
        screens = self.dev_screens()
        room = screens[label]
        if room == self.level_map.start_room:
            if not self.game.level.window_escape:
                return self.load_level(self.game.level.number)
            return self.jump_to_room(room, row=1, x=411, facing=1)
        secret = label == "Secret (right)"
        if secret:
            row, column = next((row, column) for row in range(3) for column in range(10)
                               if self.level_map.tile(room, column, row).kind == 1)
            return self.jump_to_room(room, row=row, x=column * TILE_WIDTH + 30, facing=1)
        if label == "8":
            # Entry from screen 7 is the upper roof, not the quay below.
            row, x = 0, 5 * TILE_WIDTH + 14
        elif self.game.level.kind == 1 and label == "2 (Stones)":
            rows = [row for row in range(3)
                    if self.level_map.tile(room, 9, row).kind == 1]
            if not rows:
                raise ValueError("The stone screen has no supported entry")
            return self.jump_to_room(room, rows[0], 9 * TILE_WIDTH + 30, facing=0)
        elif self.game.level.kind == 3:
            from pop2.development_entry import room_entry

            # Retain Room 21's useful lower-floor test entry; level five's
            # Room 3 starts on the upper platform beside the bars' plate.
            preferred = {(3, 20): 2, (5, 2): 0}.get((self.game.level.number, room))
            row, column = room_entry(self.level_map, room, preferred_row=preferred)
            return self.jump_to_room(room, row=row, x=column * TILE_WIDTH + 30, facing=0)
        elif self.game.level.kind == 4:
            from pop2.development_entry import room_entry

            row, column = room_entry(self.level_map, room)
            x = column * TILE_WIDTH + 30
        else:
            rows = [row for row in range(3)
                    if self.level_map.tile(room, 9, row).kind == 1]
            if not rows:
                raise ValueError("This screen has no supported entry")
            # Use the same supported entry-cell inset as the secret-room warp.
            # A near-boundary spawn changes the phase of subsequent run stops.
            row, x = rows[0], 9 * TILE_WIDTH + 30
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
        if (getattr(self, "intro", None) is not None or getattr(self, "demo", None) is not None
                or getattr(self, 'copy_challenge', None) is not None):
            return 1000 / 60
        interval_ms = animation_interval_for_frame(
            self.sequence_state.sequence_id, self.sequence_state.action)
        if self._combat_controls_locked() and self.sword_drawn:
            interval_ms = COMBAT_ANIMATION_INTERVAL_MS
        return interval_ms

    def schedule_next_animation(self):
        self.schedule_gate_presentation()
        if self.paused or (getattr(self, "level_complete", False) and self.game.exit is None):
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

    def cancel_gate_presentation(self):
        pending = getattr(self, 'gate_presentation_after_id', None)
        if pending is not None:
            self.root.after_cancel(pending)
        self.gate_presentation_after_id = None

    def schedule_gate_presentation(self):
        self.cancel_gate_presentation()
        caverns = getattr(getattr(self, 'game', None), 'caverns', None)
        if self.paused or caverns is None:
            return
        delay = caverns.crush.next_delay_ms()
        if delay is not None:
            if caverns.crush.last_updated_at is not None:
                delay += (caverns.crush.last_updated_at - time.perf_counter()) * 1000
            self.gate_presentation_after_id = self.root.after(
                max(1, math.ceil(delay - 1e-6)), self.advance_gate_presentation)

    def advance_gate_presentation(self):
        self.gate_presentation_after_id = None
        caverns = getattr(getattr(self, 'game', None), 'caverns', None)
        if self.paused or caverns is None or caverns.crush.key is None:
            return
        state = self.sequence_state
        caverns.crush.advance(self.level_map, self.terrain_motion, state,
                              self.frames[state.action], caverns.plates,
                              now=time.perf_counter())
        room = self.level_renderer.enter_room(self.room_id, caverns)
        self.background, self.foreground = room.background, room.foreground
        self.render()
        self.schedule_gate_presentation()

    def pause_gate_presentation(self, paused, now):
        self.cancel_gate_presentation()
        caverns = getattr(getattr(self, 'game', None), 'caverns', None)
        if caverns is None or caverns.crush.key is None:
            return
        if paused:
            caverns.crush.update(now)
            room = self.level_renderer.enter_room(self.room_id, caverns)
            self.background, self.foreground = room.background, room.foreground
        else:
            caverns.crush.last_updated_at = now
            self.schedule_gate_presentation()

    def player_sprite(self, action=None):
        # Lava's SEQS 116 is drawn by its pool. Scythes also use death
        # method 5, but their ordinary Kid frames 267-271 must remain visible.
        death = getattr(self, 'death', None)
        if (death is not None and death.counter >= 0 and death.method == 5
                and self.sequence_state.source_sequence_id == 116):
            return None
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

    def sword_set(self):
        """LoadSwordSet 3:5a4e: sword type 2 draws SHPL 1200 with AFRM 25201
        (3:5aae-5ab6, 5b2a-5b3e); every other type SHPL 1000 with AFRM 25001."""
        game = getattr(self, 'game', None)
        return 2 if getattr(game, 'sword_type', 1) == 2 else 1

    @property
    def attachment_frames(self):
        if self.sword_set() != 2:
            return self.ordinary_attachment_frames
        cached = getattr(self, '_second_sword_attachments', None)
        if cached is None:
            from pop2.animation_data import parse_aframe_records

            cached = self._second_sword_attachments = parse_aframe_records(
                self.resources.kid['AFRM'][25201]['data'])
        return cached

    @attachment_frames.setter
    def attachment_frames(self, frames):
        self.ordinary_attachment_frames = frames

    def sword_sprite(self):
        attachment_type, shape_index, dx, dy = self.attachment_frames[
            self.frames[self.action].afrm_index
        ]
        if attachment_type == 3 and self.game.caverns is not None:
            from pop2.caverns import flask_assets

            resources, palette = flask_assets()
            shape_id = 3001 + shape_index
            key = 'flask', shape_id
            if key not in self.sword_sprite_cache:
                self.sword_sprite_cache[key] = decode_shap(resources['SHAP'][shape_id]['data'], palette)
            return self.sword_sprite_cache[key], dx, dy
        if attachment_type != 1 or shape_index < 0:
            return None
        base = self.first_sword_shape_id
        if self.sword_set() == 2:
            base = int.from_bytes(self.resources.prince['SHPL'][1200]['data'][:2], 'big')
        shape_id = base + shape_index
        if shape_id not in self.sword_sprite_cache:
            self.sword_sprite_cache[shape_id] = decode_shap(
                self.sword_shapes[shape_id]["data"], self.sword_palette
            )
        return self.sword_sprite_cache[shape_id], dx, dy

    def composite_actor(self, frame, layer, row=None, bottom=None, state=None, bounds=None, record=None):
        # ClipChar 4:4152 skips an actor that IsCharNonViewable (4:4724)
        # marks by +0x34, e.g. the Prince after SEQS:27 sinks him (-21 7).
        if getattr(state, 'sequence_mode', 0) in (4, 5, 6, 7, 10, 12):
            return frame
        # An upper roof's foreground must not erase a lower-row fall.
        rooms = getattr(self, "room_cache", {})
        room = rooms.get(getattr(self, "room_id", None))
        mask = (room.actor_mask(row, bottom, state, bounds, record)
                if room is not None and row is not None else self.foreground.getchannel("A"))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), ImageChops.invert(mask)))
        level = getattr(getattr(self, 'game', None), 'level', None)
        level_kind = getattr(state, 'level_kind', getattr(level, 'kind', None))
        if level_kind == 3 and state is not None and bounds is not None and row is not None:
            clip_top = cavern_clip_top(self.level_map, self.room_id, row, state, bounds)
            if clip_top > 0:
                layer.paste((0, 0, 0, 0), (0, 0, layer.width, clip_top))
        if level_kind in (2, 3, 4) and state is not None and bounds is not None and row is not None:
            exit_clip = cavern_exit_clip(self.level_map, self.room_id, row, state, record)
            if exit_clip is not None:
                top, right = exit_clip
                layer.paste((0, 0, 0, 0), (0, 0, layer.width, top))
                layer.paste((0, 0, 0, 0), (right, 0, layer.width, layer.height))
        # ClipChar 4:4218-4228 restricts the dock waterline to environment 5.
        if level_kind == 5 and self.room_id in (15, 18):
            water_y = 354 if state is not None and state.animation_state == 9 else 327
            layer.paste((0, 0, 0, 0), (0, water_y, layer.width, layer.height))
        if (getattr(state, 'level_kind', None) == 1
                and getattr(state, 'source_sequence_id', None) == 27):
            # SetupSand 18:057a draws the surface at bottom 243.
            layer.paste((0, 0, 0, 0), (0, 243, layer.width, layer.height))
        frame = Image.alpha_composite(frame, layer)
        if level_kind in (2, 3, 4) and room is not None and state is not None and bounds is not None:
            frame = room.draw_actor_foreground(frame, state, bounds)
            if (state.actor_type in (0, 2, 4) and record is not None
                    and actor_draw_order(state, record, bounds, row)[0] == 0):
                # IndexCell1 maps offscreen actors to bucket30, drawn before
                # visible debris. Preserve that order where a falling actor
                # still overlaps the last visible slab at the room boundary.
                from pop2.caverns import draw_cavern_falling

                frame = draw_cavern_falling(frame, self.room_id, self.game.caverns,
                    self.game.level.data, room, level_number=self.game.level.number, actor_bounds=bounds)
        return frame

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

    def draw_screenshot_notice(self, viewport, *, visible=False):
        gallery = (self.game_menu.screenshot_gallery if self.game_menu is not None
                   and self.game_menu.page == 'screenshots' else None)
        if gallery is not None and (gallery.choosing or gallery.deleting):
            return viewport
        message = None if gallery is not None else getattr(self, "screenshot_toast", None)
        showing_toast = message is not None
        if not showing_toast and (self.game_menu is None or self.game_menu.page != "screenshots"):
            return viewport
        if not showing_toast:
            message = "Take Screenshots with F8"
        text = self.ui_font.text(message, (253, 255, 168, 255))
        sx = viewport.width / (510 if visible else VIEWPORT_WIDTH)
        sy = viewport.height / VIEWPORT_HEIGHT
        x = 8 if showing_toast else VIEWPORT_WIDTH - text.width - 8

        def point(x, y):
            return round((x - int(visible)) * sx), round(y * sy)

        if showing_toast:
            plate_height = text.height + 8
            plate_top = ROOM_HEIGHT - 2 - plate_height
            y = plate_top + (plate_height - text.height) // 2
            plate = Image.new("RGBA", viewport.size, (0, 0, 0, 0))
            ImageDraw.Draw(plate).rectangle(
                (*point(x - 4, plate_top), *point(x + text.width + 4, ROOM_HEIGHT - 3)),
                fill=(0, 0, 0, 128),
            )
            viewport = Image.alpha_composite(viewport, plate)
        else:
            y = ROOM_HEIGHT - self.ui_font.height - 6
        size = max(1, round(text.width * sx)), max(1, round(text.height * sy))
        if text.size != size:
            text = text.resize(size, Image.Resampling.NEAREST)
        viewport.paste((0, 0, 0, 255), point(x + 1, y + 1), text)
        viewport.paste(text, point(x, y), text)
        return viewport

    def render(self):
        if getattr(self, "intro", None) is not None:
            viewport = Image.new("RGBA", (VIEWPORT_WIDTH, VIEWPORT_HEIGHT), (0, 0, 0, 255))
            viewport.paste(self.intro.frame().crop((0, 0, ROOM_WIDTH, VIEWPORT_HEIGHT)),
                           (ROOM_ORIGIN_X, 0))
            self.screenshot_viewport = viewport.copy()
            if self.dev_menu is not None:
                viewport = self.dev_menu.draw(viewport, self.ui_font)
            elif self.game_menu is not None:
                self.refresh_game_menu()
                viewport = self.game_menu.draw(viewport, self.ui_font)
            elif self.paused:
                viewport = self.draw_cutscene_pause(viewport)
            viewport = self.draw_screenshot_notice(viewport)
            self.native_viewport = viewport
            self.present_viewport()
            return
        environment = environment_for(self)
        frame = self.background.copy()
        frame = self.level_renderer.animated_layer(frame, self.room_id, self.harbor,
                    frame_number=self.combat.world_frame if self.combat is not None else 0,
                    desert=getattr(self.game, "desert", None), caverns=self.game.caverns)
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
        motion = getattr(self, "terrain_motion", None)
        if motion is not None:
            frame = environment.scenery_layer(frame, motion)
        frame = Image.alpha_composite(frame, self.foreground)
        self.level_renderer.remember_scenery(frame)
        hide_guards = getattr(self, "peaceful", False) and getattr(self, "demo", None) is None
        actors = []
        crush_poses = getattr(self, 'slab_crush_poses', {})
        if combat is not None and not hide_guards:
            for guard in (*combat.visible_guards(), *combat.visible_ruins()):
                layer = Image.new("RGBA", frame.size)
                ground = floor_y(guard.row) + environment.draw_sag(guard)
                state = slab_crush_draw_state(guard, crush_poses)
                record = self.guard_art.frames[actor_frame_index(state)]
                neck = getattr(getattr(guard, 'ruins', None), 'neck', None)
                if neck is not None:
                    # AlignHeadOnKidNeck 7:0006 gives the drawing point itself.
                    shift = record.offset_x if state.facing else -record.offset_x
                    state = replace(state, target_x=neck[0] - shift,
                                    current_y=neck[1] - ground - record.offset_y)
                self.guard_art.draw(layer, state, ground, guard.palette_variant)
                bounds = self.guard_art.bounds(state, ground)
                actors.append((state, record, bounds, guard.row, layer))
        player_layer = Image.new("RGBA", frame.size)
        draw_state, draw_height = environment.drawn_player(self.sequence_state)
        draw_action = self.action if draw_height is None else draw_state.action
        sprite = self.player_sprite(draw_action)
        drawn_bounds = None
        if sprite is not None:
            record = self.frames[draw_action]
            if draw_height is not None and draw_height != sprite.height:
                sprite = sprite.resize((sprite.width, draw_height), Image.Resampling.NEAREST)
            anchor_x = record.offset_x
            if draw_state.facing:
                sprite = ImageOps.mirror(sprite)
                anchor_x = sprite.width - anchor_x
            x = (self.player_x if draw_height is None else draw_state.target_x) - anchor_x
            y = character_sprite_top(
                self.player_floor_y()
                + record.offset_y
                + draw_state.current_y
                + (environment.draw_sag(combat.player) if combat is not None else 0),
                sprite.height,
            )
            player_layer.paste(sprite, (x, y), sprite)
            drawn_bounds = (x, y, x + sprite.width - 1, y + sprite.height - 1)
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
        draw_bounds = drawn_bounds if draw_height is not None else player_bounds
        if motion is not None and draw_bounds is not None:
            actors.append((draw_state, self.frames[draw_action], draw_bounds, motion.row, player_layer))
            actors.sort(key=lambda actor: actor_draw_order(*actor[:4]))
            for state, record, bounds, row, layer in actors:
                frame = self.composite_actor(frame, layer, row, bounds[3], state, bounds, record)
        else:
            for state, record, bounds, row, layer in actors:
                frame = self.composite_actor(frame, layer, row, bounds[3], state, bounds, record)
            frame = self.composite_actor(frame, player_layer)
        if motion is not None:
            frame = environment.after_actors(frame, player_bounds)

        if combat is not None:
            for guard in (() if hide_guards else (*combat.visible_guards(), *combat.visible_ruins())):
                layer = Image.new("RGBA", frame.size)
                ground = floor_y(guard.row) + environment.draw_sag(guard)
                state = slab_crush_draw_state(guard, crush_poses)
                self.hit_art.draw(layer, state, ground)
                bounds = self.guard_art.bounds(state, ground)
                record = self.guard_art.frames[actor_frame_index(state)]
                frame = self.composite_actor(frame, layer, guard.row, bounds[3],
                                             state, bounds, record)
            layer = Image.new("RGBA", frame.size)
            self.hit_art.draw(layer, combat.player.state,
                              self.player_floor_y() + environment.draw_sag(combat.player))
            frame = self.composite_actor(frame, layer, motion.row if motion is not None else None,
                                         player_bounds[3] if player_bounds is not None else None,
                                         self.sequence_state, player_bounds, self.frames[self.action])
        if show_opening and opening.glass_frame is not None:
            glass = self.glass_sprites[opening.glass_frame]
            glass_x, glass_y = GLASS_POSITIONS[opening.glass_frame]
            layer = Image.new("RGBA", frame.size)
            layer.paste(glass, (glass_x, character_sprite_top(glass_y, glass.height)), glass)
            frame = self.composite_actor(frame, layer)
        frame = self.level_renderer.animated_layer(frame, self.room_id, self.harbor, front=True,
                                                  desert=getattr(self.game, "desert", None),
                                                  caverns=self.game.caverns)
        if self.world_flipped():
            # 2:5952-59de draws the game area (365 rows) upside down.
            frame = ImageOps.flip(frame)
        viewport = Image.new("RGBA", (VIEWPORT_WIDTH, VIEWPORT_HEIGHT), (0, 0, 0, 255))
        viewport.paste(frame, (ROOM_ORIGIN_X, 0))
        if combat is not None and not self.death.prompt_visible:
            player_life = environment.display_life(combat.player.life)
            self.health_art.draw(viewport, combat, show_opponent=not hide_guards,
                                 player_life=player_life)
        self.screenshot_viewport = viewport.copy()
        if self.death.prompt_visible:
            text = self.restart_text
            ink = text.getbbox()
            y = ROOM_HEIGHT + (VIEWPORT_HEIGHT - ROOM_HEIGHT - (ink[3] - ink[1])) // 2 - ink[1]
            self.screenshot_viewport.paste(text, ((VIEWPORT_WIDTH - text.width) // 2, y), text)
        message = getattr(self, 'time_message', None)
        notice = getattr(self, 'audio_notice_text', None)
        hud_text = (notice if notice is not None else
                    self.pause_text if self.paused else
                    self.restart_text if self.death.prompt_visible else
                    self.ui_font.text(message, self.hud_text_color) if message else None)
        demo_paused = self.paused and getattr(self, "demo", None) is not None
        if (hud_text is not None and not demo_paused
                and self.dev_menu is None and self.game_menu is None):
            ink = (self.pause_text if notice is not None else hud_text).getbbox()
            pause_y = ROOM_HEIGHT + (VIEWPORT_HEIGHT - ROOM_HEIGHT - (ink[3] - ink[1])) // 2 - ink[1]
            viewport.paste(hud_text, ((VIEWPORT_WIDTH - hud_text.width) // 2,
                                      pause_y), hud_text)
        if (self.level_complete and self.game.exit is None
                and notice is None
                and self.dev_menu is None and self.game_menu is None):
            text = self.ui_font.text(f"Level {self.game.level.number} Complete")
            viewport.paste(text, ((VIEWPORT_WIDTH - text.width) // 2, ROOM_HEIGHT), text)
            self.screenshot_viewport.paste(text, ((VIEWPORT_WIDTH - text.width) // 2, ROOM_HEIGHT), text)
        if demo_paused and self.dev_menu is None and self.game_menu is None:
            viewport = self.draw_cutscene_pause(viewport)
        if getattr(self, "copy_challenge", None) is not None:
            viewport = self.copy_challenge.draw(viewport, self.ui_font)
            self.screenshot_viewport = viewport.copy()
        if self.dev_menu is not None:
            viewport = self.dev_menu.draw(viewport, self.ui_font)
        if self.game_menu is not None:
            self.refresh_game_menu()
            viewport = self.game_menu.draw(viewport, self.ui_font)
        viewport = self.draw_screenshot_notice(viewport)
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
