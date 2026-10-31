import unittest

from pop2.paths import ASSET_DIR


TEMPLE_INSTALLED = all((ASSET_DIR / name).is_file()
                       for name in ('temple.json', 'temple_level10.json', 'Temple.rsrc'))


@unittest.skipUnless(TEMPLE_INSTALLED, 'Imported temple scene and scenery required')
class RideLastShotTests(unittest.TestCase):
    def test_the_ride_ends_on_level_ten_room_22_with_the_horse(self):
        # NISTemple 15:5fd4's last shot: DrawRoomFromNIS 2:03d4(10, 22), CTBL
        # 3500 at 64, then TransFunc8 (15:65d4) animates the horse and the
        # Prince (Kid.rsrc, mirrored by FlipKids/FlipKid) over the room.
        from pop2.caverns import room_indices
        from pop2.intro import IntroAssets, IntroPlayer

        assets = IntroAssets(program_name='temple.json')
        operations = assets.program['operations']
        shot = next(index for index, item in enumerate(operations) if item['op'] == 'game_room')
        self.assertEqual(operations[shot]['args'], [10, 22])
        drawn = {item['args'][0] for item in operations[shot:] if item['op'] == 'shape'}
        self.assertTrue(any(900000 < shape < 1000000 for shape in drawn))
        self.assertTrue(any(item['args'][3] & 256 for item in operations[shot:] if item['op'] == 'shape'))
        room = room_indices(10, 21).tobytes()

        def shown(player):
            pixels = player.display.crop((0, 0, 510, 365)).tobytes()
            return sum(a == b for a, b in zip(pixels, room)) / len(room)

        # The first frame shows the whole room (the horse covers a part).
        player = IntroPlayer(assets)
        player.seek_operation(shot)
        self.assertGreater(shown(player), 0.9)
        self.assertNotEqual(player.palette[64:80], [(0, 0, 0)] * 16)
        player.seek_operation(len(operations) - 1)
        self.assertTrue(player.done or player.position >= len(operations) - 1)
        self.assertGreater(shown(player), 0.9)


@unittest.skipUnless(TEMPLE_INSTALLED, 'Imported temple scene and scenery required')
class TempleSaveTests(unittest.TestCase):
    def test_level_ten_round_trips_through_a_save(self):
        from pathlib import Path
        import tempfile
        from pop2.game_session import GameResources, GameSession
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        resources = GameResources.load()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'temple.pop2save'
            original = GameSession.load(resources, 10)
            original.combat.player.life = 2
            original.caverns.rocks.bank.append((339, 356, 28, 0, -2, 6, 2, 459))
            write_save(path, capture_snapshot(original))
            restored, _saved = read_snapshot(path, resources)
        self.assertEqual((restored.level.number, restored.motion.room), (10, 21))
        self.assertEqual(vars(restored.runtime.state), vars(original.runtime.state))
        self.assertEqual(restored.combat.player.life, 2)
        self.assertEqual(restored.caverns.rocks.bank, [(339, 356, 28, 0, -2, 6, 2, 459)])
        self.assertIs(restored.level_map.caverns, restored.caverns)


