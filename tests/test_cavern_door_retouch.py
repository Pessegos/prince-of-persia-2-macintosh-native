import hashlib
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.cavern_retouch import door_retouch_assets, retouched_door_sprite
from pop2.caverns import cavern_assets, cavern_command_sprite, cavern_room
from pop2.paths import ASSET_DIR


class BundledCavernDoorRetouchTests(unittest.TestCase):
    def test_six_context_specific_crops_share_the_existing_atlas(self):
        assets = door_retouch_assets()
        self.assertEqual({key[:2] for key in assets}, {(3, 0), (3, 12), (3, 29), (4, 0), (4, 21), (5, 0)})
        self.assertEqual(len(assets), 6)
        for key, (record, image) in assets.items():
            with self.subTest(key=key):
                self.assertEqual(key[2], 3564)
                self.assertEqual(key[-1], 16)
                self.assertEqual(record['size'], [109, 120])
                self.assertEqual(record['source_rect'], [99, 90, 109, 102])
                self.assertEqual(image.size, (10, 12))
                self.assertEqual(set(image.getchannel('A').tobytes()), {255})
        early = [image.tobytes() for key, (_, image) in assets.items() if key[0] != 5]
        self.assertEqual(len(set(early)), 1)
        five = next(image for key, (_, image) in assets.items() if key[0] == 5)
        self.assertNotEqual(five.tobytes(), early[0])

    def test_unrelated_libraries_shapes_modes_and_levels_do_not_load_door_assets(self):
        source = Image.new('RGBA', (2, 2), 'red')
        command = ['back', 3564, 186, 219, 16, 1, [], 4]
        with patch('pop2.cavern_retouch.door_retouch_assets', side_effect=AssertionError('Unexpected load')):
            for level in (1, 2, 6, 7, 10):
                self.assertIs(retouched_door_sprite(level, 0, command, source), source)
            for index, value in ((1, 3550), (4, 0), (7, 1)):
                unrelated = command.copy()
                unrelated[index] = value
                self.assertIs(retouched_door_sprite(3, 0, unrelated, source), source)
            self.assertIs(retouched_door_sprite(3, 0, [], source), source)


@unittest.skipUnless(all((ASSET_DIR / name).is_file() for name in
                         ('caverns_entry.json', 'caverns_level4.json', 'caverns_level5.json')),
                     'Imported cavern levels required')
