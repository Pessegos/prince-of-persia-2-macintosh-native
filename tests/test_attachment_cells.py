"""A drawn sword marks the cells of its own rectangle for the front redraw."""

import unittest

from PIL import Image

from pop2.animation_data import FrameRecord
from pop2.caverns import CavernRoom
from pop2.combat_art import GuardArtwork
from pop2.sequence_runtime import SequenceState

SIZE = (510, 365)


def room_with_pillar():
    # Cell (9, 1) holds a front piece (room 32's pillar 3540 is at X 467-501).
    pillar = Image.new('L', (34, 115), 255)
    return CavernRoom(Image.new('RGBA', SIZE), Image.new('RGBA', SIZE), {}, (), (), 0, 2,
                      actor_cell_occlusion={(9, 1): (pillar, (467, 125))})


class AttachmentCellTests(unittest.TestCase):
    def test_a_sword_reaching_the_next_cell_takes_that_cells_front_pieces(self):
        # 3:0e74-0e80: MarkBufsForRect(MarkFRedraw, sword rect).
        room = room_with_pillar()
        state = SequenceState(150, actor_type=2, facing=1, level_kind=2)
        body, sword = (410, 140, 455, 240), (430, 170, 480, 180)
        self.assertIsNone(room.actor_mask(1, state=state, bounds=body).getbbox())
        mask = room.actor_mask(1, state=state, bounds=body, attachment=sword)
        self.assertEqual(mask.getbbox(), (467, 125, 501, 240))

    def test_a_tumbling_character_marks_no_sword_cells(self):
        # 3:0e6c-0e72: animation state 9 skips the sword's MarkBufsForRect.
        room = room_with_pillar()
        state = SequenceState(150, actor_type=2, facing=1, level_kind=2, animation_state=9)
        mask = room.actor_mask(1, state=state, bounds=(410, 140, 455, 240),
                               attachment=(430, 170, 480, 180))
        self.assertIsNone(mask.getbbox())

    def test_guard_drawing_returns_the_rectangle_it_pasted_the_sword_in(self):
        art = GuardArtwork.__new__(GuardArtwork)
        art.frames = {1: FrameRecord(1, 0, 0, 10, 0, 0)}
        art.attachments = {0: (1, 3, 4, -20)}
        art.sword_base = 100
        art.sword_cache = {103: Image.new('RGBA', (30, 6), 'white')}
        art.body = lambda state, palette_variant=1: Image.new('RGBA', (40, 60), 'blue')
        for facing in (0, 1):
            with self.subTest(facing=facing):
                layer = Image.new('RGBA', SIZE)
                state = SequenceState(150, action=150, actor_type=2, facing=facing, target_x=200)
                rect = art.draw(layer, state, 240)
                drawn = layer.crop((0, 0, *SIZE))
                white = Image.eval(drawn.convert('L'), lambda value: 255 if value == 255 else 0)
                left, top, right, bottom = white.getbbox()
                self.assertEqual(rect, (left, top, right - 1, bottom - 1))


if __name__ == '__main__':
    unittest.main()
