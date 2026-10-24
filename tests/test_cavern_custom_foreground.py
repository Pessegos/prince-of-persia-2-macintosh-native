from dataclasses import replace
import struct
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.caverns import cavern_room, custom_foreground_records
from pop2.paths import ASSET_DIR


class CustomForegroundTests(unittest.TestCase):
    def resources(self):
        records = ((0, 300, 410, 1, 16, 0), (1, 200, 460, 0, 16, 0),
                   (2, 310, 420, 1, 16, -1), (3, 320, 430, 2, 16, 0))
        data = bytearray(30 + len(records) * 32)
        struct.pack_into('>H', data, 2, 4050)
        struct.pack_into('>H', data, 28, len(records))
        for index, record in enumerate(records):
            struct.pack_into('>6h', data, 30 + index * 32, *record)
        return {'CUST': {4050: {'data': bytes(data)}}}

    def test_only_visible_foreground_records_keep_their_full_room_coverage(self):
        self.assertEqual(custom_foreground_records(self.resources(), 2), {(4050, 410, 300, 16)})
        self.assertEqual(custom_foreground_records(self.resources(), 3), set())
        self.assertEqual(custom_foreground_records({}, 2), set())

    def test_truncated_custom_header_or_records_are_rejected(self):
        for length in (12, 30, 62):
            resources = self.resources()
            resources['CUST'][4050]['data'] = resources['CUST'][4050]['data'][:length]
            with self.assertRaisesRegex(ValueError, 'Truncated custom scenery'):
                custom_foreground_records(resources, 2)

    def art(self, *, custom=True, redraw=False):
        commands = [['front', 4050, 410, 300, 16, 0, [290, 410, 300, 420], 4, 9, 0],
                    ['front', 3501, 440, 300, 16, 0, [290, 440, 300, 450], 4, 9, 0]]
        program = {'version': 6, 'level': 5, 'rooms': {'2': commands}}
        resources = self.resources() if custom else {}
        shapes = {4050: Image.new('RGBA', (10, 10), 'red'),
                  3501: Image.new('RGBA', (10, 10), 'green')}
        variant = None
        if redraw:
            variant = {'commands': commands + [
                ['back', 3501, 410, 300, 16, 2, [290, 410, 300, 420], 4, 8, 2]],
                'redraw_start': 2, 'floor_redraw': [], 'climb_redraw': {}}
        with (patch('pop2.caverns.room_assets', return_value=(program, resources, {}, shapes)),
              patch('pop2.caverns.loose_variant', return_value=variant)):
            return cavern_room(2, level_number=5)

    def test_clean_cut_admission_cell_does_not_limit_custom_actor_mask(self):
        art = self.art()
        # Actor touches column8/row2, not the CUST clean-cut caller (9, 0).
        mask = art.actor_mask(2, bounds=(410, 280, 445, 310))
        self.assertEqual(mask.getpixel((415, 295)), 255)
        self.assertEqual(mask.getpixel((445, 295)), 0)
        self.assertEqual(replace(art, custom_occlusion=None).actor_mask(
            2, bounds=(410, 280, 445, 310)).getpixel((415, 295)), 0)

    def test_ordinary_foreground_retains_cell_admission(self):
        art = self.art(custom=False)
        self.assertEqual(art.actor_mask(2, bounds=(410, 280, 445, 310)).getpixel((415, 295)), 0)
        self.assertEqual(art.actor_mask(0, bounds=(459, 1, 480, 30)).getpixel((415, 295)), 255)

    def test_custom_mask_also_applies_to_legacy_exports_and_fallback_rows(self):
        art = replace(self.art(), actor_cell_occlusion=None)
        self.assertEqual(art.actor_mask(2, bounds=(410, 280, 445, 310)).getpixel((415, 295)), 255)
        self.assertEqual(art.actor_mask(2).getpixel((415, 295)), 255)

    def test_later_background_repaint_can_cover_custom_foreground(self):
        art = self.art(redraw=True)
        self.assertEqual(art.custom_occlusion.getpixel((415, 295)), 0)
        self.assertEqual(art.actor_mask(2, bounds=(410, 280, 420, 310)).getpixel((415, 295)), 0)


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class CarpetRoomForegroundTests(unittest.TestCase):
    def test_right_pillar_and_ascent_are_foreground_below_the_admission_row(self):
        art = cavern_room(2, level_number=5)
        old = replace(art, custom_occlusion=None)
        for bounds, point in (((410, 258, 439, 346), (425, 300)),
                              ((461, 205, 489, 288), (475, 260))):
            with self.subTest(bounds=bounds):
                mask = art.actor_mask(2, bounds=bounds)
                self.assertEqual(mask.getpixel(point), 255)
                self.assertEqual(old.actor_mask(2, bounds=bounds).getpixel(point), 0)

    def test_custom_pillar_covers_actor_ink_not_just_the_floor_redraw(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(5)
        scene.peaceful = True
        scene.jump_to_room(2, 2, 430, 0)
        room, state = scene.room_cache[2], scene.sequence_state
        bounds, record = scene.player_bounds(), scene.frames[scene.action]
        layer = Image.new('RGBA', (510, 365))
        sprite = scene.player_sprite(scene.action)
        left = state.target_x - record.offset_x
        layer.paste(sprite, (left, bounds[1]), sprite)
        covered = ImageChops.multiply(layer.getchannel('A'), room.custom_occlusion)
        self.assertIsNotNone(covered.getbbox())
        background = room.flattened()
        drawn = scene.composite_actor(background, layer, 2, bounds[3], state, bounds, record)
        differences = ImageChops.difference(drawn.convert('RGB'), background.convert('RGB'))
        for channel in differences.split():
            self.assertIsNone(ImageChops.multiply(channel, covered).getbbox())


if __name__ == '__main__':
    unittest.main()
