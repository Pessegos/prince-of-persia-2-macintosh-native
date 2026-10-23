import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported level-six resources required')
class LevelSixSceneryTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(6)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_level_six_starts_on_the_cliff_with_its_custom_palette(self):
        from pop2.caverns import room_assets

        scene = self.scene
        self.tick(4)
        state = scene.sequence_state
        self.assertEqual((scene.room_id, state.sequence_id, state.target_x), (26, 2, 167))
        self.assertIsNotNone(scene.game.caverns)
        # CUST kind 22's enter hook 7:37a6 loads CTBL 3502 over entry 64.
        _program, resources, palette, _shapes = room_assets(6, 26)
        self.assertNotEqual(palette[64], room_assets(6, 0)[2][64])
        self.assertEqual(scene.level_renderer.cavern_program['level'], 6)

    def test_walking_left_off_the_cliff_comes_out_of_room_threes_door(self):
        # CutChar 6:4d7c-4d92 -> S07_373E: native room 3, column 4, row 2,
        # facing right, SEQS 5; its exit closes behind the Prince.
        from types import SimpleNamespace

        scene = self.scene
        self.tick(4)
        event = SimpleNamespace(keysym='Left', state=0)
        scene.horizontal_key(event, -1, True)
        for _ in range(25):
            self.tick()
            if scene.room_id != 26:
                break
        scene.horizontal_key(event, -1, False)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (2, 2))
        self.assertEqual(scene.game.caverns.entry_room, 2)
        self.assertIn(scene.sequence_state.selected_sequence_id, (5, 2))
        program = scene.level_renderer.cavern_program
        self.assertEqual((program['entry_exit']['room'], program['entry_exit']['cell']), (2, 24))

    def test_running_over_room_ones_loose_floors_drops_ruins_slabs(self):
        # DrawObjLoose 3:412c-41aa draws a falling ruins slab with pieces 14
        # and 18; the caverns' SHAP 3604 is absent from Ruins.rsrc and froze
        # the game.
        from types import SimpleNamespace

        scene = self.scene
        scene.jump_to_room(0, 2, 160, 1)
        event = SimpleNamespace(keysym='Right', state=0)
        scene.horizontal_key(event, 1, True)
        loose = scene.game.caverns.loose
        fell = False
        for _ in range(60):
            self.tick()
            scene.render()
            fell = fell or bool(loose.falling)
        scene.horizontal_key(event, 1, False)
        self.assertTrue(fell)
        self.assertEqual(loose.tiles.get((0, 24)), (0, 3))

    def test_room_threes_door_stays_shut_and_silent_until_the_cliff_exit(self):
        caverns = self.scene.game.caverns
        self.assertEqual(caverns.entry_room, 2)
        self.assertEqual(caverns.entry_frame, len(caverns.entry_frames) - 1)
        self.assertEqual(caverns.advance(), ())

    def test_crouching_at_a_crevice_uncovers_its_whole_run(self):
        from pop2.caverns import cavern_scene_signature

        scene = self.scene
        caverns = scene.game.caverns
        scene.jump_to_room(16, 1, 399, 1)
        program = scene.level_renderer.cavern_program
        self.assertEqual(cavern_scene_signature(program, 16, caverns), '000')
        scene.set_key_state('down', True)
        self.tick(12)
        scene.set_key_state('down', False)
        self.assertEqual({key for key, (kind, value) in caverns.loose.tiles.items()
                          if kind == 7 and value & 0x80}, {(16, 18), (16, 19), (17, 10)})
        self.assertEqual(cavern_scene_signature(program, 16, caverns), '111')

    def test_down_and_forward_at_a_crevice_lies_down_and_crawls_through_it(self):
        # GenCtrl 6:0a4e-0b28 lies down (SEQS 125); prone, CheckCollide
        # 4:5ade lets the body (at most 34 pixels high) through open crevices
        # and 6:07ee-0994 crawls (122) and stands (124) once clear of them.
        from types import SimpleNamespace

        scene = self.scene
        state = scene.sequence_state
        scene.jump_to_room(16, 1, 399, 1)
        scene.set_key_state('down', True)
        self.tick(10)
        event = SimpleNamespace(keysym='Right', state=0)
        scene.horizontal_key(event, 1, True)
        seen = []
        for _ in range(70):
            self.tick()
            seen.append((scene.room_id, state.selected_sequence_id))
            if state.selected_sequence_id == 124:
                break
        scene.horizontal_key(event, 1, False)
        scene.set_key_state('down', False)
        self.assertEqual(seen[0], (16, 125))
        self.assertIn((16, 122), seen)
        self.assertIn((17, 122), seen)
        self.assertEqual(seen[-1], (17, 124))
        self.assertEqual(scene.terrain_motion.row, 1)
        self.assertFalse(scene.terrain_motion.falling)

    def test_a_standing_prince_is_still_stopped_by_a_crevice(self):
        level_map = self.scene.level_map
        tile = level_map.tile(16, 8, 1)
        self.assertEqual((tile.kind, tile.foreground & 3 != 3), (7, True))
        x = 8 * 51 + 22 + 3 - 20
        standing = level_map.wall_correction(16, x - 10, x, (x - 20, 150, x + 20, 230), physical_row=1)
        self.assertLess(standing, x)
        prone = level_map.wall_correction(16, x - 10, x, (x - 20, 200, x + 20, 230), physical_row=1)
        self.assertEqual(prone, x)

    def test_entering_rooms_beside_heads_does_not_raise(self):
        # Room 6 neighbours rooms whose opponent set 5 is not generated yet;
        # choosing the visible opponent bank raised and froze the game.
        for room in range(32):
            self.scene.game.combat.enter_room(room, 1)

    def test_the_sword_item_room_draws_from_the_sword_library(self):
        scene = self.scene
        scene.jump_to_room(16, 1, 100, 1)
        program = scene.level_renderer.cavern_program
        self.assertIn(1046, [command[1] for command in program['rooms']['16'] if command[7] == 0])
        self.tick()
        self.assertEqual(scene.room_id, 16)


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported level-six resources required')
class LevelSixSwordTests(unittest.TestCase):
    """3:6202-6216 (no sword in level six) and the sword item pickup 6:14ce-1574."""

    def setUp(self):
        LevelSixSceneryTests.setUp(self)

    def tick(self, count=1):
        LevelSixSceneryTests.tick(self, count)

    def test_level_six_starts_without_a_sword(self):
        scene = self.scene
        self.assertEqual(scene.game.sword_type, -1)
        self.assertTrue(scene.combat.player.sword_lost)
        self.assertFalse(scene.queue_sword_action('sword_draw'))

    def test_crouching_at_the_sword_item_takes_it(self):
        scene = self.scene
        picked = None
        for x in range(240, 300, 3):
            scene.jump_to_room(16, 1, x, 1)
            scene.combat.player.sword_lost = True
            scene.shift_held = True
            scene.down_held = True
            for _ in range(10):
                self.tick()
                if scene.sequence_state.sequence_id in (91, 92):
                    picked = x
                    break
            scene.shift_held = scene.down_held = False
            if picked is not None:
                break
        self.assertIsNotNone(picked)
        self.assertFalse(scene.combat.player.sword_lost)
        self.assertEqual(scene.game.sword_type, 2)
        self.assertEqual(scene.level_map.tile(16, 5, 1).kind, 1)


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported level-six resources required')
class LevelSixSaveTests(unittest.TestCase):
    def test_a_picked_up_sword_survives_both_save_formats(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pop2.game_session import GameResources, GameSession
        from pop2.save_game import capture, capture_snapshot, read_save, read_snapshot, write_save

        resources = GameResources.load()
        game = GameSession.load(resources, 6)
        self.assertTrue(game.combat.player.sword_lost)
        game.sword_type = 2
        game.arm_prince()
        with TemporaryDirectory() as directory:
            for name, document, reader in (('progress', capture(game), read_save),
                                           ('snapshot', capture_snapshot(game), read_snapshot)):
                path = Path(directory) / f'{name}.json'
                write_save(path, document)
                loaded, _saved = reader(path, resources)
                self.assertEqual(loaded.sword_type, 2, name)
                self.assertFalse(loaded.combat.player.sword_lost, name)
                loaded.restart()
                self.assertTrue(loaded.combat.player.sword_lost, name)



@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported level-six resources required')
class LevelSixMapTests(unittest.TestCase):
    def test_the_level_map_opens_without_generating_heads_or_serpents(self):
        # Opponent set 5 is not generated yet; the map previously raised on
        # every repaint of the level menu.
        from pop2.development_map import build_development_map
        from pop2.game_session import GameResources

        level_map = build_development_map(GameResources.load().level(6))
        self.assertEqual(level_map.start, 'Room 27')
        self.assertIn('Room 17', level_map.positions)
        # Rooms 28 and 14 are never shown; the cliff sits beside room 1.
        self.assertNotIn('Room 28', level_map.positions)
        self.assertNotIn('Room 14', level_map.positions)
        self.assertNotIn('Room 10', level_map.positions)
        x, y = level_map.positions['Room 1']
        self.assertEqual(level_map.positions['Room 27'], (x + 1, y))
        # Only plate-linked exits end the level: not the room-1 or room-3 doors.
        self.assertEqual(level_map.exits, frozenset({'Room 16'}))


if __name__ == '__main__':
    unittest.main()
