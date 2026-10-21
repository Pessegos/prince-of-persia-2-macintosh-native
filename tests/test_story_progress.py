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

    def test_minute_messages_follow_keep_time_thresholds(self):
        # KeepTime 2:5226-5242: every fifth minute and each of the last four.
        shown = []
        for minutes in range(75, 1, -1):
            story = StoryProgress(minutes=minutes, frames_remaining=1, tree_stage=0)
            story.advance_frame()
            if story.message_pending:
                shown.append(story.message_text())
        # Reaching the last minute formats seconds: (719 + 1) / 12 = 60.
        self.assertEqual(shown, [f'{m} Minutes Left' for m in
                                 (70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 4, 3, 2)]
                         + ['60 Seconds Left'])

    def test_last_minute_counts_seconds_every_twelve_updates(self):
        # 2:5244-526c and 2:529c-52d4: (frames + 1) / 12 seconds.
        story = StoryProgress(minutes=1, frames_remaining=FRAMES_PER_MINUTE, tree_stage=0)
        messages = []
        while story.frames_remaining > 1:
            story.advance_frame()
            if story.message_pending:
                messages.append(story.message_text())
                story.message_pending = None
        self.assertEqual(messages[0], '59 Seconds Left')
        self.assertEqual(messages[-1], '1 Second Left')
        self.assertEqual(len(messages), 59)

    def test_expired_message_and_presentation_state_is_not_campaign_state(self):
        story = StoryProgress(minutes=0, tree_stage=0)
        self.assertEqual(story.message_text(), 'Time has expired!')
        story.message_pending = 'minutes'
        self.assertEqual(story, StoryProgress(minutes=0, tree_stage=0))


if __name__ == '__main__':
    unittest.main()
