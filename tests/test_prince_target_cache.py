import unittest

from pop2.combat import PLAYER_COMBAT_TURN_SEQUENCE, Fighter
from pop2.sequence_runtime import SequenceRuntime, SequenceState
import tests.test_combat as combat_tests


class PrinceTargetCacheTests(unittest.TestCase):
    """Persistent Prince target (native +0x3a) versus the effective opponent.

    Evidence: docs/research/prince-turn-flag-and-rear-target.md,
    teststrike-prince-target-writes.md and death-target-lifecycle.md.
    """

    setUpClass = classmethod(combat_tests.GuardCombatTests.setUpClass.__func__)
    encounter = combat_tests.GuardCombatTests.encounter

    def add_guard(self, combat, x, facing, action=158):
        state = SequenceState(227, current_x=x, target_x=x, facing=facing,
                              actor_type=2, level_kind=5)
        guard = Fighter(SequenceRuntime(self.sequences, state), 3, 3,
                        combat.player.room, combat.player.row, sword_drawn=True,
                        alert_mode=3, native_alive=True)
        guard.runtime.next_frame()
        guard.state.action = action
        guard.bank_slot = len(combat.guards)
        combat.guards.append(guard)
        return guard

    def d1(self, facing):
        # SwordCtrl 6:2174-21de keeps rear A (Prince's facing, positive HP)
        # although B ahead is nearer; 6:2252-22ea then selects the turn.
        direction = 1 if facing else -1
        x = 260 if facing else 140
        c = self.encounter(player_x=x, player_facing=facing)
        rear = c.guard
        rear.state.target_x = rear.state.current_x = x - 60 * direction
        rear.state.facing = facing
        rear.alert_mode = 2
        front = self.add_guard(c, x + 40 * direction, 1 - facing)
        return c, rear, front

    def test_armed_prince_turns_toward_cached_rear_target_despite_nearer_front_guard(self):
        for facing in (1, 0):
            c, rear, _front = self.d1(facing)
            c.refresh_target()
            self.assertIs(c.guard, rear, facing)
            self.assertTrue(c.choose_player_turn(), facing)
            self.assertEqual(c.player.state.sequence_id, PLAYER_COMBAT_TURN_SEQUENCE)

    def test_rear_target_cached_during_strike_survives_a_nearer_arrival(self):
        # Supplied S1 sequence: the front target dies while the Prince is in
        # mode 2, SwordCtrl stores the nearest native-ALIVE actor (rear A),
        # then B approaches; the original turns toward A at the ready pose.
        for facing in (1, 0):
            direction = 1 if facing else -1
            x = 260 if facing else 140
            c = self.encounter(player_x=x, player_facing=facing)
            front = c.guard
            front.state.target_x = front.state.current_x = x + 40 * direction
            front.state.facing = 1 - facing
            rear = self.add_guard(c, x - 50 * direction, facing)
            rear.alert_mode = 2
            arrival = self.add_guard(c, x + 90 * direction, 1 - facing)
            front.life, front.native_alive = 0, False
            c.player.state.animation_state = 2
            c.refresh_target()
            arrival.state.target_x = arrival.state.current_x = x + 30 * direction
            c.player.state.animation_state = 3
            c.refresh_target()
            c.player.state.animation_state = 1
            c.refresh_target()
            self.assertIs(c.guard, rear, facing)
            self.assertTrue(c.choose_player_turn(), facing)

    def prince_strike(self, facing=1):
        x = 260 if facing else 140
        c = self.encounter(player_x=x, player_facing=facing)
        c.player.state.action = 154
        return c, x, 1 if facing else -1

    def test_prince_hit_makes_the_struck_guard_the_target(self):
        # TestStrike 6:5a06 writes the struck slot into the Prince target.
        for facing in (1, 0):
            c, x, d = self.prince_strike(facing)
            cached = c.guard
            cached.state.target_x = cached.state.current_x = x + 110 * d
            cached.state.facing = 1 - facing
            struck = self.add_guard(c, x + 55 * d, 1 - facing)
            events = c.resolve_contacts()
            self.assertEqual([(e.kind, e.actor) for e in events], [('hit', 'guard')])
            self.assertIs(c.guard, struck, facing)
            self.assertIs(c.target_cache, struck, facing)

    def test_two_prince_hits_target_the_later_bank_slot(self):
        c, x, d = self.prince_strike()
        first = c.guard
        first.life = first.max_life = 3
        first.state.target_x = first.state.current_x = x + 50 * d
        first.state.facing = 0
        second = self.add_guard(c, x + 58 * d, 0)
        events = c.resolve_contacts()
        self.assertEqual([(e.kind, e.actor) for e in events], [('hit', 'guard')] * 2)
        self.assertIs(c.guard, second)

    def test_blocked_prince_targets_the_blocking_guard(self):
        # TestStrike 6:5a48 writes the blocking slot, at poses 153 and 154.
        for pose in (153, 154):
            c, x, d = self.prince_strike()
            c.player.state.action = pose
            cached = c.guard
            cached.state.target_x = cached.state.current_x = x + 110 * d
            cached.state.facing = 0
            blocker = self.add_guard(c, x + 70 * d, 0, action=161)
            events = c.resolve_contacts()
            self.assertEqual([(e.kind, e.actor) for e in events], [('parry', 'guard')], pose)
            self.assertIs(c.guard, blocker, pose)

    def test_guard_strikes_do_not_write_the_prince_target(self):
        c, x, d = self.prince_strike()
        c.player.state.action = 158
        cached = c.guard
        cached.state.target_x = cached.state.current_x = x + 110 * d
        cached.state.facing = 0
        self.add_guard(c, x + 55 * d, 0, action=154)
        c.resolve_contacts()
        self.assertIs(c.guard, cached)

    def test_cached_corpse_is_released_after_registration_even_when_unarmed(self):
        # GenCtrl 6:0762-077c reselects once the death is registered.
        c, _rear, front = self.d1(1)
        c.player.sword_drawn = False
        corpse = c.guard
        corpse.state.facing = 0
        corpse.life, corpse.native_alive = 0, True     # killed, not yet registered
        c.refresh_target()
        self.assertIs(c.guard, corpse)
        c.choose_guard_action(corpse)
        c.refresh_target()
        self.assertIs(c.guard, front)


if __name__ == '__main__':
    unittest.main()
