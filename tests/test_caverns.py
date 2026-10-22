import json
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from PIL import Image, ImageChops

from pop2.caverns import (CavernRoom, cavern_clip_top, cavern_room, flask_shape,
                         flask_assets, floor_redraw_cells)
from pop2.cavern_state import CavernState
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import (OpeningRoom, load_resource_file, decode_shap,
                                 decode_ctbl, native_buffer_cells)
from pop2.terrain import LevelMap, Tile
from tools.render_cavern_map import room_positions
from tools.extract_caverns import (CavernRecovery, clip_climbing, exit_closing_frames,
                                   recover_climbing, recover_room, recovery_inputs)
from tools.audit_caverns import pixel_difference


class CavernClipTests(unittest.TestCase):
    def setUp(self):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x218a, 3)
        self.terrain = SimpleNamespace(level=level, tile=lambda *args: Tile(1))

    def state(self, action=136, mode=1, facing=1, actor_type=0):
        return SimpleNamespace(action=action, animation_state=mode,
                               facing=facing, actor_type=actor_type)

    def test_climb_rectangles_match_execution_of_macintosh_clipchar(self):
        # Original CODE:4 GetCharEdges + ClipChar, room 1, ordinary Prince.
        # Bounds are inclusive; QuickDraw rectangles are top/left/bottom/right.
        cases = (
            (2, 80, 2, (106, 221, 129, 314), (245, 106, 315, 130)),
            (2, 91, 2, (113, 221, 132, 318), (245, 113, 319, 133)),
            (2, 135, 1, (109, 221, 125, 317), (245, 109, 318, 126)),
            (2, 136, 1, (106, 218, 125, 302), (245, 106, 303, 126)),
            (2, 137, 1, (108, 207, 133, 290), (206, 108, 291, 134)),
            (1, 142, 1, (104, 198, 158, 240), (197, 104, 241, 159)),
        )
        for row, action, mode, bounds, native_rect in cases:
            with self.subTest(action=action):
                clip = cavern_clip_top(self.terrain, 0, row, self.state(action, mode), bounds)
                left, top, right, bottom = bounds
                rect = (max(top - 1, clip) if clip else top - 1, left, bottom + 1, right + 1)
                self.assertEqual(rect, native_rect)

    def test_top_clip_has_native_strict_height_and_bottom_thresholds(self):
        for row in (1, 2):
            boundary = row * 120 + 5
            for top, bottom, expected in ((boundary - 28, boundary + 60, 0),
                                          (boundary - 27, boundary + 60, boundary),
                                          (boundary - 27, boundary, 0),
                                          (boundary - 27, boundary + 1, boundary)):
                with self.subTest(row=row, top=top, bottom=bottom):
                    result = cavern_clip_top(self.terrain, 0, row, self.state(), (106, top, 125, bottom))
                    self.assertEqual(result, expected)

    def test_recrop_is_shared_by_rooms_directions_and_ordinary_actor_types(self):
        for room in range(32):
            for facing in (0, 1):
                for actor_type in (0, 2):
                    with self.subTest(room=room, facing=facing, actor_type=actor_type):
                        result = cavern_clip_top(self.terrain, room, 2,
                                                 self.state(facing=facing, actor_type=actor_type),
                                                 (106, 218, 125, 302))
                        self.assertEqual(result, 245)

    def test_empty_tile_at_either_body_edge_disables_top_clip(self):
        for empty_column in (1, 2):
            for kind in (0, 9, 27, 47, 49):
                self.terrain.tile = lambda room, col, row: Tile(kind if col == empty_column else 1)
                with self.subTest(column=empty_column, kind=kind):
                    result = cavern_clip_top(self.terrain, 0, 2, self.state(), (94, 218, 133, 302))
                    self.assertEqual(result, 0)

    def test_native_hang_and_stationary_exceptions_skip_tile_checks(self):
        self.terrain.tile = lambda *args: Tile(0)
        self.assertEqual(cavern_clip_top(self.terrain, 0, 2, self.state(91, 2), (106, 221, 129, 314)), 245)
        self.assertEqual(cavern_clip_top(self.terrain, 0, 2, self.state(91, 2, facing=0),
                                        (106, 221, 129, 314)), 0)
        self.terrain.tile = lambda room, col, row: Tile(1 if col == 1 else 0)
        bounds = (94, 218, 133, 302)
        self.assertEqual(cavern_clip_top(self.terrain, 0, 2, self.state(79, 0), bounds), 245)
        self.assertEqual(cavern_clip_top(self.terrain, 0, 2, self.state(79, 2), bounds), 0)

    def test_tumbling_and_special_actor_types_keep_their_full_sprite(self):
        for state in (self.state(mode=9), self.state(actor_type=7), self.state(actor_type=8)):
            self.assertEqual(cavern_clip_top(self.terrain, 0, 2, state, (106, 218, 125, 302)), 0)

    def test_floor_redraw_cells_match_native_quickfloor_execution(self):
        cases = (
            (79, 2, 1, (304, 102, 333, 191), ((5, 0), (6, 0))),
            (78, 2, 1, (96, 241, 119, 333), ((1, 1), (2, 1))),
            (15, 3, 1, (108, 207, 133, 290), ((2, 1),)),
            (15, 4, 0, (108, 207, 133, 290), ((2, 1),)),
            (149, 5, 1, (108, 207, 133, 290), ((2, 1),)),
            (149, 5, 1, (104, 198, 158, 240), ()),
            (137, 1, 1, (108, 207, 133, 290), ()),
            (137, 1, 0, (108, 207, 133, 290), ()),
            (15, 2, 1, (80, 90, 140, 105), ()),
            (15, 2, 1, (80, 90, 140, 106), ((1, 0), (2, 0))),
            (15, 0, 1, (108, 207, 133, 290), ()),
        )
        for action, mode, facing, bounds, expected in cases:
            with self.subTest(action=action, mode=mode, facing=facing, bounds=bounds):
                self.assertEqual(floor_redraw_cells(self.state(action, mode, facing), bounds), expected)


