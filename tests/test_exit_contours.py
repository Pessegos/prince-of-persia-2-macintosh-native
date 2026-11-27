"""Ending-door stone uses its real alpha, including irregular cave notches."""

from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from pop2.caverns import (CavernRoom, cavern_assets, cavern_command_sprite,
                          clipped_sprite, scenery_name)
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState


DOORS = ((3, 12, 16), (3, 29, 25), (4, 21, 24),
         (6, 0, 22), (6, 15, 22), (6, 15, 26), (7, 20, 18),
         (8, 0, 24), (8, 4, 24), (8, 22, 22), (8, 22, 26),
         (8, 23, 22), (8, 23, 26), (8, 24, 24), (9, 4, 24))
ALREADY_CLEAR = (7, 20, 18)


def strongest_channel(image):
    red, green, blue = image.split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


class ExitContourTests(unittest.TestCase):
    def test_original_alpha_and_environment_specific_height_gate(self):
        size = (510, 365)
        stone = Image.new('RGBA', (12, 12))
        ImageDraw.Draw(stone).polygon(((0, 0), (11, 0), (11, 11), (8, 11),
                                       (9, 7), (6, 5), (7, 2), (0, 2)), fill='gray')
        stone.putpixel((9, 4), (0, 0, 0, 0))
        room = CavernRoom(Image.new('RGBA', size), Image.new('RGBA', size), {}, (), (), 0, 3,
                          actor_cell_occlusion={},
                          exit_foreground=((stone, (120, 130)),))
        for kind, actor, pose, y in product((2, 3, 4), (0, 2), (216, 217, 226, 227), (0, -24, -25, -42)):
            with self.subTest(kind=kind, actor=actor, pose=pose, y=y):
                state = SequenceState(70, actor_type=actor, action=pose, level_kind=kind, current_y=y)
                frame = Image.new('RGBA', size)
                room.draw_actor_foreground(frame, state, (100, 100, 200, 240))
                active = actor == 0 and 217 <= pose <= 226 and (kind != 3 or y < -24)
                mask = room.actor_mask(1, state=state, bounds=(100, 100, 200, 240))
                self.assertIsNone(frame.getbbox(), 'The doorway must not repaint the scene')
                if active:
                    self.assertEqual(mask.crop((120, 130, 132, 142)).tobytes(),
                                     stone.getchannel('A').tobytes())
                else:
                    self.assertIsNone(mask.getbbox())

    def test_mask_keeps_live_background_colours_and_leaves_the_aperture_open(self):
        size = (510, 365)
        stone = Image.new('RGBA', (12, 12), 'gray')
        stone.putpixel((5, 5), (0, 0, 0, 0))
        room = CavernRoom(Image.new('RGBA', size), Image.new('RGBA', size), {}, (), (), 0, 3,
                          actor_cell_occlusion={}, exit_foreground=((stone, (120, 130)),))
        for kind in (2, 3, 4):
            with self.subTest(kind=kind):
                state = SequenceState(70, actor_type=0, action=224, level_kind=kind, current_y=-25)
                # A distinct backdrop stands in for a live light/particle
                # effect already drawn behind the actor; static gray must
                # never replace it merely because the Prince enters.
                frame = Image.new('RGBA', size, (30, 60, 90, 255))
                layer = Image.new('RGBA', size, 'white')
                layer.putalpha(ImageChops.invert(room.actor_mask(1, state=state,
                                                                bounds=(100, 100, 200, 240))))
                frame = Image.alpha_composite(frame, layer)
                frame = room.draw_actor_foreground(frame, state, (100, 100, 200, 240))
                self.assertEqual(frame.getpixel((120, 130)), (30, 60, 90, 255))
                self.assertEqual(frame.getpixel((125, 135)), (255, 255, 255, 255))


@unittest.skipUnless(all((ASSET_DIR / scenery_name(n)).is_file() for n in range(3, 10)),
                     'Imported cavern and ruins artwork required')
