"""AnimCharTap's silent player signal and its standing-guard consumer."""

import unittest

from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceRuntime, SequenceState


class SilentCallbackTests(unittest.TestCase):
    def test_silent_player_callback_sets_noise_without_a_footstep(self):
        for kind in (None, 1, 3, 5, 6):
            with self.subTest(kind=kind):
                state = SequenceState(1, actor_type=0, level_kind=kind, callback_counter=99)
                frame = SequenceRuntime({1: (-15, 0, 171)}, state).next_frame()
                self.assertEqual((frame.action, state.callback_flag, state.callback_counter), (171, 1, 99))
                self.assertEqual(state.sound_events, [])

    def test_other_actor_types_do_not_raise_or_clear_the_player_signal(self):
        for actor in range(1, 13):
            for flag in (0, 1, 7):
                state = SequenceState(1, actor_type=actor, callback_flag=flag, callback_counter=9)
                SequenceRuntime({1: (-15, 0, 171)}, state).next_frame()
                self.assertEqual((state.callback_flag, state.callback_counter, state.sound_events), (flag, 9, []))

    def test_silent_callback_preserves_pending_sound_and_sequence_events(self):
        state = SequenceState(1, actor_type=0, sound_events=[30], sequence_events=[(-13, ())])
        SequenceRuntime({1: (-15, 0, 171)}, state).next_frame()
        self.assertEqual(state.callback_flag, 1)
        self.assertEqual(state.sound_events, [30])
        self.assertEqual(state.sequence_events, [(-13, ())])

    def test_repeated_silent_callbacks_are_idempotent(self):
        state = SequenceState(1, actor_type=0, callback_counter=17)
        SequenceRuntime({1: (-15, 0, -15, 0, 171)}, state).next_frame()
        self.assertEqual((state.callback_flag, state.callback_counter, state.sound_events), (1, 17, []))

    def test_peeking_does_not_signal_movement_before_the_frame_is_consumed(self):
        runtime = SequenceRuntime({1: (-15, 0, 171)}, SequenceState(1, actor_type=0))
        self.assertEqual(runtime.peek_frame().action, 171)
        self.assertEqual((runtime.state.cursor, runtime.state.callback_flag), (0, 0))
        runtime.next_frame()
        self.assertEqual(runtime.state.callback_flag, 1)

    def test_terminal_hold_does_not_repeat_a_consumed_signal(self):
        runtime = SequenceRuntime({1: (-15, 0, 171, -23)}, SequenceState(1, actor_type=0))
        runtime.next_frame()
        self.assertEqual(runtime.state.callback_flag, 1)
        runtime.state.callback_flag = 0
        for _ in range(10):
            self.assertEqual(runtime.next_frame().action, 171)
            self.assertEqual(runtime.state.callback_flag, 0)

    def test_audible_footsteps_keep_their_counter_sound_and_actor_gating(self):
        for actor in (0, 2, 4):
            state = SequenceState(1, actor_type=actor, level_kind=5)
            SequenceRuntime({1: (-15, 1, 171)}, state).next_frame()
            self.assertEqual((state.callback_counter, state.callback_flag, state.sound_events),
                             (1, int(actor == 0), [0x127]))


@unittest.skipUnless((ASSET_DIR / 'enemy_profiles.json').is_file(), 'Imported enemy profiles required')
class SilentCallbackGuardTests(unittest.TestCase):
    def test_silent_combat_entry_turns_a_guard_and_last_unarmed_record_consumes_it(self):
        from pop2.combat import CombatEncounter, Fighter

        sequences = {227: (-15, 0, 158), 77: (166, -23), 80: (166, -23)}
        combat = CombatEncounter.__new__(CombatEncounter)
        combat.player = Fighter(SequenceRuntime(sequences, SequenceState(
            227, actor_type=0, target_x=150, current_x=150)), 3, 3, 0, 1)
        guard = Fighter(SequenceRuntime(sequences, SequenceState(
            77, actor_type=2, facing=1, target_x=250, current_x=250, action=166)),
            3, 3, 0, 1, selected_sequence=77)
        combat.guard, combat.guards, combat.level, combat.rooftop_escape = guard, [guard], b'', False
        combat.room_encounters = {0: ([guard], [])}
        combat.choose_guard_action(guard)
        self.assertEqual(guard.selected_sequence, 77)
        combat.player.runtime.next_frame()
        self.assertEqual(combat.player.state.callback_flag, 1)
        combat.choose_guard_action(guard)
        self.assertEqual(guard.selected_sequence, 80)
        self.assertEqual(combat.player.state.callback_flag, 0)
        self.assertEqual(combat.player.state.sound_events, [])


if __name__ == '__main__':
    unittest.main()
