"""The cave ambience made faster without changing a pixel of it.

The room reading was rewritten for speed: the stalactites, the smoothing of the
dark, the steady wall behind a flame, the palette search and the firelight are
each checked here against the way they were worked out before, and the rooms
next door are read ahead while the game waits for its next frame.
"""

import random
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import numpy
from PIL import Image, ImageFilter

from pop2.cavern_ambience import (
    AIR_LUMINANCE, HEIGHT, TIP_CLEARANCE, TIP_LENGTH, TIP_LUMINANCE, TIP_TAPER, TIP_WIDTH, WIDTH, Colours,
    analyze_room, majority, stalactite_tips, steady_wall,
)
from pop2.firelight import Relief, rock_height
from pop2.paths import ASSET_DIR

CAVERNS_INSTALLED = (ASSET_DIR / 'caverns_level4.json').is_file()


def tips_as_before(shades):
    """stalactite_tips as it was: pixel by pixel."""
    def dark(x, y):
        return shades[y * WIDTH + x] < AIR_LUMINANCE

    found = []
    for x in range(TIP_WIDTH, WIDTH - TIP_WIDTH):
        for y in range(TIP_LENGTH, HEIGHT - TIP_CLEARANCE):
            if (shades[y * WIDTH + x] >= TIP_LUMINANCE and dark(x, y + 1)
                    and dark(x - TIP_WIDTH, y - 1) and dark(x + TIP_WIDTH, y - 1)
                    and dark(x - TIP_TAPER, y - TIP_LENGTH) and dark(x + TIP_TAPER, y - TIP_LENGTH)
                    and all(dark(x, below) for below in range(y + 1, y + TIP_CLEARANCE))):
                length = 0
                while length < y and not dark(x, y - length):
                    length += 1
                if length >= TIP_LENGTH:
                    found.append((x, y, length))
    return [tip for tip in found if not any(
        abs(other[0] - tip[0]) <= TIP_WIDTH and abs(other[1] - tip[1]) <= 2 * TIP_LENGTH
        and other[1] > tip[1] for other in found)]


