import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_contact import ContactCellReader
from tools.probe_temple_gate_ejection import ejection_reference, hard_contact_reference
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word


class TempleGateEjectionTests(unittest.TestCase):
    def actor(self, *, facing=-1, kind=0, alive=-1, hp=3, source=9):
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((4, 460), (8, kind), (10, 109), (26, 0), (28, alive),
                              (30, hp), (40, source), (42, 20), (46, 94)):
            put_actor(actor, offset, value)
        return bytes(actor)

    def query(self, edges, *, foreground=0, **kwargs):
        return ejection_reference(self.actor(**kwargs), foreground, 1, 4, edges, 1, (0,) * 6)

    def contact(self, *, foreground=0, overlap=(255, 255), **kwargs):
        level = bytearray(0x218c)
        for offset, value in ((0x2180, 32), (0x2186, 2), (0x218a, 10),
                              (14 * 2, 4), (0x780 + 14 * 4, foreground)):
            struct.pack_into('>H', level, offset, value)
        actor = self.actor(**kwargs)
        return hard_contact_reference(actor, ContactCellReader(level, 1),
                                      tuple((v,) * 10 for v in overlap), (480, 500), 1, (0,) * 6)

    def test_closer_face_adds_three_pixels_of_clearance(self):
        result = self.query((480, 500))
        self.assertEqual((result['delta'], actor_word(result['actor'], 4)), (-6, 466))
        self.assertEqual(result['calls'], ['face', 'face', 'back', 'back'])

    def test_actor_kind_four_gets_eight_more_pixels_only_in_the_face_branch(self):
        result = self.query((480, 500), kind=4)
        self.assertEqual((result['delta'], actor_word(result['actor'], 4)), (-14, 474))
        self.assertEqual(self.query((450, 480), kind=4)['delta'], 7)

    def test_equal_absolute_distances_choose_the_back(self):
        result = self.query((470, 486))
        self.assertEqual((result['delta'], actor_word(result['actor'], 4)), (13, 447))

    def test_facing_changes_the_side_and_relative_displacement(self):
        result = self.query((480, 500), facing=0)
        self.assertEqual((result['delta'], actor_word(result['actor'], 4)), (3, 463))

    def test_ejection_itself_changes_no_health_alive_animation_or_death_fields(self):
        for alive, hp in ((-1, 3), (-1, 0), (0, 0)):
            actor = self.actor(alive=alive, hp=hp)
            result = ejection_reference(actor, 0, 1, 4, (480, 500), 1, (0,) * 6)['actor']
            self.assertEqual(result[:4] + result[6:], actor[:4] + actor[6:])

    def test_direct_open_gate_ejection_does_not_replace_the_callers_admission(self):
        self.assertNotEqual(self.query((480, 500), foreground=184)['actor'], self.actor())
        result = self.contact(foreground=184)
        self.assertEqual((result['actor'], result['events'], result['calls']), (self.actor(), [], []))

    def test_hard_contact_marks_then_ejects_without_zeroing_life(self):
        result = self.contact()
        self.assertEqual((result['events'], result['mark']), ([('eject',)], 1))
        self.assertEqual(actor_word(result['actor'], 4), 466)
        self.assertEqual((actor_word(result['actor'], 28), actor_word(result['actor'], 30)), (-1, 3))

    def test_exact_overlap_and_early_exits_prevent_ejection(self):
        for kwargs in ({'overlap': (511, 511)}, {'alive': 0}, {'source': 118}):
            self.assertEqual(self.contact(**kwargs)['events'], [])
        self.assertEqual(self.contact(overlap=(511, 255))['events'], [('eject',)])

    def test_signed_absolute_minimum_remains_negative_when_stored(self):
        # Left face distance = -32768; its stored absolute word is still
        # negative and wins the signed comparison against a positive back.
        result = self.query((-32285, 500))
        self.assertEqual(result['delta'], 32765)
