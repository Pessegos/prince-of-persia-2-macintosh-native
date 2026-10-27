import struct
import unittest

from tools.probe_temple_air_collision import air_collision_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word


class TempleAirCollisionTests(unittest.TestCase):
    def query(self, *, pose=15, facing=0, vy=49, available=True, floating=False,
              mode=0, row=1, height=0, x=460, alive=-1, hp=3, pending=0):
        actor = bytearray(actor_fixture(1, row, 4, facing, mode))
        for offset, value in ((4, x), (6, row * 120 + 106 - height), (8, 0), (10, pose),
                              (18, 5), (20, vy), (24, 17), (26, 0), (28, alive),
                              (30, hp), (34, pending), (36, 0), (38, 2), (40, 2)):
            put_actor(actor, offset, value)
        sequences = {2: (-7, 0, 15), 45: (-7, 5, -6, 5, -10, 229, 102),
                     46: (-7, 5, -5, -5, -6, -7, 102), 47: (-7, 5, -5, -16, 50),
                     121: (-7, 1, 251), 229: (102,)}
        frames = struct.pack('>5h', 1, 0, 0, 0, 0) * 352
        return air_collision_reference(bytes(actor), sequences, frames, bytes(8),
                                       available=available, floating=floating)

    def test_exact30_pixel_ground_redirect_precedes_air_alignment(self):
        air, ground = self.query(height=29), self.query(height=30)
        self.assertEqual(air['events'][0], ('align',))
        self.assertEqual(ground['events'][0], ('ground',))
        self.assertEqual(actor_word(air['actor'], 6), 226)
        self.assertEqual(actor_word(ground['actor'], 6), 201)

    def test_signed50_velocity_threshold_preserves_fall_and_skips_animation_mark(self):
        for vy in (-1, 49):
            ordinary = self.query(vy=vy)
            self.assertEqual(actor_word(ordinary['actor'], 20), 0)
            self.assertEqual((actor_word(ordinary['actor'], 4), ordinary['mark']), (444, 1))
        fast = self.query(vy=50)
        self.assertEqual([actor_word(fast['actor'], o) for o in (4, 10, 18, 20)], [443, 15, 5, 50])
        self.assertEqual((fast['events'], fast['mark']), ([('align',), ('frame',)], 73))

    def test_fast_fall_backoff_precedes_even_native_alive_zero(self):
        result = self.query(alive=0, vy=50, hp=0)
        self.assertEqual(actor_word(result['actor'], 4), 443)
        self.assertEqual(result['events'], [('align',), ('frame',)])

    def test_dead_slow_actor_aligns_and_stops_vertical_speed_without_frame_reload(self):
        result = self.query(alive=0, height=1)
        self.assertEqual([actor_word(result['actor'], o) for o in (4, 6, 10, 18, 20)], [460, 226, 15, 5, 0])
        self.assertEqual(result['events'], [('align',)])
        self.assertEqual((result['mark'], result['metadata'], result['remainder']), (73, bytes(range(18)), 79))

    def test_pending_health_uses_a_signed_long_sum_not_a_wrapped_word(self):
        for hp, pending, selected in ((0, 1, 47), (1, -1, 2), (32767, 1, 47), (-32768, -1, 2)):
            with self.subTest(hp=hp, pending=pending):
                self.assertEqual(actor_word(self.query(hp=hp, pending=pending)['actor'], 40), selected)

    def test_special_pose_interval_clears_word24_not_horizontal_velocity(self):
        for pose in (246, 261):
            result = self.query(pose=pose, hp=0, pending=-1)
            self.assertEqual([actor_word(result['actor'], o) for o in (4, 10, 16, 18, 24, 40)],
                             [455, 251, 1, 5, 0, 121])
        for pose in (245, 262):
            result = self.query(pose=pose)
            self.assertEqual((actor_word(result['actor'], 24), actor_word(result['actor'], 40)), (17, 47))

    def test_pose_specific_bump_clip46_differs_from_default47(self):
        for pose in (24, 25, 40, 41, 42, 102, 103, 104, 105, 106):
            result = self.query(pose=pose)
            self.assertEqual([actor_word(result['actor'], o) for o in (4, 6, 10, 40)], [455, 219, 102, 46])
        for pose in (23, 26, 39, 43, 101, 107):
            self.assertEqual(actor_word(self.query(pose=pose)['actor'], 40), 47)

    def test_relative_backoff_wraps_and_type0_alignment_does_not_use_modes7_or8(self):
        self.assertEqual(actor_word(self.query(vy=50, x=32767, facing=-1)['actor'], 4), -32752)
        self.assertEqual(actor_word(self.query(vy=50, x=-32768)['actor'], 4), 32751)
        for mode in (7, 8):
            self.assertEqual(actor_word(self.query(mode=mode, vy=50)['actor'], 6), 226)
        self.assertEqual(actor_word(self.query(row=-1, mode=7, vy=50)['actor'], 6), -14)

    def test_missing_requested_clip_animates_old_source_after_explicit_response_writes(self):
        ordinary = self.query(pose=24, available=False)
        self.assertEqual([actor_word(ordinary['actor'], o) for o in (4, 10, 36, 38, 40)], [460, 15, 3, 2, 2])
        special = self.query(pose=246, available=False)
        self.assertEqual([actor_word(special['actor'], o) for o in (4, 10, 16, 18, 24, 40)], [455, 15, 0, 5, 0, 2])

    def test_ground_redirect_retains_real_floating_source_and_active_clip_distinction(self):
        result = self.query(height=30, floating=True)
        self.assertEqual([actor_word(result['actor'], o) for o in (38, 40)], [229, 45])

    def test_armed_and_non_prince_types_remain_explicit_boundaries(self):
        for offset in (8, 26):
            actor = bytearray(actor_fixture(1, 1, 4, 0, 0))
            put_actor(actor, 8, 0)
            put_actor(actor, 26, 0)
            put_actor(actor, offset, 1)
            with self.assertRaises(ValueError):
                air_collision_reference(bytes(actor), {}, bytes(3520), bytes(8))
