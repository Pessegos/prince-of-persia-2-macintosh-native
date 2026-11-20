"""The original SkelAddOpponent 4:198a settle against the port (native CPU)."""

from pathlib import Path
import unittest
from unittest.mock import patch

RECOVERY = Path(__file__).resolve().parents[2] / 'PoP2-Mac-Code-Recovery'

try:
    import unicorn  # noqa: F401
except ImportError:  # pragma: no cover - optional research dependency
    unicorn = None


@unittest.skipUnless(unicorn is not None and (RECOVERY / 'resource_forks').is_dir(),
                     'Unicorn and the original recovery are required')
class NativeSkeletonSettleTests(unittest.TestCase):
    def test_the_original_routine_agrees_with_the_port(self):
        from tools.probe_skeleton_settle import run_probe

        result = run_probe(RECOVERY, stride=4)
        self.assertEqual(result['mismatches'], 0)
        self.assertEqual(set(result['counts']), {'level_3', 'level_4', 'level_5'})
        self.assertGreater(sum(result['moved'].values()), 300)

    def test_the_heap_pose_foot_column_is_rejected(self):
        from pop2.skeleton import Skeleton
        from tools.probe_skeleton_settle import run_probe

        # Before 2026-11-20 the port took the cell beside the heap pose's
        # supporting foot (FRAM 206/207), not GetCharCol of the record X.
        def foot_column(actor):
            return actor.probe_encounter._supporting_column(actor)

        original = Skeleton.settle_heap

        def settle(self, encounter, actor):
            actor.probe_encounter = encounter
            return original(self, encounter, actor)

        with patch.object(Skeleton, 'heap_column', staticmethod(foot_column)), \
                patch.object(Skeleton, 'settle_heap', settle):
            with self.assertRaises(AssertionError):
                run_probe(RECOVERY, stride=4)


if __name__ == '__main__':
    unittest.main()
