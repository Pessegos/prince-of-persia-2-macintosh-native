"""Falling slab repaint must include the complete drawn SHAP footprint."""
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from pop2.caverns import CavernRoom, falling_floor_redraw_cells, draw_cavern_falling
from pop2.paths import ASSET_DIR


def previous_foreground(art, frame, x, y, size=(87, 43)):
    width, height = (87, 43)
    records = [record for cell in falling_floor_redraw_cells(x, y, height)
               for record in (art.floor_redraw or {}).get(cell, ())]
    return art.draw_floor_records(frame, records, (x, y - height, x + width, y + 1))


class StationaryForegroundTests(unittest.TestCase):
    def test_slab_keeps_live_foreground_and_its_holes_without_floor_records(self):
        size = (120, 100)
        foreground = Image.new('RGBA', size)
        ImageDraw.Draw(foreground).rectangle((45, 15, 85, 80), fill='red')
        ImageDraw.Draw(foreground).rectangle((60, 35, 65, 40), fill=(0, 0, 0, 0))
        room = CavernRoom(Image.new('RGBA', size), foreground, {}, (), (), 0, 3,
                          floor_redraw={})
        live = Image.new('RGBA', size, 'blue')
        block = SimpleNamespace(room=0, x=10, y=50, size=(91, 31))
        state = SimpleNamespace(loose=SimpleNamespace(falling=[block]))
        slab = Image.new('RGBA', (90, 30), 'white')
        empty = Image.new('RGBA', (51, 5))
        before = slab.tobytes()
        with patch('pop2.caverns.room_assets', return_value=(None, None, None, None)), \
                patch('pop2.caverns.cavern_command_sprite', side_effect=(slab, empty)):
            draw_cavern_falling(live, 0, state, bytearray(0x49ca), room, level_number=10)
        self.assertEqual(slab.tobytes(), before, 'cached source artwork must remain unchanged')
        for point in ((50, 30), (80, 45), (5, 30), (50, 55)):
            self.assertEqual(live.getpixel(point), (0, 0, 255, 255), point)
        for point in ((62, 37), (20, 30), (90, 30)):
            self.assertEqual(live.getpixel(point), (255, 255, 255, 255), point)


@unittest.skipUnless((ASSET_DIR / 'temple_level10.json').is_file(), 'Imported artwork required')
class ImportedFallingForegroundTests(unittest.TestCase):
    def test_detached_room8_slab_keeps_its_last_three_pixels_behind_the_right_tile(self):
        from tools.audit_temple_routes import Harness

        harness = Harness(10, draw=True)
        scene = harness.scene
        scene.audio = None
        try:
            scene.jump_to_room(7, 1, 330, 1)
            loose = scene.game.caverns.loose
            loose.trigger(scene.level_map.tile(7, 3, 1), force=True)
            loose.advance_tiles(scene.level_map)
            self.assertEqual(len(loose.falling), 1)
            # Original AnimLoose creates temple MOB3 at the floor bottom.
            self.assertEqual((loose.falling[0].y, loose.falling[0].mob_type), (245, 3))
            art = scene.level_renderer.room(7, scene.game.caverns)
            changed = 0
            for y in (263, 271, 287, 311):
                loose.falling[0].y = y
                saved = asdict(loose.falling[0])
                scene.render()
                fixed = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                with patch.object(CavernRoom, 'draw_falling_foreground', previous_foreground):
                    scene.render()
                    old = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                self.assertEqual(asdict(loose.falling[0]), saved)
                delta = ImageChops.difference(old, fixed)
                if delta.getbbox():
                    changed += 1
                scenery = art.flattened().convert('RGB')
                if delta.getbbox():
                    left, top, right, bottom = delta.getbbox()
                    self.assertGreaterEqual(left, 240)
                    self.assertLessEqual(right, 243)
                    for py in range(top, bottom):
                        for px in range(left, right):
                            if delta.getpixel((px, py)) != (0, 0, 0):
                                self.assertEqual(fixed.getpixel((px, py)), scenery.getpixel((px, py)))
            self.assertGreater(changed, 0)
        finally:
            harness.close()
