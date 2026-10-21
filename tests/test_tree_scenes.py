import json
import struct
import unittest
from unittest.mock import patch

from pop2.intro import IntroAssets, IntroPlayer
from pop2.paths import ASSET_DIR
from tests.test_intro import instruction, script
from tools import extract_intro as extractor


def two_frame_resources():
    animation = script(instruction(4, 6), instruction(5, 1, 1), instruction(1),
                       instruction(5, 1, 2), instruction(1), instruction(5, 1, 1),
                       instruction(1), instruction(0))
    return {'ANI ': {26001: {'data': struct.pack('>9h', 0, 0, 384, 512, 1,
                                                 26001, 26001, 26001, 26001)}},
            'SCRP': {26001: {'data': animation}},
            'SHAP': {number: {'data': struct.pack('>HhhH', 0, 2, 2, 1)}
                     for number in (26001, 26002)}}


class TreeExpansionTests(unittest.TestCase):
    def test_callback_runs_after_drawing_frame_two_and_before_its_copy(self):
        # PlayTheAnimation 16:13d4-13f8 draws, calls back with frame+1, then
        # copies (16:140a). TreeFunc 15:04d0 acts only for frame 2.
        callback = [{'op': 'fade_in_both', 'args': [0x40001], 'pc': 0x04e8}]
        result = extractor.expand_animations(
            [{'op': 'animation', 'args': [26000, 1, 1, 1, 'tree'], 'pc': 0x069c}],
            two_frame_resources(), {'tree': {2: callback}})
        self.assertEqual([op['op'] for op in result], [
            'shape', 'copy', 'wait', 'shape', 'fade_in_both', 'copy', 'wait',
            'shape', 'copy', 'wait'])
        self.assertEqual(result[3]["args"][0], 26002)

    def test_animation_without_callback_is_unchanged(self):
        result = extractor.expand_animations(
            [{'op': 'animation', 'args': [26000, 1, 1, 1], 'pc': 0}], two_frame_resources())
        self.assertNotIn('fade_in_both', [op['op'] for op in result])

    def test_tree_overlay_rejects_colliding_resources(self):
        with patch.object(extractor, 'parse_resource_fork',
                          side_effect=[{'SHAP': {1: 'nis'}, 'TEXT': {26000: 't'}},
                                       {'SHAP': {26001: 'tree'}}]):
            merged = extractor.tree_resources(b'nis', b'tree')
        self.assertEqual((set(merged['SHAP']), set(merged['TEXT'])), ({1, 26001}, {26000}))
        with patch.object(extractor, 'parse_resource_fork',
                          side_effect=[{'SHAP': {1: 'nis'}}, {'SHAP': {1: 'tree'}}]):
            with self.assertRaises(ValueError):
                extractor.tree_resources(b'nis', b'tree')


def tree_program(variant):
    return json.loads((ASSET_DIR / f'tree-{variant}.json').read_text(encoding='ascii'))


@unittest.skipUnless(all((ASSET_DIR / f'tree-{n}.json').is_file() for n in range(1, 10))
                     and (ASSET_DIR / 'NISTree.rsrc').is_file(), 'Imported tree scenes required')
class OriginalTreeSceneTests(unittest.TestCase):
    def ops(self, variant):
        return [(item['op'], item['args']) for item in tree_program(variant)['operations']]

    def test_variant_selects_music_and_palette_from_tree_check(self):
        # TreeCheck 15:0612-0672: CTBL 26000 + (v + 2) / 3, MIDI 26010 + v.
        for variant in range(1, 10):
            with self.subTest(variant=variant):
                ops = self.ops(variant)
                self.assertIn(('palette', [26000 + (variant + 2) // 3, 70, 0x40001]), ops)
                self.assertIn(('sound', [26010 + variant, 0]), ops)
                self.assertEqual(ops[-3:], [('fade_both', [0x10001]), ('stop', [0]), ('stop', [1])])

    def test_fade_in_follows_the_second_drawn_frame(self):
        for variant in range(1, 10):
            with self.subTest(variant=variant):
                ops = [op for op, _args in self.ops(variant)]
                fade = ops.index('fade_in_both')
                self.assertEqual(ops[:fade].count('wait'), 1)
                self.assertEqual(ops[fade - 1], 'shape')
                self.assertEqual(ops[fade + 1:].count('fade_in_both'), 0)

    def test_first_variant_speaks_its_captions_and_last_waits_on_music_cues(self):
        first = self.ops(1)
        for item in (('sound', [26001, 1]), ('text', [26000, 1, 0, 0, 0]),
                     ('sound', [26002, 1]), ('sound', [26004, 1]),
                     ('text', [26000, 2, 0, 0, 0]), ('timer', [0, 60]),
                     ('sound', [26005, 1]), ('text', [26000, 3, 0, 0, 0])):
            self.assertIn(item, first)
        self.assertLess(first.index(('sound', [26001, 1])), first.index(('sound', [26004, 1])))
        last = self.ops(9)
        self.assertEqual([args[0] for op, args in last if op == 'cue'], [ord('a'), ord('b'), ord('c')])
        self.assertIn(('palette', [26028, 114, 0x40001]), last)
        for variant in range(2, 9):
            self.assertNotIn('text', [op for op, _args in self.ops(variant)])

    def test_every_tree_scene_plays_to_the_end_with_the_overlaid_resources(self):
        for variant in (1, 5, 9):
            with self.subTest(variant=variant):
                assets = IntroAssets(program_name=f'tree-{variant}.json')
                self.assertIn(26001, assets.shapes)
                self.assertIn(26000, assets.strings)
                player = IntroPlayer(assets)
                first = player.frame().copy()
                for _ in range(4000):
                    if player.done:
                        break
                    player.advance(0.05)
                self.assertTrue(player.done)
                self.assertNotEqual(first.tobytes(), player.display.tobytes())


if __name__ == '__main__':
    unittest.main()
