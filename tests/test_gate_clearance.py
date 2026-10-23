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
        state = SequenceState(sequence, action=action, target_x=340 if on_right else 280,
                              facing=facing, level_kind=3, actor_type=0, current_y=y)
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
                            self.assertEqual(state.target_x, 340 if facing else 280)

    def test_run_stop_rear_arm_margin_ends_before_the_head_and_torso(self):
        for facing in (0, 1):
            for action, inset in ((53, 15), (54, 7), (55, 18), (56, 15)):
                for phase in (0, 64, 104):
                    with self.subTest(facing=facing, action=action, phase=phase):
                        for overlap in (5, inset):
                            event, state = self.contact(facing, overlap, action=action, phase=phase)
                            self.assertIsNone(event)
                            self.assertEqual(state.source_sequence_id, 13)
                        event, state = self.contact(facing, inset + 1, action=action, phase=phase)
                        self.assertIsNotNone(event)
                        self.assertEqual(state.source_sequence_id, 50)

    def test_stop_pose_numbers_do_not_extend_the_margin_for_other_sequences(self):
        for facing in (0, 1):
            for sequence in (1, 200, 201, 202, 5):
                event, _state = self.contact(facing, 9, sequence=sequence, action=56)
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
