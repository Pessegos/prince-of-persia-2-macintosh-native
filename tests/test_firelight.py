"""Firelight traced over the relief read from the painted rock."""

import unittest
from unittest.mock import patch

import numpy

from pop2.firelight import (
    DIRECTIONS, LIGHT_REACH, RECESS_LIGHT, around, direction_of, flame_burn, flame_cells, flame_outlines, gaussian,
    rock_height, trace_firelight,
)

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
    """The light as traced, and the left and top of its window."""
    firelight = traced(shades, heat, recess)
    return firelight.steady, firelight.left, firelight.top


LEFTWARDS, UP, RIGHTWARDS, DOWN = 0, DIRECTIONS // 4, DIRECTIONS // 2, DIRECTIONS * 3 // 4


def reaching(direction, amount, width=4):
    """How far the light goes: as traced, but for a few directions."""
    reach = numpy.ones(DIRECTIONS)
    reach[direction - width:direction + width + 1] = amount
    return reach


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

    def test_lit_paint_stands_forward(self):
        shades = flat_rock(0.1)
        shades[100:120, 100:120] = 0.8
        height = rock_height(shades)
        self.assertGreater(height[110, 110], height[50, 50])


class FlameCellTests(unittest.TestCase):
    def test_the_cells_cover_the_flame_as_it_burns_on_average(self):
        places, shares = flame_cells(burning((4, 4), (16, 16)))
        self.assertAlmostEqual(float(shares.sum()), 1.0)
        self.assertGreater(len(places), 1)
        self.assertLess(places[:, 0].min(), 8)
        self.assertGreater(places[:, 0].max(), 12)

    def test_a_small_flame_burns_less(self):
        heat = burning((10, 10), (10, 10))
        heat[1, :, 10:] = 0
        burn = flame_burn(heat)
        self.assertGreater(burn[0], 1)
        self.assertLess(burn[1], 1)


def tall_and_wide():
    """A flame that stretches up, and one that squats and spreads."""
    heat = numpy.zeros((2, 60, 60))
    heat[0, 10:40, 28:32] = 1.0
    heat[1, 30:36, 12:48] = 1.0
    return heat


