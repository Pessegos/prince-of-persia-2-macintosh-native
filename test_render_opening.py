import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageChops

from animation_data import parse_frame_records, sequence_words
from opening_animation import OpeningEscape
from sequence_runtime import SequenceRuntime, SequenceState
from render_opening import (
    actor_foreground_column,
    OPENING_FLOOR_Y,
    ROOM_HEIGHT,
    ROOM_ORIGIN_X,
    ROOM_WIDTH,
    ROOF_DECORATIONS,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    build_opening_room,
    character_sprite_top,
    decode_ctbl,
    decode_shap,
    load_resource_file,
    load_shapes,
    rooftop_scene_data,
    roof_ledge_width,
    RoofLedge,
)
from scene_prototype import SCALE, START_FLOOR_Y, ScenePrototype


class DummyCanvas:
    def winfo_width(self):
        return VIEWPORT_WIDTH * SCALE

    def winfo_height(self):
        return VIEWPORT_HEIGHT * SCALE

    def find_all(self):
        return ()

    def create_image(self, *_args, **_kwargs):
        pass


class OpeningRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.room = build_opening_room()
        cls.roof = load_resource_file("Rooftops.rsrc")
        cls.roof_palette = decode_ctbl(cls.roof["CTBL"][3500]["data"])
        cls.kid = load_resource_file("Kid.rsrc")
        cls.kid_palette = decode_ctbl(cls.kid["CTBL"][25001]["data"])
        cls.frames = parse_frame_records(cls.kid["FRAM"][25001]["data"])

    def test_screen_changes_reuse_decoded_atlas_without_modifying_prior_room(self):
        rooftop_scene_data.cache_clear()
        with patch("render_opening.load_shapes", wraps=load_shapes) as decode:
            room = build_opening_room(False, 3)
            before = room.flattened().tobytes()
            build_opening_room(False, 2)
            build_opening_room(False, 0)
            decode.assert_called_once()
            self.assertEqual(room.flattened().tobytes(), before)

    def render_scene(self, facing=0, dy=0, sword=None, opening=None, x=370):
        scene = ScenePrototype.__new__(ScenePrototype)
        scene.paused = False
        scene.dev_menu = None
        scene.background = self.room.background
        scene.foreground = self.room.foreground
        scene.kid = self.kid
        scene.palette = self.kid_palette
        scene.first_shape_id = int.from_bytes(self.kid["SHPL"][25001]["data"][:2], "big")
        scene.frames = self.frames
        scene.action = 15
        scene.player_x = x
        scene.sequence_state = SimpleNamespace(facing=facing, current_y=dy)
        scene.sprite_cache = {}
        scene.sword_sprite = lambda: sword
        scene.canvas = DummyCanvas()
        if opening is not None:
            scene.opening = opening
            scene.background = build_opening_room(include_curtain=False).background
            scene.sequence_state = opening.state
            scene.action = opening.state.action
            scene.player_x = opening.state.target_x
            scene.curtain_sprites = [
                decode_shap(self.roof["SHAP"][3588 + index]["data"], self.roof_palette)
                for index in range(9)
            ]
            scene.glass_sprites = [
                decode_shap(self.roof["SHAP"][3597 + index]["data"], self.roof_palette)
                for index in range(12)
            ]
        with patch("window_controls.ImageTk.PhotoImage", side_effect=lambda frame: frame.copy()):
            scene.render()
        self.assertEqual(scene.image_ref.size, (VIEWPORT_WIDTH * SCALE, VIEWPORT_HEIGHT * SCALE))
        return scene.image_ref.resize((VIEWPORT_WIDTH, VIEWPORT_HEIGHT), Image.Resampling.NEAREST)

    def viewport_background(self):
        image = Image.new("RGBA", (VIEWPORT_WIDTH, VIEWPORT_HEIGHT), (0, 0, 0, 255))
        image.paste(self.room.flattened(), (ROOM_ORIGIN_X, 0))
        return image

    def changed_pixels(self, image):
        return ImageChops.difference(image.convert("RGB"), self.viewport_background().convert("RGB"))

    def test_original_room_clip_and_actor_baseline(self):
        self.assertEqual((ROOM_WIDTH, ROOM_HEIGHT), (510, 365))
        self.assertEqual(self.room.background.size, (510, 365))
        self.assertEqual(self.room.foreground.size, (510, 365))
        self.assertEqual(OPENING_FLOOR_Y, 226)
        self.assertEqual(START_FLOOR_Y, 226)

    def test_foreground_masks_keep_floor_ownership_without_changing_scenery(self):
        room = self.room
        self.assertIsNone(room.actor_occlusion[4].getbbox())
        # Upper parapet / descending ledge versus the lower palace wall.
        for x, y in ((380, 222), (418, 240)):
            self.assertEqual(room.foreground.getpixel((x, y))[3], 255)
            self.assertEqual(room.actor_occlusion[1].getpixel((x, y)), 255)
            self.assertEqual(room.actor_occlusion[2].getpixel((x, y)), 0)
        self.assertEqual(room.actor_occlusion[2].getpixel((380, 320)), 255)
        # The side's back half is visible scenery, not a foreground veil.
        self.assertEqual(room.foreground.getpixel((430, 240))[3], 255)
        self.assertEqual(room.actor_occlusion[1].getpixel((430, 240)), 0)

    def test_roof_ledge_foreground_width_matches_native_room_exceptions(self):
        for room, row, actor_row, bottom, width in (
                (3, 1, 1, 226, 20), (0, 1, 1, 226, 19), (2, 1, 1, 226, 19),
                (1, 1, 1, 226, 22), (9, 0, 0, 109, 22), (9, 0, 0, 110, 17),
                (10, 1, 2, 226, 17), (10, 1, 1, 229, 22)):
            with self.subTest(room=room, row=row, actor_row=actor_row, bottom=bottom):
                self.assertEqual(roof_ledge_width(room, row, actor_row, bottom), width)

    def test_ledge_transparency_cannot_erase_another_foreground_piece(self):
        mask = Image.new("L", (20, 20), 255)
        ledge = RoofLedge(0, 3, 4, Image.new("L", (10, 10), 0))
        ledge.add_to(mask, 5)
        self.assertEqual(mask.getextrema(), (255, 255))

    def test_foreground_index_uses_native_foot_and_behind_cell_in_both_directions(self):
        from terrain import character_column, floor_contact_x

        for facing in (0, 1):
            for action, mode, behind in ((15, 0, False), (91, 2, True), (80, 3, True),
                                          (106, 4, True), (135, 0, True), (148, 0, True),
                                          (149, 0, False), (15, 6, True)):
                with self.subTest(facing=facing, action=action, mode=mode):
                    state = SequenceState(2, action=action, animation_state=mode,
                                          target_x=336, facing=facing)
                    record = self.frames[action]
                    expected = character_column(floor_contact_x(336, facing, record))
                    if behind:
                        expected += -1 if facing else 1
                    self.assertEqual(actor_foreground_column(state, record), expected)

    def test_caught_pose_keeps_near_facade_in_front_even_outside_indexed_cells(self):
        room = build_opening_room(room_id=0)
        state = SequenceState(25, action=91, animation_state=6, target_x=336, facing=1)
        record = self.frames[91]
        static = room.actor_mask(2)
        dynamic = room.actor_mask(2, state=state, record=record)
        self.assertEqual(static.getpixel((330, 270)), 255)
        self.assertEqual(dynamic.getpixel((330, 270)), 255)
        self.assertIsNone(ImageChops.subtract(dynamic, static).crop((306, 245, 357, 365)).getbbox())
        # Drawing order changes for the actor, never the building artwork.
        self.assertEqual(room.flattened().getpixel((330, 270))[3], 255)
        state.animation_state = 0
        state.action = 15
        wall = room.actor_mask(2, state=state, record=self.frames[15])
        self.assertEqual(wall.getpixel((330, 270)), 255)

    def test_hanging_on_near_facade_also_keeps_the_upper_parapet_in_front(self):
        for room_id, x, column in ((0, 332, 6), (2, 281, 5)):
            with self.subTest(room_id=room_id):
                room = build_opening_room(room_id=room_id)
                state = SequenceState(25, action=92, animation_state=6, target_x=x, facing=1)
                left = x - 16
                mask = room.actor_mask(2, state=state, bounds=(left, 221, x - 1, 317),
                                       record=self.frames[92])
                self.assertEqual(mask.getpixel((column * 51 + 12, 234)), 255)
                self.assertEqual(mask.getpixel((column * 51 + 12, 270)), 255)

    def test_climb_half_redraw_keeps_only_the_native_floor_strip(self):
        room = build_opening_room(room_id=0)
        state = SequenceState(10, action=141, animation_state=3, target_x=344, facing=1)
        mask = room.actor_mask(1, state=state, record=self.frames[141])
        # Pose 141: DATA Rect=(109,0,120,30), cell 6/row 1 gives
        # x=306..335 and y=229..239. The whole parapet must not erase the torso.
        self.assertEqual(room.actor_mask(1).getpixel((322, 222)), 255)
        self.assertEqual(mask.getpixel((322, 222)), 0)
        self.assertEqual(mask.getpixel((322, 232)), 255)
        self.assertEqual(mask.getpixel((337, 232)), 0)
        state.action = 147
        self.assertEqual(room.actor_mask(1, state=state, record=self.frames[147]).getpixel((322, 232)), 0)

    def test_climb_mode_indexes_drawn_rectangle_instead_of_supporting_foot(self):
        state = SequenceState(10, action=141, animation_state=1, target_x=202, facing=0)
        bounds = (197, 81, 240, 131)
        record = self.frames[141]
        self.assertEqual(actor_foreground_column(state, record, bounds), 4)
        # A wider frame must index its left edge, not retain the old foot cell.
        self.assertEqual(actor_foreground_column(state, record, (145, 81, 240, 131)), 3)

    def test_junction_climb_keeps_roof_pillar_and_near_ledge_in_front_of_head_and_arm(self):
        room = build_opening_room(room_id=9)
        state = SequenceState(10, action=140, animation_state=1, target_x=225, facing=0)
        bounds = (198, 79, 240, 135)
        mask = room.actor_mask(1, state=state, bounds=bounds, record=self.frames[140])
        self.assertEqual(mask.getpixel((199, 85)), 255)
        self.assertEqual(mask.getpixel((209, 111)), 255)
        # The long shaded side is behind the Prince, not a blanket wall mask.
        self.assertEqual(mask.getpixel((233, 130)), 0)
        self.assertEqual(mask.getpixel((209, 78)), 0)

    def test_climb_row_transition_does_not_drop_lower_wall_or_cover_unrelated_upper_roofs(self):
        room = build_opening_room(room_id=9)
        state = SequenceState(10, action=141, animation_state=1, target_x=202, facing=0)
        mask = room.actor_mask(0, state=state, bounds=(197, 81, 240, 131), record=self.frames[141])
        self.assertEqual(mask.getpixel((199, 127)), 255)
        self.assertEqual(mask.getpixel((50, 100)), 0)
        self.assertEqual(mask.getpixel((233, 130)), 0)

    def test_ledge_draw_order_uses_native_modes_poses_and_sequence_veto(self):
        ledge = RoofLedge(0, 10, 20, Image.new("L", (22, 30), 255))
        bounds = (9, 19, 10, 20)
        for mode, action, sequence, expected in (
                (3, 15, 10, True), (4, 15, 23, True), (6, 15, 24, True),
                (0, 91, 25, True), (0, 80, 24, True), (0, 81, 24, True),
                (0, 136, 10, True), (0, 15, 1, False), (3, 136, 68, False)):
            with self.subTest(mode=mode, action=action, sequence=sequence):
                state = SimpleNamespace(animation_state=mode, action=action, sequence_id=sequence)
                self.assertEqual(ledge.behind_actor(state, bounds), expected)
        state = SimpleNamespace(animation_state=3, action=135, sequence_id=10)
        for outside in ((0, 0, 9, 19), (32, 20, 40, 30), (10, 50, 20, 60)):
            self.assertFalse(ledge.behind_actor(state, outside))

    def test_junction_climb_removes_only_intersecting_ledge_occlusion(self):
        room = build_opening_room(room_id=9)
        ledge = next(ledge for ledge in room.ledges if ledge.row == 0)
        bounds = (ledge.x, ledge.y, ledge.x + 21, ledge.y + ledge.alpha.height - 1)
        state = SimpleNamespace(animation_state=3, action=136, sequence_id=10)
        normal = room.actor_mask(0, bounds[3])
        climbing = room.actor_mask(0, state=state, bounds=bounds)
        changed = ImageChops.subtract(normal, climbing)
        self.assertIsNotNone(changed.getbbox())
        self.assertIsNone(ImageChops.subtract(climbing, normal).getbbox())
        left, top, right, bottom = changed.getbbox()
        self.assertGreaterEqual(left, ledge.x)
        self.assertGreaterEqual(top, ledge.y)
        self.assertLessEqual(right, ledge.x + 22)
        self.assertLessEqual(bottom, ledge.y + ledge.alpha.height)
        self.assertEqual(room.actor_mask(0, state=state).size, (ROOM_WIDTH, ROOM_HEIGHT))

    def test_falling_past_junction_shortens_only_the_ledge_foreground(self):
        room = build_opening_room(room_id=9)
        normal = room.actor_mask(0, 109)
        falling = room.actor_mask(0, 110)
        changed = ImageChops.subtract(normal, falling)
        self.assertIsNotNone(changed.getbbox())
        # Texture and solid wall remain unchanged; only five ledge columns differ.
        ledge = next(ledge for ledge in room.ledges if ledge.row == 0)
        self.assertIsNone(changed.crop((0, 0, ledge.x + 17, ROOM_HEIGHT)).getbbox())
        self.assertIsNone(changed.crop((ledge.x + 22, 0, ROOM_WIDTH, ROOM_HEIGHT)).getbbox())

    def test_character_draw_uses_inclusive_bottom_coordinate(self):
        for bottom_y, height in ((226, 79), (196, 79), (0, 3), (-5, 4)):
            with self.subTest(bottom_y=bottom_y, height=height):
                top = character_sprite_top(bottom_y, height)
                self.assertEqual(top + height - 1, bottom_y)

    def test_uncompressed_shape_ignores_row_padding(self):
        palette = {1: (11, 22, 33, 255), 2: (44, 55, 66, 255)}
        header = struct.pack(">HhhH4x", 0xB000, 4, 3, 2)
        shape = decode_shap(header + bytes((1, 2, 0, 255, 2, 1, 1, 255)), palette)
        self.assertEqual(shape.size, (3, 2))
        self.assertEqual([shape.getpixel((x, y)) for y in range(2) for x in range(3)], [
            palette[1], palette[2], (0, 0, 0, 0), palette[2], palette[1], palette[1],
        ])

    def test_real_uncompressed_roof_decoration(self):
        shape = decode_shap(self.roof["SHAP"][3559]["data"], self.roof_palette)
        self.assertEqual(shape.size, (4, 17))
        self.assertIsNotNone(shape.getbbox())

    def test_native_decoration_table_has_all_eleven_original_shapes_and_passes(self):
        self.assertEqual(ROOF_DECORATIONS, (
            (59, 47, -56, 1), (60, 0, 0, 5), (61, 48, -7, 5),
            (62, 0, -42, 5), (63, 35, -88, 1), (64, 47, -85, 1),
            (65, 45, -18, 1), (66, 46, -12, 1), (67, 46, -21, 1),
            (68, 48, 0, 1), (121, 38, -88, 5)))
        shapes = rooftop_scene_data()[1]
        for index, _, _, _ in ROOF_DECORATIONS:
            self.assertIsNotNone(shapes[3500 + index].getbbox())

    def test_empty_tile_decorations_restore_both_right_building_corners(self):
        shapes = rooftop_scene_data()[1]
        for room_id, column, shape_id, dx, dy in (
                (0, 5, 3567, 46, -21), (2, 4, 3568, 48, 0), (2, 4, 3563, 35, -88)):
            row = 2 if shape_id == 3563 else 1
            with self.subTest(room=room_id, shape=shape_id):
                room = build_opening_room(room_id=room_id)
                tile = rooftop_scene_data()[0].tile(room_id, column, row)
                self.assertEqual(tile.kind, 0)
                shape = shapes[shape_id]
                piece = next(p for p in room.pieces if p.decoration and p.column == column and p.row == row)
                expected = (column * 51 + dx, (row + 1) * 120 + 5 + dy - shape.height)
                self.assertEqual((piece.x, piece.y), expected)
                self.assertEqual(piece.alpha.tobytes(), shape.getchannel("A").tobytes())
                self.assertEqual(room.actor_mask(row).crop(
                    (*expected, expected[0] + shape.width, expected[1] + shape.height)).tobytes(),
                    shape.getchannel("A").tobytes())

    def test_back_pass_decoration_is_scenery_not_an_actor_foreground_mask(self):
        room = build_opening_room(room_id=0)
        shape = rooftop_scene_data()[1][3560]
        x, y = 255, 365 - shape.height
        foreground = room.actor_mask(2).crop((x, y, x + shape.width, y + shape.height))
        self.assertIsNone(foreground.getbbox())
        self.assertIsNotNone(room.background.crop((x, y, x + shape.width, y + shape.height)).getbbox())

    def test_right_facing_hang_retains_upper_corner_decoration_in_front(self):
        for room_id, x in ((0, 332), (2, 281)):
            with self.subTest(room=room_id):
                room = build_opening_room(room_id=room_id)
                state = SequenceState(25, action=92, animation_state=6, target_x=x, facing=1)
                corner = next(p for p in room.pieces if p.decoration and p.row == 1)
                bounds = (corner.x, corner.y, corner.x + corner.alpha.width - 1, 337)
                mask = room.actor_mask(2, state=state, bounds=bounds, record=self.frames[92])
                self.assertIsNone(ImageChops.subtract(corner.alpha, mask.crop(
                    (corner.x, corner.y, corner.x + corner.alpha.width,
                     corner.y + corner.alpha.height))).getbbox())

    def test_sky_fill_removes_black_strip_next_to_wall(self):
        sky = decode_shap(self.roof["SHAP"][3501]["data"], self.roof_palette)
        for y in range(5, 120):
            for x in range(347, 357):
                self.assertEqual(self.room.background.getpixel((x, y)), sky.getpixel((x - 306, y)))

    def test_upper_neighbor_fills_five_pixel_margin(self):
        upper_wall = decode_shap(self.roof["SHAP"][3540]["data"], self.roof_palette)
        for y in range(5):
            self.assertEqual(
                self.room.background.getpixel((180, y)),
                upper_wall.getpixel((27, upper_wall.height - 5 + y)),
            )

    def test_secret_room_without_upper_neighbor_has_sky_not_a_physics_wall(self):
        room = build_opening_room(room_id=4)
        sky = decode_shap(self.roof["SHAP"][3501]["data"], self.roof_palette)
        for y in range(5):
            for x in range(510):
                self.assertEqual(room.background.getpixel((x, y)), sky.getpixel((x % 51, y)))
        self.assertIsNone(room.foreground.crop((0, 0, 510, 5)).getbbox())

    def test_static_window_uses_original_curtain(self):
        curtain = decode_shap(self.roof["SHAP"][3596]["data"], self.roof_palette)
        opaque_count = 0
        for y in range(curtain.height):
            for x in range(curtain.width):
                color = curtain.getpixel((x, y))
                if color[3] == 255:
                    opaque_count += 1
                    self.assertEqual(self.room.background.getpixel((266 + x, 38 + y)), color)
        self.assertGreater(opaque_count, 100)

    def test_parapet_hides_standing_legs_both_facings(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                difference = self.changed_pixels(self.render_scene(facing=facing))
                self.assertIsNotNone(difference.crop((340, 140, 400, 212)).getbbox())
                self.assertIsNone(difference.crop((340, 212, 400, 245)).getbbox())

    def test_jump_raises_prince_without_moving_scenery(self):
        standing = self.changed_pixels(self.render_scene()).getbbox()
        airborne_image = self.render_scene(dy=-30)
        airborne = self.changed_pixels(airborne_image).getbbox()
        self.assertEqual(airborne[1], standing[1] - 30)
        self.assertEqual(airborne[3], 197)
        self.assertIsNone(self.changed_pixels(airborne_image).crop((0, 245, 512, 384)).getbbox())

    def test_foreground_also_covers_sword_attachment(self):
        sword = Image.new("RGBA", (20, 35), (255, 0, 255, 255))
        image = self.render_scene(sword=(sword, 0, 0))
        above = image.crop((340, 191, 400, 212))
        colors_above = {color for _count, color in above.getcolors(above.width * above.height)}
        self.assertIn((255, 0, 255, 255), colors_above)
        self.assertIsNone(self.changed_pixels(image).crop((340, 212, 400, 245)).getbbox())

    def test_display_keeps_native_pixels_and_hud_band(self):
        image = self.render_scene()
        self.assertEqual(image.size, (512, 384))
        self.assertEqual(image.crop((0, 365, 512, 384)).getextrema(), ((0, 0), (0, 0), (0, 0), (255, 255)))
        self.assertEqual(image.getpixel((0, 200)), (0, 0, 0, 255))
        self.assertEqual(image.getpixel((511, 200)), (0, 0, 0, 255))

    def opening(self):
        prince = load_resource_file("Prince.rsrc")
        sequences = {
            key: sequence_words(value["data"])
            for key, value in prince["SEQS"].items()
        }
        return OpeningEscape(
            SequenceRuntime(sequences, SequenceState(2, actor_type=0, level_kind=5)), 2
        )

    def test_dynamic_window_does_not_retain_static_curtain(self):
        opening = self.opening()
        image = self.render_scene(opening=opening)
        # Native empty sky and room border still agree with the static scene.
        self.assertEqual(image.getpixel((500, 70)), self.viewport_background().getpixel((500, 70)))
        self.assertIsNotNone(self.changed_pixels(image).crop((260, 38, 350, 149)).getbbox())
        self.assertEqual(image.getpixel((511, 200)), (0, 0, 0, 255))

    def test_finished_opening_is_pixel_identical_to_static_room_at_landing_x(self):
        opening = self.opening()
        while opening.active:
            opening.advance()
        image = self.render_scene(opening=opening)
        expected = self.render_scene(facing=1, x=411)
        self.assertIsNone(ImageChops.difference(image.convert("RGB"), expected.convert("RGB")).getbbox())

    def test_glass_fragments_are_clipped_by_parapet_foreground(self):
        opening = self.opening()
        for _ in range(7):
            opening.advance()
        image = self.render_scene(opening=opening)
        # Glass index 8 extends below the parapet, which must remain in front.
        for y in range(212, 245):
            for x in range(398, 408):
                self.assertEqual(image.getpixel((x + ROOM_ORIGIN_X, y)), self.viewport_background().getpixel((x + ROOM_ORIGIN_X, y)))


if __name__ == "__main__":
    unittest.main()
