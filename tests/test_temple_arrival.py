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


if __name__ == '__main__':
    unittest.main()
