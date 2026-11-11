"""Macintosh NIS 5, the final tower's Jaffar spell scene."""

import json
from pathlib import Path
import tempfile
import unittest

from pop2.audio import scene_sound_key
from pop2.intro import IntroAssets, IntroPlayer
from tools.extract_intro import recover_final_spell


FORKS = Path(__file__).resolve().parents[2] / 'PoP2-Mac-Code-Recovery' / 'resource_forks'
ORIGINAL = all((FORKS / name).is_file() for name in (
    'Prince of Persia 2.bin', 'NIS.rsrc.bin', 'Happy.rsrc.bin',
    'Prince.rsrc.bin', 'Kid.rsrc.bin', 'Title.rsrc.bin'))


@unittest.skipUnless(ORIGINAL, 'Preserved Macintosh resource forks required')
class FinalSpellRecoveryTests(unittest.TestCase):
    def test_native_jaffar_magic_callback_expands_into_a_renderable_scene(self):
        operations = recover_final_spell(*(
            (FORKS / name).read_bytes() for name in (
                'Prince of Persia 2.bin', 'NIS.rsrc.bin', 'Happy.rsrc.bin')))
        self.assertEqual(len(operations), 766)
        self.assertFalse(any(item['op'] == 'animation' for item in operations))
        self.assertIn({'op': 'fade', 'args': [1031001, True, 262145], 'pc': 0x0a5c},
                      operations)
        self.assertIn(31030, [item['args'][0] for item in operations
                               if item['op'] == 'sound'])
        self.assertIn(31031, [item['args'][0] for item in operations
                               if item['op'] == 'sound'])
        self.assertTrue(any(item['op'] == 'brightness' for item in operations))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            for name in ('NIS', 'Happy', 'Prince', 'Kid', 'Title'):
                (destination / f'{name}.rsrc').write_bytes((FORKS / f'{name}.rsrc.bin').read_bytes())
            audio = {scene_sound_key(item['args'][0], item['args'][1]):
                     {'duration': 0.01, 'markers': {}}
                     for item in operations if item['op'] == 'sound'}
            (destination / 'final_spell.json').write_text(json.dumps({
                'schema': 1, 'kind': 'final_spell',
                'resource_files': {'Happy.rsrc': 1000000},
                'operations': operations, 'audio': audio,
            }), encoding='ascii')
            assets = IntroAssets(directory=destination, program_name='final_spell.json')
            shape_ids = {item['args'][0] for item in operations if item['op'] == 'shape'}
            self.assertTrue(shape_ids)
            self.assertTrue(shape_ids <= assets.shapes.keys())
            self.assertIn(1031001, assets.palettes)
            player = IntroPlayer(assets)
            player.advance(30)
            self.assertTrue(player.done)
            self.assertIsNotNone(player.frame().getbbox())


if __name__ == '__main__':
    unittest.main()
