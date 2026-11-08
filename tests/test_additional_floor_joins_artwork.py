"""Full production goldens for the newly approved cavern floor joins."""
import hashlib
import unittest

from pop2.cavern_retouch import retouched_sprite
from pop2.caverns import cavern_command_sprite, cavern_room, room_assets
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tests.floor_join_expectations import approved_floor_rooms
from tests import test_cavern_retouch as retouch_tests


class FloorJoinFixtureTests(unittest.TestCase):
    def test_reviewed_native_pixel_masks_are_valid_and_do_not_target_buttons(self):
        for key, room in approved_floor_rooms().items():
            with self.subTest(room=key):
                self.assertEqual(len(room['rgb_sha256']), 64)
                for source in room['sources']:
                    self.assertNotIn(source['shape'], (3554, 3555, 3556, 3557))
                    self.assertTrue(source['offsets'])
                    self.assertEqual(len(source['offsets']), len(set(source['offsets'])))
                    self.assertTrue(all(0 <= p < source['size'][0]*source['size'][1]
                                        for p in source['offsets']))


@unittest.skipUnless((ASSET_DIR/'caverns_entry.json').is_file(), 'Imported game resources required')
class AdditionalFloorJoinArtworkTests(unittest.TestCase):
    def test_full_approved_production_frames_foreground_and_masks(self):
        prince = load_resource_file('Prince.rsrc')
        for key, expected in approved_floor_rooms().items():
            level, room = map(int, key.split(':'))
            with self.subTest(level=level, room=room):
                definition = LevelDefinition.read(prince, level)
                result = LevelRenderer(definition, preload_room=False).room(room-1)
                self.assertEqual(hashlib.sha256(result.flattened().convert('RGB').tobytes()).hexdigest(),
                                 expected['rgb_sha256'])
                self.assertEqual(hashlib.sha256(result.foreground.tobytes()).hexdigest(),
                                 expected['foreground_sha256'])
                native = cavern_room(room-1, level_number=level, animated=True)
                retouch_tests.CavernRetouchTests().assert_masks_equal(native, result)
                original = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
                self.assertEqual(original.room(room-1).flattened().tobytes(), native.flattened().tobytes())

    def test_whole_approved_sources_and_hash_placement_library_guards(self):
        for key, expected in approved_floor_rooms().items():
            level, room = map(int, key.split(':'))
            program, resources, palette, shapes = room_assets(level, room-1)
            for source_expected in expected['sources']:
                fields = [source_expected[k] for k in ('shape', 'x', 'bottom', 'mode')]
                with self.subTest(level=level, room=room, source=fields):
                    command = next(c for c in program['rooms'][str(room-1)] if c[1:5] == fields and c[7] == 4)
                    source = cavern_command_sprite(command, resources, palette, shapes)
                    result = retouched_sprite(room-1, command, source, level_number=level)
                    self.assertEqual(hashlib.sha256(result.tobytes()).hexdigest(), source_expected['approved_sha256'])
                    self.assertEqual(result.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                    corrupted = source.copy()
                    corrupted.putpixel((0, 0), (1, 2, 3, 255))
                    self.assertIs(retouched_sprite(room-1, command, corrupted, level_number=level), corrupted)
                    for field, value in ((2, command[2]+1), (3, command[3]+1), (7, 1)):
                        shifted = command.copy()
                        shifted[field] = value
                        self.assertIs(retouched_sprite(room-1, shifted, source, level_number=level), source)

    def test_all_button_and_cut_floor_source_variants_preserve_previous_artwork(self):
        for key, expected in approved_floor_rooms().items():
            level, room = map(int, key.split(':'))
            _, resources, palette, shapes = room_assets(level, room-1)
            for glyph in expected['glyphs']:
                with self.subTest(level=level, room=room, command=glyph['command'][:5]):
                    source = cavern_command_sprite(glyph['command'], resources, palette, shapes)
                    self.assertEqual(hashlib.sha256(source.tobytes()).hexdigest(), glyph['native_sha256'])
                    result = retouched_sprite(room-1, glyph['command'], source, level_number=level)
                    self.assertEqual(hashlib.sha256(result.tobytes()).hexdigest(), glyph['previous_sha256'])
