"""Temple walk-off falls keep the same floor-contour policy as ledges."""

from dataclasses import replace
from itertools import product
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from pop2.caverns import CavernRoom
from pop2.paths import ASSET_DIR
from pop2.render_opening import ledge_surface_clip


def falling_prince(pose=102, facing=0):
    return SimpleNamespace(actor_type=0, source_sequence_id=7, sequence_id=214,
                           level_kind=2, animation_state=3, action=pose, facing=facing)


class TempleFallSurfaceTests(unittest.TestCase):
    def test_admission_uses_temple_fall_controller_pose_and_drawn_row(self):
        for facing, pose, mode, row in product((0, 1), range(102, 107), (3, 4), range(3)):
            state = falling_prince(pose, facing)
            state.animation_state = mode
            bounds = (139, row * 120 + 41, 195, row * 120 + 111)
            with self.subTest(facing=facing, pose=pose, mode=mode, row=row):
                self.assertEqual(ledge_surface_clip(state, bounds),
                                 (row, (139, row * 120 + 107, 196, row * 120 + 112)))
        bounds = (139, 161, 195, 231)
        for field, values in (('actor_type', (2, 4, 7, 8, 11)),
                              ('level_kind', (1, 3, 4, 5, 6, None)),
                              ('source_sequence_id', (0, 9, 14, 20, 43, 68)),
                              ('action', (101, 107, 135, 140)),
                              ('animation_state', (0, 1, 2, 5, 6, 9))):
            for value in values:
                state = falling_prince()
                setattr(state, field, value)
                with self.subTest(field=field, value=value):
                    self.assertIsNone(ledge_surface_clip(state, bounds))

    def test_both_facings_keep_the_support_line_contour_holes_and_feet(self):
        size = (510, 365)
        floor = Image.new('RGBA', (51, 30))
        ImageDraw.Draw(floor).polygon(((0, 29), (30, 0), (50, 0), (50, 29)), fill='gray')
        floor.putpixel((24, 20), (0, 0, 0, 0))
        front = Image.new('RGBA', size)
        front.putpixel((80, 115), (0, 255, 0, 255))
        room = CavernRoom(Image.new('RGBA', size), front, {}, (), (), 0, 3,
                          floor_redraw={(1, 0): [(floor, (51, 95))]})
        for facing in (0, 1):
            with self.subTest(facing=facing):
                frame = Image.new('RGBA', size, 'red')
                room.draw_actor_foreground(frame, falling_prince(facing=facing), (55, 90, 95, 145))
                self.assertEqual(frame.getpixel((70, 110)), (128, 128, 128, 255))
                for point in ((80, 106), (55, 110), (75, 115), (80, 130), (96, 115)):
                    self.assertEqual(frame.getpixel(point), (255, 0, 0, 255), point)
                self.assertEqual(frame.getpixel((80, 115)), (0, 255, 0, 255))


@unittest.skipUnless((ASSET_DIR / 'temple_level10.json').is_file(), 'Imported temple artwork required')
class TempleFallSceneTests(unittest.TestCase):
    def test_real_walk_offs_restore_the_boot_without_changing_falls_or_other_pixels(self):
        from tools.audit_temple_routes import Harness, press

        # Unmodified supported starts: the reported room, then one left edge
        # in each temple level. Room indices are zero-based here.
        sites = ((10, 18, 1, 225), (10, 6, 1, 327), (11, 20, 2, 174),
                 (12, 6, 0, 327), (13, 3, 1, 378))
        harness = Harness(10, draw=True)
        scene = harness.scene
        scene.audio = None
        changed = set()
        try:
            for site in sites:
                with self.subTest(site=site):
                    number, room, row, x = site
                    scene.load_level(number)
                    scene.jump_to_room(room, row, x, 0)
                    press(harness, 'L', True)
                    for _ in range(16):
                        harness.tick()
                        state = scene.sequence_state
                        if scene.room_id != room:
                            break
                        if state.source_sequence_id != 7 or not 102 <= state.action <= 106:
                            continue
                        before = replace(state)
                        scene.render()
                        improved = scene.native_viewport.convert('RGB').copy()
                        with patch('pop2.caverns.ledge_surface_clip', return_value=None):
                            scene.render()
                            previous = scene.native_viewport.convert('RGB').copy()
                        self.assertEqual(state, before)
                        difference = ImageChops.difference(improved, previous)
                        if difference.getbbox():
                            changed.add(site)
                        if site == sites[0] and state.action == 102:
                            self.assertEqual((state.target_x, state.current_y, scene.terrain_motion.row),
                                             (151, -115, 2))
                            self.assertEqual(improved.getpixel((186, 220)), (161, 133, 153))
                            self.assertEqual(improved.getpixel((190, 222)), (230, 115, 58))
                            self.assertNotEqual(previous.getpixel((190, 222)), improved.getpixel((190, 222)))
                            self.assertIsNone(difference.crop((0, 227, 512, 365)).getbbox())
                        if state.action == 105:
                            break
                    self.assertTrue(scene.combat.player.alive)
            self.assertEqual(changed, set(sites))
        finally:
            harness.close()
