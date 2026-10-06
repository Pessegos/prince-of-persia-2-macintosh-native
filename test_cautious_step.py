import unittest

from mac_input import StepBoundary, StepPlan, plan_cautious_step


class CautiousStepTests(unittest.TestCase):
    def test_first_edge_attempt_warns_then_second_commits_a_step(self):
        boundary = StepBoundary(4, tile_kind=0)
        self.assertEqual(plan_cautious_step(boundary, True), (StepPlan(44, 0), False))
        self.assertEqual(plan_cautious_step(boundary, False), (StepPlan(42, 0), False))

    def test_warning_includes_source_loose_tile_and_pressure_plate_kinds(self):
        for kind in (11, 12, 13):
            with self.subTest(kind=kind):
                self.assertEqual(plan_cautious_step(StepBoundary(3, 0, kind), True),
                                 (StepPlan(44, 0), False))

    def test_solid_barrier_does_not_warn_but_plate_barrier_does(self):
        for kind in (2, 7, 20, 25, 43):
            with self.subTest(kind=kind):
                self.assertEqual(plan_cautious_step(StepBoundary(0, 1, kind), True),
                                 (StepPlan(42, 0), True))
        for kind in (12, 13):
            with self.subTest(kind=kind):
                self.assertEqual(plan_cautious_step(StepBoundary(0, 1, kind), True),
                                 (StepPlan(44, 0), False))

    def test_positive_distance_rearms_caution_and_preserves_short_step_math(self):
        self.assertEqual(plan_cautious_step(StepBoundary(21), False), (StepPlan(33, 2), True))
        self.assertEqual(plan_cautious_step(StepBoundary(42, 2), True), (StepPlan(40, 2), True))


if __name__ == "__main__":
    unittest.main()
