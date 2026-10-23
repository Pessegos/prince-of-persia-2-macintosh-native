"""Asset-free checks of connected motion/geometry and crush-admission references."""

import struct
import unittest

from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_update import (
    actor_effects_reference, actor_word, crush_admission_reference, make_prince, update_reference,
)


def rock(x=204, room=1, mark=0, control=-2, y=236):
    return (x, y, room, mark, control, 6, 1, 459)


class TempleSlideRockUpdateTests(unittest.TestCase):
    def test_crush_requires_both_room_and_row_even_in_sequence_mode_four(self):
        for room, row in ((2, 1), (1, 0), (2, 2)):
            self.assertFalse(crush_admission_reference(
                rock(), make_prince(room=room, row=row, mode=4), 22))

    def test_normal_crush_interval_is_strict_at_both_ends(self):
        for x, expected in ((426, False), (427, False), (428, True),
                            (451, True), (452, False), (453, False)):
            self.assertEqual(crush_admission_reference(rock(), make_prince(x=x), 22), expected)

    def test_any_nonzero_facing_adds_the_signed_width(self):
        self.assertFalse(crush_admission_reference(rock(), make_prince(x=410), 22))
        for facing in (-1, 1, 2):
            self.assertTrue(crush_admission_reference(
                rock(), make_prince(x=410, facing=facing), 22))
        self.assertTrue(crush_admission_reference(
            rock(), make_prince(x=450, facing=-1), -10))

    def test_front_addition_wraps_but_the_upper_bound_uses_long_arithmetic(self):
        self.assertTrue(crush_admission_reference(rock(x=32540), make_prince(x=32764), 22))
        self.assertFalse(crush_admission_reference(
            rock(x=32540), make_prince(x=32764, facing=-1), 22))
        self.assertTrue(crush_admission_reference(
            rock(x=32760), make_prince(x=-32540), 22))

    def test_sequence_mode_four_not_actor_kind_four_bypasses_proximity(self):
        self.assertTrue(crush_admission_reference(rock(), make_prince(x=0, mode=4), 22))
        self.assertFalse(crush_admission_reference(rock(), make_prince(x=0, actor_kind=4), 22))

    def test_crush_gate_does_not_filter_control_removal_mark_or_room_zero(self):
        for control in (-2, 0, 100):
            for mark in (-1, 0, 1):
                self.assertTrue(crush_admission_reference(
                    rock(mark=mark, control=control), make_prince(x=440), 22))
        self.assertTrue(crush_admission_reference(rock(room=0), make_prince(room=0, x=440), 22))

    def test_true_filled_band_predicate_stops_motion_and_preserves_real_cell_cache(self):
        reader = TempleCellReader(level_fixture(), 1)
        prince, working = make_prince(room=2), bytes(62)
        result = update_reference(rock(control=8), reader, prince, working, 22, pending=192)
        self.assertEqual(result['mob'], rock(control=0))
        self.assertEqual(result['events'], [('filled', 204), ('stop', 192)])
        self.assertEqual(reader.requests, [(1, 4, 0), (1, 5, 0), (1, 4, 1), (1, 5, 1)])
        self.assertEqual(reader.cache[2:], (15, 1, 5, 1))
        self.assertEqual(result['pending'], -1)
        self.assertEqual(result['prince'], prince)
        self.assertEqual(result['working'], working)

    def test_empty_bands_do_not_stop_the_rock_and_query_real_tiles_in_order(self):
        level = level_fixture()
        for cell in range(30):
            struct.pack_into('>H', level, cell * 2, 0)
        reader = TempleCellReader(level, 1)
        result = update_reference(rock(control=2), reader, make_prince(room=2), bytes(62), 22)
        self.assertEqual(result['mob'], rock(x=202, control=3))
        self.assertEqual(reader.requests, [(1, 4, 0), (1, 3, 0), (1, 3, 1)])
        self.assertEqual(result['events'], [('filled', 204), ('filled', 188),
                                           ('cell', 1, 3, 1), ('sound', 192)])

    def test_real_wall_phase_finalizes_and_persists_across_repeated_updates(self):
        level = level_fixture()
        tile(level, 1, 0, 1, 4)
        reader = TempleCellReader(level, 1)
        prince, working = make_prince(room=2), bytes(62)
        first = update_reference(rock(x=58), reader, prince, working, 22)
        self.assertEqual(first['mob'], rock(x=56, mark=1, y=235))
        second = update_reference(first['mob'], reader, first['prince'], first['working'], 22)
        self.assertEqual(second['mob'], rock(x=57, control=100))
        for _ in range(4):
            second = update_reference(second['mob'], reader, second['prince'], second['working'], 22)
            self.assertEqual(second['mob'], rock(x=57, control=100))
            self.assertEqual(second['events'], [])

    def test_motion_always_precedes_crush_admission_even_when_motion_is_inert(self):
        mob = rock(control=0)
        result = update_reference(mob, TempleCellReader(level_fixture(), 1),
                                  make_prince(x=440), bytes(62), 22)
        self.assertEqual(result['phases'], [('motion', mob), ('crush', mob)])
        self.assertEqual(result['events'], [('actor', '10:1b04')])
        self.assertEqual(actor_word(result['prince'], 0), 30005)

    def test_actor_effect_then_crush_effect_sees_the_updated_prince_buffer(self):
        level = level_fixture()
        tile(level, 1, 0, 1, 2)
        prince = make_prince(x=293)
        result = update_reference(rock(x=58, mark=1), TempleCellReader(level, 1),
                                  prince, bytes(62), 22)
        self.assertEqual([e for e in result['events'] if e[0] == 'actor'],
                         [('actor', '5:3cee'), ('actor', '10:1b04')])
        self.assertEqual(result['actor_inputs'][0], prince)
        self.assertEqual(actor_word(result['actor_inputs'][1], 0), 30001)
        self.assertEqual(actor_word(result['prince'], 0), 30005)
        self.assertEqual(result['prince'][2:60], prince[2:60])

    def test_motion_frame_reaction_has_no_room_gate_but_crush_still_has_row_gate(self):
        prince = make_prince(room=2, row=2, column=1, frame=87)
        result = update_reference(rock(x=65), TempleCellReader(level_fixture(), 1),
                                  prince, bytes(62), 22)
        self.assertIn(('actor', '6:1a84'), result['events'])
        self.assertNotIn(('actor', '10:1b04'), result['events'])

    def test_endpoint_marker_contract_copies_the_entire_prince_buffer(self):
        prince = make_prince()
        after, working, inputs = actor_effects_reference(
            prince, bytes([255]) * 62, [('sound', 192), ('actor', '10:1b04')])
        self.assertEqual(after, working)
        self.assertEqual(inputs, [prince])
        self.assertEqual(after[2:60], prince[2:60])
        self.assertEqual(actor_word(after, 60), 30006)

    def test_invalid_actor_or_word_buffers_fail_closed(self):
        for mob, actor, width in (((1, 2), make_prince(), 22),
                                   (rock(), bytes(60), 22), (rock(), make_prince(), 32768)):
            with self.assertRaises(ValueError):
                crush_admission_reference(mob, actor, width)
        with self.assertRaises(ValueError):
            update_reference(rock(), TempleCellReader(level_fixture(), 1), bytes(60), bytes(62), 22)


if __name__ == '__main__':
    unittest.main()
