"""Approved floor joins preserve the wall relief and native collision masks."""
import hashlib
import unittest

from PIL import Image, ImageChops

from pop2.cavern_retouch import retouched_sprite
from pop2.caverns import (cavern_assets, cavern_command_sprite, cavern_room, clipped_sprite,
                          pressure_drawing_commands, room_assets)
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tests import test_cavern_retouch as retouch_tests


# Native level/room, approved cached RGB, preserved foreground RGBA, source placements.
APPROVED_FLOOR_JOINS = {
    (5, 9): ('c38b6f0dc49853d652be724aa228f18c3bb603b959650be594a91443796f5ee9',
              'd48906ee476325905e0f47d25991192a333e4fb25d07c157490204257b1320ad',
              ((3551, 102, 365, 16),)),
    (5, 19): ('72de66968e0cb63ddf9e982da4c589e7e4926b331fc8c67c8d1d5cfee0238107',
               'a8e4eaabbe47ff8d837e488f1d29ec57da25136972034315e30a9b0832e76a2b',
               ((3551, 306, 245, 16), (3556, 331, 232, 16))),
    (5, 13): ('a97267870d5c5ca70e25822525085021a3200b9abdd9bd38ba53ebffd8214f4e',
               'fa6699b4f1c62d3f2d4fcc9f3d3ad2d1d5bcef98231f5d3375ff528bd27a0915',
               ((3551, 255, 125, 16), (3525, 257, 125, 16))),
    (5, 11): ('bb1b2208c8f31a0be54d692a8fdd1d9bdf2c4d4ee04a951145ec138b1fae55c6',
               '1d1bf4cc4fd13e91c2c12360a3006c829989e9b64577d87d6a593bc4de14a63b',
               ((3551, 153, 245, 16), (3525, 155, 245, 16), (3551, 51, 365, 16), (3525, 53, 365, 16))),
    (4, 18): ('91ca82a8add9bbf792fae9d09f297a189c91849cdd4f4580edcc9faebfbaad65',
               'd8f650c6c598b7dd03be5ebf746d62812ca55049ad5f50959236b3488b06eaf6',
               ((3551, 102, 245, 16), (3556, 127, 232, 16), (3557, 102, 245, 16))),
    (4, 14): ('1b624888aa2e8417c4305244956567b77668b8d3c59931e0b7451d7a7eda2b7b',
               'b13c9ff078829fb96f68bcda0475c43a621efd11829f056c8fe367502ba18058',
               ((3551, 204, 365, 16), (3525, 206, 365, 16))),
    (4, 13): ('e08b3742a5b27f099f9b01e4f253e7b2ff7f58a6cc93bb5ed35cf0007db0e97a',
               'f8f1eabdc729c33c9e6cfb6ab6297089bbc90a9478d82a299d8bd6d1a4d4a23f',
               ((3551, 204, 125, 16), (3526, 206, 125, 16), (3551, 306, 365, 16), (3525, 308, 365, 16))),
    (3, 32): ('d23f55b7b625e87f2698dd5e8bd3399479c5293371cb9591b7b1987603f94e2f',
               '2dd6259c8d73db3a93989a3d304673ead5e142b601887af3d24fc9698712e5b5',
               ((3551, 51, 245, 16), (3525, 53, 245, 16))),
    (3, 26): ('64d955ab1a78694f3c1efee0b910f573f9dbdaef0695c167a7f42be941d4a67a',
               '63ba23709a693af28d05e09463f0a9d20fdf6c42c66300b03ce4e460971cc136',
               ((3551, 408, 245, 16), (3525, 410, 245, 16))),
    (3, 21): ('7ed2ab1071684891b8a2fab70a1bbefeee8327f39e2509ea64886ce9b2403912',
               '6f34c34d818f8abb73025ecceaa286ed200f08fac56537a09d7512d4689c42ab',
               ((3551, 255, 125, 16), (3525, 257, 125, 16))),
    (3, 15): ('1eac3788306c661ce31fee4fa3c51e458189f2d1f85d16465dad67312551d430',
               'e9c2e4e68b67d5d490a3992286c99d2c10f5829a093630968613dda51c865d8d',
               ((3551, 255, 125, 16), (3525, 257, 125, 16))),
    (3, 12): ('9152e74b8fdb313e8d91c09d631c695bbe6e47b93c64c6695041a87df2ac6519',
               'fb1d565baa6b3095c869f72cea16dcf7f7cb0662ca59f156f013d6b284795a60',
               ((3550, 51, 245, 16), (3525, 53, 245, 16))),
}


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(),
                     'Imported game resources required')
