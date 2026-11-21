import struct
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from pop2.mac_input import StepBoundary
from pop2.paths import ASSET_DIR
from pop2.render_opening import OpeningRoom, add_ceiling_cover
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import (LevelMap, RooftopPhysics, TerrainMotion, character_column,
                         floor_y, floor_contact_x)


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level 5 artwork required')
class RoomNineCeilingMaskTests(unittest.TestCase):
    def test_short_jump_hides_only_the_hand_pixels_behind_the_rock(self):
        from PIL import ImageChops

        from tools.audit_temple_routes import Harness, press

        harness = Harness(5, draw=True)
        scene = harness.scene
        scene.audio = None
        scene.cave_ambience_enabled = False
        scene.present_viewport = lambda: None
        try:
            for facing, x, expected in ((0, 69, [(78, 5)]), (1, 62, [(79, 59)])):
                with self.subTest(facing=facing):
                    scene.load_level(5)
                    scene.jump_to_room(8, row=1, x=x, facing=facing, redraw=False)
                    loose = scene.game.caverns.loose
                    changed = []
                    poses = []
                    with patch.object(type(loose), 'shake_row', autospec=True,
                                      side_effect=type(loose).shake_row) as shake:
                        press(harness, 'up', True)
                        for tick in range(18):
                            harness.tick()
                            if tick == 1:
                                press(harness, 'up', False)
                            state = scene.sequence_state
                            pose = state.action
                            if state.source_sequence_id == 14:
                                poses.append(pose)
                            if pose == 79:
                                self.assertEqual(state.sound_events, [20])
                                self.assertEqual([call.args[2:4] for call in shake.call_args_list], [(8, 0)])
                            snapshot = replace(state)
                            fixed = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                            with patch.object(OpeningRoom, 'short_jump_ceiling', return_value=None):
                                scene.render()
                                ordinary = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                            self.assertEqual(state, snapshot)
                            difference = ImageChops.difference(ordinary, fixed)
                            region = difference.getbbox()
                            if region is not None:
                                scenery = scene.room_cache[8].flattened().convert('RGB')
                                left, top, right, bottom = region
                                pixels = 0
                                for py in range(top, bottom):
                                    for px in range(left, right):
                                        point = (px, py)
                                        if difference.getpixel(point) != (0, 0, 0):
                                            self.assertEqual(fixed.getpixel(point), scenery.getpixel(point))
                                            pixels += 1
                                changed.append((pose, pixels))
                        self.assertEqual(poses, list(range(68, 80)))
                        self.assertEqual(changed, expected)
                        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action), (8, 1, 15))
                        scene.clear_keys(None)
        finally:
            harness.close()


