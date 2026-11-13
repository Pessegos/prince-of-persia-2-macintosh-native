"""Moving panels must remain visible across room boundaries."""

import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.caverns import draw_trapdoors, trapdoor_floor_redraw_cells
from pop2.paths import ASSET_DIR


class TrapDoorDrawingTests(unittest.TestCase):
    def test_floor_marks_include_the_neighbor_and_linked_top_edge(self):
        self.assertEqual(trapdoor_floor_redraw_cells((62, 83, 137, 134)),
                         ((1, 0), (2, 0), (1, 1), (2, 1)))
        self.assertEqual(trapdoor_floor_redraw_cells((62, 0, 137, 10)),
                         ((1, -1), (2, -1), (1, 0), (2, 0)))
        # MarkBufsForRect assigns Y=5 to row0 (GetRow assigns it row-1).
        self.assertEqual(trapdoor_floor_redraw_cells((62, 5, 137, 5 + 1)), ((1, 0), (2, 0)))
        self.assertEqual(trapdoor_floor_redraw_cells((490, 5, 510, 50)), ())
        self.assertEqual(trapdoor_floor_redraw_cells((62, 380, 137, 365)), ())

    def test_flat_pose_offsets_its_top_and_copies_the_front_lip(self):
        terrain = Mock()
        terrain.neighbor.return_value = None
        top = Image.new('RGBA', (40, 30), 'cyan')
        lip = Image.new('RGBA', (20, 5), 'black')
        background = Image.new('RGBA', (100, 100), 'red')

        def sprite(command, *_args):
            if command[1] == 3529:
                self.assertEqual(command[4], 0, 'the front must copy opaque zero pixels too')
                return lip
            self.assertEqual(command[4], 16)
            return top

        with patch('pop2.caverns.room_assets', return_value=(None, None, None, None)), \
                patch('pop2.caverns.cavern_command_sprite', side_effect=sprite):
            result = draw_trapdoors(background, 0, [(0, 3528, 20, 40, 19)], terrain)
        self.assertEqual(result.getpixel((20, 10)), (255, 0, 0, 255))
        self.assertEqual(result.getpixel((21, 10)), (0, 255, 255, 255))
        self.assertEqual(result.getpixel((20, 38)), (0, 0, 0, 255))
        self.assertEqual(result.getpixel((40, 38)), (0, 255, 255, 255))
        self.assertEqual(background.getpixel((20, 38)), (255, 0, 0, 255))

    def test_panels_cross_vertical_links_and_clip_to_the_view(self):
        terrain = Mock()
        terrain.neighbor.side_effect = lambda room, direction: {
            'up': 1, 'down': 2}[direction]
        sprite = Image.new('RGBA', (40, 30), 'cyan')
        # Each projected panel has its bottom at (20, 20), leaving the top
        # ten pixels offscreen.
        for room, x, y in ((0, 20, 20), (1, 20, 384), (2, 20, -344)):
            with self.subTest(room=room), \
                    patch('pop2.caverns.room_assets', return_value=(None, None, None, None)), \
                    patch('pop2.caverns.cavern_command_sprite', return_value=sprite):
                background = Image.new('RGBA', (510, 365))
                result = draw_trapdoors(background, 0, [(room, 3551, x, y, x)], terrain)
                self.assertEqual(result.getbbox(), (20, 0, 60, 20))
                self.assertEqual(result.getpixel((20, 0)), (0, 255, 255, 255))
                self.assertIsNone(background.getbbox())

    def test_unrelated_room_and_missing_link_do_not_draw(self):
        terrain = Mock()
        terrain.neighbor.return_value = None
        background = Image.new('RGBA', (510, 365))
        with patch('pop2.caverns.room_assets') as assets:
            self.assertIs(draw_trapdoors(background, 0, [(8, 3551, 20, 20, 20)], terrain),
                          background)
        assets.assert_not_called()


@unittest.skipUnless((ASSET_DIR / 'temple_level12.json').is_file()
                     and (ASSET_DIR / 'Temple.rsrc').is_file(), 'Imported temple scenery required')
