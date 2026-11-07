"""Approved L5 artwork goldens, physical silhouettes and moving-gate coverage."""
import hashlib
import unittest

from tests.right_tip_expectations import PreviousArtworkMixin, right_tip_rooms
from unittest.mock import patch

from PIL import Image

from pop2.cavern_retouch import retouch_assets, retouched_sprite
from pop2.caverns import cavern_assets, cavern_command_sprite, cavern_room
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file


# Port room indices; room7's approval is viewed with its stone gate fully open.
# Static items are included here; cached floor previews have their own goldens.
APPROVED = {
    8: (64, 'ddd4ae0ae36b8d4fca900ab9ff1265ae3f8def4202670a3830cab4d3137a9f0f'),
    18: (91, '72de66968e0cb63ddf9e982da4c589e7e4926b331fc8c67c8d1d5cfee0238107'),
    12: (156, 'd93440d2bd470d1ff646e771c5d5dfb0fdd6558d396cfd0f53c218637861cde5'),
    10: (201, 'e78a012ab822411b095682f36ec6da60c38e30b84008bde11b5a75d188cc8136'),
    1: (591, '1f686b8ae78cb4885972c07d6d62baf4fb691568eb0aac6e745b6c25d08c324f'),
    5: (2747, '2ef93b2f6a12554f9f77acc4b07a523187769454c65eab587417dbebeb805eae'),
    6: (1196, 'd879511695be25224c60c436910ba09e3b6f44fa602f44dbd165966b3a13ad7f'),
    13: (764, 'dc3972e7a39d9f9499afc088edcf5b4792346376e500d5a1ff548922e86c96c5'),
    14: (643, '2e5bc07ca34916df66c27435e220421e87f77f0e2e4ccdd7859ab7fe42c0e756'),
    15: (1231, '5cadd904b80f1fc11fd21a8eb4fd3d44ccee4ff62b8f9ba2f831b9270e3c3413'),
    16: (1619, 'fbb686730f48d2a6e589fb13b4202a0fdcdeecddc1c3aaa751499c22ff44e471'),
    21: (691, 'a611edf0f5eb158604b1993e052820b84b6a11168bccc72e183fef60dd5c5806'),
    22: (819, '9c365261fc87ba53116fa4331aef749430e8e0c147fd903d1fea83ad1687afc7'),
    24: (1071, '4ba338d53567d00d272402a59fec0fb9664aee9fd3a164cc0ac65341f23d74a6'),
}


