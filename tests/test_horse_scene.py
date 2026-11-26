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
    def test_interior_reveals_every_palette_with_the_existing_fade_cadence(self):
        from pop2.intro import IntroAssets, IntroPlayer, fade_ticks, MAC_TICKS_PER_SECOND

        player = IntroPlayer(IntroAssets(program_name='temple.json'))
        reveals = [i for i, item in enumerate(player.operations) if item['op'] == 'fade_in_all']
        self.assertEqual(len(reveals), 1)
        reveal = reveals[0]
        player.seek_operation(reveal)
        start = player.time
        self.assertIsNone(player.frame().convert('RGB').getbbox())
        _kind, _start, duration, _source, colors = player.transition
        self.assertAlmostEqual(duration, fade_ticks(0x40001) / MAC_TICKS_PER_SECOND)
        first_pose = player.target.tobytes()
        player.advance(duration / 2)
        self.assertNotEqual(player.target.tobytes(), first_pose)
        # Fade the temple, horse and Prince together, including palettes
        # set directly by game_room/palette_at rather than loaded tables.
        for index, color in colors.items():
            for actual, full in zip(player.palette[index], color):
                self.assertLessEqual(abs(actual - full / 2), .51)
        self.assertIsNotNone(player.frame().convert('RGB').getbbox())
        player.advance(duration / 2)
        self.assertIsNone(player.transition)
        self.assertEqual(player.palette, list(colors.values()))
        self.assertAlmostEqual(player.time, start + duration)
        player.advance(60)
        self.assertAlmostEqual(player.time, 34.465319, places=6)

    def test_templ2_leads_takeoff_by_335ms_without_moving_picture_frames(self):
        from unittest.mock import Mock, call
        from pop2.intro import IntroAssets, IntroPlayer, MAC_TICKS_PER_SECOND

        audio = Mock()
        player = IntroPlayer(IntroAssets(program_name='temple.json'), audio)
        # ANI25011/12 have64/76 frames, then33 approach frames in25013,
        # all six native ticks. Frame34's picture deadline must stay fixed.
        takeoff = (64 + 76 + 33) * 6 / MAC_TICKS_PER_SECOND
        # The user requested another15 video frames beyond the prior85ms.
        start = takeoff - (.085 + 15 / 60)
        player.advance(start - .000001)
        self.assertNotIn(call(25006, 0), audio.play_intro.call_args_list)
        approach = player.frame().tobytes()
        player.advance(.000001)
        self.assertEqual(audio.play_intro.call_args_list.count(call(25006, 0)), 1)
        self.assertAlmostEqual(player.playing[0][1], start)
        self.assertEqual(player.frame().tobytes(), approach)
        # Later approach frames still advance on their original deadlines.
        last_approach = takeoff - 6 / MAC_TICKS_PER_SECOND
        player.advance(last_approach - player.time)
        approach = player.frame().tobytes()
        player.advance(6 / MAC_TICKS_PER_SECOND - .000001)
        self.assertEqual(player.frame().tobytes(), approach)
        player.advance(.000001)
        self.assertNotEqual(player.frame().tobytes(), approach)
        player.advance(60)
        self.assertTrue(player.done)
        self.assertEqual(audio.play_intro.call_args_list.count(call(25006, 0)), 1)
        self.assertNotIn(call(292, 0), audio.play_intro.call_args_list)
        self.assertAlmostEqual(player.time, 34.465319, places=6)

    def test_the_distant_rider_disappears_behind_the_marked_door_jamb(self):
        from PIL import ImageChops
        from pop2.intro import IntroAssets, IntroPlayer

        player = IntroPlayer(IntroAssets(program_name='temple.json'))
        counts, frames = [], 0
        while not player.done:
            item = player.operations[player.position - 1]
            if item['op'] == 'wait' and item.get('pc') == 0x6318:
                frames += 1
                difference = ImageChops.difference(player.target, player.background)
                with self.subTest(frame=frames):
                    self.assertIsNone(difference.crop((362, 0, 510, 365)).getbbox())
                # Count the visible rider on the bridge; he must disappear
                # progressively at the jamb, leaving the doorway unchanged.
                counts.append(sum(value != 0 for value in difference.crop(
                    (330, 220, 362, 275)).tobytes()))
            player.advance(max(0, player.wait_until - player.time))
        self.assertEqual(frames, 94)
        self.assertGreater(max(counts), 20)
        self.assertEqual(counts[-1], 0)
        self.assertGreater(len(set(counts[-15:])), 3)

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

    def test_desert_wind_moves_in_the_three_desert_shots_and_stays_behind_the_rider(self):
        import numpy as np
        from pop2.horse_desert import HORSE_GALLOP_BACKDROP, HORSE_GORGE_BACKDROP, HORSE_STATUE_BACKDROP
        from pop2.intro import IntroAssets, IntroPlayer, TEMPLE_EXTERIOR

        assets = IntroAssets(program_name='temple.json')
        ambience = True
        player = IntroPlayer(assets, ambience=lambda: ambience)
        clear = IntroPlayer(assets)
        display, revision = player.display.tobytes(), player.revision
        player.advance(1 / 12)
        self.assertGreater(player.revision, revision)
        self.assertEqual(player.display.tobytes(), display)

        shots = ((0.5, HORSE_STATUE_BACKDROP), (10.5, HORSE_GALLOP_BACKDROP), (12.3, HORSE_GALLOP_BACKDROP),
                 (14.5, HORSE_GORGE_BACKDROP), (17.4, HORSE_GORGE_BACKDROP), (24, TEMPLE_EXTERIOR), (32, None))
        for time, backdrop in shots:
            with self.subTest(time=time):
                player.advance(time - player.time)
                clear.advance(time - clear.time)
                self.assertEqual(player.horse_backdrop, backdrop)
                self.assertEqual((player.position, player.wait_until, player.playing, player.palette),
                                 (clear.position, clear.wait_until, clear.playing, clear.palette))
                self.assertEqual(player.display.tobytes(), clear.display.tobytes())
                difference = np.any(np.asarray(player.frame()) != np.asarray(clear.frame()), axis=2)
                self.assertFalse(difference[365:].any())
                self.assertFalse(difference[:, 510:].any())
                difference[:200] = False  # Fixed stars belong to the sky.
                self.assertEqual(difference.any(), backdrop not in (TEMPLE_EXTERIOR, None))
                if backdrop == HORSE_GALLOP_BACKDROP:
                    rider_and_rocks = np.asarray(player.horse_covered) > 0
                    self.assertTrue(rider_and_rocks[210:330].any())
                    self.assertFalse((difference & rider_and_rocks).any())
                elif backdrop == HORSE_GORGE_BACKDROP:
                    self.assertTrue(difference[211:, :172].any())     # Crosswind and falls on the left bank.
                    self.assertTrue(difference[220:, 305:345].any())  # Updraft and sand inside the gorge.
                ambience = False
                self.assertEqual(player.frame().tobytes(), clear.frame().tobytes())
                ambience = True

    def test_the_viewer_uses_the_same_desert_wind_when_replaying_the_ride(self):
        from pop2.cutscene_viewer import CHAPTER_BY_KEY, chapter_player
        from pop2.intro import IntroAssets, IntroPlayer

        assets = IntroAssets(program_name='temple.json')
        ambience = False
        replay = chapter_player(CHAPTER_BY_KEY['horse'], assets, ambience=lambda: ambience)
        live = IntroPlayer(assets, ambience=lambda: True)
        replay.advance(12)
        live.advance(12)
        quiet = replay.frame().crop((0, 200, 510, 365)).tobytes()
        ambience = True
        windy = replay.frame().crop((0, 200, 510, 365)).tobytes()
        self.assertNotEqual(quiet, windy)
        self.assertEqual(windy, live.frame().crop((0, 200, 510, 365)).tobytes())

    def test_the_exterior_shots_share_the_horse_room_stars_when_ambience_is_on(self):
        from unittest.mock import patch

        from PIL import ImageChops
        from pop2.caverns import cavern_room
        from pop2.intro import HORSE_SKY_PALETTES
        from pop2.ruins_ambience import HORSE_ROOM, ruins_air
        from tools.audit_temple_routes import Harness

        h = Harness(9, draw=True, god=True)
        try:
            scene = h.scene
            scene.audio = None
            scene.cave_ambience_enabled = True
            assets = scene.story_scene_assets['temple.json']
            self.assertTrue(assets.horse_stars)
            with patch('pop2.caverns.cavern_room', side_effect=AssertionError('Horse sky must already be prepared')):
                self.assertTrue(scene.start_temple_ride(lambda keep_music=False: None))
                player = scene.intro
                lit = player.frame()
            air = ruins_air(9, HORSE_ROOM, cavern_room(HORSE_ROOM, level_number=9, retouched=True))
            for x, y, kind in air.stars:
                self.assertEqual(lit.getpixel((x, y)), air.inks[kind.steps[-1]])

            for delta in (1, 7, 8, 8):
                player.advance(delta)
                lit = player.frame()
                scene.cave_ambience_enabled = False
                clear = player.frame()
                scene.cave_ambience_enabled = True
                sky, points = player.assets.horse_stars[HORSE_SKY_PALETTES[player.horse_backdrop]]
                self.assertTrue(any(lit.getpixel((x, y)) != clear.getpixel((x, y)) for x, y, _ in points))
                for x, y, _ in points:
                    if player.display.getpixel((x, y)) not in sky:
                        self.assertEqual(lit.getpixel((x, y)), clear.getpixel((x, y)))

            player.advance(60)
            lit = player.frame()
            scene.cave_ambience_enabled = False
            self.assertIsNone(ImageChops.difference(lit.convert('RGB'), player.frame().convert('RGB')).getbbox())
        finally:
            h.close()

    def test_the_temple_exterior_has_lilac_rose_and_gold_stars_that_follow_the_fade(self):
        from pop2.intro import IntroAssets, IntroPlayer, TEMPLE_EXTERIOR

        player = IntroPlayer(IntroAssets(program_name='temple.json'), ambience=lambda: True)
        exterior = next(i for i, item in enumerate(player.operations)
                        if item['op'] == 'shape' and item['args'][0] == TEMPLE_EXTERIOR)
        fade = next(i for i in range(exterior, len(player.operations))
                    if player.operations[i]['op'] == 'fade_in_both')
        player.advance(60, stop_position=fade)
        player.advance(0)
        duration = player.transition[2]
        player.advance(duration / 2)
        halfway = player.frame()
        player.advance(duration / 2)
        full = player.frame()
        sky, points = player.assets.horse_stars[TEMPLE_EXTERIOR]
        self.assertGreaterEqual(len(points), 5)
        colours = []
        for x, y, index in points:
            self.assertIn(player.display.getpixel((x, y)), sky)
            colour = full.getpixel((x, y))[:3]
            self.assertEqual(colour, player.palette[index])
            self.assertLess(sum(halfway.getpixel((x, y))[:3]), sum(colour))
            self.assertGreater(sum(halfway.getpixel((x, y))[:3]), 0)
            colours.append(colour)
        self.assertTrue(any(blue > red > 90 for red, green, blue in colours))
        self.assertTrue(any(red > blue > green for red, green, blue in colours))
        self.assertTrue(any(red > green > blue and red > 180 for red, green, blue in colours))

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
        from unittest.mock import Mock, patch

        from PIL import ImageChops
        from pop2.ruins_ambience import horse_shooting_star
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(9)
        prepared = scene.story_scene_assets['temple.json']
        scene.peaceful = True
        scene.cave_ambience_enabled = True
        scene.jump_to_screen('Room 8')
        scene.in_animation_tick = True
        scene.horizontal_key(None, -1, True)
        scene.audio = Mock()
        scene.audio.death_ready.return_value = False  # A jump effect is still playing.
        with (patch.object(scene, 'render'), patch.object(scene, 'advance_audio'),
              patch('pop2.intro.IntroAssets', side_effect=AssertionError('Loading during the leap'))):
            for tick in range(21):
                if tick == 6:
                    scene.set_key_state('up', True)
                RooftopSceneTests.tick(self)
                if scene.intro is not None:
                    break
                self.assertFalse(scene.level_complete, 'The jump pose must not wait an extra tick')
        self.assertIsNotNone(scene.intro)
        self.assertEqual(scene.intro.program_kind, 'temple')
        self.assertIs(scene.intro.assets, prepared)
        scene.audio.death_ready.assert_not_called()
        self.assertEqual(scene.sequence_state.action, 41)
        self.assertEqual(scene.room_id, 7)
        self.assertFalse(scene.level_renderer.horse_star_seen)

        player = scene.intro
        meteor = horse_shooting_star()
        samples = ((0.99, None), (1, 0), (1 + 1 / 12, 1), (1.25, 3), (4, 36), (6.5, None), (8, None))
        for time, age in samples:
            with self.subTest(time=time):
                revision = player.revision
                player.advance(time - player.time)
                with_star = player.frame().convert('RGB')
                scene.cave_ambience_enabled = False
                without = player.frame().convert('RGB')
                scene.cave_ambience_enabled = True
                # Both versions differ at the fixed stars. Compare only the
                # region swept by the meteor, below the opening stars.
                difference = ImageChops.difference(with_star, without).crop((130, 12, 386, 64))
                if age is None:
                    self.assertIsNone(difference.getbbox())
                else:
                    self.assertIsNotNone(difference.getbbox())
                    self.assertGreater(player.revision, revision)
                    if age < meteor.kind.ticks:
                        head = meteor.at(age * meteor.kind.speed)
                        self.assertNotEqual(with_star.getpixel(head), without.getpixel(head))
        scene.intro.advance(60)
        self.assertTrue(scene.intro.done)
        scene.finish_tree()
        self.assertEqual((scene.game.level.number, scene.room_id), (10, 21))
        self.assertIsNone(scene.intro)
        self.assertTrue(scene.combat.player.alive)

    def test_the_shooting_star_does_not_repeat_after_a_playable_visit(self):
        from PIL import ImageChops
        from pop2.intro import IntroPlayer
        from pop2.ruins_ambience import HORSE_ROOM, HORSE_STAR_DELAY_TICKS
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(9)
        scene.audio = None
        scene.peaceful = True
        scene.cave_ambience_enabled = True
        scene.jump_to_room(HORSE_ROOM, 2, 350, 0)
        RooftopSceneTests.tick(self, HORSE_STAR_DELAY_TICKS + 1)
        self.assertTrue(scene.level_renderer.horse_star_seen)
        self.assertTrue(scene.start_temple_ride(lambda: None))
        player = scene.intro
        replay = IntroPlayer(player.assets, ambience=lambda: True)
        for time in (1, 1.25, 2.5):
            player.advance(time - player.time)
            replay.advance(time - replay.time)
            self.assertIsNone(ImageChops.difference(player.frame().convert('RGB'),
                                                    replay.frame().convert('RGB')).getbbox())


if __name__ == '__main__':
    unittest.main()