class FlameOutlineTests(unittest.TestCase):
    def test_directions_go_round_from_the_left(self):
        for (across, down), direction in (((-10, -0.001), 0), ((0, -10), UP), ((10, 0), RIGHTWARDS), ((0, 10), DOWN)):
            place = float(direction_of(numpy.array(across, dtype=float), numpy.array(down, dtype=float)))
            self.assertLess(min(abs(place - direction), DIRECTIONS - abs(place - direction)), 0.1)

    def test_every_direction_is_one_of_them(self):
        rows, columns = numpy.mgrid[-50:50, -50:50]
        places = direction_of(columns.astype(float), rows.astype(float))
        self.assertGreaterEqual(places.min(), 0)
        self.assertLess(places.max(), DIRECTIONS)

    def test_a_blur_around_the_circle_joins_the_two_ends(self):
        values = numpy.zeros(DIRECTIONS)
        values[0] = 1.0
        blurred = around(values, 2.0)
        self.assertGreater(blurred[1], 0.05)
        self.assertAlmostEqual(blurred[1], blurred[-1])
        self.assertAlmostEqual(float(blurred.sum()), 1.0)

    def test_a_tall_flame_reaches_up_and_a_wide_one_to_the_sides(self):
        _x, _y, outlines = flame_outlines(tall_and_wide())
        self.assertGreater(outlines[0, UP], outlines[1, UP] + 0.5)
        self.assertLess(outlines[0, LEFTWARDS], outlines[1, LEFTWARDS] - 0.5)
        self.assertLess(outlines[0, RIGHTWARDS], outlines[1, RIGHTWARDS] - 0.5)

    def test_it_says_how_far_past_the_usual_outline_a_frame_burns(self):
        _x, _y, outlines = flame_outlines(tall_and_wide())
        self.assertTrue(numpy.allclose(outlines.mean(axis=0), 0))

    def test_frames_alike_have_nothing_to_say(self):
        _x, _y, outlines = flame_outlines(burning((10, 10), (10, 10)))
        self.assertTrue(numpy.allclose(outlines, 0))

    def test_a_frame_without_flame_says_nothing(self):
        heat = burning((10, 10), (12, 12))
        heat[1] = 0
        _x, _y, outlines = flame_outlines(heat)
        self.assertTrue((outlines[1] == 0).all())
        self.assertTrue(numpy.allclose(outlines[0], 0))

    def test_the_middle_is_where_the_flame_burns(self):
        x, y, _outlines = flame_outlines(burning((4, 6), (16, 6)))
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 6.0)


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
        # The flame stands well off the rock, so the shadow is close behind the ridge.
        behind, open_side = row[MIDDLE + 40 - left], row[MIDDLE - 40 - left]
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
        self.assertGreater(ring.std() / ring.mean(), 0.08)

    def test_the_painted_recess_takes_less_light(self):
        # It is painted as already lit. Lit like the rock, it was a bright oval plate.
        recess = numpy.ones((20, 20))
        firelight = traced(flat_rock(), recess=recess)
        plain = traced(flat_rock())
        inside = MIDDLE - firelight.top, MIDDLE - firelight.left
        self.assertAlmostEqual(float(firelight.taken[inside]), RECESS_LIGHT + 0.26, delta=0.26)
        self.assertLess(firelight.steady[inside], plain.steady[inside] * 0.8)
        self.assertEqual(float(plain.taken.min()), 1.0)

    def test_the_recess_fades_into_the_rock(self):
        recess = numpy.ones((20, 20))
        taken = traced(flat_rock(), recess=recess).taken
        self.assertLess(float(numpy.abs(numpy.diff(taken, axis=1)).max()), 0.1)
        self.assertEqual(float(taken[0, 0]), 1.0)

    def test_reaching_further_one_way_lights_the_rock_that_way_only(self):
        firelight = traced(flat_rock())
        row, middle = MIDDLE - firelight.top, MIDDLE - firelight.left
        steady = firelight.steady
        further = firelight.at(reaching(RIGHTWARDS, 1.5), 1.0)
        self.assertGreater(further[row, middle + 50], steady[row, middle + 50] * 1.3)
        self.assertAlmostEqual(float(further[row, middle - 50]), float(steady[row, middle - 50]))

    def test_reaching_less_far_darkens_the_rock_that_way_only(self):
        firelight = traced(flat_rock())
        row, middle = MIDDLE - firelight.top, MIDDLE - firelight.left
        steady, nearer = firelight.steady, firelight.at(reaching(UP, 0.6), 1.0)
        self.assertLess(nearer[row - 50, middle], steady[row - 50, middle] * 0.7)
        self.assertAlmostEqual(float(nearer[row + 50, middle]), float(steady[row + 50, middle]))

    def test_the_veins_stay_where_they_are(self):
        # Moving the whole light slid it over the rock.
        generator = numpy.random.default_rng(3)
        shades = (gaussian(generator.random((SIZE, SIZE)), 3.0) * 2.5 - 0.7).clip(0, 1)
        firelight = traced(shades)
        steady, further = firelight.steady, firelight.at(reaching(RIGHTWARDS, 1.4, DIRECTIONS // 2 - 1), 1.0)
        rows, columns = numpy.mgrid[:steady.shape[0], :steady.shape[1]]
        lit = (steady > 0.1) & (steady < 0.8) & (numpy.hypot(rows - rows.mean(), columns - columns.mean()) > 20)
        self.assertGreater(numpy.corrcoef(steady[lit], further[lit])[0, 1], 0.97)

    def test_no_spoke_shows_between_two_directions(self):
        firelight = traced(flat_rock())
        reach = numpy.ones(DIRECTIONS)
        reach[1::2] = 1.5
        light = firelight.at(reach, 1.0)
        rows, columns = numpy.mgrid[:light.shape[0], :light.shape[1]]
        ring = numpy.abs(numpy.hypot(rows - (MIDDLE - firelight.top), columns - (MIDDLE - firelight.left)) - 40) < 0.7
        across = numpy.abs(numpy.diff(light, axis=1))[ring[:, :-1]]
        self.assertLess(float(numpy.percentile(across, 99)), 0.05)

    def test_as_far_as_traced_it_is_the_light_as_traced(self):
        firelight = traced(flat_rock())
        self.assertTrue(numpy.allclose(firelight.at(numpy.ones(DIRECTIONS), 1.0), firelight.steady))

    def test_shadows_stay_dark_however_far_it_reaches(self):
        firelight = traced(flat_rock())
        self.assertLess(float(firelight.at(numpy.full(DIRECTIONS, 2.0), 1.0)[0, 0]), 0.01)

    def test_a_small_flame_dims_the_light_and_cannot_put_it_out(self):
        firelight = traced(flat_rock())
        reach = numpy.ones(DIRECTIONS)
        full, small = firelight.at(reach, 1.0), firelight.at(reach, 0.4)
        self.assertLess(small.mean(), full.mean())
        self.assertGreater(small.mean(), full.mean() * 0.2)

    def test_it_is_always_between_nothing_and_full(self):
        shades = gaussian(numpy.random.default_rng(1).random((SIZE, SIZE)), 2.0)
        firelight = traced(shades, burning((5, 5), (15, 15), (10, 10)))
        for reach, strength in ((1.0, 1.0), (2.0, 2.0), (0.5, 0.5)):
            light = firelight.at(numpy.full(DIRECTIONS, reach), strength)
            self.assertGreaterEqual(float(light.min()), 0.0)
            self.assertLessEqual(float(light.max()), 1.0)

    def test_without_a_flame_there_is_no_light(self):
        firelight = traced(flat_rock(), numpy.zeros((3, 20, 20)))
        self.assertLess(float(firelight.steady.max()), 1e-5)
        self.assertEqual(len(firelight.outlines), 3)

    def test_a_torch_at_the_edge_of_the_room_is_cut_to_it(self):
        shades = flat_rock()
        firelight = trace_firelight(shades, no_recess(), burning((18, 10)), SIZE - 20, TOP)
        self.assertEqual(firelight.left + firelight.rest.shape[1], SIZE)
        self.assertEqual(firelight.top, MIDDLE - LIGHT_REACH)


if __name__ == '__main__':
    unittest.main()
