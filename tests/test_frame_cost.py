"""Frame-cost guard: a whole game frame stays well inside the native frame time.

This is not a benchmark. It catches a change that makes ordinary frames or
room entries several times slower (a lost cache, a per-frame re-render, a
whole-room export drawn at run time) while the margins stay wide enough for a
loaded machine. Frames are 1/12 s (1/10 s in sword fights); on the
development machine a frame costs about 15 ms (13 of them handing the image
to Tk) and a room entry under 40 ms.
"""

import random
import statistics
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from pop2.caverns import scenery_available
from pop2.paths import ASSET_DIR
from pop2.scene_prototype import ANIMATION_INTERVAL_MS

# A median frame within half a frame interval; nine in ten room entries
# within three quarters of one, so that a room change does not drop a frame.
STEADY_BUDGET_MS = ANIMATION_INTERVAL_MS / 2
ENTRY_BUDGET_MS = ANIMATION_INTERVAL_MS * 3 / 4
LEVELS = (1, 2, 3, 4, 5, 6, 7, 8, 9)


def level_available(level):
    return level <= 2 or scenery_available(level)


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file(), 'Imported game resources required')
class FrameCostTests(unittest.TestCase):
    def setUp(self):
        from pop2.scene_prototype import ScenePrototype

        original_tk = tk.Tk

        def hidden_root():
            root = original_tk()
            root.withdraw()
            return root

        with patch('pop2.window_controls.tk.Tk', hidden_root):
            self.scene = ScenePrototype()
        self.scene.root.after_cancel(self.scene.animation_after_id)
        self.scene.animation_after_id = None
        self.scene.schedule_next_animation = lambda: None
        self.scene.combat.rng = random.Random(1)
        self.addCleanup(self.scene.root.destroy)
        self.now = 1000.0

    def frame_ms(self):
        """One animation step, timed on a clock the step does not patch."""
        self.now += 0.101
        with patch('pop2.scene_prototype.time.perf_counter', return_value=self.now):
            start = time.perf_counter_ns()
            self.scene.advance_animation()
            return (time.perf_counter_ns() - start) / 1e6

    def test_frames_and_room_entries_fit_the_frame_time(self):
        scene = self.scene
        report = []
        for level in LEVELS:
            if not level_available(level):
                continue
            with self.subTest(level=level):
                scene.load_level(level)
                if scene.opening is not None:
                    scene.opening.active = False
                self.frame_ms()
                # Standing, then running from the start position.
                steady = [self.frame_ms() for _ in range(20)]
                scene.horizontal_key(None, 1, True)
                steady += [self.frame_ms() for _ in range(20)]
                scene.horizontal_key(None, 1, False)
                # The first two frames in each room draw it from its exports.
                entries = []
                for room in range(32):
                    try:
                        scene.jump_to_room(room, 1, 200, 1)
                    except ValueError:
                        continue  # Not a room of this level (the desert shore).
                    entries += [self.frame_ms(), self.frame_ms()]
                self.assertTrue(entries)
                median = statistics.median(steady)
                entry = sorted(entries)[int(len(entries) * 0.9)]
                report.append(f'level {level}: frame median {median:.1f} ms, '
                              f'room entry 90th percentile {entry:.1f} ms, worst {max(entries):.1f} ms')
                self.assertLess(median, STEADY_BUDGET_MS, report[-1])
                self.assertLess(entry, ENTRY_BUDGET_MS, report[-1])
        print('\n' + '\n'.join(report))


if __name__ == '__main__':
    unittest.main()
