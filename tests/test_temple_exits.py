"""Temple stairs clip the Prince and hand off after the real exit-song gate."""

from dataclasses import replace
from itertools import product
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.caverns import (CavernRoom, cavern_assets, cavern_command_sprite,
                          cavern_exit_clip, clipped_sprite)
from pop2.paths import ASSET_DIR
from pop2.render_opening import ROOM_HEIGHT, ROOM_ORIGIN_X, ROOM_WIDTH
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap


DOORS = ((10, 18, 15), (11, 23, 25), (12, 6, 23),
         (13, 27, 16), (13, 31, 12), (13, 31, 15))
INSTALLED = all((ASSET_DIR / f'temple_level{number}.json').is_file() for number in (10, 11, 12, 13))
ACTOR_MASK = CavernRoom.actor_mask


def without_exit_contour(room, *args, **kwargs):
    return ACTOR_MASK(replace(room, exit_foreground=()), *args, **kwargs)


class TempleExitClipTests(unittest.TestCase):
    def test_frame_promotion_follows_stair_poses_without_the_height_gate(self):
        empty = Image.new('L', (510, 365))
        cover = Image.new('RGBA', empty.size)
        cover.paste((180, 60, 20, 255), (320, 130, 340, 220))
        room = CavernRoom(Image.new('RGBA', empty.size), Image.new('RGBA', empty.size),
                          {1: empty}, (), (), 0, 2, {}, exit_foreground=((cover, (0, 0)),))
        for actor, pose, y in product((0, 2), (216, 217, 226, 227), (0, -24, -25, -42)):
            with self.subTest(actor=actor, pose=pose, y=y):
                state = SequenceState(70, actor_type=actor, action=pose, current_y=y, level_kind=2)
                frame = room.draw_actor_foreground(Image.new('RGBA', empty.size),
                                                   state, (300, 120, 350, 220))
                self.assertIsNone(frame.getbbox())
                mask = room.actor_mask(1, state=state, bounds=(300, 120, 350, 220))
                self.assertEqual(mask.getbbox(), cover.getbbox()
                                 if actor == 0 and 217 <= pose <= 226 else None)
        self.assertIsNone(room.actor_mask(1).getbbox())

    def test_temple_uses_its_native_rectangle_and_strict_stair_height(self):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2186, 2)
        struct.pack_into('>H', level, 60 + 15 * 2, 17)
        terrain = LevelMap(level)
        state = SequenceState(70, action=224, target_x=280, facing=0,
                              actor_type=0, level_kind=2, current_y=-24)
        record = SimpleNamespace(offset_x=0, aux=0)
        self.assertIsNone(cavern_exit_clip(terrain, 1, 1, state, record))
        state.current_y = -25
        self.assertEqual(cavern_exit_clip(terrain, 1, 1, state, record), (133, 335))
        struct.pack_into('>H', level, 60 + 14 * 2, 16)
        state.target_x = 230
        self.assertEqual(cavern_exit_clip(terrain, 1, 1, state, record), (133, 335))
        for pose in (216, 227):
            state.action = pose
            self.assertIsNone(cavern_exit_clip(terrain, 1, 1, state, record))