@unittest.skipUnless(TEMPLE_INSTALLED, 'Imported temple scene and scenery required')
class LevelTenArrivalTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_level_ten_starts_beside_the_horse_and_walks(self):
        # SetKidDefaults 2:5dee-5e0e: native room 22, X 430, SEQS 2.
        from pop2.coordinates import scene_x

        scene = self.scene
        scene.enter_next_level(10)
        self.assertEqual((scene.game.level.number, scene.room_id), (10, 21))
        self.assertEqual(scene.sequence_state.source_sequence_id, 2)
        self.assertEqual(scene.player_x, scene_x(430))
        self.tick(20)
        self.assertTrue(scene.combat.player.alive)
        self.assertEqual(scene.game.level.number, 10)

    def test_temple_levels_use_the_temple_environment(self):
        # The cavern environment's exit would have started level one's
        # voyage (start_ending) after a temple level.
        from unittest.mock import patch
        from pop2.environments import Temple, environment_for

        scene = self.scene
        scene.enter_next_level(10)
        environment = environment_for(scene)
        self.assertIsInstance(environment, Temple)
        with patch.object(scene, 'start_ending') as ending,                 patch.object(environment, 'finish_via_story') as story:
            environment.finish_exit()
        ending.assert_not_called()
        story.assert_called_once_with(11)


    def test_every_temple_level_loads_and_walks(self):
        # LEVL 2010-2012 start rooms 5/19/3 (one-based) with SetKidDefaults'
        # ordinary standing entry (SEQS 5).
        scene = self.scene
        for number, room in ((11, 4), (12, 18), (13, 2)):
            if not (ASSET_DIR / f'temple_level{number}.json').is_file():
                continue
            with self.subTest(level=number):
                scene.enter_next_level(number)
                self.assertEqual((scene.game.level.number, scene.room_id), (number, room))
                self.assertEqual(scene.sequence_state.source_sequence_id, 5)
                self.tick(15)
                self.assertTrue(scene.combat.player.alive)


    def test_level_ten_plate_starts_the_sliding_rock_that_crushes_the_prince(self):
        # Native room 28: plate cell 24 (kind 6) links (61) to the rock marker
        # at cell 29. TriggerSlideRock 10:2152 creates it at control -2; it
        # slides two pixels per update; against the wall at column 3 the
        # Prince is crushed (10:1b04, control 100: pose 185). Before, the
        # plate chain ignored tile 25 and nothing moved.
        from pop2.coordinates import column_left

        scene = self.scene
        scene.enter_next_level(10)
        scene.jump_to_room(27, row=2, x=column_left(4) + 25, facing=0)
        rocks = scene.game.caverns.rocks
        self.tick(5)
        self.assertEqual(rocks.bank[0][2:], (28, 0, -2, 6, 2, 459))
        start = rocks.bank[0][0]
        self.tick(50)
        self.assertEqual(rocks.bank[0][0], start - 100)
        background = scene.native_viewport.crop((300, 250, 400, 340)).tobytes()
        self.tick(100)
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(rocks.bank[0][4], 100)
        self.assertEqual(scene.sequence_state.action, 185)
        self.assertNotEqual(scene.native_viewport.crop((300, 250, 400, 340)).tobytes(), background)


    def test_a_shaken_trap_door_opens_drops_the_prince_and_closes(self):
        # Level ten, native room 8 cell 25 (tile 26). ShakeEm 5:28c8 calls
        # TriggerTrapDoor 10:25aa: the floor is space at once; under the
        # Prince's column the door starts at phase 1 and closes after 16
        # presentations (tile 26 again, 10:2328), away from it at 75 (6).
        # Before, tile 26 was a plain floor and nothing opened.
        from pop2.coordinates import column_left

        scene = self.scene
        scene.enter_next_level(10)
        caverns, terrain = scene.game.caverns, scene.level_map
        scene.jump_to_room(7, row=2, x=column_left(1) + 25, facing=1)
        self.tick()
        state, motion = scene.sequence_state, scene.terrain_motion
        record = scene.frames[state.action]
        self.assertEqual(caverns.loose.shake_row(terrain, 7, 2, state, motion, record), (197,))
        self.assertEqual(terrain.tile(7, 5, 2).kind, 0)
        self.assertEqual(caverns.trapdoors.bank[0][7], 75)
        closed = scene.native_viewport.crop((250, 280, 360, 365)).tobytes()
        self.tick(2)
        # The door's animation piece (10:23d0 table) is drawn in the room.
        self.assertEqual([item[:2] for item in caverns.trapdoors.drawn], [(7, 3553)])
        self.assertNotEqual(scene.native_viewport.crop((250, 280, 360, 365)).tobytes(), closed)
        self.tick(4)
        self.assertEqual(terrain.tile(7, 5, 2).kind, 26)
        self.tick()
        self.assertEqual(caverns.trapdoors.bank, [])
        scene.jump_to_room(7, row=2, x=column_left(5) + 25, facing=1)
        self.tick()
        state, motion = scene.sequence_state, scene.terrain_motion
        caverns.loose.shake_row(terrain, 7, 2, state, motion, scene.frames[state.action])
        self.assertEqual(caverns.trapdoors.bank[0][7], 1)
        self.tick(8)
        self.assertTrue(scene.terrain_motion.falling or scene.room_id != 7 or scene.terrain_motion.row != 2)
        self.tick(12)
        self.assertEqual(terrain.tile(7, 5, 2).kind, 26)

    def test_level_ten_birdheads_are_ordinary_armed_opponents(self):
        # Opponent set 7: 6:2bca maps raw kind 7 to actor 2 and 3:5f58 loads
        # Birdhead.rsrc. Native room 10 has one (SEQS 77). Before, set 7 had
        # no opponents at all. Its SHAP 751 is LZ-packed (UnpackLZ 17:3aa8).
        from pop2.render_opening import decode_ctbl, decode_shap, load_resource_file

        scene = self.scene
        scene.enter_next_level(10)
        scene.jump_to_room(9, row=1, x=420, facing=0)
        guards = scene.combat.guards
        self.assertEqual([(guard.state.actor_type, guard.life, guard.state.target_x) for guard in guards],
                         [(2, 3, 302)])
        self.assertEqual(scene.combat.guard_art.base, 751)
        self.assertEqual(len(scene.combat.guard_art.frames), 108)
        birdhead = load_resource_file('Birdhead.rsrc')
        self.assertEqual(decode_shap(birdhead['SHAP'][751]['data'],
                                     decode_ctbl(birdhead['CTBL'][750]['data'])).size, (47, 72))
        # It engages and kills a Prince who does not defend himself.
        self.tick(60)
        self.assertTrue(guards[0].alive)
        self.assertFalse(scene.combat.player.alive)

