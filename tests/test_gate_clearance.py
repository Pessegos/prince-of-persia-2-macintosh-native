"""Intentional port tolerance for a running pose's trailing gate contact."""

import struct
from types import SimpleNamespace
import unittest

from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion


class RunningGateClearanceTests(unittest.TestCase):
    def setUp(self):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2186, 3)
        struct.pack_into('>H', level, 0x2198, 1)
        for cell in range(30):
            struct.pack_into('>H', level, cell * 2, 1)
        struct.pack_into('>H', level, 15 * 2, 4)
        self.level = level
        self.physics = RooftopPhysics(LevelMap(level))
        self.record = SimpleNamespace(offset_x=0, aux=0)

    def contact(self, facing, overlap, *, sequence=13, phase=104, falling=False,
                y=0, sword=False, front=False, action=49):
        left, right = 295, 327
        on_right = bool(facing) != front
        edge = right - overlap if on_right else left + overlap
        body = ((edge, 155, edge + 24, 226) if on_right else
                (edge - 25, 155, edge - 1, 226))
        # Keep the settled footprint under the gate in this edge-only fixture.
        x = right - overlap + 15 if on_right else left + overlap - 15
        state = SequenceState(sequence, action=action, target_x=x,
                              facing=facing, level_kind=3, actor_type=0, current_y=y)
        motion = TerrainMotion(0, 1, falling=falling)
        struct.pack_into('>H', self.level, 0x780 + 15 * 4, 0x300 | phase)
        event = self.physics.check_gate(motion, SequenceRuntime({}, state), body, body,
                                        self.record, True, sword)
        return event, state

    def stop_contact(self, facing, clearance, *, action=56, sequence=13,
                     phase=104, falling=False, y=0, sword=False):
        left, right = 295, 327
        width, offset = {53: (50, 6), 54: (34, 5), 55: (61, 8), 56: (49, 6)}[action]
        x = right + 15 + clearance if facing else left - 15 - clearance
        start = x - (width - offset if facing else offset)
        body = (start, 155, start + width - 1, 226)
        state = SequenceState(sequence, action=action, target_x=x, facing=facing,
                              level_kind=3, actor_type=0, current_y=y)
        motion = TerrainMotion(0, 1, falling=falling)
        struct.pack_into('>H', self.level, 0x780 + 15 * 4, 0x300 | phase)
        event = self.physics.check_gate(motion, SequenceRuntime({}, state), body, body,
                                        self.record, True, sword)
        return event, state

    def test_ordinary_running_and_settling_poses_keep_the_four_pixel_margin(self):
        for facing in (0, 1):
            for sequence in (1, 13, 200, 201, 202):
                for phase in (0, 64, 104):
                    for overlap in (1, 3, 4):
                        with self.subTest(facing=facing, sequence=sequence, phase=phase,
                                          overlap=overlap):
                            event, state = self.contact(facing, overlap, sequence=sequence, phase=phase)
                            self.assertIsNone(event)
                            self.assertEqual(state.source_sequence_id, sequence)
                            self.assertEqual(state.target_x,
                                             327 - overlap + 15 if facing else 295 + overlap - 15)

    def test_run_stop_can_finish_only_if_the_settled_footprint_fits(self):
        for facing in (0, 1):
            for action in (53, 54, 55, 56):
                for phase in (0, 64, 104):
                    with self.subTest(facing=facing, action=action, phase=phase):
                        for clearance in (0, 8):
                            event, state = self.stop_contact(facing, clearance, action=action, phase=phase)
                            self.assertIsNone(event)
                            self.assertEqual(state.source_sequence_id, 13)
                        event, state = self.stop_contact(facing, -1, action=action, phase=phase)
                        self.assertIsNotNone(event)
                        self.assertEqual(state.source_sequence_id, 50)

    def test_stop_pose_numbers_do_not_extend_the_margin_for_other_sequences(self):
        for facing in (0, 1):
            for sequence in (1, 200, 201, 202, 5):
                event, _state = self.stop_contact(facing, 8, sequence=sequence)
                self.assertIsNotNone(event)

    def test_settled_clearance_does_not_exempt_sword_or_airborne_stop_poses(self):
        for facing in (0, 1):
            for options in ({'sword': True}, {'falling': True}, {'y': -1}):
                with self.subTest(facing=facing, options=options):
                    event, _state = self.stop_contact(facing, 8, **options)
                    self.assertIsNotNone(event)

    def test_deeper_rear_contact_and_front_contact_still_interrupt_the_run(self):
        for facing in (0, 1):
            for overlap, front in ((5, False), (16, False), (1, True), (4, True)):
                with self.subTest(facing=facing, overlap=overlap, front=front):
                    event, state = self.contact(facing, overlap, front=front)
                    self.assertEqual((event.kind, state.source_sequence_id), ('gate', 50))

    def test_tolerance_does_not_cover_idle_turn_jump_crouch_sword_or_airborne(self):
        for facing in (0, 1):
            for options in ({'sequence': 2}, {'sequence': 5}, {'sequence': 4},
                            {'sequence': 117}, {'sword': True}, {'falling': True}, {'y': -1}):
                with self.subTest(facing=facing, options=options):
                    event, _state = self.contact(facing, 3, **options)
                    self.assertIsNotNone(event)
