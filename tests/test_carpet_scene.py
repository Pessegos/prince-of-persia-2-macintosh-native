import unittest

from pop2.paths import ASSET_DIR


class CarpetExportTests(unittest.TestCase):
    def test_flag_eight_animations_restore_the_background_under_moved_layers(self):
        # PlayTheAnimation 16:121c and 16:1378-13bc.
        import struct
        from tools.extract_intro import expand_animations

        body = (bytes((5, 6)) + struct.pack('>2h', 1, 1) + bytes((1, 2))
                + bytes((6, 8)) + struct.pack('>3h', 1, 3, 0) + bytes((1, 2)) + bytes((0, 2)))
        script = struct.pack('>I', len(body)) + body
        resources = {'ANI ': {100001: {'data': struct.pack('>9h', 0, 0, 10, 10, 1, 7, 0, 0, 0)}},
                     'SCRP': {100007: {'data': script}},
                     'SHAP': {100001: {'data': struct.pack('>HhhH', 0, 0, 4, 3)}}}
        operations = [{'op': 'animation', 'args': [100000, 1, 5, 6], 'pc': 0, 'flags': 0x1c}]
        result = expand_animations(operations, resources)
        self.assertEqual([(item['op'], item['args']) for item in result], [
            ('save_background', []),
            ('shape', [100001, 5, 6, 16]), ('copy', [[6, 5, 9, 9]]), ('wait', [3]),
            ('restore', [[6, 5, 9, 9]]), ('shape', [100001, 8, 6, 16]),
            ('copy', [[6, 5, 9, 9]]), ('copy', [[6, 8, 9, 12]]), ('wait', [3])])


class KidPaletteTests(unittest.TestCase):
    def test_kid_colours_are_renumbered_from_the_given_entry(self):
        # PoPSetPalette 3:508a -> RemapCTBL 17:6a78: entries become 16, 17, ...
        # The Kid CTBLs store indices 1-16, so entry 1 lands at 16, not 17.
        from types import SimpleNamespace
        from pop2.intro import IntroPlayer

        player = IntroPlayer.__new__(IntroPlayer)
        player.assets = SimpleNamespace(kid_palettes={25004: {1: (1, 1, 1), 2: (2, 2, 2), 16: (16, 16, 16)}})
        player.palette = [(0, 0, 0)] * 256
        player.changed = lambda: None
        player.execute('palette_at', [25004, 16])
        self.assertEqual(player.palette[15:19], [(0, 0, 0), (1, 1, 1), (2, 2, 2), (16, 16, 16)])
        player.assets.kid_palettes[1] = {16: (5, 5, 5), 17: (6, 6, 6)}
        player.execute('palette_at', [1, 16])
        self.assertEqual(player.palette[16:18], [(5, 5, 5), (6, 6, 6)])


class CarriedMusicTests(unittest.TestCase):
    def test_a_carried_song_paces_the_scene_cues_and_otherwise_they_pass(self):
        # 16:26d0 waits for the marker of the music still playing (FlyinRug
        # after level five) and returns at once without music.
        from types import SimpleNamespace
        from pop2.intro import IntroPlayer

        program = {'operations': [{'op': 'cue', 'args': [97]}, {'op': 'wait', 'args': [60]}],
                   'audio': {}, 'resource_files': {}}
        assets = SimpleNamespace(program=program)
        song = {'duration': 52.6, 'markers': {'a': 6.86}, 'kind': 0}
        player = IntroPlayer(assets, music=(115, 2.0, song))
        self.assertEqual(player.position, 1)
        self.assertAlmostEqual(player.wait_until, 4.86)
        silent = IntroPlayer(assets)
        self.assertEqual(silent.position, 2)
        self.assertLess(silent.wait_until, 1.01)


