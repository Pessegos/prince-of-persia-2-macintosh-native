"""The original CODE 9:16fe against the port's palace controller (native CPU)."""

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
class NativePathControllerTests(unittest.TestCase):
    def test_the_original_controller_agrees_with_the_port(self):
        from tools.probe_final_path import run_probe

        totals, kinds = run_probe(RECOVERY, count=1500)
        self.assertEqual(totals['cases'], 1500)
        for kind in ('select', 'sound', 'death', 'song', 'forward', 'step', 'climb',
                     'jump_up', 'release', 'run_jump'):
            self.assertIn(kind, kinds)

    def test_a_wrong_model_is_rejected(self):
        from pop2 import final_path
        from tools.probe_final_path import run_probe

        def distance_without_life(jaffar, prince):
            # The earlier port: CharDistance without its 4:49f0 life gate.
            if jaffar.room != prince.room or jaffar.row != prince.row:
                return 999
            value = prince.x - jaffar.x
            if jaffar.facing:
                value = -value
            if value >= 0 and jaffar.facing != prince.facing:
                value += 21
            return value

        def range_on_every_column(jaffar, prince, frames):
            return prince.life > 0 and jaffar.row == prince.row

        for name, wrong in (('distance', distance_without_life),
                            ('prince_in_range', range_on_every_column)):
            with self.subTest(name=name), patch.object(final_path, name, wrong):
                with self.assertRaises(AssertionError):
                    run_probe(RECOVERY, count=1500)


if __name__ == '__main__':
    unittest.main()
