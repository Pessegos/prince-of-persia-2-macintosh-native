"""tools.native_character runs the original's per-character setup."""

from pathlib import Path
import unittest

try:
    import unicorn
except ImportError:  # pragma: no cover - optional research dependency
    unicorn = None

RECOVERY = Path(__file__).resolve().parents[2] / 'PoP2-Mac-Code-Recovery'


@unittest.skipUnless(unicorn is not None and (RECOVERY / 'resource_forks').is_dir(),
                     'Unicorn and the original recovery are required')
class NativeCharacterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.native_character import NativeCharacter
        from tools.probe_foreground_cells import probe_level

        directory = RECOVERY / 'resource_forks'
        executable = (directory / 'Prince of Persia 2.bin').read_bytes()
        prince = (directory / 'Prince.rsrc.bin').read_bytes()
        cls.character = NativeCharacter(executable, probe_level(12, prince))

    def fall(self, room):
        # SEQS 7's fall (action 106, mode 4) in row 2, column 6.
        fields = dict(facing=0, action=106, mode=4, row=2, column=6, selected=7, sequence=7,
                      room=room, sequence_mode=0)
        return self.character.frame(fields, 368, 288, (71, 34))

    def test_a_room_past_the_count_clips_a_fall_at_the_rows_top(self):
        # Level 12 counts 26 rooms (LEVL 0x2180): native room 30's empty
        # cells read as walls (GetUndefineCellId 4:28b6), so ClipChar's
        # recrop puts the clip's top at row 2's top, 245.
        self.assertEqual(self.fall(30)['clip'][0], 245)
        self.assertNotEqual(self.fall(26)['clip'][0], 245)

    def test_marks_cover_the_cells_of_the_rectangle(self):
        setup = self.fall(30)
        self.assertEqual(setup['rect'][1:], (334, 289, 368))
        fronts = sorted(cell for kind, cell, _rect in setup['marks'] if kind == 'front')
        self.assertEqual(fronts, [16, 17, 26, 27])

    def test_a_head_above_y_five_marks_the_border_row(self):
        # GetCellNumber 4:29d8-2a10 numbers the border row's cells
        # -(column + 1): MarkBufsForRect routes them to MarkTop 5:16f2.
        fields = dict(facing=0, action=79, mode=1, row=0, column=7, selected=28, sequence=28,
                      room=5, sequence_mode=0)
        setup = self.character.frame(fields, 382, 71, (90, 30))
        cells = {cell for kind, cell, _rect in setup['marks'] if kind == 'front'}
        self.assertIn(-8, cells)


if __name__ == '__main__':
    unittest.main()
