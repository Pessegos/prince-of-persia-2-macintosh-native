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
        actor.state.special_flag = 5
        combat.enter_room(31, 1)
        combat.enter_room(3, 1)
        self.assertNotIn(actor, combat.guards)


if __name__ == '__main__':
    unittest.main()
