"""Reviewed room24 joins, including preservation of neighboring back columns."""
import hashlib
import unittest

from tests.right_tip_expectations import PreviousArtworkMixin

from pop2.cavern_retouch import retouched_sprite
from pop2.caverns import cavern_assets, cavern_command_sprite, cavern_room
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tests import test_cavern_retouch as retouch_tests


# Native room24 is port index23. Cached room hash excludes animated items.
APPROVED_HASH = '155016d0323e511fe037104e7edda38d6a9045cfcd70bc4ad3f7984dd206d567'
FRONT_COLUMNS = ((264, 243), (315, 363))


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(),
                     'Imported game resources required')
class Room24ArtworkTests(PreviousArtworkMixin, unittest.TestCase):
    def test_approved_frame_matches_and_native_opt_out_preserves_masks(self):
        definition = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
        edited = LevelRenderer(definition, preload_room=False).room(23)
        native = cavern_room(23, animated=True)
        self.assertEqual(hashlib.sha256(edited.flattened().convert('RGB').tobytes()).hexdigest(),
                         APPROVED_HASH)
        retouch_tests.CavernRetouchTests().assert_masks_equal(native, edited)
        auditor = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
        self.assertEqual(auditor.room(23).flattened().tobytes(), native.flattened().tobytes())

    def test_lit_bodies_back_columns_and_source_guards_stay_native(self):
        program, resources, palette, shapes = cavern_assets()
        for x, bottom in FRONT_COLUMNS:
            with self.subTest(x=x, bottom=bottom):
                command = next(c for c in program['rooms']['23']
                               if c[:5] == ['front', 3533, x, bottom, 16])
                source = cavern_command_sprite(command, resources, palette, shapes)
                original = source.tobytes()
                result = retouched_sprite(23, command, source)
                changed = [(px, py) for py in range(source.height) for px in range(source.width)
                           if source.getpixel((px, py)) != result.getpixel((px, py))]
                self.assertEqual(len(changed), 67)
                self.assertTrue(all(28 <= px < 37 and 57 <= py < 109
                                    and max(source.getpixel((px, py))[:3]) <= 24
                                    for px, py in changed))
                self.assertEqual(source.tobytes(), original)
                self.assertEqual(result.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                changed_source = source.copy()
                changed_source.putpixel((0, 0), (1, 2, 3, 255))
                self.assertIs(retouched_sprite(23, command, changed_source), changed_source)
                for field, value in ((2, x+1), (3, bottom+1), (7, 1)):
                    shifted = command.copy()
                    shifted[field] = value
                    self.assertIs(retouched_sprite(23, shifted, source), source)
        # The wall grade must never recolour the smaller columns behind it.
        for command in program['rooms']['23']:
            if command[0] == 'back' and command[1] == 3534 and command[7] == 4:
                source = cavern_command_sprite(command, resources, palette, shapes)
                self.assertIs(retouched_sprite(23, command, source), source)
