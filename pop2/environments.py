"""Environment-specific frame work, one class per native environment kind.

The original selects these through its environment hook table (FrameAdv
2:7124 -> a5-0x46f8[environment]): desert 18:01e0, caverns 8:3b92 (level
five's BridgeCheckBreak), rooftops 23:0874. ScenePrototype runs them in its
frame phases (pop2.frame_phases); the classes hold no state of their own.
"""

import time

from pop2.bridge import BRIDGE_ROOM, CREAK_SOUND, bridge_checked, bridge_gate_open, on_bridge
from pop2.control_mapping import IDLE_SEQUENCE
from pop2.crevices import CREVICE_TILE
from pop2.harbor import SHIP_CLIMB_SEQUENCE
from pop2.loose_floors import floor_hits_actor
from pop2.opponent_generation import character_column
from pop2.render_opening import TILE_HEIGHT
from pop2.terrain import floor_contact_x, floor_y

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

    def frame_hook(self):
        """The 'environment' frame phase."""

    def harbor_phase(self):
        """The 'harbor' frame phase: level one's ship and water."""

    def level_events(self):
        """Level mechanisms after the environment hook; True when the level changed."""
        return False

    def exit_scenery(self):
        """While the exit song plays: the main loop still runs FrameAdv."""

    def finish_exit(self):
        """After the exit song: level one's voyage scene."""
        self.scene.start_ending()


class Rooftops(Environment):
    """Level one (environment kind 5): the rooftops and the harbor."""

    def exit_scenery(self):
        self.scene.harbor.advance()

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
        return False

    def frame_start(self):
        scene = self.scene
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
        actors = (scene.combat.player, *scene.combat.active_guards())
        for block in blocks:
            for actor in actors:
                state, motion = actor.state, actor.terrain_motion
                record = (scene.frames[state.action] if actor is scene.combat.player else
                          scene.guard_art.frames[guard_frame_index(state.action)])
                if (motion is None or not floor_hits_actor(block, motion, state, record, actor.alive)
                        or actor is scene.combat.player and getattr(scene, 'god_mode', False)
                        or 5 <= state.action < 15 or state.action == 109
                        or state.animation_state >= 2 and state.animation_state != 7
                        or state.actor_type == 1):
                    continue
                # Crushed 6:28f0: one life for the Prince, fatal for an
                # ordinary guard; survivors use SEQS:52, not sword recoil.
                actor.life = max(0, actor.life - (1 if state.actor_type == 0 else 100))
                state.current_y = 0
                motion.falling = False
                actor.recovering = actor.alive
                if actor.skeleton is not None:
                    actor.skeleton.collapse(actor, encounter=scene.combat)
                    actor.runtime.next_frame()
                    continue
                scene.physics.select(actor.runtime, 52 if actor.alive else 22)
                if actor.alive:
                    state.sound_events.append(300)
                else:
                    motion.dead = True
                    if actor is scene.combat.player:
                        scene.death.begin(3)
                if actor is scene.combat.player:
                    scene.run_active = scene.run_stop_requested = scene.run_cycle_boundary_pending = False
                    scene.pending_action = None
                    scene.action, scene.player_x = state.action, state.target_x
        for room, cell, kind in caverns.loose.plate_events:
            scene.sequence_state.sound_events.extend(caverns.plates.impact(scene.level_map, room, cell, kind))
        caverns.loose.plate_events.clear()
        caverns.loose.advance_tiles(scene.level_map)
        scene.sequence_state.sound_events.extend(caverns.scythes.advance(scene.level_map))
        scene.sequence_state.sound_events.extend(caverns.plates.advance(
            scene.level_map, scene.sequence_state, scene.terrain_motion, scene.frames[scene.action]))
        scene.advance_relief(caverns)
        stopped = set(caverns.plates.stopped_sounds)
        if stopped:
            scene.sequence_state.sound_events[:] = [
                cue for cue in scene.sequence_state.sound_events if cue not in stopped]
        if getattr(scene, "audio", None) is not None:
            for cue in caverns.plates.stopped_sounds:
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
            hit = spikes.contact(scene.level_map, motion, state, record, collision,
                                 actor.alive, actor.sword_drawn)
            if hit is None:
                continue
            sequence, state.target_x = hit
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
        # FrameAdv 2:63f4-63fe and 2:664a-664e (ruins): 5:57bc may start a
        # scythe, then CheckScytheHit 5:588a, which the Prince skips while
        # invulnerable (a5-0x4f90).
        if scene.game.level.kind != 4 or 'scythes' not in scene.level_renderer.cavern_program:
            return  # An import before the scythes' drawing: leave them still.
        from pop2.scythes import CUT_SEQUENCE, CUT_SOUND

        scythes = scene.game.caverns.scythes
        for actor in (scene.combat.player, *scene.combat.active_guards()):
            state, motion = actor.state, actor.terrain_motion
            if motion is None or not actor.alive:
                continue
            player = actor is scene.combat.player
            scythes.trigger(scene.level_map, motion, state)
            if player and getattr(scene, 'god_mode', False):
                continue
            bounds = (scene.player_collision_bounds() if player else
                      scene.guard_art.collision_bounds(state, floor_y(motion.row), actor.sword_drawn))
            if not scythes.cut(scene.level_map, motion, state, bounds):
                continue
            # 5:5942-597e: SEQS 113 and death method 5 for the Prince, SEQS
            # 190 for a guard; DecLifePts(100) and sound 278.
            actor.life = 0
            motion.dead = True
            actor.recovering = False
            state.sound_events.append(CUT_SOUND)
            scene.physics.select(actor.runtime, CUT_SEQUENCE if player else 190)
            if player:
                scene.clear_keys(None)
                scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = False
                scene.run_active = scene.run_stop_requested = scene.run_cycle_boundary_pending = False
                scene.pending_action = None
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
        if getattr(scene, "audio", None) is not None:
            scene.audio.drain(state)
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

    def finish_via_story(self, following):
        from pop2.caverns import scenery_available

        scene = self.scene
        if scenery_available(following):
            scene.finish_level_via_story(scene.game.level.number, following)
        else:
            scene.game.exit = None
            scene.status.set(f'Level {following} needs a reimport of the game files')


class Ruins(Caverns):
    """Levels six and seven (kind 4)."""

    end_song = 124

    def finish_exit(self):
        scene = self.scene
        if scene.game.level.number == 6:
            self.finish_via_story(7)
        elif scene.game.level.number == 7:
            # Level eight is not available yet.
            scene.game.exit = None
            scene.status.set('Level 7 complete')
        else:
            scene.start_ending()

    def controls(self):
        scene = self.scene
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
            caverns.loose.tiles[room, cell] = CREVICE_TILE, foreground | 0x80


def environment_for(scene):
    """The environment of the scene's current level.

    Chosen by the level's environment state, which the game creates for
    kinds 3 and 4 (caverns), level two (desert) and kind 5 (the harbor).
    """
    game = scene.game
    if getattr(game, 'caverns', None) is not None:
        return (Ruins if game.level.kind == 4 else Caverns)(scene)
    if getattr(game, 'desert', None) is not None:
        return Desert(scene)
    if getattr(game, 'harbor', None) is not None:
        return Rooftops(scene)
    return Environment(scene)
