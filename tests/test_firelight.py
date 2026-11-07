"""Firelight traced over the relief read from the painted rock."""

import unittest
from unittest.mock import patch

import numpy

from pop2.firelight import LIGHT_REACH, SWING, flame_cells, flame_lean, gaussian, rock_height, trace_firelight

SIZE = 300
MIDDLE = SIZE // 2
LEFT, TOP = MIDDLE - 10, MIDDLE - 10


def flat_rock(shade=0.3):
    return numpy.full((SIZE, SIZE), shade)


def no_recess():
    return numpy.zeros((20, 20))


def burning(*places):
    """One frame per place: a little flame around that spot of a 20x20 sprite."""
    heat = numpy.zeros((len(places), 20, 20))
    for frame, (x, y) in enumerate(places):
        heat[frame, y - 2:y + 3, x - 1:x + 2] = 1.0
    return heat


def traced(shades, heat=None, recess=None):
    heat = burning((10, 10)) if heat is None else heat
    return trace_firelight(shades, no_recess() if recess is None else recess, heat, LEFT, TOP)


def light_on(shades, heat=None, recess=None):
    """The light with the flame at rest, and the left and top of its window."""
    firelight = traced(shades, heat, recess)
    return firelight.at(0.0, 0.0, 1.0), firelight.left, firelight.top


class ReliefTests(unittest.TestCase):
    def test_a_blur_keeps_an_even_surface(self):
        self.assertTrue(numpy.allclose(gaussian(numpy.full((40, 50), 0.7), 3.0), 0.7))

    def test_a_blur_spreads_a_point_and_keeps_its_amount(self):
        values = numpy.zeros((41, 41))
        values[20, 20] = 1.0
        blurred = gaussian(values, 2.0)
        self.assertAlmostEqual(blurred.sum(), 1.0, places=3)
        self.assertLess(blurred[20, 20], 0.1)
        self.assertGreater(blurred[20, 22], 0.0)

    def test_lit_paint_stands_forward_and_the_recess_falls_back(self):
        shades = flat_rock(0.1)
        shades[100:120, 100:120] = 0.8
        recess = numpy.zeros((SIZE, SIZE))
        recess[200:240, 200:240] = 1.0
        height = rock_height(shades, recess)
        self.assertGreater(height[110, 110], height[50, 50])
        self.assertLess(height[220, 220], height[50, 50])


class FlameCellTests(unittest.TestCase):
    def test_the_cells_cover_the_flame_as_it_burns_on_average(self):
        places, shares = flame_cells(burning((4, 4), (16, 16)))
        self.assertAlmostEqual(float(shares.sum()), 1.0)
        self.assertGreater(len(places), 1)
        self.assertLess(places[:, 0].min(), 8)
        self.assertGreater(places[:, 0].max(), 12)

    def test_each_frame_leans_where_its_flame_stands(self):
        lean, _burn = flame_lean(burning((4, 10), (16, 10)))
        self.assertLess(lean[0, 0], 0)
        self.assertGreater(lean[1, 0], 0)
        self.assertEqual(lean[0, 1], lean[1, 1])

    def test_a_usual_lean_is_one_whatever_the_size_of_the_art(self):
        for apart in (1, 6):
            lean, _burn = flame_lean(burning((10 - apart, 10), (10 + apart, 10)))
            self.assertAlmostEqual(float(lean[:, 0].std()), 1.0)

    def test_a_small_flame_burns_less(self):
        heat = burning((10, 10), (10, 10))
        heat[1, :, 10:] = 0
        _lean, burn = flame_lean(heat)
        self.assertGreater(burn[0], 1)
        self.assertLess(burn[1], 1)

    def test_frames_that_do_not_lean_stay_at_rest(self):
        lean, _burn = flame_lean(burning((10, 10), (10, 10)))
        self.assertTrue((lean == 0).all())