class AnimatedFadeTests(unittest.TestCase):
    """QoL: the carpet scene keeps drawing through its fades (the Mac freezes)."""

    def program(self, carpet=True):
        from types import SimpleNamespace

        operations = [{'op': 'fade', 'args': [1, True, 0x40001]},
                      {'op': 'copy', 'args': [[0, 0, 10, 10]]}, {'op': 'wait', 'args': [6]},
                      {'op': 'copy', 'args': [[0, 0, 10, 10]]}, {'op': 'wait', 'args': [30]},
                      {'op': 'copy', 'args': [[0, 0, 10, 10]]}, {'op': 'wait', 'args': [6]},
                      {'op': 'fade', 'args': [1, False, 0x40001]}, {'op': 'palette', 'args': [1, 66, 1]}]
        program = {'operations': operations, 'audio': {}}
        if carpet:
            program['resource_files'] = {}
        return SimpleNamespace(program=program, palettes={1: {64: (200, 100, 50)}})

    def test_fade_outs_start_their_duration_before_the_mac_fade(self):
        from pop2.intro import MAC_TICKS_PER_SECOND, animated_fade_outs, fade_ticks

        duration = fade_ticks(0x40001) / MAC_TICKS_PER_SECOND
        plan = animated_fade_outs(self.program().program['operations'])
        self.assertEqual(list(plan), [4])
        fade, offset = plan[4]
        self.assertEqual(fade, 7)
        self.assertAlmostEqual(offset, 36 / MAC_TICKS_PER_SECOND - duration)

    def test_drawing_continues_through_fade_in_and_fade_out(self):
        from pop2.intro import IntroPlayer, MAC_TICKS_PER_SECOND

        player = IntroPlayer(self.program())
        # The fade-in does not block: the first wait already runs.
        self.assertEqual(player.position, 3)
        self.assertEqual(player.transition[0], 'fade')
        player.advance(0.2)
        self.assertGreater(player.palette[64][0], 0)
        self.assertLess(player.palette[64][0], 200)
        # The fade-out starts while the last waits still run and ends at its step.
        player.advance(36 / MAC_TICKS_PER_SECOND - 0.2 + 0.05)
        self.assertLess(player.position, 8)
        self.assertEqual(player.transition[0], 'fade')
        player.advance(1)
        self.assertEqual(player.palette[64], (200, 100, 50))  # the palette step after it
        self.assertTrue(player.done)

    def test_other_scenes_keep_the_blocking_mac_fades(self):
        from pop2.intro import IntroPlayer

        player = IntroPlayer(self.program(carpet=False))
        self.assertEqual(player.position, 1)
        self.assertGreater(player.wait_until, 0.4)


