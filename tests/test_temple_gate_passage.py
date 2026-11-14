"""A slamming temple gate cannot push a runner back through its front plane."""

import struct
from types import SimpleNamespace
import unittest

from pop2.paths import ASSET_DIR
from pop2.terrain import LevelMap


class TempleGateSideTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 2)
        struct.pack_into('>H', self.level, 18 * 2, 4)
        struct.pack_into('>H', self.level, 0x780 + 18 * 4, 124)
        self.terrain = LevelMap(self.level)
        self.state = SimpleNamespace(actor_type=0, source_sequence_id=1)

    def test_already_overlapping_running_body_is_not_a_new_front_collision(self):
        # Native room3 right-facing poses8->9, plus the reflected body.
        for facing, old_x, x, before, after in (
                (1, 502, 516, (461, 150, 512, 225), (477, 151, 522, 225)),
                (0, 448, 434, (438, 150, 489, 225), (428, 151, 473, 225))):
            with self.subTest(facing=facing):
                self.assertEqual(self.terrain.wall_correction(0, old_x, x, after, before,
                    facing, 1, self.state), x)

    def test_genuine_front_crossing_still_blocks_both_directions(self):
        for facing, old_x, x, before, after in (
                (1, 445, 479, (431, 148, 448, 226), (449, 153, 485, 225)),
                (0, 505, 471, (502, 148, 519, 226), (465, 153, 501, 225))):
            with self.subTest(facing=facing):
                result = self.terrain.wall_correction(0, old_x, x, after, before, facing, 1, self.state)
                if facing:
                    self.assertLess(result, x)
                else:
                    self.assertGreater(result, x)


@unittest.skipUnless((ASSET_DIR / 'temple_level12.json').is_file(), 'Imported temple artwork required')
class TempleGatePassageTests(unittest.TestCase):
    def test_actual_climb_run_and_shut_plate_reach_the_right_room(self):
        from tools.audit_temple_routes import Harness, press

        harness = Harness(12, draw=True)
        scene = harness.scene
        try:
            # Supplied open gate and supported start; descent, climb, run,
            # plate activation, gate slam and room cut all run through keys.
            scene.game.caverns.plates.foreground[(2, 18)] = 184
            scene.jump_to_room(2, row=1, x=444, facing=1)
            press(harness, 'shift', True)
            press(harness, 'down', True)
            for tick in range(39):
                if tick == 2:
                    press(harness, 'down', False)
                if tick == 20:
                    press(harness, 'up', True)
                if tick == 23:
                    press(harness, 'up', False)
                harness.tick()
            self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x), (2, 1, 445))
            press(harness, 'shift', False)
            press(harness, 'R', True)
            for tick in range(13):
                harness.tick()
                self.assertEqual(scene.sequence_state.source_sequence_id, 1)
                if tick == 6:
                    self.assertEqual(scene.game.caverns.plates.active.get((2, 18)), 4)
                if tick == 7:
                    self.assertEqual(scene.player_x, 516)
                    self.assertEqual(scene.level_map.tile(2, 8, 1).foreground & 255, 124)
            self.assertEqual(scene.room_id, scene.level_map.neighbor(2, 'right'))
            self.assertEqual(scene.room_id, 10)
            self.assertEqual(scene.level_map.tile(2, 8, 1).foreground & 255, 0)
            self.assertTrue(scene.combat.player.alive)
        finally:
            harness.close()
