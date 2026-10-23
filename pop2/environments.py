"""Environment-specific frame work, one class per native environment kind.

The original selects these through its environment hook table (FrameAdv
2:7124 -> a5-0x46f8[environment]): desert 18:01e0, caverns 8:3b92 (level
five's BridgeCheckBreak), rooftops 23:0874. ScenePrototype runs them in its
frame phases (pop2.frame_phases); the classes hold no state of their own.
"""

import time

from pop2.bridge import BRIDGE_ROOM, CREAK_SOUND, bridge_checked, bridge_gate_open, on_bridge
from pop2.combat import guard_frame_index
from pop2.control_mapping import IDLE_SEQUENCE

DESERT_FAR_SHORE_SOUND_X = 0x30B


class Environment:
    """No environment-specific work (the rooftops)."""

    def __init__(self, scene):
        self.scene = scene

    def frame_hook(self):
        """The 'environment' frame phase."""

    def level_events(self):
        """Level mechanisms after the environment hook; True when the level changed."""
        return False


class Desert(Environment):
    """Level two (environment kind 1)."""

    def level_events(self):
        scene = self.scene
        desert = getattr(scene.game, "desert", None)
        if desert is not None and scene.terrain_motion is not None:
            cues = desert.advance(scene.room_id, scene.sequence_state, scene.frames[scene.action],
                                  scene.combat is None or scene.combat.player.alive,
                                  audio=scene.audio)
            for cue in cues:
                if cue in (46, 47, 49, 50) and scene.audio is not None:
                    if cue == 50:
                        if scene.audio.music_enabled:
                            scene.audio.add_song(cue, ambient=True)
                    else:
                        scene.audio.add_song(cue)
                else:
                    scene.sequence_state.sound_events.append(cue)
            entering_cavern = scene.room_id == 0 and desert.exit_open and scene.player_x < 0
            if (entering_cavern and getattr(scene, "copy_protection_enabled", True)
                    and not getattr(scene, "copy_verified", False)):
                from pop2.copy_protection import CopyProtection

                scene.copy_challenge = CopyProtection(scene.resources.prince)
                scene.last_copy_at = None
                scene.update_cursor_visibility()
                scene.clear_keys(None)
                scene.pause_resume_keys.update(scene.window_keys_down)
            if entering_cavern and getattr(scene, "copy_challenge", None) is None:
                max_life = scene.combat.player.max_life
                scene.load_level(3)
                scene.combat.player.life = scene.combat.player.max_life = max_life
                return True
            if scene.room_id == 2 and scene.player_x >= DESERT_FAR_SHORE_SOUND_X:
                scene.sequence_state.current_x = scene.sequence_state.target_x = (
                    DESERT_FAR_SHORE_SOUND_X
                )
                scene.player_x = DESERT_FAR_SHORE_SOUND_X
                scene.clear_keys(None)
                scene.start_sequence(IDLE_SEQUENCE)
        return False


