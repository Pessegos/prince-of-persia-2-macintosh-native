"""The original SortObjTable 3:3b62 against pop2.object_order (native CPU)."""

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
class NativeObjectSortTests(unittest.TestCase):
    def test_the_original_sort_agrees_with_the_port(self):
        from tools.probe_object_sort import run_probe

        report = run_probe(RECOVERY, count=2000)
        self.assertEqual(report['cases'], {'match': 2000}, report['examples'][:2])

    def test_the_earlier_cell_first_order_is_rejected(self):
        # The earlier port drew the lower row first, then left to right, and
        # compared bottoms only inside one cell.
        from pop2 import object_order
        from tools.probe_object_sort import run_probe

        def cell_first(objects):
            return sorted(reversed(objects), key=lambda item: (-(item.y // 120), item.x // 51, item.y, item.x))

        with patch.object(object_order, 'sort_objects', cell_first), \
                patch('tools.probe_object_sort.sort_objects', cell_first):
            self.assertIn('mismatch', run_probe(RECOVERY, count=500)['cases'])


if __name__ == '__main__':
    unittest.main()
