import unittest

from pop2.story_progress import FRAMES_PER_MINUTE, StoryProgress


class StoryProgressTests(unittest.TestCase):
    def test_discovery_does_not_start_the_clock_on_first_level_four_entry(self):
        story = StoryProgress()
        self.assertEqual(story.select_scene(3, 4), 10)
        for _ in range(FRAMES_PER_MINUTE * 2):
            story.advance_frame()
        self.assertEqual((story.minutes, story.frames_remaining, story.tree_stage),
                         (75, FRAMES_PER_MINUTE, -1))

    def test_first_level_four_restart_starts_tree_clock_once(self):
        story = StoryProgress()
        self.assertEqual(story.select_scene(4, 4), 20)
        self.assertTrue(story.clock_started)
        story.advance_frame()
        self.assertIsNone(story.select_scene(4, 4))
        self.assertEqual(story.frames_remaining, FRAMES_PER_MINUTE - 1)

    def test_surviving_level_four_defers_tree_until_transition_to_five(self):
        story = StoryProgress()
        story.select_scene(3, 4)
        self.assertEqual(story.select_scene(4, 5), 20)
        self.assertEqual(story.tree_stage, 0)

    def test_dying_before_level_four_does_not_show_tree(self):
        for level in (1, 2, 3):
            with self.subTest(level=level):
                story = StoryProgress()
                self.assertIsNone(story.select_scene(level, level))
                self.assertFalse(story.clock_started)

    def test_specific_transitions_take_priority_over_tree(self):
        for previous, scene in ((1, 9), (2, 100), (3, 10), (5, 1), (9, 2), (13, 3)):
            with self.subTest(previous=previous):
                story = StoryProgress()
                self.assertEqual(story.select_scene(previous, previous + 1), scene)
                self.assertFalse(story.clock_started)

    def test_tree_variants_follow_time_thresholds_and_do_not_repeat(self):
        story = StoryProgress(tree_stage=0)
        for minutes, scene in ((75, None), (64, None), (63, 21), (55, None),
                               (54, 22), (45, 23), (36, 24), (27, 25),
                               (18, 26), (10, None), (9, 27), (1, None), (0, None)):
            with self.subTest(minutes=minutes):
                story.minutes = minutes
                self.assertEqual(story.select_scene(4, 4), scene)
                self.assertIsNone(story.select_scene(4, 4))

    def test_expired_clock_uses_signed_division_without_inventing_another_scene(self):
        story = StoryProgress(minutes=0, tree_stage=0)
        self.assertEqual(story.select_scene(4, 4), 27)
        self.assertEqual(story.tree_stage, 7)

    def test_one_minute_consumes_the_original_counter_and_freezes_when_dead(self):
        story = StoryProgress(tree_stage=0)
        for _ in range(FRAMES_PER_MINUTE - 1):
            self.assertFalse(story.advance_frame())
        for _ in range(20):
            self.assertFalse(story.advance_frame(player_alive=False))
        self.assertEqual((story.minutes, story.frames_remaining), (75, 1))
        self.assertTrue(story.advance_frame())
        self.assertEqual((story.minutes, story.frames_remaining), (74, FRAMES_PER_MINUTE))

    def test_expiry_does_not_wrap_or_reset_on_level_restart(self):
        story = StoryProgress(minutes=1, frames_remaining=1, tree_stage=0)
        self.assertTrue(story.advance_frame())
        self.assertTrue(story.expired)
        for _ in range(20):
            self.assertFalse(story.advance_frame())
        self.assertEqual(story.minutes, 0)


if __name__ == '__main__':
    unittest.main()
