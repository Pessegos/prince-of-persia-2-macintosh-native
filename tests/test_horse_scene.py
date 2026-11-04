import json
from pathlib import Path
import tempfile
import unittest

from pop2.paths import ASSET_DIR


class HorseImportCompatibilityTests(unittest.TestCase):
    def test_only_the_old_synthetic_gallop_wait_is_removed(self):
        from pop2.intro import read_program

        wait = {'op': 'cue', 'args': [97], 'pc': 0x615e}
        other_wait = {**wait, 'pc': 0x1234}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            for kind in ('temple', 'tower', 'carpet'):
                with self.subTest(kind=kind):
                    path.write_text(json.dumps({'schema': 1, 'kind': kind, 'audio': {},
                                                'operations': [wait, other_wait]}))
                    operations = read_program(path)['operations']
                    self.assertEqual(operations, [other_wait] if kind == 'temple'
                                     else [wait, other_wait])


HORSE_INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'temple.json', 'temple_level10.json', 'ruins_level9.json', 'Temple.rsrc'))


@unittest.skipUnless(HORSE_INSTALLED, 'Imported horse scene and scenery required')
class HorseSceneTests(unittest.TestCase):
    def test_the_gallop_cuts_to_the_canyon_without_waiting_on_empty_scenery(self):
        from pop2.intro import IntroAssets, IntroPlayer

        player = IntroPlayer(IntroAssets(program_name='temple.json'))
        player.advance(14)
        # Original ANI 25011/12: 64 + 76 frames, six ticks each.
        # The old synthetic cue held the empty desert until 23.2 seconds.
        self.assertGreaterEqual(player.operations[player.position - 1]['pc'], 0x61c2)
        self.assertGreater(max(player.frame().getpixel((x, 20))[0]
                               for x in range(70, 130)), 20)  # canyon's tower
        player.advance(30)
        self.assertTrue(player.done)
        self.assertGreater(player.time, 34)
        self.assertLess(player.time, 36)

    def test_the_status_strip_stays_black_through_every_animation_frame(self):
        from pop2.intro import IntroAssets, IntroPlayer, MAC_TICKS_PER_SECOND

        player = IntroPlayer(IntroAssets(program_name='temple.json'))
        while not player.done:
            with self.subTest(time=player.time):
                self.assertIsNone(player.frame().convert('RGB').crop((0, 365, 512, 384)).getbbox())
                self.assertIsNone(player.frame().convert('RGB').crop((510, 0, 512, 384)).getbbox())
            player.advance(6 / MAC_TICKS_PER_SECOND)

    def test_the_arrival_statue_survives_the_first_gameplay_frame(self):
        from pop2.caverns import cavern_room
        from pop2.intro import IntroAssets, IntroPlayer
        from pop2.render_opening import decode_ctbl, decode_shap, load_resource_file
        from pop2.scene_prototype import ROOM_ORIGIN_X
        from tests.test_terrain import RooftopSceneTests

        # Both NIS 2's final frame and gameplay use Prince SHAP 25360 with
        # CTBL 25361, at the a5-0x4af2 point (74,198), facing right.
        player = IntroPlayer(IntroAssets(program_name='temple.json'))
        player.advance(60)
        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.enter_next_level(10)
        resources = load_resource_file('Prince.rsrc')
        sprite = decode_shap(resources['SHAP'][25360]['data'],
                             decode_ctbl(resources['CTBL'][25361]['data']))
        x, y = 74, 198
        foreground = cavern_room(21, level_number=10).foreground
        visible = [(dx, dy) for dx in range(0, sprite.width, 3)
                   for dy in range(0, sprite.height, 3) if sprite.getpixel((dx, dy))[3]]
        self.assertTrue(visible)
        for dx, dy in visible:
            color = sprite.getpixel((dx, dy))
            point = x + dx, y + dy
            self.assertEqual(foreground.getpixel(point), color)
            self.assertEqual(scene.native_viewport.getpixel((point[0] + ROOM_ORIGIN_X, point[1])), color)
            self.assertEqual(player.frame().getpixel(point), color)
        RooftopSceneTests.tick(self, 10)
        self.assertTrue(scene.combat.player.alive)
        self.assertEqual(scene.game.level.number, 10)
        # DrawHorse's plane 1 also stays in front when the Prince returns
        # left and overlaps it; a static paste without an actor mask fails.
        scene.jump_to_room(21, 2, 130, 0)
        for dx, dy in visible:
            self.assertEqual(scene.native_viewport.getpixel((x + dx + ROOM_ORIGIN_X, y + dy)),
                             sprite.getpixel((dx, dy)))

    def test_the_column_leap_plays_the_real_scene_then_enters_level_ten(self):
        from unittest.mock import patch
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(9)
        scene.peaceful = True
        scene.jump_to_room(7, 0, 190, 0)
        scene.in_animation_tick = True
        scene.horizontal_key(None, -1, True)
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            for tick in range(21):
                if tick == 6:
                    scene.set_key_state('up', True)
                RooftopSceneTests.tick(self)
                if scene.intro is not None:
                    break
        self.assertIsNotNone(scene.intro)
        self.assertEqual(scene.intro.program_kind, 'temple')
        self.assertEqual(scene.sequence_state.action, 41)
        self.assertEqual(scene.room_id, 7)
        scene.intro.advance(60)
        self.assertTrue(scene.intro.done)
        scene.finish_tree()
        self.assertEqual((scene.game.level.number, scene.room_id), (10, 21))
        self.assertIsNone(scene.intro)
        self.assertTrue(scene.combat.player.alive)


if __name__ == '__main__':
    unittest.main()
