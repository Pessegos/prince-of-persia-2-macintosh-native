import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_admission import admission_reference
from tools.probe_temple_gate_hanging import actor_fixture


class TempleGateAdmissionTests(unittest.TestCase):
    def actor(self, *, kind=0, source=9, top=20, bottom=68):
        actor = bytearray(actor_fixture(1, 1, 4, -1, 2))
        for offset, value in ((8, kind), (40, source), (42, top), (46, bottom)):
            put_actor(actor, offset, value)
        return bytes(actor)

    def test_exact_clearance_and_four_position_quantization(self):
        actor = self.actor()
        # Height48 requires opening25; foreground100..103 all encode25.
        self.assertEqual([admission_reference(actor, n) for n in range(96, 105)],
                         [1, 1, 1, 1, 0, 0, 0, 0, 0])

    def test_only_low_foreground_byte_matters_outside_environment_one(self):
        for environment in (2, 3, 4):
            for high in (0, 0x100, 0x8100, 0xff00):
                self.assertEqual(admission_reference(self.actor(), high | 99, environment), 1)
                self.assertEqual(admission_reference(self.actor(), high | 100, environment), 0)

    def test_guard_and_source68_bypass_body_height_test(self):
        self.assertEqual(admission_reference(self.actor(kind=1), 0), 0)
        self.assertEqual(admission_reference(self.actor(source=68), 0), 0)
        self.assertEqual(admission_reference(self.actor(source=67), 0), 1)

    def test_other_kinds_extend_the_visible_height(self):
        self.assertEqual(admission_reference(self.actor(kind=7), 188), 1)
        self.assertEqual(admission_reference(self.actor(kind=7), 192), 0)
        self.assertEqual(admission_reference(self.actor(kind=8), 164), 1)
        self.assertEqual(admission_reference(self.actor(kind=8), 168), 0)

    def test_rectangle_difference_and_extra_height_wrap_before_long_compare(self):
        self.assertEqual(admission_reference(self.actor(top=-32768, bottom=32767), 0), 1)
        self.assertEqual(admission_reference(self.actor(top=0, bottom=32767, kind=7), 0), 0)
        self.assertEqual(admission_reference(self.actor(top=0, bottom=-32768), 0), 0)

    def test_environment_one_uses_its_own_threshold_before_actor_exemptions(self):
        actor = self.actor(kind=1, source=68)
        self.assertEqual(admission_reference(actor, 18, 1), 1)
        self.assertEqual(admission_reference(actor, 19, 1), 0)
        self.assertEqual(admission_reference(actor, 32, 1), 1)

    def test_clipped_visible_height_is_not_the_full_image_height(self):
        self.assertEqual(admission_reference(self.actor(top=0, bottom=20), 44), 0)
        self.assertEqual(admission_reference(self.actor(top=-28, bottom=20), 44), 1)

    def test_invalid_fixture_rejected(self):
        for actor, foreground, environment in ((bytes(60), 0, 2), (self.actor(), -1, 2),
                                                (self.actor(), 65536, 2), (self.actor(), 0, 0)):
            with self.assertRaises(ValueError):
                admission_reference(actor, foreground, environment)


if __name__ == '__main__':
    unittest.main()
