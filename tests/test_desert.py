import random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.copy_protection import CopyProtection
from pop2.desert_state import DesertState, Stone
from pop2.paths import ASSET_DIR
from pop2.window_controls import WindowControls


class StoneTests(unittest.TestCase):
    def state(self, column, pose=15):
        return SimpleNamespace(target_x=column * 51 + 26, facing=1, action=pose)

    record = SimpleNamespace(offset_x=0, aux=0)

    def test_auto_raise_waits_for_native_delay_then_stops_at_thirteen(self):
        stone = Stone(delay=21)
        for _ in range(21):
            stone.advance()
        self.assertEqual(stone.phase, 0)
        for _ in range(30):
            stone.advance()
        self.assertEqual((stone.phase, stone.direction), (13, 0))

    def test_sinking_cancels_delayed_rise(self):
        stone = Stone(delay=24)
        stone.sink()
        for _ in range(50):
            stone.advance()
        self.assertEqual((stone.phase, stone.delay, stone.direction), (0, 0, 0))

    def test_leaving_a_stone_sinks_it_but_airborne_poses_do_not_update_contact(self):
        desert = DesertState(marked_stone=5, stones=[Stone(13, 0, 0) for _ in range(6)])
        desert.advance(0, self.state(2), self.record)
        desert.advance(0, self.state(3, 52), self.record)
        self.assertEqual(desert.last_column, 2)
        self.assertEqual(desert.stones[0].phase, 13)
        self.assertIn(53, desert.advance(0, self.state(3), self.record))
        self.assertEqual(desert.stones[0].phase, 12)

    def test_only_marked_stone_remaining_opens_the_exit_with_native_cues(self):
        stones = [Stone(0, 0, 0) for _ in range(6)]
        stones[3].phase = 13
        desert = DesertState(marked_stone=3, stones=stones)
        cues = []
        for _ in range(50):
            cues.extend(desert.advance(0, self.state(8), self.record))
        self.assertTrue(desert.exit_open)
        self.assertEqual(desert.stones[3].phase, 0)
        self.assertEqual(cues, [46, 55, 47])

    def test_standing_on_marked_stone_fails_but_jumping_over_it_does_not(self):
        desert = DesertState(marked_stone=2)
        desert.advance(0, self.state(4, 52), self.record)
        self.assertFalse(desert.failed)
        desert.advance(0, self.state(4), self.record)
        self.assertTrue(desert.failed)
        for stone in desert.stones:
            stone.phase, stone.delay, stone.direction = 0, 0, 0
        desert.stones[2].phase = 13
        for _ in range(60):
            desert.advance(0, self.state(8), self.record)
        self.assertFalse(desert.exit_open)

    def test_death_and_shore_do_not_solve_the_puzzle(self):
        desert = DesertState(marked_stone=2)
        for _ in range(50):
            desert.advance(1, self.state(4), self.record)
        phases = [stone.phase for stone in desert.stones]
        for _ in range(50):
            desert.advance(0, self.state(4), self.record, alive=False)
        self.assertFalse(desert.failed)
        self.assertEqual([stone.phase for stone in desert.stones], phases)


class CopyProtectionTests(unittest.TestCase):
    def challenge(self):
        resources = {'COPY': {8005: {'data': struct.pack('>5H', 2, 1, 3, 2, 7)}},
                     'TEXT': {8005: {'data': b'\1Select the symbol on page %d\0'}},
                     'CTBL': {8000: {'data': b''}},
                     'SHAP': {8005 + i: {'data': b''} for i in range(10)},
                     'NFNT': {24878: {'data': b''}}}
        with patch('pop2.copy_protection.decode_ctbl', return_value={}), \
                patch('pop2.copy_protection.decode_shap', return_value=Image.new('RGBA', (50, 50))), \
                patch('pop2.copy_protection.MacintoshFont'):
            return CopyProtection(resources, random.Random(12))

    def test_original_table_drives_acceptance(self):
        challenge = self.challenge()
        challenge.choose(challenge.answers[challenge.challenge][1])
        self.assertTrue(challenge.accepted)
        challenge.choose(0)
        self.assertEqual(challenge.attempts, 0)

    def test_three_wrong_answers_fail_and_pages_do_not_repeat_immediately(self):
        challenge = self.challenge()
        for attempt in range(3):
            previous = challenge.challenge
            challenge.choose(0)
            self.assertEqual(challenge.attempts, attempt + 1)
            if attempt < 2:
                self.assertNotEqual(challenge.challenge, previous)
        self.assertTrue(challenge.failed)
        self.assertFalse(challenge.accepted)

    def test_native_symbol_rectangles_and_keyboard_selection(self):
        challenge = self.challenge()
        self.assertEqual(challenge.hit(80, 131), 0)
        self.assertEqual(challenge.hit(384, 207), 9)
        self.assertIsNone(challenge.hit(0, 0))
        challenge.key('Left')
        self.assertEqual(challenge.focus, 9)
        challenge.key('Down')
        self.assertEqual(challenge.focus, 4)

    def test_paused_dialog_resumes_without_selecting_an_answer(self):
        from unittest.mock import Mock

        host = WindowControls()
        host.copy_challenge = self.challenge()
        host.game_menu = host.dev_menu = None
        host.paused = True
        host.window_keys_down = set()
        host.pause_resume_keys = set()
        host.set_paused = Mock()
        host.resolve_copy_challenge = Mock()
        host.dev_key_press(SimpleNamespace(keysym='Return', state=0, char='\r'))
        host.set_paused.assert_called_once_with(False)
        host.resolve_copy_challenge.assert_not_called()
        self.assertFalse(host.copy_challenge.accepted)
        self.assertIn('Return', host.pause_resume_keys)

    def test_dialog_keeps_escape_available_and_disables_development(self):
        host = WindowControls()
        host.copy_challenge = self.challenge()
        host.game_menu = host.dev_menu = None
        host.paused = False
        host.level_map = object()
        host.window_keys_down = set()
        host.pause_resume_keys = set()
        self.assertFalse(host.development_available())
        self.assertIsNone(host.dev_key_press(SimpleNamespace(keysym='Escape', state=0, char='')))


