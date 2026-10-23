"""Asset-free motion-model tests; these do not execute original resources."""

import unittest

from tools.probe_temple_slide_rock_motion import motion_reference, trunc_div


def rock(x=204, mark=0, state=-2, y=236):
    return (x, y, 2, mark, state, 6, 1, 459)


class TempleSlideRockMotionTests(unittest.TestCase):
    def step(self, mob=None, **options):
        return motion_reference(rock() if mob is None else mob, 3, **options)

    def test_signed_division_truncates_toward_zero(self):
        for value, expected in ((-52, -1), (-51, -1), (-50, 0), (-1, 0),
                                (0, 0), (50, 0), (51, 1), (52, 1)):
            self.assertEqual(trunc_div(value), expected)

    def test_zero_and_hundred_return_without_any_service_or_change(self):
        for state in (0, 100):
            for mark in (-1, 0, 1):
                mob = rock(state=state, mark=mark)
                self.assertEqual(self.step(mob, pending=192),
                                 dict(mob=mob, events=[], pending=192))

    def test_minus_two_skips_space_queries_and_keeps_control(self):
        result = self.step(clear=(True, True))
        self.assertEqual(result['mob'], rock(x=202))
        self.assertFalse(any(event[0] == 'clear' for event in result['events']))
        self.assertEqual(result['events'][-1], ('sound', 192))

    def test_control_increments_until_nine_but_does_not_set_speed(self):
        for state, expected in ((-32768, -32767), (-3, -2), (-1, 0),
                                (1, 2), (7, 8), (8, 9), (9, 9), (101, 101)):
            result = self.step(rock(state=state))
            self.assertEqual(result['mob'][4], expected)
            # Reaching state zero exits before committing the candidate X.
            self.assertEqual(result['mob'][0], 204 if expected == 0 else 202)

    def test_space_check_uses_original_x_and_then_x_minus_sixteen(self):
        result = self.step(rock(state=7), clear=(True, True))
        self.assertEqual(result['events'][:3],
                         [('clear', 204), ('clear', 188), ('sound', 191)])
        self.assertEqual(result['mob'], rock(x=202, state=8))

    def test_clear_space_stops_only_from_control_eight_upwards(self):
        for state in (8, 9, 99, 101, 32767):
            result = self.step(rock(state=state), clear=(True, True), pending=192)
            self.assertEqual(result['mob'], rock(state=0))
            self.assertEqual(result['events'], [('clear', 204), ('stop', 192)])
            self.assertEqual(result['pending'], -1)

    def test_only_matching_pending_cue_is_explicitly_cleared_on_space_stop(self):
        for pending in (-1, 191, 192, 193):
            result = self.step(rock(state=8), clear=(True, False), pending=pending)
            self.assertEqual(result['pending'], -1 if pending == 192 else pending)

    def test_negative_candidate_wraps_to_left_room_without_reanchoring(self):
        result = self.step(rock(x=0))
        self.assertEqual(result['mob'], (508, 236, 3, 0, -2, 6, 1, 459))
        self.assertEqual(result['events'][0], ('cell', 3, 9, 1))

    def test_missing_left_room_marks_removal_but_does_not_commit_x(self):
        result = motion_reference(rock(x=1), 0, pending=192)
        self.assertEqual(result, dict(mob=(1, 236, 0, -1, -2, 6, 1, 459),
                                     events=[('stop', 192)], pending=192))

    def test_removed_mark_is_not_an_entry_guard_in_motion_helper(self):
        result = self.step(rock(mark=-1))
        self.assertEqual(result['mob'], rock(x=202, mark=-1))

    def test_front_column_has_explicit_nonpositive_boundary_adjustment(self):
        for x, column in ((32, -1), (33, -1), (34, 0)):
            self.assertEqual(self.step(rock(x=x))['events'][0], ('cell', 2, column, 1))

    def test_wall_or_tile_four_sets_one_step_marker_and_y_minus_one(self):
        for tile in (2, 4, 7, 20, 25, 43):
            result = self.step(rock(x=58), tiles=(1, tile))
            self.assertEqual(result['mob'], rock(x=56, y=235, mark=1))
            self.assertIn(('query', 193), result['events'])
            self.assertIn(('sound', 18), result['events'])
        for tile in (0, 1, 49):
            self.assertEqual(self.step(rock(x=58), tiles=(1, tile))['mob'], rock(x=56))

    def test_front_tile_two_sets_marker_but_suppresses_sound_eighteen(self):
        result = self.step(rock(x=58), tiles=(2, 1))
        self.assertEqual(result['mob'], rock(x=56, y=235, mark=1))
        self.assertIn(('query', 193), result['events'])
        self.assertNotIn(('sound', 18), result['events'])
        self.assertNotIn(('sound', 18), self.step(
            rock(x=58), tiles=(1, 4), cue193_on=True)['events'])

    def test_nonzero_other_mark_does_not_start_wall_marker(self):
        for mark in (-1, 2):
            result = self.step(rock(x=58, mark=mark), tiles=(2, 4))
            self.assertEqual(result['mob'], rock(x=56, mark=mark))
            self.assertNotIn(('query', 193), result['events'])

    def test_mark_one_finalizes_to_hundred_with_x_correction_and_y_restore(self):
        result = self.step(rock(x=56, y=235, mark=1), tiles=(2, 4), pending=192)
        self.assertEqual(result['mob'], rock(x=57, state=100))
        self.assertEqual(result['events'], [('cell', 2, 0, 1),
                                           ('actor', '5:3cee'), ('stop', 192)])
        self.assertEqual(result['pending'], 192)
        self.assertEqual(self.step(result['mob'])['events'], [])

    def test_actor_reevaluation_admission_has_inclusive_frame_and_position_gates(self):
        for frame in (-1, 0, 86, 87, 99, 100):
            result = self.step(rock(x=65), prince=(frame, 1, 2))
            self.assertEqual(('actor', '6:1a84') in result['events'], 87 <= frame <= 99)
        for prince in ((87, 0, 2), (87, 1, 1), (87, 2, 2), (99, 1, 3)):
            self.assertNotIn(('actor', '6:1a84'),
                             self.step(rock(x=65), prince=prince)['events'])

    def test_y_words_wrap_at_native_signed_limits(self):
        self.assertEqual(self.step(rock(x=58, y=-32768), tiles=(1, 4))['mob'][1], 32767)
        self.assertEqual(self.step(rock(mark=1, y=32767))['mob'][1], -32768)

    def test_invalid_fixture_domains_fail_closed(self):
        for mob, left in (((1, 2), 3), (rock(x=-1), 3), (rock(x=562), 3),
                          ((1, 2, 0, 0, 2, 6, 1, 3), 3), (rock(), 33)):
            with self.assertRaises(ValueError):
                motion_reference(mob, left)
        with self.assertRaises(ValueError):
            self.step(prince=(32768, 0, 0))


if __name__ == '__main__':
    unittest.main()
