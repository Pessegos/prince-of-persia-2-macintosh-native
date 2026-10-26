"""Ruins gate geometry and the room-zero continuation below a cliff."""

import struct
from types import SimpleNamespace
import unittest

from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion, floor_y


class RuinsGateTests(unittest.TestCase):
    def setUp(self):
        data = bytearray(0x49ca)
        struct.pack_into('>H', data, 0x2186, 4)
        struct.pack_into('>H', data, 0x218a, 6)
        struct.pack_into('>H', data, 0x2198, 1)
        data[:60] = struct.pack('>30H', *([1] * 30))
        struct.pack_into('>H', data, 15 * 2, 4)
        self.terrain = LevelMap(data)

    def test_closed_gate_blocks_both_directions_but_open_gate_does_not(self):
        for phase, blocked in ((0, True), (100, True), (200, False), (255, False)):
            struct.pack_into('>H', self.terrain.level, 0x780 + 15 * 4, phase)
            for facing, old, new in ((1, 285, 350), (0, 355, 280)):
                old_body = old - 4, 160, old + 13, 226
                body = new - 4, 160, new + 13, 226
                state = SequenceState(1, target_x=new, facing=facing, actor_type=0, level_kind=4)
                actual = self.terrain.wall_correction(0, old, new, body, facing=facing,
                                                      physical_row=1, old_bounds=old_body, state=state)
                with self.subTest(phase=phase, facing=facing):
                    self.assertEqual(actual != new, blocked)
                    if blocked:
                        self.assertEqual(actual, 303 if facing else 331)

    def test_cautious_step_reserves_the_narrow_ruins_gate_instead_of_a_cavern_slab(self):
        record = SimpleNamespace(offset_x=4, aux=70)
        for facing, x, distance in ((1, 285, 18), (0, 355, 24)):
            state = SequenceState(2, target_x=x, facing=facing, level_kind=4, actor_type=0)
            body = x - 4, 160, x + 13, 226
            boundary = self.terrain.step_boundary(0, 1, state, record, body)
            self.assertEqual(boundary.clearance, distance)


class UnlinkedDownCutTests(unittest.TestCase):
    def test_body_leaves_before_room_zero_continuation_and_camera_y_is_retained(self):
        data = bytearray(0x49ca)
        struct.pack_into('>H', data, 0x2186, 4)
        struct.pack_into('>H', data, 0x218a, 6)
        struct.pack_into('>H', data, 0x2198, 27)
        physics = RooftopPhysics(LevelMap(data))
        motion = TerrainMotion(26, 3, falling=True)
        state = SequenceState(99, actor_type=0, level_kind=4)
        for y, leaves in ((499, False), (500, True)):
            state.current_y = y - floor_y(motion.row)
            self.assertFalse(physics.cut_down(motion, state, (250, y - 59, 270, y)))
            self.assertEqual(motion.void_fall, leaves)
            self.assertEqual(floor_y(motion.row) + state.current_y, y)
            self.assertEqual(motion.room, 26)

    def test_void_continuation_roundtrips_and_older_snapshots_default_to_false(self):
        from pop2.save_game import _pack, _unpack

        packed = _pack(TerrainMotion(26, 3, falling=True, void_fall=True))
        self.assertTrue(_unpack(packed, None, None).void_fall)
        del packed['fields']['void_fall']
        self.assertFalse(_unpack(packed, None, None).void_fall)
