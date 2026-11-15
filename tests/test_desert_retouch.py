from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageChops

from pop2 import desert_retouch
from pop2.desert_retouch import retouched_background
from pop2.paths import ASSET_DIR
from pop2.preview_cache import preview_fingerprint


class DesertRetouchBundleTests(unittest.TestCase):
    def test_a_picture_other_than_the_native_source_is_left_alone(self):
        for room in (0, 1):
            source = Image.new('RGBA', (510, 365), (10, 20, 30, 255))
            self.assertIs(retouched_background(room, source), source)

    def test_rooms_without_an_approved_edit_are_never_touched(self):
        source = Image.new('RGBA', (510, 365), 'black')
        self.assertIs(retouched_background(2, source), source)

    def test_the_bundle_records_both_seam_rooms(self):
        records = {room: record for room, (record, _patch) in desert_retouch._retouch_bundle().items()}
        self.assertEqual(set(records), {0, 1})
        for record, patch_image in desert_retouch._retouch_bundle().values():
            rect = record['source_rect']
            self.assertEqual(patch_image.size, (rect[2] - rect[0], rect[3] - rect[1]))
            opaque = sum(1 for alpha in patch_image.getchannel('A').getdata() if alpha)
            self.assertEqual(opaque, record['pixels'])

    def test_fingerprint_tracks_the_desert_retouch_artwork(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'assets'
            assets.mkdir()
            first = preview_fingerprint(assets, root)
            Image.new('RGBA', (2, 2), 'red').save(root / 'desert_retouch.png')
            second = preview_fingerprint(assets, root)
            self.assertNotEqual(first, second)
            (root / 'desert_retouch.json').write_text('{"schema":1}', encoding='ascii')
            self.assertNotEqual(second, preview_fingerprint(assets, root))


@unittest.skipUnless((ASSET_DIR / 'Desert.rsrc').is_file(), 'Imported Desert.rsrc required')
class DesertSeamArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.desert import DesertScene
        from pop2.render_opening import load_resource_file

        resources = load_resource_file('Desert.rsrc')
        cls.native = {room: DesertScene.read(resources, room, retouch=False) for room in (0, 1)}
        cls.ported = {room: DesertScene.read(resources, room) for room in (0, 1)}

    @staticmethod
    def column(image, x, rows):
        return [image.getpixel((x, y))[:3] for y in rows]

    def test_the_stone_chamber_sky_continues_the_shore_sky_at_the_join(self):
        # Rows 2-89 are open sky beside the join in both paintings.
        rows = range(2, 90)
        shore = self.native[1].room.background
        before = self.native[0].room.background
        after = self.ported[0].room.background
        # The edit lifts the painting by exactly 20 rows at the join.
        self.assertEqual(self.column(before, 509, range(22, 100)), self.column(after, 509, range(2, 80)))

        def mean(image, columns, y):
            return [sum(image.getpixel((x, y))[c] for x in columns) / len(columns) for c in range(3)]

        def mismatch(image):
            return sum(abs(a - b) for y in rows
                       for a, b in zip(mean(image, range(490, 510), y), mean(shore, range(0, 20), y)))

        # The native painting is 20 pixels low, so its sky gradient is out of
        # step with the shore's; lifted, the two dithered gradients agree.
        self.assertGreater(mismatch(before), 1500)
        self.assertLess(mismatch(after), 60)

    def test_the_lifted_chamber_keeps_its_floor_cliff_and_moving_exit(self):
        before, after = self.native[0], self.ported[0]
        changed = ImageChops.difference(before.room.background.convert('RGB'), after.room.background.convert('RGB')).getbbox()
        self.assertEqual(changed, (0, 0, 510, 190))   # floor, stones and lower cliff untouched
        self.assertIsNone(ImageChops.difference(before.room.foreground, after.room.foreground).getbbox())
        self.assertEqual(before.shapes.keys(), after.shapes.keys())
        for key, shape in before.shapes.items():
            self.assertIsNone(ImageChops.difference(shape, after.shapes[key]).getbbox())
        # The native painting starts one row down; the approved edit has no
        # black top line.
        self.assertEqual(before.room.background.getpixel((300, 0))[:3], (0, 0, 0))
        self.assertNotEqual(after.room.background.getpixel((300, 0))[:3], (0, 0, 0))

    def test_the_shore_loses_only_its_grey_shallows_at_the_join(self):
        before = self.native[1].room.background
        after = self.ported[1].room.background
        self.assertEqual(ImageChops.difference(before.convert('RGB'), after.convert('RGB')).getbbox(), (0, 120, 88, 129))
        grey = (46, 128, 139, 255)
        self.assertGreater(sum(1 for p in before.crop((0, 120, 88, 129)).getdata() if p == grey), 100)
        self.assertEqual(sum(1 for p in after.crop((0, 120, 88, 129)).getdata() if p == grey), 0)


if __name__ == '__main__':
    unittest.main()
