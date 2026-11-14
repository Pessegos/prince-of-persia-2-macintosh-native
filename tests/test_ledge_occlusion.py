"""User-guided slab masking is an intentional improvement over Macintosh."""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from pop2.caverns import CavernRoom
from pop2.paths import ASSET_DIR
from pop2.render_opening import (OpeningRoom, RoofForeground, RoofLedge,
                                 ledge_surface_clip)


def prince(action=140, sequence=10, facing=1):
    return SimpleNamespace(actor_type=0, source_sequence_id=sequence,
                           sequence_id=sequence, action=action, facing=facing,
                           animation_state=1)


class LedgeSurfaceTests(unittest.TestCase):
    def test_surface_stays_on_the_upper_floor_across_the_row_change(self):
        for sequence in (10, 68):
            for shift in (-120, 0, 120):
                for pose, bounds in ((138, (213, 196, 236, 279)),
                                     (141, (214, 201, 257, 251)),
                                     (144, (224, 190, 274, 230))):
                    left, top, right, bottom = bounds
                    with self.subTest(sequence=sequence, shift=shift, pose=pose):
                        self.assertEqual(ledge_surface_clip(prince(pose, sequence),
                            (left, top + shift, right, bottom + shift)),
                            (1 + shift // 120, (left, 227 + shift, right + 1, bottom + shift + 1)))

    def test_only_the_princes_climb_and_controlled_descent_use_the_improvement(self):
        bounds = (214, 201, 257, 251)
        self.assertIsNone(ledge_surface_clip(None, bounds))
        self.assertIsNone(ledge_surface_clip(prince(), None))
        for field, values in (('actor_type', (2, 4, 7, 8, 11)),
                              ('source_sequence_id', (0, 9, 14, 15, 27, 118)),
                              ('action', (99, 134, 145, 148, 149))):
            for value in values:
                state = prince()
                setattr(state, field, value)
                with self.subTest(field=field, value=value):
                    self.assertIsNone(ledge_surface_clip(state, bounds))

    @staticmethod
    def slab():
        slab = Image.new('RGBA', (51, 30))
        ImageDraw.Draw(slab).polygon(((0, 29), (30, 0), (50, 0), (50, 29)), fill='gray')
        slab.putpixel((24, 20), (0, 0, 0, 0))
        return slab

    def test_both_facings_and_sequences_preserve_support_corner_holes_and_underside(self):
        size = (510, 365)
        front = Image.new('RGBA', size)
        front.putpixel((80, 115), (0, 255, 0, 255))
        room = CavernRoom(Image.new('RGBA', size), front, {}, (), (), 0, 3,
                          floor_redraw={(1, 0): [(self.slab(), (51, 95))]})
        for facing in (0, 1):
            for sequence in (10, 68):
                for pose in (138, 140, 141, 143, 144):
                    with self.subTest(facing=facing, sequence=sequence, pose=pose):
                        frame = Image.new('RGBA', size, 'red')
                        room.draw_actor_foreground(frame, prince(pose, sequence, facing),
                                                   (55, 90, 95, 145))
                        self.assertEqual(frame.getpixel((70, 110)), (128, 128, 128, 255))
                        for pixel in ((80, 106), (55, 110), (75, 115), (80, 130), (96, 115)):
                            self.assertEqual(frame.getpixel(pixel), (255, 0, 0, 255), pixel)
                        self.assertEqual(frame.getpixel((80, 115)), (0, 255, 0, 255))

    def test_roof_near_edge_clips_the_slab_but_keeps_the_shaded_side_behind_him(self):
        size = (510, 365)
        ledge = RoofLedge(0, 51, 95, self.slab().getchannel('A'))
        room = OpeningRoom(Image.new('RGBA', size), Image.new('RGBA', size),
                           {}, (ledge,), (), 0)
        # Pose136 normally sends the intersecting ledge entirely behind him.
        # The shaded side beyond its 19-pixel near strip remains behind him.
        for facing in (0, 1):
            for sequence in (10, 68):
                with self.subTest(facing=facing, sequence=sequence):
                    mask = room.actor_mask(1, state=prince(136, sequence, facing),
                                           bounds=(55, 90, 95, 145))
                    self.assertEqual(mask.getpixel((68, 115)), 255)
                    for pixel in ((68, 106), (55, 110), (75, 115), (80, 130), (80, 115)):
                        self.assertEqual(mask.getpixel(pixel), 0, pixel)

    def test_harbor_planks_keep_their_alpha_beyond_the_native_half_width(self):
        size = (510, 365)
        piece = RoofForeground(0, 1, 1, 51, 95, self.slab().getchannel('A'), floor_redraw=True)
        room = OpeningRoom(Image.new('RGBA', size), Image.new('RGBA', size),
                           {}, (), (piece,), 15)
        mask = room.actor_mask(1, state=prince(136), bounds=(55, 90, 95, 145))
        self.assertEqual(mask.getpixel((80, 110)), 255)
        self.assertEqual(mask.getpixel((80, 106)), 0)
        self.assertEqual(mask.getpixel((75, 115)), 0)

    def test_custom_bridge_plank_without_a_full_floor_keeps_its_native_repaint(self):
        size = (510, 365)
        plank = Image.new('RGBA', (20, 8), 'gray')
        room = CavernRoom(Image.new('RGBA', size), Image.new('RGBA', size), {}, (), (), 9, 3,
                          floor_redraw={}, climb_redraw={(140, 1, 0): [(plank, (51, 112))]})
        frame = Image.new('RGBA', size, 'red')
        room.draw_actor_foreground(frame, prince(), (55, 90, 95, 145))
        self.assertEqual(frame.getpixel((60, 115)), (128, 128, 128, 255))
        self.assertEqual(frame.getpixel((60, 110)), (255, 0, 0, 255))


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported game artwork required')
class LedgeSceneTests(unittest.TestCase):
    def test_room8_descent_and_ascent_hide_the_intruding_pixels_and_keep_the_support_line(self):
        from tools.audit_temple_routes import Harness

        harness = Harness(6, draw=True)
        scene = harness.scene
        try:
            scene.jump_to_room(7, 1, 235, 1)
            scene.set_key_state('shift', True)
            scene.set_key_state('down', True)
            checked = set()
            for tick in range(45):
                if tick == 2:
                    scene.set_key_state('down', False)
                if tick == 20:
                    scene.set_key_state('up', True)
                if tick == 23:
                    scene.set_key_state('up', False)
                harness.tick()
                state = scene.sequence_state
                if state.source_sequence_id not in (10, 68) or state.action not in (138, 140, 141, 143, 144):
                    continue
                before_state = replace(state)
                scene.render()
                improved = scene.native_viewport.copy()
                with patch('pop2.caverns.ledge_surface_clip', return_value=None):
                    scene.render()
                    native_style = scene.native_viewport.copy()
                self.assertEqual(state, before_state, 'rendering must not change gameplay state')
                # Scene X225 appears at viewport X226 (one-pixel room margin).
                # Old rendering exposes trousers/shirt/boot here, inside the slab.
                self.assertEqual(improved.getpixel((226, 227)), (157, 114, 98, 255))
                self.assertNotEqual(native_style.getpixel((226, 227)), improved.getpixel((226, 227)))
                # All drawn pixels on/above the support line and beneath the
                # slab remain identical, including hands and dangling feet.
                for box in ((0, 0, 512, 227), (0, 245, 512, 365)):
                    self.assertIsNone(ImageChops.difference(improved.crop(box).convert('RGB'),
                        native_style.crop(box).convert('RGB')).getbbox())
                checked.add((state.source_sequence_id, state.action))
            self.assertEqual(checked, {(sequence, pose) for sequence in (10, 68)
                                      for pose in (138, 140, 141, 143, 144)})
            self.assertEqual((scene.action, scene.room_id, scene.terrain_motion.row), (15, 7, 1))
        finally:
            harness.close()

    def test_real_input_round_trips_in_both_facings_across_scenery_families(self):
        from tools.audit_temple_routes import Harness

        # Actual unmodified level cells, zero-based rooms, supplied idle starts.
        sites = ((1, 0, 1, 331, 1), (1, 0, 1, 134, 0),
                 (3, 17, 1, 433, 1), (3, 29, 0, 134, 0),
                 (6, 7, 1, 235, 1), (7, 12, 1, 134, 0),
                 (10, 6, 1, 280, 1), (10, 9, 1, 83, 0),
                 (14, 0, 1, 76, 1), (14, 0, 1, 287, 0))
        harness = Harness(6, draw=True)
        scene = harness.scene
        try:
            for number, room, row, x, facing in sites:
                with self.subTest(level=number, room=room + 1, facing=facing):
                    scene.load_level(number)
                    scene.jump_to_room(room, row, x, facing)
                    scene.set_key_state('shift', True)
                    scene.set_key_state('down', True)
                    poses = set()
                    for tick in range(45):
                        if tick == 2:
                            scene.set_key_state('down', False)
                        if tick == 20:
                            scene.set_key_state('up', True)
                        if tick == 23:
                            scene.set_key_state('up', False)
                        harness.tick()
                        if scene.sequence_state.source_sequence_id == 10:
                            poses.add(scene.action)
                    self.assertTrue(set(range(135, 149)).issubset(poses), poses)
                    self.assertEqual((scene.action, scene.room_id, scene.terrain_motion.row,
                                      scene.sequence_state.current_y, scene.sequence_state.facing),
                                     (15, room, row, 0, facing))
                    self.assertTrue(scene.combat.player.alive)
        finally:
            harness.close()
