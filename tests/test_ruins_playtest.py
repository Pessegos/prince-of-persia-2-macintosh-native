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
