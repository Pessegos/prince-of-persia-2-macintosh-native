import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level7.json').is_file(), 'Imported level-seven resources required')
class LevelSevenTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(7)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_level_seven_starts_from_room_thirty_twos_door_with_a_sword(self):
        # LEVL 2006: native room 32, cell 24; SetKidDefaults selects SEQS 5
        # and 3:61ec gives levels seven and eight sword type 2.
        scene = self.scene
        caverns = scene.game.caverns
        self.assertEqual((scene.room_id, caverns.entry_room, caverns.entry_cell), (31, 31, 24))
        self.assertEqual(scene.sequence_state.selected_sequence_id, 5)
        self.assertEqual(scene.game.sword_type, 2)
        self.assertFalse(scene.combat.player.sword_lost)
        self.tick(20)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (31, 2))

    def test_leaving_level_six_at_column_six_or_more_opens_the_upper_entrance(self):
        # Opcode -16 (4:2f3e-2f56) and SetKidDefaults 2:5eda: native room 4,
        # cell 25, whose door closes behind him, with room 32's door shut.
        scene = self.scene
        scene.load_level(6)
        scene.game.ruins_entry = 2
        scene.load_level(7)
        caverns = scene.game.caverns
        self.assertEqual((scene.room_id, caverns.entry_room, caverns.entry_cell), (3, 3, 25))
        self.assertTrue(caverns.alternate_entry)
        self.assertEqual(scene.level_map.tile(31, 4, 2).foreground & 255, 0)
        self.assertEqual(caverns.entry_frame, 0)
        self.tick(20)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (3, 2))
        scene.game.restart()
        self.assertEqual(scene.game.room_id, 3)

    def test_the_level_six_exit_column_chooses_the_entrance(self):
        # The exit sequences end at X 168 (left door, column 2) and 372
        # (right door, column 6) of level six's native room 16.
        scene = self.scene
        for x, entry in ((168, 1), (372, 2)):
            scene.sequence_state.target_x = x
            self.assertEqual(scene.level_six_exit_entry(), entry)

    def test_entering_every_room_does_not_raise(self):
        # Opponent set 5 (heads and serpents) is not generated yet.
        for room in range(32):
            self.scene.game.combat.enter_room(room, 1)
            self.scene.jump_to_room(room, 1, 200, 1)
            self.tick()

    def test_level_seven_draws_its_scythes(self):
        program = self.scene.level_renderer.cavern_program
        self.assertEqual(program['level'], 7)
        self.assertTrue(program['scythes']['scythes'])
        self.assertTrue(any(room.get('scythes') for room in program['loose_floors']['rooms'].values()))

    def test_the_level_map_opens(self):
        from pop2.development_map import build_development_map
        from pop2.game_session import GameResources

        level_map = build_development_map(GameResources.load().level(7))
        self.assertEqual(level_map.start, 'Room 32')
        self.assertEqual(len(level_map.positions), 32)


@unittest.skipUnless((ASSET_DIR / 'ruins_level7.json').is_file(), 'Imported level-seven resources required')
class LevelSixToSevenTests(unittest.TestCase):
    def test_finishing_level_six_asks_the_story_then_loads_level_seven(self):
        from unittest.mock import patch
        from tests.test_level6 import LevelSixSceneryTests

        LevelSixSceneryTests.setUp(self)
        scene = self.scene
        with patch.object(scene.game.story, 'select_scene', return_value=None) as select:
            scene.finish_level_via_story(6, 7)
        select.assert_called_once_with(6, 7)
        self.assertEqual(scene.game.level.number, 7)

    def test_a_tree_scene_plays_before_level_seven(self):
        from unittest.mock import patch
        from tests.test_level6 import LevelSixSceneryTests

        LevelSixSceneryTests.setUp(self)
        scene = self.scene
        with patch.object(scene.game.story, 'select_scene', return_value=22), \
                patch.object(scene, 'start_tree') as tree:
            scene.finish_level_via_story(6, 7)
        tree.assert_called_once_with(3)
        self.assertEqual(scene.next_level_after_tree, 7)


@unittest.skipUnless((ASSET_DIR / 'ruins_level7.json').is_file(), 'Imported level-seven resources required')
class LevelSevenSaveTests(unittest.TestCase):
    def test_a_level_seven_snapshot_round_trips(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pop2.game_session import GameResources, GameSession
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        resources = GameResources.load()
        game = GameSession.load(resources, 7)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            write_save(path, capture_snapshot(game))
            loaded, _saved = read_snapshot(path, resources)
        self.assertEqual((loaded.level.number, loaded.sword_type), (7, 2))

    def test_the_upper_entrance_survives_both_save_formats(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pop2.game_session import GameResources, GameSession
        from pop2.save_game import capture, capture_snapshot, read_save, read_snapshot, write_save

        resources = GameResources.load()
        game = GameSession.load(resources, 7, ruins_entry=2)
        self.assertEqual(game.level.start_room, 3)
        with TemporaryDirectory() as directory:
            for name, document, reader in (('progress', capture(game), read_save),
                                           ('snapshot', capture_snapshot(game), read_snapshot)):
                path = Path(directory) / f'{name}.json'
                write_save(path, document)
                loaded, _saved = reader(path, resources)
                self.assertEqual((loaded.ruins_entry, loaded.level.start_room), (2, 3), name)


if __name__ == '__main__':
    unittest.main()