@unittest.skipUnless(TEMPLE_INSTALLED, 'Imported temple scene and scenery required')
class TempleLooseFloorTests(unittest.TestCase):
    def test_a_falling_temple_floor_draws_pieces_28_and_29(self):
        # DrawObjLoose 3:4168: environment 2 draws pieces 28 and 29 at the
        # slab's bottom; the port drew the caverns' 3557/3604.
        from types import SimpleNamespace
        from PIL import Image
        from pop2.caverns import cavern_command_sprite, draw_cavern_falling, room_assets
        from pop2.game_session import GameResources
        from pop2.loose_floors import FallingFloor

        level = GameResources.load().level(10).data
        block = FallingFloor(21, 4, 1, 250)
        state = SimpleNamespace(loose=SimpleNamespace(falling=[block]))
        art = SimpleNamespace(draw_falling_foreground=lambda *args: None)
        frame = draw_cavern_falling(Image.new('RGBA', (510, 365)), 21, state, level, art, level_number=10)
        _program, resources, palette, shapes = room_assets(10, 21)
        expected = Image.new('RGBA', (510, 365))
        for index in (3528, 3529):
            sprite = cavern_command_sprite(['back', index, block.x, 250, 16], resources, palette, shapes)
            expected.paste(sprite, (block.x, 250 - sprite.height), sprite)
        self.assertEqual(frame.tobytes(), expected.tobytes())


@unittest.skipUnless((ASSET_DIR / 'temple_level13.json').is_file(), 'Imported level-13 scenery required')
class LevelThirteenFlameTests(unittest.TestCase):
    def test_room_four_draws_the_kid_file_flame(self):
        # CUST 4075 (native room 4) uses SHAP 4077-4091, found in Kid.rsrc
        # (the Resource Manager chain), not Temple.rsrc: the exporter marks
        # them library 5. Before, level 13 could not be exported.
        import json
        from pop2.caverns import cavern_room

        program = json.loads((ASSET_DIR / 'temple_level13.json').read_text(encoding='ascii'))
        flames = [command for command in program['rooms']['3'] if command[7:8] == [5]]
        self.assertEqual([command[1] for command in flames], [4077])
        room = cavern_room(3, level_number=13)
        x, bottom = flames[0][2:4]
        pixel = room.background.getpixel((x + 20, bottom - 40))
        self.assertGreater(pixel[2], pixel[0])  # Blue, not the magenta of a missing colour.


if __name__ == '__main__':
    unittest.main()
