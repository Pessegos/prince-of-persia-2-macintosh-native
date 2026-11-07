"""Approved floor joins preserve the wall relief and native collision masks."""
import hashlib
import unittest

from pop2.cavern_retouch import retouched_sprite
from pop2.caverns import cavern_assets, cavern_command_sprite, cavern_room
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tests import test_cavern_retouch as retouch_tests


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(),
                     'Imported game resources required')
class FloorJoinArtworkTests(unittest.TestCase):
    def test_room11_approved_floor_preserves_wall_foreground_and_native_opt_out(self):
        definition = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
        edited = LevelRenderer(definition, preload_room=False).room(10)
        native = cavern_room(10, animated=True)
        before, after = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
        self.assertEqual(hashlib.sha256(after.tobytes()).hexdigest(),
                         'f3b222a29bdbec22895500caffde12090d18f10d1101095ca1e41f7d25c05051')
        self.assertEqual(before.crop((0, 0, 510, 95)).tobytes(),
                         after.crop((0, 0, 510, 95)).tobytes())
        self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
        changed = [(x, y) for y in range(365) for x in range(510)
                   if before.getpixel((x, y)) != after.getpixel((x, y))]
        self.assertEqual(len(changed), 156)
        self.assertTrue(all(53 <= x < 96 and 95 <= y < 120 for x, y in changed))
        retouch_tests.CavernRetouchTests().assert_masks_equal(native, edited)
        original = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
        self.assertEqual(original.room(10).flattened().tobytes(), native.flattened().tobytes())

    def test_room11_sources_reject_changed_resource_or_placement(self):
        program, resources, palette, shapes = cavern_assets()
        for shape, x in ((3551, 51), (3525, 53)):
            with self.subTest(shape=shape):
                command = next(c for c in program['rooms']['10']
                               if c[:5] == ['back', shape, x, 125, 16])
                source = cavern_command_sprite(command, resources, palette, shapes)
                result = retouched_sprite(10, command, source)
                self.assertNotEqual(result.tobytes(), source.tobytes())
                self.assertEqual(result.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                changed = source.copy()
                changed.putpixel((0, 0), (1, 2, 3, 255))
                self.assertIs(retouched_sprite(10, command, changed), changed)
                for field, value in ((2, x+1), (3, 126), (7, 1)):
                    shifted = command.copy()
                    shifted[field] = value
                    self.assertIs(retouched_sprite(10, shifted, source), source)
