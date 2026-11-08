import hashlib
import unittest

from tests.right_tip_expectations import PreviousArtworkMixin
from unittest.mock import patch

from PIL import Image

from pop2.cavern_retouch import retouch_assets, retouched_sprite
from pop2.caverns import cavern_assets, cavern_command_sprite, cavern_room
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from pop2.terrain import LevelMap


class BundledCavernRetouchTests(unittest.TestCase):
    def test_level_four_bundle_is_separate_and_only_targets_approved_rooms(self):
        assets = retouch_assets(4)
        self.assertEqual(len(assets), 73)
        self.assertEqual({key[0] for key in assets}, {0, 1, 2, 4, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 17, 21, 22, 24, 25, 26, 27})
        key, (record, image) = next(iter(assets.items()))
        self.assertEqual(image.size, (record['source_rect'][2] - record['source_rect'][0],
                                      record['source_rect'][3] - record['source_rect'][1]))
        room, shape, x, bottom, mode = key
        source = Image.new('RGBA', record['size'], 'magenta')
        command = ['back', shape, x, bottom, mode, 0, [], 4]
        self.assertIs(retouched_sprite(room, command, source, level_number=4), source)
        self.assertIs(retouched_sprite(room, command, source, level_number=3), source)
        with patch('pop2.cavern_retouch.retouch_assets', side_effect=AssertionError('Wrong level')):
            for level in (5, 6, 7, 8, 9):
                self.assertIs(retouched_sprite(room, command, source, level_number=level), source)

    def test_new_wall_patches_reject_wrong_level_room_or_source(self):
        for key, (record, image) in retouch_assets(4).items():
            if key[0] not in (21, 22):
                continue
            room, shape, x, bottom, mode = key
            self.assertEqual(image.size, (record['source_rect'][2] - record['source_rect'][0],
                                          record['source_rect'][3] - record['source_rect'][1]))
            source = Image.new('RGBA', record['size'], 'magenta')
            command = ['back', shape, x, bottom, mode, 2, [], 4]
            self.assertIs(retouched_sprite(room, command, source, level_number=4), source)
            # This room number may also have its own level-five artwork;
            # source and placement guards must still reject the wrong patch.
            self.assertIs(retouched_sprite(room, command, source, level_number=5), source)
            # Level three can approve this same room index independently.
            self.assertIs(retouched_sprite(room, command, source, level_number=3), source)
            with patch('pop2.cavern_retouch.retouch_assets', side_effect=AssertionError('Wrong scope')):
                for level in (6, 7, 8, 9):
                    self.assertIs(retouched_sprite(room, command, source, level_number=level), source)
                # Room21 now has reviewed floor artwork. Room4 remains outside
                # the approved level-four scope and must not load the atlas.
                self.assertIs(retouched_sprite(3, command, source, level_number=4), source)

    def test_bundled_variants_have_valid_scope_and_crop_sizes(self):
        assets = retouch_assets()
        self.assertEqual(len(assets), 128)
        self.assertEqual({key[0] for key in assets}, {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 23, 24, 25, 26, 27, 29, 30, 31})
        for key, (record, image) in assets.items():
            with self.subTest(key=key):
                x1, y1, x2, y2 = record['source_rect']
                self.assertEqual(image.size, (x2 - x1, y2 - y1))
                self.assertTrue(0 <= x1 < x2 <= record['size'][0])
                self.assertTrue(0 <= y1 < y2 <= record['size'][1])
                self.assertEqual(len(record['source_sha256']), 64)
                self.assertTrue(set(image.getchannel('A').getdata()) <= {0, 255})

    def test_unaffected_rooms_do_not_even_load_retouch_assets(self):
        source = Image.new('RGBA', (5, 5), 'red')
        with patch('pop2.cavern_retouch.retouch_assets', side_effect=AssertionError('Unexpected load')):
            for room in set(range(32)) - {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 23, 24, 25, 26, 27, 29, 30, 31}:
                self.assertIs(retouched_sprite(room, [], source), source)

    def test_unmatched_sources_and_other_shape_libraries_are_untouched(self):
        key = next(iter(retouch_assets()))
        room, shape, x, bottom, mode = key
        record = retouch_assets()[key][0]
        source = Image.new('RGBA', record['size'], 'magenta')
        command = ['back', shape, x, bottom, mode, 0, [], 4]
        self.assertIs(retouched_sprite(room, command, source), source)
        command[7] = 1
        self.assertIs(retouched_sprite(room, command, source), source)
        with patch('pop2.cavern_retouch.Image.open', side_effect=AssertionError('Uncached asset read')):
            self.assertIs(retouch_assets(), retouch_assets())


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class CavernRetouchTests(PreviousArtworkMixin, unittest.TestCase):
    def test_level_eight_room_five_removes_only_the_approved_corner_fragment(self):
        native = cavern_room(4, level_number=8)
        edited = cavern_room(4, level_number=8, retouched=True)
        before, after = native.flattened(), edited.flattened()
        self.assertEqual(hashlib.sha256(after.convert('RGB').tobytes()).hexdigest(),
                         'c05c2e3cd36ad9d88399c0ac1cba8c2edd39cd6988568dd72a10595ef414a6f9')
        changed = [(x, y) for y in range(365) for x in range(510)
                   if before.getpixel((x, y)) != after.getpixel((x, y))]
        self.assertEqual(len(changed), 24)
        self.assertTrue(all(0 <= x < 8 and 0 <= y < 5 for x, y in changed))
        self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
        self.assert_masks_equal(native, edited)
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 8)
        renderer = LevelRenderer(level, preload_room=False)
        reference = LevelRenderer(level, preload_room=False, retouch_caverns=False)
        self.assertEqual(renderer.room(4).flattened().tobytes(),
                         cavern_room(4, level_number=8, animated=True, retouched=True).flattened().tobytes())
        self.assertEqual(reference.room(4).flattened().tobytes(),
                         cavern_room(4, level_number=8, animated=True).flattened().tobytes())

    def assert_masks_equal(self, before, after):
        self.assertEqual(before.foreground.getchannel('A').tobytes(), after.foreground.getchannel('A').tobytes())
        self.assertEqual(before.retained_mask.tobytes(), after.retained_mask.tobytes())
        for key in before.actor_occlusion:
            self.assertEqual(before.actor_occlusion[key].tobytes(), after.actor_occlusion[key].tobytes())
        for name in ('climb_redraw', 'floor_redraw', 'actor_cell_occlusion', 'gate_occlusion'):
            a, b = getattr(before, name), getattr(after, name)
            self.assertEqual(set(a), set(b))
            for key in a:
                old = a[key] if name in ('climb_redraw', 'floor_redraw') else [a[key]]
                new = b[key] if name in ('climb_redraw', 'floor_redraw') else [b[key]]
                self.assertEqual(len(old), len(new))
                for (old_image, old_position), (new_image, new_position) in zip(old, new):
                    self.assertEqual(old_position, new_position)
                    old_mask = old_image.getchannel('A') if old_image.mode == 'RGBA' else old_image
                    new_mask = new_image.getchannel('A') if new_image.mode == 'RGBA' else new_image
                    self.assertEqual(old_mask.tobytes(), new_mask.tobytes())

    def test_local_variants_reproduce_approved_images_exactly(self):
        hashes = {0: 'ea1a66ebf3682d25138344923e0be9a4a5076eab04ac7bcd3ef3edcd6f99e27c',
                  1: 'd3821666a9cd7439da9d4cf9331c6a3a1892d90db22e9b2a69830bffe3e6f2d5',
                  27: 'a0220428dd30bf81285c1f4f7c28ecbe82760a0030b80a646f78e544e24dba35',
                  29: '1f7cb6240cff9746a42fe39ca156c911680bddcfc784e48f3fc7d44caca1372e'}
        for room, expected in hashes.items():
            with self.subTest(room=room):
                native = cavern_room(room)
                # Keep the earlier wall-art goldens independent of the door
                # blend, whose approved combined frames have their own tests.
                with patch('pop2.caverns.retouched_door_sprite', side_effect=lambda level, room, command, source: source):
                    edited = cavern_room(room, retouched=True)
                pixels = edited.flattened().convert('RGB').tobytes()
                self.assertEqual(hashlib.sha256(pixels).hexdigest(), expected)
                self.assertNotEqual(native.flattened().tobytes(), edited.flattened().tobytes())
                self.assert_masks_equal(native, edited)

    def test_level_four_room_twelve_matches_approved_continuation_and_preserves_masks(self):
        native = cavern_room(11, level_number=4)
        edited = cavern_room(11, level_number=4, retouched=True)
        before, after = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
        self.assertEqual(hashlib.sha256(after.tobytes()).hexdigest(),
                         '531028e35010c0fda94c7a6b20b9f89f2169f37f0a13bca7dae7d620faf92059')
        changed = [(x, y) for y in range(365) for x in range(510)
                   if before.getpixel((x, y)) != after.getpixel((x, y))]
        self.assertEqual(len(changed), 791)
        self.assert_masks_equal(native, edited)
        self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
        self.assertTrue(all((188 <= x <= 199 and 144 <= y < 235)
                            or (343 <= x <= 349 and 243 <= y <= 331) for x, y in changed))
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        game = LevelRenderer(level, preload_room=False)
        reference = LevelRenderer(level, preload_room=False, retouch_caverns=False)
        self.assertEqual(game.room(11).flattened().tobytes(),
                         cavern_room(11, level_number=4, animated=True, retouched=True).flattened().tobytes())
        self.assertEqual(reference.room(11).flattened().tobytes(),
                         cavern_room(11, level_number=4, animated=True).flattened().tobytes())

    def test_level_four_other_rooms_keep_their_original_wall_art(self):
        with patch('pop2.caverns.retouched_door_sprite', side_effect=lambda level, room, command, source: source):
            for room in set(range(32)) - {0, 1, 2, 4, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 17, 21, 22, 24, 25, 26, 27}:
                with self.subTest(room=room):
                    original = cavern_room(room, level_number=4)
                    edited = cavern_room(room, level_number=4, retouched=True)
                    self.assertEqual(original.flattened().tobytes(), edited.flattened().tobytes())

    def test_level_four_final_batch_matches_approved_pixels_and_preserves_masks(self):
        # These full-room goldens include static items; cached floor previews
        # have separate exact-frame checks in test_floor_join_artwork.
        approved = {
            4: (382, '421ee7b40f740af3598ef7d1c3b8acf5ba6a5b4fd4394a2a684ed017f53d5290'),
            13: (654, '2dcad3e10b1616a79a53a78af263a06ec3c188c0db598e7b989f211fc7c5b0ee'),
            25: (481, '9ef82c6d26f7540b12e655ed87dcebaf0ab4f3ba810f609ac75d0735ab096197'),
            27: (336, 'd60832d8900669a315a5868ea9d069755f5b330f4c12b5618e6567578c8e1d63'),
        }
        colours = {tuple(c[:3]) for c in cavern_assets(4)[2].values()}
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        game = LevelRenderer(level, preload_room=False)
        for room, (count, expected) in approved.items():
            with self.subTest(room=room + 1):
                native = cavern_room(room, level_number=4)
                edited = cavern_room(room, level_number=4, retouched=True)
                a, b = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
                self.assertEqual(hashlib.sha256(b.tobytes()).hexdigest(), expected)
                changed = [new for old, new in zip(a.getdata(), b.getdata()) if old != new]
                self.assertEqual(len(changed), count)
                self.assertTrue(set(changed) <= colours)
                self.assert_masks_equal(native, edited)
                if room in (4, 27):
                    self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
                self.assertEqual(game.room(room).flattened().tobytes(),
                                 cavern_room(room, level_number=4, animated=True, retouched=True).flattened().tobytes())

    def test_batch_column_gradients_preserve_lit_bodies_and_reject_changed_sources(self):
        program, resources, palette, shapes = cavern_assets(4)
        for key, (record, _) in retouch_assets(4).items():
            room, shape, x, bottom, mode = key
            if room not in (4, 13, 25, 27):
                continue
            with self.subTest(key=key):
                command = next(c for c in program['rooms'][str(room)] if tuple(c[1:5]) == key[1:])
                source = cavern_command_sprite(command, resources, palette, shapes)
                original = source.tobytes()
                self.assertEqual(hashlib.sha256(original).hexdigest(), record['source_sha256'])
                result = retouched_sprite(room, command, source, level_number=4)
                self.assertNotEqual(result.tobytes(), original)
                self.assertEqual(source.tobytes(), original)
                self.assertEqual(result.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                if (room, shape) in ((13, 3531), (25, 3533)):
                    for old, new in zip(source.getdata(), result.getdata()):
                        if old[3] and max(old[:3]) > 24:
                            self.assertEqual(old, new)
                changed = source.copy()
                changed.putpixel((0, 0), (1, 2, 3, 255))
                self.assertIs(retouched_sprite(room, command, changed, level_number=4), changed)
                other_library = list(command)
                other_library[7] = 1
                self.assertIs(retouched_sprite(room, other_library, source, level_number=4), source)
                for level_number in (5, 6, 7, 8, 9):
                    self.assertIs(retouched_sprite(room, command, source, level_number=level_number), source)

    def test_level_four_room_twenty_two_matches_approved_gradient_and_keeps_its_column(self):
        with patch('pop2.caverns.retouched_sprite', side_effect=lambda room, command, source, **kw: source):
            before = cavern_room(21, level_number=4, retouched=True)
        edited = cavern_room(21, level_number=4, retouched=True)
        a, b = before.flattened().convert('RGB'), edited.flattened().convert('RGB')
        self.assertEqual(hashlib.sha256(b.tobytes()).hexdigest(),
                         '74912e7249bf2e288597df09ca426527045adc8cc55a9e75c0883408060cde16')
        changed = [(x, y) for y in range(365) for x in range(510)
                   if a.getpixel((x, y)) != b.getpixel((x, y))]
        self.assertEqual(len(changed), 213)
        self.assertTrue(all(37 <= x < 43 and 259 <= y < 318 for x, y in changed))
        self.assertEqual(before.foreground.tobytes(), edited.foreground.tobytes())
        self.assert_masks_equal(before, edited)
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        self.assertEqual(LevelRenderer(level, preload_room=False).room(21).flattened().tobytes(),
                         cavern_room(21, level_number=4, animated=True, retouched=True).flattened().tobytes())

    def test_room_twenty_two_gradient_survives_exit_animation(self):
        records = cavern_assets(4)[0]['pressure_plates']['rooms']['21']
        index = next(i for i, record in enumerate(records) if record['kind'] == 17)
        for phase in (0, 27, 53, 79):
            with self.subTest(exit_phase=phase):
                phases = [0] * len(records)
                phases[index] = phase
                kwargs = dict(level_number=4, retouched=True, pressure_key=tuple(phases))
                with patch('pop2.caverns.retouched_sprite', side_effect=lambda room, command, source, **kw: source):
                    before = cavern_room(21, **kwargs)
                after = cavern_room(21, **kwargs)
                self.assert_masks_equal(before, after)
                a, b = before.flattened().convert('RGB'), after.flattened().convert('RGB')
                changed = [(x, y) for y in range(365) for x in range(510)
                           if a.getpixel((x, y)) != b.getpixel((x, y))]
                self.assertEqual(len(changed), 213)
                self.assertTrue(all(37 <= x < 43 and 259 <= y < 318 for x, y in changed))

    def test_level_four_room_twenty_three_matches_approved_v9_with_original_masks(self):
        native = cavern_room(22, level_number=4)
        edited = cavern_room(22, level_number=4, retouched=True)
        before, after = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
        self.assertEqual(hashlib.sha256(after.tobytes()).hexdigest(),
                         'f4a72ba65bba70226a882dcb4cb9394e1e85b8dc688340ccd5aca5a2dfdbe68a')
        changed = [(x, y) for y in range(365) for x in range(510)
                   if before.getpixel((x, y)) != after.getpixel((x, y))]
        self.assertEqual(len(changed), 2035)
        self.assertTrue(all((102 <= x < 126 and 256 <= y < 362)
                            or (99 <= x < 105 and 252 <= y < 342) for x, y in changed))
        self.assert_masks_equal(native, edited)
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        game = LevelRenderer(level, preload_room=False)
        reference = LevelRenderer(level, preload_room=False, retouch_caverns=False)
        self.assertEqual(game.room(22).flattened().tobytes(),
                         cavern_room(22, level_number=4, animated=True, retouched=True).flattened().tobytes())
        self.assertEqual(reference.room(22).flattened().tobytes(),
                         cavern_room(22, level_number=4, animated=True).flattened().tobytes())

    def test_room_twenty_three_keeps_v1_stalactites_outside_the_marked_join(self):
        program, resources, palette, shapes = cavern_assets(4)
        command = next(c for c in program['rooms']['22'] if c[:5] == ['back', 3550, 102, 365, 16])
        source = cavern_command_sprite(command, resources, palette, shapes)
        alias = list(command)
        alias[3] = 125  # V1 reused this exact approved level-three room-one crop.
        v1 = retouched_sprite(0, alias, source)
        edited = retouched_sprite(22, command, source, level_number=4)
        self.assertEqual(edited.crop((4, 0, *source.size)).tobytes(),
                         v1.crop((4, 0, *source.size)).tobytes())
        self.assertEqual(edited.getchannel('A').tobytes(), source.getchannel('A').tobytes())

    def test_ceiling_stalactite_keeps_its_original_texels(self):
        program, resources, palette, shapes = cavern_assets()
        command = next(c for c in program['rooms']['0'] if c[:5] == ['front', 3596, 51, 51, 16])
        source = cavern_command_sprite(command, resources, palette, shapes)
        self.assertIs(retouched_sprite(0, command, source), source)

    def test_closed_entry_door_is_native_and_wall_retouch_does_not_change(self):
        opened = cavern_room(0, entry_frame=0, retouched=True).flattened()
        closed = cavern_room(0, entry_frame=2, retouched=True).flattened()
        native = cavern_room(0, entry_frame=2).flattened()
        self.assertEqual(opened.crop((35, 0, 151, 245)).tobytes(), closed.crop((35, 0, 151, 245)).tobytes())
        self.assertEqual(closed.crop((185, 135, 281, 220)).tobytes(), native.crop((185, 135, 281, 220)).tobytes())

    def test_unapproved_rooms_remain_pixel_identical(self):
        for room in set(range(32)) - {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 23, 24, 25, 26, 27, 29, 30, 31}:
            with self.subTest(room=room):
                native, edited = cavern_room(room), cavern_room(room, retouched=True)
                self.assertEqual(native.background.tobytes(), edited.background.tobytes())
                self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
                self.assert_masks_equal(native, edited)

    def test_room_thirty_only_changes_marked_margins_not_foreground_or_column_outlines(self):
        from PIL import ImageChops, ImageDraw, ImageFilter
        from pop2.caverns import clipped_sprite

        program, resources, palette, shapes = cavern_assets()
        with patch('pop2.caverns.retouched_door_sprite', side_effect=lambda level, room, command, source: source):
            native, edited = cavern_room(29), cavern_room(29, retouched=True)
        self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
        before, after = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
        protected = Image.new('L', before.size)
        for command in program['rooms']['29']:
            if 3531 <= command[1] <= 3538 or command[0] == 'front':
                clipped = clipped_sprite(cavern_command_sprite(command, resources, palette, shapes), command)
                if clipped is not None:
                    sprite, position = clipped
                    part = Image.new('L', before.size)
                    part.paste(sprite.getchannel('A'), position)
                    protected = ImageChops.lighter(protected, part)
        protected = protected.filter(ImageFilter.MaxFilter(3))
        allowed = Image.new('L', before.size)
        for trace in (((47, 295), (56, 295)),
                      ((73, 268), (91, 268), (91, 296), (89, 296)),
                      ((142, 287), (142, 307)), ((448, 27), (448, 95))):
            ImageDraw.Draw(allowed).line(trace, fill=255, width=5)
        changed = [(x, y) for y in range(before.height) for x in range(before.width)
                   if before.getpixel((x, y)) != after.getpixel((x, y))]
        colours = {tuple(c[:3]) for c in palette.values()}
        self.assertEqual(len(changed), 385)
        self.assertEqual(sum(y < 125 for x, y in changed), 206)
        for point in changed:
            self.assertTrue(allowed.getpixel(point), point)
            self.assertFalse(protected.getpixel(point), point)
            self.assertIn(after.getpixel(point), colours)

    def test_room_two_preserves_column_texels_and_only_changes_approved_shadow_edges(self):
        from PIL import ImageChops, ImageDraw, ImageFilter
        from pop2.caverns import clipped_sprite

        program, resources, palette, shapes = cavern_assets()
        native = cavern_room(1).flattened().convert('RGB')
        edited = cavern_room(1, retouched=True).flattened().convert('RGB')
        columns = Image.new('L', native.size)
        for command in program['rooms']['1']:
            if 3532 <= command[1] <= 3538:
                clipped = clipped_sprite(cavern_command_sprite(command, resources, palette, shapes), command)
                if clipped is not None:
                    sprite, position = clipped
                    part = Image.new('L', native.size)
                    part.paste(sprite.getchannel('A'), position)
                    columns = ImageChops.lighter(columns, part)
        guard = columns.filter(ImageFilter.MaxFilter(3))
        allowed = Image.new('L', native.size)
        draw = ImageDraw.Draw(allowed)
        draw.rectangle((139, 211, 153, 319), fill=255)
        draw.line(((74, 268), (90, 268), (90, 295), (69, 295)), fill=255, width=5)
        draw.line(((178, 268), (192, 268), (193, 273), (193, 294), (189, 295)), fill=255, width=5)
        colours = {tuple(c[:3]) for c in palette.values()}
        changed = []
        for y in range(native.height):
            for x in range(native.width):
                point = x, y
                if native.getpixel(point) != edited.getpixel(point):
                    changed.append(point)
                    self.assertTrue(allowed.getpixel(point), point)
                    self.assertFalse(guard.getpixel(point), point)
                    self.assertIn(edited.getpixel(point), colours)
        self.assertEqual(len(changed), 485)
        for left, top, right, bottom in ((69, 266, 93, 298), (139, 269, 145, 298), (176, 266, 196, 298)):
            self.assertTrue(any(left <= x < right and top <= y < bottom for x, y in changed))

    def test_room_two_foreground_redraws_do_not_cover_or_change_shadow_pixels(self):
        native, edited = cavern_room(1), cavern_room(1, retouched=True)
        before, after = native.flattened(), edited.flattened()
        points = [(x, y) for y in range(before.height) for x in range(before.width)
                  if before.getpixel((x, y)) != after.getpixel((x, y))]
        checked = 0
        for name in ('climb_redraw', 'floor_redraw'):
            old, new = getattr(native, name), getattr(edited, name)
            for key in old:
                blank = Image.new('RGBA', before.size)
                old_frame = native.draw_floor_records(blank.copy(), old[key], None)
                new_frame = edited.draw_floor_records(blank.copy(), new[key], None)
                self.assertEqual(old_frame.tobytes(), new_frame.tobytes())
                # This room's redraw lists paint only foreground columns; none
                # of the background shadow texels may be restored over them.
                for point in points:
                    self.assertEqual(new_frame.getpixel(point)[3], 0, (name, key, point))
                checked += 1
        self.assertGreater(checked, 0)

    def test_entry_and_loose_floor_variants_preserve_all_masks(self):
        from pop2.caverns import loose_keys

        program = cavern_assets()[0]
        for key in ('', *loose_keys(program, 0)):
            for phase in range(len(program['entry_exit']['frames'])):
                with self.subTest(variant=key, phase=phase):
                    native = cavern_room(0, entry_frame=phase, loose_key=key)
                    edited = cavern_room(0, entry_frame=phase, loose_key=key, retouched=True)
                    self.assert_masks_equal(native, edited)

    def test_local_sprite_does_not_mutate_source_or_retarget_changed_exports(self):
        program, resources, palette, shapes = cavern_assets()
        record = next(iter(retouch_assets().values()))[0]
        room = record['room']
        command = next(c for c in program['rooms'][str(room)]
                       if [c[1], c[2], c[3], c[4]] ==
                       [record['shape'], record['x'], record['bottom'], record['mode']])
        source = cavern_command_sprite(command, resources, palette, shapes)
        original = source.tobytes()
        result = retouched_sprite(room, command, source)
        self.assertNotEqual(result.tobytes(), original)
        self.assertEqual(source.tobytes(), original)
        self.assertEqual(result.getchannel('A').tobytes(), source.getchannel('A').tobytes())
        self.assertIs(retouched_sprite(2, command, source), source)
        shifted = list(command)
        shifted[2] += 1
        self.assertIs(retouched_sprite(room, shifted, source), source)
        changed = source.copy()
        changed.putpixel((0, 0), (1, 2, 3, 255))
        self.assertIs(retouched_sprite(room, command, changed), changed)
        with patch('pop2.cavern_retouch.Image.open', side_effect=AssertionError('Uncached asset read')):
            self.assertEqual(retouched_sprite(room, command, source).tobytes(), result.tobytes())

    def test_game_renderer_enables_local_variants_and_native_auditor_can_opt_out(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
        game = LevelRenderer(level, preload_room=False)
        reference = LevelRenderer(level, preload_room=False, retouch_caverns=False)
        for room in range(32):
            expected = cavern_room(room, animated=True, retouched=room in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 23, 24, 25, 26, 27, 29, 30, 31))
            self.assertEqual(game.room(room).flattened().tobytes(), expected.flattened().tobytes())
            self.assertEqual(reference.room(room).flattened().tobytes(), cavern_room(room, animated=True).flattened().tobytes())

    def test_retained_pixels_do_not_propagate_retouch_into_adjacent_rooms(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
        terrain = LevelMap(level.data)
        for source in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 23, 24, 25, 26, 27, 29, 30, 31):
            for direction in ('left', 'right', 'up', 'down'):
                destination = terrain.neighbor(source, direction)
                if destination is None or destination in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 23, 24, 25, 26, 27, 29, 30, 31):
                    continue
                with self.subTest(source=source, destination=destination):
                    game = LevelRenderer(level, preload_room=False)
                    native = LevelRenderer(level, preload_room=False, retouch_caverns=False)
                    game.enter_room(source)
                    native.enter_room(source)
                    self.assertEqual(game.enter_room(destination).flattened().tobytes(),
                                     native.enter_room(destination).flattened().tobytes())


