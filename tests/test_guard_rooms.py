"""Ordinary active room banks and their cold/resumed records."""

import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'Guard.rsrc').is_file(), 'Imported guard resources required')
class GuardRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_rooftop_pursuit import RooftopPursuitTests

        RooftopPursuitTests.setUpClass()
        cls.fixture = RooftopPursuitTests()

    def actor(self, room=3, x=250, flags=0):
        from pop2.combat import select_sequence

        combat = self.fixture.encounter(room, player_x=150, running=False)
        actor = self.fixture.runner(combat, room, x, facing=1, flags=flags)
        select_sequence(actor, 227)
        actor.runtime.next_frame()
        actor.sword_drawn = True
        return combat, actor

    def test_non_selected_pursuer_freezes_until_its_room_is_loaded(self):
        combat, actor = self.actor()
        actor.pursuing = True
        combat.enter_room(31, 1)
        self.assertNotIn(actor, combat.active_guards())
        self.assertTrue(actor.guard_record.pending)
        before = dict(vars(actor.state))
        for _ in range(20):
            self.fixture.tick(combat)
        self.assertEqual(vars(actor.state), before)

    def test_living_in_bounds_revisit_keeps_identity_but_restarts_unarmed_at_full_life(self):
        combat, actor = self.actor()
        actor.life = 2
        combat.enter_room(31, 1)
        self.assertEqual(actor.guard_record.cursor, 0)
        combat.enter_room(3, 1)
        self.assertIs(combat.guards[0], actor)
        self.assertEqual((actor.life, actor.selected_sequence, actor.state.action), (3, 77, 166))
        self.assertFalse(actor.sword_drawn)
        self.assertFalse(actor.guard_record.pending)

    def test_same_room_refresh_does_not_heal_or_restart_live_animation(self):
        combat, actor = self.actor()
        actor.life = 2
        before = actor.state.sequence_id, actor.state.cursor, actor.state.action
        combat.enter_room(3, 1)
        self.assertEqual(actor.life, 2)
        self.assertEqual((actor.state.sequence_id, actor.state.cursor, actor.state.action), before)

    def test_armed_follower_uses_native_alive_word_until_zero_hp_control(self):
        from pop2.combat import opponent_follows_cut

        combat, actor = self.actor(x=450)
        actor.life, actor.native_alive = 0, True
        self.assertTrue(opponent_follows_cut(actor, 'right', 0))
        combat.choose_guard_action(actor)
        self.assertFalse(opponent_follows_cut(actor, 'right', 0))

    def test_zero_hp_resumed_pose_is_registered_on_control_not_during_reload(self):
        combat, actor = self.actor()
        actor.life, actor.native_alive = 0, False
        actor.runtime.next_frame()
        combat.enter_room(31, 1)
        self.assertGreater(actor.guard_record.cursor, 0)
        combat.enter_room(3, 1)
        self.assertEqual(actor.life, 0)
        self.assertTrue(actor.native_alive)
        self.assertFalse(actor.death_registered)
        combat.choose_guard_action(actor)
        self.assertFalse(actor.native_alive)
        self.assertTrue(actor.death_registered)

    def test_non_following_out_of_bounds_record_normalizes_to_real_room(self):
        combat, actor = self.actor(0, 560)
        combat.enter_room(31, 1)
        self.assertEqual((actor.room, actor.state.target_x), (2, 50))
        self.assertNotIn(actor, combat.room_encounters[0][0])
        self.assertIn(actor, combat.room_encounters[2][0])
        self.assertTrue(actor.guard_record.pending)
        self.assertEqual(sum(other is actor for guards, _ in combat.room_encounters.values()
                             for other in guards), 1)

    def test_current_room_records_precede_side_imports_and_cap_active_bank_at_five(self):
        combat = self.fixture.encounter(0, player_x=150, running=False)
        residents = [self.fixture.runner(combat, 0, 200 + i) for i in range(5)]
        side = self.fixture.runner(combat, 2, 20)
        self.assertEqual(combat.active_guards(), residents)
        self.assertNotIn(side, combat.active_guards())
        self.assertIsNone(side.bank_room)
        self.assertEqual([actor.bank_slot for actor in residents], list(range(5)))

    def test_side_import_keeps_membership_after_moving_away_from_import_threshold(self):
        combat = self.fixture.encounter(0, player_x=150, running=False)
        actor = self.fixture.runner(combat, 2, 20)
        self.assertIn(actor, combat.active_guards())
        actor.state.target_x = actor.state.current_x = 250
        self.assertIn(actor, combat.active_guards())
        combat.enter_room(31, 1)
        self.assertNotIn(actor, combat.active_guards())

    def test_terminal_removed_guard_does_not_reappear_on_revisit(self):
        combat, actor = self.actor()
        actor.state.sequence_mode = 5
        combat.enter_room(31, 1)
        combat.enter_room(3, 1)
        self.assertNotIn(actor, combat.guards)

    def test_target_selection_returns_real_side_actor_not_its_rebased_view(self):
        combat = self.fixture.encounter(0, player_x=500, running=False)
        side = self.fixture.runner(combat, 2, 20)
        self.assertIs(combat._nearest_guard(), side)
        self.assertIsNone(combat._nearest_guard(-1))
        self.assertIs(combat._nearest_guard(1), side)
        self.assertEqual((side.room, side.state.target_x), (2, 20))
        combat.guard = None
        combat.refresh_target()
        self.assertIs(combat.guard, side)
        with combat._local_opponents(side):
            self.assertIs(combat._nearest_guard(), side)
        self.assertIs(combat._nearest_guard(), side)

    def test_opposing_side_target_is_retained_until_its_control_hit_points_reach_zero(self):
        combat = self.fixture.encounter(0, player_x=500, running=False)
        resident = self.fixture.runner(combat, 0, 500)
        side = self.fixture.runner(combat, 2, 20, facing=1 - combat.player.state.facing)
        combat.guard = side
        combat.refresh_target()
        self.assertIs(combat.guard, side)
        side.life, side.native_alive = 0, False
        combat.refresh_target()
        self.assertIs(combat.guard, resident)

    def test_pending_zero_hp_candidate_stops_obstructing_selection_after_control_registration(self):
        combat = self.fixture.encounter(0, player_x=500, running=False)
        dying = self.fixture.runner(combat, 0, 500)
        side = self.fixture.runner(combat, 2, 20)
        dying.life, dying.native_alive = 0, True
        combat.guard = dying
        combat.refresh_target()
        self.assertIs(combat.guard, dying)
        combat.choose_guard_action(dying)
        combat.refresh_target()
        self.assertIs(combat.guard, side)

    def test_target_refresh_discards_stale_actor_and_falls_back_to_slot_zero(self):
        combat = self.fixture.encounter(0, player_x=500, running=False)
        resident = self.fixture.runner(combat, 0, 300)
        stale = self.fixture.runner(combat, 31, 200)
        resident.life, resident.native_alive = 0, False
        combat.guard = stale
        combat.refresh_target()
        self.assertIs(combat.guard, resident)
        combat.guards.clear()
        combat.refresh_target()
        self.assertIsNone(combat.guard)

    def test_player_turn_uses_projected_side_target_without_moving_it(self):
        combat = self.fixture.encounter(0, player_x=500, facing=0, running=False)
        side = self.fixture.runner(combat, 2, 20, facing=1)
        combat.guard = side
        combat.player.sword_drawn = True
        side.alert_mode = 3
        self.assertTrue(combat.choose_player_turn())
        self.assertEqual((side.room, side.state.target_x), (2, 20))

    def test_player_bump_uses_projected_side_target_without_moving_it(self):
        combat = self.fixture.encounter(0, player_x=500, facing=1, running=False)
        side = self.fixture.runner(combat, 2, -10, facing=0)
        combat.guard = side
        side.alert_mode = 3
        self.assertTrue(combat.choose_player_bump())
        self.assertEqual((side.room, side.state.target_x), (2, -10))

    def test_local_bank_context_is_restored_on_error(self):
        combat = self.fixture.encounter(0, player_x=500, running=False)
        side = self.fixture.runner(combat, 2, 20)
        player, guards = combat.player, combat.guards
        with self.assertRaisesRegex(RuntimeError, 'probe'):
            with combat._local_opponents(side):
                raise RuntimeError('probe')
        self.assertIs(combat.player, player)
        self.assertIs(combat.guards, guards)
        self.assertFalse(combat._local_opponent_bank)
        self.assertIs(combat._nearest_guard(), side)

    def standing(self, combat, room, x):
        from pop2.combat import select_sequence

        actor = self.fixture.runner(combat, room, x, facing=1)
        select_sequence(actor, 77)
        actor.runtime.next_frame()
        actor.sword_drawn = False
        return actor

    def test_noise_reaches_imported_guard_before_last_active_slot_consumes_it(self):
        combat = self.fixture.encounter(0, player_x=150, running=False)
        resident = self.standing(combat, 0, 350)
        side = self.standing(combat, 2, 20)
        combat.player.state.callback_flag = 1
        with combat._local_opponents(resident):
            combat.choose_guard_action(resident)
        self.assertEqual((resident.selected_sequence, combat.player.state.callback_flag), (80, 1))
        with combat._local_opponents(side):
            combat.choose_guard_action(side)
        self.assertEqual((side.selected_sequence, combat.player.state.callback_flag), (80, 0))

    def test_unselected_later_source_record_does_not_prevent_noise_consumption(self):
        combat = self.fixture.encounter(0, player_x=150, running=False)
        side = self.standing(combat, 2, 20)
        hidden = self.standing(combat, 2, 250)
        self.assertNotIn(hidden, combat.active_guards())
        combat.player.state.callback_flag = 1
        with combat._local_opponents(side):
            combat.choose_guard_action(side)
        self.assertEqual(combat.player.state.callback_flag, 0)

    def test_last_dead_or_armed_slot_does_not_consume_unarmed_noise(self):
        for dead in (False, True):
            with self.subTest(dead=dead):
                combat = self.fixture.encounter(0, player_x=150, running=False)
                resident = self.standing(combat, 0, 350)
                side = self.standing(combat, 2, 20)
                side.sword_drawn, side.life = not dead, 0 if dead else 3
                combat.player.state.callback_flag = 1
                for actor in (resident, side):
                    with combat._local_opponents(actor):
                        combat.choose_guard_action(actor)
                self.assertEqual(combat.player.state.callback_flag, 1)


if __name__ == '__main__':
    unittest.main()