class TrapDoorSceneDrawingTests(unittest.TestCase):
    def test_row_shakes_present_new_panels_in_all_six_upper_room_views(self):
        from PIL import ImageChops
        from pop2.environments import environment_for
        from tools.audit_temple_routes import Harness

        for number, rooms in ((10, (3, 8, 18)), (12, (2, 16)), (13, (6,))):
            harness = Harness(number, peaceful=True, draw=True)
            try:
                scene = harness.scene
                for room in rooms:
                    with self.subTest(level=number, room=room + 1):
                        scene.load_level(number)
                        scene.jump_to_room(room, row=0, x=110, facing=1)
                        # Supply the SEQS row-above shake endpoint. The real
                        # level-events pass resolves the link and opens it.
                        scene.sequence_state.sequence_events.append((-12, ()))
                        environment_for(scene).level_events()
                        trap = scene.game.caverns.trapdoors
                        upper = scene.level_map.neighbor(room, 'up')
                        self.assertTrue(any(obj[0] == upper and obj[1] == 3551 for obj in trap.drawn))
                        scene.render()
                        shown = scene.native_viewport.crop((0, 0, 512, 16)).convert('RGB')
                        with patch.object(trap, 'drawn', []):
                            scene.render()
                            hidden = scene.native_viewport.crop((0, 0, 512, 16)).convert('RGB')
                        self.assertIsNotNone(ImageChops.difference(shown, hidden).getbbox())
            finally:
                harness.close()

    def test_standing_on_the_panel_presents_phase1_in_its_trigger_frame(self):
        from tools.audit_temple_routes import Harness

        harness = Harness(12, peaceful=True, draw=True)
        try:
            scene = harness.scene
            scene.jump_to_room(0, row=0, x=90, facing=1)
            harness.tick()
            trap = scene.game.caverns.trapdoors
            self.assertEqual(scene.level_map.tile(0, 1, 0).kind, 0)
            self.assertEqual(trap.bank[0][7], 1)
            self.assertEqual(trap.drawn, [(0, 3551, 62, 133, 51)])
            harness.tick()
            self.assertEqual(trap.bank[0][7], 2)
        finally:
            harness.close()

    def test_room1_jump_shows_the_first_pose_and_repaints_the_neighbor_floor(self):
        from pop2.caverns import cavern_command_sprite, room_assets
        from pop2.render_opening import ROOM_ORIGIN_X
        from tools.audit_temple_routes import Harness, press

        harness = Harness(12, peaceful=True, draw=True)
        try:
            scene = harness.scene
            scene.jump_to_room(0, row=0, x=170, facing=1)
            press(harness, 'up', True)
            poses, restored = [], False
            for tick in range(35):
                if tick == 3:
                    press(harness, 'up', False)
                harness.tick()
                trap = scene.game.caverns.trapdoors
                if scene.level_map.tile(0, 1, 0).kind == 26:
                    if poses:
                        restored = True
                        self.assertFalse(trap.drawn)
                    continue
                self.assertFalse(restored)
                self.assertEqual(len(trap.drawn), 1, 'opening the tile must also show its moving panel')
                room, index, x, y, _origin = trap.drawn[0]
                self.assertEqual(room, 0)
                poses.append(index)
                self.assertEqual(trap.bank[0][7] & 31, 10 + len(poses))
                # DrawFloorBuf covers the panel's overlap with tile2, even
                # though that floor's top is in the room's back plane.
                for px, py in ((111, 115), (119, 111), (126, 107)):
                    self.assertEqual(scene.native_viewport.getpixel((ROOM_ORIGIN_X + px, py)),
                                     scene.background.getpixel((px, py)), (index, px, py))
                if len(poses) == 1:
                    _, resources, palette, shapes = room_assets(12, 0)
                    sprite = cavern_command_sprite(['back', 3551, x, y, 16], resources, palette, shapes)
                    self.assertEqual(scene.native_viewport.getpixel((ROOM_ORIGIN_X + 80, 128)),
                                     sprite.getpixel((80 - x, 128 - y + sprite.height)))
                    self.assertNotEqual(scene.native_viewport.getpixel((ROOM_ORIGIN_X + 80, 128)),
                                        scene.background.getpixel((80, 128)))
            # The paired Macintosh recording shows all six low phases11..16,
            # then the closed cell. In ad33e6d the first entry was an empty hole.
            self.assertEqual(poses, [3551, 3552, 3553, 3554, 3528, 3551])
            self.assertTrue(restored)
        finally:
            harness.close()

    def test_room1_jump_redraws_the_flat_panels_front_lip(self):
        from pop2.caverns import cavern_command_sprite, room_assets
        from pop2.render_opening import ROOM_ORIGIN_X
        from tools.audit_temple_routes import Harness, press

        harness = Harness(12, peaceful=True, draw=True)
        try:
            scene = harness.scene
            scene.jump_to_room(0, row=0, x=390, facing=1)
            press(harness, 'up', True)
            harness.tick(3)
            press(harness, 'up', False)
            seen = False
            for _ in range(32):
                harness.tick()
                for room, index, x, y, _origin in scene.game.caverns.trapdoors.drawn:
                    if room != 0 or index != 3528:
                        continue
                    _, resources, palette, shapes = room_assets(12, 0)
                    lip = cavern_command_sprite(['back', 3529, x, y, 0], resources, palette, shapes)
                    # The open slot has no static front. This pixel must be
                    # supplied by DrawObjTrapDoor's second piece, not the wall.
                    actual = scene.native_viewport.getpixel((ROOM_ORIGIN_X + x + 25, y - lip.height + 2))
                    self.assertEqual(actual, lip.getpixel((25, 2)))
                    seen = True
            self.assertTrue(seen, 'the real jump must trigger the distant room1 trap')
            self.assertEqual(scene.level_map.tile(0, 1, 0).kind, 26)
        finally:
            harness.close()


if __name__ == '__main__':
    unittest.main()
