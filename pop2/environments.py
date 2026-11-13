"""Environment-specific frame work, one class per native environment kind.

The original selects these through its environment hook table (FrameAdv
2:7124 -> a5-0x46f8[environment]): desert 18:01e0, caverns 8:3b92 (level
five's BridgeCheckBreak), rooftops 23:0874. ScenePrototype runs them in its
frame phases (pop2.frame_phases); the classes hold no state of their own.

Hooks, in the order ScenePrototype calls them during a frame: frame_start,
controls, room_crossed/entered_room/player_died (terrain), frame_hook
(environment phase), harbor_phase, level_events, queue_songs/ambient_audio,
then the drawing hooks in render order (scenery_layer, draw_sag,
drawn_player, after_actors, display_life). While the exit song plays:
exit_scenery, then finish_exit. A new environment (the temple, 10:27ba)
subclasses Environment and is selected in environment_for.
"""

import time
from types import SimpleNamespace

from pop2.bridge import BRIDGE_ROOM, CREAK_SOUND, bridge_checked, bridge_gate_open, bridge_sag, on_bridge
from pop2.mac_input import DirectionalInput
from pop2.carpet import (
    CARPET_ROOM, CARPET_TILE, CLOSED_SONG, CRASH_SEQUENCE, OPEN_SONG, RIDE_FRAME, ROOM_SONG, SIT_SEQUENCE,
    carpet_room,
)
from pop2.control_mapping import IDLE_SEQUENCE
from pop2.coordinates import native_x, scene_x
from pop2.crevices import CREVICE_TILE
from pop2.harbor import SHIP_CLIMB_SEQUENCE
from pop2.loose_floors import crush_sequence, floor_hits_actor, floor_hits_body
from pop2.opponent_generation import character_column
from pop2.render_opening import TILE_HEIGHT, TILE_WIDTH
from pop2.terrain import floor_contact_x, floor_y
from pop2.trapdoors import LOOP_CUE, OPEN_CUE

DESERT_FAR_SHORE_SOUND_X = 0x30B


def guard_frame_index(action):
    # pop2.combat reads the imported enemy profiles; import it when used so
    # that this module stays importable without the game files.
    from pop2.combat import guard_frame_index as index

    return index(action)


