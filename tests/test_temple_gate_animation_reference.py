import unittest

from tools.probe_temple_gate_animation import gate_animation_reference


class TempleGateAnimationTests(unittest.TestCase):
    def test_opening_moves_four_units_but_sound_requires_eight_unit_alignment(self):
        first = gate_animation_reference(0, 2)
        second = gate_animation_reference(first['foreground'], first['phase'])
        self.assertEqual((first['foreground'], first['events']), (4, [('redraw', 4, 2)]))
        self.assertEqual((second['foreground'], second['events']), (8, [('sound', 0x110), ('redraw', 8, 2)]))

    def test_normal_open_limit_redraws_old_state_before_storing237_and_holding(self):
        result = gate_animation_reference(180, 2)
        self.assertEqual((result['foreground'], result['phase']), (237, 0))
        self.assertEqual(result['events'], [('redraw', 180, 2), ('sound', 0x111)])

    def test_hold_delay_counts_helper_calls_and_changes_phase_only_below184(self):
        foreground, phase = 237, 0
        for _ in range(53):
            result = gate_animation_reference(foreground, phase)
            foreground, phase = result['foreground'], result['phase']
        self.assertEqual((foreground, phase, result['events']), (184, 0, [('redraw', 184, 0)]))
        result = gate_animation_reference(foreground, phase)
        self.assertEqual((result['foreground'], result['phase']), (183, 1))
        self.assertEqual(result['events'], [('sound', 0x110), ('redraw', 183, 1)])

    def test_permanent_open_limit_stops_at255_without_final_redraw(self):
        result = gate_animation_reference(180, 3)
        self.assertEqual((result['foreground'], result['phase']), (255, -1))
        self.assertEqual(result['events'], [('sound', 0x112), ('load_kid',)])

    def test_already_permanent_position_stops_any_nonnegative_phase_below4(self):
        for phase in range(4):
            result = gate_animation_reference(255, phase)
            self.assertEqual((result['foreground'], result['phase']), (255, -1))

    def test_fast_closing_increments_phase_before_selecting_step(self):
        result = gate_animation_reference(250, 4)
        self.assertEqual((result['foreground'], result['phase'], result['events']), (190, 5, []))
        result = gate_animation_reference(250, 5)
        self.assertEqual((result['foreground'], result['phase']), (170, 6))

    def test_terminal_fast_close_uses_supplied_relief_result_not_inferred_damage(self):
        for relief, countdown in ((False, 1234), (True, 4)):
            result = gate_animation_reference(120, 8, relief)
            self.assertEqual((result['foreground'], result['phase'], result['relief_countdown']), (0, -1, countdown))
            self.assertEqual(result['events'], [('relief_check',), ('sound', 0x113), ('redraw', 0, -1)])

    def test_normal_closing_stops_without_calling_fast_close_relief_predicate(self):
        result = gate_animation_reference(3, 1, True)
        self.assertEqual((result['foreground'], result['phase'], result['relief_countdown']), (0, -1, 1234))
        self.assertEqual(result['events'], [('sound', 0x112), ('load_kid',), ('redraw', 0, -1)])

    def test_decoration_high_byte_survives_motion_and_terminal_positions(self):
        for high in (0, 0x300, 0xff00):
            self.assertEqual(gate_animation_reference(high | 180, 2)['foreground'], high | 237)
            self.assertEqual(gate_animation_reference(high | 60, 4)['foreground'], high)

    def test_negative_phase_skips_motion_but_still_requests_redraw_below_threshold(self):
        result = gate_animation_reference(184, -1)
        self.assertEqual(result['events'], [('redraw', 184, -1)])
        self.assertEqual(gate_animation_reference(185, -1)['events'], [])

    def test_normal_open_hold_close_reaches_terminal_state_in_bounded_calls(self):
        foreground, phase = 180, 2
        calls = 0
        while phase >= 0 and calls < 200:
            result = gate_animation_reference(foreground, phase)
            foreground, phase = result['foreground'], result['phase']
            calls += 1
        self.assertEqual((foreground, phase, calls), (0, -1, 101))

    def test_out_of_scope_phase_and_foreground_are_rejected(self):
        for foreground, phase in ((0, 9), (0, -2), (-1, 2), (65536, 2)):
            with self.assertRaises(ValueError):
                gate_animation_reference(foreground, phase)


if __name__ == '__main__':
    unittest.main()