class ExitContourSceneTests(unittest.TestCase):
    def test_all_door_anchors_hide_covered_pixels_keep_voids_and_leave_scenery_stable(self):
        from tools.audit_temple_routes import Harness

        harness = Harness(3, draw=True)
        scene = harness.scene
        scene.audio = None
        original = scene.composite_actor
        original_mask = CavernRoom.actor_mask
        changed, visible, checked = set(), set(), set()

        def legacy(art, *args, **kwargs):
            return original_mask(replace(art, exit_foreground=()), *args, **kwargs)

        def without_player(frame, layer, row=None, bottom=None, state=None, bounds=None, record=None):
            if state is not None and state.actor_type == 0:
                layer = Image.new('RGBA', layer.size)
            return original(frame, layer, row, bottom, state, bounds, record)

        try:
            for site in DOORS:
                with self.subTest(site=site):
                    number, room, cell = site
                    # Canonical level-entry fixture; a prior level-6 ending
                    # must not select level 7's separate upper entrance.
                    scene.game.ruins_entry = None
                    scene.load_level(number)
                    row, column = divmod(cell, 10)
                    value = scene.level_map.tile(room, column, row).foreground
                    scene.game.caverns.plates.foreground[(room, cell)] = (value & 0xff00) | 79
                    scene.jump_to_room(room, row, column * 51 + 24, 1)
                    self.assertTrue(scene.start_cavern_exit())
                    program, resources, palette, shapes = cavern_assets(number)
                    shape = 3565 if number in (3, 4, 5) else 3545
                    cover = Image.new('L', (510, 365))
                    for command in program['rooms'][str(room)]:
                        if command[:2] != ['back', shape] or command[7] != 4:
                            continue
                        sprite, position = clipped_sprite(
                            cavern_command_sprite(command, resources, palette, shapes), command)
                        plane = Image.new('L', cover.size)
                        plane.paste(sprite.getchannel('A'), position)
                        if shape == 3545:
                            plane.paste(0, (0, 0, 510, max(0, command[5] * 120 - 10)))
                        cover = ImageChops.lighter(cover, plane)
                    self.assertIsNotNone(cover.getbbox())
                    for _ in range(36):
                        state = scene.sequence_state
                        saved = replace(state)
                        scene.render()
                        fixed = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                        with patch.object(CavernRoom, 'actor_mask', legacy):
                            scene.render()
                            previous = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                        difference = strongest_channel(ImageChops.difference(fixed, previous))
                        active = 217 <= state.action <= 226 and (number >= 6 or state.current_y < -24)
                        if active:
                            self.assertIsNone(ImageChops.multiply(difference, ImageChops.invert(cover)).getbbox(),
                                              'Stone notches and all pixels outside its alpha must stay intact')
                            left, top, right, bottom = scene.player_bounds()
                            scenery_delta = difference.copy()
                            scenery_delta.paste(0, (max(0, left), max(0, top),
                                                    min(510, right + 1), min(365, bottom + 1)))
                            self.assertIsNone(scenery_delta.getbbox(), 'Scenery outside the Prince changed')
                            with patch.object(scene, 'composite_actor', side_effect=without_player):
                                scene.render()
                                empty = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                            ink = strongest_channel(ImageChops.difference(fixed, empty))
                            self.assertIsNone(ImageChops.multiply(ink, cover).getbbox(),
                                              f'Prince is drawn over stone at pose {state.action}')
                            if ink.getbbox():
                                visible.add(site)
                            if difference.getbbox():
                                changed.add(site)
                            checked.add(site)
                        else:
                            self.assertIsNone(difference.getbbox(), 'Unrelated/early cave poses changed')
                        self.assertEqual(state, saved, 'Rendering changed the sequence state')
                        if scene.level_complete:
                            break
                        harness.tick()
            self.assertEqual(checked, set(DOORS))
            self.assertEqual(visible, set(DOORS))
            self.assertEqual(changed, set(DOORS) - {ALREADY_CLEAR})
        finally:
            harness.close()