class BundledLevelFiveArtworkTests(unittest.TestCase):
    def test_approved_scope_and_changed_source_guards(self):
        assets = retouch_assets(5)
        self.assertEqual(len(assets), 80)
        self.assertEqual({key[0] for key in assets}, (set(APPROVED) | right_tip_rooms(5)))
        for key, (record, image) in assets.items():
            room, shape, x, bottom, mode = key
            with self.subTest(key=key):
                x1, y1, x2, y2 = record['source_rect']
                self.assertTrue(0 <= x1 < x2 <= record['size'][0])
                self.assertTrue(0 <= y1 < y2 <= record['size'][1])
                self.assertEqual(image.size, (x2-x1, y2-y1))
                source = Image.new('RGBA', record['size'], 'magenta')
                command = ['back', shape, x, bottom, mode, 0, [], 4]
                self.assertIs(retouched_sprite(room, command, source, level_number=5), source)
        with patch('pop2.cavern_retouch.retouch_assets', side_effect=AssertionError('Wrong scope')):
            for room in set(range(32)) - (set(APPROVED) | right_tip_rooms(5)):
                self.assertIs(retouched_sprite(room, [], source, level_number=5), source)


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported game resources required')
class LevelFiveArtworkTests(PreviousArtworkMixin, unittest.TestCase):
    def baseline(self, room, **kwargs):
        # Preserve the already approved door blends when isolating wall changes.
        with patch('pop2.caverns.retouched_sprite', side_effect=lambda room, command, source, **kw: source):
            return cavern_room(room, level_number=5, retouched=True, **kwargs)

    def assert_masks_equal(self, before, after):
        for name in ('foreground', 'retained_mask', 'custom_occlusion'):
            a, b = getattr(before, name), getattr(after, name)
            if a is None:
                self.assertIsNone(b)
            else:
                self.assertEqual((a.getchannel('A') if a.mode == 'RGBA' else a).tobytes(),
                                 (b.getchannel('A') if b.mode == 'RGBA' else b).tobytes())
        for name in ('actor_occlusion', 'climb_redraw', 'floor_redraw', 'actor_cell_occlusion', 'gate_occlusion'):
            old, new = getattr(before, name), getattr(after, name)
            self.assertEqual(set(old), set(new))
            for key in old:
                if name == 'actor_occlusion':
                    self.assertEqual(old[key].tobytes(), new[key].tobytes())
                    continue
                a = old[key] if name in ('climb_redraw', 'floor_redraw') else [old[key]]
                b = new[key] if name in ('climb_redraw', 'floor_redraw') else [new[key]]
                self.assertEqual(len(a), len(b))
                for (im1, pos1), (im2, pos2) in zip(a, b):
                    self.assertEqual(pos1, pos2)
                    self.assertEqual((im1.getchannel('A') if im1.mode == 'RGBA' else im1).tobytes(),
                                     (im2.getchannel('A') if im2.mode == 'RGBA' else im2).tobytes())

    def test_approved_images_match_and_runtime_uses_them(self):
        colours = {tuple(c[:3]) for c in cavern_assets(5)[2].values()}
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 5)
        game = LevelRenderer(level, preload_room=False)
        for room, (count, expected) in APPROVED.items():
            kwargs = {'pressure_key': (46, 0, 0)} if room == 6 else {}
            with self.subTest(room=room+1):
                before = self.baseline(room, **kwargs)
                after = cavern_room(room, level_number=5, retouched=True, **kwargs)
                a, b = before.flattened().convert('RGB'), after.flattened().convert('RGB')
                self.assertEqual(hashlib.sha256(b.tobytes()).hexdigest(), expected)
                changed = [new for old, new in zip(a.getdata(), b.getdata()) if old != new]
                self.assertEqual(len(changed), count)
                self.assertTrue(set(changed) <= colours)
                self.assert_masks_equal(before, after)
                if room in (6, 13):
                    self.assertEqual(before.foreground.tobytes(), after.foreground.tobytes())
                self.assertEqual(game.room(room).flattened().tobytes(),
                                 cavern_room(room, level_number=5, animated=True, retouched=True).flattened().tobytes())

    def test_other_rooms_and_native_opt_out_keep_original_wall_art(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 5)
        auditor = LevelRenderer(level, preload_room=False, retouch_caverns=False)
        for room in range(32):
            with self.subTest(room=room+1):
                self.assertEqual(auditor.room(room).flattened().tobytes(),
                                 cavern_room(room, level_number=5, animated=True).flattened().tobytes())
                if room not in APPROVED:
                    self.assertEqual(self.baseline(room).flattened().tobytes(),
                                     cavern_room(room, level_number=5, retouched=True).flattened().tobytes())

    def test_room_seven_wall_gradient_survives_every_gate_phase(self):
        before = self.baseline(6, pressure_key=(46, 0, 0)).flattened().convert('RGB')
        after = cavern_room(6, level_number=5, retouched=True, pressure_key=(46, 0, 0)).flattened().convert('RGB')
        allowed = {(x, y): after.getpixel((x, y)) for y in range(365) for x in range(510)
                   if before.getpixel((x, y)) != after.getpixel((x, y))}
        for phase in range(47):
            with self.subTest(phase=phase):
                native = self.baseline(6, pressure_key=(phase, 0, 0))
                edited = cavern_room(6, level_number=5, retouched=True, pressure_key=(phase, 0, 0))
                self.assert_masks_equal(native, edited)
                self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
                a, b = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
                for y in range(140, 220):
                    for x in range(178, 208):
                        if a.getpixel((x, y)) != b.getpixel((x, y)):
                            self.assertEqual(b.getpixel((x, y)), allowed.get((x, y)))

    def test_column_bodies_sources_and_library_guards(self):
        program, resources, palette, shapes = cavern_assets(5)
        for key, (record, _) in retouch_assets(5).items():
            room, shape, x, bottom, mode = key
            command = next(c for c in program['rooms'][str(room)] if tuple(c[1:5]) == key[1:])
            source = cavern_command_sprite(command, resources, palette, shapes)
            original = source.tobytes()
            with self.subTest(key=key):
                self.assertEqual(hashlib.sha256(original).hexdigest(), record['source_sha256'])
                result = retouched_sprite(room, command, source, level_number=5)
                self.assertNotEqual(result.tobytes(), original)
                self.assertEqual(source.tobytes(), original)
                self.assertEqual(source.getchannel('A').tobytes(), result.getchannel('A').tobytes())
                if shape in (3531, 3533):
                    for py in range(source.height):
                        edge = max((px for px in range(source.width)
                                    if source.getpixel((px, py))[3]), default=-1)
                        for px in range(source.width):
                            old, new = source.getpixel((px, py)), result.getpixel((px, py))
                            # Room22's reviewed upper fringe includes brown shadow texels.
                            # Keep the original stricter rule for all earlier artwork.
                            if room == 21 and shape == 3531:
                                protected = px < edge-2 or max(old[:3]) > 66 or old[1] > 33
                            else:
                                protected = max(old[:3]) > 24
                            if old[3] and protected:
                                self.assertEqual(old, new)
                other = list(command)
                other[7] = 1
                self.assertIs(retouched_sprite(room, other, source, level_number=5), source)
                changed = source.copy()
                changed.putpixel((0, 0), (1, 2, 3, 255))
                self.assertIs(retouched_sprite(room, command, changed, level_number=5), changed)

    def test_room_seventeen_column_and_exposed_right_margin_are_native(self):
        before = self.baseline(16)
        after = cavern_room(16, level_number=5, retouched=True)
        a, b = before.flattened(), after.flattened()
        self.assertEqual(a.crop((192, 0, 193, 365)).tobytes(), b.crop((192, 0, 193, 365)).tobytes())
        # The whole foreground column is exact; the separate3542 rock edge
        # may recolour as approved, so compare only the actual column mask.
        program, resources, palette, shapes = cavern_assets(5)
        command = next(c for c in program['rooms']['16'] if c[:5] == ['front', 3533, 162, 363, 16])
        source = cavern_command_sprite(command, resources, palette, shapes)
        top = command[3] - source.height
        for y in range(source.height):
            for x in range(source.width):
                if source.getpixel((x, y))[3]:
                    point = x+command[2], y+top
                    self.assertEqual(a.getpixel(point), b.getpixel(point))
