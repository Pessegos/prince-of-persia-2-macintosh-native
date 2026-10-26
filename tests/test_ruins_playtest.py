"""Regressions for the overnight ruins playtest, using isolated scene input."""

import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported ruins required')
class RuinsPlaytestTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(6)
        self.scene.peaceful = True

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_first_head_is_crushed_by_the_falling_shelf_and_stays_dead_on_return(self):
        from unittest.mock import patch

        s = self.scene
        s.peaceful = False
        s.jump_to_room(3, 2, 120, 1)
        brain = s.combat.ruins
        head = s.combat.visible_ruins()[0]
        head.row = 2
        head.state.current_y = -33
        head.state.target_x = head.state.current_x = 200
        head.state.horizontal_velocity = head.state.vertical_velocity = 0
        brain.jump(head, 141)  # Angry hovering pose, distinct from resting150.
        head.runtime.next_frame()
        brain.banked = head
        tile = s.level_map.tile(3, 3, 1)
        self.assertEqual(tile.kind, 15)
        s.game.caverns.loose.break_shelf(s.level_map, tile, 3)
        # Hold its horizontal AI position to isolate the falling-slab trick.
        # The real shelf, gravity, contact, damage and animation still run.
        with patch.object(brain, 'control_head'):
            for _ in range(8):
                previous_pose = head.state.action
                self.tick()
                if not head.alive:
                    break
        self.assertEqual(head.life, 0)
        self.assertEqual(head.state.source_sequence_id, 146)
        self.assertIsNone(brain.banked)
        self.assertNotEqual(previous_pose, 150)
        self.assertEqual((head.state.action, head.state.cursor), (150, 1))
        with patch.object(s.guard_art, 'draw', wraps=s.guard_art.draw) as draw:
            s.render()
        self.assertEqual(draw.call_args_list[0].args[1].action, previous_pose)
        self.assertEqual((head.state.action, head.state.cursor), (150, 1))
        self.tick()
        self.assertEqual(head.state.action, 226)
        self.assertEqual(s.slab_crush_poses, {})
        self.tick(12)
        s.jump_to_room(2, 2, 100, 1, reset_guards=False)
        s.jump_to_room(3, 2, 120, 1, reset_guards=False)
        self.assertIn(head, brain.actors(3))
        self.assertEqual(head.life, 0)
        self.assertEqual(head.state.source_sequence_id, 146)

    def test_falling_slab_uses_the_serpents_flattened_death(self):
        from unittest.mock import patch
        from pop2.loose_floors import FallingFloor

        s = self.scene
        s.peaceful = False
        s.jump_to_room(19, 2, 120, 1)
        brain = s.combat.ruins
        serpent = s.combat.visible_ruins()[0]
        self.assertEqual(serpent.state.actor_type, 11)
        serpent.state.target_x = serpent.state.current_x = 250
        column = brain.column(serpent, s.combat)
        s.game.caverns.loose.falling.append(FallingFloor(19, column, 2, 330, 16, 3))
        with patch.object(brain, 'control_serpent'):
            self.tick(2)
        self.assertEqual(serpent.life, 0)
        self.assertEqual(serpent.state.source_sequence_id, 169)

    def test_physical_up_and_its_release_both_map_to_down_while_inverted(self):
        s = self.scene
        s.jump_to_room(24, 1, 137, 1)
        s.game.caverns.potions.toggle_flip()
        s.sync_flipped_controls()
        s.up_key(None)  # Actual KeyPress-Up uses its own binding.
        self.assertTrue(s.down_held)
        self.assertFalse(s.up_held)
        s.set_key_state('up', False)
        self.assertFalse(s.down_held or s.up_held)
        self.tick(15)
        self.assertNotIn(s.sequence_state.source_sequence_id, (14, 28))

    def test_mega_potion_shaft_preserved_slab_cushions_a_cautious_descent(self):
        from unittest.mock import patch

        s = self.scene
        # Native rooms5 ->6 (cell25) ->18. Cautious descent from the
        # mega-potion platform; the unused slab must still be present.
        s.jump_to_room(4, 2, 340, 1)
        s.in_animation_tick = True
        s.set_key_state('down', True)
        with patch.object(s, 'render'), patch.object(s, 'advance_audio'):
            for step in range(50):
                if step == 8:
                    s.set_key_state('down', False)
                self.tick()
                if s.room_id == 17 and not s.terrain_motion.falling or not s.combat.player.alive:
                    break
        self.assertIn((5, 25), s.game.caverns.loose.cleared)
        self.assertEqual((s.room_id, s.terrain_motion.row), (17, 1))
        self.assertTrue(s.combat.player.alive)
        self.assertEqual(s.combat.player.life, 2)

    def test_level7_room32_special_floor_falls_on_contact_and_redraws(self):
        s = self.scene
        s.load_level(7)
        s.jump_to_room(31, 2, 128, 1)
        self.assertEqual(s.level_map.tile(31, 2, 2).kind, 15)
        self.tick(2)
        self.assertEqual(s.level_map.tile(31, 2, 2).kind, 0)
        self.assertTrue(s.game.caverns.loose.falling)
        s.render()

    def test_room25_inverted_potion_then_jump_and_falling_slab_do_not_freeze(self):
        s = self.scene
        s.jump_to_room(24, 1, 137, 1)
        s.set_key_state('shift', True)
        self.tick(32)
        s.set_key_state('shift', False)
        self.assertTrue(s.world_flipped())
        s.set_key_state('down', True)
        self.tick(3)
        s.set_key_state('down', False)
        self.tick(55)
        self.assertIn((24, 2), s.game.caverns.loose.cleared)
        self.assertEqual(s.level_map.tile(24, 2, 1).kind, 14)

    def test_scythe_cut_keeps_all_five_kid_frames_visible(self):
        s = self.scene
        s.jump_to_room(18, 2, 285, 1)
        s.combat.player.life = 0
        s.death.begin(5)
        s.physics.select(s.sequence_runtime, 113)
        for pose in range(267, 272):
            self.assertEqual(s.sequence_state.action, pose)
            self.assertIsNotNone(s.player_sprite(s.sequence_state.action))
            s.sequence_runtime.next_frame()

    def test_god_k_kills_heads_and_serpents_without_changing_other_rooms(self):
        from types import SimpleNamespace

        s = self.scene
        s.set_god_mode(True)
        for room in (3, 19):
            s.jump_to_room(room, 2, 100, 1)
            c = s.combat
            c.ruins.load_room(c, 6)
            others = [(actor.life, actor.state.source_sequence_id) for actor in c.ruins.actors(6)]
            actors = c.ruins.actors(room)
            self.assertTrue(actors)
            s.dev_key_press(SimpleNamespace(keysym='k', state=0))
            s.dev_key_release(SimpleNamespace(keysym='k', state=0))
            self.assertTrue(all(actor.life == 0 for actor in actors))
            self.assertTrue(all(actor.state.source_sequence_id in (154, 174) for actor in actors))
            c.ruins.load_room(c, room)
            self.assertTrue(all(actor.life == 0 for actor in actors))
            self.assertEqual(others, [(actor.life, actor.state.source_sequence_id)
                                     for actor in c.ruins.actors(6)])

    def test_level7_map_keeps_both_entry_doors_and_roundtrips_cached_starts(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pop2.development_map import cached_development_map

        with TemporaryDirectory() as directory:
            level = self.scene.resources.level(7)
            first = cached_development_map(level, 'alternate-start-regression', Path(directory))
            second = cached_development_map(level, 'alternate-start-regression', Path(directory))
        self.assertEqual(first.starts, frozenset(('Room 32', 'Room 4')))
        self.assertEqual(first.starts, second.starts)

    def test_requested_unused_rooms_are_hidden_only_from_the_level6_map(self):
        from pop2.development_map import room_positions

        terrain = self.scene.level_map
        before = terrain.level
        positions = room_positions(terrain)
        self.assertNotIn(23, positions)
        self.assertNotIn(25, positions)
        self.assertIn(24, positions)  # Potion/serpent room stays reachable.
        self.assertEqual(terrain.level, before)

    def test_cautious_cliff_descent_reaches_the_scream_without_a_floor_impact(self):
        from unittest.mock import patch

        s = self.scene
        s.jump_to_room(26, 2, 250, 0)
        s.in_animation_tick = True
        heard = []
        s.set_key_state('down', True)
        with patch.object(s, 'render'), patch.object(s, 'advance_audio'):
            for step in range(45):
                if step == 5:
                    s.set_key_state('down', False)
                s.sequence_state.sound_events.clear()
                self.tick()
                heard.extend(s.sequence_state.sound_events)
                if s.terrain_motion.dead:
                    break
        self.assertTrue(s.terrain_motion.void_fall)
        self.assertTrue(s.terrain_motion.dead)
        self.assertEqual(heard.count(8), 1)
        self.assertNotIn(7, heard)
