"""Only the supplied first fall frame loses its tip behind the floor slope."""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from pop2.caverns import CavernRoom
from pop2.paths import ASSET_DIR


def first_fall():
    return SimpleNamespace(actor_type=0, level_kind=2, source_sequence_id=7,
                           action=102, animation_state=3, facing=0)


class WalkoffTipTests(unittest.TestCase):
    def test_only_first_leftward_temple_frame_uses_the_bounded_contour(self):
        size = (510, 365)
        floor = Image.new('RGBA', (51, 30))
        ImageDraw.Draw(floor).polygon(((0, 29), (30, 0), (50, 0), (50, 29)), fill='gray')
        floor.putpixel((24, 20), (0, 0, 0, 0))
        front = Image.new('RGBA', size)
        front.putpixel((80, 115), (0, 255, 0, 255))
        room = CavernRoom(Image.new('RGBA', size), front, {}, (), (), 0, 3,
                          platform_contours={(1, 0): [(floor, (51, 95))]})
        bounds = (55, 90, 95, 145)
        frame = Image.new('RGBA', size, 'red')
        room.draw_walkoff_tip(frame, first_fall(), bounds)
        self.assertEqual(frame.getpixel((80, 101)), (128, 128, 128, 255))
        self.assertEqual(frame.getpixel((80, 115)), (0, 255, 0, 255))
        for point in ((55, 110), (75, 115), (80, 130), (96, 115), (80, 89)):
            self.assertEqual(frame.getpixel(point), (255, 0, 0, 255), point)
        for field, values in (('actor_type', (2, 4, 7, 8, 11)),
                              ('level_kind', (1, 3, 4, 5, 6)),
                              ('source_sequence_id', (0, 9, 10, 20, 43, 68)),
                              ('action', (101, 103, 104, 105, 106, 135, 140)),
                              ('animation_state', (0, 1, 2, 4, 5, 6, 9)),
                              ('facing', (1,))):
            for value in values:
                state = first_fall()
                setattr(state, field, value)
                with self.subTest(field=field, value=value):
                    untouched = Image.new('RGBA', size, 'red')
                    room.draw_walkoff_tip(untouched, state, bounds)
                    self.assertIsNone(ImageChops.difference(untouched.convert('RGB'),
                                                          Image.new('RGB', size, 'red')).getbbox())


@unittest.skipUnless((ASSET_DIR / 'temple_level10.json').is_file(), 'Imported temple artwork required')
class WalkoffTipSceneTests(unittest.TestCase):
    def test_reported_frame_hides_only_seventeen_pixels_and_rest_of_fall_is_unchanged(self):
        from tools.audit_temple_routes import Harness, press

        harness = Harness(10, draw=True)
        scene = harness.scene
        scene.audio = None
        checked = set()
        changed = []
        try:
            scene.jump_to_room(18, 1, 225, 0)
            press(harness, 'L', True)
            for _ in range(13):
                harness.tick()
                state = scene.sequence_state
                before = replace(state)
                scene.render()
                fixed = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                with patch.object(CavernRoom, 'draw_walkoff_tip', lambda art, frame, *_args: frame):
                    scene.render()
                    ordinary = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                self.assertEqual(state, before)
                difference = ImageChops.difference(fixed, ordinary)
                if state.source_sequence_id == 7 and state.action == 102:
                    self.assertEqual((state.target_x, state.current_y, scene.terrain_motion.row), (151, -115, 2))
                    self.assertEqual(difference.getbbox(), (185, 217, 195, 220))
                    self.assertEqual(sum(count for count, colour in difference.getcolors(510 * 365)
                                         if any(colour)), 17)
                    # Every changed pixel takes the visible floor colour;
                    # no previously hidden boot/trouser pixels are revealed.
                    scenery = scene.room_cache[18].flattened().convert('RGB')
                    for y in range(217, 220):
                        for x in range(185, 195):
                            if difference.getpixel((x, y)) != (0, 0, 0):
                                self.assertEqual(fixed.getpixel((x, y)), scenery.getpixel((x, y)))
                    changed.append(state.action)
                else:
                    self.assertIsNone(difference.getbbox(), f'Unrelated frame {state.action} changed')
                checked.add(state.action)
            self.assertEqual(changed, [102])
            self.assertTrue({2, 3, 4, 5, 6, 7, 102, 103, 104, 105, 106} <= checked)
        finally:
            harness.close()
