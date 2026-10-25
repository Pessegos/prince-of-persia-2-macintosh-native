"""Synthetic regressions for state carried between rock update and drawing passes."""

import struct
import unittest

from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import (
    present_bank_reference, store_bank, trigger_state_reference, update_bank_reference,
)
from tools.probe_temple_slide_rock_presentation import STORAGE_SIZE, view_for
from tools.probe_temple_slide_rock_update import make_prince


def rock(x=204, mark=0, control=-2, anchor=459):
    return (x, 236, 1, mark, control, 6, 1, anchor)


class TempleSlideRockLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.level = level_fixture()
        self.reader = TempleCellReader(self.level, 1)
        self.view = view_for(1, 'current')
        self.decorations = ((79, -68), (76, -37), (66, -57))
        self.clip = (0, 0, 365, 510)
        self.guard = bytes((i * 29 + 3) % 256 for i in range(512))

    def state(self, bank=()):
        heights, widths = list(range(50, 64)), list(range(20, 34))
        heights[6:8], widths[6] = (80, 83), 82
        return dict(mob=(17, 19, 23, 29, 31, 37, 41, 43), bank=tuple(bank),
                    bank_storage=store_bank(self.guard, bank),
                    prince=make_prince(room=2, x=-30000), working=bytes(62), pending=192,
                    heights=tuple(heights), widths=tuple(widths),
                    objects=bytes((i * 13 + 3) % 256 for i in range(STORAGE_SIZE)),
                    count=0, screen_cell=-1234, events=[], phases=[], actor_inputs=[])

    def present(self, state, visible=True):
        return present_bank_reference(state, self.reader, self.view, visible,
                                      self.decorations, self.clip)

    def assert_physics_equal(self, first, second):
        for name in ('bank', 'bank_storage', 'prince', 'working', 'pending'):
            self.assertEqual(first[name], second[name], name)

    def test_trigger_then_release_reuses_bank_without_resetting_scratch(self):
        initial = self.state()
        created = trigger_state_reference(initial, self.reader, 1, 14, 1)
        self.assertEqual(created['bank'], (rock(anchor=204),))
        self.assertEqual(created['mob'], rock(anchor=204))
        released = trigger_state_reference(created, self.reader, 1, 14, 2)
        self.assertEqual(released['bank'], (rock(control=2, anchor=204),))
        self.assertEqual(released['mob'], created['mob'])
        self.assertEqual(released['bank_storage'][:16], self.guard[:16])
        self.assertEqual(released['bank_storage'][32:], self.guard[32:])
        self.assertEqual(initial['bank_storage'], self.guard)

    def test_repeated_presentation_appends_again_without_advancing_rock(self):
        moved = update_bank_reference(self.state((rock(),)), self.reader)
        self.assertEqual(moved['bank'][0][0], 202)
        once = self.present(moved)
        twice = self.present(once)
        self.assertGreater(once['count'], 0)
        self.assertEqual(twice['count'], 2 * once['count'])
        self.assertEqual(once['mob'], rock(x=202))
        self.assertEqual(twice['mob'], rock(x=202))
        self.assert_physics_equal(moved, once)
        self.assert_physics_equal(moved, twice)
        prefix_end = 16 + once['count'] * 28
        self.assertEqual(twice['objects'][:prefix_end], once['objects'][:prefix_end])

    def test_next_motion_uses_restored_position_after_two_presentations(self):
        moved = update_bank_reference(self.state((rock(),)), self.reader)
        without_draw = update_bank_reference(moved, TempleCellReader(self.level, 1))
        drawn = self.present(self.present(moved))
        after_draw = update_bank_reference(drawn, self.reader)
        self.assert_physics_equal(after_draw, without_draw)
        self.assertEqual(after_draw['bank'], (rock(x=200),))
        self.assertEqual(after_draw['events'], without_draw['events'])

    def test_compaction_preserves_updated_tail_through_presentation(self):
        initial = self.state((rock(x=0), rock()))
        moved = update_bank_reference(initial, self.reader)
        self.assertEqual(moved['bank'], (rock(x=202),))
        self.assertEqual(struct.unpack_from('>8h', moved['bank_storage'], 32), rock(x=202))
        self.assertEqual(moved['bank_storage'][:16], self.guard[:16])
        self.assertEqual(moved['bank_storage'][48:], self.guard[48:])
        drawn = self.present(moved)
        self.assertEqual(drawn['bank_storage'], moved['bank_storage'])
        self.assertEqual(initial['bank'], (rock(x=0), rock()))

    def test_wall_marker_finalizes_after_drawing_and_terminal_still_draws(self):
        tile(self.level, 1, 0, 1, 4)
        marked = update_bank_reference(self.state((rock(x=58),)), self.reader)
        self.assertEqual(marked['bank'], ((56, 235, 1, 1, -2, 6, 1, 459),))
        drawn = self.present(marked)
        terminal = update_bank_reference(drawn, self.reader)
        self.assertEqual(terminal['bank'], (rock(x=57, control=100),))
        terminal['count'] = 0
        terminal_drawn = self.present(terminal)
        self.assertGreater(terminal_drawn['count'], 0)
        self.assert_physics_equal(terminal_drawn, terminal)
        next_update = update_bank_reference(terminal_drawn, self.reader)
        self.assert_physics_equal(next_update, terminal)

    def test_invisible_presentation_preserves_queue_and_dimensions(self):
        state = self.state((rock(),))
        invisible = self.present(state, visible=False)
        self.assertEqual(invisible['events'], [('visibility', 1, 14)])
        for name in ('objects', 'count', 'heights', 'widths'):
            self.assertEqual(invisible[name], state[name])
        self.assert_physics_equal(invisible, state)

    def test_visible_dimension_canonicalization_survives_next_motion(self):
        state = self.state((rock(),))
        drawn = self.present(state)
        self.assertEqual(drawn['heights'][6:8], (83, 83))
        self.assertEqual(state['heights'][6:8], (80, 83))
        moved = update_bank_reference(drawn, self.reader)
        self.assertEqual(moved['heights'], drawn['heights'])
        self.assertEqual(moved['widths'], state['widths'])

    def test_two_records_append_to_one_queue_and_last_scratch_is_restored(self):
        bank = (rock(anchor=0), rock(x=102, anchor=0))
        drawn = self.present(self.state(bank))
        self.assertEqual(drawn['count'], 2)
        self.assertEqual(drawn['mob'], bank[-1])
        self.assertEqual(drawn['bank'], bank)
        self.assertEqual(struct.unpack_from('>h', drawn['objects'], 16)[0], 204)
        self.assertEqual(struct.unpack_from('>h', drawn['objects'], 44)[0], 102)
        self.assertEqual(drawn['heights'][6:8], (83, 83))

    def test_empty_bank_preserves_scratch_queue_and_guard_bytes(self):
        state = self.state()
        state['count'] = 2
        moved = update_bank_reference(state, self.reader)
        drawn = self.present(moved)
        self.assertEqual(drawn, state)
        self.assertEqual(self.reader.requests, [])

    def test_unsupported_bank_type_and_buffer_size_fail_explicitly(self):
        state = self.state(((204, 236, 1, 0, -2, 10, 1, 459),))
        with self.assertRaises(ValueError):
            update_bank_reference(state, self.reader)
        with self.assertRaises(ValueError):
            self.present(state)
        with self.assertRaises(ValueError):
            store_bank(bytes(511), ())
        with self.assertRaises(ValueError):
            store_bank(self.guard, (rock(),) * 31)


if __name__ == '__main__':
    unittest.main()
