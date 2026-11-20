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
        # The port's rule agrees except where the opponent's pose advanced in
        # the crossing frame itself (the port has not stepped it yet).
        self.assertGreater(result['port']['agree'], 20)
        self.assertLessEqual(set(result['port']), {'agree', 'pose_advanced_in_frame'})

    def test_the_prince_frame_on_every_crossing_is_rejected(self):
        from pop2.combat import CombatEncounter
        from tools.probe_crossing_frame import run_probe

        # Before 2026-11-20 the heap settle always used the Prince's frame.
        with patch.object(CombatEncounter, '_last_loaded_opponent_frame', lambda self, actors: None):
            result = run_probe(RECOVERY, **SCOPE)
        self.assertGreater(sum(v for k, v in result['port'].items() if k != 'agree'),
                           result['port'].get('agree', 0))


if __name__ == '__main__':
    unittest.main()
