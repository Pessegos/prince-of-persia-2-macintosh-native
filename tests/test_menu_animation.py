import unittest

from pop2.menu_animation import MenuFrameClock, spring_step


class MenuAnimationTests(unittest.TestCase):
    def test_spring_motion_depends_on_elapsed_time_rather_than_frame_count(self):
        states = []
        for rate in (30, 60, 120):
            position, velocity = 0, 0
            for _ in range(rate // 5):
                position, velocity = spring_step(position, velocity, 100, 1 / rate)
            states.append((position, velocity))
        for position, velocity in states[1:]:
            self.assertAlmostEqual(position, states[0][0], places=10)
            self.assertAlmostEqual(velocity, states[0][1], places=10)

    def test_motion_starts_gently_and_a_delayed_frame_converges(self):
        position, velocity = spring_step(0, 0, 100, 1 / 120)
        self.assertGreater(position, 0)
        self.assertLess(position, 3)
        position, velocity = spring_step(position, velocity, 100, 2)
        self.assertAlmostEqual(position, 100)
        self.assertAlmostEqual(velocity, 0)

    def test_frame_clock_aims_above_game_rate_and_skips_expired_deadlines(self):
        clock = MenuFrameClock(0)
        self.assertLessEqual(clock.delay(0), 9)
        self.assertGreater(clock.deadline, 0)
        delay = clock.delay(5)
        self.assertGreater(clock.deadline, 5)
        self.assertGreaterEqual(delay, 1)
        self.assertLessEqual(delay, 9)

    def test_frame_clock_leaves_headroom_when_rendering_is_slower(self):
        clock = MenuFrameClock(0)
        for frame in range(100):
            clock.delay(frame * .03, .02)
        self.assertGreater(clock.cost, .019)
        self.assertGreaterEqual(clock.deadline - 99 * .03, .001)
