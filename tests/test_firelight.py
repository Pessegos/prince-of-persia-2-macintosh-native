"""Firelight traced over the relief read from the painted rock."""

import unittest
from unittest.mock import patch

import numpy

from pop2.firelight import LIGHT_REACH, flame_cells, gaussian, rock_height, trace_firelight

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


def light_on(shades, heat=None, recess=None):
    heat = burning((10, 10)) if heat is None else heat
    return trace_firelight(shades, no_recess() if recess is None else recess, heat, LEFT, TOP)


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
    def test_each_frame_burns_where_its_flame_is(self):
        places, burn = flame_cells(burning((4, 4), (16, 16)))
        self.assertEqual(len(places), burn.shape[1])
        self.assertLess(places[burn[0].argmax()][0], places[burn[1].argmax()][0])

    def test_a_small_flame_burns_less_on_the_whole(self):
        heat = burning((10, 10), (10, 10))
        heat[1, :, 9:] = 0
        _places, burn = flame_cells(heat)
        self.assertGreater(burn[0].sum(), burn[1].sum())


class TracedLightTests(unittest.TestCase):
    def test_on_even_rock_it_fades_with_distance(self):
        lights, left, top = light_on(flat_rock())
        row = lights[0, MIDDLE - top, MIDDLE - left:]
        self.assertTrue((numpy.diff(row[12:]) <= 1e-6).all())
        self.assertGreater(row[12], 0.8)
        self.assertLess(row[-1], 0.02)

    def test_it_stops_at_its_reach(self):
        lights, left, top = light_on(flat_rock())
        self.assertLessEqual(lights.shape[1], 2 * LIGHT_REACH)
        self.assertLessEqual(lights.shape[2], 2 * LIGHT_REACH)
        self.assertEqual((left, top), (MIDDLE - LIGHT_REACH, MIDDLE - LIGHT_REACH))

    def test_rock_in_the_way_casts_a_shadow(self):
        # A wall of bright paint to the right of the flame, none to the left.
        shades = flat_rock(0.2)
        shades[:, MIDDLE + 30:MIDDLE + 36] = 0.9
        lights, left, top = light_on(shades)
        row = lights[0, MIDDLE - top]
        behind, open_side = row[MIDDLE + 56 - left], row[MIDDLE - 56 - left]
        self.assertLess(behind, open_side * 0.6)

    def test_the_side_of_a_ridge_facing_the_flame_takes_more_light(self):
        shades = flat_rock(0.2)
        shades[:, MIDDLE + 40:MIDDLE + 46] = 0.9
        with patch('pop2.firelight.BOUNCE', 0.0):
            lights, left, top = light_on(shades)
        row = lights[0, MIDDLE - top]
        near_side = row[MIDDLE + 37 - left:MIDDLE + 42 - left].max()
        far_side = row[MIDDLE + 45 - left:MIDDLE + 50 - left].max()
        self.assertGreater(near_side, far_side * 1.5)

    def test_it_is_no_ball_on_rock_with_relief(self):
        # A blurred ball of light looks the same at every point of a ring.
        generator = numpy.random.default_rng(3)
        shades = gaussian(generator.random((SIZE, SIZE)), 3.0) * 2.5 - 0.7
        lights, left, top = light_on(shades.clip(0, 1))
        rows, columns = numpy.mgrid[top:top + lights.shape[1], left:left + lights.shape[2]]
        distance = numpy.hypot(columns - MIDDLE, rows - MIDDLE)
        ring = lights[0][(distance > 30) & (distance < 40)]
        self.assertGreater(ring.std() / ring.mean(), 0.2)

    def test_a_recess_keeps_light_in_its_walls(self):
        recess = numpy.ones((20, 20))
        sunk = light_on(flat_rock(), recess=recess)[0][0]
        open_wall = light_on(flat_rock())[0][0]
        inside = MIDDLE - (MIDDLE - LIGHT_REACH)
        self.assertLess(sunk[inside, inside + 40], open_wall[inside, inside + 40])

    def test_a_flame_on_one_side_lights_that_side(self):
        lights, _left, _top = light_on(flat_rock(), burning((3, 10), (17, 10)))
        middle = lights.shape[2] // 2
        self.assertGreater(lights[0, :, :middle].sum(), lights[0, :, middle:].sum())
        self.assertLess(lights[1, :, :middle].sum(), lights[1, :, middle:].sum())

    def test_a_small_flame_dims_the_light_and_cannot_put_it_out(self):
        # Deepened by subtraction, the smallest real frame came out at 0.001.
        heat = burning((10, 10), (10, 10), (10, 10))
        heat[2, 8] = 0
        lights, _left, _top = light_on(flat_rock(), heat)
        self.assertLess(lights[2].mean(), lights[0].mean())
        self.assertGreater(lights[2].mean(), lights[0].mean() * 0.15)

    def test_it_is_always_between_nothing_and_full(self):
        shades = gaussian(numpy.random.default_rng(1).random((SIZE, SIZE)), 2.0)
        lights, _left, _top = light_on(shades, burning((5, 5), (15, 15), (10, 10)))
        self.assertGreaterEqual(float(lights.min()), 0.0)
        self.assertLessEqual(float(lights.max()), 1.0)

    def test_without_a_flame_there_is_no_light(self):
        lights, _left, _top = light_on(flat_rock(), numpy.zeros((3, 20, 20)))
        self.assertEqual(float(lights.max()), 0.0)

    def test_a_torch_at_the_edge_of_the_room_is_cut_to_it(self):
        shades = flat_rock()
        lights, left, top = trace_firelight(shades, no_recess(), burning((18, 10)), SIZE - 20, TOP)
        self.assertEqual(left + lights.shape[2], SIZE)
        self.assertEqual(top, MIDDLE - LIGHT_REACH)


if __name__ == '__main__':
    unittest.main()
