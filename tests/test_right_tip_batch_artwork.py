"""Full, unmasked production snapshots of the reviewed right-tip batch."""
import hashlib
import unittest

from pop2.cavern_retouch import retouched_sprite
from pop2.caverns import cavern_room, room_assets, cavern_command_sprite
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tests.right_tip_expectations import approved_rooms
from tests import test_cavern_retouch as retouch_tests


class RightTipFixtureTests(unittest.TestCase):
    def test_reviewed_masks_have_unique_valid_native_coordinates(self):
        for key, item in approved_rooms().items():
            with self.subTest(room=key):
                self.assertEqual(len(item['rgb_sha256']), 64)
                for source in item['sources']:
                    self.assertEqual(source['shape'], 3526)
                    self.assertEqual(len(source['offsets']), len(set(source['offsets'])))
                    self.assertTrue(all(0 <= p < source['size'][0]*source['size'][1]
                                        for p in source['offsets']))


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(),
                     'Imported game resources required')
class RightTipBatchArtworkTests(unittest.TestCase):
    def test_full_approved_room_frames_and_foreground(self):
        prince = load_resource_file('Prince.rsrc')
        for key, item in approved_rooms().items():
            level, native_room = map(int, key.split(':'))
            with self.subTest(level=level, room=native_room):
                definition = LevelDefinition.read(prince, level)
                result = LevelRenderer(definition, preload_room=False).room(native_room-1)
                self.assertEqual(hashlib.sha256(result.flattened().convert('RGB').tobytes()).hexdigest(),
                                 item['rgb_sha256'])
                self.assertEqual(hashlib.sha256(result.foreground.tobytes()).hexdigest(),
                                 item['foreground_sha256'])
                native = cavern_room(native_room-1, level_number=level, animated=True)
                retouch_tests.CavernRetouchTests().assert_masks_equal(native, result)
                original = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
                self.assertEqual(original.room(native_room-1).flattened().tobytes(),
                                 native.flattened().tobytes())

    def test_approved_source_pixels_hash_alpha_and_placement_guards(self):
        for key, item in approved_rooms().items():
            level, native_room = map(int, key.split(':'))
            room = native_room-1
            program, resources, palette, shapes = room_assets(level, room)
            for expected in item['sources']:
                with self.subTest(level=level, room=native_room, x=expected['x'], bottom=expected['bottom']):
                    fields = [expected[n] for n in ('shape', 'x', 'bottom', 'mode')]
                    command = next(c for c in program['rooms'][str(room)] if c[1:5] == fields)
                    source = cavern_command_sprite(command, resources, palette, shapes)
                    result = retouched_sprite(room, command, source, level_number=level)
                    self.assertEqual(hashlib.sha256(result.tobytes()).hexdigest(), expected['approved_sha256'])
                    self.assertEqual(result.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                    changed = source.copy()
                    changed.putpixel((0, 0), (1, 2, 3, 255))
                    self.assertIs(retouched_sprite(room, command, changed, level_number=level), changed)
                    for field, value in ((2, command[2]+1), (3, command[3]+1), (7, 1)):
                        shifted = command.copy()
                        shifted[field] = value
                        self.assertIs(retouched_sprite(room, shifted, source, level_number=level), source)
