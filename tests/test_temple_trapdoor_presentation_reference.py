"""Synthetic checks of presentation/restoration reference boundaries."""

import struct
import unittest

from tools.probe_temple_trapdoor_presentation import (
    intersect_rect, presentation_reference, project, view_for,
)


MAPPING = (66, *([0] * 16), 1)
FRAMES = ((51, 11, 8, 74, 49), (28, 1, 0, 90, 29))
CLIP = (-1000, -1000, 2000, 2000)


def fixture():
    level = bytearray(0x2000)
    struct.pack_into('>2H', level, 0x780 + 120 + 14 * 4, 0xa581, 0x1234)
    return level


def mob(phase=1):
    return (204, 245, 2, 0, 0, 10, 1, phase)


def reference(phase=1, visible=True, pending=198, relation='current'):
    return presentation_reference(fixture(), mob(phase), view_for(2, relation), visible,
                                  pending, MAPPING, FRAMES, CLIP)


class TrapDoorPresentationReferenceTests(unittest.TestCase):
    def test_terminal_restoration_does_not_require_visibility(self):
        for visible in (False, True):
            result = reference(17, visible)
            self.assertEqual(struct.unpack_from('>H', result['level'], 60 + 14 * 2)[0], 26)
            self.assertEqual(struct.unpack_from('>2H', result['level'], 0x780 + 120 + 14 * 4), (0xa500, 0x1234))
            self.assertEqual(result['mob'][3], -1)
            self.assertEqual((result['sounds'], result['resets'], result['pending_cue']), ([27], [198], -1))

    def test_upper_phase_bits_do_not_delay_restoration(self):
        self.assertEqual(reference(81, False)['mob'][3], -1)
        self.assertEqual(reference(80, False)['mob'][3], 0)

    def test_visible_offsets_are_transient_not_physics_motion(self):
        result = reference()
        self.assertEqual(result['mob'], mob())
        self.assertEqual(result['draws'][0]['mob'][:2], (215, 253))
        self.assertEqual(result['draws'][0]['y'], 253)
        self.assertEqual(result['dimensions'], (50, 75))
        self.assertEqual(result['rectangles'], [(203, 240, 254, 290)])

    def test_terminal_phase_redraws_but_does_not_enqueue_object_draw(self):
        result = reference(17)
        self.assertEqual((result['sizes'], result['redraw'], result['draws'], result['rectangles']),
                         ([27], [0], [], []))

    def test_invisible_nonterminal_phase_skips_all_drawing(self):
        result = reference(1, False)
        self.assertEqual(result['level'], fixture())
        self.assertEqual(result['mob'], mob())
        self.assertEqual((result['sizes'], result['redraw'], result['draws']), ([], [], []))
        self.assertEqual(result['dimensions'], (91, 92))

    def test_pending_cue_only_clears_the_expected_sound(self):
        for pending in (-1, 99, 197):
            self.assertEqual(reference(17, False, pending)['pending_cue'], pending)

    def test_projection_uses_364_vertical_and_510_horizontal_offsets(self):
        for relation, point in (('above', (204, 609)), ('below', (204, -119)),
                                ('right', (-306, 245)), ('left', (714, 245))):
            view = view_for(2, relation)
            self.assertEqual(project(mob(), view), (*point, view['current']))
        self.assertEqual(project(mob(), view_for(2, 'unrelated')), mob()[:3])

    def test_cell_query_uses_original_row_but_projected_column(self):
        result = reference(1, False, relation='right')
        self.assertEqual(result['visibility'], [(3, 4)])
        self.assertEqual(result['screen_cell'], 30)

    def test_reference_rejects_untested_phase_zero_and_visible_neighbors(self):
        with self.assertRaises(ValueError):
            reference(0)
        with self.assertRaises(ValueError):
            reference(1, True, relation='above')

    def test_supplied_rectangle_intersection(self):
        self.assertEqual(intersect_rect((0, 0, 50, 80), (10, 20, 60, 70)), (10, 20, 50, 70))
        self.assertEqual(intersect_rect((0, 0, 10, 10), (10, 10, 20, 20)), (0, 0, 0, 0))


if __name__ == '__main__':
    unittest.main()