@unittest.skipUnless((ASSET_DIR / 'carpet.json').is_file(), 'Imported carpet scene required')
class CarpetSceneTests(unittest.TestCase):
    def test_the_scene_flies_over_the_sea_and_lands_on_the_cliff(self):
        from pop2.intro import IntroAssets, IntroPlayer

        assets = IntroAssets(program_name='carpet.json')
        self.assertEqual(set(assets.program['resource_files']),
                         {'TNIS1.rsrc', 'TNIS2.rsrc', 'TNIS3.rsrc', 'Ruins.rsrc', 'Caverns.rsrc'})
        player = IntroPlayer(assets)
        player.advance(60)
        self.assertTrue(player.done)
        self.assertGreater(player.time, 20)
        ops = [item['op'] for item in assets.program['operations']]
        self.assertIn('palette_at', ops)
        # The last screen's sprites use TNIS3's copy of the Kid colours at 16-31.
        kid = list(assets.kid_palettes[25004].values())
        self.assertEqual(player.palette[16:16 + len(kid)], kid)
        self.assertEqual(ops.count('save_background'), 3)

    def test_flyinrug_plays_on_into_the_scene_and_paces_its_cues(self):
        # 2:61ce-61ea: no ResetSoundItem after level five.
        from unittest.mock import Mock
        from pop2.intro import game_song
        from tests.test_terrain import RooftopSceneTests

        song = game_song(115)
        self.assertEqual(sorted(song['markers']), ['a', 'b', 'c'])
        self.assertAlmostEqual(song['markers']['a'], 6.857, places=2)
        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(5)
        scene.audio = Mock(current_music=115)
        scene.audio.music_elapsed.return_value = 3.0
        scene.start_carpet()
        scene.audio.reset.assert_not_called()
        self.assertEqual(scene.intro.playing[0][:2], (115, -3.0))
        # The first screen's cue (operation 59) waits for marker a.
        scene.intro.advance(3.8)
        self.assertEqual(scene.intro.position, 60)
        self.assertAlmostEqual(scene.intro.wait_until, song['markers']['a'] - 3.0)
        # ... and on into level six when the scene ends.
        scene.next_level_after_tree = 6
        scene.finish_tree()
        self.assertEqual(scene.game.level.number, 6)
        scene.audio.reset.assert_called_once_with(keep_music=True)
        scene.load_level(5)
        scene.audio = Mock(current_music=114)
        scene.audio.music_elapsed.return_value = 3.0
        scene.start_carpet()
        scene.audio.reset.assert_called_once_with()
        self.assertNotIn(0, scene.intro.playing)
        scene.next_level_after_tree = 6
        scene.finish_tree()
        scene.audio.reset.assert_called_with(keep_music=False)
        scene.audio = None

    def test_finishing_level_five_plays_the_carpet_scene_then_loads_level_six(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(5)
        scene.finish_level_via_story(5, 6)
        self.assertEqual((scene.attract_stage, scene.next_level_after_tree), ('tree', 6))
        self.assertIs(scene.intro.assets, scene.carpet_assets)
        scene.finish_tree()
        self.assertEqual(scene.game.level.number, 6)
        self.assertIsNone(scene.intro)


if __name__ == '__main__':
    unittest.main()


class ThroneVisionPlayerTests(unittest.TestCase):
    """The operations of NIS 6 (15:66f4), the vision at the throne."""

    def player(self, operations, **options):
        from types import SimpleNamespace
        from PIL import Image
        from pop2.intro import IntroPlayer

        shape = Image.new('L', (3, 2), 7)
        shape.putpixel((0, 0), 9)
        program = {'kind': 'throne', 'prince': [457, 313], 'audio': {},
                   'variants': {'0': operations, '-1': operations}, 'operations': operations}
        assets = SimpleNamespace(program=program, shapes={1: shape},
                                 palettes={5: {1: (10, 10, 10), 2: (20, 20, 20)}, 6: {3: (30, 30, 30)}})
        return IntroPlayer(assets, variant=0, **options)

    def test_palette_entries_tables_and_combination(self):
        player = self.player([
            {'op': 'rgb', 'args': [1, 255, 90, 0]},
            {'op': 'set_palette', 'args': [5, 240]},
            {'op': 'palette', 'args': [5, 1, 0]}, {'op': 'palette', 'args': [6, 2, 0]},
            {'op': 'remap', 'args': [1, 16]}, {'op': 'remap', 'args': [2, 240]},
            {'op': 'combine', 'args': []}, {'op': 'brightness', 'args': [0x51, 100]}])
        # ShowNthvRGB 17:130e, PoPSetPalette/RemapCTBL, CombineCtabs 17:1520.
        self.assertEqual(player.palette[1], (255, 90, 0))
        # PoPSetPalette put 5 at 240; the combined table then shows 6 there.
        self.assertEqual(player.palette[240:242], [(30, 30, 30), (20, 20, 20)])
        self.assertEqual(player.palette[16:18], [(10, 10, 10), (20, 20, 20)])
        self.assertEqual(player.loaded, {1: {16: (10, 10, 10), 17: (20, 20, 20), 240: (30, 30, 30)}})

    def test_drawing_follows_the_prince_and_mirrors(self):
        operations = [{'op': 'shape', 'args': [1, 10, 20, 256], 'follow': 'xy'},
                      {'op': 'save_rect', 'args': [1, [20, 10, 22, 13]], 'follow': 'x'},
                      {'op': 'shape', 'args': [1, 100, 100, 0]},
                      {'op': 'restore_rect', 'args': [1]}]
        player = self.player(operations, prince=(462, 310))
        # FreeShpInfo 17:5fd0 mirrors the shape; follow moves it by (+5, -3).
        self.assertEqual(player.target.getpixel((17, 17)), 9)
        self.assertEqual(player.target.getpixel((15, 17)), 7)
        self.assertEqual(player.saved_rects[1][0], (15, 20, 18, 22))
        player = self.player(operations)
        self.assertEqual(player.target.getpixel((12, 20)), 9)

    def test_without_dissolve_data_a_dissolve_copies_at_once(self):
        player = self.player([{'op': 'dissolve_area', 'args': [None]},
                              {'op': 'fill', 'args': [4, [0, 0, 384, 512]]},
                              {'op': 'dissolve', 'args': [240]}])
        # 15:2c06: CopyBits of the whole screen, no wait.
        self.assertTrue(player.done)
        self.assertEqual(player.display.getpixel((300, 300)), 4)
        player = self.player([{'op': 'dissolve_area', 'args': [[210, 243, 314, 320]]},
                              {'op': 'fill', 'args': [4, [0, 0, 384, 512]]},
                              {'op': 'dissolve', 'args': [60]}])
        player.advance(2)
        # InitDissolve 15:2c40 mode 2: only the rectangle changes.
        self.assertEqual(player.display.getpixel((250, 250)), 4)
        self.assertEqual(player.display.getpixel((100, 100)), 1)

    def test_text_panel_is_the_saved_strip_in_orange(self):
        from types import SimpleNamespace
        from PIL import Image

        player = self.player([{'op': 'fill', 'args': [9, [0, 0, 87, 510]]},
                              {'op': 'save_rect', 'args': [2, [0, 0, 87, 510]]},
                              {'op': 'text_panel', 'args': [2]}])
        player.assets.strings = {32000: ['I died at his side.']}
        mask = Image.new('RGBA', (20, 10), (0, 0, 0, 255))
        player.assets.font = SimpleNamespace(height=12, ascent=9, text=lambda _line: mask)
        before = player.display.crop((0, 297, 512, 384)).tobytes()
        player.text(32000, 1, 0, 0, 0)
        # 15:026e-028c: the strip saved at a5-0x27da, then colours 1 and 2.
        colors = {player.display.getpixel((x, y)) for x in range(510) for y in range(87)}
        self.assertTrue({9, 1, 2, 255} <= colors)
        self.assertNotIn(3, colors)
        self.assertEqual(player.display.crop((0, 297, 512, 384)).tobytes(), before)
        player.text(0, 0, 0, 0, 0)
        self.assertEqual(set(player.display.crop((0, 0, 510, 87)).tobytes()), {9})

    def test_full_picture_dissolve_keeps_the_actual_status_pixels(self):
        from PIL import Image

        status = Image.new('RGBA', (512, 19), (220, 7, 19, 255))
        player = self.player([
            {'op': 'rgb', 'args': [3, 40, 40, 40]},
            {'op': 'rgb', 'args': [4, 200, 200, 200]},
            {'op': 'fill', 'args': [3, [0, 0, 384, 512]]},
            {'op': 'copy', 'args': [[0, 0, 384, 512]]},
            {'op': 'dissolve_area', 'args': [[0, 0, 365, 512]]},
            {'op': 'fill', 'args': [4, [0, 0, 384, 512]]},
            {'op': 'dissolve', 'args': [60]},
            {'op': 'fade_out_all', 'args': [0x40001]},
            {'op': 'copy', 'args': [[0, 0, 384, 512]]}], status=status)
        player.advance(.5)
        self.assertEqual(set(player.display.crop((0, 0, 512, 365)).tobytes()), {3, 4})
        self.assertEqual(player.frame().crop((0, 365, 512, 384)).tobytes(), status.tobytes())
        player.advance(10)
        self.assertTrue(player.done)
        self.assertEqual(player.frame().crop((0, 365, 512, 384)).tobytes(), status.tobytes())
