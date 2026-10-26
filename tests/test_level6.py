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
        cells = program['loose_floors']['rooms']['16']['cells']
        crevices = {(16, 18), (16, 19), (17, 10)}
        self.assertEqual(cavern_scene_signature(program, 16, caverns), '0' * len(cells))
        scene.set_key_state('down', True)
        self.tick(12)
        scene.set_key_state('down', False)
        self.assertEqual({key for key, (kind, value) in caverns.loose.tiles.items()
                          if kind == 7 and value & 0x80}, {(16, 18), (16, 19), (17, 10)})
        self.assertEqual(cavern_scene_signature(program, 16, caverns),
                         ''.join('1' if tuple(key) in crevices else '0' for key in cells))

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

    def test_a_shaking_loose_floor_shows_both_ruins_shake_images(self):
        # 7:2bd6: per column parity two shake images; for this odd column
        # phases 1 and 8-10 show the first, phases 3-4 the second (exported
        # as the cell's last choice; the port used to show the first for all).
        from pop2.caverns import cavern_room, cavern_scene_signature, room_assets
        from pop2.cavern_state import CavernState

        program, *_ = room_assets(6, 5)
        choices = program['loose_floors']['cells']['5:25']
        if len(choices) < 4:
            self.skipTest('Ruins export from before the second shake image: reimport the game')

        def drawn(phase):
            state = CavernState()
            state.loose.tiles[(5, 25)] = (11, (choices[0][1] & 0xfff0) | phase)
            key = cavern_scene_signature(program, 5, state)
            art = cavern_room(5, level_number=6, loose_key=key)
            return key, art.background.tobytes() + art.foreground.tobytes()

        keys = {phase: drawn(phase) for phase in (0, 1, 3, 8)}
        self.assertEqual([keys[phase][0] for phase in (0, 1, 3, 8)], ['0', '1', '3', '1'])
        self.assertNotEqual(keys[1][1], keys[3][1])
        self.assertNotEqual(keys[0][1], keys[3][1])
        self.assertEqual(keys[1][1], keys[8][1])

    def test_lying_down_facing_left_against_a_crevice_stays_down_and_crawls(self):
        # tools/probe_crawl_lie_down.py: the original lies down 34 past the
        # crevice (X 85), collides at frame 259 (35 pixels high) and Collide
        # 4:59b6-59dc backs the prone Prince off 5 (X 89) into SEQS 121;
        # the port used to choose the standing bump 47 and loop forever.
        from types import SimpleNamespace

        scene = self.scene
        state = scene.sequence_state
        scene.jump_to_room(17, 1, 81, 0)
        self.tick(3)
        scene.set_key_state('down', True)
        self.tick(10)
        event = SimpleNamespace(keysym='Left', state=0)
        scene.horizontal_key(event, -1, True)
        seen = []
        for _ in range(60):
            self.tick()
            seen.append((state.selected_sequence_id, state.target_x))
            if scene.room_id != 17 or state.selected_sequence_id == 124:
                break
        scene.horizontal_key(event, -1, False)
        scene.set_key_state('down', False)
        self.assertIn((121, 89), seen)
        self.assertNotIn(47, [sequence for sequence, _x in seen])
        self.assertIn(122, [sequence for sequence, _x in seen])

    def test_a_crevice_uncovered_on_screen_is_redrawn_over_the_displayed_wall(self):
        # 7:344a marks the uncovered cells; RedrawCell (3:1d3a) repaints them
        # in per-cell mode over the screen. Ruins SHAP 3582 is its ceiling,
        # not a cavern torch frame: 7:2344 draws the newly uncovered front
        # over the old wall, before a later whole-room redraw.
        from PIL import Image

        scene = self.scene
        program = scene.level_renderer.cavern_program
        if 'redraws' not in program['loose_floors']['rooms']['17']:
            self.skipTest('Ruins export from before crevice redraws: reimport the game')

        def scenery(box):
            return Image.alpha_composite(scene.background, scene.foreground).crop(box).tobytes()

        above, inside = (0, 130, 40, 170), (0, 190, 40, 225)
        scene.jump_to_room(17, 1, 120, 0)
        self.tick(3)
        wall, covered = scenery(above), scenery(inside)
        scene.set_key_state('down', True)
        self.tick(10)
        scene.set_key_state('down', False)
        caverns = scene.game.caverns
        self.assertEqual(caverns.loose.redrawn, {(16, 18), (16, 19), (17, 10)})
        self.assertFalse(scenery(above) == wall)  # The native tunnel ceiling.
        self.assertFalse(scenery(inside) == covered)  # The tunnel is drawn.
        scene.jump_to_room(16, 1, 300, 0)
        self.tick()
        self.assertEqual(caverns.loose.redrawn, set())
        scene.jump_to_room(17, 1, 120, 0)
        self.tick()
        # Entering the room draws it whole, with the uncovered run's backdrop.
        self.assertFalse(scenery(above) == wall)

    def test_a_standing_prince_is_still_stopped_by_a_crevice(self):
        level_map = self.scene.level_map
        tile = level_map.tile(16, 8, 1)
        self.assertEqual((tile.kind, tile.foreground & 3 != 3), (7, True))
        x = 8 * 51 + 22 + 3 - 20
        standing = level_map.wall_correction(16, x - 10, x, (x - 20, 150, x + 20, 230), physical_row=1)
        self.assertLess(standing, x)
        prone = level_map.wall_correction(16, x - 10, x, (x - 20, 200, x + 20, 230), physical_row=1)
        self.assertEqual(prone, x)

    def test_an_upside_down_world_swaps_up_and_down_and_flips_the_view(self):
        # GenCtrl 4:3da6-3dcc (4:3e1c) and the drawing 2:5952-59de.
        from PIL import ImageOps

        scene = self.scene
        self.tick()
        scene.render()
        upright = scene.screenshot_viewport.crop((1, 0, 511, 365))
        potions = scene.game.caverns.potions
        potions.toggle_flip()
        scene.sync_flipped_controls()
        scene.set_key_state('up', True)
        self.assertTrue(scene.down_held)
        self.assertFalse(scene.up_held)
        scene.set_key_state('up', False)
        scene.render()
        flipped = scene.screenshot_viewport.crop((1, 0, 511, 365))
        from PIL import ImageChops

        # The cliff's animated sky may move between the two paints.
        difference = ImageChops.difference(ImageOps.flip(flipped).convert('RGB'), upright.convert('RGB'))
        changed = 510 * 365 - difference.convert('L').histogram()[0]
        self.assertLess(changed, 510 * 365 // 50)
        self.assertNotEqual(flipped.tobytes(), upright.tobytes())
        potions.toggle_flip()
        scene.sync_flipped_controls()
        scene.set_key_state('up', True)
        self.assertTrue(scene.up_held)
        scene.set_key_state('up', False)

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
class LevelSixScytheTests(unittest.TestCase):
    """5:57bc, TriggerScythe 5:5fde, AnimScythe 5:4584 and CheckScytheHit 5:588a."""

    def setUp(self):
        LevelSixSceneryTests.setUp(self)
        if 'scythes' not in self.scene.level_renderer.cavern_program:
            self.skipTest('Level-six import predates the scythes')

    def tick(self, count=1):
        LevelSixSceneryTests.tick(self, count)

    def test_running_into_a_scythe_starts_it_and_its_blade_cuts_the_prince(self):
        from types import SimpleNamespace

        scene = self.scene
        state, scythes = scene.sequence_state, scene.game.caverns.scythes
        scene.jump_to_room(18, 2, 200, 1)
        event = SimpleNamespace(keysym='Right', state=0)
        scene.horizontal_key(event, 1, True)
        sounds = []
        for _ in range(30):
            self.tick()
            sounds.extend(state.sound_events)
            if not scene.combat.player.alive:
                break
        scene.horizontal_key(event, 1, False)
        self.assertGreater(state.target_x, 5 * 51 + 28)
        self.assertEqual(state.selected_sequence_id, 113)
        self.assertEqual(scene.death.method, 5)
        self.assertIn(277, sounds)
        self.assertIn(278, sounds)
        self.assertEqual(scythes.foreground[18, 26] & 0x5f, 0x42)
        self.assertEqual(scythes.foreground[18, 25], scythes.foreground[18, 26])

    def test_a_started_scythe_runs_twenty_phases_and_keeps_its_blood(self):
        from pop2.scythes import Scythes

        terrain = self.scene.level_map
        scythes = self.scene.game.caverns.scythes = Scythes()
        terrain.caverns = self.scene.game.caverns
        scythes.active.add((18, 26))
        scythes.foreground = {(18, 26): 0x40, (18, 25): 0x40}
        sounds, values = [], []
        for _ in range(20):
            sounds.extend(scythes.advance(terrain))
            values.append(scythes.foreground[18, 26])
        self.assertEqual(values[0], 0x41)
        self.assertEqual(values[15], 0x50)
        self.assertEqual(values[16], 0xd1)  # 0x80 once the retracting blade is bloody
        self.assertEqual(values[18], 0xd3)
        self.assertEqual(values[19], 0xc0)
        self.assertEqual(sounds, [277, 276])
        self.assertEqual(scythes.active, set())

    def test_standing_short_of_the_scythe_column_edge_does_not_start_it(self):
        from types import SimpleNamespace

        scene = self.scene
        scythes = scene.game.caverns.scythes
        motion = SimpleNamespace(room=18, row=2)
        state = SimpleNamespace(actor_type=0, current_y=0, target_x=5 * 51 + 28)
        self.assertFalse(scythes.trigger(scene.level_map, motion, state))
        state.target_x += 1
        self.assertTrue(scythes.trigger(scene.level_map, motion, state))
        state.current_y = -31
        scythes.active.clear()
        self.assertFalse(scythes.trigger(scene.level_map, motion, state))

    def test_each_scythe_state_draws_its_exported_drawing(self):
        # Slot units (loose-floor schema 2) or, in older imports, patches.
        from types import SimpleNamespace
        from pop2.caverns import cavern_room, cavern_scythe_signature

        program = self.scene.level_renderer.cavern_program
        state = SimpleNamespace(scythes=SimpleNamespace(foreground={(18, 26): 8, (18, 25): 8}))
        signature = cavern_scythe_signature(program, 18, state)
        rest = cavern_room(18, animated=True, level_number=6)
        extended = cavern_room(18, animated=True, level_number=6, scythe_patch=signature)
        self.assertNotEqual(rest.background.tobytes(), extended.background.tobytes())


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

    def test_failed_sword_attempt_does_not_consume_held_shift(self):
        # TryPickUp 6:1350 checks the foot's cell and the cell ahead.
        # StandingCtrl 6:0c50 checks held Shift on each eligible pose.
        scene = self.scene
        scene.jump_to_room(16, 1, 228, 1)
        scene.start_sequence(13)
        scene.sequence_state.action = scene.action = 50
        scene.set_key_state('shift', True)
        self.assertFalse(scene.update_potion_controls())  # One pixel outside reach.
        scene.player_x = scene.sequence_state.target_x = 229
        self.assertTrue(scene.update_potion_controls())
        self.assertEqual(scene.sequence_state.sequence_id, 50)
        self.tick(12)
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

    def test_a_moving_bloody_scythe_survives_a_snapshot(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pop2.game_session import GameResources, GameSession
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        resources = GameResources.load()
        game = GameSession.load(resources, 6)
        game.caverns.scythes.foreground = {(18, 26): 0x45, (18, 25): 0x45}
        game.caverns.scythes.active = {(18, 26)}
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            write_save(path, capture_snapshot(game))
            loaded, _saved = read_snapshot(path, resources)
        self.assertEqual(loaded.caverns.scythes.foreground, {(18, 26): 0x45, (18, 25): 0x45})
        self.assertEqual(loaded.caverns.scythes.active, {(18, 26)})
        self.assertEqual(loaded.level_map.tile(18, 6, 2).foreground & 255, 0x45)



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
