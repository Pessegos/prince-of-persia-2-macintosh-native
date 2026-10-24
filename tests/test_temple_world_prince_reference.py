import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_world_prince import CallerInputs, EDGE_SOURCES, gravity_reference, world_reference


CLIPS = {47: (-7, 5, -5, -16, 50, 51, 52, -1, 2), 2: (-7, 0, 15, -1, 2),
         9: (-7, 2, 91, -1, 210), 210: (90, 89, 88, 87)}


class TempleWorldPrinceTests(unittest.TestCase):
    def state(self, *, room=3, phase=1, position=3, countdown=-2):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 2 * 60 + 2 * 2, 4)
        struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, position)
        actor = bytearray(actor_fixture(room, 1, 2, -1, 2))
        for field, value in ((4, 400), (6, 100), (10, 91), (18, 0), (20, 0), (28, -1),
                              (30, 3), (34, 0), (36, 3), (38, 9), (40, 9), (58, -1)):
            put_actor(actor, field, value)
        return dict(initial_state(level, ((2, 3, phase, 4),)), prince=bytes(actor), working=bytes(range(62)),
                    countdown=countdown, saved_edges=(11, 13, 17, 19), view=3, exit_flag=1234, result=-2)

    def run_world(self, state=None, inputs=None):
        return world_reference(self.state() if state is None else state, CLIPS,
                               CallerInputs() if inputs is None else inputs)

    def test_real_caller_order_is_bank_then_prince_then_opponents(self):
        result = self.run_world()
        names = [event[0] for event in result['events']]
        self.assertLess(names.index('bank'), names.index('prince'))
        self.assertLess(names.index('prince'), names.index('opponents'))
        self.assertLess(names.index('controls'), names.index('animate'))
        self.assertLess(names.index('pressure'), names.index('prince_copy'))
        self.assertEqual((actor_word(result['prince'], 16), actor_word(result['prince'], 10)), (5, 50))
        self.assertEqual(result['prince'], result['working'])
        self.assertEqual(result['saved_edges'], EDGE_SOURCES)

    def test_suppression_keeps_selected47_unexecuted_and_returns_world_minus_two(self):
        result = self.run_world(inputs=CallerInputs(suppress_animation=1))
        self.assertEqual(tuple(actor_word(result['prince'], i) for i in (10, 16, 36, 38)), (91, 2, 0, 47))
        self.assertNotIn('animate', [e[0] for e in result['events']])
        self.assertIn(('environment',), result['events'])
        self.assertEqual(result['result'], -2)

    def test_control_minus_one_returns_after_gate_and_prince_copy_without_opponents(self):
        result = self.run_world(inputs=CallerInputs(control_result=-1))
        self.assertEqual(result['trobs'], ())
        self.assertEqual(actor_word(result['prince'], 38), 47)
        self.assertEqual(result['result'], -1)
        names = [e[0] for e in result['events']]
        self.assertNotIn('animate', names)
        self.assertNotIn('opponents', names)
        self.assertIn('prince_copy', names)

    def test_not_live_skips_objects_and_actor_animation_but_still_runs_controls(self):
        state = self.state()
        result = self.run_world(state, CallerInputs(live=0))
        self.assertEqual(result['trobs'], state['trobs'])
        self.assertEqual(result['prince'], state['prince'])
        self.assertEqual(result['saved_edges'], state['saved_edges'])
        names = [e[0] for e in result['events']]
        self.assertIn('controls', names)
        self.assertNotIn('bank', names)
        self.assertNotIn('animate', names)

    def test_room0_uses_outside_fall_service_and_not_the_ordinary_clip_path(self):
        state = self.state(room=0, countdown=0)
        result = self.run_world(state)
        self.assertEqual(actor_word(result['prince'], 38), 47)
        self.assertIn(('outside_fall',), result['events'])
        self.assertNotIn('animate', [e[0] for e in result['events']])
        self.assertEqual(result['countdown'], 0)
        self.assertEqual(result['saved_edges'], state['saved_edges'])
        self.assertIn(('generators', 3), result['events'])

    def test_invulnerability_skips_hit_and_strike_services_but_not_pressure_or_start(self):
        result = self.run_world(inputs=CallerInputs(invulnerable=1))
        names = {e[0] for e in result['events']}
        self.assertTrue({'pressure', 'spikes', 'temple_hazard', 'scythe_start'} <= names)
        self.assertFalse({'strike', 'stab', 'hit_hazard', 'scythe_hit'} & names)

    def test_cut_and_timeout_returns_have_distinct_clock_paths(self):
        cut = self.run_world(inputs=CallerInputs(prep_result=7))
        self.assertEqual(cut['result'], 7)
        self.assertNotIn(('clock',), cut['events'])
        timeout = self.run_world(inputs=CallerInputs(time_left=0))
        self.assertEqual((timeout['result'], timeout['exit_flag']), (-1, 0))
        self.assertIn(('clock',), timeout['events'])
        self.assertIn(('timeout',), timeout['events'])

    def test_only_minus_one_control_result_skips_the_ordinary_animation(self):
        result = self.run_world(inputs=CallerInputs(control_result=7))
        self.assertIn(('animate', 47, 0), result['events'])
        self.assertEqual(result['result'], -2)

    def test_countdown_checks_saved_mode_before_copying_the_current_mode(self):
        state = self.state(phase=2, position=80, countdown=0)
        result = self.run_world(state, CallerInputs(force_mode=4))
        self.assertEqual(actor_word(result['prince'], 16), 4)
        self.assertIn(('audio', 110), result['events'])
        self.assertEqual(result['countdown'], -2)

    def test_positive_countdown_decrements_and_mode4_saved_state_can_suppress_cue(self):
        state = self.state(phase=2, position=80, countdown=1)
        first = self.run_world(state, CallerInputs(force_mode=4))
        second = self.run_world(first, CallerInputs(force_mode=4))
        self.assertEqual((first['countdown'], second['countdown']), (0, -1))
        self.assertNotIn(('audio', 110), second['events'])

    def test_gravity_and_vertical_movement_are_separate_and_float_halves_signed_x(self):
        state = self.state(phase=2, position=80)
        actor = bytearray(state['prince'])
        put_actor(actor, 16, 4)
        put_actor(actor, 18, -3)
        plain, _ = gravity_reference(actor, False)
        floating, _ = gravity_reference(actor, True)
        self.assertEqual(tuple(actor_word(plain, i) for i in (4, 6, 20)), (403, 106, 6))
        self.assertEqual(tuple(actor_word(floating, i) for i in (4, 6, 20)), (402, 102, 2))

    def test_vertical_threshold_prevents_motion_but_not_velocity_update(self):
        actor = bytearray(self.state()['prince'])
        for field, value in ((6, 3650), (16, 4), (20, 62)):
            put_actor(actor, field, value)
        result, events = gravity_reference(actor, False)
        self.assertEqual((actor_word(result, 6), actor_word(result, 20)), (3650, 63))
        self.assertNotIn(('frame',), events)


if __name__ == '__main__':
    unittest.main()
