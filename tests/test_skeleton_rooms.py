from copy import deepcopy
import unittest

from pop2.combat import select_sequence
from pop2.skeleton import SkeletonRoomRecord
from pop2.terrain import TerrainMotion
import tests.test_skeletons as fixtures


class SkeletonRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SkeletonTests.setUpClass()
        cls.fixture = fixtures.SkeletonTests()

    def encounter(self):
        return self.fixture.encounter(14)

    def test_room_save_distinguishes_living_restart_from_carried_and_dead_cursor(self):
        for living, restart in ((False, False), (False, True), (True, False), (True, True)):
            with self.subTest(living=living, restart=restart):
                _, _combat, actor = self.encounter()
                select_sequence(actor, 227 if living else 119)
                actor.runtime.next_frame()
                actor.life, actor.sword_drawn = (2, True) if living else (0, False)
                cursor, state = actor.state.cursor, deepcopy(vars(actor.state))
                actor.skeleton.store_room(actor, restart_living=restart)
                self.assertEqual(actor.skeleton.room_record, SkeletonRoomRecord(
                    actor.state.sequence_id, 0 if living and restart else cursor,
                    actor.life, actor.sword_drawn))
                self.assertEqual(vars(actor.state), state)

    def test_native_alive_word_can_require_restart_even_when_health_is_zero(self):
        _, _combat, actor = self.encounter()
        actor.life = 0
        actor.skeleton.native_alive = True
        actor.skeleton.store_room(actor, restart_living=True)
        self.assertEqual(actor.skeleton.room_record.cursor, 0)
        actor.skeleton.native_alive = False
        actor.skeleton.store_room(actor, restart_living=True)
        self.assertEqual(actor.skeleton.room_record.cursor, actor.state.cursor)

    def test_zero_cursor_load_uses_marker_and_bank_slot_not_saved_combat_pose(self):
        for marker, slot, sequence, pose, life, armed in (
                (0, 0, 112, 207, 0, False), (0, 1, 119, 206, 0, False),
                (-1, 0, 119, 206, 0, False), (1, 0, 63, 229, 3, True)):
            with self.subTest(marker=marker, slot=slot):
                _, _combat, actor = self.encounter()
                actor.skeleton.marker = marker
                actor.skeleton.room_record = SkeletonRoomRecord(227, 0, 2, True)
                self.assertTrue(actor.skeleton.restore_room(actor, slot))
                self.assertEqual((actor.selected_sequence, actor.state.action, actor.life,
                                  actor.sword_drawn), (sequence, pose, life, armed))
                self.assertIsNone(actor.skeleton.room_record)

    def test_active_marker_preserves_existing_timer_and_shakes(self):
        _, _combat, actor = self.encounter()
        actor.skeleton.marker, actor.skeleton.timer, actor.skeleton.shakes = 1, 99, 2
        actor.skeleton.room_record = SkeletonRoomRecord(227, 0, 1, False)
        actor.skeleton.restore_room(actor, 0)
        self.assertEqual((actor.life, actor.skeleton.timer, actor.skeleton.shakes), (3, 99, 2))

    def test_reloaded_heap_clears_timer_but_preserves_remaining_shakes(self):
        _, _combat, actor = self.encounter()
        actor.skeleton.timer, actor.skeleton.shakes = 87, 2
        actor.skeleton.room_record = SkeletonRoomRecord(119, 1, 0, False)
        actor.skeleton.restore_room(actor, 0)
        self.assertEqual((actor.state.action, actor.skeleton.timer, actor.skeleton.shakes), (206, 0, 2))
        self.assertEqual((actor.life, actor.skeleton.phase), (0, 'dormant'))
        self.assertFalse(actor.skeleton.native_alive)

    def test_reload_advances_past_stored_pose_and_restores_current_not_selected_sequence(self):
        _, _combat, actor = self.encounter()
        select_sequence(actor, 227)
        actor.runtime.next_frame()
        actor.state.selected_sequence_id = 88
        actor.life, actor.sword_drawn = 2, True
        actor.skeleton.store_room(actor, restart_living=False)
        actor.skeleton.restore_room(actor, 0)
        self.assertEqual((actor.state.source_sequence_id, actor.state.action,
                          actor.life, actor.sword_drawn), (227, 170, 2, True))
        self.assertEqual(actor.skeleton.phase, 'active')

    def test_mid_shake_reload_preserves_native_alive_gate_and_does_not_decrement_dead_timer(self):
        _, combat, actor = self.encounter()
        actor.skeleton.timer = 37
        actor.skeleton.room_record = SkeletonRoomRecord(112, 5, 0, False)
        actor.skeleton.restore_room(actor, 0)
        self.assertEqual((actor.state.action, actor.life, actor.skeleton.native_alive), (208, 0, True))
        combat.player.state.target_x = actor.state.target_x - 51
        self.assertFalse(actor.skeleton.can_wake(combat, actor))
        actor.skeleton.control(combat, actor)
        self.assertEqual(actor.skeleton.timer, 37)

    def test_reload_discards_stale_control_events_and_resets_floor_and_velocity(self):
        _, _combat, actor = self.encounter()
        actor.state.current_y, actor.state.sequence_mode = -27, 13
        actor.state.horizontal_velocity = actor.state.vertical_velocity = 10
        actor.state.sound_events[:] = [99]
        actor.state.sequence_events[:] = [(-10, (99,))]
        actor.alert_mode, actor.recovering, actor.contact_consumed = 3, True, True
        actor.terrain_motion = TerrainMotion(actor.room, actor.row, falling=True, dead=True)
        actor.skeleton.room_record = SkeletonRoomRecord(119, 1, 0, False)
        actor.skeleton.restore_room(actor, 0)
        self.assertEqual((actor.state.current_y, actor.state.animation_state,
                          actor.state.horizontal_velocity, actor.state.vertical_velocity,
                          actor.state.sequence_mode), (0, 1, 0, 0, 0))
        self.assertEqual((actor.alert_mode, actor.recovering, actor.contact_consumed), (0, False, False))
        self.assertEqual((actor.state.sound_events, actor.state.sequence_events), ([], []))
        self.assertFalse(actor.terrain_motion.dead or actor.terrain_motion.falling)

    def test_living_reload_clears_native_approach_and_attack_pause_but_not_parry_timer(self):
        _, combat, actor = self.encounter()
        actor.skeleton.marker = 1
        actor.life, actor.sword_drawn = 3, True
        select_sequence(actor, 227)
        actor.runtime.next_frame()
        combat.enter_room(0, 2)
        combat.advance_pause, combat.attack_pause, combat.parry_timer = 15, 9, 4
        combat.player.state.callback_flag = 1
        combat.enter_room(14, 2)
        self.assertEqual((combat.advance_pause, combat.attack_pause, combat.parry_timer), (0, 0, 4))
        self.assertEqual(combat.player.state.callback_flag, 0)

    def test_dead_reload_does_not_clear_shared_combat_pauses(self):
        _, combat, actor = self.encounter()
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        combat.enter_room(0, 2)
        combat.advance_pause, combat.attack_pause, combat.parry_timer = 15, 9, 4
        combat.enter_room(14, 2)
        self.assertEqual((combat.advance_pause, combat.attack_pause, combat.parry_timer), (15, 9, 4))

    def test_same_room_refresh_does_not_create_or_consume_a_room_record(self):
        _, combat, actor = self.encounter()
        before = deepcopy(vars(actor.state))
        combat.enter_room(14, 2)
        self.assertEqual(vars(actor.state), before)
        self.assertIsNone(actor.skeleton.room_record)

    def test_repeated_departures_keep_one_actor_and_do_not_replay_old_sounds(self):
        _, combat, actor = self.encounter()
        actor.state.target_x = actor.state.current_x = 300
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        actor.state.sound_events[:] = [61]
        for _ in range(20):
            combat.enter_room(16, 2)
            record = deepcopy(actor.skeleton.room_record)
            self.fixture.tick(combat, 3)
            self.assertEqual(actor.skeleton.room_record, record)
            combat.enter_room(14, 2)
            self.assertIs(combat.guards[0], actor)
            self.assertEqual(actor.state.sound_events, [])
            self.assertEqual(sum(g is actor for guards, _ in combat.room_encounters.values()
                                 for g in guards), 1)

    def test_terminal_skeleton_records_are_removed_and_do_not_respawn_on_revisit(self):
        for special, sequence in ((4, 119), (5, 119), (0, 154), (0, 196)):
            with self.subTest(special=special, sequence=sequence):
                _, combat, actor = self.encounter()
                actor.state.sequence_mode = special
                actor.state.selected_sequence_id = sequence
                combat.enter_room(0, 2)
                combat.enter_room(14, 2)
                self.assertNotIn(actor, combat.guards)
                self.assertEqual(combat.guards, [])

    def test_normal_bones_are_not_treated_as_terminal(self):
        _, combat, actor = self.encounter()
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        combat.enter_room(0, 2)
        combat.enter_room(14, 2)
        self.assertIs(combat.guards[0], actor)
        self.assertEqual(actor.state.action, 206)
