import hashlib
import unittest
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
    def test_only_two_rooms_have_bundled_variants_with_valid_crop_sizes(self):
        assets = retouch_assets()
        self.assertEqual(len(assets), 20)
        self.assertEqual({key[0] for key in assets}, {0, 27})
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
            for room in set(range(32)) - {0, 27}:
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
class CavernRetouchTests(unittest.TestCase):
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
        hashes = {0: '18f6592d8c185dbb7c224e4550172cdbde0dfaff88c28a8695e30442f5bede7b',
                  27: 'a0220428dd30bf81285c1f4f7c28ecbe82760a0030b80a646f78e544e24dba35'}
        for room, expected in hashes.items():
            with self.subTest(room=room):
                native = cavern_room(room)
                edited = cavern_room(room, retouched=True)
                pixels = edited.flattened().convert('RGB').tobytes()
                self.assertEqual(hashlib.sha256(pixels).hexdigest(), expected)
                self.assertNotEqual(native.flattened().tobytes(), edited.flattened().tobytes())
                self.assert_masks_equal(native, edited)

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

    def test_other_thirty_rooms_remain_pixel_identical(self):
        for room in set(range(32)) - {0, 27}:
            with self.subTest(room=room):
                native, edited = cavern_room(room), cavern_room(room, retouched=True)
                self.assertEqual(native.background.tobytes(), edited.background.tobytes())
                self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
                self.assert_masks_equal(native, edited)

    def test_entry_and_loose_floor_variants_preserve_all_masks(self):
        program = cavern_assets()[0]
        variants = program['loose_floors']['rooms']['0']['variants']
        for key in ('', *variants):
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
        self.assertIs(retouched_sprite(1, command, source), source)
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
            expected = cavern_room(room, animated=True, retouched=room in (0, 27))
            self.assertEqual(game.room(room).flattened().tobytes(), expected.flattened().tobytes())
            self.assertEqual(reference.room(room).flattened().tobytes(), cavern_room(room, animated=True).flattened().tobytes())

    def test_retained_pixels_do_not_propagate_retouch_into_adjacent_rooms(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
        terrain = LevelMap(level.data)
        for source in (0, 27):
            for direction in ('left', 'right', 'up', 'down'):
                destination = terrain.neighbor(source, direction)
                if destination is None or destination in (0, 27):
                    continue
                with self.subTest(source=source, destination=destination):
                    game = LevelRenderer(level, preload_room=False)
                    native = LevelRenderer(level, preload_room=False, retouch_caverns=False)
                    game.enter_room(source)
                    native.enter_room(source)
                    self.assertEqual(game.enter_room(destination).flattened().tobytes(),
                                     native.enter_room(destination).flattened().tobytes())