class CampaignCeilingMaskTests(unittest.TestCase):
    def test_cover_keeps_alpha_gaps_and_applies_to_the_princes_short_jump_only(self):
        from PIL import Image

        background = Image.new('RGBA', (510, 365))
        ordinary = Image.new('L', background.size)
        alpha = Image.new('L', (3, 4), 255)
        alpha.putpixel((1, 2), 0)
        covers = {}
        add_ceiling_cover(covers, 1, alpha, 51, 122)
        room = OpeningRoom(background, background, {0: ordinary, 1: ordinary},
                           (), (), 0, 3, ceiling_covers=covers)
        state = SequenceState(14, actor_type=0, selected_sequence_id=14)
        mask = room.actor_mask(1, state=state)
        self.assertEqual(mask.getbbox(), (51, 122, 54, 125))
        self.assertEqual(mask.getpixel((52, 124)), 0)
        self.assertIsNone(ordinary.getbbox())
        self.assertIsNone(room.actor_mask(0, state=state).getbbox())
        self.assertIsNone(room.actor_mask(1, state=replace(state, actor_type=2)).getbbox())
        self.assertIsNone(room.actor_mask(1, state=replace(state, selected_sequence_id=28)).getbbox())

    def test_short_jump_uses_the_overhead_contour_in_each_scenery_family(self):
        from PIL import ImageChops

        from tools.audit_temple_routes import Harness, press

        cases = (
            # The rooftop's existing front beam fills its contour already.
            (1, 'Rooftops.rsrc', 21, 1, 292, {}),
            (2, 'Desert.rsrc', 1, 1, 39, {78: 12, 79: 108}),
            (3, 'caverns_entry.json', 16, 1, 60, {79: 49}),
            (4, 'caverns_level4.json', 7, 1, 162, {79: 73}),
            (5, 'caverns_level5.json', 14, 1, 213, {79: 47}),
            (6, 'ruins_level6.json', 8, 1, 61, {79: 66}),
            (10, 'temple_level10.json', 7, 1, 163, {79: 56}),
            (14, 'final_level14.json', 6, 1, 179, {78: 15, 79: 268}),
            (14, 'final_level14.json', 6, 2, 214, {78: 15, 79: 262}),
        )
        if not all((ASSET_DIR / name).is_file() for _, name, *_ in cases):
            self.skipTest('Imported campaign scenery required')

        for level, _, native_room, row, x, expected in cases:
            with self.subTest(level=level, room=native_room, row=row):
                harness = Harness(level, draw=True)
                scene = harness.scene
                scene.audio = None
                scene.cave_ambience_enabled = False
                scene.present_viewport = lambda: None
                try:
                    scene.jump_to_room(native_room - 1, row=row, x=x, facing=1, redraw=False)
                    press(harness, 'up', True)
                    poses, changed = [], {}
                    for tick in range(12):
                        harness.tick()
                        if tick == 1:
                            press(harness, 'up', False)
                        state = scene.sequence_state
                        self.assertEqual(state.source_sequence_id, 14)
                        poses.append(state.action)
                        fixed = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                        with patch.object(OpeningRoom, 'short_jump_ceiling', return_value=None):
                            scene.render()
                        ordinary = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                        difference = ImageChops.difference(fixed, ordinary)
                        region = difference.getbbox()
                        if region is not None:
                            self.assertLessEqual(region[3], row * 120 + 5)
                            changed[state.action] = sum(count for count, rgb in
                                                        difference.crop(region).getcolors(510 * 365) if any(rgb))
                    self.assertEqual(poses, list(range(68, 80)))
                    self.assertEqual(changed, expected)
                finally:
                    harness.close()


class VerticalJumpTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        struct.pack_into('>H', self.level, 0x2198, 1)
        struct.pack_into('>H', self.level, 0x2084, 2)
        self.terrain = LevelMap(self.level)
        self.state = SequenceState(2, action=15, target_x=405, facing=1, actor_type=0)
        self.record = SimpleNamespace(offset_x=0, aux=0x40)

    def choose(self, room=0, row=0, boundary=StepBoundary(42, 2)):
        with patch.object(self.terrain, 'step_boundary', return_value=boundary):
            return self.terrain.vertical_jump(room, row, self.state, self.record, (0, 0, 0, 0))

    def put_tile(self, room, column, row, kind):
        struct.pack_into('>H', self.level, room * 60 + (row * 10 + column) * 2, kind)

    def test_solid_ceiling_uses_the_original_low_jump_in_both_facings(self):
        for facing in (0, 1):
            self.state.facing = facing
            for kind in (1, 2, 4, 10, 11, 19, 20):
                self.put_tile(1, 7, 2, kind)
                with self.subTest(facing=facing, kind=kind):
                    self.assertEqual(self.choose(), (14, 0))

    def test_native_space_kinds_keep_the_normal_vertical_jump(self):
        for kind in (0, 9, 27, 47, 49):
            self.put_tile(1, 7, 2, kind)
            self.assertEqual(self.choose(), (28, 0))

    def test_back_ledge_high_jump_uses_native_alignment_in_both_facings(self):
        for facing, x, column, offset in ((0, 149, 2, 17), (1, 253, 4, -17)):
            self.level[:0x780] = bytes(0x780)
            self.state.target_x, self.state.facing = x, facing
            self.put_tile(0, column, 1, 34)
            self.assertIsNone(self.terrain.upper_ledge(0, 2, self.state, self.record))
            self.assertEqual(self.terrain.back_ledge_jump(0, 2, self.state, self.record), (16, offset))
            self.assertEqual(self.state.target_x, x)
            self.state.target_x += 1 if facing else -1
            self.assertIsNone(self.terrain.back_ledge_jump(0, 2, self.state, self.record))

    def test_temple_ledges_refuse_only_a_space_marked_0x80(self):
        # IsLedge 4:3f58-3f70: in environment 2 bit 0x80 of the space (an open
        # trap door) refuses the ledge. Ordinary spaces keep every ledge, or
        # level 11 cannot climb through its fallen floor in room 10.
        struct.pack_into('>H', self.level, 0x2186, 2)
        self.level[:0x780] = bytes(0x780)
        self.state.target_x, self.state.facing = 253, 1
        self.put_tile(0, 4, 1, 34)
        self.assertEqual(self.terrain.back_ledge_jump(0, 2, self.state, self.record), (16, -17))
        struct.pack_into('>H', self.level, 0x780 + (10 + 3) * 4, 0x81)
        self.assertIsNone(self.terrain.back_ledge_jump(0, 2, self.state, self.record))

    def test_the_forward_ledge_shares_the_refusals(self):
        struct.pack_into('>H', self.level, 0x2186, 2)
        self.level[:0x780] = bytes(0x780)
        self.state.target_x, self.state.facing = 253, 1
        self.put_tile(0, 5, 1, 34)
        self.assertIsNotNone(self.terrain.upper_ledge(0, 2, self.state, self.record))
        struct.pack_into('>H', self.level, 0x780 + (10 + 4) * 4, 0x81)
        self.assertIsNone(self.terrain.upper_ledge(0, 2, self.state, self.record))
        struct.pack_into('>H', self.level, 0x780 + (10 + 4) * 4, 0)
        self.put_tile(0, 5, 1, 11)
        struct.pack_into('>H', self.level, 0x780 + (10 + 5) * 4, 3)
        self.assertIsNone(self.terrain.upper_ledge(0, 2, self.state, self.record))

    def test_a_sliding_rock_within_51_pixels_refuses_the_ledges(self):
        # DoJumpUp 6:162c-165c.
        from pop2.coordinates import native_x

        struct.pack_into('>H', self.level, 0x2186, 2)
        self.level[:0x780] = bytes(0x780)
        self.state.target_x, self.state.facing = 253, 1
        self.put_tile(0, 5, 1, 34)
        from pop2.cavern_state import CavernState

        self.terrain.caverns = caverns = CavernState()
        caverns.rocks = SimpleNamespace(edge=lambda room, row: native_x(253) + 51)
        self.assertIsNone(self.terrain.upper_ledge(0, 2, self.state, self.record))
        caverns.rocks = SimpleNamespace(edge=lambda room, row: native_x(253) + 52)
        self.assertIsNotNone(self.terrain.upper_ledge(0, 2, self.state, self.record))

    def test_supported_back_step_uses_the_forward_grab_sequence(self):
        for facing, x, column, offset in ((0, 149, 2, 48), (1, 253, 4, -48)):
            self.level[:0x780] = bytes(0x780)
            self.state.target_x, self.state.facing = x, facing
            self.put_tile(0, column, 1, 34)
            self.put_tile(0, column + (1 if not facing else -1), 2, 1)
            self.assertEqual(self.terrain.back_ledge_jump(0, 2, self.state, self.record), (24, offset))

    def test_back_ledge_requires_open_space_and_a_still_usable_floor(self):
        self.state.target_x, self.state.facing = 149, 0
        self.put_tile(0, 2, 1, 34)
        self.put_tile(0, 3, 1, 20)
        self.assertIsNone(self.terrain.back_ledge_jump(0, 2, self.state, self.record))
        self.put_tile(0, 3, 1, 0)
        for kind in (0, 20, 2, 7, 25, 43):
            self.put_tile(0, 2, 1, kind)
            self.assertIsNone(self.terrain.back_ledge_jump(0, 2, self.state, self.record))
        self.put_tile(0, 2, 1, 11)
        fg = 0x780 + (10 + 2) * 4
        struct.pack_into('>H', self.level, fg, 1)
        self.assertIsNone(self.terrain.back_ledge_jump(0, 2, self.state, self.record))
        struct.pack_into('>H', self.level, fg, 0)
        self.assertEqual(self.terrain.back_ledge_jump(0, 2, self.state, self.record), (16, 17))

    def test_ceiling_probe_uses_the_eight_pixel_forward_foot_position(self):
        self.state.target_x = 376
        self.put_tile(1, 6, 2, 0)
        self.put_tile(1, 7, 2, 20)
        self.assertEqual(character_column(self.state.target_x), 6)
        self.assertEqual(self.choose(), (14, 0))
        self.state.facing = 0
        self.put_tile(1, 6, 2, 20)
        self.put_tile(1, 7, 2, 0)
        self.state.target_x = 382
        self.assertEqual(character_column(self.state.target_x), 7)
        self.assertEqual(self.choose(), (14, 0))

    def test_close_barrier_correction_precedes_the_ceiling_probe(self):
        for facing, expected in ((1, -7), (0, 7)):
            self.state.facing = facing
            self.assertEqual(self.choose(boundary=StepBoundary(3, 1)), (28, expected))
            self.assertEqual(self.choose(boundary=StepBoundary(3, 2)), (28, 0))
            self.assertEqual(self.choose(boundary=StepBoundary(6, 1)), (28, 0))

    def test_rooftop_boat_exception_is_retained(self):
        struct.pack_into('>H', self.level, 0x2186, 5)
        self.put_tile(14, 7, 0, 20)
        self.assertEqual(self.choose(room=14, row=1), (28, 0))
        self.put_tile(13, 7, 0, 20)
        self.assertEqual(self.choose(room=13, row=1), (14, 0))

    def test_temple_exceptions_use_the_cached_column_before_the_forward_probe(self):
        struct.pack_into('>H', self.level, 0x2186, 6)
        for room in (6, 7):
            for column in range(10):
                self.put_tile(room, column, 1, 20)
        for room, column, expected in ((6, 2, 14), (6, 3, 28), (6, 6, 14),
                                      (7, 2, 28), (7, 6, 14)):
            self.state.target_x = (column + 5) * 51 - 182
            self.assertEqual(character_column(self.state.target_x), column)
            self.assertEqual(character_column(self.state.target_x + 8), column + 1)
            self.assertEqual(self.choose(room=room, row=2), (expected, 0))

    def test_barrier_bypass_uses_selected_sequence_not_the_pose_or_linked_sequence(self):
        physics = RooftopPhysics(self.terrain)
        for facing in (0, 1):
            for selected in (14, 28, 69, 70, 71, 77, 78, 79, 81):
                for action in (70, 71, 78, 79, 81):
                    state = SequenceState(14, action=action, animation_state=1,
                                          target_x=130, facing=facing, selected_sequence_id=selected)
                    with self.subTest(facing=facing, selected=selected, action=action):
                        with patch.object(self.terrain, 'wall_correction', return_value=130) as check:
                            physics.advance(TerrainMotion(0, 1), SequenceRuntime({}, state),
                                            131, (105, 102, 134, 191), frame_flags=0)
                        self.assertEqual(check.called, selected not in (70, 78))

    def test_landing_edge_reserve_matches_native_threshold_in_both_facings(self):
        for facing in (0, 1):
            self.state.facing = facing
            self.state.actor_type = 0
            direction = 1 if facing else -1
            for distance in (0, 1, 17, 30, 31, 50):
                self.state.target_x = 430 - distance if facing else 380 + distance
                column = character_column(self.state.target_x)
                self.put_tile(0, column, 1, 1)
                for kind in (0, 9, 11, 15, 26, 12, 13, 23, 24, 1, 20, 6, 34):
                    self.put_tile(0, column + direction, 1, kind)
                    expected = ((distance - 32) * direction if distance <= 30
                                and kind in (0, 9, 11, 15, 26, 12, 13, 23, 24) else 0)
                    with self.subTest(facing=facing, distance=distance, kind=kind):
                        self.assertEqual(self.terrain.landing_offset(
                            0, 1, self.state, self.record), expected)
                        crouch_offset = min(0, distance - 20) * direction if kind in (0, 9) else expected
                        self.assertEqual(self.terrain.landing_offset(
                            0, 1, self.state, self.record, crouch_drop=True), crouch_offset)

    def test_landing_alignment_preserves_native_actor_and_special_floor_exclusions(self):
        self.state.target_x = 420
        column = character_column(420)
        self.put_tile(0, column + 1, 1, 0)
        for kind, actor in ((1, 0), (23, 0), (24, 0), (1, 7), (1, 8)):
            self.state.actor_type = actor
            self.put_tile(0, column, 1, kind)
            self.assertEqual(self.terrain.landing_offset(0, 1, self.state, self.record),
                             -22 if kind == 1 and actor == 0 else 0)

    def test_player_down_cut_waits_for_440_then_rebases_by_360(self):
        struct.pack_into('>H', self.level, 0x2086, 2)
        for y in (346, 365, 439, 440, 448, 466):
            state = SequenceState(12, target_x=200, current_y=y-floor_y(3), actor_type=0)
            motion = TerrainMotion(0, 3, falling=True)
            self.assertEqual(RooftopPhysics(self.terrain).cut_down(motion, state), y >= 440)
            self.assertEqual(motion.room, int(y >= 440))
            self.assertEqual(floor_y(motion.row) + state.current_y,
                             y - 360 if y >= 440 else y)

    def test_player_up_cut_uses_actor_height_and_rebases_by_360(self):
        for y in (-120, -14, 0, 18, 19, 20, 106):
            state = SequenceState(10, current_y=y-floor_y(0), actor_type=0)
            motion = TerrainMotion(0, 0)
            self.assertEqual(RooftopPhysics(self.terrain).cut_up(motion, state), y < 19)
            self.assertEqual(motion.room, int(y < 19))
            self.assertEqual(floor_y(motion.row) + state.current_y,
                             y + 360 if y < 19 else y)
        self.assertEqual(motion.row, 0)

    def test_player_up_cut_retains_native_mode_and_selected_sequence_vetoes(self):
        for mode in range(10):
            for selected in (10, 70):
                state = SequenceState(235, action=70, animation_state=mode,
                                      selected_sequence_id=selected,
                                      current_y=-14-floor_y(-1), actor_type=0)
                motion = TerrainMotion(0, -1)
                allowed = mode not in (3, 4, 5) and selected != 70
                with self.subTest(mode=mode, selected=selected):
                    self.assertEqual(RooftopPhysics(self.terrain).cut_up(motion, state), allowed)
                    self.assertEqual(motion.room, int(allowed))
                    self.assertEqual((motion.row, state.current_y),
                                     (2, 0) if allowed else (-1, 0))

    def test_player_up_cut_preserves_level_five_exception_and_missing_links(self):
        struct.pack_into('>H', self.level, 0x218a, 5)
        struct.pack_into('>H', self.level, 0x2094, 2)
        for room, allowed in ((0, True), (1, False), (2, False)):
            state = SequenceState(10, current_y=-14-floor_y(-1), actor_type=0)
            motion = TerrainMotion(room, -1)
            self.assertEqual(RooftopPhysics(self.terrain).cut_up(motion, state), allowed)
            self.assertEqual(motion.room, 1 if allowed else room)
        struct.pack_into('>H', self.level, 0x218a, 3)
        self.assertTrue(RooftopPhysics(self.terrain).cut_up(motion, state))
        self.assertEqual((motion.room, motion.row, state.current_y), (1, 2, 0))

    def test_protected_climb_can_cut_without_running_free_fall_physics(self):
        struct.pack_into('>H', self.level, 0x2086, 2)
        for y, expected_row, expected_y in ((-14, 2, 0), (440, 0, -26)):
            state = SequenceState(10, action=135, target_x=123, current_y=y-floor_y(-1),
                                  vertical_velocity=8, actor_type=0)
            motion = TerrainMotion(0, -1)
            with patch.object(self.terrain, 'wall_correction') as wall:
                events = RooftopPhysics(self.terrain).advance(
                    motion, SequenceRuntime({}, state), 123, (100, -80, 130, 10),
                    protected=True, frame_flags=0)
            self.assertEqual([event.kind for event in events], ['room'])
            self.assertEqual((motion.room, motion.row, state.current_y),
                             (1, expected_row, expected_y))
            self.assertEqual((state.target_x, state.vertical_velocity), (123, 8))
            self.assertFalse(motion.falling)
            wall.assert_not_called()

    def test_protected_camera_cut_requires_live_player_and_enabled_cuts(self):
        for actor, dead, enabled in ((2, False, True), (0, True, True), (0, False, False)):
            state = SequenceState(10, action=135, current_y=0, actor_type=actor)
            motion = TerrainMotion(0, -1, dead=dead)
            events = RooftopPhysics(self.terrain).advance(
                motion, SequenceRuntime({}, state), 123, (100, -80, 130, 10),
                protected=True, frame_flags=0, cut_enabled=enabled)
            self.assertEqual(events, ())
            self.assertEqual((motion.room, motion.row, state.current_y), (0, -1, 0))

    def test_body_overlap_with_ceiling_is_not_a_physical_row_wall(self):
        self.put_tile(0, 1, 0, 20)
        bounds, old = (104, 102, 133, 191), (107, 121, 130, 213)
        self.assertEqual(self.terrain.wall_correction(
            0, 114, 114, bounds, old, 0, physical_row=1), 114)
        self.assertGreater(self.terrain.wall_correction(0, 114, 114, bounds, old, 0), 114)


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class OriginalCeilingTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.load_level(3)
        self.scene.peaceful = True

    def tick(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.tick(self)

    def test_entrance_ceiling_uses_short_jump_and_returns_to_its_floor(self):
        scene = self.scene
        scene.jump_to_room(0, row=0, x=347, facing=1)
        scene.in_animation_tick = True
        scene.start_jump()
        self.assertEqual(scene.sequence_state.sequence_id, 14)
        frames = []
        for _ in range(30):
            self.tick()
            frames.append((scene.action, scene.sequence_state.current_y))
            if scene.sequence_state.sequence_id == 2:
                break
        self.assertIn((79, 0), frames)
        self.assertEqual(sum(action == 79 for action, _ in frames), 1)
        self.assertNotIn((79, -11), frames)
        self.assertEqual((scene.sequence_state.sequence_id, scene.terrain_motion.row,
                          scene.sequence_state.current_y, scene.player_x), (2, 0, 0, 363))

    def test_blocked_jump_repeats_under_another_ceiling_without_room_specific_logic(self):
        scene = self.scene
        for room, row, x in ((0, 0, 347), (3, 2, 338), (4, 1, 185)):
            scene.jump_to_room(room, row=row, x=x, facing=1)
            self.assertIsNone(scene.level_map.upper_ledge(room, row, scene.sequence_state, scene.frames[15]))
            scene.in_animation_tick = True
            scene.start_jump()
            self.assertEqual(scene.sequence_state.sequence_id, 14)

    def test_left_ceiling_jump_is_not_replaced_by_a_false_ground_bump(self):
        from PIL import ImageChops

        scene = self.scene
        scene.jump_to_room(0, row=1, x=127, facing=0)
        floor = scene.native_viewport.convert('RGB').copy()
        scene.in_animation_tick = True
        scene.start_jump()
        self.assertEqual(scene.sequence_state.sequence_id, 14)
        for _ in range(12):
            self.tick()

        self.assertEqual(scene.action, 78)
        self.tick()
        self.assertEqual((scene.action, scene.sequence_state.sequence_id,
                          scene.player_x, scene.terrain_motion.row), (79, 14, 114, 1))
        self.assertFalse(scene.terrain_motion.falling)
        self.tick()
        self.assertEqual(scene.terrain_motion.row, 2)
        self.assertNotEqual(scene.sequence_state.source_sequence_id, 45)
        self.assertTrue(scene.terrain_motion.falling)
        self.assertLess(scene.sequence_state.current_y, 0)
        for _ in range(3):
            # The former ground-bump legs crossed this solid floor strip.
            region = (140, 227, 175, 241)
            self.assertIsNone(ImageChops.difference(
                scene.native_viewport.convert('RGB').crop(region),
                floor.crop(region)).getbbox())
            self.tick()

    def test_entrance_drop_lands_and_finishes_recovery_on_the_lower_platform(self):
        scene = self.scene
        scene.jump_to_room(0, row=1, x=234, facing=1)
        scene.held_directions.append(1)
        scene.start_running(1)
        landed = False
        for _ in range(45):
            self.tick()
            if scene.terrain_motion.falling:
                scene.held_directions.clear()
            elif scene.terrain_motion.row == 2:
                landed = True
            self.assertEqual(scene.room_id, 0)
        self.assertTrue(landed)
        self.assertEqual((scene.action, scene.terrain_motion.row,
                          scene.sequence_state.current_y, scene.player_x), (15, 2, 0, 379))
        self.assertFalse(scene.terrain_motion.falling)
        foot = floor_contact_x(scene.player_x, 1, scene.frames[15])
        self.assertNotEqual(scene.level_map.tile(0, character_column(foot), 2).kind, 0)

    def test_player_drop_cuts_below_entrance_at_the_native_threshold(self):
        scene = self.scene
        scene.jump_to_room(0, row=2, x=410, facing=1)
        scene.sequence_state.select(12)
        scene.sequence_runtime.next_frame()
        scene.terrain_motion.row = 3
        scene.terrain_motion.falling = True
        scene.sequence_state.current_y = 430 - floor_y(3)
        self.tick()
        self.assertEqual(scene.room_id, 0)
        self.assertEqual(floor_y(scene.terrain_motion.row) + scene.sequence_state.current_y, 436)
        self.tick()
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (3, 0))
        self.assertEqual(floor_y(scene.terrain_motion.row) + scene.sequence_state.current_y, 88)
        self.assertTrue(scene.terrain_motion.falling)

    def test_upper_room_climb_cuts_during_pose_141_and_finishes_on_its_floor(self):
        scene = self.scene
        # The recorded route has already collapsed this loose floor above the grab.
        scene.game.caverns.loose.tiles[(8, 22)] = (0, 0)
        scene.jump_to_room(2, row=0, x=145, facing=0)
        scene.in_animation_tick = True
        scene.shift_held = scene.up_held = True
        scene.start_jump()
        self.assertEqual(scene.sequence_state.sequence_id, 24)
        for _ in range(21):
            self.tick()
            self.assertEqual(scene.room_id, 2)
        self.assertEqual(scene.action, 140)
        self.assertTrue(scene.ledge_climbing)
        self.tick()
        self.assertEqual((scene.action, scene.room_id, scene.terrain_motion.row,
                          scene.sequence_state.current_y, scene.player_x), (141, 8, 2, 0, 100))
        self.assertTrue(scene.ledge_climbing)
        scene.up_held = False
        for _ in range(14):
            self.tick()
            self.assertEqual(scene.room_id, 8)
        self.assertEqual((scene.action, scene.terrain_motion.row,
                          scene.sequence_state.current_y, scene.player_x), (15, 2, 0, 112))
        self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.ledge_climbing)
        self.assertFalse(scene.native_ledge)
