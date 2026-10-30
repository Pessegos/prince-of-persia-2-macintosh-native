import unittest
from unittest.mock import patch

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level9.json').is_file(), 'Imported level-eight/nine resources required')
class LevelEightAndNineTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_both_levels_start_standing_at_their_entrance_door(self):
        # LEVL 2007/2008: native rooms 16 and 10; SetKidDefaults 2:5e34
        # selects the ordinary standing entry (SEQS 5) for both.
        scene = self.scene
        for number, room in ((8, 15), (9, 9)):
            scene.load_level(number)
            caverns = scene.game.caverns
            self.assertEqual((scene.room_id, caverns.entry_room), (room, room))
            self.assertEqual(scene.sequence_state.selected_sequence_id, 5)
            self.tick(20)
            self.assertEqual(scene.terrain_motion.row, 1)
            self.assertTrue(scene.combat.player.alive)

    def test_entering_every_room_does_not_raise(self):
        scene = self.scene
        for number in (8, 9):
            scene.load_level(number)
            for room in range(32):
                scene.game.combat.enter_room(room, 1)
                scene.jump_to_room(room, 1, 200, 1)
                self.tick()

    def test_the_ruins_lead_from_level_seven_to_nine_and_stop_before_the_temple(self):
        from pop2.environments import environment_for

        scene = self.scene
        for number in (7, 8):
            scene.load_level(number)
            scene.game.story.tree_stage = 7  # No tree scene in between.
            environment_for(scene).finish_exit()
            self.assertEqual(scene.game.level.number, number + 1)
        scene.game.exit = object()
        # With Horse.rsrc/TempleNIS.rsrc installed the ride plays first and
        # finishes the level later; check the stop itself without it.
        with patch.object(scene, 'start_temple_ride', return_value=False):
            environment_for(scene).finish_exit()
        self.assertIsNone(scene.game.exit)
        self.assertEqual(scene.game.level.number, 9)


if __name__ == '__main__':
    unittest.main()
