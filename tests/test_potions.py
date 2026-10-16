import random
import struct
from types import SimpleNamespace
import unittest

from PIL import ImageChops

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
        from pop2.caverns import draw_cavern_flasks

        s = self.make_scene()
        s.jump_to_room(9, row=1, x=430, facing=0)
        before = s.background.copy()
        draw_cavern_flasks(before, 9, s.game.caverns, s.level_map)
        self.assertIsNotNone(ImageChops.difference(before, s.background).convert('RGB').getbbox())
        s.game.caverns.potions.take(s.level_map.tile(9, 7, 1))
        after = s.background.copy()
        draw_cavern_flasks(after, 9, s.game.caverns, s.level_map)
        self.assertIsNone(ImageChops.difference(after, s.background).convert('RGB').getbbox())


if __name__ == '__main__':
    unittest.main()
