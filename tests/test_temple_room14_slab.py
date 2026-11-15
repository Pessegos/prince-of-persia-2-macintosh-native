"""Room14 loose-floor contact, debris and downstairs guard progression."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.paths import ASSET_DIR
from pop2.caverns import CavernRoom, loose_contact_floor_cell


class LooseContactRevealTests(unittest.TestCase):
    def test_contact_mask_uses_whole_slab_alpha_and_preserves_upper_stone_holes_and_cache(self):
        size = (20, 20)
        contour = Image.new('RGBA', (8, 5), 'gray')
        contour.putpixel((3, 2), (0, 0, 0, 0))
        room = CavernRoom(Image.new('RGBA', size), Image.new('RGBA', size), {}, (), (), 0, 2,
                          platform_contours={(0, 0): [(contour, (8, 10))]})
        original = Image.new('L', size, 255)
        source_bytes = contour.tobytes()
        mask = room.contact_floor_mask(original, (0, 0))
        self.assertEqual(mask.getpixel((10, 12)), 0)
        for point in ((11, 12), (10, 9), (17, 12), (10, 15)):
            self.assertEqual(mask.getpixel(point), 255, point)
        self.assertEqual(original.tobytes(), Image.new('L', size, 255).tobytes())
        self.assertEqual(contour.tobytes(), source_bytes)
        self.assertIs(room.contact_floor_mask(original, (1, 0)), original)

    def test_deferring_one_floor_keeps_the_neighbouring_floor_repaint(self):
        size = (510, 365)
        red = Image.new('RGBA', (20, 20), 'red')
        blue = Image.new('RGBA', (20, 20), 'blue')
        room = CavernRoom(Image.new('RGBA', size), Image.new('RGBA', size), {}, (), (), 0, 2,
                          floor_redraw={(0, 1): [(red, (10, 220))],
                                        (1, 1): [(blue, (60, 220))]})
        state = SimpleNamespace(action=106, facing=1, animation_state=4)
        frame = Image.new('RGBA', size, 'white')
        room.draw_actor_floor_foreground(frame, state, (0, 200, 100, 240), (0, 1))
        self.assertEqual(frame.getpixel((15, 225)), (255, 255, 255, 255))
        self.assertEqual(frame.getpixel((65, 225)), (0, 0, 255, 255))

    def test_only_forced_first_short_jump_contact_defers_its_supporting_floor(self):
        state = SimpleNamespace(level_kind=2, actor_type=0, source_sequence_id=18,
                                action=106, animation_state=4, current_y=6,
                                target_x=318, facing=1)
        tile = SimpleNamespace(room=13, kind=11, foreground=11)
        terrain = SimpleNamespace(tile=lambda room, col, row: tile)
        loose = SimpleNamespace(active={(13, 25): 39})
        record = SimpleNamespace(offset_x=0, aux=0)

        def cell():
            return loose_contact_floor_cell(terrain, loose, 13, 2, state, record)

        self.assertEqual(cell(), (5, 2))
        for field, values in (('level_kind', (1, 3, 4, 5, 6)),
                              ('actor_type', (2, 4, 6, 11)),
                              ('source_sequence_id', (7, 9, 20, 21)),
                              ('action', (102, 105, 107)),
                              ('animation_state', (0, 3, 5)),
                              ('current_y', (0, 5, 7, -89))):
            original = getattr(state, field)
            for value in values:
                with self.subTest(field=field, value=value):
                    setattr(state, field, value)
                    self.assertIsNone(cell())
            setattr(state, field, original)
        for field, values in (('room', (12, None)), ('kind', (0, 1, 15, 26)),
                              ('foreground', (0, 10, 12, 0x4b))):
            original = getattr(tile, field)
            for value in values:
                with self.subTest(field=field, value=value):
                    setattr(tile, field, value)
                    self.assertIsNone(cell())
            setattr(tile, field, original)
        for active in ({}, {(13, 25): 1}, {(12, 25): 39}, {(13, 26): 39}):
            loose.active = active
            self.assertIsNone(cell())


@unittest.skipUnless((ASSET_DIR / 'temple_level10.json').is_file(), 'Imported temple resources required')
class Room14SlabTests(unittest.TestCase):
    def test_first_contact_keeps_the_whole_boot_in_front_of_the_neighbouring_stone_base(self):
        from tools.audit_temple_routes import Harness, press

        for start_x in (150, 155):
            with self.subTest(start_x=start_x):
                harness = Harness(10, draw=True, peaceful=False)
                scene = harness.scene
                scene.audio = None
                changed = []
                try:
                    scene.jump_to_room(13, 1, start_x, 1)
                    press(harness, 'up', True)
                    press(harness, 'R', True)
                    for tick in range(23):
                        harness.tick()
                        if tick == 2:
                            press(harness, 'up', False)
                        if tick == 9:
                            press(harness, 'R', False)
                        scene.render()
                        fixed = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                        # e24c078 deferred only QuickFloor; the earlier alpha
                        # mask still removed the toe at these actual positions.
                        with patch.object(CavernRoom, 'contact_floor_mask',
                                          lambda art, mask, cell: mask):
                            scene.render()
                            previous = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                        delta = ImageChops.difference(fixed, previous)
                        if tick != 16:
                            self.assertIsNone(delta.getbbox(), f'Frame {tick} changed')
                            continue
                        bounds = scene.player_bounds()
                        foot = (bounds[0], bounds[3] - 24, bounds[2] + 1, bounds[3] + 1)
                        # Independently remove ALL actor masks to obtain the
                        # original complete leg/boot artwork, not another
                        # floor-only control that retains the same toe cut.
                        with patch.object(CavernRoom, 'actor_mask',
                                          return_value=Image.new('L', (510, 365))):
                            scene.render()
                            raw = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                        self.assertIsNone(ImageChops.difference(fixed.crop(foot), raw.crop(foot)).getbbox(),
                                          'Lower leg/boot still cut by the neighbouring plinth')
                        self.assertIsNotNone(delta.getbbox())
                        # Upper statue/body masking stays exactly as before.
                        self.assertIsNone(delta.crop((0, 0, 510, foot[1])).getbbox())
                        self.assertIsNotNone(ImageChops.difference(fixed, raw).crop(
                            (0, 0, 510, foot[1])).getbbox())
                        changed.append(tick)
                    self.assertEqual(changed, [16])
                finally:
                    harness.close()

    def test_first_contact_reveals_boot_and_leg_but_neighbouring_frames_keep_native_mask(self):
        from tools.audit_temple_routes import Harness, press

        harness = Harness(10, draw=True, peaceful=False)
        scene = harness.scene
        scene.audio = None
        changed = []
        try:
            scene.jump_to_room(13, 1, 145, 1)
            press(harness, 'up', True)
            press(harness, 'R', True)
            for tick in range(23):
                harness.tick()
                if tick == 2:
                    press(harness, 'up', False)
                if tick == 9:
                    press(harness, 'R', False)
                state = replace(scene.sequence_state)
                motion = deepcopy(scene.terrain_motion)
                loose = deepcopy(scene.game.caverns.loose)
                scene.render()
                fixed = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                with patch('pop2.scene_prototype.loose_contact_floor_cell', return_value=None):
                    scene.render()
                    native = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                self.assertEqual(scene.sequence_state, state)
                self.assertEqual(scene.terrain_motion, motion)
                self.assertEqual(scene.game.caverns.loose, loose)
                delta = ImageChops.difference(fixed, native)
                if tick != 16:
                    self.assertIsNone(delta.getbbox(), f'Unrelated frame {tick} changed')
                    continue
                self.assertEqual((state.action, state.current_y, motion.row), (106, 6, 2))
                self.assertIsNotNone(delta.getbbox(), 'First-contact leg is still hidden')
                # All revealed pixels must come from the actual actor, and
                # the entire leg/boot must match drawing without floor paint.
                with patch.object(CavernRoom, 'draw_actor_floor_foreground',
                                  lambda art, frame, *_args: frame):
                    scene.render()
                    actor = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                self.assertIsNone(ImageChops.difference(fixed, actor).getbbox())
                mask = scene.room_cache[13].foreground.getchannel('A')
                for channel in delta.split():
                    self.assertIsNone(ImageChops.multiply(channel, mask).getbbox(),
                                      'Statue/plinth foreground changed')
                changed.append(tick)
            self.assertEqual(changed, [16])
        finally:
            harness.close()

    def test_real_short_jump_keeps_slab_at_contact_and_guard_waits_for_head_crossing(self):
        from tools.audit_temple_routes import Harness, press
        from pop2.caverns import cavern_room

        harness = Harness(10, draw=True, peaceful=False)
        scene = harness.scene
        scene.audio = None
        try:
            scene.jump_to_room(13, 1, 120, 1)
            # Actual key events select the directional short jump, then its
            # SEQS18 fall. Start/keys are supplied, not recovered video input.
            press(harness, 'up', True)
            press(harness, 'R', True)
            scenery = cavern_room(13, level_number=10).flattened().convert('RGB')
            observed = {}
            for tick in range(23):
                harness.tick()
                if tick == 2:
                    press(harness, 'up', False)
                if tick == 9:
                    press(harness, 'R', False)
                blocks = scene.game.caverns.loose.falling
                if tick == 16:
                    self.assertEqual((scene.sequence_state.action, scene.sequence_state.current_y), (106, 6))
                    self.assertFalse(blocks)
                if tick == 17:
                    block, = blocks
                    self.assertEqual((block.room, block.y, block.mob_type, block.size),
                                     (13, 365, 3, (91, 31)))
                    self.assertNotIn((12, 5), scene.game.caverns.loose.tiles)
                    scene.render()
                    drawn = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                    # Original slab still masks the trousers at the bottom
                    # border; the old cave-origin slab was already18px lower.
                    box = (285, 345, 301, 360)
                    # Native dynamic images use an inclusive bottom, one
                    # raster row below the same static floor SHAP.
                    source = (box[0], box[1] - 1, box[2], box[3] - 1)
                    self.assertIsNone(ImageChops.difference(drawn.crop(box), scenery.crop(source)).getbbox())
                    room = scene.room_cache[13]
                    self.assertFalse(room.floor_redraw.get((6, 2)))
                    # The slab must mask the trousers while remaining behind
                    # the statue's stationary plinth in the adjacent cell.
                    box = (306, 334, 345, 365)
                    mask = room.foreground.crop(box).getchannel('A')
                    difference = ImageChops.difference(drawn.crop(box), scenery.crop(box))
                    self.assertIsNotNone(mask.getbbox())
                    for channel in difference.split():
                        self.assertIsNone(ImageChops.multiply(channel, mask).getbbox())
                if tick in (18, 19, 20, 21):
                    observed[tick] = (blocks[0].y, blocks[0].row)
                if tick == 20:
                    guard, = scene.combat.active_guards()
                    self.assertEqual(guard.life, 4, 'slabY165 has not crossed the native head plane169')
                if tick == 21:
                    guard, = scene.combat.active_guards()
                    self.assertEqual((guard.life, guard.state.source_sequence_id), (0, 22))
                if tick == 22:
                    self.assertFalse(blocks)
                    self.assertEqual(scene.level_map.tile(12, 5, 1).kind, 14)
            self.assertEqual(observed, {18: (47, 0), 19: (102, 0), 20: (165, 1), 21: (228, 1)})
        finally:
            harness.close()

    def test_detached_slab_stays_behind_statue_for_overlapping_fall_positions(self):
        from tools.audit_temple_routes import Harness, press
        from pop2.caverns import cavern_room

        for x in (125, 130, 135, 140, 145):
            with self.subTest(start_x=x):
                harness = Harness(10, draw=True, peaceful=False)
                scene = harness.scene
                scene.audio = None
                try:
                    scene.jump_to_room(13, 1, x, 1)
                    press(harness, 'up', True)
                    press(harness, 'R', True)
                    for tick in range(18):
                        harness.tick()
                        if tick == 2:
                            press(harness, 'up', False)
                        if tick == 9:
                            press(harness, 'R', False)
                    block, = scene.game.caverns.loose.falling
                    self.assertEqual((block.y, block.mob_type), (365, 3))
                    self.assertEqual(scene.terrain_motion.row, 3)
                    scene.render()
                    room = scene.room_cache[13]
                    self.assertFalse(room.floor_redraw.get((6, 2)))
                    drawn = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                    scenery = cavern_room(13, level_number=10).flattened().convert('RGB')
                    box = (306, 334, 345, 365)
                    mask = room.foreground.crop(box).getchannel('A')
                    delta = ImageChops.difference(drawn.crop(box), scenery.crop(box))
                    for channel in delta.split():
                        self.assertIsNone(ImageChops.multiply(channel, mask).getbbox())
                finally:
                    harness.close()
