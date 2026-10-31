"""Resource-independent ordinary guard save/reload contracts."""

from types import SimpleNamespace
import unittest

from pop2.opponent_records import GuardRoomRecord, removed_on_room_save
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import TerrainMotion


class GuardRecordTests(unittest.TestCase):
    def actor(self):
        sequences = {77: (-7, 1, 166, -23), 22: (185, -23), 195: (228, -23),
                     227: (158, 170, 171, -23), 100: (-6, -3, 205, -23),
                     186: (-6, 7, 219, -23)}
        state = SequenceState(227, action=171, cursor=3, actor_type=2, level_kind=5,
                              current_x=300, target_x=300, facing=1)
        return SimpleNamespace(runtime=SequenceRuntime(sequences, state), state=state,
                               row=1, room=3, life=2, max_life=3, sword_drawn=True,
                               selected_sequence=227, native_alive=None, guard_record=None,
                               terrain_motion=TerrainMotion(3, 1, falling=True))

    def test_living_save_clears_cursor_without_replacing_generator_header(self):
        actor = self.actor()
        actor.guard_record = GuardRoomRecord(100, 8, 2, True, height=150, pending=False)
        record = GuardRoomRecord.capture(actor, restart_living=True, cell=12)
        self.assertEqual((record.sequence, record.cursor, record.height, record.cell), (100, 0, 150, 12))
        record.restore(actor, 0)
        self.assertEqual((actor.state.sequence_id, actor.life, actor.state.current_y), (77, 3, -76))
        self.assertFalse(actor.sword_drawn)

    def test_nonzero_cursor_restores_current_resource_and_saved_health(self):
        actor = self.actor()
        actor.guard_record = GuardRoomRecord(77, 0, 3, False, pending=False)
        record = GuardRoomRecord.capture(actor, restart_living=False, cell=12)
        self.assertEqual((record.sequence, record.cursor), (227, 3))
        self.assertTrue(record.restore(actor, 0))
        self.assertEqual((actor.state.action, actor.life, actor.sword_drawn), (171, 2, True))
        self.assertTrue(actor.native_alive)
        self.assertFalse(record.restore(actor, 0))

    def test_zero_hp_live_pose_stays_native_alive_until_control_registration(self):
        actor = self.actor()
        GuardRoomRecord(227, 3, 0, True, 12).restore(actor, 0)
        self.assertEqual((actor.life, actor.state.action, actor.native_alive, actor.death_registered),
                         (0, 171, True, False))

    def test_save_before_zero_hp_control_uses_the_still_living_native_word(self):
        actor = self.actor()
        actor.life, actor.native_alive = 0, True
        actor.guard_record = GuardRoomRecord(77, 0, 3, False, pending=False)
        record = GuardRoomRecord.capture(actor, restart_living=True, cell=12)
        self.assertEqual((record.cursor, record.life), (0, 0))
        record.restore(actor, 0)
        self.assertEqual((actor.life, actor.selected_sequence), (3, 77))

    def test_cold_corpse_and_alternate_slot_do_not_resurrect(self):
        for slot in range(5):
            actor = self.actor()
            GuardRoomRecord(22, 0, 3, False, 12).restore(actor, slot)
            self.assertEqual((actor.life, actor.native_alive, actor.death_registered), (0, False, True))
            self.assertEqual(actor.state.action, 228 if slot % 2 else 185)
        actor = self.actor()
        actor.state.level_kind = 6
        GuardRoomRecord(22, 0, 3, False, 12).restore(actor, 1)
        self.assertEqual(actor.state.action, 185)

    def test_only_resource100_reloads_saved_absolute_height(self):
        for sequence, delta, expected in ((100, -3, -79), (186, 7, 7), (77, 0, 0)):
            actor = self.actor()
            actor.runtime.sequences[sequence] = (171, -6, delta, 171, -23)
            GuardRoomRecord(sequence, 1, 2, True, 12, 150).restore(actor, 0)
            self.assertEqual(actor.state.current_y, expected)

    def test_height_save_uses_selected_history_and_keeps_untouched_metadata(self):
        for source in (77, 100, 186, 227):
            for update in (False, True):
                actor = self.actor()
                actor.guard_record = GuardRoomRecord(77, 0, 3, False, height=99)
                actor.state.selected_sequence_id, actor.state.current_y = source, -30
                record = GuardRoomRecord.capture(actor, restart_living=False, update_height=update)
                self.assertEqual(record.height, 196 if update and source in (100, 186) else 99)

    def test_negative_exact_tenth_cell_and_stale_motion_flags(self):
        actor = self.actor()
        actor.state.sequence_mode, actor.state.horizontal_velocity = 5, 27
        actor.state.sound_events.append(61)
        GuardRoomRecord(227, 3, 2, True, -10).restore(actor, 0)
        self.assertEqual((actor.row, actor.state.current_y, actor.state.animation_state), (-2, 0, 1))
        self.assertEqual((actor.state.sequence_mode, actor.state.horizontal_velocity, actor.state.sound_events), (0, 0, []))
        self.assertFalse(actor.terrain_motion.falling)
        self.assertEqual(actor.terrain_motion.row, -2)

    def test_terminal_record_removal_is_independent_of_health(self):
        for flag, source, expected in ((0, 227, False), (4, 227, True), (5, 227, True),
                                       (0, 154, True), (0, 196, True)):
            actor = self.actor()
            actor.state.sequence_mode, actor.state.selected_sequence_id = flag, source
            self.assertEqual(removed_on_room_save(actor), expected)


if __name__ == '__main__':
    unittest.main()
