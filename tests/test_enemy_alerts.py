"""Asset-free limits from Macintosh alert acquisition, CODE:2 6e7e."""

from dataclasses import replace
import struct
import unittest

from pop2.combat import CombatEncounter, Fighter
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap


class EnemyAlertTests(unittest.TestCase):
    def encounter(self, player_column=7, guard_column=2, environment=3, actor=4):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2180, 32)
        struct.pack_into('>H', self.level, 0x2198, 1)
        struct.pack_into('>H', self.level, 0x2186, environment)
        self.level[:60] = struct.pack('>30H', *([1] * 30))

        def fighter(column, actor_type):
            x = column * 51 + 30
            state = SequenceState(227, actor_type=actor_type, action=171,
                                  current_x=x, target_x=x, facing=1, animation_state=1,
                                  level_kind=environment)
            return Fighter(SequenceRuntime({}, state), 3, 3, 0, 1)

        combat = CombatEncounter.__new__(CombatEncounter)
        combat.level, combat.level_kind = self.level, environment
        combat.terrain = LevelMap(self.level)
        combat.player = fighter(player_column, 0)
        combat.guard = fighter(guard_column, actor)
        combat.guards, combat.rooftop_escape = [combat.guard], False
        return combat

    def tile(self, column, kind, modifier=0, *, room=0):
        cell = 10 + column
        struct.pack_into('>H', self.level, room * 60 + cell * 2, kind)
        struct.pack_into('>H', self.level, 0x780 + room * 120 + cell * 4, modifier)

    def alert(self, combat):
        combat._update_guard_alert(combat.guard)
        return combat.guard.alert_mode

    def test_right_endpoint_gate_is_excluded_regardless_of_actor_order_or_opening(self):
        for actor in (2, 4):
            for player, guard in ((7, 2), (2, 7)):
                for modifier in (0, 103, 104, 255, 0x200 | 103):
                    with self.subTest(actor=actor, player=player, modifier=modifier):
                        combat = self.encounter(player, guard, actor=actor)
                        self.tile(7, 4, modifier)
                        self.assertEqual(self.alert(combat), 3)
                        self.assertTrue(combat.guard.pursuing)

    def test_adjacent_endpoint_gate_skips_the_remaining_single_cell(self):
        for player, guard in ((2, 3), (3, 2)):
            combat = self.encounter(player, guard)
            self.tile(2, 20)
            self.tile(3, 4)
            self.assertEqual(self.alert(combat), 3)

    def test_gate_inside_path_or_at_left_endpoint_keeps_native_threshold(self):
        for player, guard in ((7, 2), (2, 7)):
            for column in (2, 3, 6):
                for modifier, expected in ((0, 1), (103, 1), (104, 3), (0x268, 3)):
                    with self.subTest(player=player, column=column, modifier=modifier):
                        combat = self.encounter(player, guard)
                        self.tile(column, 4, modifier)
                        self.assertEqual(self.alert(combat), expected)

    def test_only_cavern_tile24_at_the_left_endpoint_has_the_exception(self):
        for environment in (1, 3, 5, 6):
            for player, guard in ((7, 2), (2, 7)):
                for column in (2, 3, 6, 7):
                    with self.subTest(environment=environment, player=player, column=column):
                        combat = self.encounter(player, guard, environment)
                        self.tile(column, 24)
                        expected = 3 if environment == 3 and column == 2 else 1
                        self.assertEqual(self.alert(combat), expected)

    def test_tile24_exception_does_not_hide_another_obstruction(self):
        for kind, expected in ((0, 1), (4, 1), (20, 0), (11, 1)):
            combat = self.encounter()
            self.tile(2, 24)
            self.tile(5, kind)
            self.assertEqual(self.alert(combat), expected)

    def test_scan_stops_at_first_obstruction_in_left_to_right_order(self):
        for first, second, expected in ((0, 20, 1), (20, 0, 0), (4, 20, 1)):
            for player, guard in ((7, 2), (2, 7)):
                combat = self.encounter(player, guard)
                self.tile(3, first)
                self.tile(5, second)
                self.assertEqual(self.alert(combat), expected)

    def test_same_column_skips_terrain_but_not_the_actor_exclusions(self):
        for kind in range(50):
            combat = self.encounter(2, 2)
            self.tile(2, kind)
            self.assertEqual(self.alert(combat), 3)
        for condition in ('dead_player', 'dead_guard', 'other_row', 'shadow', 'escape'):
            combat = self.encounter(2, 2)
            if condition == 'dead_player':
                combat.player.life = 0
            elif condition == 'dead_guard':
                combat.guard.life = 0
            elif condition == 'other_row':
                combat.guard.row = 2
            elif condition == 'shadow':
                combat.player.state.actor_type = 1
            else:
                combat.rooftop_escape = True
            self.assertEqual(self.alert(combat), 0)

    def test_excluded_endpoint_does_not_promote_a_waiting_non_primary_enemy(self):
        combat = self.encounter()
        nearer_state = replace(combat.guard.state, current_x=4 * 51 + 30, target_x=4 * 51 + 30)
        nearer = replace(combat.guard, runtime=SequenceRuntime({}, nearer_state))
        combat.guards.append(nearer)
        self.tile(7, 4)
        self.assertEqual(self.alert(combat), 2)

    def test_live_gate_and_removed_floor_are_queried_again(self):
        combat = self.encounter()
        for kind, modifier, expected in ((4, 103, 1), (4, 104, 3), (0, 0, 1), (1, 0, 3)):
            self.tile(5, kind, modifier)
            self.assertEqual(self.alert(combat), expected)

    def test_linked_cell_uses_its_normalized_column_for_cavern_exception(self):
        combat = self.encounter(12, 2)
        struct.pack_into('>H', self.level, 0x2082, 2)
        self.level[60:120] = struct.pack('>30H', *([1] * 30))
        self.tile(1, 24, room=1)
        self.assertEqual(self.alert(combat), 3)
        self.tile(2, 24, room=1)
        self.assertEqual(self.alert(combat), 3)
        self.tile(3, 24, room=1)
        combat.player.state.current_x = combat.player.state.target_x = 13 * 51 + 30
        self.assertEqual(self.alert(combat), 1)


if __name__ == '__main__':
    unittest.main()
