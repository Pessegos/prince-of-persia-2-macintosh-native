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
        self.assertEqual(len(operations), 767)
        # 15:0ae4-0b0c starts 30500 once 10055 has ended; the earlier
        # extraction restarted 10055 instead.
        self.assertFalse(any(item['op'] == 'ensure_sound' for item in operations))
        self.assertEqual({tuple(item['args']) for item in operations if item['op'] == 'sound_after'},
                         {(10055, 1, 30500, 1)})
        # Room 4's enter hook (9:1afe) waits on it.
        self.assertEqual(operations[-1], {'op': 'wait_sound', 'args': [30500, 1], 'pc': 0x1afe, 'code': 9})
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
            audio[scene_sound_key(30500, 1)] = {'duration': 0.01, 'markers': {}}
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


class SoundAfterTests(unittest.TestCase):
    def test_the_follow_sound_starts_once_when_the_watched_one_ends(self):
        from unittest.mock import Mock

        audio = {scene_sound_key(10055, 1): {'duration': 1.0, 'markers': {}},
                 scene_sound_key(30500, 1): {'duration': 3.0, 'markers': {}}}
        step = {'op': 'sound_after', 'args': [10055, 1, 30500, 1]}
        operations = [{'op': 'sound', 'args': [10055, 1]}]
        operations += [dict(step), {'op': 'wait', 'args': [6]}] * 40
        operations.append({'op': 'wait_sound', 'args': [30500, 1]})
        assets = Mock(program={'operations': operations, 'audio': audio}, shapes={}, palettes={})
        player = IntroPlayer.__new__(IntroPlayer)
        started = []
        IntroPlayer.__init__(player, assets)
        player.sound = lambda resource, kind, original=player.sound: (
            started.append((round(player.time, 1), resource)), original(resource, kind))
        player.advance(10)
        self.assertEqual([resource for _, resource in started], [30500])
        self.assertGreaterEqual(started[0][0], 1.0)
        # The last wait holds until 30500 ends.
        self.assertTrue(player.done)
        self.assertAlmostEqual(player.time, started[0][0] + 3.0, delta=0.2)


    def test_a_code_hook_runs_as_its_tagged_step_starts(self):
        # Room 4's enter hook (CODE 9:1ab4-1afe) adds ChessRm before its
        # WaitSndId(30500, 1), so the song plays during the black hold.
        from unittest.mock import Mock

        audio = {scene_sound_key(30500, 1): {'duration': 3.0, 'markers': {}}}
        operations = [{'op': 'sound', 'args': [30500, 1]}, {'op': 'wait', 'args': [30]},
                      {'op': 'wait_sound', 'args': [30500, 1], 'code': 9}]
        assets = Mock(program={'operations': operations, 'audio': audio}, shapes={}, palettes={})
        player = IntroPlayer(assets)
        calls = []
        player.code_hooks[9] = lambda: calls.append(round(player.time, 1))
        player.advance(0.2)
        self.assertEqual(calls, [])
        player.advance(1)
        self.assertEqual(calls, [0.5])
        self.assertFalse(player.done)
        player.advance(5)
        self.assertTrue(player.done)
        self.assertEqual(calls, [0.5])

if __name__ == '__main__':
    unittest.main()