def stalactite_field(seed):
    """Dark wall hung with thin bright spikes, some at the very edges of the rows."""
    rng = random.Random(seed)
    shades = bytearray(rng.randrange(0, AIR_LUMINANCE) for _ in range(WIDTH * HEIGHT))
    for _ in range(60):
        x = rng.choice((rng.randrange(WIDTH), rng.randrange(8), WIDTH - 1 - rng.randrange(8)))
        bottom = rng.randrange(TIP_LENGTH, HEIGHT - 1)
        for y in range(max(0, bottom - rng.randrange(4, 30)), bottom + 1):
            width = rng.randrange(1, 3) if y > bottom - 3 else rng.randrange(1, 6)
            for column in range(x - width // 2, x + width // 2 + 1):
                if 0 <= column < WIDTH:
                    shades[y * WIDTH + column] = rng.randrange(TIP_LUMINANCE - 4, 256)
    return bytes(shades)


def wall_as_before(frames, flame, unlit):
    wall = numpy.array(frames[0])
    codes = frames[..., 0].astype(numpy.int64) << 16 | frames[..., 1].astype(numpy.int64) << 8 | frames[..., 2]
    for row, column in numpy.argwhere((codes != codes[0]).any(axis=0) | flame.any(axis=0)):
        shows = codes[:, row, column][~flame[:, row, column]]
        if len(shows):
            colours, counts = numpy.unique(shows, return_counts=True)
            kept = int(colours[counts.argmax()])
            wall[row, column, :3] = kept >> 16, (kept >> 8) & 255, kept & 255
        else:
            wall[row, column] = unlit[row, column]
    return wall


class SameResultTests(unittest.TestCase):
    def test_stalactites_are_found_as_before(self):
        for seed in range(3):
            shades = stalactite_field(seed)
            expected = tips_as_before(shades)
            self.assertTrue(expected, seed)
            self.assertEqual(stalactite_tips(shades), expected, seed)

    def test_a_taper_past_the_edge_reads_the_next_row_as_before(self):
        shades = bytearray(bytes([10]) * (WIDTH * HEIGHT))
        # A spike at the right edge: its taper reads the start of the next row.
        for y in range(50, 71):
            shades[y * WIDTH + WIDTH - 5] = 150
        for value in (10, 150):
            shades[42 * WIDTH + WIDTH + 1] = value   # x + TIP_TAPER at y - TIP_LENGTH
            shades[43 * WIDTH + 1] = value
            self.assertEqual(stalactite_tips(bytes(shades)), tips_as_before(bytes(shades)), value)

    def test_the_dark_is_smoothed_as_the_median_filter_did(self):
        rng = numpy.random.default_rng(4)
        for height, width in ((HEIGHT, WIDTH), (9, 7), (5, 5), (3, 11)):
            picked = rng.random((height, width)) < rng.random()
            image = Image.fromarray(picked.astype(numpy.uint8) * 255, 'L')
            expected = numpy.asarray(image.filter(ImageFilter.MedianFilter(5))) > 0
            numpy.testing.assert_array_equal(majority(picked, 5), expected)

    def test_the_wall_behind_a_flame_is_the_same(self):
        rng = numpy.random.default_rng(7)
        for _ in range(5):
            # Few colours, so that two often show as often as each other.
            frames = rng.integers(0, 3, (9, 12, 10, 4), dtype=numpy.uint8) * 60
            flame = rng.random((9, 12, 10)) < 0.4
            flame[:, 0, 0] = True   # Behind the flame in every frame.
            unlit = rng.integers(0, 255, (12, 10, 4), dtype=numpy.uint8)
            numpy.testing.assert_array_equal(steady_wall(frames, flame, unlit),
                                             wall_as_before(frames, flame, unlit))

    def test_the_nearest_colour_is_the_same_ties_and_all(self):
        rng = numpy.random.default_rng(2)
        palette = {index: (*rng.integers(0, 256, 3), 255) for index in range(60)}
        palette[60] = palette[61] = (10, 10, 10, 255)
        palette.update({62: (0, 0, 0, 255), 63: (2, 0, 0, 255), 64: (0, 0, 2, 255)})
        colours = Colours(palette)
        values = numpy.concatenate((rng.integers(0, 256, (500, 3)), [[1, 0, 0], [1, 0, 1], [0, 0, 1]]))
        before = (((values[:, None, :] - colours.rgb[None, :, :]) * (2, 3, 2)) ** 2).sum(axis=2).argmin(axis=1)
        numpy.testing.assert_array_equal(colours.closest(values.astype(numpy.int32)), before)

    def test_cells_of_flame_together_cast_the_light_each_casts_alone(self):
        rng = numpy.random.default_rng(3)
        relief = Relief(rock_height(rng.random((90, 110))).astype(numpy.float32))
        places = rng.random((19, 2)) * (110, 90)
        shares = rng.random(19)
        alone = sum(share * relief.light_from(x, y) for (x, y), share in zip(places, shares))
        numpy.testing.assert_array_equal(relief.flame(places, shares), alone)

    def test_a_room_without_torches_is_not_drawn_with_its_gates_up(self):
        art = Mock()
        art.background = Image.new('RGBA', (WIDTH, HEIGHT), (20, 10, 10, 255))
        art.foreground = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        terrain = Mock()
        terrain.tile.return_value = Mock(kind=0)
        palette = {index: (index, index, index, 255) for index in range(256)}
        raised = Mock()
        analyze_room({}, 0, art, terrain, palette, resources={}, shapes={}, raised=raised)
        raised.assert_not_called()


@unittest.skipUnless(CAVERNS_INSTALLED, 'Imported cavern resources required')
class ReadAheadTests(unittest.TestCase):
    def setUp(self):
        from pop2.cavern_state import CavernState
        from pop2.level_data import LevelDefinition
        from pop2.level_rendering import LevelRenderer
        from pop2.render_opening import load_resource_file
        from pop2.terrain import LevelMap

        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        self.renderer = LevelRenderer(level, preload_room=False)
        self.world = CavernState()
        program = self.renderer.cavern_program
        self.world.configure_entry(program.get('entry_exit'))
        self.world.configure_torches(program.get('torches', {}))
        self.world.configure_lava(program.get('lava'))
        self.terrain = LevelMap(level.data)

    def read_ahead_fully(self, room):
        steps = 0
        while self.renderer.read_ambience_ahead(room, self.world, self.terrain):
            steps += 1
            self.assertLess(steps, 40)
        return steps

    def test_a_room_read_ahead_is_what_walking_in_reads(self):
        from pop2.cavern_ambience import room_air

        renderer = self.renderer
        renderer.enter_room(16, self.world)
        renderer.advance_ambience(16, self.terrain)
        self.assertGreater(self.read_ahead_fully(16), 0)
        self.assertTrue(renderer.ambience_ahead)
        for near, (seen, ahead) in tuple(renderer.ambience_ahead.items()):
            renderer.enter_room(near, self.world)
            # The room drawn ahead is the one shown, not drawn a second time.
            self.assertIs(renderer.rooms[near], renderer.cavern_frames[seen[0]])
            fresh = room_air(4, near, renderer.rooms[near], self.terrain, renderer.room_with_gates_up(near))
            renderer.advance_ambience(near, self.terrain)
            self.assertIs(renderer.ambience_air[near], ahead, near)
            self.assertEqual(ahead.open, fresh.open)
            self.assertEqual(ahead.covered, fresh.covered)
            self.assertEqual(ahead.drips, fresh.drips)
            self.assertEqual(ahead.flames, fresh.flames)
            self.assertEqual(len(ahead.torches), len(fresh.torches))
            for one, other in zip(ahead.torches, fresh.torches):
                numpy.testing.assert_array_equal(one.wall, other.wall)
                numpy.testing.assert_array_equal(one.light.falloff, other.light.falloff)
                numpy.testing.assert_array_equal(one.lit_air, other.lit_air)
            for one, other in zip(ahead.pool_glows, fresh.pool_glows):
                numpy.testing.assert_array_equal(one.falloff, other.falloff)

    def test_a_room_that_changed_since_is_read_again(self):
        renderer = self.renderer
        renderer.enter_room(16, self.world)
        renderer.advance_ambience(16, self.terrain)
        self.read_ahead_fully(16)
        near = next(iter(renderer.ambience_ahead))
        seen, ahead = renderer.ambience_ahead[near]
        # As if a tile of it had changed since it was read.
        renderer.ambience_ahead[near] = ((seen[0], (99,) + seen[1][1:]), ahead)
        renderer.enter_room(near, self.world)
        renderer.advance_ambience(near, self.terrain)
        self.assertIsNot(renderer.ambience_air[near], ahead)
        self.assertNotIn(near, renderer.ambience_ahead)

    def test_only_rooms_next_door_and_each_once(self):
        renderer = self.renderer
        renderer.enter_room(16, self.world)
        renderer.advance_ambience(16, self.terrain)
        self.read_ahead_fully(16)
        doors = {self.terrain.neighbor(16, way) for way in ('left', 'right', 'up', 'down')} - {None}
        self.assertTrue(set(renderer.ambience_ahead) <= doors)
        self.assertFalse(renderer.read_ambience_ahead(16, self.world, self.terrain))


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file() and CAVERNS_INSTALLED, 'Imported game resources required')
class NextDoorEntryTests(unittest.TestCase):
    """Walking into the room next door costs no more than a frame without the ambience."""

    def setUp(self):
        from pop2.scene_prototype import ScenePrototype

        original_tk = tk.Tk

        def hidden_root():
            root = original_tk()
            root.withdraw()
            return root

        with patch('pop2.window_controls.tk.Tk', hidden_root):
            self.scene = ScenePrototype()
        self.scene.root.after_cancel(self.scene.animation_after_id)
        self.scene.animation_after_id = None
        self.scene.schedule_next_animation = lambda: None
        self.scene.combat.rng = random.Random(1)
        self.addCleanup(self.scene.root.destroy)
        self.now = 1000.0

    def frame_ms(self):
        self.now += 0.101
        with patch('pop2.scene_prototype.time.perf_counter', return_value=self.now):
            start = time.perf_counter_ns()
            self.scene.advance_animation()
            return (time.perf_counter_ns() - start) / 1e6

    def test_spare_time_reads_the_rooms_next_door(self):
        from pop2.scene_prototype import ANIMATION_INTERVAL_MS

        scene = self.scene
        scene.cave_ambience_enabled = True
        scene.load_level(4)
        if scene.opening is not None:
            scene.opening.active = False
        self.frame_ms()
        terrain, renderer = scene.level_map, scene.level_renderer
        rooms = sorted(renderer.supported_rooms())
        entries = []
        for room in rooms[:12]:
            scene.jump_to_room(room, 1, 200, 1)
            self.frame_ms()
            # The spare time of a few frames.
            scene.next_animation_at = time.perf_counter() + 1
            for _ in range(8):
                scene.use_spare_time()
            near = next((terrain.neighbor(room, way) for way in ('left', 'right', 'up', 'down')
                         if terrain.neighbor(room, way) in renderer.ambience_ahead), None)
            if near is None:
                continue
            scene.jump_to_room(near, 1, 200, 1)
            entries.append(self.frame_ms())
        self.assertGreater(len(entries), 5)
        entries.sort()
        self.assertLess(entries[len(entries) // 2], ANIMATION_INTERVAL_MS / 2, entries)

    def test_no_reading_without_spare_time(self):
        scene = self.scene
        scene.cave_ambience_enabled = True
        scene.load_level(4)
        scene.next_animation_at = time.perf_counter() + 0.01
        with patch.object(scene.level_renderer, 'read_ambience_ahead') as read:
            scene.use_spare_time()
        read.assert_not_called()
        scene.next_animation_at = time.perf_counter() + 1
        with patch.object(scene.level_renderer, 'read_ambience_ahead') as read:
            scene.use_spare_time()
        read.assert_called_once()

    def test_rooms_next_door_are_read_only_with_the_ambience_on(self):
        scene = self.scene
        scene.load_level(4)
        scene.next_animation_at = time.perf_counter() + 1
        scene.cave_ambience_enabled = False
        with patch.object(scene.level_renderer, 'read_ambience_ahead') as read, \
                patch.object(scene, 'ready_next_level') as ready:
            scene.use_spare_time()
        read.assert_not_called()
        ready.assert_called_once()
        with patch.object(scene.root, 'after_idle', return_value='id') as idle:
            scene.schedule_spare_work()
            scene.schedule_spare_work()
        idle.assert_called_once()

    def ready_level_three(self):
        scene = self.scene
        scene.cave_ambience_enabled = True
        scene.load_level(2)
        if scene.opening is not None:
            scene.opening.active = False
        self.frame_ms()
        for _ in range(20):
            scene.next_animation_at = time.perf_counter() + 1
            scene.use_spare_time()
        self.assertTrue(scene.next_level.done)
        return scene.next_level.renderer

    def test_the_first_cave_level_is_ready_before_the_prince_walks_in(self):
        from pop2.cavern_ambience import room_air
        from pop2.level_rendering import LevelRenderer

        scene = self.scene
        prepared = self.ready_level_three()
        self.assertIsNotNone(prepared)
        built = []
        original = LevelRenderer.built_room

        def build(renderer, key):
            built.append(key)
            return original(renderer, key)

        with patch.object(LevelRenderer, 'built_room', build):
            scene.load_level(3)
            self.frame_ms()
            self.frame_ms()
        self.assertIs(scene.level_renderer, prepared)
        self.assertIs(prepared.level, scene.game.level)
        # Nothing drawn again: the start room and the door's first frames were ready.
        self.assertEqual(built, [])
        room = scene.room_id
        air = prepared.ambience_air[room]
        fresh = room_air(3, room, prepared.rooms[room], scene.level_map, prepared.room_with_gates_up(room))
        self.assertEqual((air.open, air.covered, air.drips, air.flames),
                         (fresh.open, fresh.covered, fresh.drips, fresh.flames))
        for one, other in zip(air.torches, fresh.torches, strict=True):
            numpy.testing.assert_array_equal(one.light.falloff, other.light.falloff)

    def test_another_level_is_built_as_before(self):
        scene = self.scene
        prepared = self.ready_level_three()
        scene.load_level(5)
        self.assertIsNot(scene.level_renderer, prepared)

if __name__ == '__main__':
    unittest.main()
