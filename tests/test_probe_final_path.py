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

    def test_the_original_copy_controller_agrees_with_the_port(self):
        from pop2 import final_tower
        from tools.probe_final_copies import run_probe

        compared, kinds = run_probe(RECOVERY, count=1500)
        self.assertEqual(compared, 1500)
        for kind in ('select 75', 'select 240', 'select 92', 'select 197', 'select 49', 'turn'):
            self.assertGreater(kinds.get(kind, 0), 0, kind)

        def distance_in_port_facing(copy, prince):
            # Mistaking the port's facing (1 right) for the native word
            # (0 right) measures every distance the wrong way round.
            if copy.room != prince.room or copy.row != prince.row:
                return 999
            distance = prince.x - copy.state.target_x
            return -distance if copy.state.facing else distance

        with patch.object(final_tower, 'copy_distance', distance_in_port_facing):
            with self.assertRaises(AssertionError):
                run_probe(RECOVERY, count=1500)

    def test_the_original_turn_rules_agree_with_the_port(self):
        from pop2 import final_magic
        from tools.probe_final_magic import run_probe

        totals = run_probe(RECOVERY)
        self.assertEqual((totals['4:250a'], totals['4:2174']), (6400, 2400))
        self.assertEqual(set(totals['outcomes']), {'count', 'kill', 'flash', 'leave'})
        # 4:2046 leaves the body above 4 life; a threshold of 3 is rejected.
        with patch.object(final_magic, 'TRANSFORM_LIFE', 3):
            with self.assertRaises(AssertionError):
                run_probe(RECOVERY)

    def test_the_original_defeat_and_laugh_agree_with_the_port(self):
        from pop2 import final_magic, opponent_records
        from tools import probe_final_defeat

        totals = probe_final_defeat.run_probe(RECOVERY)
        self.assertEqual(totals, {'6:0780/9:0062': 364, 'moved': 78, '6:2d64': 2560,
                                  'laughs': 1})
        # ALIVE above 6, not 5; and only type 6 keeps SEQS 197.
        with patch.object(final_magic, 'DEFEAT_DELAY', 5):
            with self.assertRaises(AssertionError):
                probe_final_defeat.run_probe(RECOVERY)

        def every_type_laughs(actor_type, sequence):
            if sequence == 197:
                return sequence, 261
            return (2, None) if actor_type == 6 else ((sequence if sequence == 22 else 77), None)

        with patch.object(probe_final_defeat, 'fresh_sequence', every_type_laughs):
            with self.assertRaises(AssertionError):
                probe_final_defeat.run_probe(RECOVERY)
        self.assertIs(probe_final_defeat.fresh_sequence, opponent_records.fresh_sequence)


if __name__ == '__main__':
    unittest.main()