# Native room numbers are converted to zero-based indices in the keys.
# Values are X, bottom and RGB hash of the approved previews, including earlier retouches.
COLUMN_SHADOWS = {
    (3, 0): (111, 243, '470358256d02d9371eabfc773426c3b6949e14c62852acbf6b9eac022ad44f02'),
    (3, 4): (60, 243, '4c21295ad0cc54ed2aecc91cf40433df13f4576ee3fab320c53544783cc798a5'),
    (3, 6): (366, 363, '07151ff23ba5c20cf5fbf29a65b08c80c80041705ecf7657fa18e4fcb6294d5e'),
    (3, 7): (366, 243, '9043537b7de6fc860b4b72ec272dd8c44486179d4e224914df2fd90b676c8073'),
    (3, 12): (213, 243, 'd7dceac57950745d0880bdc06aea68f923d59006f722dda0a823b0d14e0f9298'),
    (5, 1): (60, 243, '1f686b8ae78cb4885972c07d6d62baf4fb691568eb0aac6e745b6c25d08c324f'),
    (5, 22): (60, 243, 'cad5cd9c75b8de390f507820356915a8bf915adfe8eb29731e39a54f4b533f4e'),
}


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ColumnShadowArtworkTests(PreviousArtworkMixin, unittest.TestCase):
    def test_runtime_reproduces_approved_frames_without_changing_physics_masks(self):
        prince = load_resource_file('Prince.rsrc')
        for (level, room), (_x, _bottom, expected) in COLUMN_SHADOWS.items():
            with self.subTest(level=level, room=room+1):
                definition = LevelDefinition.read(prince, level)
                renderer = LevelRenderer(definition, preload_room=False)
                edited = renderer.room(room)
                self.assertEqual(hashlib.sha256(edited.flattened().convert('RGB').tobytes()).hexdigest(),
                                 expected)
                native = cavern_room(room, level_number=level, animated=True)
                CavernRetouchTests().assert_masks_equal(native, edited)
                auditor = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
                self.assertEqual(auditor.room(room).flattened().tobytes(), native.flattened().tobytes())

    def test_column_body_alpha_and_placement_guards_are_preserved(self):
        for (level, room), (x, bottom, _expected) in COLUMN_SHADOWS.items():
            with self.subTest(level=level, room=room+1):
                program, resources, palette, shapes = cavern_assets(level)
                command = next(c for c in program['rooms'][str(room)]
                               if c[:5] == ['front', 3533, x, bottom, 16])
                source = cavern_command_sprite(command, resources, palette, shapes)
                original = source.tobytes()
                edited = retouched_sprite(room, command, source, level_number=level)
                changes = [(px, py) for py in range(source.height) for px in range(source.width)
                           if source.getpixel((px, py)) != edited.getpixel((px, py))]
                self.assertEqual(len(changes), 67)
                self.assertTrue(all(28 <= px < 37 and 57 <= py < 109 for px, py in changes))
                self.assertEqual(edited.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                self.assertEqual(source.tobytes(), original)
                shifted = command.copy()
                shifted[2] += 1
                self.assertIs(retouched_sprite(room, shifted, source, level_number=level), source)
                changed = source.copy()
                changed.putpixel((0, 0), (1, 2, 3, 255))
                self.assertIs(retouched_sprite(room, command, changed, level_number=level), changed)