class FloorJoinArtworkTests(unittest.TestCase):
    def test_room9_button_pixels_stay_native_released_and_pressed(self):
        program, resources, palette, shapes = room_assets(5, 8)
        records = program['pressure_plates']['rooms']['8']
        expected = ('c38b6f0dc49853d652be724aa228f18c3bb603b959650be594a91443796f5ee9',
                    '9d7ec4ba9d172850b2a51e82d9803c2f0d736534a66226b84acc1d10b12d2984')
        for phase in (0, 1):
            with self.subTest(phase=phase):
                phases = (0, 0, phase, 0)
                native = cavern_room(8, level_number=5, animated=True, pressure_key=phases)
                edited = cavern_room(8, level_number=5, animated=True, pressure_key=phases,
                                     retouched=True)
                commands = pressure_drawing_commands(program['rooms']['8'], records, phases, resources)
                mask = Image.new('L', (510, 365))
                for command in commands:
                    if command[7] != 4 or command[1] not in (3554, 3555):
                        continue
                    source = cavern_command_sprite(command, resources, palette, shapes)
                    self.assertIs(retouched_sprite(8, command, source, level_number=5), source)
                    clipped = clipped_sprite(source, command)
                    if clipped:
                        image, (x, y) = clipped
                        mask.paste(255, (x, y, x+image.width, y+image.height), image.getchannel('A'))
                self.assertIsNotNone(mask.getbbox())
                before, after = native.flattened().convert('RGB'), edited.flattened().convert('RGB')
                difference = ImageChops.multiply(ImageChops.difference(before, after), mask.convert('RGB'))
                self.assertIsNone(difference.getbbox(), 'The entire button drawing must stay native')
                self.assertEqual(hashlib.sha256(after.tobytes()).hexdigest(), expected[phase])
                retouch_tests.CavernRetouchTests().assert_masks_equal(native, edited)
                self.assertEqual(native.foreground.tobytes(), edited.foreground.tobytes())

    def test_additional_approved_frames_and_foreground_match(self):
        prince = load_resource_file('Prince.rsrc')
        for (level, room), (expected, foreground, _sources) in APPROVED_FLOOR_JOINS.items():
            with self.subTest(level=level, room=room):
                definition = LevelDefinition.read(prince, level)
                edited = LevelRenderer(definition, preload_room=False).room(room-1)
                native = cavern_room(room-1, level_number=level, animated=True)
                self.assertEqual(hashlib.sha256(edited.flattened().convert('RGB').tobytes()).hexdigest(),
                                 expected)
                self.assertEqual(hashlib.sha256(edited.foreground.tobytes()).hexdigest(), foreground)
                retouch_tests.CavernRetouchTests().assert_masks_equal(native, edited)
                original = LevelRenderer(definition, preload_room=False, retouch_caverns=False)
                self.assertEqual(original.room(room-1).flattened().tobytes(), native.flattened().tobytes())

    def test_additional_floor_source_guards_preserve_alpha(self):
        for (level, room), (_expected, _foreground, sources) in APPROVED_FLOOR_JOINS.items():
            program, resources, palette, shapes = cavern_assets(level)
            for shape, x, bottom, mode in sources:
                with self.subTest(level=level, room=room, shape=shape, x=x, bottom=bottom):
                    command = next(c for c in program['rooms'][str(room-1)]
                                   if c[:5] == ['back', shape, x, bottom, mode])
                    source = cavern_command_sprite(command, resources, palette, shapes)
                    result = retouched_sprite(room-1, command, source, level_number=level)
                    self.assertNotEqual(source.tobytes(), result.tobytes())
                    self.assertEqual(source.getchannel('A').tobytes(), result.getchannel('A').tobytes())
                    altered = source.copy()
                    altered.putpixel((0, 0), (1, 2, 3, 255))
                    self.assertIs(retouched_sprite(room-1, command, altered, level_number=level), altered)
                    for field, value in ((2, x+1), (3, bottom+1), (7, 1)):
                        shifted = command.copy()
                        shifted[field] = value
                        self.assertIs(retouched_sprite(room-1, shifted, source, level_number=level), source)

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