class CavernDrawingTests(unittest.TestCase):
    def test_scenery_audit_counts_changed_pixels_and_excludes_only_requested_rectangles(self):
        before = Image.new('RGBA', (4, 3), 'black')
        after = before.copy()
        after.putpixel((0, 0), (1, 0, 0, 255))
        after.putpixel((2, 1), (0, 0, 1, 255))
        self.assertEqual(pixel_difference(before, after)[0], 2)
        count, difference = pixel_difference(before, after, [(1, 2, 2, 3)])
        self.assertEqual(count, 1)
        self.assertEqual(difference.getbbox(), (0, 0, 1, 1))

    def test_unpainted_mask_distinguishes_transparency_from_native_black_copy(self):
        def shape(index):
            return {'data': struct.pack('>HhhHHH', 0xb000, 1, 1, 1, 0, 0) + bytes([index])}

        commands = [['back', 3501, 0, 1, 16, 0],
                    ['front', 3502, 1, 1, 16, 0],
                    ['front', 3502, 2, 1, 0, 0]]
        export = {'version': 14, 'level': 3, 'rooms': {'0': commands}}
        resources = {'SHAP': {3501: shape(1), 3502: shape(0)}}
        with patch('pop2.caverns.cavern_assets', return_value=(
                export, resources, {1: (150, 100, 50, 255)}, {})):
            room = cavern_room(0)
        self.assertEqual([room.retained_mask.getpixel((x, 0)) for x in range(4)],
                         [0, 255, 0, 255])
        self.assertEqual(room.foreground.getpixel((1, 0)), (0, 0, 0, 0))
        self.assertEqual(room.foreground.getpixel((2, 0)), (0, 0, 0, 255))

    def test_room_cuts_keep_only_untouched_scenery_without_mutating_cached_art(self):
        mask = Image.new('L', (4, 3))
        mask.putpixel((1, 1), 255)
        def room(color):
            return CavernRoom(Image.new('RGBA', mask.size, color), Image.new('RGBA', mask.size),
                              {}, (), (), 0, 3, retained_mask=mask)

        blue, red, green = room('blue'), room('red'), room('green')
        with patch('pop2.caverns.cavern_assets', return_value=({}, None, None, None)):
            renderer = LevelRenderer(SimpleNamespace(number=3, kind=3), preload_room=False)
        with patch.object(renderer, 'room', side_effect=[blue, red, red, green, red]):
            renderer.enter_room(0)
            first = renderer.enter_room(1)
            self.assertEqual(first.background.getpixel((1, 1)), (0, 0, 255, 255))
            self.assertEqual(first.background.getpixel((2, 1)), (255, 0, 0, 255))
            self.assertEqual(red.background.getpixel((1, 1)), (255, 0, 0, 255))
            self.assertIs(renderer.enter_room(1), first)
            frame = green.background.copy()
            renderer.enter_room(2)
            renderer.remember_scenery(frame)
            frame.putpixel((1, 1), (255, 255, 255, 255))
            second = renderer.enter_room(1)
            self.assertEqual(second.background.getpixel((1, 1)), (0, 128, 0, 255))
            self.assertIsNot(first, second)

    def test_same_room_variants_use_the_entry_underlay_not_the_previous_gate_frame(self):
        def room(color, retained=False):
            return CavernRoom(Image.new('RGBA', (4, 3), color), Image.new('RGBA', (4, 3)),
                              {}, (), (), 0, 3,
                              retained_mask=Image.new('L', (4, 3), 255 if retained else 0))

        blue, closed, opened = room('blue'), room('red'), room('black', retained=True)
        with patch('pop2.caverns.cavern_assets', return_value=({}, None, None, None)):
            renderer = LevelRenderer(SimpleNamespace(number=3, kind=3), preload_room=False)
        with patch.object(renderer, 'room', side_effect=[blue, closed, opened]):
            renderer.enter_room(0)
            renderer.enter_room(1)
            result = renderer.enter_room(1)
        self.assertEqual(result.background.getpixel((1, 1)), (0, 0, 255, 255))

    def test_shared_recovery_restores_ram_registers_and_releases_hooks_on_failure(self):
        from unicorn.m68k_const import UC_M68K_REG_D1

        recovery_inputs.cache_clear()
        self.addCleanup(recovery_inputs.cache_clear)
        resources = {'CODE': {0: {'data': bytes(16)}, 3: {'data': bytes(8)}}}
        artwork = {'PIEC': {3500: {'data': b'piece'}}}
        with (patch('tools.extract_caverns.parse_resource_fork', side_effect=[resources, artwork]),
              patch('tools.extract_caverns.expand_a5_data', return_value=b'initial'),
              self.assertRaisesRegex(RuntimeError, 'draw failure')):
            with CavernRecovery(b'program', b'artwork', None) as machine:
                cpu = machine.reset()
                cpu.mem_write(0x93000, b'dirty')
                cpu.reg_write(UC_M68K_REG_D1, 12345)
                self.assertIs(machine.reset(), cpu)
                self.assertEqual(bytes(cpu.mem_read(0x93000, 5)), bytes(5))
                self.assertEqual(cpu.reg_read(UC_M68K_REG_D1), 0)
                machine.callback = Mock()
                with self.assertRaisesRegex(RuntimeError, 'already drawing'):
                    machine.reset()
                raise RuntimeError('draw failure')
        self.assertIsNone(machine.callback)
        self.assertFalse(cpu._callbacks)
        self.assertEqual(list(cpu.mem_regions()), [])
        machine.close()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            machine.reset()

    def test_climb_recovery_reuses_rectangles_but_keeps_pose_141_native(self):
        bounds = [(109, 0, 120, 26)] * 10
        bounds[3], bounds[7] = (109, 0, 120, 31), (112, 0, 120, 22)
        data = bytearray(0x6000)
        for index, rect in enumerate(bounds):
            struct.pack_into('>4h', data, len(data) - 0x4b46 + index * 8, *rect)
        code = bytearray(0x2600)
        code[0x25fa:0x2600] = bytes.fromhex('0c6d008daf38')
        inputs = {'CODE': {8: {'data': bytes(code)}}}, {}, {}, bytes(data), {}
        command = ['front', 3501, 102, 245, 16, 1, [229, 102, 241, 133], 4, 2, 1]
        special = ['native pose 141']
        recover = Mock(side_effect=[{'commands': [command]}, {'commands': special}])
        with patch('tools.extract_caverns.recovery_inputs', return_value=inputs):
            redraw = recover_climbing(b'program', b'art', b'prince', b'level', 0, recover)
        self.assertEqual([call.args[-1] for call in recover.call_args_list], [138, 141])
        self.assertEqual(redraw['141'], special)
        self.assertEqual(redraw['142'][0][6], [232, 102, 241, 124])
        self.assertEqual(redraw['135'][0][6], [229, 102, 241, 128])
        self.assertEqual(command[6], [229, 102, 241, 133])
        self.assertEqual(clip_climbing([command], (241, 0, 250, 31)), [])

    def test_unrecognized_climb_geometry_falls_back_to_all_native_poses(self):
        data = bytes(0x6000)
        recover = Mock(return_value={'commands': []})
        with patch('tools.extract_caverns.recovery_inputs', return_value=({'CODE': {}}, {}, {}, data, {})):
            redraw = recover_climbing(b'program', b'art', b'prince', b'level', 0, recover)
        self.assertEqual(list(redraw), [str(action) for action in range(135, 145)])
        self.assertEqual([call.args[-1] for call in recover.call_args_list], list(range(135, 145)))

    def test_recovery_index_hooks_only_modeled_primitive_entries(self):
        recovery_inputs.cache_clear()
        self.addCleanup(recovery_inputs.cache_clear)
        code = bytes.fromhex('4ead 4e75 4e71 a8a8 a123 4e90 4e71')
        resources = {'CODE': {0: {'data': b''}, 3: {'data': code}}}
        with (patch('tools.extract_caverns.parse_resource_fork', side_effect=[resources, {}]),
              patch('tools.extract_caverns.expand_a5_data', return_value=b'')):
            intercepts = recovery_inputs(b'program', b'artwork', None)[4]
        # OffsetRect traps are serviced wherever they occur (bridge/custom pieces).
        self.assertEqual(intercepts, {0x130004: b'\x4e\x71', 0x130006: b'\xa8\xa8'})

    def test_floor_redraw_is_clipped_to_the_current_actor_rectangle(self):
        size = (510, 365)
        floor = Image.new('RGBA', (42, 25), (100, 80, 60, 255))
        room = CavernRoom(Image.new('RGBA', size), Image.new('RGBA', size), {}, (), (), 0, 3,
                          floor_redraw={(6, 0): [(floor, (315, 100))]})
        frame = Image.new('RGBA', size, 'red')
        state = SimpleNamespace(action=79, animation_state=2, facing=1)
        room.draw_actor_foreground(frame, state, (304, 102, 333, 191))
        self.assertEqual(frame.getpixel((315, 102)), (100, 80, 60, 255))
        self.assertEqual(frame.getpixel((333, 124)), (100, 80, 60, 255))
        self.assertEqual(frame.getpixel((315, 101)), (255, 0, 0, 255))
        self.assertEqual(frame.getpixel((334, 124)), (255, 0, 0, 255))

    def test_native_climb_redraw_uses_its_drawn_cell_and_keeps_pillars_in_front(self):
        size = (510, 365)
        front = Image.new('RGBA', size)
        front.putpixel((110, 234), (130, 90, 60, 255))
        redraw = Image.new('RGBA', (3, 3), (100, 80, 60, 255))
        other = Image.new('RGBA', (3, 3), 'cyan')
        room = CavernRoom(Image.new('RGBA', size), front, {}, (), (), 0, 3,
                          climb_redraw={(137, 2, 1): [(redraw, (109, 232))],
                                        (137, 3, 1): [(other, (109, 232))]})
        frame = Image.new('RGBA', size, 'red')
        state = SimpleNamespace(action=137, facing=1)
        room.draw_actor_foreground(frame, state, (108, 207, 133, 290))
        self.assertEqual(frame.getpixel((109, 232)), (100, 80, 60, 255))
        self.assertEqual(frame.getpixel((110, 234)), (130, 90, 60, 255))
        for action, facing in ((137, 0), (134, 1), (145, 1)):
            unchanged = Image.new('RGBA', size, 'red')
            room.draw_actor_foreground(unchanged, SimpleNamespace(action=action, facing=facing),
                                       (108, 207, 133, 290))
            self.assertEqual(unchanged.getpixel((109, 232)), (255, 0, 0, 255))

    def test_native_buffer_cells_follow_full_actor_rectangle(self):
        self.assertEqual(native_buffer_cells((50, 4, 51, 5)),
                         ((0, -1), (1, -1), (0, 0), (1, 0)))
        self.assertEqual(native_buffer_cells((459, 124, 460, 125)),
                         ((9, 0), (9, 1)))
        self.assertEqual(native_buffer_cells((50, 5, 50, 6)), ())

    def test_actor_occlusion_uses_only_native_cells_touched_by_bounds(self):
        blank = {row: Image.new('L', (510, 365)) for row in range(-1, 5)}
        cells = {}
        for cell, point in (((0, 0), (20, 20)), ((1, 0), (70, 20)),
                            ((0, 1), (20, 140)), ((1, 1), (70, 140)),
                            ((2, 1), (120, 140))):
            cell_mask = Image.new('L', (1, 1), 255)
            cells[cell] = (cell_mask, point)
        room = OpeningRoom(Image.new('RGBA', (510, 365)), Image.new('RGBA', (510, 365)),
                           blank, (), (), 0, 3, cells)

        mask = room.actor_mask(0, bounds=(50, 124, 51, 125))
        points = ((20, 20), (70, 20), (20, 140), (70, 140), (120, 140))
        self.assertEqual([mask.getpixel(point) for point in points], [255, 255, 255, 255, 0])

    def test_actor_occlusion_uses_every_native_cell_row_touched_by_sprite_bounds(self):
        masks = {row: Image.new('L', (510, 365)) for row in range(-1, 5)}
        for row, y in ((0, 20), (1, 140), (2, 260), (3, 340)):
            masks[row].putpixel((20, y), 255)
        room = OpeningRoom(Image.new('RGBA', (510, 365)), Image.new('RGBA', (510, 365)),
                           masks, (), (), 0, 3)

        # Native MarkBufsForRect maps the sprite's top and bottom to 120-pixel
        # cell rows. This bounds rectangle touches rows 0, 1 and 2.
        mask = room.actor_mask(1, bounds=(10, 124, 30, 245))
        self.assertEqual([mask.getpixel((20, y)) for y in (20, 140, 260, 340)],
                         [255, 255, 255, 0])
        self.assertEqual(room.actor_mask(3).getpixel((20, 340)), 255)

    def test_export_draws_only_environments_with_a_known_piece_table(self):
        # a5-0x4aea holds one piece-drawing table per LEVL environment; only
        # the caverns (3, kinds 0-44) and ruins (4, kinds 0-23) are decoded.
        from tools.extract_caverns import DRAW_KINDS

        self.assertEqual(DRAW_KINDS, {3: 45, 4: 24})
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2186, 5)
        with (patch('tools.extract_caverns.recovery_inputs',
                    return_value=({'CODE': {0: {'data': b''}}}, {}, {}, b'', {})),
              self.assertRaisesRegex(ValueError, 'environment 5')):
            recover_room(b'program', b'artwork', bytes(level), _machine=Mock())

    def test_export_uses_clean_cut_flag_and_full_clip_for_every_cell(self):
        from unicorn import Uc

        recovery_inputs.cache_clear()
        self.addCleanup(recovery_inputs.cache_clear)
        code = bytearray(0x259a)
        for offset in (0x1ab0, 0x1ff4, 0x2598):
            code[offset:offset + 2] = bytes.fromhex('4e75')  # Synthetic RTS, no game assets.
        cells_code = bytearray(0x0b52)
        for offset in (0x026a, 0x03bc, 0x0a4c, 0x0b50):
            cells_code[offset:offset + 2] = bytes.fromhex('4e75')
        resources = {'CODE': {0: {'data': bytes(16)}, 3: {'data': bytes(code)},
                              5: {'data': bytes(cells_code)}}}
        artwork = {'PIEC': {3500: {'data': bytes(4)}}}
        data = bytearray(0x6000)
        struct.pack_into('>i', data, len(data) - 0x4aea + 12, -0x100)
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2198, 1)
        # The drawing table is now chosen by the LEVL environment (caverns).
        struct.pack_into('>H', level, 0x2186, 3)
        observed = []
        released = []

        emulate = Uc.emu_start
        remove_hook = Uc.hook_del
        unmap = Uc.mem_unmap

        def release(cpu, handle):
            remove_hook(cpu, handle)

        def free_memory(cpu, address, size):
            self.assertFalse(cpu._callbacks)
            unmap(cpu, address, size)
            released.append(list(cpu.mem_regions()))

        def observe(cpu, *args, **kwargs):
            observed.append((struct.unpack('>h', cpu.mem_read(0x80000 - 0x4832, 2))[0],
                             struct.unpack('>4h', cpu.mem_read(0x80000 - 0x4600, 8))))
            return emulate(cpu, *args, **kwargs)

        with (patch.object(Uc, 'emu_start', observe),
              patch.object(Uc, 'hook_del', release),
              patch.object(Uc, 'mem_unmap', free_memory),
              patch('tools.extract_caverns.parse_resource_fork',
                    side_effect=[resources, artwork]) as parse,
              patch('tools.extract_caverns.expand_a5_data', return_value=bytes(data)) as expand):
            for _ in range(2):
                recover_room(b'program', b'artwork', bytes(level))
            self.assertEqual(parse.call_count, 2)
            expand.assert_called_once_with(resources)
            self.assertEqual(released, [[], []])
            with (patch.object(Uc, 'emu_start', side_effect=RuntimeError('native failure')),
                  self.assertRaisesRegex(ValueError, 'Cavern renderer failed')):
                recover_room(b'program', b'artwork', bytes(level))
            self.assertEqual(released, [[], [], []])
        self.assertEqual(len(observed), 270)
        self.assertEqual(set(observed), {(1, (0, 0, 365, 510))})

    def test_repaint_export_keeps_live_flames_out_of_static_scenery(self):
        sprite = Image.new('RGBA', (3, 3), 'orange')
        commands = [['back', 3581, 10, 20, 16, 1, [0, 0, 365, 510], 4, 0, 1]]
        program = {'version': 6, 'level': 3, 'rooms': {'0': commands}}
        with patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {3581: sprite})):
            self.assertEqual(cavern_room().background.getpixel((10, 18)), (255, 165, 0, 255))
            self.assertEqual(cavern_room(animated=True).background.getpixel((10, 18)), (0, 0, 0, 255))

    def test_version_six_export_populates_draw_cell_occlusion(self):
        sprite = Image.new('RGBA', (3, 3), (200, 100, 30, 255))
        command = ['front', 3501, 10, 20, 16, 0, [0, 0, 365, 510], 4, 2, 1]
        next_command = ['front', 3502, 12, 20, 16, 0, [0, 0, 365, 510], 4, 2, 1]
        program = {'version': 6, 'level': 3, 'rooms': {'0': [command, next_command]}}
        with patch('pop2.caverns.cavern_assets',
                   return_value=(program, {}, {}, {3501: sprite, 3502: sprite})):
            art = cavern_room()
        cell_mask, position = art.actor_cell_occlusion[(2, 1)]
        self.assertEqual((position, cell_mask.size), ((10, 17), (5, 3)))
        self.assertEqual((cell_mask.getpixel((0, 0)), cell_mask.getpixel((4, 2))), (255, 255))
        self.assertNotIn((1, 1), art.actor_cell_occlusion)

    def test_gate_masks_belong_to_the_stone_tile_not_the_repaint_callers(self):
        sprite = Image.new('RGBA', (41, 146), 'gray')
        commands = [
            ['back', 3563, 408, 357, 16, 2, [211, 408, 357, 449], 4, 7, 2],
            ['back', 3563, 408, 357, 16, 2, [211, 408, 357, 449], 4, 8, 2],
            ['back', 3563, 0, 357, 16, 2, [211, 0, 357, 41], 4, 0, 2],
            ['back', 3563, 102, 477, 16, 3, [331, 102, 365, 143], 4, 1, 2],
        ]
        record = {'kind': 4, 'commands': [['back', 3563, 4, *c[8:10]] for c in commands]}
        program = {'version': 14, 'level': 3, 'rooms': {'0': commands},
                   'pressure_plates': {'rooms': {'0': [record]}}}
        with patch('pop2.caverns.cavern_assets',
                   return_value=(program, {}, {}, {3563: sprite})):
            art = cavern_room()
        self.assertEqual(set(art.gate_occlusion), {(7, 2), (-1, 2), (1, 3)})
        state = SimpleNamespace(actor_type=0, animation_state=0, action=15,
                                source_sequence_id=2, target_x=35, facing=0)
        record = SimpleNamespace(offset_x=4, aux=70)
        mask = art.actor_mask(2, state=state, bounds=(31, 268, 48, 346), record=record)
        self.assertEqual(mask.getpixel((35, 310)), 0)
        self.assertEqual(mask.getpixel((120, 340)), 0)
        state.target_x = 420
        mask = art.actor_mask(2, state=state, bounds=(426, 268, 443, 346), record=record)
        self.assertEqual(mask.getpixel((430, 310)), 255)
        state.target_x = 440  # The column beyond the gate must not peel it.
        mask = art.actor_mask(2, state=state, bounds=(436, 268, 453, 346), record=record)
        self.assertEqual(mask.getpixel((430, 310)), 0)

    def test_monochrome_flask_uses_native_whole_bitmap_rle_and_ink_color(self):
        data = struct.pack('>HhhH2H', 0x9200, 2, 9, 2, 0, 0) + bytes([1, 128, 128, 0])
        colors = {233: (25, 112, 217, 255)}
        image = flask_shape(data, colors, 233)
        self.assertEqual(image.size, (9, 2))
        self.assertEqual(image.getpixel((0, 0)), colors[233])
        self.assertEqual(image.getpixel((1, 0)), (0, 0, 0, 0))
        self.assertEqual(image.getpixel((0, 1)), (0, 0, 0, 0))

    def test_monochrome_flask_rejects_truncation_and_run_overflow(self):
        header = struct.pack('>HhhH2H', 0x9200, 2, 9, 2, 0, 0)
        for body in (b'', bytes([128]), bytes([130, 0]), bytes([0])):
            with self.subTest(body=body), self.assertRaises(ValueError):
                flask_shape(header + body, {233: (1, 2, 3, 255)}, 233)

    def test_flask_library_is_not_decoded_with_the_cavern_palette(self):
        commands = [['front', 3001, 10, 20, 16, 1, [0, 0, 365, 510], 1]]
        program = {'version': 3, 'level': 3, 'rooms': {'0': commands}}
        data = b'flask'
        colors = {225: (250, 250, 198, 255)}
        sprite = Image.new('RGBA', (12, 16), colors[225])
        with (patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {})),
              patch('pop2.caverns.flask_assets', return_value=({'SHAP': {3001: {'data': data}}}, colors)),
              patch('pop2.caverns.flask_shape', return_value=sprite) as decode):
            art = cavern_room()
        decode.assert_called_once_with(data, colors, 16)
        self.assertEqual(art.foreground.getbbox(), (10, 4, 22, 20))

    def test_native_clip_bounds_apply_to_pixels_and_foreground_masks(self):
        sprite = Image.new('RGBA', (8, 6), (200, 100, 30, 255))
        commands = [['front', 3501, 10, 20, 16, 1, [16, 12, 19, 16]]]
        program = {'version': 2, 'level': 3, 'rooms': {'4': commands}}
        with patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {3501: sprite})):
            art = cavern_room(4)
        self.assertEqual((art.room_id, art.level_kind), (4, 3))
        self.assertEqual(art.foreground.getbbox(), (12, 16, 16, 19))
        self.assertEqual(art.actor_occlusion[1].getbbox(), (12, 16, 16, 19))
        self.assertIsNone(art.actor_occlusion[0].getbbox())
        self.assertEqual(art.foreground.getpixel((12, 16)), (200, 100, 30, 255))

    def test_empty_clip_does_not_draw(self):
        program = {'version': 2, 'level': 3, 'rooms': {
            '0': [['front', 3501, 10, 20, 16, 1, [100, 100, 110, 110]]]}}
        sprite = Image.new('RGBA', (8, 6), (200, 100, 30, 255))
        with patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {3501: sprite})):
            art = cavern_room()
        self.assertIsNone(art.foreground.getbbox())


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class OriginalCavernClimbTests(unittest.TestCase):
    def test_room_four_background_gates_do_not_hide_prince_or_feet(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        for x in (35, 135):
            with self.subTest(x=x):
                scene.jump_to_room(3, row=2, x=x, facing=0)
                expected = scene.player_sprite(scene.action)
                record = scene.frames[scene.action]
                left, top = x - record.offset_x, scene.player_bounds()[1]
                actual = scene.screenshot_viewport
                for sy in range(max(0, 280 - top), expected.height):
                    for sx in range(expected.width):
                        pixel = expected.getpixel((sx, sy))
                        if pixel[3]:
                            self.assertEqual(actual.getpixel((1 + left + sx, top + sy)), pixel)

    def test_room_four_bones_cover_prince_feet_but_pillars_still_cover_him(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(3, row=2, x=95, facing=0)
        guard = scene.combat.visible_guards()[0]
        layer = Image.new('RGBA', (510, 365))
        scene.guard_art.draw(layer, guard.state, 346, guard.palette_variant)
        prince = scene.player_sprite(scene.action)
        left = 95 - scene.frames[scene.action].offset_x
        top = scene.player_bounds()[1]
        overlap = []
        for y in range(top, 347):
            for x in range(left, left + prince.width):
                if layer.getpixel((x, y))[3] and prince.getpixel((x - left, y - top))[3]:
                    overlap.append((x, y))
                    self.assertEqual(scene.screenshot_viewport.getpixel((x + 1, y)),
                                     layer.getpixel((x, y)))
        self.assertTrue(overlap)
        scene.jump_to_room(3, row=2, x=185, facing=0)
        room = scene.room_cache[3]
        mask = room.actor_mask(2, state=scene.sequence_state, bounds=scene.player_bounds(),
                               record=scene.frames[scene.action])
        self.assertEqual(mask.getpixel((183, 310)), 255)

    def test_live_scenery_retention_does_not_capture_the_prince_or_menu(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        for room in (25, 26, 27):
            scene.jump_to_room(room, row=2, x=147, facing=1)
        snapshot = scene.level_renderer.cavern_scenery
        self.assertEqual(snapshot.getpixel((257, 160)), (41, 16, 8, 255))
        self.assertEqual(snapshot.getpixel((307, 40)), (82, 41, 24, 255))
        capture = scene.screenshot_viewport.crop((1, 0, 511, 365))
        self.assertIsNotNone(ImageChops.difference(snapshot.convert('RGB'),
                                                  capture.convert('RGB')).getbbox())
        before = snapshot.tobytes()
        with self.assertRaises(ValueError):
            scene.jump_to_room(25, row=2, x=510)
        self.assertEqual(scene.level_renderer.cavern_scenery.tobytes(), before)
        scene.open_game_menu()
        self.assertEqual(scene.level_renderer.cavern_scenery.tobytes(), before)

    def test_original_room_28_wall_holes_retain_the_room_26_scenery_on_the_native_route(self):
        renderer = LevelRenderer(LevelDefinition.read(load_resource_file('Prince.rsrc'), 3),
                                 preload_room=False)
        snapshots = {room: renderer.room(room).background.tobytes() for room in (25, 26, 27)}
        renderer.enter_room(25)
        original_torch = cavern_room(25, animated=False)
        renderer.remember_scenery(Image.alpha_composite(
            original_torch.background, original_torch.foreground))
        for room in (26, 27):
            art = renderer.enter_room(room)
        frame = Image.alpha_composite(art.background, art.foreground)
        self.assertEqual(frame.getpixel((257, 160)), (41, 16, 8, 255))
        self.assertEqual(frame.getpixel((307, 40)), (82, 41, 24, 255))
        for room, pixels in snapshots.items():
            self.assertEqual(renderer.room(room).background.tobytes(), pixels)
        direct = LevelRenderer(renderer.level, preload_room=False).enter_room(27)
        self.assertEqual(direct.background.getpixel((257, 160)), (0, 0, 0, 255))
        self.assertEqual(direct.background.getpixel((307, 40)), (0, 0, 0, 255))

    def test_upper_platform_hides_the_turban_before_the_catch(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.peaceful = True
        scene.load_level(3)
        scene.jump_to_room(0, row=1, x=323, facing=1)
        scene.in_animation_tick = True
        scene.shift_held = True
        scene.up_key(None)
        for _ in range(25):
            if scene.sequence_state.action == 79:
                break
            RooftopSceneTests.tick(self)
        self.assertEqual(scene.sequence_state.action, 79)
        self.assertEqual(scene.player_bounds(), (304, 102, 333, 191))
        corrected = scene.native_viewport.crop((316, 102, 335, 125))
        with patch.object(CavernRoom, 'draw_actor_foreground', side_effect=lambda frame, *args: frame):
            scene.render()
        previous = scene.native_viewport.crop((316, 102, 335, 125))
        is_blue = lambda color: color[2] > 130 and color[2] > color[0] * 1.5
        def has_blue(image):
            return any(is_blue(image.getpixel((x, y)))
                       for y in range(image.height) for x in range(image.width))

        self.assertTrue(has_blue(previous))
        self.assertFalse(has_blue(corrected))

    def test_climbing_does_not_leave_red_body_pixels_through_the_floor(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.peaceful = True
        scene.load_level(3)
        scene.jump_to_room(0, row=2, x=115, facing=1)
        scene.in_animation_tick = True
        scene.shift_held = True
        scene.up_key(None)
        for _ in range(25):
            if scene.sequence_state.action == 137:
                break
            RooftopSceneTests.tick(self)
        self.assertEqual(scene.sequence_state.action, 137)
        self.assertEqual(scene.player_bounds(), (108, 207, 133, 290))
        self.assertNotEqual(scene.native_viewport.getpixel((117, 234)), (249, 18, 6, 255))
        with patch.object(CavernRoom, 'draw_actor_foreground', side_effect=lambda frame, *args: frame):
            scene.render()
        self.assertEqual(scene.native_viewport.getpixel((117, 234)), (249, 18, 6, 255))

    def test_entry_climb_hides_the_turban_until_it_clears_the_rock_edge(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.peaceful = True
        scene.load_level(3)
        scene.jump_to_room(0, row=2, x=115, facing=1)
        scene.in_animation_tick = True
        scene.shift_held = True
        scene.up_key(None)
        for _ in range(25):
            if scene.sequence_state.action == 136:
                break
            RooftopSceneTests.tick(self)
        self.assertEqual(scene.sequence_state.action, 136)
        self.assertEqual(scene.player_bounds(), (106, 218, 125, 302))
        scenery = scene.room_cache[0].flattened()
        # The native clip top is 245. There must be no actor ink in this
        # slice; the viewport has a one-pixel room origin offset.
        self.assertEqual(scene.native_viewport.crop((107, 218, 127, 229)).tobytes(),
                         scenery.crop((106, 218, 126, 229)).tobytes())
        with patch('pop2.scene_prototype.cavern_clip_top', return_value=0):
            scene.render()
        self.assertNotEqual(scene.native_viewport.crop((107, 218, 127, 229)).tobytes(),
                            scenery.crop((106, 218, 126, 229)).tobytes())


class CavernEntryTests(unittest.TestCase):
    def test_torch_initialization_is_shared_across_visible_fragments_and_preserves_flags(self):
        state = CavernState()
        record = {'room': 0, 'cell': 21, 'foreground': 0x0102}
        with patch('pop2.cavern_state.random.randint', return_value=8) as random:
            state.configure_torches({'0': [record, record], '3': [record]})
        random.assert_called_once_with(0, 8)
        self.assertEqual(state.foreground(0, 21, 0x0102), 0x0108)
        self.assertEqual(state.foreground(0, 22, 0x0102), 0x0102)

    def test_visible_torches_advance_once_per_tick_and_never_repeat_a_frame(self):
        state = CavernState(torches={(0, 21): 0x0108, (4, 3): 2})
        records = [{'room': 0, 'cell': 21}] * 2
        with patch('pop2.cavern_state.random.randint', return_value=8) as random:
            state.advance_torches(records)
        random.assert_called_once_with(0, 8)
        self.assertEqual(state.torches, {(0, 21): 0x0100, (4, 3): 2})
        with patch('pop2.cavern_state.random.randint', return_value=5):
            state.advance_torches(records)
        self.assertEqual(state.torches[0, 21], 0x0105)

    def test_closing_frames_are_extracted_from_the_native_table(self):
        data = bytearray(0x5000)
        struct.pack_into('>2h', data, len(data) - 0x45fc + 10, 32, 200)
        with patch('tools.extract_caverns.expand_a5_data', return_value=bytes(data)):
            frames = exit_closing_frames({})
        self.assertEqual(frames, [{'phase': 79, 'sounds': []},
                                  {'phase': 47, 'sounds': []},
                                  {'phase': 0, 'sounds': [20]}])

    def test_entry_advances_phases_preserves_upper_flags_and_sounds_once(self):
        state = CavernState()
        state.configure_entry({'room': 4, 'cell': 16, 'frames': [
            {'phase': 79, 'sounds': []}, {'phase': 47, 'sounds': []},
            {'phase': 0, 'sounds': [20]}]})
        self.assertEqual(state.foreground(4, 16, 0x7f4f), 0x7f4f)
        self.assertEqual(state.advance(), ())
        self.assertEqual(state.foreground(4, 16, 0x7f4f), 0x7f2f)
        self.assertEqual(state.foreground(4, 17, 0x7f4f), 0x7f4f)
        self.assertEqual(state.advance(), (20,))
        self.assertEqual(state.foreground(4, 16, 0x7f4f), 0x7f00)
        for _ in range(5):
            self.assertEqual(state.advance(), ())


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class OriginalCavernTests(unittest.TestCase):
    def test_dock_waterline_does_not_clip_cavern_actors_in_same_numbered_rooms(self):
        # The scene host imports gameplay tables from the installed game files.
        from pop2.scene_prototype import ScenePrototype

        scene = ScenePrototype.__new__(ScenePrototype)
        scene.game = SimpleNamespace(room_id=0, level=SimpleNamespace(kind=3))
        scene.foreground = Image.new('RGBA', (510, 365))
        background = Image.new('RGBA', (510, 365), 'black')
        for room in (15, 18):
            scene.room_id = room
            for kind, animation, visible in ((3, 0, True), (3, 9, True),
                                             (5, 0, False), (5, 9, True)):
                with self.subTest(room=room, kind=kind, animation=animation):
                    layer = Image.new('RGBA', background.size, 'magenta')
                    state = SimpleNamespace(level_kind=kind, animation_state=animation)
                    frame = scene.composite_actor(background, layer, state=state)
                    self.assertEqual(frame.getpixel((250, 340)),
                                     (255, 0, 255, 255) if visible else (0, 0, 0, 255))
                    self.assertEqual(frame.getpixel((250, 360)),
                                     (255, 0, 255, 255) if kind == 3 else (0, 0, 0, 255))

    def test_entry_records_native_right_wall_shadows_top_border_and_room_clips(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        commands = program['rooms']['0']
        # DrawCaveWall back pass next to pillars, omitted by the old
        # incorrect RightPieceId stub. Coordinates come from PIEC.
        self.assertTrue(any(command[1:4] == [3550, 51, 245] for command in commands))
        self.assertTrue(any(command[1:4] == [3551, 306, 365] for command in commands))
        self.assertTrue(any(command[5] == -1 for command in commands))
        self.assertTrue(any(command[6][3] - command[6][1] > 51 for command in commands))
        for command in commands:
            top, left, bottom, right = command[6]
            self.assertTrue(0 <= left < right <= 510)
            self.assertTrue(0 <= top < bottom <= 365)

    def test_door_threshold_survives_left_floor_without_covering_right_floor(self):
        resources = load_resource_file('Caverns.rsrc')
        palette = decode_ctbl(resources['CTBL'][3500]['data'])
        door = decode_shap(resources['SHAP'][3564]['data'], palette)
        right_floor = decode_shap(resources['SHAP'][3527]['data'], palette)
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        frames = program['entry_exit']['frames']
        for phase in range(len(frames)):
            art = cavern_room(entry_frame=phase)
            with self.subTest(phase=phase):
                for x, y in ((191, 215), (200, 215), (239, 215), (190, 218)):
                    self.assertEqual(art.background.getpixel((x, y)), door.getpixel((x - 186, y - 99)))
                self.assertEqual(art.background.getpixel((240, 218)), right_floor.getpixel((34, 3)))
                # Clean-cut drawing lets the right portal repaint across both cells.
                self.assertTrue(any(command[1] == 3564 and command[6][1] < 204
                                    and command[6][3] > 255 for command in frames[phase]['commands']))

    def test_scene_torch_moves_without_rebuilding_scenery_and_freezes_when_paused(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.advance_level_events()
        scene.advance_level_events()
        scene.render()
        first = scene.native_viewport.copy()
        first_background = scene.background
        key = (0, 20)
        previous = scene.game.caverns.torches[key] & 15
        with patch('pop2.cavern_state.random.randint', return_value=previous):
            scene.advance_level_events()
        self.assertNotEqual(scene.game.caverns.torches[key] & 15, previous)
        scene.render()
        self.assertIs(scene.background, first_background)
        self.assertNotEqual(first.tobytes(), scene.native_viewport.tobytes())
        scene.paused = True
        phases = scene.game.caverns.torches.copy()
        RooftopSceneTests.tick(self, 3)
        self.assertEqual(scene.game.caverns.torches, phases)

    def test_all_native_rooms_render_with_recorded_clip_rectangles(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        self.assertEqual(program['version'], 15)
        self.assertEqual(set(program['rooms']), {str(room) for room in range(32)})
        for room in range(32):
            with self.subTest(room=room):
                commands = program['rooms'][str(room)]
                self.assertTrue(commands)
                self.assertTrue(all(len(command) == 10 and len(command[6]) == 4 for command in commands))
                self.assertTrue(all(command[7] in (1, 4) for command in commands))
                self.assertTrue(all(0 <= command[8] <= 9 and -1 <= command[9] <= 2
                                    for command in commands))
                art = cavern_room(room)
                self.assertEqual(art.background.size, (510, 365))
                self.assertGreater(len(art.background.getcolors(510 * 365)), 20)
                self.assertIsNotNone(art.foreground.getbbox())

    def test_climb_exports_cover_every_room_and_use_native_partial_rectangles(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        self.assertEqual(set(program['climb_redraw']), {str(room) for room in range(32)})
        for room, poses in program['climb_redraw'].items():
            with self.subTest(room=room):
                self.assertEqual(set(poses), {str(action) for action in range(135, 145)})
                self.assertTrue(all(command[0] == 'front' and len(command) == 10
                                    for commands in poses.values() for command in commands))
        command = next(command for command in program['climb_redraw']['0']['137']
                       if command[8:10] == [2, 1])
        self.assertEqual(command, ['front', 3525, 104, 245, 16, 1, [229, 104, 240, 128], 4, 2, 1])

    def test_floor_exports_cover_all_rooms_and_record_native_top_strip(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        self.assertEqual(set(program['floor_redraw']), {str(room) for room in range(32)})
        command = next(command for command in program['floor_redraw']['0']
                       if command[8:10] == [6, 0])
        self.assertEqual(command, ['front', 3528, 315, 125, 16, 0, [100, 315, 125, 357], 4, 6, 0])

    def test_original_flasks_use_prince_shapes_and_small_colored_masks(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        source, colors = flask_assets()
        requests = [command for commands in program['rooms'].values() for command in commands if command[7] == 1]
        self.assertTrue(requests)
        for command in requests:
            self.assertTrue(3001 <= command[1] <= 3033)
            image = flask_shape(source['SHAP'][command[1]]['data'], colors, command[4])
            self.assertLessEqual(image.width, 30)
            self.assertLessEqual(image.height, 64)
            self.assertIsNotNone(image.getbbox())

    def test_unlinked_upper_borders_use_native_scenery_floor_not_collision_wall(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        terrain = LevelMap(LevelDefinition.read(load_resource_file('Prince.rsrc'), 3).data)
        for room in range(32):
            if terrain.neighbor(room, 'up') is not None:
                continue
            with self.subTest(room=room):
                commands = [command for command in program['rooms'][str(room)] if command[9] == -1]
                fronts = [command for command in commands if command[0] == 'front']
                self.assertEqual([command[1] for command in fronts], [3523] * 10)
                self.assertEqual([command[2] for command in fronts], list(range(0, 510, 51)))
                self.assertTrue(all(command[3] == 5 and command[6][0:3:2] == [0, 5]
                                    for command in commands))
                self.assertFalse(any(command[1] == 3537 for command in commands))

    def test_entry_closes_updates_scenery_and_resets_on_restart(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        original = scene.background.copy()
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 79)
        scene.advance_level_events()
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 47)
        scene.advance_level_events()
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 0)
        self.assertIn(20, scene.sequence_state.sound_events)
        self.assertNotEqual(scene.background.tobytes(), original.tobytes())
        scene.sequence_state.sound_events.clear()
        scene.advance_level_events()
        self.assertNotIn(20, scene.sequence_state.sound_events)
        scene.restart_opening(play_sound=False)
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 79)
        self.assertEqual(scene.background.tobytes(), original.tobytes())

    def test_map_covers_all_original_rooms_and_matches_every_link(self):
        terrain = LevelMap(LevelDefinition.read(load_resource_file('Prince.rsrc'), 3).data)
        positions = room_positions(terrain)
        self.assertEqual(set(positions), set(range(32)))
        self.assertEqual(len(set(positions.values())), 32)
        offsets = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}
        for room, (x, y) in positions.items():
            for direction, (dx, dy) in offsets.items():
                neighbor = terrain.neighbor(room, direction)
                if neighbor is not None:
                    self.assertEqual(positions[neighbor], (x + dx, y + dy))

    def test_map_tool_writes_a_nonblank_native_map(self):
        from tools.render_cavern_map import render_map

        with TemporaryDirectory() as directory, patch('PIL.ImageDraw.ImageDraw.text') as text:
            output = render_map(Path(directory) / 'map.png')
            text.assert_not_called()
            with Image.open(output) as image:
                self.assertEqual(image.size, (5610, 2160))
                self.assertIsNotNone(image.getbbox())

    def test_f3_can_load_every_room_and_place_on_accessible_standing_floor(self):
        from pop2.development_entry import STANDING_TILES
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        self.assertEqual(scene.level_renderer.supported_rooms(), list(range(32)))
        entries = scene.level_renderer.screen_entries()
        self.assertEqual(len(entries), 32)
        for label, room in entries.items():
            with self.subTest(room=room):
                scene.jump_to_screen(label)
                self.assertEqual(scene.room_id, room)
                self.assertEqual(scene.room_cache[room].room_id, room)
                if room != scene.game.level.start_room:
                    column = (scene.player_x - 30) // 51
                    self.assertIn(scene.level_map.tile(room, column, scene.terrain_motion.row).kind,
                                  STANDING_TILES)
                self.assertGreater(len(scene.native_viewport.getcolors(512 * 384)), 20)
                self.assertFalse(scene.terrain_motion.dead)

    def test_gameplay_crosses_the_original_link_outside_the_entrance(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(0, row=2, x=22, facing=0)
        scene.horizontal_key(None, -1, True)
        for _ in range(12):
            RooftopSceneTests.tick(self)
            if scene.room_id != 0:
                break
        self.assertEqual(scene.room_id, scene.level_map.neighbor(0, 'left'))
        self.assertEqual(scene.background, scene.room_cache[scene.room_id].background)
        self.assertFalse(scene.terrain_motion.dead)


if __name__ == '__main__':
    unittest.main()


class LooseVariantDeltaTests(unittest.TestCase):
    def test_delta_encoding_round_trips_reordered_and_changed_commands(self):
        from pop2.caverns import delta_commands
        from tools.extract_caverns import encode_delta

        base = [['back', shape, 0, 0] for shape in range(10)]
        changed = base[:3] + [['front', 99, 1, 1]] + base[5:8] + base[9:] + [['back', 7, 0, 0]]
        items = encode_delta(base, changed)
        self.assertEqual(delta_commands(base, items), changed)
        self.assertLess(len(items), len(changed))
        self.assertEqual(delta_commands(base, encode_delta(base, base)), base)


class RuinsPressureDrawingTests(unittest.TestCase):
    def test_a_toggled_ruins_plate_uses_its_exported_commands(self):
        from pop2.caverns import pressure_drawing_commands

        plate = ['back', 3552, 408, 365, 16, 2, [335, 408, 365, 497], 4, 9, 2]
        pressed = ['back', 3552, 408, 366, 16, 2, [336, 408, 365, 497], 4, 9, 2]
        record = {'kind': 5, 'room': 0, 'cell': 29, 'foreground': 1,
                  'commands': [['back', 3552, 4, 9, 2]], 'toggled': [pressed]}
        self.assertEqual(pressure_drawing_commands([plate], [record], (0,), {}), [plate])
        self.assertEqual(pressure_drawing_commands([plate], [record], (1,), {}), [pressed])
        front = ['front', *plate[1:]]
        self.assertEqual(pressure_drawing_commands([front], [record], (1,), {}), [['front', *pressed[1:]]])
