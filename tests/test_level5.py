import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class CeilingBarsSceneTests(unittest.TestCase):
    """Room 3's plate (cell 8, link 17) and ceiling bars (cell 6, tile 27)."""

    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)
        self.tick(16)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_export_draws_the_closed_bars_and_records_both_pressure_slots(self):
        from pop2.caverns import cavern_assets

        program = cavern_assets(5)[0]
        bars = [command for command in program['rooms']['2'] if command[1] == 4051]
        self.assertEqual(bars, [['back', 4051, 165, 50, 0, 0, [10, 165, 50, 318], 4, 6, 0]])
        records = program['pressure_plates']['rooms']['2']
        self.assertEqual([(record['cell'], record['kind']) for record in records], [(6, 27), (8, 34)])

    def test_stepping_on_the_upper_right_plate_opens_the_bars(self):
        scene = self.scene
        self.assertEqual(scene.level_map.tile(2, 6, 0).kind, 27)
        scene.jump_to_room(2, 0, 445, 1)
        self.tick(12)
        self.assertEqual(scene.level_map.tile(2, 6, 0).foreground & 7, 3)
        from pop2.caverns import cavern_pressure_signature

        program = scene.level_renderer.cavern_program
        self.assertEqual(cavern_pressure_signature(program, 2, scene.game.caverns)[0], 3)


class CarpetTests(unittest.TestCase):
    """Sitting 8:13a8, frame selection 8:11e4 and SetupCarpet 8:12b6."""

    def test_first_ride_frame_starts_the_carpet_and_low_closed_bars_crash_it(self):
        from pop2.carpet import CRASH_SOUND, Carpet

        carpet = Carpet()
        self.assertEqual(carpet.sit(346, False), (None, False, False))
        self.assertEqual(carpet.counter, 1)
        self.assertEqual(carpet.sit(100, False), (None, False, False))
        self.assertEqual(carpet.sit(99, True), (None, False, False))
        self.assertEqual(carpet.sit(99, False), (CRASH_SOUND, True, False))
        self.assertEqual((carpet.counter, carpet.crashed), (1, True))
        self.assertEqual(carpet.sit(39, False), (None, False, True))

    def test_frames_unfold_then_wave_and_a_crash_shows_the_underside(self):
        from pop2.carpet import Carpet

        carpet = Carpet()
        frames = []
        for counter in range(1, 16):
            carpet.counter = counter
            frames.append(carpet.frame())
        self.assertEqual(frames, [1, 2, 3, 4, 5, 6, 7, 8, 6, 7, 8, 3, 4, 5, 6])
        carpet.crashed, carpet.counter = True, 1
        self.assertEqual(carpet.frame(), 9)
        carpet.counter = 5
        self.assertEqual(carpet.drawing(218, 39, 0), (25318, 218 - 69, 39 + 8))
        self.assertEqual(Carpet().sit_x(1), 248)

    def test_counter_only_runs_once_the_carpet_is_used(self):
        from pop2.carpet import Carpet

        carpet = Carpet()
        carpet.advance()
        self.assertEqual(carpet.counter, 0)
        carpet.counter = 3
        carpet.advance()
        self.assertEqual(carpet.counter, 4)


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class CarpetRideSceneTests(unittest.TestCase):
    def setUp(self):
        CeilingBarsSceneTests.setUp(self)

    def tick(self, count=1):
        CeilingBarsSceneTests.tick(self, count)

    def ride(self, bars_open):
        scene = self.scene
        if bars_open:
            scene.game.caverns.plates.foreground[2, 6] = 3
        scene.jump_to_room(2, 2, 200, 0)
        self.tick(3)
        # Crouching (frame 109) on carpet cell 23 sits down (GenCtrl 6:09b4).
        scene.physics.select(scene.sequence_runtime, 50)
        for _ in range(60):
            self.tick()
            if scene.game.caverns.carpet.crashed or scene.game.complete:
                break
        return scene

    def test_open_bars_let_the_carpet_carry_the_prince_out_of_level_five(self):
        scene = self.ride(True)
        self.assertTrue(scene.game.complete)
        self.assertTrue(scene.combat.player.alive)
        self.assertEqual(scene.sequence_state.target_x, 218)

    def test_closed_bars_crush_the_rising_prince(self):
        scene = self.ride(False)
        self.assertTrue(scene.game.caverns.carpet.crashed)
        self.tick(2)
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(scene.sequence_state.sequence_mode, 10)
        self.assertEqual(scene.death.method, 9)
        self.tick(10)
        self.assertGreater(scene.death.counter, 6)


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class CarpetRoomPaletteTests(unittest.TestCase):
    def test_room_three_uses_ctbl_3501_and_other_rooms_keep_3500(self):
        # CheckCarpetImg 8:0d30 is room 3's CUST enter hook (kind 0).
        from pop2.caverns import cavern_assets, room_assets
        from pop2.render_opening import decode_ctbl

        _program, resources, palette, _shapes = cavern_assets(5)
        alternate = decode_ctbl(resources['CTBL'][3501]['data'])
        room_palette = room_assets(5, 2)[2]
        self.assertTrue(all(room_palette[index] == color for index, color in alternate.items()))
        self.assertNotEqual(room_palette, palette)
        self.assertIs(room_assets(5, 9)[2], palette)
        self.assertIs(room_assets(4, 2)[2], cavern_assets(4)[2])

    def test_carpet_entries_16_to_31_repeat_the_cavern_prince_palette(self):
        from pop2.caverns import carpet_palette
        from pop2.render_opening import decode_ctbl, load_resource_file

        kid = decode_ctbl(load_resource_file('Kid.rsrc')['CTBL'][25003]['data'])
        palette = carpet_palette()
        self.assertEqual([palette[index + 15] for index in range(1, 17)],
                         [kid[index] for index in range(1, 17)])
        # Emulator capture of the unused carpet: index 16 is orange, 30 blue.
        self.assertEqual((palette[16][:3], palette[30][:3]), ((220, 92, 17), (45, 46, 182)))

    def test_room_three_hides_the_left_rooms_last_column(self):
        # 5:0bbc-0be2 marks the left neighbour column 0xc000 in a CUST room.
        from pop2.caverns import cavern_assets

        commands = cavern_assets(5)[0]['rooms']['2']
        self.assertFalse([command for command in commands
                          if command[1] in (3513, 3527, 3532) and command[8:10] == [0, 1]])


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class RoomSevenGateSongTests(unittest.TestCase):
    """AddGateSound 5:3828-388e: BrgDoor (120) when room 7's gate slams."""

    def setUp(self):
        CeilingBarsSceneTests.setUp(self)

    def tick(self, count=1):
        CeilingBarsSceneTests.tick(self, count)

    def slam(self, room, x):
        scene = self.scene
        scene.jump_to_room(room, 1, x, 0)
        caverns = scene.game.caverns
        caverns.plates.songs.clear()
        caverns.plates.slam_sounds.append((6, 13))
        scene.advance_relief(caverns)
        return list(caverns.plates.songs)

    def test_slam_plays_brgdoor_unless_the_prince_is_at_room_sevens_left_edge(self):
        self.assertEqual(self.slam(9, 255), [120])
        self.assertEqual(self.slam(6, 40), [])
