"""Moving gates must use their live height in actor/floor repaints too."""

from dataclasses import replace
import struct
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.caverns import cavern_room, pressure_drawing_commands
from pop2.paths import ASSET_DIR


class GateRepaintCommandsTests(unittest.TestCase):
    def test_temple_front_repaint_tracks_closed_partial_and_open_gate(self):
        # Actual level12 room3 lower gate; native DrawTempGateMovable10:0976.
        source = ['front', 3576, 458, 235, 16, 1, [109, 458, 235, 488], 4, 8, 1]
        record = {'kind': 4, 'foreground': 0, 'commands': [['back', 3576, 4, 8, 1]]}
        resources = {'SHAP': {3576: {'data': struct.pack('>4H', 0, 0, 30, 126)}}}
        for phase, bottom, top in ((0, 235, 109), (23, 189, 101), (46, 143, 101)):
            with self.subTest(phase=phase):
                expected = [*source[:3], bottom, *source[4:6], [top, 458, bottom, 488], *source[7:]]
                self.assertEqual(pressure_drawing_commands([source], [record], (phase,), resources),
                                 [expected])
        self.assertEqual(source[3:7], [235, 16, 1, [109, 458, 235, 488]])

    def test_repaint_does_not_move_a_different_cell_or_library(self):
        source = ['front', 3576, 458, 235, 16, 1, [109, 458, 235, 488], 4, 8, 1]
        record = {'kind': 4, 'foreground': 0, 'commands': [['back', 3576, 4, 8, 1]]}
        for index, value in ((7, 1), (8, 7), (9, 0)):
            other = list(source)
            other[index] = value
            self.assertEqual(pressure_drawing_commands([other], [record], (46,), {}), [other])


@unittest.skipUnless((ASSET_DIR / 'temple_level12.json').is_file(), 'Imported temple artwork required')
class GateRepaintSceneTests(unittest.TestCase):
    def test_open_gate_does_not_reappear_in_floor_or_pose141_repaint(self):
        # This is the strip crossing the head in the user's room3 recording.
        for phase in (0, 23, 46):
            art = cavern_room(2, level_number=12, pressure_key=(0, 0, 0, 0, phase, 0, 0))
            for records in (art.floor_redraw[(8, 1)], art.climb_redraw[(141, 8, 1)]):
                frame = Image.new('RGBA', (510, 365), 'magenta')
                art.draw_floor_records(frame, records, (459, 170, 488, 235))
                self.assertEqual(frame.getpixel((480, 190)),
                                 (255, 0, 255, 255) if phase else (82, 24, 8, 255))
                if phase == 46:
                    self.assertIsNone(ImageChops.difference(
                        frame.convert('RGB'), Image.new('RGB', frame.size, 'magenta')).getbbox())

    def test_real_room3_descent_and_climb_use_current_gate_without_changing_motion(self):
        from tools.audit_temple_routes import Harness, press

        harness = Harness(12, draw=True)
        scene = harness.scene
        try:
            scene.game.caverns.plates.foreground[(2, 18)] = 255
            scene.jump_to_room(2, row=1, x=444, facing=1)
            press(harness, 'shift', True)
            press(harness, 'down', True)
            poses = set()
            for tick in range(39):
                if tick == 2:
                    press(harness, 'down', False)
                if tick == 20:
                    press(harness, 'up', True)
                if tick == 23:
                    press(harness, 'up', False)
                harness.tick()
                state = scene.sequence_state
                if state.source_sequence_id != 10 or not 135 <= state.action <= 148:
                    continue
                poses.add(state.action)
                before = replace(state)
                scene.render()
                actual = scene.native_viewport.copy()

                # Independent drawing control: remove only lower-gate repaint
                # pixels, all of which belong above the actor when fully open.
                original = pressure_drawing_commands

                def without_gate(commands, records, phases, resources):
                    return [c for c in original(commands, records, phases, resources)
                            if not (c[0] == 'front' and c[1] == 3576 and c[8:10] == [8, 1])]

                current = scene.room_cache[2]
                try:
                    with (patch('pop2.caverns.pressure_drawing_commands', without_gate),
                          patch.dict(scene.level_renderer.cavern_frames, clear=True)):
                        scene.render()
                        expected = scene.native_viewport.copy()
                finally:
                    scene.room_cache[2] = current
                self.assertIsNone(ImageChops.difference(actual.crop((450, 170, 490, 240)).convert('RGB'),
                    expected.crop((450, 170, 490, 240)).convert('RGB')).getbbox(), state.action)
                self.assertEqual(state, before)
            self.assertEqual(poses, set(range(135, 149)))
            self.assertEqual((scene.room_id, scene.terrain_motion.row), (2, 1))
            self.assertTrue(scene.combat.player.alive)
        finally:
            harness.close()
