"""The temple's loose floors shake through both images of their column's
table (7:2bd6, a5-0x2c66/-0x2c7e), as the ruins' do."""

import json
import unittest

from pop2.paths import ASSET_DIR

EXPORT = ASSET_DIR / 'temple_level10.json'


def shake_pairs():
    return EXPORT.is_file() and json.loads(EXPORT.read_text(encoding='ascii'))[
        'loose_floors'].get('shake_pairs', False)


@unittest.skipUnless(EXPORT.is_file(), 'Imported temple level 10 required')
class TempleShakeTests(unittest.TestCase):
    def test_a_shaking_temple_floor_shows_its_second_image_in_phase_three(self):
        # Level 10's native room 20, column 3 (odd table: phase 1 value 1,
        # phases 3-4 value 2). The export before 2026-11-16 kept only phase
        # 1's image, so phase 3 repeated it.
        from pop2.cavern_state import CavernState
        from pop2.caverns import cavern_room, cavern_scene_signature, room_assets

        if not shake_pairs():
            self.skipTest('Temple export from before the second shake image: reimport the game')
        program, *_ = room_assets(10, 19)
        choices = program['loose_floors']['cells']['19:3']
        self.assertEqual(len(choices), 4)

        def drawn(phase):
            state = CavernState()
            state.loose.tiles[(19, 3)] = (11, (choices[0][1] & 0xfff0) | phase)
            key = cavern_scene_signature(program, 19, state)
            art = cavern_room(19, level_number=10, loose_key=key)
            return key, art.background.tobytes() + art.foreground.tobytes()

        keys = {phase: drawn(phase) for phase in (0, 1, 3, 4, 8)}
        # The room's first unit is this cell; the other nine rest.
        self.assertEqual([keys[phase][0] for phase in (0, 1, 3, 4, 8)],
                         [digit + '0' * 9 for digit in '01331'])
        self.assertTrue(keys[1][1] != keys[3][1])
        self.assertTrue(keys[0][1] != keys[3][1])
        self.assertTrue(keys[1][1] == keys[8][1])


if __name__ == '__main__':
    unittest.main()
