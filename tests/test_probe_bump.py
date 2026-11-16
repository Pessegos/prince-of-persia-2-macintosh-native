"""The original FrameAdv bump 2:6c64 against the port's (native CPU)."""

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
class NativeBumpTests(unittest.TestCase):
    def test_the_original_bump_agrees_with_the_port(self):
        from tools.probe_bump import run_probe

        compared, outcomes = run_probe(RECOVERY, count=3000)
        self.assertEqual(compared, 3000)
        for kind in ('SEQS 46', 'SEQS 47', 'SEQS None', 'excluded type'):
            self.assertGreater(outcomes.get(kind, 0), 0, kind)

    def test_the_earlier_opponent_test_is_rejected(self):
        # The earlier port excluded only SEQS 110, for every opponent type.
        from pop2 import combat
        from tools.probe_bump import run_probe

        with patch.object(combat, 'bump_opponent', lambda _type, _pose, sequence: sequence != 110):
            with self.assertRaises(AssertionError):
                run_probe(RECOVERY, count=3000)


if __name__ == '__main__':
    unittest.main()
