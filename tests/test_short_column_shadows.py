"""Reviewed short-column shadows: complete frames and unchanged stone/masks."""
import hashlib
import unittest

from pop2.cavern_retouch import retouched_sprite
from pop2.caverns import cavern_assets, cavern_command_sprite, cavern_room
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tests import test_cavern_retouch as retouch_tests


# Zero-based room keys; placements are X, bottom, changed source pixels.
# Frame hashes include all earlier approved artwork in each room.
APPROVED = {
    (3, 4): ([(212, 362, 197)],
             '4c21295ad0cc54ed2aecc91cf40433df13f4576ee3fab320c53544783cc798a5'),
}


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(),
                     'Imported game resources required')
class ShortColumnShadowTests(unittest.TestCase):
    def test_approved_frames_and_native_opt_out_preserve_masks(self):
        prince = load_resource_file('Prince.rsrc')
        for (level, room), (_placements, expected) in APPROVED.items():
            with self.subTest(level=level, room=room+1):
                definition = LevelDefinition.read(prince, level)
                edited = LevelRenderer(definition, preload_room=False).room(room)
                native = cavern_room(room, level_number=level, animated=True)
                self.assertEqual(hashlib.sha256(edited.flattened().convert('RGB').tobytes()).hexdigest(),
                                 expected)
                retouch_tests.CavernRetouchTests().assert_masks_equal(native, edited)
                auditor = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
                self.assertEqual(auditor.room(room).flattened().tobytes(), native.flattened().tobytes())

    def test_only_dark_contour_fringe_recolours_and_changed_sources_are_rejected(self):
        for (level, room), (placements, _expected) in APPROVED.items():
            program, resources, palette, shapes = cavern_assets(level)
            for x, bottom, count in placements:
                with self.subTest(level=level, room=room+1, bottom=bottom):
                    command = next(c for c in program['rooms'][str(room)]
                                   if c[:5] == ['front', 3531, x, bottom, 16])
                    source = cavern_command_sprite(command, resources, palette, shapes)
                    original = source.tobytes()
                    edited = retouched_sprite(room, command, source, level_number=level)
                    changed = [(px, py) for py in range(source.height) for px in range(source.width)
                               if source.getpixel((px, py)) != edited.getpixel((px, py))]
                    self.assertEqual(len(changed), count)
                    # Both halves must be treated, with lit stone and the inner body intact.
                    self.assertTrue(any(py < 59 for _px, py in changed))
                    self.assertTrue(any(py >= 75 for _px, py in changed))
                    for px, py in changed:
                        edge = max(sx for sx in range(15, source.width)
                                   if source.getpixel((sx, py))[3])
                        self.assertTrue(5 <= py < 107 and edge-2 <= px <= edge)
                        old = source.getpixel((px, py))
                        self.assertLessEqual(max(old[:3]), 66)
                        self.assertLessEqual(old[1], 33)
                    self.assertEqual(edited.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                    self.assertEqual(source.tobytes(), original)
                    changed_source = source.copy()
                    changed_source.putpixel((0, 0), (1, 2, 3, 255))
                    self.assertIs(retouched_sprite(room, command, changed_source, level_number=level),
                                  changed_source)
                    for field, value in ((1, 3532), (2, x+1), (3, bottom+1), (4, 0), (7, 1)):
                        shifted = command.copy()
                        shifted[field] = value
                        self.assertIs(retouched_sprite(room, shifted, source, level_number=level), source)
