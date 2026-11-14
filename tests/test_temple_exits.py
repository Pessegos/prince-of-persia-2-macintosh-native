"""Temple stairs clip the Prince and hand off after the real exit-song gate."""

from dataclasses import replace
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import ImageChops

from pop2.caverns import cavern_exit_clip
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap


DOORS = ((10, 18, 15), (11, 23, 25), (12, 6, 23),
         (13, 27, 16), (13, 31, 12), (13, 31, 15))
INSTALLED = all((ASSET_DIR / f'temple_level{number}.json').is_file() for number in (10, 11, 12, 13))


class TempleExitClipTests(unittest.TestCase):
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