class TracedLightTests(unittest.TestCase):
    def test_on_even_rock_it_fades_with_distance(self):
        light, left, top = light_on(flat_rock())
        row = light[MIDDLE - top, MIDDLE - left:]
        self.assertTrue((numpy.diff(row[14:]) <= 1e-3).all())
        self.assertGreater(row[14], 0.8)
        self.assertLess(row[-1], 0.02)

    def test_it_stops_at_its_reach(self):
        light, left, top = light_on(flat_rock())
        self.assertLessEqual(light.shape[0], 2 * LIGHT_REACH)
        self.assertLessEqual(light.shape[1], 2 * LIGHT_REACH)
        self.assertEqual((left, top), (MIDDLE - LIGHT_REACH, MIDDLE - LIGHT_REACH))

    def test_rock_in_the_way_casts_a_shadow(self):
        # A wall of bright paint to the right of the flame, none to the left.
        shades = flat_rock(0.2)
        shades[:, MIDDLE + 30:MIDDLE + 36] = 0.9
        light, left, top = light_on(shades)
        row = light[MIDDLE - top]
        behind, open_side = row[MIDDLE + 56 - left], row[MIDDLE - 56 - left]
        self.assertLess(behind, open_side * 0.6)

    def test_the_side_of_a_ridge_facing_the_flame_takes_more_light(self):
        shades = flat_rock(0.2)
        shades[:, MIDDLE + 40:MIDDLE + 46] = 0.9
        with patch('pop2.firelight.BOUNCE', 0.0):
            light, left, top = light_on(shades)
        row = light[MIDDLE - top]
        near_side = row[MIDDLE + 37 - left:MIDDLE + 42 - left].max()
        far_side = row[MIDDLE + 45 - left:MIDDLE + 50 - left].max()
        self.assertGreater(near_side, far_side * 1.5)

    def test_it_is_no_ball_on_rock_with_relief(self):
        # A blurred ball of light looks the same at every point of a ring.
        generator = numpy.random.default_rng(3)
        shades = gaussian(generator.random((SIZE, SIZE)), 3.0) * 2.5 - 0.7
        light, left, top = light_on(shades.clip(0, 1))
        rows, columns = numpy.mgrid[top:top + light.shape[0], left:left + light.shape[1]]
        distance = numpy.hypot(columns - MIDDLE, rows - MIDDLE)
        ring = light[(distance > 30) & (distance < 40)]
        self.assertGreater(ring.std() / ring.mean(), 0.1)

    def test_a_recess_keeps_light_in_its_walls(self):
        recess = numpy.ones((20, 20))
        sunk = light_on(flat_rock(), recess=recess)[0]
        open_wall = light_on(flat_rock())[0]
        inside = MIDDLE - (MIDDLE - LIGHT_REACH)
        self.assertLess(sunk[inside, inside + 40], open_wall[inside, inside + 40])

    def test_moving_the_flame_moves_the_light(self):
        firelight = traced(flat_rock())
        middle = firelight.rest.shape[1] // 2
        left_lit = firelight.at(-SWING, 0.0, 1.0)
        right_lit = firelight.at(SWING, 0.0, 1.0)
        self.assertGreater(left_lit[:, :middle].sum(), left_lit[:, middle:].sum())
        self.assertLess(right_lit[:, :middle].sum(), right_lit[:, middle:].sum())
        up, down = firelight.at(0.0, -SWING, 1.0), firelight.at(0.0, SWING, 1.0)
        centre = firelight.rest.shape[0] // 2
        self.assertGreater(up[:centre].sum(), down[:centre].sum())

    def test_moving_the_flame_moves_the_shadows(self):
        shades = flat_rock(0.2)
        shades[:, MIDDLE + 30:MIDDLE + 36] = 0.9
        firelight = traced(shades)
        behind = MIDDLE - firelight.top, MIDDLE + 44 - firelight.left
        self.assertGreater(firelight.at(SWING, 0.0, 1.0)[behind], firelight.at(-SWING, 0.0, 1.0)[behind] * 1.3)

    def test_the_light_goes_no_further_than_it_was_traced(self):
        firelight = traced(flat_rock())
        self.assertTrue((firelight.at(SWING * 5, 0.0, 1.0) == firelight.at(SWING, 0.0, 1.0)).all())

    def test_between_two_places_the_light_is_between_their_lights(self):
        firelight = traced(flat_rock())
        rest, half, full = (firelight.at(x, 0.0, 1.0) for x in (0.0, SWING / 2, SWING))
        row, column = rest.shape[0] // 2, rest.shape[1] // 2 + 30
        self.assertGreater(half[row, column], rest[row, column])
        self.assertLess(half[row, column], full[row, column])

    def test_a_small_flame_dims_the_light_and_cannot_put_it_out(self):
        firelight = traced(flat_rock())
        full, small = firelight.at(0.0, 0.0, 1.0), firelight.at(0.0, 0.0, 0.4)
        self.assertLess(small.mean(), full.mean())
        self.assertGreater(small.mean(), full.mean() * 0.2)

    def test_it_is_always_between_nothing_and_full(self):
        shades = gaussian(numpy.random.default_rng(1).random((SIZE, SIZE)), 2.0)
        firelight = traced(shades, burning((5, 5), (15, 15), (10, 10)))
        for x, y, strength in ((0.0, 0.0, 1.0), (SWING, -SWING, 2.0), (-SWING, SWING, 0.5)):
            light = firelight.at(x, y, strength)
            self.assertGreaterEqual(float(light.min()), 0.0)
            self.assertLessEqual(float(light.max()), 1.0)

    def test_without_a_flame_there_is_no_light(self):
        firelight = traced(flat_rock(), numpy.zeros((3, 20, 20)))
        self.assertEqual(float(firelight.at(SWING, 0.0, 1.0).max()), 0.0)
        self.assertEqual(len(firelight.lean), 3)

    def test_a_torch_at_the_edge_of_the_room_is_cut_to_it(self):
        shades = flat_rock()
        firelight = trace_firelight(shades, no_recess(), burning((18, 10)), SIZE - 20, TOP)
        self.assertEqual(firelight.left + firelight.rest.shape[1], SIZE)
        self.assertEqual(firelight.top, MIDDLE - LIGHT_REACH)


if __name__ == '__main__':
    unittest.main()
