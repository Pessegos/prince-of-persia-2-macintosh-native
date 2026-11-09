"""Temple candles animate from existing scenery exports, with native six-frame selection."""

import json
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.cavern_state import CavernState
from pop2.caverns import cavern_assets, cavern_room, draw_cavern_torches, temple_torch_records
from pop2.paths import ASSET_DIR


class CandleFrameTests(unittest.TestCase):
    def test_six_frames_initialize_once_per_candle_and_preserve_flags(self):
        record = {'room': 0, 'cell': 20, 'foreground': 0x1200, 'frame_count': 6}
        state = CavernState()
        with patch('pop2.cavern_state.random.randint', return_value=5) as random:
            state.configure_torches({'0': [record, record], '1': [record]})
        random.assert_called_once_with(0, 5)
        self.assertEqual(state.torches, {(0, 20): 0x1205})

    def test_repeated_last_frame_wraps_at_six_once_per_logical_candle(self):
        record = {'room': 0, 'cell': 20, 'frame_count': 6}
        state = CavernState(torches={(0, 20): 0x1205, (1, 20): 3})
        with patch('pop2.cavern_state.random.randint', return_value=5) as random:
            state.advance_torches([record, record])
        random.assert_called_once_with(0, 5)
        self.assertEqual(state.torches, {(0, 20): 0x1200, (1, 20): 3})


class CandleMetadataTests(unittest.TestCase):
    def test_a_fragment_in_the_next_slot_keeps_the_actual_candle_source(self):
        pieces = bytearray(0x18a)
        struct.pack_into('>h', pieces, 0x186, 42)
        command = ['back', 3598, 42, 288, 16, 2, [246, 51, 288, 89], 4, 1, 2]
        calls = []

        def tile(room, column, row):
            calls.append((room, column, row))
            return SimpleNamespace(kind=19, room=3, column=0, row=2, foreground=2)

        records = temple_torch_records([command], SimpleNamespace(tile=tile), 3,
                                       {'PIEC': {3500: {'data': pieces}}})
        self.assertEqual(calls, [(3, 0, 2)])
        self.assertEqual(records, [{'room': 3, 'cell': 20, 'foreground': 2,
                                    'command': command, 'first_shape': 3596, 'frame_count': 6}])


INSTALLED = all((ASSET_DIR / f'temple_level{number}.json').is_file()
                for number in (10, 11, 12, 13)) and (ASSET_DIR / 'Temple.rsrc').is_file()


@unittest.skipUnless(INSTALLED, 'Imported temple scenery required')
class CandleSceneTests(unittest.TestCase):
    def test_a_checkpoint_from_before_live_candles_can_retry_and_keep_animating(self):
        from tools.audit_temple_routes import Harness

        harness = Harness(12, peaceful=True, draw=True)
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.capture_rebirth_checkpoint(scene.checkpoints[0])
        # The preceding version stored no candle phases in temple checkpoints.
        scene.checkpoint.caverns.torches.clear()
        scene.restart_level_now(redraw=False)
        scene.jump_to_room(0, row=0, x=230, facing=1, preserve_checkpoint=True)
        scene.advance_level_events()
        records = scene.level_renderer.cavern_program['torches']['0']
        self.assertTrue(records)
        for record in records:
            self.assertIn(scene.game.caverns.torches[record['room'], record['cell']], range(6))
        scene.render()

    def test_live_candles_keep_the_native_scenery_overlap_in_every_room(self):
        # In particular, L10 R1's later floor piece covers the candle's
        # lower-right corner. A plain live paste would paint over it.
        for number in (10, 11, 12, 13):
            program = cavern_assets(number)[0]
            state = CavernState(torches={(r['room'], r['cell']): r['foreground']
                                        for records in program['torches'].values() for r in records})
            for room, records in program['torches'].items():
                if not records:
                    continue
                with self.subTest(level=number, room=int(room) + 1):
                    still = cavern_room(int(room), level_number=number)
                    live = cavern_room(int(room), animated=True, level_number=number)
                    expected = Image.alpha_composite(still.background, still.foreground)
                    actual = draw_cavern_torches(live.background.copy(), int(room), state,
                                               level_number=number, occlusion=live.torch_occlusion)
                    actual = Image.alpha_composite(actual, live.foreground)
                    for record in records:
                        top, left, bottom, right = record['command'][6]
                        box = left, top, right, bottom
                        difference = ImageChops.difference(expected.crop(box).convert('RGB'),
                                                          actual.crop(box).convert('RGB'))
                        self.assertIsNone(difference.getbbox())

    def test_existing_exports_supply_candles_in_all_four_levels(self):
        # Historical exports have the candle drawings but empty torches lists.
        # Count logical sources, not visible clips (some candles span two cells).
        for number, expected in ((10, 39), (11, 26), (12, 31), (13, 22)):
            with self.subTest(level=number):
                program = cavern_assets(number)[0]
                records = [record for room in program['torches'].values() for record in room]
                self.assertEqual(len({(r['room'], r['cell']) for r in records}), expected)
                self.assertTrue(all(r['first_shape'] == 3596 and r['frame_count'] == 6
                                    for r in records))

    def test_real_frames_change_without_rebuilding_scenery_and_pause_freezes_them(self):
        from tools.audit_temple_routes import Harness

        for number in (10, 11, 12, 13):
            with self.subTest(level=number):
                harness = Harness(number, peaceful=True, draw=True)
                try:
                    scene = harness.scene
                    scene.jump_to_room(0, row=0, x=230, facing=1)
                    # Choose an explicit phase; every image must replace the
                    # previous flame, including its transparent outline.
                    records = scene.level_renderer.cavern_program['torches']['0']
                    self.assertTrue(records)
                    frames = []
                    background = scene.background
                    for phase in range(6):
                        for record in records:
                            scene.game.caverns.torches[record['room'], record['cell']] = phase
                        scene.render()
                        frames.append(scene.native_viewport.tobytes())
                        self.assertIs(scene.background, background)
                    self.assertEqual(len(set(frames)), 6)
                    phases = scene.game.caverns.torches.copy()
                    scene.paused = True
                    harness.tick(3)
                    self.assertEqual(scene.game.caverns.torches, phases)
                    scene.paused = False
                    previous = {key: value & 15 for key, value in phases.items()}
                    with patch('pop2.cavern_state.random.randint', return_value=5):
                        scene.advance_level_events()
                    for record in records:
                        key = record['room'], record['cell']
                        self.assertNotEqual(scene.game.caverns.torches[key] & 15, previous[key])
                finally:
                    harness.close()

    def test_runtime_upgrade_keeps_the_imported_files_unchanged(self):
        for number in (10, 11, 12, 13):
            with self.subTest(level=number):
                path = ASSET_DIR / f'temple_level{number}.json'
                before = path.read_bytes()
                # Force the path taken on starting a new game process.
                from pop2.caverns import _cavern_assets

                _cavern_assets.cache_clear()
                program = cavern_assets(number)[0]
                self.assertTrue(any(program['torches'].values()))
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(json.loads(before)['rooms'], program['rooms'])
