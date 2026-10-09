from types import SimpleNamespace
import unittest

from pop2.playback_navigation import playback_parts


class PlaybackNavigationTests(unittest.TestCase):
    def test_parts_use_scene_operations_and_first_recorded_room_entries(self):
        intro = SimpleNamespace(program={"operations": [
            {"op": "text", "args": [0, 0]}, {"op": "text", "args": [0, 10]},
            {"op": "title", "args": []}, {"op": "wait", "args": [60]},
            {"op": "text", "args": [0, 20]}]})
        data = {"frames": [{"room": room} for room in (4, 4, 2, 4, 10)],
                "credits": {"pages": [[], []]}}
        parts = playback_parts(intro, data, lambda room: str({3: 1, 1: 2, 9: 5}[room]))
        self.assertEqual([(p.stage, p.index) for p in parts],
                         [("intro", 1), ("intro", 2), ("intro", 4),
                          ("demo", 0), ("demo", 2), ("demo", 4),
                          ("credits", 0), ("credits", 1)])
        self.assertEqual([p.label for p in parts],
                         ["Story 1", "Clouds / titles", "Story 2", "Demo: screen 1",
                          "Demo: screen 2", "Demo: screen 5", "Credits: page 1", "Credits: page 2"])


if __name__ == "__main__":
    unittest.main()
