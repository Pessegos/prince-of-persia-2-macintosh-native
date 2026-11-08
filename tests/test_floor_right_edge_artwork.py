"""Reviewed right tips of the floor beneath columns and shooting traps."""
import hashlib
import unittest

from tests.right_tip_expectations import PreviousArtworkMixin

from PIL import Image, ImageChops

from pop2.cavern_retouch import retouched_sprite
from pop2.caverns import (cavern_assets, cavern_command_sprite, cavern_room, clipped_sprite,
                          pressure_drawing_commands)
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tests import test_cavern_retouch as retouch_tests


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(),
                     'Imported game resources required')
class FloorRightEdgeArtworkTests(PreviousArtworkMixin, unittest.TestCase):
    def test_room16_approved_tips_preserve_other_floor_and_native_opt_out(self):
        definition = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
        edited = LevelRenderer(definition, preload_room=False).room(15)
        native = cavern_room(15, animated=True)
        before, after = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
        self.assertEqual(hashlib.sha256(after.tobytes()).hexdigest(),
                         'a5f823e2a653cfc956104a2483f8f1dc69fb94758ffee8135c12544e8cc25a38')
        changed = [(x, y) for y in range(365) for x in range(510)
                   if before.getpixel((x, y)) != after.getpixel((x, y))]
        self.assertEqual(len(changed), 220)
        self.assertTrue(all(215 <= y < 240 and (99 <= x < 142 or 354 <= x < 397)
                            for x, y in changed))
        self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
        retouch_tests.CavernRetouchTests().assert_masks_equal(native, edited)
        original = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
        self.assertEqual(original.room(15).flattened().tobytes(), native.flattened().tobytes())

    def test_room16_columns_buttons_and_trap_mouths_stay_native_in_other_states(self):
        program, resources, palette, shapes = cavern_assets()
        records = program['pressure_plates']['rooms']['15']
        states = [(0, a, 0, b) for a in (0, 1) for b in (0, 1)]
        states.extend((phase, 0, phase, 0) for phase in range(1, 7))
        for phases in states:
            with self.subTest(phases=phases):
                native = cavern_room(15, animated=True, pressure_key=phases)
                edited = cavern_room(15, animated=True, retouched=True, pressure_key=phases)
                commands = pressure_drawing_commands(program['rooms']['15'], records, phases, resources)
                mask = Image.new('L', (510, 365))
                for command in commands:
                    if command[7] != 4 or command[1] not in (*range(3531, 3539), 3554, 3555):
                        continue
                    source = cavern_command_sprite(command, resources, palette, shapes)
                    self.assertIs(retouched_sprite(15, command, source), source)
                    clipped = clipped_sprite(source, command)
                    if clipped:
                        image, (x, y) = clipped
                        mask.paste(255, (x, y, x+image.width, y+image.height), image.getchannel('A'))
                difference = ImageChops.difference(native.flattened().convert('RGB'),
                                                  edited.flattened().convert('RGB'))
                self.assertIsNone(ImageChops.multiply(difference, mask.convert('RGB')).getbbox())
                self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())
                retouch_tests.CavernRetouchTests().assert_masks_equal(native, edited)

    def test_room16_source_placement_hash_and_alpha_guards(self):
        program, resources, palette, shapes = cavern_assets()
        for x in (53, 308):
            with self.subTest(x=x):
                command = next(c for c in program['rooms']['15']
                               if c[:5] == ['back', 3526, x, 245, 16])
                source = cavern_command_sprite(command, resources, palette, shapes)
                result = retouched_sprite(15, command, source)
                self.assertNotEqual(result.tobytes(), source.tobytes())
                self.assertEqual(result.getchannel('A').tobytes(), source.getchannel('A').tobytes())
                altered = source.copy()
                altered.putpixel((0, 0), (1, 2, 3, 255))
                self.assertIs(retouched_sprite(15, command, altered), altered)
                for field, value in ((2, x+1), (3, 246), (7, 1)):
                    shifted = command.copy()
                    shifted[field] = value
                    self.assertIs(retouched_sprite(15, shifted, source), source)
