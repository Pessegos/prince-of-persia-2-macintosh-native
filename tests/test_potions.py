import random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.cavern_state import CavernState
from pop2.paths import ASSET_DIR
from pop2.potions import Potions, pickup_target, potion_kind
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap
from pop2.animation_data import FrameRecord


class PotionTests(unittest.TestCase):
    def setUp(self):
        data = bytearray(0x6000)
        data[:1920] = struct.pack('>960H', *([1] * 960))
        struct.pack_into('>H', data, 0x2198, 1)
        struct.pack_into('>H', data, 0x2186, 3)
        self.data = data
        self.place(0, 13, 0x132)
        self.terrain = LevelMap(bytes(data))
        self.caverns = self.terrain.caverns = CavernState()
        self.potions = self.caverns.potions
        self.potions.configure(self.terrain, random.Random(1))

    def place(self, room, cell, foreground):
        struct.pack_into('>H', self.data, room * 60 + cell * 2, 10)
        struct.pack_into('>H', self.data, 0x780 + room * 120 + cell * 4, foreground)

    def test_kind_ignores_floor_decoration_and_animation_phase(self):
        for kind in range(8):
            for phase in range(32):
                self.assertEqual(potion_kind(0xab00 | kind << 5 | phase), kind)

    def test_front_pass_draws_flasks_before_the_front_spikes(self):
        from pop2.level_rendering import LevelRenderer

        renderer = LevelRenderer.__new__(LevelRenderer)
        renderer.cavern_map = self.terrain
        actors = Image.new('RGBA', (2, 2), 'blue')
        flasks = Image.new('RGBA', (2, 2), 'red')
        for number in (3, 4):
            renderer.level = SimpleNamespace(number=number, kind=3)
            with (self.subTest(level=number),
                  patch('pop2.caverns.draw_cavern_flasks', return_value=flasks) as draw,
                  patch('pop2.caverns.draw_cavern_spikes', return_value=flasks) as spikes):
                self.assertIs(renderer.animated_layer(actors, 0, None, front=True,
                                                     caverns=self.caverns), flasks)
            draw.assert_called_once_with(actors, 0, self.caverns, self.terrain, level_number=number)
            spikes.assert_called_once_with(flasks, 0, self.caverns, self.terrain, front=True,
                                           level_number=number)

    def test_pickup_alignment_matches_native_standing_and_crouched_anchors(self):
        motion = SimpleNamespace(room=0, row=1)
        records = {15: FrameRecord(15, 14, 0, 4, 0, 70),
                   109: FrameRecord(109, 119, 0, 1, 0, 81)}
        for facing, pose, delta in ((0, 15, 12), (0, 109, 6), (1, 15, 3), (1, 109, -3)):
            state = SequenceState(2, action=pose, target_x=188, facing=facing)
            tile, actual = pickup_target(self.terrain, motion, state, records[pose])
            self.assertEqual((tile.room, tile.row, tile.column, actual), (0, 1, 3, delta))

    def test_native_cycle_preserves_type_and_floor_decoration(self):
        self.potions.phases = {(0, 13): 0xa121, (1, 13): 0x142}
        for phase in list(range(2, 28)) + [0, 1]:
            self.potions.advance([(0, 13), (0, 13)])
            self.assertEqual(self.potions.phases[0, 13], 0xa120 | phase)
            self.assertEqual(self.potions.phases[1, 13], 0x142)

    def test_removal_leaves_a_floor_and_preserves_only_native_rock_decoration(self):
        tile = self.terrain.tile(0, 3, 1)
        self.potions.take(tile)
        result = self.terrain.tile(0, 3, 1)
        self.assertEqual((result.kind, result.foreground), (1, 0x100))
        self.potions.advance([(0, 13)])
        self.assertEqual(self.terrain.tile(0, 3, 1), result)

    def test_healing_waits_for_the_late_effect_and_is_not_applied_twice(self):
        self.potions.take(self.terrain.tile(0, 3, 1))
        actor = SimpleNamespace(life=1, max_life=3, alive=True)
        state = SequenceState(78, sequence_events=[(-14, (2,))])
        self.potions.consume_events(state, actor)
        self.assertEqual(actor.life, 1)
        state.sequence_events.extend([(-14, (1,)), (-14, (1,))])
        self.potions.consume_events(state, actor)
        self.assertEqual((actor.life, actor.max_life), (2, 3))
        self.assertEqual(self.potions.songs, [24])
        self.assertEqual(state.sequence_events, [])

    def test_normal_potion_never_exceeds_full_health(self):
        self.potions.take(self.terrain.tile(0, 3, 1))
        actor = SimpleNamespace(life=3, max_life=3, alive=True)
        self.potions.consume_events(SequenceState(78, sequence_events=[(-14, (1,))]), actor)
        self.assertEqual((actor.life, actor.max_life), (3, 3))

    def test_mega_potion_fully_heals_and_caps_capacity_at_twelve(self):
        for maximum in (3, 11, 12):
            with self.subTest(maximum=maximum):
                p = Potions(held_kind=2, effect_pending=True)
                actor = SimpleNamespace(life=1, max_life=maximum, alive=True)
                p.consume_events(SequenceState(78, sequence_events=[(-14, (1,))]), actor)
                self.assertEqual((actor.life, actor.max_life), (min(12, maximum + 1),) * 2)

    def test_effect_does_not_revive_a_dead_prince(self):
        p = Potions(held_kind=2, effect_pending=True)
        actor = SimpleNamespace(life=0, max_life=3, alive=False)
        p.consume_events(SequenceState(78, sequence_events=[(-14, (1,))]), actor)
        self.assertEqual((actor.life, actor.max_life), (0, 3))
        self.assertEqual(p.songs, [])

    def test_poison_costs_one_life_with_sound_twelve_and_no_song(self):
        # DoPickupEffect 4:4678-46b0: DecLifePts(1), AddSound(12).
        p = Potions(held_kind=5, effect_pending=True)
        actor = SimpleNamespace(life=3, max_life=3, alive=True)
        state = SequenceState(78, sequence_events=[(-14, (1,))])
        p.consume_events(state, actor)
        self.assertEqual((actor.life, actor.max_life, state.sound_events, p.songs, p.fatal),
                         (2, 3, [12], [], False))

    def test_poison_on_the_last_life_requests_the_native_death(self):
        p = Potions(held_kind=5, effect_pending=True)
        actor = SimpleNamespace(life=1, max_life=3, alive=True)
        p.consume_events(SequenceState(78, sequence_events=[(-14, (1,))]), actor)
        self.assertEqual((actor.life, p.fatal), (0, True))

    def test_poison_flask_can_be_picked_up_but_unmodelled_types_cannot(self):
        motion = SimpleNamespace(room=0, row=1)
        record = FrameRecord(15, 14, 0, 4, 0, 70)
        state = SequenceState(2, action=15, facing=1, target_x=188)
        for kind, drinkable in ((1, True), (2, True), (3, True), (4, False), (5, True), (6, False)):
            with self.subTest(kind=kind):
                self.place(0, 13, kind << 5)
                terrain = LevelMap(bytes(self.data))
                self.assertEqual(pickup_target(terrain, motion, state, record) is not None, drinkable)

    def test_float_flask_starts_the_global_slow_fall_timer_and_song(self):
        # 4:466c -> 2:5a26: 228 updates and AddSong(111); 2:6c5e counts down.
        p = Potions(held_kind=3, effect_pending=True)
        actor = SimpleNamespace(life=2, max_life=3, alive=True)
        p.consume_events(SequenceState(78, sequence_events=[(-14, (1,))]), actor)
        self.assertEqual((p.float_timer, p.songs, actor.life), (228, [111], 2))
        for _ in range(228):
            self.assertTrue(p.floating)
            p.advance_float()
        self.assertFalse(p.floating)
        p.advance_float()
        self.assertEqual(p.float_timer, 0)

    def test_sequence_pickup_operations_are_emitted_at_their_original_boundaries(self):
        state = SequenceState(78)
        runtime = SequenceRuntime({78: (196, -14, 2, 197, 205, -14, 1, 205)}, state)
        runtime.next_frame()
        self.assertEqual(state.sequence_events, [])
        runtime.next_frame()
        self.assertEqual(state.sequence_events, [(-14, (2,))])
        runtime.next_frame()
        runtime.next_frame()
        self.assertEqual(state.sequence_events, [(-14, (2,)), (-14, (1,))])


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedPotionTests(unittest.TestCase):
    def make_scene(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(3)
        self.scene.peaceful = True
        return self.scene

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_level_three_has_five_normal_and_two_mega_potions(self):
        s = self.make_scene()
        entries = [(room + 1, cell, potion_kind(value))
                   for (room, cell), value in s.game.caverns.potions.phases.items()]
        self.assertEqual(entries, [(7, 3, 1), (9, 16, 1), (10, 17, 2), (12, 11, 1),
                                   (20, 8, 2), (26, 26, 1), (32, 27, 1)])

    def test_original_palette_remapping_starts_at_224_without_a_missing_pink_color(self):
        from pop2.caverns import flask_assets, flask_shape
        from pop2.render_opening import decode_ctbl

        resources, colors = flask_assets()
        original = list(decode_ctbl(resources['CTBL'][3000]['data']).values())
        self.assertEqual([colors[i] for i in range(224, 239)], original)
        for shape in (3001, 3002):
            sprite = flask_shape(resources['SHAP'][shape]['data'], colors, 16)
            self.assertNotIn((255, 0, 255, 255), [color for _count, color in sprite.getcolors()])

    def test_all_flasks_and_particles_stay_in_front_of_overlapping_prince(self):
        from pop2.caverns import draw_cavern_flasks
        from pop2.scene_prototype import ROOM_ORIGIN_X

        s = self.make_scene()
        for room, cell in s.game.caverns.potions.phases:
            row, column = divmod(cell, 10)
            for facing in (0, 1):
                s.jump_to_room(room, row=row, x=column * 51 + 35, facing=facing)
                original = s.game.caverns.potions.phases[room, cell]
                for phase in (0, 10, 14, 24):
                    with self.subTest(room=room + 1, facing=facing, phase=phase):
                        s.game.caverns.potions.phases[room, cell] = original & ~31 | phase
                        expected = Image.new('RGBA', s.background.size)
                        draw_cavern_flasks(expected, room, s.game.caverns, s.level_map)
                        self.assertIsNotNone(expected.getbbox())
                        s.render()
                        actual = s.screenshot_viewport.crop((
                            ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + expected.width, expected.height))
                        difference = ImageChops.difference(actual.convert('RGB'), expected.convert('RGB'))
                        self.assertIsNone(ImageChops.multiply(
                            difference, expected.getchannel('A').convert('RGB')).getbbox())

    def test_each_real_potion_can_be_drunk_from_both_sides_with_native_timing(self):
        s = self.make_scene()
        locations = list(s.game.caverns.potions.phases)
        for room, cell in locations:
            for facing in (0, 1):
                with self.subTest(room=room + 1, facing=facing):
                    s.load_level(3)
                    row, column = divmod(cell, 10)
                    # Start in the potion's own supporting-foot cell.
                    x = column * 51 + 35
                    s.jump_to_room(room, row=row, x=x, facing=facing)
                    s.combat.player.life = 1
                    kind = potion_kind(s.level_map.tile(room, column, row).foreground)
                    s.shift_held = True
                    frames, health = [], []
                    for _ in range(28):
                        self.tick()
                        frames.append(s.action)
                        health.append((s.combat.player.life, s.combat.player.max_life))
                    self.assertIn(191, frames)
                    self.assertIn(205, frames)
                    self.assertEqual(health[0], (1, 3))
                    self.assertEqual(health[-1], (4, 4) if kind == 2 else (2, 3))
                    self.assertEqual(s.level_map.tile(room, column, row).kind, 1)
                    self.assertFalse(s.game.caverns.potions.effect_pending)
                    self.assertIn(s.action, (15,))

    def test_level_four_poison_flasks_cost_a_life_and_can_kill(self):
        # Rooms 14 and 29 hold type-5 flasks (4:4678-46b0).
        s = self.make_scene()
        for room, cell, life in ((28, 25, 3), (13, 15, 1)):
            with self.subTest(room=room + 1):
                s.load_level(4)
                row, column = divmod(cell, 10)
                self.assertEqual(potion_kind(s.level_map.tile(room, column, row).foreground), 5)
                s.jump_to_room(room, row=row, x=column * 51 + 35, facing=1)
                s.combat.player.life = life
                s.shift_held = True
                for _ in range(28):
                    self.tick()
                s.shift_held = False
                self.assertEqual(s.level_map.tile(room, column, row).kind, 1)
                self.assertEqual(s.combat.player.life, life - 1)
                if life == 1:
                    self.assertTrue(s.terrain_motion.dead)
                    self.assertEqual(s.death.method, 3)

    def test_level_four_float_flask_survives_the_room_six_shaft(self):
        # Without the float the shaft below room 6 is a fatal fall.
        s = self.make_scene()
        for drink in (True, False):
            with self.subTest(drink=drink):
                s.load_level(4)
                s.jump_to_room(5, row=0, x=2 * 51 + 35, facing=1)
                if drink:
                    s.shift_held = True
                    for _ in range(28):
                        self.tick()
                    s.shift_held = False
                    self.assertTrue(s.game.caverns.potions.floating)
                s.horizontal_key(None, 1, True)
                fall_sequences, speeds = set(), []
                for step in range(260):
                    self.tick()
                    if step == 6:
                        s.horizontal_key(None, 1, False)
                    if s.terrain_motion.falling:
                        fall_sequences.add(s.sequence_state.source_sequence_id)
                        speeds.append(s.sequence_state.vertical_velocity)
                    if not s.combat.player.alive or s.terrain_motion.dead:
                        break
                if drink:
                    self.assertIn(228, fall_sequences)
                    self.assertLessEqual(max(speeds), 8)
                    self.assertEqual(s.combat.player.life, s.combat.player.max_life)
                else:
                    self.assertFalse(s.combat.player.alive)

    def test_running_jumping_and_wrong_row_do_not_pick_up_a_flask(self):
        s = self.make_scene()
        for sequence in (202, 4, 3):
            s.jump_to_room(9, row=1, x=400, facing=0)
            s.start_sequence(sequence)
            s.sequence_runtime.next_frame()
            s.action = s.sequence_state.action
            s.shift_held = True
            s.game.caverns.potions.shift_was_held = False
            self.assertFalse(s.update_potion_controls())
            self.assertEqual(s.level_map.tile(9, 7, 1).kind, 10)
        s.jump_to_room(9, row=2, x=400, facing=0)
        s.shift_held = True
        s.game.caverns.potions.shift_was_held = False
        self.assertFalse(s.update_potion_controls())

    def test_shift_and_forward_press_near_a_potion_pick_it_up_before_stepping(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=430, facing=0)
        s.in_animation_tick = True
        s.shift_held = True
        s.horizontal_key(None, -1, True)
        self.assertEqual(s.sequence_state.sequence_id, 50)
        self.tick(23)
        self.assertEqual(s.combat.player.max_life, 4)

    def room_18_drop(self):
        s = self.make_scene()
        s.jump_to_room(17, row=1, x=445, facing=1)
        s.in_animation_tick = True
        s.combat.player.life = 1
        s.set_key_state('down', True)
        s.set_key_state('down', False)
        for _ in range(25):
            self.tick()
            if s.terrain_motion.falling:
                return s
        self.fail('The room 18 ledge never released')

    def stop_at_room_10_potion(self, scene, direction, release_frame=7):
        scene.load_level(3)
        scene.jump_to_room(9, row=1, x=300 if direction > 0 else 460,
                           facing=int(direction > 0))
        scene.in_animation_tick = True
        scene.horizontal_key(None, direction, True)
        self.tick(release_frame)
        scene.horizontal_key(None, direction, False)

    def test_shift_tap_survives_run_braking_from_both_sides(self):
        s = self.make_scene()
        with patch.object(s, 'render'):
            for direction in (-1, 1):
                for release_frame in (6, 7):
                    for delay in (0, 2, 6):
                        with self.subTest(direction=direction, release_frame=release_frame, delay=delay):
                            self.stop_at_room_10_potion(s, direction, release_frame)
                            self.tick(delay)
                            # Both events arrive before the next simulation tick.
                            s.set_key_state('shift', True)
                            s.set_key_state('shift', False)
                            self.assertIsNotNone(s.pending_potion_pickup)
                            previous = None
                            for _ in range(16):
                                previous = s.sequence_state.sequence_id, s.action
                                self.tick()
                                if s.sequence_state.sequence_id == 50:
                                    break
                            self.assertEqual(previous, (13, 50))
                            self.assertEqual((s.sequence_state.sequence_id, s.action), (50, 107))
                            self.assertFalse(s.shift_held)
                            self.assertIsNone(s.pending_potion_pickup)
                            self.assertEqual(s.combat.player.max_life, 3)
                            self.tick(24)
                            self.assertEqual((s.combat.player.life, s.combat.player.max_life), (4, 4))
                            self.assertEqual(s.level_map.tile(9, 7, 1).kind, 1)

    def test_held_shift_can_pick_up_at_first_braking_control_pose(self):
        s = self.make_scene()
        with patch.object(s, 'render'):
            for direction in (-1, 1):
                self.stop_at_room_10_potion(s, direction)
                s.set_key_state('shift', True)
                self.tick(6)
                self.assertEqual((s.sequence_state.sequence_id, s.action), (13, 50))
                self.tick()
                self.assertEqual((s.sequence_state.sequence_id, s.action), (50, 107))

    def test_grounded_shift_tap_also_survives_until_next_idle_tick(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=380, facing=1)
        s.set_key_state('shift', True)
        s.set_key_state('shift', False)
        self.tick()
        self.assertEqual((s.sequence_state.sequence_id, s.action), (50, 107))

    def test_pickup_tap_is_cancelled_by_new_movement_warp_or_cleared_controls(self):
        s = self.make_scene()
        with patch.object(s, 'render'):
            for cancel in ('run', 'up', 'ctrl', 'clear', 'warp', 'fall'):
                with self.subTest(cancel=cancel):
                    self.stop_at_room_10_potion(s, 1)
                    s.set_key_state('shift', True)
                    s.set_key_state('shift', False)
                    if cancel == 'run':
                        s.horizontal_key(None, 1, True)
                    elif cancel in ('up', 'ctrl'):
                        s.set_key_state(cancel, True)
                    elif cancel == 'clear':
                        s.clear_keys(None)
                    elif cancel == 'warp':
                        s.jump_to_room(9, row=1, x=380, facing=1)
                    else:
                        s.terrain_motion.falling = True
                    s.update_potion_controls()
                    self.assertIsNone(s.pending_potion_pickup)
                    self.assertIsNone(s.game.caverns.potions.picking)
                    self.assertFalse(s.game.caverns.potions.drinking)

    def test_tap_without_reachable_flask_expires_and_does_not_latch_shift(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=300, facing=1)
        s.set_key_state('shift', True)
        s.set_key_state('shift', False)
        self.tick()
        self.assertIsNone(s.pending_potion_pickup)
        self.assertFalse(s.shift_held)
        s.player_x = s.sequence_state.target_x = s.sequence_state.current_x = 380
        self.assertFalse(s.update_potion_controls())
        self.assertEqual(s.level_map.tile(9, 7, 1).kind, 10)

    def test_shift_does_not_interrupt_wall_bump_poses_that_resemble_braking(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=380, facing=1)
        s.start_sequence(47)
        s.sequence_runtime.next_frame()
        s.set_key_state('shift', True)
        self.assertEqual(s.sequence_state.action, 50)
        self.assertFalse(s.update_potion_controls())
        self.assertIsNone(s.game.caverns.potions.picking)

    def test_shift_held_during_room_18_drop_drinks_mega_from_the_room_20_landing_crouch(self):
        s = self.room_18_drop()
        s.set_key_state('shift', True)
        poses = []
        for _ in range(25):
            self.tick()
            poses.append((s.action, s.sequence_state.source_sequence_id))
            if s.game.caverns.potions.drinking:
                break
            self.assertEqual((s.combat.player.life, s.combat.player.max_life), (1, 3))
            self.assertEqual(s.level_map.tile(19, 8, 0).kind, 10)
        self.assertEqual((s.room_id, s.terrain_motion.row), (19, 0))
        self.assertEqual(poses[-2:], [(109, 17), (191, 78)])
        self.assertNotIn(110, [action for action, _sequence in poses])
        self.tick(28)
        self.assertEqual((s.combat.player.life, s.combat.player.max_life), (4, 4))
        self.assertEqual(s.level_map.tile(19, 8, 0).kind, 1)

    def test_releasing_queued_shift_before_landing_cancels_the_drink_request(self):
        s = self.room_18_drop()
        s.set_key_state('shift', True)
        self.tick()
        s.set_key_state('shift', False)
        for _ in range(45):
            self.tick()
            self.assertFalse(s.game.caverns.potions.drinking)
        self.assertEqual((s.room_id, s.terrain_motion.row), (19, 0))
        self.assertEqual((s.combat.player.life, s.combat.player.max_life), (1, 3))
        self.assertEqual(s.level_map.tile(19, 8, 0).kind, 10)

    def test_hard_fall_crouch_does_not_consume_shift_or_interrupt_protected_recovery(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=400, facing=0)
        s.start_sequence(20)
        s.sequence_state.action = s.action = 109
        s.sequence_state.animation_state = 5
        s.set_key_state('shift', True)
        self.assertFalse(s.update_potion_controls())
        self.assertEqual(s.sequence_state.source_sequence_id, 20)
        self.assertFalse(s.game.caverns.potions.shift_was_held)
        s.start_sequence(2)
        s.sequence_runtime.next_frame()
        s.action = s.sequence_state.action
        self.assertTrue(s.update_potion_controls())
        self.assertEqual(s.sequence_state.source_sequence_id, 50)

    def test_restart_restores_consumed_flasks_without_leaving_a_pending_effect(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=430, facing=0)
        s.shift_held = True
        self.tick(28)
        self.assertEqual(s.level_map.tile(9, 7, 1).kind, 1)
        s.restart_level()
        self.assertEqual(s.level_map.tile(9, 7, 1).kind, 10)
        self.assertFalse(s.game.caverns.potions.drinking)
        self.assertEqual(s.game.caverns.potions.held_kind, 0)
        self.assertEqual(s.combat.player.max_life, 3)

    def test_restart_preserves_entry_capacity_not_an_upgrade_collected_in_this_attempt(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=430, facing=0)
        s.combat.player.life = s.combat.player.max_life = 5
        s.shift_held = True
        self.tick(28)
        self.assertEqual(s.combat.player.max_life, 6)
        s.restart_level()
        self.assertEqual((s.combat.player.life, s.combat.player.max_life), (5, 5))

    def test_f3_preserves_mega_upgrades_and_consumed_flasks_until_restart(self):
        s = self.make_scene()
        for room, row, column, capacity in ((9, 1, 7, 4), (19, 0, 8, 5)):
            with self.subTest(room=room + 1):
                s.jump_to_room(room, row=row, x=column * 51 + 35, facing=0)
                self.tick()
                s.shift_held = True
                self.tick(28)
                self.assertEqual((s.combat.player.life, s.combat.player.max_life),
                                 (capacity, capacity))
                s.jump_to_room(9, row=1, x=430, facing=0)
                self.assertEqual((s.combat.player.life, s.combat.player.max_life),
                                 (capacity, capacity))
                self.assertEqual(s.level_map.tile(room, column, row).kind, 1)
        s.restart_level()
        self.assertEqual((s.combat.player.life, s.combat.player.max_life), (3, 3))
        self.assertEqual(s.level_map.tile(9, 7, 1).kind, 10)
        self.assertEqual(s.level_map.tile(19, 8, 0).kind, 10)

    def test_pause_freezes_collection_animation_health_and_particle_phase(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=430, facing=0)
        s.shift_held = True
        self.tick(10)
        before = (s.action, s.sequence_state.cursor, s.combat.player.life,
                  dict(s.game.caverns.potions.phases))
        s.set_paused(True)
        self.tick(10)
        self.assertEqual((s.action, s.sequence_state.cursor, s.combat.player.life,
                          s.game.caverns.potions.phases), before)
        s.set_paused(False)
        self.tick(18)
        self.assertEqual(s.combat.player.max_life, 4)

    def test_attachment_uses_the_original_flask_library_not_the_sword_library(self):
        from pop2.caverns import flask_assets
        from pop2.render_opening import decode_shap

        s = self.make_scene()
        s.game.caverns.potions.held_kind = 2
        resources, palette = flask_assets()
        for action in range(191, 206):
            if action == 199:
                continue
            s.action = action
            _kind, index, dx, dy = s.attachment_frames[s.frames[action].afrm_index]
            sprite, actual_x, actual_y = s.sword_sprite()
            expected = decode_shap(resources['SHAP'][3001 + index]['data'], palette)
            self.assertEqual((actual_x, actual_y), (dx, dy))
            self.assertIsNone(ImageChops.difference(sprite, expected).convert('RGB').getbbox())

    def test_consumed_flask_is_removed_from_static_and_animated_scenery(self):
        s = self.make_scene()
        s.jump_to_room(9, row=1, x=430, facing=0)
        before = s.background.copy()
        s.level_renderer.animated_layer(before, 9, None, front=True, caverns=s.game.caverns)
        self.assertIsNotNone(ImageChops.difference(before, s.background).convert('RGB').getbbox())
        s.game.caverns.potions.take(s.level_map.tile(9, 7, 1))
        after = s.background.copy()
        s.level_renderer.animated_layer(after, 9, None, front=True, caverns=s.game.caverns)
        self.assertIsNone(ImageChops.difference(after, s.background).convert('RGB').getbbox())


if __name__ == '__main__':
    unittest.main()