@unittest.skipUnless((ASSET_DIR / 'Caverns.rsrc').is_file(), 'Imported game resources required')
class OriginalDesertTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.load_level(2)
        self.scene.peaceful = True

    def test_supplied_manual_matches_every_original_answer(self):
        challenge = CopyProtection(self.scene.resources.prince)
        pages = ((5, 7), (2, 12), (1, 19), (8, 17), (4, 16),
                 (6, 15), (11, 14), (3,), (9, 13), (10, 18))
        self.assertEqual(set(challenge.answers), {(page, symbol) for symbol, group in enumerate(pages)
                                                for page in group})

    def test_challenge_blocks_world_and_acceptance_preserves_puzzle_state(self):
        scene = self.scene
        scene.jump_to_room(0, x=440)
        scene.advance_level_events()
        challenge, desert = scene.copy_challenge, scene.game.desert
        self.assertIsNotNone(challenge)
        before = scene.sequence_state.action
        scene.advance_animation()
        self.assertEqual(scene.action, before)
        challenge.choose(challenge.answers[challenge.challenge][1])
        scene.resolve_copy_challenge()
        self.assertTrue(scene.copy_verified)
        self.assertIsNone(scene.copy_challenge)
        self.assertIs(scene.game.desert, desert)

    def test_f1_bypass_keeps_stones_and_does_not_open_exit(self):
        scene = self.scene
        scene.jump_to_room(0, x=440)
        scene.advance_level_events()
        desert = scene.game.desert
        scene.apply_game_action('copy_protection')
        self.assertIsNone(scene.copy_challenge)
        self.assertIs(scene.game.desert, desert)
        self.assertFalse(desert.exit_open)
        self.assertFalse(scene.copy_verified)

    def test_open_cave_exit_enters_level_three_with_health_capacity(self):
        scene = self.scene
        scene.copy_protection_enabled = False
        scene.jump_to_room(0, x=90)
        scene.game.desert.gate = 20
        scene.combat.player.max_life = 5
        scene.sequence_state.current_x = scene.sequence_state.target_x = scene.player_x = -1
        scene.advance_level_events()
        self.assertEqual((scene.game.level.number, scene.room_id), (3, 0))
        self.assertEqual(scene.combat.player.life, 5)
        self.assertIsNone(scene.game.desert)
        self.assertGreater(len(scene.native_viewport.getcolors(512 * 384)), 100)

    def test_closed_gate_blocks_walk_and_open_gate_does_not(self):
        terrain = self.scene.level_map
        bounds = (60, 160, 80, 226)
        self.assertEqual(terrain.wall_correction(0, 90, 80, bounds, facing=0), 92)
        self.scene.game.desert.gate = 20
        self.assertEqual(terrain.wall_correction(0, 90, 80, bounds, facing=0), 80)

    def test_cave_music_and_puzzle_effects_use_separate_audio_channels(self):
        from unittest.mock import Mock

        scene = self.scene
        scene.copy_protection_enabled = False
        scene.jump_to_room(0, x=440)
        scene.audio = Mock(music_busy=False, effect_busy=False)
        scene.game.desert.stones = [Stone(0, 0, 0) for _ in range(6)]
        scene.game.desert.stones[scene.game.desert.marked_stone].phase = 13
        scene.game.desert.counter = 6
        scene.advance_level_events()
        scene.audio.add_song.assert_called_once_with(46)
        scene.audio.reset_mock()
        scene.game.desert.counter = 9
        scene.advance_level_events()
        self.assertIn(55, scene.sequence_state.sound_events)
        scene.audio.add_song.assert_not_called()
        scene.advance_audio()
        scene.audio.stop_sound.assert_called_once_with(51)
        scene.audio.add_song.assert_called_once_with(50, ambient=True)

    def test_running_from_arrival_reaches_stones_without_loading_dummy_rooms(self):
        from tests.test_terrain import RooftopSceneTests

        scene = self.scene
        scene.copy_protection_enabled = False
        RooftopSceneTests.tick(self, 50)
        self.assertEqual(scene.action, 15)
        scene.horizontal_key(None, -1, True)
        RooftopSceneTests.tick(self, 130)
        self.assertEqual(scene.room_id, 0)
        self.assertFalse(scene.terrain_motion.dead)
        self.assertTrue(scene.game.desert.failed)
        self.assertGreaterEqual(scene.player_x, 80)