@unittest.skipUnless(INSTALLED, 'Imported temple artwork required')
class TempleExitSceneTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(10, draw=True)
        self.scene = self.harness.scene
        self.addCleanup(self.harness.close)

    def open_exit(self, number, room, cell):
        scene = self.scene
        scene.load_level(number)
        scene.game.story.tree_stage = 0
        scene.game.story.minutes = 75
        row, column = divmod(cell, 10)
        value = scene.level_map.tile(room, column, row).foreground
        scene.game.caverns.plates.foreground[(room, cell)] = (value & 0xff00) | 79
        scene.jump_to_room(room, row, column * 51 + 24, 1)
        self.assertTrue(scene.start_cavern_exit())

    def complete_stairs(self):
        for _ in range(40):
            if self.scene.level_complete:
                break
            self.harness.tick()
        self.assertTrue(self.scene.level_complete)
        self.assertIsNotNone(self.scene.game.exit, 'Temple completion must schedule its exit, not freeze')
        self.assertEqual(self.scene.game.exit.song, 187)

    def test_room_32_exit_leaves_the_fallen_birdhead_in_front(self):
        from pop2.combat import select_sequence

        scene = self.scene
        scene.audio = None
        scene.peaceful = False
        self.open_exit(13, 31, 12)
        combat = scene.combat
        point, = combat.generation_points
        point.countdown = 0
        combat.world_frame = 1
        with patch.object(combat, '_supporting_column', return_value=4):
            combat.generate_opponents()
        guard, = combat.guards
        point.remaining = 0
        guard.life = 0
        guard.entry_x = None
        guard.state.facing = 1
        guard.state.current_x = guard.state.target_x = 125
        select_sequence(guard, 85)
        for _ in range(20):
            guard.runtime.next_frame()
            if guard.state.action == 185:
                break
        self.assertEqual(guard.state.action, 185)

        original = scene.composite_actor

        def without_player(frame, layer, row=None, bottom=None, state=None, bounds=None, record=None):
            if state is not None and state.actor_type == 0:
                layer = Image.new('RGBA', layer.size)
            return original(frame, layer, row, bottom, state, bounds, record)

        with patch.object(scene, 'composite_actor', side_effect=without_player):
            for pose in range(217, 227):
                self.assertEqual(scene.sequence_state.action, pose)
                scene.render()
                actual = scene.native_viewport.convert('RGB')
                with patch.object(CavernRoom, 'draw_actor_foreground',
                                  CavernRoom.draw_actor_floor_foreground):
                    scene.render()
                    expected = scene.native_viewport.convert('RGB')
                    with patch.object(combat, 'visible_guards', return_value=()):
                        scene.render()
                        empty = scene.native_viewport.convert('RGB')
                corpse = ImageChops.difference(expected, empty)
                room = scene.room_cache[31]
                self.assertTrue(any(
                    ImageChops.multiply(
                        corpse.crop((ROOM_ORIGIN_X + x, y, ROOM_ORIGIN_X + x + stone.width,
                                     y + stone.height)),
                        stone.getchannel('A').convert('RGB')).getbbox()
                    for stone, (x, y) in room.exit_foreground))
                with self.subTest(pose=pose):
                    self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
                self.harness.tick()

    def test_each_door_keeps_its_stone_pixels_in_front_through_the_whole_entry(self):
        scene = self.scene
        scene.audio = None
        observed, exposed = set(), set()
        original = scene.composite_actor
        room_rect = (ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + ROOM_WIDTH, ROOM_HEIGHT)

        def without_player(frame, layer, row=None, bottom=None, state=None, bounds=None, record=None):
            if state is not None and state.actor_type == 0:
                layer = Image.new('RGBA', layer.size)
            return original(frame, layer, row, bottom, state, bounds, record)

        for site in DOORS:
            with self.subTest(site=site):
                number, room, _cell = site
                self.open_exit(*site)
                program, resources, palette, shapes = cavern_assets(number)
                cover = Image.new('L', (510, 365))
                for command in program['rooms'][str(room)]:
                    if command[:2] == ['back', 3579] and command[7] == 4:
                        sprite, position = clipped_sprite(
                            cavern_command_sprite(command, resources, palette, shapes), command)
                        cover.paste(sprite.getchannel('A'), position)
                self.assertIsNotNone(cover.getbbox())
                for _ in range(36):
                    state = scene.sequence_state
                    if 217 <= state.action <= 226:
                        scene.render()
                        fixed = scene.native_viewport.crop(room_rect).convert('RGB')
                        # Remove the sprite, retaining the floor repaint.
                        with patch.object(scene, 'composite_actor', side_effect=without_player):
                            scene.render()
                            stone = scene.native_viewport.crop(room_rect).convert('RGB')
                        difference = ImageChops.difference(fixed, stone)
                        for channel in difference.split():
                            self.assertIsNone(ImageChops.multiply(channel, cover).getbbox(),
                                              f'Prince overwrites door stone at pose {state.action}')
                        observed.add((site, state.action))
                        # A control with this promotion disabled must expose
                        # actual Prince pixels on the jamb, as in the report.
                        with patch.object(CavernRoom, 'actor_mask', without_exit_contour):
                            scene.render()
                            unmasked = scene.native_viewport.crop(room_rect).convert('RGB')
                        difference = ImageChops.difference(unmasked, stone)
                        if any(ImageChops.multiply(channel, cover).getbbox()
                               for channel in difference.split()):
                            exposed.add(site)
                    if scene.level_complete:
                        break
                    self.harness.tick()
        self.assertEqual({site for site, _pose in observed}, set(DOORS))
        self.assertEqual({pose for _site, pose in observed}, set(range(217, 227)))
        self.assertEqual(exposed, set(DOORS))

    def test_entry_occlusion_keeps_the_floor_corner_and_other_uncovered_scenery_stable(self):
        scene = self.scene
        scene.audio = None
        room_rect = (ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + ROOM_WIDTH, ROOM_HEIGHT)
        checked = set()
        for site in DOORS:
            with self.subTest(site=site):
                self.open_exit(*site)
                row, column = divmod(site[2], 10)
                corners = [(column * 51 + dx, row * 120 + dy)
                           for dx, dy in ((88, 96), (89, 96), (87, 97))]
                for _ in range(36):
                    state = scene.sequence_state
                    if 217 <= state.action <= 226:
                        scene.render()
                        fixed = scene.native_viewport.crop(room_rect).convert('RGB')
                        with patch.object(CavernRoom, 'actor_mask', without_exit_contour):
                            scene.render()
                            ordinary = scene.native_viewport.crop(room_rect).convert('RGB')
                        for point in corners:
                            self.assertEqual(fixed.getpixel(point), ordinary.getpixel(point),
                                             f'Door entry changes the floor corner at {point}')
                        difference = ImageChops.difference(fixed, ordinary)
                        left, top, right, bottom = scene.player_bounds()
                        difference.paste((0, 0, 0), (max(0, left), max(0, top),
                                                    min(ROOM_WIDTH, right + 1),
                                                    min(ROOM_HEIGHT, bottom + 1)))
                        self.assertIsNone(difference.getbbox(),
                                          f'Door entry repaints scenery outside the Prince at pose {state.action}')
                        checked.add(site)
                    if scene.level_complete:
                        break
                    self.harness.tick()
        self.assertEqual(checked, set(DOORS))

    def test_all_six_temple_exit_doors_clip_real_late_stair_pixels(self):
        scene = self.scene
        scene.audio = None
        original = scene.composite_actor
        observed, changed = set(), set()
        site = None

        def composite(frame, layer, row=None, bottom=None, state=None, bounds=None, record=None):
            result = original(frame, layer, row, bottom, state, bounds, record)
            if (state is not None and state.actor_type == 0 and 217 <= state.action <= 226
                    and state.current_y < -24):
                clip = cavern_exit_clip(scene.level_map, scene.room_id, row, state, record)
                self.assertIsNotNone(clip)
                ink = layer.getchannel('A').getbbox()
                if ink is not None:
                    self.assertGreaterEqual(ink[1], clip[0])
                    self.assertLessEqual(ink[2], clip[1])
                observed.add(site)
            return result

        with patch.object(scene, 'composite_actor', side_effect=composite):
            for site in DOORS:
                with self.subTest(site=site):
                    self.open_exit(*site)
                    for _ in range(36):
                        state = scene.sequence_state
                        before = replace(state)
                        scene.render()
                        fixed = scene.native_viewport.copy()
                        if 217 <= state.action <= 226 and state.current_y < -24:
                            with (patch('pop2.scene_prototype.cavern_exit_clip', return_value=None),
                                  patch.object(scene, 'composite_actor', wraps=original)):
                                scene.render()
                                previous = scene.native_viewport.copy()
                            if ImageChops.difference(fixed.convert('RGB'), previous.convert('RGB')).getbbox():
                                changed.add(site)
                        self.assertEqual(state, before)
                        if scene.level_complete:
                            break
                        self.harness.tick()
        self.assertEqual(observed, set(DOORS))
        self.assertEqual(changed, set(DOORS))

    def test_each_transition_waits_for_the_song_then_loads_the_next_level(self):
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback

        scene = self.scene
        for number, room, cell in DOORS[:3]:
            with self.subTest(level=number):
                audio = scene.audio = AudioEngine(playback=object())
                backend = audio.playback = TimedPlayback(audio.cues)
                self.open_exit(number, room, cell)
                self.complete_stairs()
                audio.flush()
                self.assertEqual(audio.current_music, 187)
                self.assertTrue(audio.music_busy)
                self.harness.tick()
                self.assertEqual(scene.game.level.number, number)
                self.assertTrue(scene.level_complete)
                # The terminal transition must preserve the established health
                # and campaign clock, then release the completed/exit state.
                scene.combat.player.life = scene.combat.player.max_life = 5
                story = scene.game.story
                for _ in range(300):
                    backend.advance(.101)
                    self.harness.tick()
                    if scene.game.level.number != number:
                        break
                self.assertEqual(scene.game.level.number, number + 1)
                self.assertIs(scene.game.story, story)
                self.assertEqual((scene.combat.player.life, scene.combat.player.max_life), (5, 5))
                self.assertFalse(scene.level_complete)
                self.assertIsNone(scene.game.exit)
                self.assertIsNone(scene.intro)
                self.assertEqual(scene.room_id, scene.game.level.start_room)

    def test_a_gate_shutting_during_the_exit_song_is_heard(self):
        # FrameAdv keeps running while the end song plays (2:6100-6168).
        # The port moved the gate but only drained its cue: nothing flushed
        # it until the next level, so the gate shut silently.
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback

        scene = self.scene
        audio = scene.audio = AudioEngine(playback=object())
        backend = audio.playback = TimedPlayback(audio.cues)
        played, play = [], backend.play
        backend.play = lambda bus, cue, **_options: (played.append((bus, cue)), play(bus, cue))
        number, room, cell = DOORS[0]
        self.open_exit(number, room, cell)
        self.complete_stairs()
        gate = next((key, tile) for key in ((r, c) for r in range(32) for c in range(30))
                    if (tile := scene.level_map.tile(key[0], key[1] % 10, key[1] // 10)).kind == 4)
        key, tile = gate
        plates = scene.game.caverns.plates
        plates.foreground[key] = (tile.foreground & 0xff00) | 120
        plates.add(key, 4)
        played.clear()
        for _ in range(20):
            backend.advance(.101)
            self.harness.tick()
        self.assertTrue(scene.level_complete)
        self.assertTrue(any(bus in ('mechanism', 'closing') for bus, _cue in played), played)

    def test_silent_transitions_use_duration_fallback_and_keep_the_tree_handoff(self):
        scene = self.scene
        scene.audio = None
        for number, room, cell in DOORS[:3]:
            with self.subTest(level=number):
                self.open_exit(number, room, cell)
                scene.game.story.tree_stage = -1
                self.complete_stairs()
                for _ in range(300):
                    self.harness.tick()
                    if scene.intro is not None:
                        break
                self.assertEqual(scene.game.level.number, number)
                self.assertEqual(scene.attract_stage, 'tree')
                self.assertEqual(scene.next_level_after_tree, number + 1)
                self.assertEqual(scene.tree_variant, 1)
                self.assertFalse(scene.level_complete)
                scene.finish_tree(skipped=True)
                self.assertEqual(scene.game.level.number, number + 1)
                self.assertFalse(scene.level_complete)
                self.assertIsNone(scene.game.exit)