class CavernDoorRetouchTests(unittest.TestCase):
    def wall_only(self, level, room, **kwargs):
        with patch('pop2.caverns.retouched_door_sprite', side_effect=lambda level, room, command, source: source):
            return cavern_room(room, retouched=True, level_number=level, **kwargs)

    def test_every_exported_cavern_door_has_a_baked_variant(self):
        expected = set()
        for level in (3, 4, 5):
            program = cavern_assets(level)[0]
            for room, commands in program['rooms'].items():
                for command in commands:
                    if command[1] == 3564 and command[7] == 4:
                        expected.add((level, int(room), *command[1:5]))
        self.assertEqual(set(door_retouch_assets()), expected)

    def test_baked_source_corrections_are_exact_and_do_not_mutate_native_sprites(self):
        for key, (record, _crop) in door_retouch_assets().items():
            level, room, shape, x, bottom, mode = key
            program, resources, palette, shapes = cavern_assets(level)
            command = next(c for c in program['rooms'][str(room)] if tuple(c[1:5]) == (shape, x, bottom, mode))
            source = cavern_command_sprite(command, resources, palette, shapes)
            original = source.tobytes()
            result = retouched_door_sprite(level, room, command, source)
            expected = ('ffdaec61bdbb84c1a1178a32e89105363e806eca8617da8aa77a087eb455cb81' if level == 5 else
                        'cbce7ea807f426cd36b57f1da7d1c9965dae2f58aa07596518efeb2acd131431')
            with self.subTest(key=key):
                self.assertEqual(hashlib.sha256(result.tobytes()).hexdigest(), expected)
                self.assertEqual(source.tobytes(), original)
                self.assertEqual(source.getchannel('A').tobytes(), result.getchannel('A').tobytes())
                self.assertEqual(hashlib.sha256(original).hexdigest(), record['source_sha256'])
                changed = source.copy()
                changed.putpixel((0, 0), (1, 2, 3, 255))
                self.assertIs(retouched_door_sprite(level, room, command, changed), changed)
                shifted = command.copy()
                shifted[2] += 1
                self.assertIs(retouched_door_sprite(level, room, shifted, source), source)
                self.assertIs(retouched_door_sprite(level, 99, command, source), source)
                resized = source.resize((1, 1))
                self.assertIs(retouched_door_sprite(level, room, command, resized), resized)
                with patch('pop2.cavern_retouch.Image.open', side_effect=AssertionError('Repeated file read')):
                    self.assertEqual(retouched_door_sprite(level, room, command, source).tobytes(), result.tobytes())

    def test_entry_and_exit_reproduce_the_user_approved_previews(self):
        for room, kwargs, expected in (
                (0, {'entry_frame': 2}, 'dafedfbf341b66b0d7e6ad0d720b85a7ec0ce1c527977a65dfef902ae938cef9'),
                (29, {}, '595b9def05ce7fc25446c4c98e05cd881028f6dc69fae9467b167ac8510791bf')):
            pixels = cavern_room(room, retouched=True, **kwargs).flattened().convert('RGB').tobytes()
            self.assertEqual(hashlib.sha256(pixels).hexdigest(), expected)

    def assert_local_fade(self, level, room, **kwargs):
        old = self.wall_only(level, room, **kwargs)
        new = cavern_room(room, retouched=True, level_number=level, **kwargs)
        self.assertEqual(old.foreground.tobytes(), new.foreground.tobytes())
        self.assertEqual(old.retained_mask.tobytes(), new.retained_mask.tobytes())
        for row in old.actor_occlusion:
            self.assertEqual(old.actor_occlusion[row].tobytes(), new.actor_occlusion[row].tobytes())
        a, b = old.flattened().convert('RGB'), new.flattened().convert('RGB')
        difference = ImageChops.difference(a, b)
        bbox = difference.getbbox()
        self.assertIsNotNone(bbox)
        record = next(record for key, (record, _) in door_retouch_assets().items() if key[:2] == (level, room))
        x, top = record['x'], record['bottom'] - 120
        self.assertTrue(x + 99 <= bbox[0] < bbox[2] <= x + 109)
        self.assertTrue(top + 90 <= bbox[1] < bbox[3] <= top + 102)
        count = sum(a.getpixel((x, y)) != b.getpixel((x, y))
                    for y in range(bbox[1], bbox[3]) for x in range(bbox[0], bbox[2]))
        self.assertEqual(count, 43 if level == 5 else 40)

    def test_all_entry_closing_phases_and_all_eighty_exit_phases_preserve_the_fade(self):
        for level in (3, 4, 5):
            program = cavern_assets(level)[0]
            entry = program['entry_exit']
            for phase in range(len(entry['frames'])):
                with self.subTest(level=level, entry=phase):
                    self.assert_local_fade(level, entry['room'], entry_frame=phase)
            for room, records in program.get('pressure_plates', {}).get('rooms', {}).items():
                for index, record in enumerate(records):
                    if record['kind'] != 17:
                        continue
                    for phase in range(80):
                        phases = [0] * len(records)
                        phases[index] = phase
                        with self.subTest(level=level, room=int(room), exit=phase):
                            self.assert_local_fade(level, int(room), pressure_key=tuple(phases))

    def test_rooms_without_arches_are_unchanged_in_all_three_levels(self):
        doors = {key[:2] for key in door_retouch_assets()}
        for level in (3, 4, 5):
            for room in map(int, cavern_assets(level)[0]['rooms']):
                if (level, room) in doors:
                    continue
                with self.subTest(level=level, room=room):
                    old = self.wall_only(level, room)
                    new = cavern_room(room, retouched=True, level_number=level)
                    self.assertEqual(old.background.tobytes(), new.background.tobytes())
                    self.assertEqual(old.foreground.tobytes(), new.foreground.tobytes())
