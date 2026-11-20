"""The original CheckSideRoomsForVisibleOpps 6:2f4e against the port (native CPU)."""

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
class NativeSideRoomRecordTests(unittest.TestCase):
    def test_the_original_routine_agrees_with_the_port(self):
        from tools.probe_side_room_records import run_probe

        result = run_probe(RECOVERY)
        self.assertEqual(result['mismatches'], 0)
        self.assertEqual(result['counts']['initial_room_entries'], 238)
        # Settling heaps on entry, not on building, includes the 53 synthetic
        # heaps once excluded for a settle that crossed a threshold.
        self.assertEqual(result['counts']['sweep_room_entries'], 3498)
        self.assertGreater(result['positive']['sweep_transferred_records'], 800)
        # Only the palace branch 2fe8-300a moves records the port leaves.
        self.assertEqual(set(result['excluded_moves']),
                         {'level 14 sweep raw kind 3 port actor 6'})

    def test_the_old_side_bank_view_is_rejected(self):
        from pop2.combat import CombatEncounter
        from tools.probe_side_room_records import run_probe

        # Before 2026-11-20 nothing moved; the actor stayed in its own room.
        with patch.object(CombatEncounter, '_take_visible_side_records', lambda self, room: None):
            with self.assertRaises(AssertionError):
                run_probe(RECOVERY)

    def test_settling_heaps_when_a_side_room_is_built_is_rejected(self):
        from pop2.combat import CombatEncounter
        from tools.probe_side_room_records import run_probe

        # Before 2026-11-20 _load_room settled a heap (4:19f0) at once, so
        # 2f4e saw a settled X that the native record does not have yet.
        def load_and_settle(original):
            def wrapped(encounter, room):
                fresh = room not in encounter.room_encounters
                original(encounter, room)
                if fresh:
                    for actor in encounter.room_encounters[room][0]:
                        if actor.skeleton is not None:
                            actor.skeleton.settle_heap(encounter, actor)
            return wrapped

        with patch.object(CombatEncounter, '_load_room', load_and_settle(CombatEncounter._load_room)):
            with self.assertRaises(AssertionError):
                run_probe(RECOVERY)

    def test_an_off_by_one_threshold_is_rejected(self):
        from tools.probe_side_room_records import run_probe

        def inclusive(x, side):
            return x >= 378 if side == 'left' else x <= 124
        with patch('pop2.combat.visible_side_opponent', inclusive):
            with self.assertRaises(AssertionError):
                run_probe(RECOVERY)


if __name__ == '__main__':
    unittest.main()
