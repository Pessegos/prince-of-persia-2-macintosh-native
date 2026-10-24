import unittest

from tools.probe_temple_gate_services import ReliefActor, relief_reference


class TempleGateServicesTests(unittest.TestCase):
    def check(self, opponents, prince=ReliefActor(1, 4, 1), room=1, cell=12, number=4, countdown=-1):
        return relief_reference(number, countdown, room, cell, prince, opponents)

    def test_temple_levels_never_admit_level4_relief(self):
        for level in (10, 11, 12, 13):
            self.assertFalse(self.check((ReliefActor(1, 0, 1),), number=level))

    def test_once_only_countdown_sentinel_but_other_countdowns_are_admitted(self):
        for countdown in (-1, 0, 4):
            self.assertTrue(self.check((ReliefActor(1, 0, 1),), countdown=countdown))
        self.assertFalse(self.check((ReliefActor(1, 0, 1),), countdown=-2))

    def test_gate_to_left_includes_enemy_at_gate_but_not_on_prince_side(self):
        self.assertTrue(self.check((ReliefActor(1, 2, 1),)))
        self.assertFalse(self.check((ReliefActor(1, 3, 1),)))

    def test_gate_at_prince_column_treats_only_greater_enemy_columns_as_far(self):
        self.assertTrue(self.check((ReliefActor(1, 5, 1),), cell=14))
        self.assertFalse(self.check((ReliefActor(1, 4, 1),), cell=14))

    def test_distance_four_admits_and_five_rejects(self):
        self.assertTrue(self.check((ReliefActor(1, 0, 1),), prince=ReliefActor(1, 6, 1)))
        self.assertFalse(self.check((ReliefActor(1, 0, 1),), prince=ReliefActor(1, 7, 1)))

    def test_near_enemy_vetoes_far_enemy_in_either_order(self):
        far, near = ReliefActor(1, 0, 1), ReliefActor(1, 8, 1)
        self.assertFalse(self.check((far, near)))
        self.assertFalse(self.check((near, far)))

    def test_dead_or_other_room_row_are_ignored_not_positive_evidence(self):
        ignored = (ReliefActor(1, 8, 1, 0), ReliefActor(2, 8, 1), ReliefActor(1, 8, 0))
        self.assertFalse(self.check(ignored))
        self.assertTrue(self.check(ignored[:2] + (ReliefActor(1, 0, 1),)))

    def test_prince_room_row_and_nonempty_bank_are_required(self):
        self.assertFalse(self.check(()))
        self.assertFalse(self.check((ReliefActor(1, 0, 1),), room=0))
        self.assertFalse(self.check((ReliefActor(1, 0, 1),), prince=ReliefActor(2, 4, 1)))
        self.assertFalse(self.check((ReliefActor(1, 0, 1),), prince=ReliefActor(1, 4, 0)))

    def test_bounded_domain_rejects_uncovered_records_and_indexes(self):
        for room, cell, bank in ((33, 12, ()), (1, 30, ()), (1, 12, (ReliefActor(1, 0, 1),) * 4)):
            with self.assertRaises(ValueError):
                self.check(bank, room=room, cell=cell)


if __name__ == '__main__':
    unittest.main()
