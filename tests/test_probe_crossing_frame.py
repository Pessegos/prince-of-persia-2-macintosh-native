"""Original FrameAdv across room crossings: the frame InitOpps finds (native CPU)."""

from pathlib import Path
import unittest
from unittest.mock import patch

RECOVERY = Path(__file__).resolve().parents[2] / 'PoP2-Mac-Code-Recovery'

try:
    import unicorn  # noqa: F401
except ImportError:  # pragma: no cover - optional research dependency
    unicorn = None

# Level 3, native room 3: both neighbours, skeletons appended to the room left.
SCOPE = dict(rooms={(3, 3)}, levels=(3,), distances=(40,))


@unittest.skipUnless(unicorn is not None and (RECOVERY / 'resource_forks').is_dir(),
                     'Unicorn and the original recovery are required')
class NativeCrossingFrameTests(unittest.TestCase):
    def test_initopps_sees_the_last_frame_loaded_by_the_prince_or_the_opponent_pass(self):
        from tools.probe_crossing_frame import run_probe

        result = run_probe(RECOVERY, **SCOPE)
        counts = result['counts']
        self.assertEqual(counts.get('native_failures', 0), 0)
        self.assertGreater(counts['crossings'], 20)
        # Every last load comes from the Prince's step or the opponent pass.
        phases = {key.split()[1] for key in result['sources']}
        self.assertLessEqual(phases, {'prince_step', 'opponent_pass'})
        self.assertTrue(any(key.startswith('opponent') for key in result['sources']))
        # The port's rule, on the room left's opponents after their pass (the
        # port steps them before the cut since 2026-11-20), agrees everywhere.
        self.assertEqual(result['port']['agree'], counts['crossings'])
        self.assertLessEqual(set(result['port']), {'agree', 'before_pass_agree', 'before_pass_differs'})

    def test_their_poses_before_the_pass_are_rejected(self):
        # The earlier tick order entered the new room before the opponent
        # pass, so the rule read the room left's poses of the frame before.
        # Level 3, native room 1, 12 pixels inside each edge.
        from tools.probe_crossing_frame import run_probe

        result = run_probe(RECOVERY, rooms={(3, 1)}, levels=(3,), distances=(12,))
        self.assertEqual(result['port']['agree'], result['counts']['crossings'])
        self.assertGreater(result['port'].get('before_pass_differs', 0), 0)

    def test_the_prince_frame_on_every_crossing_is_rejected(self):
        from pop2.combat import CombatEncounter
        from tools.probe_crossing_frame import run_probe

        # Before 2026-11-20 the heap settle always used the Prince's frame.
        with patch.object(CombatEncounter, '_last_loaded_opponent_frame', lambda self, actors: None):
            result = run_probe(RECOVERY, **SCOPE)
        port = {k: v for k, v in result['port'].items() if not k.startswith('before_pass')}
        self.assertGreater(sum(v for k, v in port.items() if k != 'agree'), port.get('agree', 0))


if __name__ == '__main__':
    unittest.main()
