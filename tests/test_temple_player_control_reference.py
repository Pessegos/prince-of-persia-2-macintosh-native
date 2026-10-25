from dataclasses import replace
import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_player_control import PlayerInputs, normalize_latches, player_reference
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_world_prince import world_reference


CLIPS = {2: (-7, 0, 15), 9: (-7, 2, 91, -1, 210), 210: (90, 89, 88),
         47: (-7, 5, -5, -16, 50), 10: (-7, 1, 135), 11: (81,),
         23: (-7, 3, 81), 25: (-7, 6, 92), 73: (135,), 99: (-7, 3, 81)}


class TemplePlayerControlTests(unittest.TestCase):
    def state(self, inputs, *, facing=-1, room=3):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 2 * 60 + 2 * 2, 4)
        struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, 3)
        actor = bytearray(actor_fixture(room, 1, 2, facing, 2))
        for field, value in ((4, 400), (6, 100), (10, 91), (18, 0), (20, 0), (24, -1), (26, 0),
                              (28, -1), (30, 3), (34, 0), (36, 3), (38, 9), (40, 9), (52, 0), (58, -1)):
            put_actor(actor, field, value)
        return dict(initial_state(level, ((2, 3, 1, 4),)), prince=bytes(actor), working=bytes(range(62)),
                    countdown=-2, saved_edges=(11, 13, 17, 19), view=3, exit_flag=1234, result=-2,
                    cooldown=inputs.cooldown, input_latches=inputs.previous_latches,
                    working_latches=(31, 37, 41, 43, 47), raw_axes=(53, 59, 61), cell_cache=bytes(range(12)))

    def world(self, inputs=None, **kwargs):
        inputs = PlayerInputs() if inputs is None else inputs
        return world_reference(self.state(inputs, **kwargs), CLIPS, inputs, player_reference)

    def test_complete_order_keeps_controls_between_gate_and_actor_animation(self):
        result = self.world()
        names = [e[0] for e in result['events']]
        for first, second in (('bank', 'player_ctrl'), ('player_ctrl', 'prepare_controls'),
                              ('restore_latches', 'sample_input'), ('sample_input', 'normalize_latches'),
                              ('orient_controls', 'gen_ctrl'), ('gen_ctrl', 'save_latches'),
                              ('save_latches', 'animate'), ('animate', 'prince_copy')):
            self.assertLess(names.index(first), names.index(second))
        self.assertEqual(tuple(actor_word(result['prince'], i) for i in (4, 10, 16, 40)), (416, 50, 5, 47))

    def test_cooldown1_allows_climb_in_same_update_after_decrement(self):
        one = self.world(PlayerInputs(raw_axes=(0, -1, -1), cooldown=1))
        two = self.world(PlayerInputs(raw_axes=(0, -1, -1), cooldown=2))
        self.assertEqual((one['cooldown'], actor_word(one['prince'], 40)), (0, 10))
        self.assertEqual((two['cooldown'], actor_word(two['prince'], 40)), (1, 47))
        self.assertNotIn(('climb',), two['events'])

    def test_negative_cooldown_is_decremented_not_clamped(self):
        result = self.world(PlayerInputs(raw_axes=(0, -1, -1), cooldown=-1))
        self.assertEqual(result['cooldown'], -2)
        self.assertNotIn(('climb',), result['events'])

    def test_consumed_direction_stays_consumed_while_held_then_releases(self):
        self.assertEqual(normalize_latches((0, 0, 1, 0, 1), (0, -1, -1)), (0, 0, 1, 0, 1))
        self.assertEqual(normalize_latches((0, 0, 1, 0, 1), (0, 0, 0)), (0, 0, 0, 0, 0))
        self.assertEqual(normalize_latches((0, 0, 0, 0, 0), (0, -1, -1)), (0, 0, -1, 0, -1))

    def test_hanging_climb_accepts_consumed_up_because_it_tests_nonzero(self):
        inputs = PlayerInputs(raw_axes=(0, -1, -1), previous_latches=(0, 0, 1, 0, 1))
        result = self.world(inputs)
        self.assertIn(('climb',), result['events'])
        self.assertEqual(actor_word(result['prince'], 40), 10)

    def test_negative_direction_latches_survive_contradictory_sample(self):
        self.assertEqual(normalize_latches((-1, -2, -1, -2, -1), (1, 0, 0)), (-1, -2, -1, -2, 0))

    def test_second_held_action_uses_separate_consumed_state(self):
        self.assertEqual(normalize_latches((0, 0, 0, 0, 2), (0, 0, -2))[-1], 2)
        self.assertEqual(normalize_latches((0, 0, 0, 0, 1), (0, 0, -2))[-1], -2)
        self.assertEqual(normalize_latches((0, 0, 0, 0, 2), (0, 0, -1))[-1], -1)

    def test_restore_uses_saved_bank_not_working_canary(self):
        result = self.world(PlayerInputs(previous_latches=(0, 0, 0, 0, 0)))
        self.assertEqual(result['input_latches'], (0, 0, 0, 0, -1))
        self.assertEqual(result['input_latches'], result['working_latches'])

    def test_facing_flips_controls_before_genctrl_and_back_before_save(self):
        result = self.world(facing=0)
        names = [e[0] for e in result['events']]
        flips = [i for i, name in enumerate(names) if name == 'flip_horizontal']
        self.assertEqual(len(flips), 2)
        self.assertLess(flips[0], names.index('gen_ctrl'))
        self.assertLess(names.index('gen_ctrl'), flips[1])
        self.assertEqual(result['raw_axes'], (0, 0, -1))

    def test_vertical_flip_changes_climb_admission_and_restores_axes(self):
        inputs = PlayerInputs(raw_axes=(0, -1, -1))
        ordinary = self.world(inputs)
        flipped = self.world(replace(inputs, vertical_flip=1))
        self.assertIn(('climb',), ordinary['events'])
        self.assertNotIn(('climb',), flipped['events'])
        self.assertEqual(flipped['raw_axes'], inputs.raw_axes)

    def test_context_change_clears_sampled_directions_but_not_held(self):
        inputs = PlayerInputs(raw_axes=(1, -1, -1), matching_context=False)
        result = self.world(inputs)
        self.assertEqual(result['raw_axes'], (0, 0, -1))
        self.assertNotIn(('climb',), result['events'])
        self.assertEqual(actor_word(result['prince'], 40), 47)

    def test_source59_clears_sampled_axes_without_erasing_pending_negative_latch(self):
        inputs = PlayerInputs(raw_axes=(1, -1, -1), previous_latches=(0, 0, -1, 0, 0))
        state = self.state(inputs)
        actor = bytearray(state['prince'])
        put_actor(actor, 40, 59)
        result = player_reference(actor, CLIPS, inputs, state)
        self.assertEqual(result['updates']['raw_axes'], (0, 0, -1))
        self.assertIn(('climb',), result['events'])

    def test_release_preview_effects_survive_into_actual_prince_save(self):
        result = self.world(PlayerInputs(raw_axes=(0, 0, 0), current=0, front=9))
        self.assertEqual(tuple(actor_word(result['prince'], i) for i in (4, 10, 16, 40)), (416, 81, 3, 99))
        self.assertEqual(result['prince'], result['working'])
        self.assertIn(('preview',), result['events'])
        self.assertIn(('prince_copy',), result['events'])

    def test_animation_suppression_does_not_skip_controller_or_latch_save(self):
        result = self.world(PlayerInputs(raw_axes=(0, -1, -1), suppress_animation=1))
        self.assertEqual((actor_word(result['prince'], 40), actor_word(result['prince'], 16)), (10, 2))
        self.assertNotIn('animate', [e[0] for e in result['events']])
        self.assertEqual(result['input_latches'], (0, 0, 1, 0, 1))

    def test_room0_still_prepares_controls_but_skips_ordinary_clip(self):
        result = self.world(PlayerInputs(raw_axes=(1, -1, -1)), room=0)
        self.assertEqual(result['raw_axes'], (0, 0, -1))
        self.assertIn(('player_ctrl',), result['events'])
        self.assertIn(('outside_fall',), result['events'])
        self.assertNotIn('animate', [e[0] for e in result['events']])

    def test_wrong_latch_sizes_and_dead_controller_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_latches((0,), (0, 0, 0))
        inputs = PlayerInputs()
        state = self.state(inputs)
        actor = bytearray(state['prince'])
        put_actor(actor, 24, 0)
        with self.assertRaises(ValueError):
            player_reference(actor, CLIPS, inputs, state)


if __name__ == '__main__':
    unittest.main()