class Caverns(Environment):
    """Levels three to five (kind 3); the ruins share their mechanisms."""

    def frame_hook(self):
        scene = self.scene
        # The environment frame hook (2:7124 -> a5-0x46f8[environment]) runs
        # after the opponents and the strike checks; the caverns' hook 8:3b92
        # is level five's BridgeCheckBreak.
        if scene.game.caverns is None or getattr(scene, 'level_map', None) is None:
            return
        self.advance_bridge()
        if bridge_checked(scene.game.level.number, scene.room_id):
            room = scene.level_renderer.enter_room(scene.room_id, scene.game.caverns)
            scene.background, scene.foreground = room.background, room.foreground


    def bridge_column(self, actor):
        scene = self.scene
        # The stored cell (+0xc/+0xe) used by 8:04e6, or None off the bridge.
        motion = actor.terrain_motion
        if motion is None:
            return None
        column = scene.combat._supporting_column(actor)
        return column if on_bridge(scene.level_map, motion.room, column, motion.row) else None


    def advance_bridge(self):
        scene = self.scene
        bridge = scene.game.caverns.bridge
        bridge.advance_planks()
        entered = scene.room_id != getattr(scene, 'bridge_last_room', None)
        scene.bridge_last_room = scene.room_id
        if entered and scene.game.level.number == 5 and scene.room_id == 9:
            # Room 10's CUST enter hook MarkBrgFloorsForChars (8:050e-0532,
            # table a5-0x4c2e kind 33) clears the break counter and, once the
            # bridge has started breaking, the tension.
            bridge.counter = 0
            if bridge.state:
                bridge.set_tension(bridge.tension_level, -bridge.tension)
        if not bridge_checked(scene.game.level.number, scene.room_id) or scene.combat is None:
            return
        state = scene.sequence_state
        prince = self.bridge_column(scene.combat.player)
        motion = scene.terrain_motion
        if (prince is None and motion is not None and motion.room == 6
                and not scene.combat.player.sword_lost
                and scene.combat._supporting_column(scene.combat.player) <= 5
                and bridge_gate_open(scene.level_map)):
            # 8:020a-0236: off the bridge in room 7, at column <= 5, a Prince
            # who still has his sword shuts room 7's open gate
            # (TriggerGateWithRevPlate(7, 13)).
            gate = scene.level_map.tile(6, 3, 1)
            scene.game.caverns.plates.trigger_gate((6, 13), gate.foreground, 34)
        # 8:01f6-0206: standing (frame 15) or frame 185 does not count.
        if state.action in (15, 185):
            prince = None
        # 8:0252-02a6: LoadShad(0) when the current room holds opponents.
        opponent = next((guard for guard in scene.combat.active_guards()
                         if guard.bank_slot == 0), None)
        opponent = self.bridge_column(opponent) if opponent is not None else None
        audio = getattr(scene, "audio", None)
        playing = audio is not None and audio.sound_playing(CREAK_SOUND)
        state.sound_events.extend(bridge.creak(prince, opponent, playing))
        if scene.room_id == BRIDGE_ROOM:
            bridge.advance_wobble()
        else:
            bridge.wobble.clear()
        sounds, push = bridge.check_break(prince, opponent, state.source_sequence_id)
        state.sound_events.extend(sounds)
        motion = scene.terrain_motion
        if push and motion is not None and state.facing:
            # 8:0134-0150: LoadKid; a Prince in column <= 4 facing right moves
            # AddCharX(17).
            if scene.combat._supporting_column(scene.combat.player) <= 4:
                state.target_x += 17
                state.current_x = scene.player_x = state.target_x

    def level_events(self):
        scene = self.scene
        if scene.game.caverns is None:
            return
        from pop2.caverns import cavern_flask_instances

        potions = scene.game.caverns.potions
        potions.consume_events(scene.sequence_state, scene.combat.player)
        potions.advance_float()
        potions.advance_flip(scene.combat.player.alive)
        scene.sync_flipped_controls()
        scene.sequence_state.floating = potions.floating
        if potions.fatal:
            potions.fatal = False
            motion = scene.terrain_motion
            scene.clear_keys(None)
            scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
            if motion is not None:
                motion.dead, motion.falling = True, False
            scene.sequence_state.horizontal_velocity = scene.sequence_state.vertical_velocity = 0
            scene.physics.select(scene.sequence_runtime, 71)
            scene.death.begin(3)
            scene.status.set("Defeated")
        potions.advance((tile.room, tile.row * 10 + tile.column)
            for _command, tile in cavern_flask_instances(
                scene.level_renderer.cavern_program, scene.room_id, scene.level_map))
        lava = scene.game.caverns.lava
        lava.enter_room(scene.room_id, scene.level_renderer.cavern_program.get(
            'lava', {}).get('rooms', {}).get(str(scene.room_id), ()))
        scene.sequence_state.sound_events.extend(lava.advance())
        pool = (lava.contact(scene.level_map, scene.terrain_motion, scene.sequence_state,
                             scene.frames[scene.action], landed=scene.terrain_motion.lava_landing)
                if scene.terrain_motion is not None else None)
        if scene.terrain_motion is not None:
            scene.terrain_motion.lava_landing = False
        if pool is not None and not getattr(scene, 'god_mode', False):
            state, motion = scene.sequence_state, scene.terrain_motion
            sequence, cue = pool.begin_death(state.animation_state, state.facing)
            scene.clear_keys(None)
            scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
            motion.dead, motion.falling = True, False
            state.horizontal_velocity = state.vertical_velocity = 0
            scene.combat.player.life = 0
            scene.death.begin(5)
            scene.physics.select(scene.sequence_runtime, sequence)
            scene.death.music_method = state.death_song_method
            state.sound_events.append(cue)
            scene.action, scene.player_x = state.action, state.target_x
            scene.status.set('Defeated')
        loose = scene.game.caverns.loose
        for guard in scene.combat.active_guards():
            if guard.skeleton is None or not guard.alive or guard.terrain_motion is None:
                continue
            state, motion = guard.state, guard.terrain_motion
            pool = lava.contact(scene.level_map, motion, state,
                scene.guard_art.frames[guard_frame_index(state.action)], landed=motion.lava_landing)
            motion.lava_landing = False
            if pool is not None:
                sequence, cue = pool.begin_death(state.animation_state, state.facing, actor_type=4)
                guard.life, guard.targetable = 0, False
                guard.skeleton.phase = 'lava'
                motion.dead, motion.falling = True, False
                state.horizontal_velocity = state.vertical_velocity = 0
                scene.physics.select(guard.runtime, sequence)
                state.sound_events.append(cue)
        state, motion = scene.sequence_state, scene.terrain_motion
        if motion is not None:
            state.sound_events.extend(loose.press(scene.level_map, motion, state, scene.frames[state.action]))
            state.sound_events.extend(scene.game.caverns.plates.press(
                scene.level_map, motion, state, scene.frames[state.action], scene.combat.player.alive))
            for guard in scene.combat.active_guards():
                if guard.terrain_motion is not None:
                    guard.state.sound_events.extend(loose.press(scene.level_map, guard.terrain_motion,
                        guard.state, scene.guard_art.frames[guard_frame_index(guard.state.action)]))
                    guard.state.sound_events.extend(scene.game.caverns.plates.press(
                        scene.level_map, guard.terrain_motion, guard.state,
                        scene.guard_art.frames[guard_frame_index(guard.state.action)], guard.alive))
            shakes = [event for event in state.sequence_events if event[0] in (-12, -13)]
            if shakes:
                # CheckAlert 2:6c1c consumes one scalar request; a later
                # SEQS shake operation replaces an earlier one.
                row = motion.row - int(shakes[-1][0] == -12)
                state.sound_events.extend(loose.shake_row(scene.level_map, motion.room, row,
                                                         state, motion, scene.frames[state.action]))
                for event in shakes:
                    state.sequence_events.remove(event)
        for room, row in loose.shake_events:
            scene.combat.shake_bones(room, row)
        loose.shake_events.clear()
        scene.check_cavern_darts()
        scene.check_cavern_spikes()
        scene.check_cavern_scythes()
        scene.game.caverns.crush.advance(scene.level_map, motion, state,
                                       scene.frames[state.action], scene.game.caverns.plates,
                                       now=time.perf_counter())
        scene.sequence_state.sound_events.extend(scene.game.caverns.advance())
        scene.game.caverns.advance_torches(
            scene.level_renderer.cavern_program.get('torches', {}).get(str(scene.room_id), ()))
        room = scene.level_renderer.enter_room(scene.room_id, scene.game.caverns)
        scene.background, scene.foreground = room.background, room.foreground
        return False


class Ruins(Caverns):
    """Levels six and seven (kind 4)."""


def environment_for(scene):
    """The environment of the scene's current level.

    Chosen by the level's environment state, which the game creates for
    kinds 3 and 4 (caverns) and level two (desert).
    """
    game = scene.game
    if getattr(game, 'caverns', None) is not None:
        return (Ruins if game.level.kind == 4 else Caverns)(scene)
    if getattr(game, 'desert', None) is not None:
        return Desert(scene)
    return Environment(scene)
