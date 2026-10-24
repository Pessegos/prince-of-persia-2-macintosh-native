import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_contact import ContactCellReader, contact_reference
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word


class TempleGateContactTests(unittest.TestCase):
    def fixture(self, *, foreground=1, source=9, pose=1, armed=0, alive=-1, hp=3,
                facing=-1, kind=0, room=1, number=10, environment=2, gates=None):
        level = bytearray(0x218c)
        for offset, value in ((0x2180, 32), (0x2186, environment), (0x218a, number)):
            struct.pack_into('>H', level, offset, value)
        for col, position in (((4, foreground),) if gates is None else gates):
            struct.pack_into('>H', level, (room - 1) * 60 + (10 + col) * 2, 4)
            struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + (10 + col) * 4, position)
        actor = bytearray(actor_fixture(room, 1, 4, facing, 0))
        for offset, value in ((4, 462), (8, kind), (10, pose), (26, armed), (28, alive),
                              (30, hp), (40, source), (42, 20), (46, 68)):
            put_actor(actor, offset, value)
        return bytes(actor), ContactCellReader(level, room)

    def query(self, *, overlap=None, distance=24, available=True, **kwargs):
        actor, reader = self.fixture(**kwargs)
        overlap = ((255,) * 10, (255,) * 10) if overlap is None else overlap
        return contact_reference(actor, reader, overlap, distance, sequence_available=available), reader

    def test_soft_contact_selects50_and_corrects_only_below25(self):
        for facing, sign in ((-1, 1), (0, -1)):
            for distance in (-1, 24, 25, 26):
                result, _reader = self.query(facing=facing, distance=distance)
                self.assertEqual([actor_word(result['actor'], o) for o in (36, 38, 40)], [0, 50, 50])
                self.assertEqual(actor_word(result['actor'], 4), 462 + sign * max(0, 25 - distance))
                self.assertEqual(result['events'], [('resource', 50), ('distance',)])
                self.assertEqual(result['mark'], 73)

    def test_source50_suppresses_repeat_selection_and_distance(self):
        result, _reader = self.query(source=50, distance=-1)
        self.assertEqual(result['events'], [])
        self.assertEqual(actor_word(result['actor'], 4), 462)

    def test_missing_sequence_preserves_clip_but_still_corrects_position(self):
        actor, _reader = self.fixture()
        result, _reader = self.query(available=False)
        self.assertEqual(result['actor'][36:42], actor[36:42])
        self.assertEqual(actor_word(result['actor'], 4), 463)

    def test_hard_contact_marks_and_calls_ejection_without_inventing_death(self):
        for kwargs in ({'foreground': 0}, {'armed': 1}, {'pose': 109}):
            actor, _reader = self.fixture(**kwargs)
            result, _reader = self.query(**kwargs)
            self.assertEqual(result, dict(actor=actor, events=[('eject',)], mark=1))
            self.assertEqual(actor_word(result['actor'], 28), -1)
            self.assertEqual(actor_word(result['actor'], 30), 3)

    def test_source118_and_nonnegative_alive_still_read_current_cell_once(self):
        for kwargs in ({'source': 118}, {'alive': 0}, {'alive': 1}):
            result, reader = self.query(**kwargs)
            self.assertEqual(result['events'], [])
            self.assertEqual(reader.requests, [(1, 4, 1)])

    def test_hp_zero_is_not_substituted_for_native_alive(self):
        result, _reader = self.query(hp=0, alive=-1)
        self.assertEqual(result['events'], [('resource', 50), ('distance',)])

    def test_overlap_intersection_must_equal_exactly255(self):
        for pair, expected in (((255, 255), True), ((511, 255), True),
                               ((511, 511), False), ((127, 255), False)):
            result, _reader = self.query(overlap=((pair[0],) * 10, (pair[1],) * 10))
            self.assertEqual(bool(result['events']), expected)

    def test_contact_checks_front_before_opposite_neighbor(self):
        for facing, first, second in ((-1, 5, 3), (0, 3, 5)):
            result, reader = self.query(facing=facing, gates=((first, 100), (second, 1)))
            self.assertEqual(result['events'], [])
            self.assertEqual(reader.requests, [(1, 4, 1), (1, first, 1)])

    def test_high_foreground_flags_affect_soft_choice_not_admission(self):
        result, _reader = self.query(foreground=0x8100)
        self.assertEqual(result['events'], [('resource', 50), ('distance',)])
        self.assertEqual(self.query(foreground=0)[0]['events'], [('eject',)])

    def test_cave_contact_is_separate_from_temple_ejection(self):
        self.assertEqual(self.query(environment=3, pose=109)[0]['events'], [('cave_contact',)])
        self.assertEqual(self.query(environment=3, pose=109, armed=1)[0]['events'], [('eject',)])
        self.assertEqual(self.query(environment=3, foreground=0x8100, pose=109)[0]['events'], [('eject',)])

    def test_level8_resolved_room9_exemption_keeps_current_read(self):
        result, reader = self.query(number=8, room=9)
        self.assertEqual(result['events'], [])
        self.assertEqual(reader.requests, [(9, 4, 1)])

    def test_guard_and_source68_are_exempt_before_response(self):
        for kwargs in ({'kind': 1}, {'source': 68}):
            self.assertEqual(self.query(foreground=0, **kwargs)[0]['events'], [])

    def test_distance_correction_wraps_word_before_relative_add(self):
        for facing, expected in ((-1, -32281), (0, -32331)):
            result, _reader = self.query(facing=facing, distance=-32768)
            self.assertEqual(actor_word(result['actor'], 4), expected)

    def test_cave_control_rejects_unproved_undefined_cell_rules(self):
        _actor, reader = self.fixture(environment=3)
        with self.assertRaises(ValueError):
            reader.read(1, -1, 1)


if __name__ == '__main__':
    unittest.main()
