"""Asset-free regressions for the bounded CheckPress admission model."""

from dataclasses import replace
import unittest

from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_pressure_admission import PressureActor, admission_reference
from tools.probe_temple_slide_rock_geometry import TempleCellReader


def admission(actor=None, above=1, below=6):
    level = level_fixture()
    tile(level, 1, 3, 0, above)
    tile(level, 1, 3, 1, below)
    reader = TempleCellReader(level, 1)
    events, flag = admission_reference(actor or PressureActor(1, 3, 1, 236), reader)
    return events, flag, reader


class TemplePressureAdmissionTests(unittest.TestCase):
    def test_types_ten_eleven_and_floating_prince_return_before_cell_reads(self):
        for actor in (PressureActor(1, 3, 1, 236, kind=10),
                      PressureActor(1, 3, 1, 236, kind=11),
                      PressureActor(1, 3, 1, 236, floating=-1)):
            events, flag, reader = admission(actor)
            self.assertEqual((events, flag, reader.requests), ([], 4321, []))
        events, _, _ = admission(PressureActor(1, 3, 1, 236, kind=4, floating=1))
        self.assertEqual(events, [('push', (0, -1))])

    def test_type_one_selected_sequence_range_is_inclusive_and_not_a_pose_range(self):
        for selected in (28, 29, 42, 43):
            events, _, _ = admission(PressureActor(1, 3, 1, 236, kind=1, selected=selected))
            self.assertEqual(bool(events), selected in (28, 43))
        self.assertTrue(admission(PressureActor(1, 3, 1, 236, pose=29))[0])

    def test_above_pose_ranges_bypass_mode_and_aux_but_keep_height_gate(self):
        for pose in (87, 99, 135, 140):
            actor = PressureActor(1, 3, 1, 215, pose=pose, mode=4, aux=0)
            events, _, reader = admission(actor, above=5)
            self.assertEqual(events, [('push', (0, -1))])
            self.assertEqual(reader.requests, [(1, 3, 0)])
            self.assertEqual(admission(replace(actor, y=214), above=5)[0], [])
        for pose in (86, 100, 134, 141, -1):
            events, _, reader = admission(PressureActor(1, 3, 1, 236, pose=pose, mode=4, aux=0))
            self.assertEqual((events, reader.requests), ([], []))

    def test_grounded_modes_read_above_before_aux_filtered_current_cell(self):
        for mode in (-1, 0, 1, 5, 7, 8):
            events, _, reader = admission(PressureActor(1, 3, 1, 236, mode=mode))
            self.assertEqual(events, [('push', (0, -1))])
            self.assertEqual(reader.requests, [(1, 3, 0), (1, 3, 1)])
        for mode in (2, 3, 4, 6, 9):
            events, _, reader = admission(PressureActor(1, 3, 1, 236, mode=mode))
            self.assertEqual((events, reader.requests), ([], []))
        events, _, reader = admission(PressureActor(1, 3, 1, 236, aux=0), above=5)
        self.assertEqual((events, reader.requests, reader.cache[0]), ([], [(1, 3, 0)], 5))

    def test_alive_word_not_hp_selects_permanent_except_type_four(self):
        for alive in (-1, -32768, 0, 1):
            for kind in (0, 1, 4):
                events, _, _ = admission(PressureActor(1, 3, 1, 236, alive=alive, kind=kind))
                expected = ('push', (0, -1)) if alive < 0 or kind == 4 else ('permanent', ())
                self.assertEqual(events, [expected])

    def test_height_is_inclusive_at_row_times_120_plus_95(self):
        for y in (214, 215, 216):
            self.assertEqual(bool(admission(PressureActor(1, 3, 1, y))[0]), y >= 215)

    def test_pose_79_above_floor_dispatch_precedes_height_and_does_not_write_flag(self):
        actor = PressureActor(1, 3, 1, 0, pose=79, aux=0)
        for kind, expected in ((11, ('loose', (0,))), (15, ('trapdoor', ()))):
            events, flag, reader = admission(actor, above=kind)
            self.assertEqual((events, flag, reader.requests), ([expected], 4321, [(1, 3, 0)]))
        self.assertEqual(admission(actor, above=5)[0], [])

    def test_ordinary_loose_and_trapdoor_write_flag_while_plates_leave_it_for_endpoint(self):
        for kind, event in ((11, ('loose', (0,))), (15, ('trapdoor', ()))):
            events, flag, _ = admission(below=kind)
            self.assertEqual((events, flag), ([event], 1))
        for kind in (5, 6, 34):
            events, flag, _ = admission(below=kind)
            self.assertEqual((events, flag), ([('push', (0, -1))], 4321))


if __name__ == '__main__':
    unittest.main()