class Environment:
    """No environment-specific work."""

    # GetEndSong 5:4e0c: 32 for rooftop and cavern exits, 124 for the ruins.
    end_song = 32

    def __init__(self, scene):
        self.scene = scene

    def frame_start(self):
        """Before the Prince's controls: traps and floors that animate on their own."""

    def controls(self):
        """With the Prince's controls (GenCtrl)."""

    def room_crossed(self, old_room, room):
        """The Prince crossed into another room; True when he was moved instead."""
        return False

    def entered_room(self):
        """After the scene entered the Prince's new room."""

    def player_died(self):
        """The terrain killed the Prince, before his life is cleared."""

    def frame_hook(self):
        """The 'environment' frame phase."""


    def harbor_phase(self):
        """The 'harbor' frame phase: level one's ship and water."""

    def level_events(self):
        """Level mechanisms after the environment hook; True when the level changed."""
        return False

    def exit_scenery(self):
        """While the exit song plays: the main loop still runs FrameAdv."""

    def exit_song(self):
        """The song a completed level waits for, or None."""
        return self.end_song

    def finish_exit(self):
        """After the exit song: level one's voyage scene."""
        self.scene.start_ending()

    def queue_songs(self, audio):
        """Songs the level mechanisms requested this frame."""

    def gate_audio(self):
        """Attributed gate cues, or None for unmodified native arbitration."""
        return None

    def ambient_audio(self, audio, motion):
        """Ambient music and environment sounds, after the actors' sounds."""

    def room_ambient(self, audio, motion, fighting, contact, *, special=None, special_when_idle=False):
        """The rooftops' and caverns' room ambient (5:5398 SpecialMusic, 5:5494)."""
        scene = self.scene
        # 5:5494-54c8: no new ambient while the first bank skeleton of an
        # exit-guarded room is rising (88) or running (102/216).
        from pop2.skeleton import exit_guarded

        first = next(iter(scene.combat.active_guards()), None)
        chasing = (first is not None and first.skeleton is not None
                   and exit_guarded(scene.combat, first)
                   and first.state.source_sequence_id in (88, 102, 216))
        if not chasing:
            # SpecialMusic 5:5398-53bc: BrgFight for fights in level five's
            # bridge rooms 7, 10 and 12.
            if special is None:
                special = 119 if bridge_checked(scene.game.level.number, scene.room_id) else None
            options = {'special_when_idle': True} if special_when_idle else {}
            audio.ambient(scene.room_id, motion.row, max(0, min(9, int(contact // 51))),
                          fighting, scene.combat.player.alive, special=special, **options)

    # Drawing, in ScenePrototype.render order.

    def scenery_layer(self, frame, motion):
        """Scenery objects drawn before the room's foreground."""
        return frame

    def draw_sag(self, actor):
        """Pixels an actor is drawn lower than its floor."""
        return 0

    def drawn_player(self, state):
        """(state, height) the Prince is drawn with; height None is his sprite's."""
        return state, None

    def after_actors(self, frame, player_bounds):
        """Drawn over the actors, before the front scenery."""
        return frame

    def extra_actors(self, size):
        """(state, record, bounds, row, layer) actors drawn among the others."""
        return ()

    def display_life(self, life):
        """The life the meter shows."""
        return life


class Final(Environment):
    """The level-14 room-2 spell and its entry into the mental rooms."""

    def frame_start(self):
        scene = self.scene
        # FinlWatchOpps reads the saved Prince record (a5-0x50d2), which
        # trails the current actor through the native frame. Keep that
        # pre-control snapshot when a room crossing happens in this tick.
        scene.final_saved_prince = (scene.room_id, scene.player_bounds()[2],
                                    scene.sequence_state.animation_state)

    def frame_hook(self):
        scene = self.scene
        room, right_edge, animation = getattr(scene, 'final_saved_prince', (-1, 0, 4))
        if (room != 1 or right_edge > 486 or animation == 4
                or not scene.combat.player.alive):
            return
        scene.start_story_scene('final_spell.json', self.finish_spell, "Jaffar's spell")

    def finish_spell(self):
        scene = self.scene
        # CODE 9:071a-075e calls PlayNIS(5), then 9:05d2 selects SEQS 55
        # in native room 4, row 1, column 5, native X 484 (port X 277).
        life, capacity = scene.combat.player.life, scene.combat.player.max_life
        mode = scene.sequence_state.sequence_mode
        scene.jump_to_room(3, row=1, x=scene_x(484), facing=0,
                           reset_guards=False, redraw=False)
        scene.combat.player.life, scene.combat.player.max_life = life, capacity
        scene.sequence_state.sequence_mode = mode
        scene.start_sequence(55)
        frame = scene.sequence_runtime.next_frame()
        scene.action, scene.player_x = frame.action, frame.target_x


class Rooftops(Environment):
    """Level one (environment kind 5): the rooftops and the harbor."""

    def exit_scenery(self):
        self.scene.harbor.advance()

    def entered_room(self):
        scene = self.scene
        scene.harbor.enter_room(scene.room_id, scene.action)

    def ambient_audio(self, audio, motion):
        scene = self.scene
        if scene.level_complete:
            return
        fighting = not scene.peaceful and scene.combat.opponent_to_fight()
        contact = floor_contact_x(scene.sequence_state.target_x,
                                 scene.sequence_state.facing, scene.frames[scene.action])
        self.room_ambient(audio, motion, fighting, contact)

    def harbor_phase(self):
        scene = self.scene
        motion = getattr(scene, "terrain_motion", None)
        if motion is None or scene.harbor is None:
            return
        state = scene.sequence_state
        if (state.sequence_id == SHIP_CLIMB_SEQUENCE
                or scene.harbor.hanging_from_ship(motion.room, state)):
            state.target_x -= 2
            state.current_x = state.target_x
        scene.harbor.advance()
        if (not motion.dead and not getattr(scene, 'god_mode', False)
                and scene.harbor.right_exit_is_fatal(motion.room, state)):
            scene.clear_keys(None)
            motion.dead, motion.falling = True, False
            scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
            state.horizontal_velocity = state.vertical_velocity = 0
            state.sound_events.append(34)
            scene.physics.select(scene.sequence_runtime, 71)
            scene.combat.player.life = 0
            scene.death.begin(14)
            scene.status.set("Defeated")
        bounds = scene.player_bounds()
        if not motion.dead and not getattr(scene, 'god_mode', False) and scene.harbor.watch_water(
                0, motion.room, motion.row, state, bounds[2] - bounds[0] + 1):
            scene.clear_keys(None)
            scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
            motion.dead = True
            motion.falling = False
            state.horizontal_velocity = state.vertical_velocity = 0
            state.animation_state, state.action = 1, 185
            state.selected_sequence_id = 22
            state.sequence_id, state.cursor = 22, len(scene.sequences[22]) - 1
            scene.combat.player.life = 0
            scene.death.begin(15)
            scene.status.set("Defeated")
        if not scene.peaceful:
            for guard in scene.combat.active_guards():
                if guard.terrain_motion is not None and not guard.terrain_motion.dead:
                    bounds = scene.guard_art.bounds(guard.state, floor_y(guard.row))
                    if scene.harbor.watch_water(id(guard), guard.room, guard.row, guard.state,
                                               bounds[2] - bounds[0] + 1):
                        guard.life = 0
                        guard.targetable = False
                        guard.terrain_motion.dead = True
                        guard.state.horizontal_velocity = guard.state.vertical_velocity = 0
                        guard.state.action, guard.state.animation_state = 185, 1
                        guard.state.selected_sequence_id = 22
                        guard.state.sequence_id, guard.state.cursor = 22, len(scene.sequences[22]) - 1
        scene.player_x, scene.action = state.target_x, state.action


class Desert(Environment):
    """Level two (environment kind 1)."""

    def ambient_audio(self, audio, motion):
        scene = self.scene
        # DesertFunc 18:01ee checks PrinceSndOn(51) before queuing another wave.
        # Cave cue 50 and puzzle cues 46/49 use AddSong instead.
        if scene.room_id == 0:
            # 18:0212-0238 retains waves until desert song 50 starts.
            if audio.song_playing(50):
                audio.stop_sound(51)
            allow_song = not audio.song_playing(50)
        else:
            allow_song = scene.game.desert.music_started
            if not audio.sound_playing(51):
                audio.add_sound(51)
            # DesertFunc 18:0334-0392 checks native room 3, X >= 0x30B,
            # then gates cue 56 with Rnd(20) while it is not playing.
            if (scene.room_id == 2 and scene.player_x >= DESERT_FAR_SHORE_SOUND_X
                    and not audio.sound_playing(56)):
                if audio.rng.randrange(21) == 0:
                    audio.add_sound(56)
        # DesertFunc 18:023c-0278 retries only with no active stone,
        # no playing song, a live actor outside mode 7 and inclusive Rnd(30)==0.
        if (allow_song and audio.music_enabled and scene.combat.player.alive
                and scene.sequence_state.animation_state != 7 and not audio.music_busy
                and audio.rng.randrange(31) == 0
                and not any(stone.direction for stone in scene.game.desert.stones)):
            scene.game.desert.music_started = True
            audio.add_song(50, ambient=True)

    def after_actors(self, frame, player_bounds):
        scene = self.scene
        if (scene.sequence_state.level_kind == 1 and scene.sequence_state.source_sequence_id == 27
                and player_bounds[1] < 227):
            art = scene.level_renderer.desert_rooms[scene.room_id]
            frame = art.draw_sand(frame, scene.combat.world_frame, player_bounds)
        return frame

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
            # DesertFunc 18:02f8-0332: in native room 1 the level ends once
            # the Kid's X is left of the origin, whatever the exit's phase;
            # only the gate collision (4:5b0e, open from phase 19) holds him.
            entering_cavern = scene.room_id == 0 and scene.player_x < 0
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
        if potions.jinnee_prompt:
            from pop2.jinnee import PRINCE_SEQUENCE

            potions.jinnee_prompt = False
            scene.physics.select(scene.sequence_runtime, PRINCE_SEQUENCE)
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
            # GetLavaInfoHnd 8:3546-3548 marks the Kid too (IsCharNonViewable).
            state.sequence_mode = 5
            scene.combat.player.life = 0
            scene.death.begin(5)
            scene.physics.select(scene.sequence_runtime, sequence)
            scene.death.music_method = state.death_song_method
            state.sound_events.append(cue)
            scene.action, scene.player_x = state.action, state.target_x
            scene.status.set('Defeated')
        loose = scene.game.caverns.loose
        for guard in scene.combat.active_guards():
            # CheckLavaBoil 8:3480 gates repeated entry on special5, not HP:
            # a zero-HP skeleton heap can still be consumed by the pool.
            if (guard.skeleton is None or guard.state.sequence_mode == 5
                    or guard.terrain_motion is None):
                continue
            state, motion = guard.state, guard.terrain_motion
            pool = lava.contact(scene.level_map, motion, state,
                scene.guard_art.frames[guard_frame_index(state.action)], landed=motion.lava_landing)
            motion.lava_landing = False
            if pool is not None:
                sequence, cue = pool.begin_death(state.animation_state, state.facing, actor_type=4)
                guard.life, guard.targetable = 0, False
                guard.skeleton.phase = 'lava'
                # GetLavaInfoHnd 8:3546-3548 marks the actor for removal;
                # UpdateOppInfo 6:30c4-30d4 must not save a revivable heap.
                state.sequence_mode = 5
                motion.dead, motion.falling = True, False
                state.horizontal_velocity = state.vertical_velocity = 0
                scene.physics.select(guard.runtime, sequence)
                state.sound_events.append(cue)
        state, motion = scene.sequence_state, scene.terrain_motion
        if motion is not None:
            from pop2.combat import _native_alive

            state.sound_events.extend(loose.press(scene.level_map, motion, state, scene.frames[state.action]))
            state.sound_events.extend(scene.game.caverns.trapdoors.check(
                scene.level_map, motion, state, scene.frames[state.action]))
            state.sound_events.extend(scene.game.caverns.plates.press(
                scene.level_map, motion, state, scene.frames[state.action], scene.combat.player.alive,
                sword_type=scene.game.sword_type, native_alive=_native_alive(scene.combat.player),
                displayed_room=scene.room_id))
            for guard in scene.combat.active_guards():
                if guard.terrain_motion is not None:
                    guard.state.sound_events.extend(loose.press(scene.level_map, guard.terrain_motion,
                        guard.state, scene.guard_art.frames[guard_frame_index(guard.state.action)]))
                    guard.state.sound_events.extend(scene.game.caverns.trapdoors.check(
                        scene.level_map, guard.terrain_motion, guard.state,
                        scene.guard_art.frames[guard_frame_index(guard.state.action)]))
                    guard.state.sound_events.extend(scene.game.caverns.plates.press(
                        scene.level_map, guard.terrain_motion, guard.state,
                        scene.guard_art.frames[guard_frame_index(guard.state.action)], guard.alive,
                        sword_type=scene.game.sword_type, native_alive=_native_alive(guard),
                        displayed_room=scene.room_id))
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
        self.check_darts()
        self.check_spikes()
        self.check_scythes()
        scene.game.caverns.crush.advance(scene.level_map, motion, state,
                                       scene.frames[state.action], scene.game.caverns.plates,
                                       now=time.perf_counter())
        scene.sequence_state.sound_events.extend(scene.game.caverns.advance())
        scene.game.caverns.advance_torches(
            scene.level_renderer.cavern_program.get('torches', {}).get(str(scene.room_id), ()))
        room = scene.level_renderer.enter_room(scene.room_id, scene.game.caverns)
        scene.background, scene.foreground = room.background, room.foreground
        self.advance_ambience()
        return False

    def advance_ambience(self):
        scene = self.scene
        if getattr(scene, 'cave_ambience_enabled', False):
            scene.level_renderer.advance_ambience(scene.room_id, scene.level_map, self.prince_footing(),
                                                  self.thuds())

    def prince_footing(self):
        """Where the Prince's feet are, for the dust they raise. Only read."""
        from pop2.cavern_ambience import Footing

        scene = self.scene
        state, motion = scene.sequence_state, scene.terrain_motion
        if motion is None:
            return None
        record = scene.frames[state.action]
        return Footing(state.target_x, floor_contact_x(state.target_x, state.facing, record), floor_y(motion.row),
                       bool(record.aux & 0x40), motion.falling, state.vertical_velocity, state.action)

    def thuds(self):
        """What came down in this room this tick, for the dust. The tiles are taken, as
        the exit's ticks do not move them on."""
        from pop2.cavern_ambience import door_coming_down, tile_landing

        scene = self.scene
        caverns = scene.game.caverns
        thuds = [door_coming_down(scene.level_map.tile(room, cell % 10, cell // 10).kind, cell, slammed)
                 for (room, cell), slammed in caverns.plates.shut if room == scene.room_id]
        thuds.extend(tile_landing(cell) for room, cell in caverns.loose.landed if room == scene.room_id)
        caverns.loose.landed.clear()
        thuds.extend(self.crush_slam())
        return thuds

    def crush_slam(self):
        """A gate coming down on the Prince stops on him, so it never says it shut: its
        slam is the crush's, drawn at SLAM_AT_MS. Yields its dust once, the tick it lands."""
        from pop2.cavern_ambience import GATE, door_coming_down
        from pop2.gate_crush import SLAM_AT_MS

        scene = self.scene
        crush = scene.game.caverns.crush
        # The environment is made afresh each time, so the scene keeps what was seen.
        seen = getattr(scene, 'cave_crush_seen', None)
        scene.cave_crush_seen = None if crush.key is None else (crush.key, crush.elapsed_ms)
        if (crush.key is not None and seen is not None and seen[0] == crush.key and crush.room == scene.room_id
                and seen[1] < SLAM_AT_MS <= crush.elapsed_ms):
            room, cell = crush.key
            if room == scene.room_id:
                yield door_coming_down(GATE, cell, True)

    def frame_start(self):
        scene = self.scene
        scene.slab_crush_poses = {}
        caverns = scene.game.caverns
        if caverns is None:
            return
        for actor in (scene.combat.player, *scene.combat.active_guards()):
            actor.state.hit_flash = False
        scene.sequence_state.sound_events.extend(caverns.spikes.advance(scene.level_map, scene.room_id))
        scene.sequence_state.sound_events.extend(caverns.plates.darts.advance(
            scene.level_map, scene.room_id, scene.player_collision_bounds(), scene.sequence_state))
        # FrameAdv 2:622c-6230 moves existing debris before AnimTrobs.
        cues, blocks = caverns.loose.advance_falling(scene.level_map, scene.sequence_state,
                                                    scene.terrain_motion, scene.frames[scene.action])
        scene.sequence_state.sound_events.extend(cues)
        for room, row in caverns.loose.shake_events:
            scene.combat.shake_bones(room, row)
        caverns.loose.shake_events.clear()
        ruins = getattr(scene.combat, 'ruins', None)
        if ruins is not None:
            ruins.crush_offscreen(scene.combat, blocks)
        else:
            scene.combat.crush_offscreen(blocks)
        actors = (scene.combat.player, *scene.combat.active_guards(),
                  *(scene.combat.visible_ruins() if ruins is not None else ()))
        for block in blocks:
            for actor in actors:
                state, motion = actor.state, actor.terrain_motion
                special = getattr(actor, 'ruins', None) is not None
                if special:
                    # Ruins actors keep their physical room/row in Fighter;
                    # their controller owns motion, not RooftopPhysics.
                    motion = SimpleNamespace(room=actor.room, row=actor.row)
                record = (scene.frames[state.action] if actor is scene.combat.player else
                          ruins.record(actor, scene.combat) if special else
                          scene.guard_art.frames[guard_frame_index(state.action)])
                damage = 1 if state.actor_type == 0 else 100
                sequence = crush_sequence(state, actor.life <= damage)
                body_hit = False
                if (scene.game.level.kind == 2 and state.actor_type == 2
                        and actor is not scene.combat.player and motion is not None):
                    # User-approved temple exception: a slab visibly hitting
                    # a guard kills him even during the native mode-5 advance
                    # exemption or a supporting-foot change (room14 -> 13).
                    body_hit = floor_hits_body(block, motion,
                        scene.guard_art.bounds(state, floor_y(motion.row)), actor.alive)
                    if body_hit:
                        sequence = 22
                if (motion is None or not (body_hit or floor_hits_actor(block, motion, state, record, actor.alive))
                        or actor is scene.combat.player and getattr(scene, 'god_mode', False)
                        or sequence is None):
                    continue
                # Crushed 6:28f0: one life for the Prince, fatal for an
                # ordinary guard; survivors use SEQS:52, not sword recoil.
                actor.life = max(0, actor.life - damage)
                if special:
                    # Crushed6:2934/2950-2980: SetCharFloor, then146 for
                    # heads or169 for serpents. This is not sword-hit death.
                    if state.actor_type in (7, 8) and sequence == 146:
                        scene.slab_crush_poses[id(actor)] = (actor, state.action)
                    ruins.set_floor(actor)
                    ruins.jump(actor, sequence)
                    if ruins.banked is actor:
                        ruins.banked = None
                    continue
                state.current_y = 0
                motion.falling = False
                actor.recovering = actor.alive
                if actor.skeleton is not None:
                    actor.skeleton.collapse(actor, encounter=scene.combat)
                    actor.runtime.next_frame()
                    continue
                scene.physics.select(actor.runtime, sequence)
                if actor.alive:
                    state.sound_events.append(300)
                else:
                    motion.dead = True
                    if actor is scene.combat.player:
                        scene.death.begin(3)
                if actor is scene.combat.player:
                    # The crush replaces a climb/descent before its normal
                    # completion can retire the host ledge controller. Leaving
                    # it active swallows movement even after recovery reaches
                    # idle (and need not involve a subsequent wall bump).
                    scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
                    scene.ledge_climb_requested = False
                    scene.ledge_grip_delay = 0
                    scene.run_active = scene.run_stop_requested = scene.run_cycle_boundary_pending = False
                    scene.action, scene.player_x = state.action, state.target_x
        for room, cell, kind in caverns.loose.plate_events:
            scene.sequence_state.sound_events.extend(caverns.plates.impact(
                scene.level_map, room, cell, kind, sword_type=scene.game.sword_type))
        caverns.loose.plate_events.clear()
        caverns.loose.advance_tiles(scene.level_map)
        scene.sequence_state.sound_events.extend(caverns.scythes.advance(scene.level_map))
        scene.sequence_state.sound_events.extend(caverns.plates.advance(
            scene.level_map, scene.sequence_state, scene.terrain_motion, scene.frames[scene.action]))
        self.advance_relief(caverns)
        stopped = set(caverns.plates.stopped_sounds)
        if stopped:
            scene.sequence_state.sound_events[:] = [
                cue for cue in scene.sequence_state.sound_events if cue not in stopped]
        if getattr(scene, "audio", None) is not None:
            for cue in caverns.plates.stopped_sounds:
                if cue != 17 or not scene.audio.split_mechanisms:
                    scene.audio.stop_sound(cue)
        caverns.plates.stopped_sounds.clear()

    def check_spikes(self):
        scene = self.scene
        spikes = scene.game.caverns.spikes
        for actor in (scene.combat.player, *scene.combat.active_guards()):
            state, motion = actor.state, actor.terrain_motion
            if motion is None:
                continue
            player = actor is scene.combat.player
            record = (scene.frames[state.action] if player else
                      scene.guard_art.frames[guard_frame_index(state.action)])
            bounds = scene.player_bounds() if player else scene.guard_art.bounds(state, floor_y(motion.row))
            spikes.approach(scene.level_map, motion, state, record, bounds, actor.sword_drawn)
            if player and getattr(scene, 'god_mode', False):
                continue
            collision = (scene.player_collision_bounds() if player else
                         scene.guard_art.collision_bounds(state, floor_y(motion.row), actor.sword_drawn))
            width = collision[2] + 1 - collision[0]
            hit = spikes.contact(scene.level_map, motion, state, record, collision,
                                 actor.alive, actor.sword_drawn,
                                 rock_near=lambda tile, facing=state.facing, width=width:
                                 scene.level_map.slide_rock_near_spikes(tile, facing, width))
            if hit is not None:
                self.impale(actor, *hit)

    def impale(self, actor, sequence, x):
        """5:3cee after a spike hit: the actor is pinned at X and dies."""
        scene = self.scene
        state, motion = actor.state, actor.terrain_motion
        player = actor is scene.combat.player
        state.target_x = x
        state.current_x = state.target_x
        state.current_y = state.horizontal_velocity = state.vertical_velocity = 0
        state.facing = 0
        actor.life, actor.recovering = 0, False
        motion.dead, motion.falling = True, False
        if not player:
            sequence = 189 if sequence == 54 else 188
            actor.targetable = False
        scene.physics.select(actor.runtime, sequence)
        state.sound_events.append(281)
        if player:
            scene.clear_keys(None)
            scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
            scene.death.begin(4)
            scene.death.music_method = 4
            scene.action, scene.player_x = state.action, state.target_x
            scene.status.set('Defeated')

    def check_scythes(self):
        scene = self.scene
        # FrameAdv 2:63f4-63fe and 2:664a-664e (ruins, and the temple's case
        # falls through to them): 5:57bc may start a scythe, then
        # CheckScytheHit 5:588a, which the Prince skips while invulnerable
        # (a5-0x4f90).
        if scene.game.level.kind not in (2, 4) or 'scythes' not in scene.level_renderer.cavern_program:
            return  # An import before the scythes' drawing: leave them still.
        from pop2.scythes import CUT_SEQUENCE, CUT_SOUND

        scythes = scene.game.caverns.scythes
        for actor in (scene.combat.player, *scene.combat.active_guards()):
            state, motion = actor.state, actor.terrain_motion
            if motion is None or not actor.alive:
                continue
            player = actor is scene.combat.player
            record = (scene.frames[state.action] if player else
                      scene.guard_art.frames[guard_frame_index(state.action)])
            scythes.trigger(scene.level_map, motion, state, record)
            if player and getattr(scene, 'god_mode', False):
                continue
            bounds = (scene.player_collision_bounds() if player else
                      scene.guard_art.collision_bounds(state, floor_y(motion.row), actor.sword_drawn))
            if not scythes.cut(scene.level_map, motion, state, bounds, record):
                continue
            # 5:5942-597e: SEQS 113 and death method 5 for the Prince, SEQS
            # 190 for a guard; DecLifePts(100) and sound 278.
            actor.life = 0
            motion.dead = True
            actor.recovering = False
            state.sound_events.append(CUT_SOUND)
            scene.physics.select(actor.runtime, CUT_SEQUENCE if player else 190)
            # Both cut sequences begin with -19 (SetCharFloor 4:31fa),
            # immediately executed by AnimChar at 5:596e, even during a jump.
            state.current_y = 0
            motion.falling = False
            if player:
                scene.clear_keys(None)
                scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
                scene.run_active = scene.run_stop_requested = scene.run_cycle_boundary_pending = False
                scene.death.begin(5)
                scene.action, scene.player_x = state.action, state.target_x
                scene.status.set('Defeated')
            else:
                actor.targetable = False

    def check_darts(self):
        scene = self.scene
        from pop2.darts import dart_death

        darts = scene.game.caverns.plates.darts
        for actor in (scene.combat.player, *scene.combat.active_guards()):
            state, motion = actor.state, actor.terrain_motion
            if motion is None:
                continue
            player = actor is scene.combat.player
            bounds = (scene.player_collision_bounds() if player else
                      scene.guard_art.collision_bounds(state, floor_y(motion.row), actor.sword_drawn))
            if not darts.contacts(motion.room, state, bounds) or not actor.alive:
                continue
            if player and getattr(scene, 'god_mode', False):
                continue
            # DoCharHurt stores the maximum pending wound, not one life per
            # projectile when multiple darts contact the actor in one update.
            actor.life -= 1
            state.hit_flash = True
            if actor.alive:
                # A nonfatal dart does not select a hurt pose or stop a run.
                state.sound_events.extend((29 if player else 59, 66))
                continue
            if actor.skeleton is not None:
                actor.skeleton.collapse(actor, encounter=scene.combat)
                actor.runtime.next_frame()
                state.sound_events.append(66)
                continue
            record = (scene.frames[state.action] if player else
                      scene.guard_art.frames[guard_frame_index(state.action)])
            sequence, offset = dart_death(scene.level_map, motion, state, record)
            state.target_x += offset
            state.current_x = state.target_x
            state.current_y = state.vertical_velocity = 0
            if sequence == 18:
                motion.row += 1
                state.current_y -= TILE_HEIGHT
            motion.dead, motion.falling = sequence != 18, sequence == 18
            motion.hit_fall = sequence == 18
            actor.recovering = False
            scene.physics.select(actor.runtime, sequence)
            if sequence == 98:
                state.sound_events.append(12)
            state.sound_events.append(66)
            if player:
                scene.clear_keys(None)
                scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
                scene.death.begin(0)
                scene.death.music_method = 0
                scene.action, scene.player_x = state.action, state.target_x
                scene.status.set('Defeated')
            else:
                actor.row = motion.row
                actor.targetable = False

    def exit_scenery(self):
        scene = self.scene
        # The main loop (2:6100-6134) still runs FrameAdv while the exit song
        # plays, so flasks, lava, torches and moving gates keep animating.
        caverns = scene.game.caverns
        if caverns is None or getattr(scene, "level_map", None) is None:
            return
        from pop2.caverns import cavern_flask_instances

        program = scene.level_renderer.cavern_program
        state = scene.sequence_state
        caverns.potions.advance((tile.room, tile.row * 10 + tile.column)
            for _command, tile in cavern_flask_instances(program, scene.room_id, scene.level_map))
        caverns.lava.enter_room(scene.room_id, program.get('lava', {}).get('rooms', {}).get(str(scene.room_id), ()))
        state.sound_events.extend(caverns.lava.advance())
        state.sound_events.extend(caverns.spikes.advance(scene.level_map, scene.room_id))
        state.sound_events.extend(caverns.plates.advance(scene.level_map))
        state.sound_events.extend(caverns.scythes.advance(scene.level_map))
        caverns.advance_torches(program.get('torches', {}).get(str(scene.room_id), ()))
        room = scene.level_renderer.enter_room(scene.room_id, caverns)
        scene.background, scene.foreground = room.background, room.foreground
        self.advance_ambience()
        if getattr(scene, "audio", None) is not None:
            scene.audio.drain(state, gate_events=self.gate_audio())
        else:
            state.sound_events.clear()

    def finish_exit(self):
        scene = self.scene
        if scene.game.level.number == 3:
            scene.start_discovery()
        elif scene.game.level.number == 4:
            scene.finish_level_four()
        elif scene.game.level.number == 5:
            # CheckPlayNIS(5, 6) shows the carpet scene (NIS 1), then
            # RestartGame loads level six.
            self.finish_via_story(6)
        else:
            scene.start_ending()

    def exit_song(self):
        # 6:0fea-0ff2 adds the end song only at the stairs' frame 224; the
        # carpet (SEQS 128's -16 at frame 295) leaves with FlyinRug playing.
        scene = self.scene
        if (carpet_room(scene.game.level.number, scene.room_id)
                and scene.sequence_state.action == RIDE_FRAME):
            return None
        return self.end_song

    def finish_via_story(self, following):
        from pop2.caverns import scenery_available

        scene = self.scene
        if scenery_available(following):
            scene.finish_level_via_story(scene.game.level.number, following)
        else:
            scene.game.exit = None
            scene.status.set(f'Level {following} needs a reimport of the game files')

    def controls(self):
        self.carpet_controls()

    def carpet_controls(self):
        scene = self.scene
        caverns = scene.game.caverns
        motion, state = scene.terrain_motion, scene.sequence_state
        if (caverns is None or motion is None or not carpet_room(scene.game.level.number, motion.room)
                or motion.falling):
            return False
        carpet = caverns.carpet
        if state.action == 109 and state.source_sequence_id not in (17, 20) and scene.combat.player.alive:
            # GenCtrl 6:09b4-09fe: crouching on the carpet tile, or just right
            # of it, sits down (8:14ae).
            column = scene.combat._supporting_column(scene.combat.player)
            if CARPET_TILE in (scene.level_map.tile(motion.room, column, motion.row).kind,
                               scene.level_map.tile(motion.room, column - 1, motion.row).kind):
                scene.clear_keys(None)
                scene.physics.select(scene.sequence_runtime, SIT_SEQUENCE)
                state.target_x = state.current_x = scene.player_x = carpet.sit_x(state.facing)
                caverns.plates.songs.append(OPEN_SONG if self.cave_bars_open() else CLOSED_SONG)
                return True
        if state.action == RIDE_FRAME:
            carpet.advance()  # DrawObjCarpet 8:11a4 counted the last drawing.
            sound, crash, kill = carpet.sit(floor_y(motion.row) + state.current_y, self.cave_bars_open())
            if sound is not None:
                state.sound_events.append(sound)
            if crash:
                # 8:1456-1474: Y 39, hidden mode 10, SEQS 129.
                state.current_y = 39 - floor_y(motion.row)
                scene.physics.select(scene.sequence_runtime, CRASH_SEQUENCE)
                state.sequence_mode = 10
            if kill and scene.combat.player.alive and not getattr(scene, 'god_mode', False):
                # 8:1486-1498: DecLifePts(100) and death method 9.
                scene.combat.player.life = 0
                scene.death.begin(9)
                scene.status.set("Defeated")
        return False

    def cave_bars_open(self):
        scene = self.scene
        # IsCaveBarsOpen 8:157a: tile (3, 6, 0) phase >= 3.
        return scene.level_map.tile(CARPET_ROOM, 6, 0).foreground & 7 >= 3

    def advance_relief(self, caverns):
        scene = self.scene
        motion = scene.terrain_motion
        for room, cell in caverns.plates.slam_sounds:
            # AddGateSound 5:3828-388e: a slam (sound 20) of level five's room-7
            # gate adds BrgDoor (120), unless it plays or the Prince stands in
            # room 7 left of column 3.
            audio = getattr(scene, "audio", None)
            if (scene.game.level.number == 5 and room == 6
                    and not (audio is not None and audio.song_playing(120))
                    and not (motion is not None and motion.room == 6
                             and scene.combat._supporting_column(scene.combat.player) < 3)):
                caverns.plates.songs.append(120)
        for room, cell in caverns.plates.slams:
            if self.shut_out_opponents(room, cell):
                caverns.phew_countdown = 4
        # FrameAdv 2:640c-6446: when the countdown reaches zero, a living
        # Prince outside modes 3/4 sighs (sound 110) once per level.
        countdown = caverns.phew_countdown
        if countdown < 0:
            return
        state = scene.sequence_state
        if countdown == 0 and scene.combat.player.alive and state.animation_state not in (3, 4):
            state.sound_events.append(110)
            caverns.phew_countdown = -2
        else:
            caverns.phew_countdown -= 1

    def shut_out_opponents(self, room, cell):
        scene = self.scene
        # 5:4766-489c: in level four, a slammed gate in the Prince's room and
        # row, under five columns away, with the living opponents of that row
        # all on its far side.
        motion = scene.terrain_motion
        if (scene.game.level.number != 4 or scene.game.caverns.phew_countdown == -2
                or motion is None or room != motion.room or cell // 10 != motion.row):
            return False
        from pop2.combat import _native_alive

        gate, prince = cell % 10, scene.combat._supporting_column(scene.combat.player)
        if abs(gate - prince) >= 5:
            return False
        result = False
        for guard in scene.combat.active_guards():
            if guard.row != motion.row or guard.room != room or not _native_alive(guard):
                continue
            column = scene.combat._supporting_column(guard)
            if (column <= gate) if gate < prince else (column > gate):
                result = True
            else:
                return False
        return result

    def scenery_layer(self, frame, motion):
        from pop2.caverns import draw_carpet

        scene = self.scene
        state = scene.sequence_state
        return draw_carpet(frame, scene.room_id, scene.game.caverns,
                           (state.target_x, floor_y(motion.row) + state.current_y,
                            state.facing, state.action) if motion.room == scene.room_id else None,
                           level_number=scene.game.level.number)

    def draw_sag(self, actor):
        scene = self.scene
        # 8:063e lowers a character standing on a plank by its sag; the port
        # applies it to drawing only.
        game = getattr(scene, "game", None)
        motion = getattr(actor, "terrain_motion", None)
        if (getattr(game, "caverns", None) is None or motion is None or game.level.number != 5
                or getattr(scene, "level_map", None) is None or motion.falling):
            return 0
        record = (scene.frames[actor.state.action] if actor is scene.combat.player else
                  scene.guard_art.frames[guard_frame_index(actor.state.action)])
        return bridge_sag(scene.level_map, motion.room, scene.combat._supporting_column(actor),
                          motion.row, actor.state.action, record)

    def drawn_player(self, state):
        drawn, height = self.scene.game.caverns.crush.actor(state)
        terminal = getattr(self.scene, 'jump_descent_frame', None)
        if (height is None and terminal is not None
                and state.source_sequence_id == 21 and state.action == 102):
            return terminal, self.scene.player_sprite(terminal.action).height
        return drawn, height

    def display_life(self, life):
        scene = self.scene
        return scene.game.caverns.crush.display_life(scene.sequence_state, life)

    def gate_audio(self):
        events = tuple(self.scene.game.caverns.plates.gate_sounds)
        self.scene.game.caverns.plates.gate_sounds.clear()
        return events

    def queue_songs(self, audio):
        caverns = self.scene.game.caverns
        for cue in (*caverns.plates.songs, *caverns.potions.songs, *caverns.bridge.songs):
            if audio is not None and not audio.song_playing(cue):
                audio.add_song(cue)
        caverns.plates.songs.clear()
        caverns.potions.songs.clear()
        caverns.bridge.songs.clear()

    def ambient_audio(self, audio, motion):
        scene = self.scene
        in_carpet_room = carpet_room(scene.game.level.number, scene.room_id)
        # CUST entry 8:0d50 requests 114 once; leave 8:0d5c -> 14f0 stops it.
        audio.room_song((scene.game.level.number, scene.room_id),
                        ROOM_SONG if in_carpet_room and scene.game.caverns.carpet.counter == 0 else None)
        if scene.level_complete:
            return
        fighting = not scene.peaceful and scene.combat.opponent_to_fight()
        contact = floor_contact_x(scene.sequence_state.target_x,
                                 scene.sequence_state.facing, scene.frames[scene.action])
        for guard in scene.combat.guards:
            skeleton = guard.skeleton
            if (skeleton is not None and skeleton.victory_pending and not fighting
                    and scene.combat.player.alive and 0 < skeleton.timer < 116
                    and not any(audio.sound_playing(cue) for cue in (61, 68, 69))):
                audio.add_song(63)
                skeleton.victory_pending = False
            flame = guard.flame_sword
            if flame is not None and flame.song_pending:
                from pop2.flame_sword import FALL_SONG

                # FlameSwordDecLifePts 4:1cb6: AddSong(238) as it drops.
                audio.add_song(FALL_SONG)
                flame.song_pending = False
            if skeleton is not None and skeleton.rise_song_pending:
                # SkelDoneShaking 4:1b1c-1b30: AddSong(112) unless playing.
                if not audio.song_playing(112):
                    audio.add_song(112)
                skeleton.rise_song_pending = False
        self.room_ambient(audio, motion, fighting, contact)

    def player_died(self):
        scene = self.scene
        if scene.sequence_state.source_sequence_id == 118:
            scene.game.caverns.crush.begin(scene.combat.player.life)


# Level eight's throne room (native room 9) and its vision (6:14ec-152a,
# 4:3dd0-3df6, 7:38ca).
THRONE_ROOM = 8
THRONE_COLLAPSE_SEQUENCE = 237
THRONE_WAKE_SEQUENCE = 231


class Ruins(Caverns):
    """Levels six and seven (kind 4)."""

    end_song = 124

    def ambient_audio(self, audio, motion):
        # PlayAmbient 5:4fd0 with the ruins' bank (LEVL 0x2186 = 4: groups
        # 139-154, 155-170, combat 171-174) and the room table at 0x424a.
        scene = self.scene
        if scene.level_complete:
            return
        fighting = not scene.peaceful and scene.combat.opponent_to_fight()
        contact = floor_contact_x(scene.sequence_state.target_x,
                                 scene.sequence_state.facing, scene.frames[scene.action])
        # SpecialMusic 5:5418-5436: Throne1 replaces ordinary ambience even
        # outside combat, until the Prince has his father's sword.
        throne = (scene.game.level.number == 8 and scene.room_id == THRONE_ROOM
                  and scene.game.sword_type != 1)
        self.room_ambient(audio, motion, fighting, contact,
                          special=180 if throne else None, special_when_idle=throne)

    def entered_room(self):
        super().entered_room()
        scene = self.scene
        ruins = getattr(scene.combat, 'ruins', None) if scene.combat is not None else None
        if ruins is None:
            return
        caverns = scene.game.caverns
        if scene.game.level.number == 8 and scene.room_id == THRONE_ROOM and not caverns.throne_done:
            # The throne room's enter hook 7:3864-38a2 (CUST kind 34).
            if scene.combat._supporting_column(scene.combat.player) < 9:
                ruins.songs.append(180)  # Throne1
            elif not caverns.throne_seen:
                ruins.songs.append(179)  # SeeThron, once (a5-0x4ff6)
                caverns.throne_seen = True
        if scene.game.level.number != 9:
            return
        # The enter hook 7:37d6 of CUST kinds 20/21 (level nine's native
        # rooms 2 and 16), with the Prince's column. Chasm292 belongs to
        # gameplay here; the cutscene uses its separate ToTempl2 theme.
        column = scene.combat._supporting_column(scene.combat.player)
        if scene.room_id == 15 and column >= 9:
            ruins.songs.append(292)
        elif scene.room_id == 1 and column < 5 and not ruins.room_two_song:
            ruins.songs.append(185)
            ruins.room_two_song = True

    def queue_songs(self, audio):
        super().queue_songs(audio)
        ruins = getattr(self.scene.combat, 'ruins', None) if self.scene.combat is not None else None
        if ruins is not None:
            for cue in ruins.songs:
                if audio is not None and not audio.song_playing(cue):
                    audio.add_song(cue)
            ruins.songs.clear()

    def frame_start(self):
        super().frame_start()
        combat = getattr(self.scene, 'combat', None)
        if combat is not None and getattr(combat, 'ruins', None) is not None:
            # FrameAdv step 4 and the drawn objects come before the Prince.
            combat.ruins.before_prince(combat)

    def room_crossed(self, old_room, room):
        if self.scene.game.level.number == 6 and old_room == 26 and room == 27:
            self.leave_cliff()
            return True
        return False

    def leave_cliff(self):
        scene = self.scene
        # CutChar 6:4d7c-4d92 -> S07_373E: leaving level six's cliff (native
        # room 27) to the left, the Prince steps out of native room 3's door
        # at column 4, row 2, facing right with SEQS 5 (FirstFrame 2:5f36).
        # Load the open backdrop before drawing the arrival. The same tick's
        # later level-events phase must not consume its first visible frame.
        scene.game.caverns.start_entry()
        held = (list(scene.held_directions), scene.up_held, scene.down_held,
                scene.shift_held, scene.ctrl_held)
        # This is a continuous room cut, so retain the cliff's music cursor.
        scene.jump_to_room(2, 2, 4 * TILE_WIDTH + 22, 1, reset_guards=False,
                          preserve_checkpoint=True, redraw=False, keep_music=True)
        scene.start_sequence(5)
        # The keys stay held through the cut. 7:379a-379e then calls
        # ClearControls and zeroes the modifier: a key still held is a fresh
        # request, so a held Left turns into a run at SEQS 5's pose 48.
        (scene.held_directions, scene.up_held, scene.down_held,
         scene.shift_held, scene.ctrl_held) = held
        scene.sample_keyboard()
        scene.directional_input = DirectionalInput()
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        scene.render()

    def finish_exit(self):
        scene = self.scene
        if scene.game.level.number in (6, 7, 8):
            self.finish_via_story(scene.game.level.number + 1)
        elif scene.game.level.number == 9:
            # CheckPlayNIS(9, 10) shows NIS 2, the ride to the temple, whose
            # last shot is level ten's room 22; RestartGame then loads level
            # ten there (SetKidDefaults 2:5dee). Without the temple scenery
            # the game stops after the ride.
            from pop2.caverns import scenery_available

            def finish(keep_music=False):
                scene.game.exit = None
                if scenery_available(10):
                    scene.enter_next_level(10, keep_music=keep_music)
                else:
                    scene.level_complete = True
                    scene.status.set('Level 9 complete')
            # The ride runs as a scene: the completed level must not keep
            # calling this exit while it plays.
            scene.game.exit = None
            scene.level_complete = False
            if not scene.start_temple_ride(finish):
                finish()
        else:
            scene.start_ending()

    def controls(self):
        super().controls()
        scene = self.scene
        self.throne_vision()
        # GenCtrl 6:06b4-06e0: crouched (109) or crawling (246-261) in the
        # ruins, RuinSetCreviceRevealed 7:3404 uncovers the crevice ahead.
        caverns, motion, state = scene.game.caverns, scene.terrain_motion, scene.sequence_state
        if (caverns is None or motion is None or scene.game.level.kind != 4
                or not (state.action == 109 or 246 <= state.action <= 261)
                or not scene.combat.player.alive):
            return
        from pop2.crevices import front_crevice_group

        column = character_column(floor_contact_x(state.target_x, state.facing, scene.frames[state.action]))
        for room, cell in front_crevice_group(scene.level_map, motion.room, column, motion.row,
                                              state.facing, state.selected_sequence_id):
            foreground = scene.level_map.tile(room, cell % 10, cell // 10).foreground
            if not caverns.loose.tiles.get((room, cell), (0, 0))[1] & 0x80:
                # 7:344a only redraws a cell it uncovers now (every crevice
                # starts covered, InitState 3:5dce).
                caverns.loose.redrawn.add((room, cell))
            caverns.loose.tiles[room, cell] = CREVICE_TILE, foreground | 0x80

    def throne_vision(self):
        """4:3dd0-3df6: collapsed at the throne (SEQS 237, pose 185) in
        level eight's room 9, 7:38ca shows NIS 6 and wakes the Prince."""
        scene = self.scene
        state = scene.sequence_state
        if (scene.game.level.number != 8 or scene.room_id != THRONE_ROOM
                or state.selected_sequence_id != THRONE_COLLAPSE_SEQUENCE or state.action != 185):
            return
        if not scene.start_vision(self.wake_from_vision):
            # Without the imported scene the Prince wakes at once.
            self.wake_from_vision()

    def wake_from_vision(self):
        # 7:391c-395e after PlayNIS(6): facing right, SEQS 231 on the floor,
        # full life, logical sword word1 (a5-0x500a); song 182 (39d4),
        # which the scene usually leaves playing.
        scene = self.scene
        state, caverns = scene.sequence_state, scene.game.caverns
        state.facing = 1
        scene.start_sequence(THRONE_WAKE_SEQUENCE)
        # 7:39ca-39d0: ClearControls and a zero modifier. Presses made during
        # the collapse are gone; a key still held is a fresh request.
        scene.directional_input = DirectionalInput()
        scene.modifier_input = 0
        state.current_y = state.vertical_velocity = 0
        player = scene.combat.player
        player.life = player.max_life
        scene.game.sword_type = 1
        player.sword_lost = False
        caverns.throne_done = True
        # 7:3958 changes the logical word without LoadSwordSet. Keep the
        # old sword art loaded and the floor item until actual pickup
        # (6:152c-1552), which consumes the item and reloads the artwork.
        scene.combat.ruins.songs.append(182)
        scene.status.set("The father's sword")

    def exit_entry(self):
        scene = self.scene
        # Opcode -16 (4:2f3e-2f56): leaving at character column >= 6 opens
        # level seven at its upper entrance (a5-0x500c = 2).
        return 2 if character_column(scene.sequence_state.target_x) >= 6 else 1


class Temple(Caverns):
    """Levels 10-13 (environment 2): the temple's mechanisms, level 13's
    altar and the flight to the tower (docs/research/temple-*.md)."""

    # GetEndSong 5:4e0c-4e3e selects LvTemple for environment 2.
    end_song = 187

    def frame_start(self):
        super().frame_start()
        scene = self.scene
        caverns = scene.game.caverns
        if caverns is None:
            return
        # MakeRubble 5:29e8 advances existing doors before the actors move.
        # ATMLoose presents them after the actors can trigger new ones.
        if (scene.game.level.number, scene.room_id) == (13, 3):
            from pop2.caverns import advance_flame

            caverns.flame = advance_flame(caverns.flame)
        audio = getattr(scene, 'audio', None)
        if (caverns.trapdoors.advance() and audio is not None
                and not audio.sound_playing(OPEN_CUE) and not audio.sound_playing(LOOP_CUE)):
            audio.add_sound(LOOP_CUE)
        if not caverns.rocks.bank:
            return
        state, motion = scene.sequence_state, scene.terrain_motion
        player = scene.combat.player
        row = motion.row if motion is not None else -1
        column = scene.combat._supporting_column(player)
        # a5-0x3570: the ShapeBounds width (image + 1, with the sword's
        # extension, 4:5d20-5d56) saved from the last drawn frame (2:6454,
        # 4:23ae); the current bounds stand in for that copy.
        left, _top, right, _bottom = scene.player_collision_bounds()
        width = right - left + 2
        # The type-6 case of MakeRubble 5:2afa: motion 10:1d5c, then
        # CheckSlideRockCrush 10:16f6 against the Prince.
        for mob, events in caverns.rocks.update(scene.level_map, (state.action, column, row)):
            if motion is not None and player.alive:
                self.rock_events(mob, events)
            if (motion is not None and player.alive
                    and caverns.rocks.crushes(mob, motion.room + 1, row, native_x(state.target_x),
                                              state.sequence_mode, state.facing, width)):
                self.rock_contact(mob)
        for kind, cue in caverns.rocks.sounds:
            if kind == 'play':
                state.sound_events.append(cue)
            elif getattr(scene, 'audio', None) is not None:
                scene.audio.stop_sound(cue)

    def frame_hook(self):
        super().frame_hook()
        # The opponents (the shadow's AutoCtrl/AnimChar) run before the
        # environment hook (FrameAdv 2:7124).
        self.shadow()
        self.jinnee()
        self.altar()
        self.palette_flash(self.scene.sequence_state)

    def level_events(self):
        changed = super().level_events()
        if changed:
            return changed
        # DrawRoom3 3:324e calls ATMLoose after FrameAdv's actor/row-shake
        # triggers (2:63e6/6402, 6642). Taking this snapshot at frame_start
        # erases a newly opened tile without showing its first moving pose.
        scene = self.scene
        cues, scene.game.caverns.trapdoors.drawn = scene.game.caverns.trapdoors.present(scene.level_map)
        if cues:
            if getattr(scene, 'audio', None) is not None:
                scene.audio.stop_sound(LOOP_CUE)
            scene.sequence_state.sound_events.extend(cues)
            # Presentation restores finished cells. Rebuild their scenery
            # in this frame too, including panels in linked rooms.
            room = scene.level_renderer.enter_room(scene.room_id, scene.game.caverns)
            scene.background, scene.foreground = room.background, room.foreground
        return False

    def altar(self):
        """10:27ba -> 2a62: the Kid at level 13's sacred flame."""
        from pop2.caverns import FLARE
        from pop2.temple_altar import (
            ALTAR_LEVEL, ALTAR_ROOM, APPROACH_SONG, BURN_DEATH_METHOD, BURN_SEQUENCE, BURN_SOUND,
            BURN_X, altar_event,
        )
        from pop2.temple_shadow import shadow_rises

        scene = self.scene
        caverns, motion, state = scene.game.caverns, scene.terrain_motion, scene.sequence_state
        if caverns is None or motion is None or getattr(scene, 'god_mode', False):
            return
        if (scene.game.level.number, scene.room_id) != (ALTAR_LEVEL, ALTAR_ROOM):
            return
        # A sword kill leaves the terrain motion alone: only the Fighter is dead.
        if motion.dead or not scene.combat.player.alive:
            # KeepTime 2:6838-685e: the death message there sets a5-0x4fd4.
            if caverns.altar == 0 and scene.death.prompt_visible:
                caverns.altar = 1
            if (state.selected_sequence_id != BURN_SEQUENCE
                    and shadow_rises(motion.row, native_x(state.target_x), state.action,
                                     state.sequence_mode, caverns.altar)):
                self.raise_shadow()
            return
        audio = getattr(scene, 'audio', None)
        event = altar_event(scene.game.level.number, scene.room_id, motion.row, native_x(state.target_x),
                            state.selected_sequence_id,
                            audio is not None and audio.song_playing(APPROACH_SONG))
        if event == 'song':
            if audio is not None:
                audio.add_song(APPROACH_SONG)
        elif event == 'burn':
            # 10:2a7e-2ab4: JumpSeq(230) without AnimChar, X 335,
            # DecLifePts(100), AddSound(249), SetKidDeathMethod(16) and the
            # flame cell's foreground 0x85 (a flare).
            scene.clear_keys(None)
            scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
            state.select(BURN_SEQUENCE)
            state.target_x = state.current_x = scene_x(BURN_X)
            state.horizontal_velocity = state.vertical_velocity = 0
            motion.dead, motion.falling = True, False
            scene.combat.player.life = 0
            state.sound_events.append(BURN_SOUND)
            scene.death.begin(BURN_DEATH_METHOD)
            scene.death.music_method = BURN_DEATH_METHOD
            caverns.flame = FLARE
            scene.player_x = state.target_x
            scene.status.set('Defeated')

    def palette_flash(self, state):
        """SEQS opcode -24: fill palette entries 1-254 with one colour
        (SetPaletteToColorIdx 3:4fbc), or restore them (3:4f30)."""
        for event in [event for event in state.sequence_events if event[0] == -24]:
            state.sequence_events.remove(event)
            self.scene.palette_flash = event[1][0] if event[1] else None

    def raise_shadow(self):
        """10:2b32: the dead Kid's double rises in his place (type 1)."""
        from pop2.sequence_runtime import SequenceRuntime, SequenceState
        from pop2.temple_shadow import RISE_SEQUENCE, RISE_SONG, SHADOW_TYPE, TempleShadow
        from pop2.terrain import TerrainMotion

        scene = self.scene
        caverns, kid, motion = scene.game.caverns, scene.sequence_state, scene.terrain_motion
        # A new opponent record (count + 1, 6:3642) at the Kid's cell, X and
        # facing; SetCharFloor, Y - 1, mode 0, then JumpSeq(231) and AnimChar.
        state = SequenceState(RISE_SEQUENCE, action=kid.action, current_x=kid.target_x,
                              target_x=kid.target_x, current_y=-1, facing=kid.facing,
                              actor_type=SHADOW_TYPE, level_kind=kid.level_kind)
        caverns.shadow = TempleShadow(state, TerrainMotion(motion.room, motion.row),
                                      getattr(scene, 'step_cautious', True))
        SequenceRuntime(scene.sequence_runtime.sequences, state).next_frame()
        caverns.altar = -1
        audio = getattr(scene, 'audio', None)
        if audio is not None:
            audio.add_song(RISE_SONG)

    def shadow(self):
        """One opponent frame for the shadow: AutoCtrl 10:2850 (native room 4
        of level 13 only, 6:4f44), AnimChar, then the Kid's terrain rules."""
        from pop2.caverns import FLARE
        from pop2.mac_input import StepBoundary, plan_cautious_step
        from pop2.sequence_runtime import SequenceRuntime
        from pop2.temple_altar import ALTAR_LEVEL, ALTAR_ROOM
        from pop2.temple_shadow import (
            CATCH_SEQUENCE, CLIMB_SEQUENCE, FLAME_PALETTE, IMBUED_MODE, LEDGE_SEQUENCES, TURN_SONG,
            add_char_x, auto_ctrl,
        )
        from pop2.terrain import RooftopPhysics

        scene = self.scene
        caverns = scene.game.caverns
        shadow = getattr(caverns, 'shadow', None)
        if shadow is None or shadow.motion.room != scene.room_id:
            return
        state, motion = shadow.state, shadow.motion
        runtime = SequenceRuntime(scene.sequence_runtime.sequences, state)
        audio = getattr(scene, 'audio', None)

        def bounds(view=None):
            return scene.kid_bounds(state if view is None else view, floor_y(motion.row))

        def step(distance):
            # DoStepFwd 6:1276; 0 measures GetBarrDistances (4:5eae).
            boundary = (StepBoundary(distance) if distance else scene.level_map.step_boundary(
                motion.room, motion.row, state, scene.frames[state.action], bounds(), cautious=True))
            plan, shadow.cautious = plan_cautious_step(boundary, shadow.cautious)
            add_char_x(state, plan.pre_offset)
            if plan.sequence_id is not None:
                state.select(plan.sequence_id)
            return state.selected_sequence_id

        def run_jump():
            # DoRunJump(4) 6:1c14 (poses 7-14, reserve 48): the port's
            # Prince rule, whose actor type 0 stands for argument 4.
            if not 7 <= state.action <= 14:
                return
            from dataclasses import replace

            offset = scene.level_map.run_jump_offset(motion.room, motion.row,
                                                     replace(state, actor_type=0))
            if offset is not None:
                state.target_x += offset
                state.current_x = state.target_x
                state.select(4)

        animated = False
        if (scene.game.level.number, scene.room_id) == (ALTAR_LEVEL, ALTAR_ROOM):
            record = scene.frames[state.action]
            column = character_column(floor_contact_x(state.target_x, state.facing, record))
            kid = scene.sequence_state
            sequence, event = auto_ctrl(state, column, native_x(kid.target_x), kid.facing,
                                        step, run_jump)
            if event == 'merge':
                self.merge_shadow()
                return
            if event == 'turn' and audio is not None:
                audio.add_song(TURN_SONG)
            elif event == 'catch':
                if motion.falling and scene.level_map.catch_ledge(motion.room, motion.row, state, record):
                    # Catch 4:37ca: JumpSeq(15) and its first pose (80),
                    # aligned with that pose's frame (4:38da).
                    motion.falling = False
                    state.select(CATCH_SEQUENCE)
                    runtime.next_frame()
                    scene.level_map.align_catch(motion.room, motion.row, state,
                                                scene.frames[state.action])
                    state.sound_events.append(9)
                    animated = True
            elif event == 'hang':
                # DoJumpHang 6:1b7e previews AnimChar: a later pose climbs
                # (6:1998 gives the shadow SEQS 10 without the gate test).
                if runtime.peek_frame().action > state.action:
                    sequence = CLIMB_SEQUENCE
                    if state.sequence_mode == IMBUED_MODE:
                        state.current_y -= 2
            elif event == 'flare':
                caverns.flame = FLARE
            elif event == 'palette':
                shadow.palette = FLAME_PALETTE
            if sequence is not None:
                state.select(sequence)
        old_x = state.target_x
        if not animated:
            runtime.next_frame()
        # SEQS -3/-4 change the floor row, -6 the absolute Y.
        if state.engine_counter:
            motion.row += state.engine_counter
            state.current_y -= state.engine_counter * TILE_HEIGHT
            state.engine_counter = 0
        self.palette_flash(state)
        state.sequence_events.clear()
        RooftopPhysics(scene.level_map, scene.frames).advance(
            motion, runtime, old_x, bounds(), frame_record=scene.frames[state.action],
            bounds_for_state=bounds, cut_enabled=False,
            protected=state.sequence_id in LEDGE_SEQUENCES)
        state.current_x = state.target_x
        # FrameAdv 2:6602: every opponent runs CheckPress 5:127e, which keeps
        # a branch for this actor type (5:12a6). Altar plate 4:12 is what
        # opens level 13's door 32:12.
        record = scene.frames[state.action]
        state.sound_events.extend(caverns.loose.press(scene.level_map, motion, state, record))
        state.sound_events.extend(caverns.plates.press(scene.level_map, motion, state, record,
                                                       sword_type=scene.game.sword_type))
        # The shadow's footsteps join the Kid's cues (both actor sounds).
        scene.sequence_state.sound_events.extend(state.sound_events)
        state.sound_events.clear()

    def jinnee(self):
        """Level 12's genie: released by SEQS 111, then one opponent frame of
        AnimChar and CheckPress (2:6602) while the Prince is in his room."""
        from pop2.jinnee import Jinnee, SONG
        from pop2.sequence_runtime import SequenceRuntime

        scene = self.scene
        caverns = scene.game.caverns
        potions = caverns.potions
        kid = scene.sequence_state
        if potions.jinnee_released:
            potions.jinnee_released = False
            caverns.jinnee = Jinnee.released(kid, scene.terrain_motion)
            potions.songs.append(SONG)
        jinnee = caverns.jinnee
        if jinnee is None or jinnee.motion.room != scene.room_id:
            return
        state, motion = jinnee.state, jinnee.motion
        SequenceRuntime(scene.sequence_runtime.sequences, state).next_frame()
        state.current_x = state.target_x
        state.sequence_events.clear()
        record = jinnee.record
        kid.sound_events.extend(caverns.loose.press(scene.level_map, motion, state, record))
        kid.sound_events.extend(caverns.trapdoors.check(scene.level_map, motion, state, record))
        kid.sound_events.extend(caverns.plates.press(scene.level_map, motion, state, record,
                                                     sword_type=scene.game.sword_type))
        state.sound_events.clear()
        if jinnee.gone:
            caverns.jinnee = None

    def extra_actors(self, size):
        return (*self.shadow_actors(size), *self.jinnee_actors(size))

    def jinnee_actors(self, size):
        """The genie: FRAM 750's body and, as with the flaming sword, its AFRM
        piece at the same arithmetic (3:0b4a-0b64). Drawn only if imported."""
        from PIL import Image

        from pop2.animation_data import parse_aframe_records, parse_frame_records
        from pop2.jinnee import FIRST_POSE, SHAPE_LIST
        from pop2.render_opening import (
            character_sprite_top, decode_ctbl, decode_shap, load_resource_file,
        )

        scene = self.scene
        jinnee = scene.game.caverns.jinnee
        if jinnee is None or jinnee.motion.room != scene.room_id:
            return ()
        art = scene.__dict__.get('jinnee_art')
        if art is None:
            try:
                resource = load_resource_file('Jinnee.rsrc')
            except OSError:
                return ()
            art = scene.__dict__['jinnee_art'] = dict(
                resource=resource, palette=decode_ctbl(resource['CTBL'][SHAPE_LIST]['data']),
                base=int.from_bytes(resource['SHPL'][SHAPE_LIST]['data'][:2], 'big'),
                frames=parse_frame_records(resource['FRAM'][SHAPE_LIST]['data']),
                attachments=parse_aframe_records(resource['AFRM'][SHAPE_LIST]['data']), images={})

        def image(index):
            shape = art['base'] + index
            if shape not in art['images']:
                art['images'][shape] = decode_shap(art['resource']['SHAP'][shape]['data'], art['palette'])
            return art['images'][shape]

        state = jinnee.state
        record = art['frames'][state.action - FIRST_POSE]
        floor = floor_y(jinnee.motion.row) + state.current_y + record.offset_y
        placed = []
        if record.shape_index >= 0:
            sprite = image(record.shape_index)
            placed.append((sprite, state.target_x - record.offset_x, floor))
        _, piece, dx, dy = art['attachments'][record.afrm_index]
        if piece > 0:
            sprite = image(piece)
            placed.append((sprite, state.target_x - record.offset_x - dx, floor + dy))
        if not placed:
            return ()
        layer = Image.new('RGBA', size)
        for sprite, x, bottom in placed:
            layer.paste(sprite, (x, character_sprite_top(bottom, sprite.height)), sprite)
        left = min(x for _, x, _ in placed)
        right = max(x + sprite.width - 1 for sprite, x, _ in placed)
        bottom = max(bottom for _, _, bottom in placed)
        top = min(character_sprite_top(bottom, sprite.height) for sprite, _, bottom in placed)
        return ((state, record, (left, top, right, bottom), jinnee.motion.row, layer),)

    def shadow_actors(self, size):
        """The shadow: Kid frames in palette entries 48-63 (draw mode 0x30)."""
        from PIL import Image, ImageOps

        from pop2.animation_data import shape_id_for_action
        from pop2.render_opening import character_sprite_top, decode_ctbl, decode_shap
        from pop2.temple_shadow import FLAME_PALETTE, IMBUED_MODE, flame_shape

        scene = self.scene
        shadow = getattr(scene.game.caverns, 'shadow', None)
        if shadow is None or shadow.motion.room != scene.room_id:
            return ()
        state = shadow.state
        shape_id = shape_id_for_action(scene.frames, scene.first_shape_id, state.action)
        if shape_id is None or shape_id not in scene.kid['SHAP']:
            return ()
        cache = scene.__dict__.setdefault('shadow_sprites', {})

        def image(palette, shape):
            if (palette, shape) not in cache:
                colours = decode_ctbl(scene.kid['CTBL'][palette]['data'])
                if palette == FLAME_PALETTE:
                    # CTBL 4077 holds entries 224-239: loaded at 48 (or the
                    # flame's base 224) it colours the images' 1-16.
                    colours = {index - 223: colour for index, colour in colours.items()}
                cache[palette, shape] = decode_shap(scene.kid['SHAP'][shape]['data'], colours)
            return cache[palette, shape]

        sprite, record = image(shadow.palette, shape_id), scene.frames[state.action]
        anchor = record.offset_x
        if state.facing:
            sprite = ImageOps.mirror(sprite)
            anchor = sprite.width - anchor
        floor = floor_y(shadow.motion.row)
        x = state.target_x - anchor
        y = character_sprite_top(floor + record.offset_y + state.current_y, sprite.height)
        layer = Image.new('RGBA', size)
        if state.sequence_mode == IMBUED_MODE:
            # SetupOpponent 3:0a4c -> SetupShadowFlame 4:2630: while
            # IsShadowImbued (4:2590, mode 13) SHAP 4102 + frame % 9, palette
            # base 224 (CTBL 4077, 10:2edc), centred on its image with the
            # bottoms aligned (10:2f1e). It is object type 14: GetObjForePriority
            # gives it 200 against the shadow's 127, and SortObjTable 3:3b62
            # draws the higher priority first, so it burns behind the shadow.
            combat = getattr(scene, 'combat', None)
            flame = image(FLAME_PALETTE, flame_shape(combat.world_frame if combat is not None else 0))
            if state.facing:
                flame = ImageOps.mirror(flame)
            layer.paste(flame, (x + sprite.width // 2 - flame.width // 2,
                                y + sprite.height - flame.height), flame)
        layer.paste(sprite, (x, y), sprite)
        return ((state, record, scene.kid_bounds(state, floor), shadow.motion.row, layer),)

    def merge_shadow(self):
        """10:27d8: the shadow lying on the body revives the Kid."""
        from pop2.rebirth import DeathState
        from pop2.temple_shadow import IMBUED_MODE, MERGE_SONG, RISE_SEQUENCE

        scene = self.scene
        kid, motion, player = scene.sequence_state, scene.terrain_motion, scene.combat.player
        # JumpSeq(231), ALIVE -1, full life, the death message cleared
        # (a5-0x4fcc/-4fca), mode 13, unarmed; the shadow removed (4:48f8).
        kid.select(RISE_SEQUENCE)
        kid.sequence_mode = IMBUED_MODE
        motion.dead = motion.falling = False
        player.life = player.max_life
        scene.death = DeathState()
        scene.sword_drawn = False
        scene.game.caverns.shadow = None
        scene.status.set('Ready')
        audio = getattr(scene, 'audio', None)
        if audio is not None:
            audio.add_song(MERGE_SONG)

    def rock_events(self, mob, events):
        """The actor endpoints of 10:1d5c, for the Prince."""
        from pop2.slide_rocks import face_column

        scene = self.scene
        player, state = scene.combat.player, scene.sequence_state
        if '5:3cee' in events and not getattr(scene, 'god_mode', False):
            # A rock stopping at spikes (its face tile 2) runs the spike
            # impalement 5:3cee on the Prince: the spike cell bloodied
            # (0xf0), the Prince pinned in his own column (4:3b30).
            spike = scene.level_map.tile(mob[2] - 1, face_column(mob[0] - 3), mob[6])
            if spike.room is not None:
                scene.game.caverns.spikes.foreground[spike.room, spike.row * 10 + spike.column] = 240
            record = scene.frames[state.action]
            own = character_column(floor_contact_x(state.target_x, state.facing, record))
            self.impale(player, 54 if state.facing else 51, own * 51 + 90)
        elif '6:1a84' in events and scene.native_ledge:
            # A rock reaching the hanging Prince's ledge makes him let go.
            scene.release_native_ledge()

    def rock_contact(self, mob):
        """10:1b04: the rock pushes the Prince to its face; against a wall it
        crushes him (control 100: pose 185, else SEQS 71), in the open he
        bumps (armed 93, else 47 facing right / 48 left)."""
        scene = self.scene
        player, state, motion = scene.combat.player, scene.sequence_state, scene.terrain_motion
        if state.action == 5:
            return
        if native_x(state.target_x) - 229 > mob[0]:
            state.target_x = scene_x(mob[0] + 223)
        column = character_column(state.target_x - 12)
        tile = scene.level_map.tile(motion.room, column, motion.row).kind
        if tile in (20, 2, 7, 25, 43, 4):
            state.target_x = column * TILE_WIDTH + 63 + (6 if state.facing else 0)
            state.current_x = state.target_x
            if tile == 2:
                return
            if mob[4] == 100:
                player.life = 0
                state.action = 185
                motion.dead = True
                scene.death.begin(13)
                return
            # 10:1c04-1c4c: crushed against the wall (SetKidDeathMethod 13
            # when the rock's face is close enough), sequence mode 4, SEQS 71.
            state.sequence_mode = 4
            scene.physics.select(player.runtime, 71)
            player.life = 0
            motion.dead = True
            scene.death.begin(13)
        elif player.sword_drawn:
            player.sword_drawn = False
            scene.physics.select(player.runtime, 93)
        else:
            scene.physics.select(player.runtime, 47 if state.facing else 48)
        state.current_x = state.target_x
        state.current_y = state.vertical_velocity = 0
        scene.action, scene.player_x = state.action, state.target_x

    def scenery_layer(self, frame, motion):
        from pop2.caverns import draw_slide_rocks, draw_temple_flame, draw_trapdoors

        scene = self.scene
        frame = super().scenery_layer(frame, motion)
        frame = draw_temple_flame(frame, scene.room_id, scene.game.caverns.flame,
                                  level_number=scene.game.level.number)
        frame = draw_trapdoors(frame, scene.room_id, scene.game.caverns.trapdoors.drawn,
                               scene.level_map, level_number=scene.game.level.number,
                               art=scene.level_renderer.room(scene.room_id, scene.game.caverns))
        return draw_slide_rocks(frame, scene.room_id, scene.game.caverns.rocks, scene.level_map,
                                level_number=scene.game.level.number)

    def finish_exit(self):
        scene = self.scene
        number = scene.game.level.number
        if number in (10, 11, 12):
            # CheckPlayNIS 2:0180 (a tree scene at most), then RestartGame.
            self.finish_via_story(number + 1)
        else:
            # CheckPlayNIS(13, 14) shows NIS 3, the flight to the tower.
            def finish():
                scene.game.exit = None
                from pop2.caverns import scenery_available

                if scenery_available(14):
                    scene.enter_next_level(14)
                else:
                    # A running installation may lose the final files after
                    # startup; name the missing handoff instead of claiming
                    # that the campaign ends at level thirteen.
                    scene.level_complete = True
                    scene.status.set('Level 14 files missing; reimport game files')
            scene.game.exit = None
            scene.level_complete = False
            if not scene.start_tower_flight(finish):
                finish()


def environment_for(scene):
    """The environment of the scene's current level.

    Chosen by the level's environment state, which the game creates for
    kinds 2, 3, 4 and 6 (exported scenery), level two (desert) and kind 5
    (the harbor).
    """
    game = scene.game
    if getattr(game, 'caverns', None) is not None:
        # Final's scenery shares the exported room format; CODE 9 owns its
        # gameplay hooks rather than the cavern/ruins controller.
        return {4: Ruins, 2: Temple, 6: Final}.get(game.level.kind, Caverns)(scene)
    if getattr(game, 'desert', None) is not None:
        return Desert(scene)
    if getattr(game, 'harbor', None) is not None:
        return Rooftops(scene)
    return Environment(scene)
