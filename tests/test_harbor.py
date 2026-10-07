import struct
import unittest
from dataclasses import replace
from unittest.mock import patch

from PIL import Image, ImageChops, ImageOps

from pop2.harbor import Harbor, WaterEntry
from pop2.combat import Fighter
from pop2.render_opening import (
    CLIMB_FOREGROUND_RECTS, build_opening_room, draw_harbor, rooftop_scene_data, load_resource_file,
)
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import TerrainMotion, floor_y
import tests.test_terrain as terrain_tests


class HarborRulesTests(unittest.TestCase):
    def test_right_exit_uses_the_native_room_and_strict_x_limit(self):
        state = SequenceState(201, actor_type=0, level_kind=5, target_x=611)
        self.assertFalse(Harbor.right_exit_is_fatal(14, state))
        state.target_x += 1
        self.assertTrue(Harbor.right_exit_is_fatal(14, state))
        self.assertFalse(Harbor.right_exit_is_fatal(15, state))
        state.level_kind = 1
        self.assertFalse(Harbor.right_exit_is_fatal(14, state))

    def test_dock_caps_and_planks_use_the_original_draw_pass_and_offsets(self):
        level_map, shapes, pieces = rooftop_scene_data()
        for room_id in (15, 18):
            room = build_opening_room(False, room_id)
            for column in range(10):
                tile = level_map.tile(room_id, column, 1)
                if tile.kind != 1:
                    continue
                cell_pieces = [p for p in room.pieces if (p.row, p.column) == (1, column)]
                expected = [(3612, 0, pieces[1][6], None, True)]
                if level_map.tile(room_id, column - 1, 1).kind in (0, 9, 27, 47, 49):
                    expected.append((3612, 0, pieces[1][6], 22, False))
                if tile.foreground & 15:
                    expected.append((3613, pieces[1][8], pieces[1][9], None, False))
                    cap = shapes[3614]
                    x, y = column * 51 + pieces[1][2], 245 + pieces[1][3] - cap.height
                    for cy in range(cap.height):
                        for cx in range(cap.width):
                            if cap.getpixel((cx, cy))[3] == 255 and 0 <= x + cx < 510:
                                self.assertEqual(room.background.getpixel((x + cx, y + cy)),
                                                 cap.getpixel((cx, cy)))
                self.assertEqual(len(cell_pieces), len(expected))
                for piece, (shape_id, dx, dy, width, redraw) in zip(cell_pieces, expected):
                    sprite = shapes[shape_id]
                    if width is not None:
                        sprite = sprite.crop((0, 0, width, sprite.height))
                    self.assertEqual((piece.x, piece.y),
                                     (column * 51 + dx, 245 + dy - sprite.height))
                    self.assertEqual(piece.alpha.tobytes(), sprite.getchannel('A').tobytes())
                    self.assertEqual(piece.floor_redraw, redraw)

    def test_exposed_dock_lip_is_foreground_but_does_not_cover_the_walkable_surface(self):
        room = build_opening_room(False, 18)
        lip = next(p for p in room.pieces if (p.row, p.column, p.alpha.width) == (1, 5, 22))
        self.assertFalse(lip.floor_redraw)
        self.assertEqual((lip.x, lip.y), (255, 215))
        self.assertIsNone(lip.alpha.crop((0, 0, 22, 227 - lip.y)).getbbox())
        self.assertIsNotNone(lip.alpha.crop((0, 227 - lip.y, 22, lip.alpha.height)).getbbox())

    def test_dock_plank_redraw_uses_only_the_native_climb_rectangle(self):
        for room_id, column in ((15, 3), (18, 7)):
            room = build_opening_room(False, room_id)
            plank = next(p for p in room.pieces if (p.row, p.column) == (1, column))
            isolated = replace(room, pieces=(plank,), ledges=())
            for action in range(135, 149):
                with self.subTest(room=room_id, action=action):
                    row = 2 if action < 141 else 1
                    state = SequenceState(10, action=action, animation_state=6)
                    actual = isolated.actor_mask(row, state=state)
                    expected = Image.new('L', actual.size)
                    if action < 145:
                        top, left, bottom, right = CLIMB_FOREGROUND_RECTS[action - 135]
                        rect = (column * 51 + left, 120 + top,
                                column * 51 + min(right, 22), 120 + bottom)
                        alpha = plank.alpha.crop((rect[0] - plank.x, rect[1] - plank.y,
                                                   rect[2] - plank.x, rect[3] - plank.y))
                        expected.paste(alpha, rect[:2])
                    self.assertEqual(actual.tobytes(), expected.tobytes())
            self.assertIsNone(room.actor_mask(1).crop((column * 51, 215, column * 51 + 22, 227)).getbbox())

    def test_ship_stays_at_berth_before_entering_final_room(self):
        harbor = Harbor()
        for room in (3, 11, 14, 15):
            harbor.enter_room(room, 39)
            harbor.advance()
        self.assertEqual((harbor.ship_frame, harbor.ship_x), (0, 0))

    def test_ship_native_trigger_speed_and_stop(self):
        harbor = Harbor()
        harbor.enter_room(18, 35)
        self.assertEqual(harbor.ship_frame, 6)
        harbor.advance()
        self.assertEqual((harbor.ship_frame, harbor.ship_x), (7, -14))
        for _ in range(200):
            harbor.advance()
        self.assertEqual(harbor.ship_frame, 99)
        self.assertFalse(harbor.ship_active)
        harbor.enter_room(18, 35)
        self.assertFalse(harbor.ship_active)

    def test_ship_grab_strict_native_limits(self):
        harbor = Harbor(ship_frame=32)
        self.assertTrue(harbor.can_grab_ship(18, 2, 89))
        for room, row, x in ((15, 2, 89), (18, 3, 89), (18, 2, 90)):
            self.assertFalse(harbor.can_grab_ship(room, row, x))
        harbor.ship_frame = 33
        self.assertFalse(harbor.can_grab_ship(18, 2, 89))

    def test_level_transition_opcode_yields_invisible_hold_once(self):
        runtime = SequenceRuntime({59: (119, -16, -1, 215), 215: (0, -1, 215)},
                                  SequenceState(59))
        self.assertEqual(runtime.next_frame().action, 119)
        self.assertEqual(runtime.next_frame().action, 0)
        for _ in range(20):
            self.assertEqual(runtime.next_frame().action, 0)
        self.assertEqual(runtime.state.sequence_events, [(-16, ())])

    def test_water_thresholds_exemptions_and_delay(self):
        for tumble, threshold in ((False, 327), (True, 354)):
            harbor = Harbor()
            state = SequenceState(12, target_x=100, current_y=threshold - 346 - 1,
                                  animation_state=9 if tumble else 4)
            self.assertFalse(harbor.watch_water(0, 15, 2, state))
            self.assertFalse(harbor.water)
            state.current_y += 1
            self.assertFalse(harbor.watch_water(0, 15, 2, state))
            self.assertEqual(state.sound_events, [35])
            for _ in range(7):
                harbor.advance()
                self.assertFalse(harbor.watch_water(0, 15, 2, state))
            harbor.advance()
            self.assertTrue(harbor.watch_water(0, 15, 2, state))
        for sequence in (68, 15, 59, 10):
            harbor = Harbor()
            state = SequenceState(sequence, animation_state=1, current_y=100)
            harbor.watch_water(0, 18, 2, state)
            self.assertFalse(harbor.water)

    def test_custom_quay_uses_cust_images_not_roof_tiles(self):
        room = build_opening_room(False, 14)
        _, shapes, _ = rooftop_scene_data()
        roof = load_resource_file('Rooftops.rsrc')
        custom = roof['CUST'][4350]['data']
        self.assertEqual(struct.unpack_from('>4h', custom, 30), (0, 365, 0, 0))
        expected_background = Image.new('RGBA', room.background.size, (0, 0, 0, 255))
        sprite = shapes[4351]
        expected_background.alpha_composite(sprite, (0, 365 - sprite.height))
        self.assertEqual(room.background.tobytes(), expected_background.tobytes())
        expected = Image.new('RGBA', room.foreground.size)
        sprite = shapes[4352]
        expected.paste(sprite, (6, 245 - sprite.height), sprite)
        self.assertEqual(room.foreground.tobytes(), expected.tobytes())

    def test_waves_and_ship_change_pixels_without_rebuilding_atlas(self):
        room = build_opening_room(False, 18)
        harbor = Harbor(ship_active=True)
        before = draw_harbor(room.flattened(), 18, harbor)
        harbor.advance()
        after = draw_harbor(room.flattened(), 18, harbor)
        self.assertIsNotNone(ImageChops.difference(before.convert('RGB'), after.convert('RGB')).getbbox())
        self.assertEqual(draw_harbor(room.background, 3, harbor).tobytes(), room.background.tobytes())

    def test_splash_finishes_even_after_an_actor_stops_updating(self):
        harbor = Harbor(water={0: WaterEntry(18, 200, False)})
        background = build_opening_room(False, 18).background
        before = draw_harbor(background, 18, harbor, front=True)
        for _ in range(8):
            harbor.advance()
        after = draw_harbor(background, 18, harbor, front=True)
        self.assertEqual(harbor.water[0].age, 8)
        self.assertIsNotNone(ImageChops.difference(before.convert('RGB'), after.convert('RGB')).getbbox())

    def test_foreground_waves_use_the_native_cell_clip_rectangle(self):
        level_map, shapes, pieces = rooftop_scene_data()
        harbor = Harbor(wave_frame=2)
        blank = Image.new('RGBA', (510, 365))
        actual = draw_harbor(blank, 15, harbor, front=True)
        expected = blank.copy()
        for column in (1, 7):
            tile = level_map.tile(15, column, 2)
            sprite = shapes[3617 + ((tile.foreground + 2) & 3)]
            top = 365 + pieces[46][6] - sprite.height
            expected.alpha_composite(sprite.crop((0, 344 - top, sprite.width, 365 - top)),
                                     (column * 51 + 13, 344))
        self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_player_splash_stays_behind_near_posts_through_all_six_frames(self):
        _, shapes, pieces = rooftop_scene_data()
        offsets = (5, 4, 5, 7, 1, 0)
        for room_id, column in ((15, 1), (15, 7), (18, 5)):
            room = build_opening_room(False, room_id)
            post = shapes[3615]
            x, y = column * 51 + pieces[47][8], 365 + pieces[47][9] - post.height
            baseline = draw_harbor(room.flattened(), room_id, Harbor(), front=True)
            for age, offset in enumerate(offsets):
                with self.subTest(room=room_id, column=column, age=age):
                    entry = WaterEntry(room_id, x + post.width // 2, False, age)
                    actual = draw_harbor(room.flattened(), room_id,
                                         Harbor(water={0: entry}), front=True)
                    post_area = (x, y, x + post.width, y + post.height)
                    difference = ImageChops.difference(actual.convert('RGB'),
                                                      baseline.convert('RGB')).crop(post_area)
                    self.assertIsNone(ImageChops.multiply(difference,
                                                          post.getchannel('A').convert('RGB')).getbbox())
                    splash = shapes[3628 + age]
                    splash_layer = Image.new('RGBA', actual.size)
                    splash_layer.alpha_composite(splash, (entry.x - splash.width // 2,
                                                          331 + offset - splash.height))
                    post_mask = Image.new('L', actual.size)
                    post_mask.paste(post.getchannel('A'), (x, y))
                    splash_layer.putalpha(ImageChops.subtract(splash_layer.getchannel('A'), post_mask))
                    self.assertIsNotNone(splash_layer.getbbox())
                    expected = Image.alpha_composite(baseline, splash_layer)
                    self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_player_splash_away_from_posts_keeps_the_original_pixels(self):
        _, shapes, _ = rooftop_scene_data()
        room = build_opening_room(False, 18)
        for age, offset in enumerate((5, 4, 5, 7, 1, 0)):
            baseline = draw_harbor(room.flattened(), 18, Harbor(), front=True)
            splash = shapes[3628 + age]
            expected = baseline.copy()
            expected.alpha_composite(splash, (200 - splash.width // 2,
                                               331 + offset - splash.height))
            actual = draw_harbor(room.flattened(), 18,
                                 Harbor(water={0: WaterEntry(18, 200, False, age)}), front=True)
            self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_tumble_splash_keeps_its_distinct_waterline_and_draw_order(self):
        _, shapes, _ = rooftop_scene_data()
        room = build_opening_room(False, 18)
        for age, offset in enumerate((5, 4, 5, 7, 1, 0)):
            baseline = draw_harbor(room.flattened(), 18, Harbor(), front=True)
            splash = shapes[3628 + age]
            expected = baseline.copy()
            expected.alpha_composite(splash, (280 - splash.width // 2,
                                               358 + offset - splash.height))
            actual = draw_harbor(room.flattened(), 18,
                                 Harbor(water={0: WaterEntry(18, 280, True, age)}), front=True)
            self.assertEqual(actual.tobytes(), expected.tobytes())


class HarborSceneTests(unittest.TestCase):
    setUp = terrain_tests.RooftopSceneTests.setUp

    def tick(self, count=1):
        for _ in range(count):
            self.now += self.scene.current_animation_interval_ms() / 1000
            with patch('pop2.scene_prototype.time.perf_counter', return_value=self.now):
                self.scene.advance_animation()

    def prepare(self, screen):
        self.scene.peaceful = True
        self.scene.jump_to_screen(screen)

    def test_right_exit_keeps_the_quay_visible_and_then_kills_the_player(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(14, row=1, x=420, facing=1)
        background = scene.background
        scene.horizontal_key(None, 1, True)
        left_view = False
        for _ in range(80):
            self.tick()
            self.assertEqual(scene.room_id, 14)
            self.assertIs(scene.background, background)
            left_view |= scene.player_x > 525
            if scene.terrain_motion.dead:
                break
        self.assertTrue(left_view)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertEqual(scene.combat.player.life, 0)
        self.assertEqual(scene.sequence_state.sequence_id, 71)
        self.tick(12)
        self.assertEqual(scene.room_id, 14)
        self.assertEqual(scene.action, 185)

    def test_right_exit_veto_does_not_change_other_room_links(self):
        scene = self.scene
        state = SequenceState(201, action=7, target_x=530, facing=1,
                              actor_type=0, level_kind=5)
        motion = TerrainMotion(3, 1)
        self.assertTrue(scene.physics.cut_horizontal(motion, state, (520, 160, 540, 226)))
        self.assertEqual(motion.room, 4)
        self.assertEqual(state.target_x, 20)
        for room, kind, cuts in ((14, 5, False), (14, 1, True)):
            state = SequenceState(201, action=7, target_x=530, facing=1,
                                  actor_type=0, level_kind=kind)
            motion = TerrainMotion(room, 1)
            self.assertEqual(scene.physics.cut_horizontal(motion, state, (520, 160, 540, 226)), cuts)
            self.assertEqual(motion.room, 5 if cuts else 14)

    def test_drop_from_roof_finishes_the_full_rise_beside_the_wall(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(11, row=1, x=340, facing=1)
        scene.set_key_state('shift', True)
        scene.set_key_state('down', True)
        poses, rise = [], []
        released = False
        for _ in range(90):
            if scene.action == 91 and not released:
                scene.set_key_state('shift', False)
                scene.set_key_state('down', False)
                released = True
            self.tick()
            if scene.room_id == 14 and not scene.terrain_motion.falling:
                poses.append(scene.action)
                if scene.sequence_state.sequence_id == 49:
                    rise.append(scene.action)
                if scene.action == 15:
                    break
        self.assertTrue(released)
        self.assertEqual(poses, list(range(107, 120)) + [15])
        self.assertEqual(rise, list(range(110, 120)))
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (14, 0))
        self.assertFalse(scene.terrain_motion.dead)
        self.assertFalse(scene.terrain_motion.smooth_landing)
        self.assertEqual(scene.combat.player.life, 3)
        self.assertLess(scene.player_bounds()[2], 6 * 51 + 25)
        scene.horizontal_key(None, 1, True)
        self.tick(30)
        self.assertLess(scene.player_bounds()[2], 6 * 51 + 25)
        self.assertEqual(scene.room_id, 14)

    def test_landing_recovery_elsewhere_retains_the_normal_wall_response(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(14, row=0, x=320, facing=1)
        scene.physics.select(scene.sequence_runtime, 49)
        poses = []
        for _ in range(20):
            self.tick()
            poses.append(scene.action)
        self.assertIn(50, poses)
        self.assertFalse(scene.terrain_motion.smooth_landing)

    def test_real_dock_descent_stays_behind_near_post_and_climbs_back(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(18, row=1, x=289, facing=1)
        room = scene.room_cache[18]
        post = next(p for p in room.pieces if (p.kind, p.column) == (47, 5))
        scene.set_key_state('shift', True)
        scene.set_key_state('down', True)
        hanging_poses = set()
        for _ in range(34):
            self.tick()
            if 87 <= scene.action <= 99:
                hanging_poses.add(scene.action)
                bounds = scene.player_bounds()
                mask = room.actor_mask(scene.terrain_motion.row, state=scene.sequence_state,
                                       bounds=bounds, record=scene.frames[scene.action])
                area = mask.crop((post.x, post.y, post.x + post.alpha.width,
                                  post.y + post.alpha.height))
                self.assertIsNone(ImageChops.subtract(post.alpha, area).getbbox())
        self.assertTrue({87, 91, 97}.issubset(hanging_poses))
        self.assertTrue(scene.ledge_hanging)
        scene.up_key(None)
        self.tick(25)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (18, 1))
        self.assertFalse(scene.ledge_hanging)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.terrain_motion.dead)

    def test_dock_plank_tip_stays_in_front_through_descent_hold_and_climb(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(18, row=1, x=289, facing=1)
        room = scene.room_cache[18]
        plank = next(p for p in room.pieces if (p.row, p.column) == (1, 5))
        rect = (255, 220, 277, 245)
        wood = plank.alpha.crop((rect[0] - plank.x, rect[1] - plank.y,
                                 rect[2] - plank.x, rect[3] - plank.y))
        expected = room.flattened().crop(rect).convert('RGB')
        scene.set_key_state('shift', True)
        scene.set_key_state('down', True)
        checked = {'down': set(), 'up': set()}
        for phase, ticks in (('down', 45), ('up', 25)):
            if phase == 'up':
                scene.set_key_state('down', False)
                scene.up_key(None)
            exposed_pixels = 0
            for _ in range(ticks):
                self.tick()
                if 87 <= scene.action < 100 or 135 <= scene.action < 149:
                    checked[phase].add(scene.action)
                    bounds = scene.player_bounds()
                    sprite = ImageOps.mirror(scene.player_sprite())
                    raw_actor = Image.new('L', room.background.size)
                    raw_actor.paste(sprite.getchannel('A'), bounds[:2])
                    exposed_pixels += sum(ImageChops.multiply(raw_actor.crop(rect), wood).tobytes())
                    actual = scene.native_viewport.crop((256, 220, 278, 245)).convert('RGB')
                    difference = ImageChops.multiply(ImageChops.difference(actual, expected), wood.convert('RGB'))
                    with self.subTest(phase=phase, action=scene.action):
                        self.assertIsNone(difference.getbbox())
                if phase == 'up' and scene.action == 15:
                    break
            self.assertGreater(exposed_pixels, 0)
        self.assertTrue({87, 91, 97, 136, 140, 141, 145}.issubset(checked['down']))
        self.assertTrue({135, 140, 141, 145}.issubset(checked['up']))
        self.assertEqual((scene.terrain_motion.row, scene.action), (1, 15))
        self.assertFalse(scene.ledge_hanging)
        self.assertFalse(scene.terrain_motion.falling)

    def test_far_dock_cap_is_behind_an_overlapping_player(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(18, row=1, x=330, facing=1)
        room = scene.room_cache[18]
        bounds = scene.player_bounds()
        mask = room.actor_mask(1, state=scene.sequence_state, bounds=bounds,
                               record=scene.frames[15])
        self.assertLess(bounds[0], 337)
        self.assertGreater(bounds[2], 306)
        self.assertIsNone(mask.crop((306, 185, 337, 215)).getbbox())

    def test_player_feet_remain_visible_on_the_dock_surface(self):
        scene = self.scene
        scene.peaceful = True
        for room_id, x in ((15, 220), (18, 400)):
            for facing in (0, 1):
                scene.jump_to_room(room_id, row=1, x=x, facing=facing)
                for action in (15, 1, 7, 14, 110, 119, 150):
                    with self.subTest(room=room_id, facing=facing, action=action):
                        scene.action = scene.sequence_state.action = action
                        scene.render()
                        sprite = scene.player_sprite()
                        if facing:
                            sprite = ImageOps.mirror(sprite)
                        left, top, _, _ = scene.player_bounds()
                        visible = 0
                        for sy in range(sprite.height):
                            for sx in range(sprite.width):
                                pixel = sprite.getpixel((sx, sy))
                                if pixel[3] == 255 and 215 <= top + sy <= 226:
                                    visible += 1
                                    self.assertEqual(scene.native_viewport.getpixel((left + sx + 1, top + sy)),
                                                     pixel)
                        self.assertGreater(visible, 0)

    def test_dock_near_pillar_masks_overlapping_hanging_and_climbing_poses(self):
        scene = self.scene
        for room_id, column in ((15, 1), (15, 7), (18, 5)):
            room = build_opening_room(False, room_id)
            post = next(p for p in room.pieces if (p.kind, p.column) == (47, column))
            for action, mode in ((80, 3), (87, 2), (91, 6), (135, 6), (141, 6)):
                for facing in (0, 1):
                    with self.subTest(room=room_id, action=action, facing=facing):
                        state = SequenceState(15, action=action, animation_state=mode,
                                              target_x=column * 51 + 7, facing=facing)
                        bounds = (post.x - 10, post.y - 20,
                                  post.x + post.alpha.width + 10, post.y + post.alpha.height)
                        mask = room.actor_mask(2, state=state, bounds=bounds,
                                               record=scene.frames[action])
                        area = mask.crop((post.x, post.y, post.x + post.alpha.width,
                                          post.y + post.alpha.height))
                        self.assertIsNone(ImageChops.subtract(post.alpha, area).getbbox())

    def run_to_ship(self):
        scene = self.scene
        scene.horizontal_key(None, -1, True)
        for _ in range(240):
            if scene.room_id == 18 and scene.player_x < 350 and not scene.up_held:
                scene.up_key(None)
                scene.set_key_state('shift', True)
            self.tick()
            if scene.level_complete or scene.terrain_motion.dead:
                break

    def test_route_from_last_rooftop_to_ship_completes_without_teleporting(self):
        self.prepare('7')
        seen = set()
        scene = self.scene
        scene.horizontal_key(None, -1, True)
        for _ in range(400):
            seen.add(scene.room_id)
            if scene.room_id == 18 and scene.player_x < 350 and not scene.up_held:
                scene.up_key(None)
                scene.set_key_state('shift', True)
            self.tick()
            if scene.level_complete or scene.terrain_motion.dead:
                break
        self.assertEqual(seen, {11, 14, 15, 18})
        self.assertTrue(scene.level_complete)
        self.assertFalse(scene.terrain_motion.dead)
        self.assertEqual(scene.action, 0)
        self.assertGreater(scene.combat.player.life, 0)

    def test_complete_level_route_from_window_escape_with_real_controls(self):
        scene = self.scene
        scene.peaceful = True
        self.tick(19)
        self.assertFalse(scene.opening.active)
        scene.horizontal_key(None, -1, True)
        seen, jumps = set(), set()
        climbed = False
        for _ in range(650):
            seen.add(scene.room_id)
            if scene.room_id in (2, 0, 10) and scene.room_id not in jumps:
                threshold = 345 if scene.room_id == 2 else 385
                if scene.room_id == 10:
                    threshold = 345
                if scene.player_x < threshold:
                    scene.up_key(None)
                    jumps.add(scene.room_id)
            elif (scene.room_id == 9 and not climbed and scene.player_x < 250
                  and scene.action == 15 and not scene.run_active):
                scene.horizontal_key(None, -1, False)
                scene.up_key(None)
                climbed = True
            elif scene.room_id == 18 and scene.player_x < 350 and not scene.up_held:
                scene.up_key(None)
                scene.set_key_state('shift', True)
            self.tick()
            if scene.sequence_state.sequence_id == 4 and scene.room_id in (2, 0, 10):
                scene.set_key_state('up', False)
            if scene.room_id == 9 and scene.terrain_motion.row == 0:
                scene.set_key_state('up', False)
                if -1 not in scene.held_directions:
                    scene.horizontal_key(None, -1, True)
            if scene.level_complete or scene.terrain_motion.dead:
                break
        self.assertEqual(seen, {3, 1, 2, 0, 9, 10, 11, 14, 15, 18})
        self.assertTrue(scene.level_complete,
                        (scene.room_id, scene.terrain_motion, scene.sequence_state))
        self.assertFalse(scene.terrain_motion.dead)
        self.assertGreater(scene.combat.player.life, 0)

    def test_boat_climb_follows_original_poses_and_drifts_with_ship(self):
        self.prepare('9')
        scene = self.scene
        scene.horizontal_key(None, -1, True)
        poses = []
        relative_x = []
        for _ in range(180):
            if scene.room_id == 18 and scene.player_x < 350 and not scene.up_held:
                scene.up_key(None)
                scene.set_key_state('shift', True)
            self.tick()
            if scene.sequence_state.sequence_id == 59:
                poses.append(scene.action)
                if scene.action in range(135, 141):
                    relative_x.append(scene.player_x - scene.harbor.ship_x)
            if scene.level_complete or scene.terrain_motion.dead:
                break
        self.assertEqual(poses, list(range(135, 150)) + [118, 119])
        self.assertEqual(len(set(relative_x)), 1)
        self.assertTrue(scene.level_complete)

    def test_missing_ship_grip_drowns_instead_of_completing(self):
        self.prepare('10')
        scene = self.scene
        scene.horizontal_key(None, -1, True)
        for _ in range(140):
            if scene.player_x < 350 and not scene.up_held:
                scene.up_key(None)
            self.tick()
        self.assertTrue(scene.terrain_motion.dead)
        self.assertFalse(scene.level_complete)
        self.assertEqual(scene.combat.player.life, 0)
        self.assertGreater(scene.harbor.water[0].age, 6)

    def test_expired_ship_cannot_be_caught(self):
        self.prepare('10')
        self.tick(120)
        scene = self.scene
        scene.horizontal_key(None, -1, True)
        scene.set_key_state('shift', True)
        self.tick(100)
        self.assertFalse(scene.ledge_hanging)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertFalse(scene.level_complete)

    def test_completion_stops_gameplay_but_dev_jump_and_restart_remain_usable(self):
        self.prepare('9')
        self.run_to_ship()
        scene = self.scene
        self.assertTrue(scene.level_complete)
        snapshot = (scene.player_x, scene.action, scene.harbor.ship_frame, scene.combat.world_frame)
        self.tick(20)
        self.assertEqual(snapshot, (scene.player_x, scene.action, scene.harbor.ship_frame, scene.combat.world_frame))
        scene.jump_to_screen('10')
        self.assertFalse(scene.level_complete)
        self.assertEqual(scene.harbor.ship_frame, 0)
        scene.restart_opening()
        self.assertEqual(scene.room_id, 3)
        self.assertTrue(scene.opening.active)
        self.assertFalse(scene.harbor.ship_active)

    def test_f2_entry_for_descent_starts_on_upper_roof(self):
        self.prepare('8')
        scene = self.scene
        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x), (14, 0, 269))
        self.tick(20)
        self.assertFalse(scene.terrain_motion.dead)
        self.assertFalse(scene.terrain_motion.falling)

    def test_harbor_generators_use_extracted_profiles(self):
        scene = self.scene
        for label, room, skill, remaining, max_between in (
                ('8', 14, 3, 2, 1), ('9', 15, 3, 5, 1), ('10', 18, 4, 7, 2)):
            scene.jump_to_screen(label)
            points = scene.combat.generation_points
            self.assertEqual(len(points), 1)
            point = points[0]
            self.assertEqual((point.skill, point.remaining, point.max_between),
                             (skill, remaining, max_between))
            self.assertEqual(scene.combat.player.room, room)
            scene.jump_to_room(room, row=1, x=300, facing=0)
            with patch.object(scene.combat.player, 'life', 999):
                self.tick(50)
            self.assertTrue(scene.combat.guards)
            self.assertTrue(all(guard.skill == skill for guard in scene.combat.guards))

    def test_harbor_void_limit_does_not_bypass_the_water_death_delay(self):
        self.prepare('9')
        scene = self.scene
        for actor_type in (0, 2):
            with self.subTest(actor_type=actor_type):
                state = SequenceState(12, action=102, actor_type=actor_type, level_kind=5,
                                      target_x=100, current_x=100, facing=0,
                                      animation_state=9 if actor_type == 2 else 4,
                                      current_y=729 - floor_y(2), vertical_velocity=63)
                runtime = SequenceRuntime(scene.sequences, state)
                motion = TerrainMotion(15, 2, falling=True)
                events = scene.physics.advance(motion, runtime, 100, (100, 650, 120, 729),
                                               cut_enabled=False)
                self.assertNotIn('death', [event.kind for event in events])
                self.assertFalse(motion.dead)
                self.assertEqual(floor_y(motion.row) + state.current_y, 730)
                self.assertEqual((state.vertical_velocity, state.animation_state), (0, 1))
                harbor = Harbor()
                self.assertFalse(harbor.watch_water(0, 15, motion.row, state))
                for _ in range(7):
                    harbor.advance()
                    self.assertFalse(harbor.watch_water(0, 15, motion.row, state))
                harbor.advance()
                self.assertTrue(harbor.watch_water(0, 15, motion.row, state))

    def test_a_guard_killed_on_the_quay_tumbles_into_the_water(self):
        self.scene.jump_to_screen('9')
        scene = self.scene
        scene.combat.guards.clear()
        scene.combat.generation_points.clear()
        runtime = SequenceRuntime(scene.sequences, SequenceState(
            227, current_x=300, target_x=300, facing=1, actor_type=2, level_kind=5))
        runtime.next_frame()
        guard = Fighter(runtime, 1, 3, 15, 1, sword_drawn=True)
        scene.combat.guards.append(guard)
        scene.combat._hurt('guard', guard, scene.combat.player)
        self.assertEqual(guard.state.sequence_id, 185)
        self.assertEqual(guard.state.animation_state, 9)
        for _ in range(40):
            self.tick()
        self.assertTrue(guard.terrain_motion.dead)
        self.assertFalse(guard.targetable)
        self.assertIn(id(guard), scene.harbor.water)
        self.assertGreater(scene.harbor.water[id(guard)].age, 7)
        self.assertEqual(guard.state.action, 185)
