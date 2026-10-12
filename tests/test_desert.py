import random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageChops

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
        desert = DesertState(marked_stone=5, stones=[Stone(13, 0, 0) for _ in range(6)], room=0)
        desert.advance(0, self.state(2), self.record)
        desert.advance(0, self.state(3, 52), self.record)
        self.assertEqual(desert.last_column, 2)
        self.assertEqual(desert.stones[0].phase, 13)
        self.assertIn(53, desert.advance(0, self.state(3), self.record))
        self.assertEqual(desert.stones[0].phase, 11)

    def test_only_marked_stone_remaining_opens_the_exit_with_native_cues(self):
        stones = [Stone(0, 0, 0) for _ in range(6)]
        stones[3].phase = 13
        desert = DesertState(marked_stone=3, stones=stones, room=0)
        cues = []
        for _ in range(50):
            cues.extend(desert.advance(0, self.state(8), self.record))
        self.assertTrue(desert.exit_open)
        self.assertEqual(desert.stones[3].phase, 0)
        self.assertEqual(cues, [46, 55, 53, 47] + [17] * 20)

    def test_stone_delays_start_on_cave_entry_after_waiting_on_the_beach(self):
        desert = DesertState(marked_stone=3)
        for _ in range(200):
            self.assertEqual(desert.advance(1, self.state(8), self.record), [])
        self.assertEqual([(stone.phase, stone.delay) for stone in desert.stones], [(0, 0)] * 6)
        with patch('pop2.desert_state.random.randint', return_value=21):
            self.assertEqual(desert.advance(0, self.state(8), self.record), [])
            self.assertEqual([stone.delay for stone in desert.stones], [21] * 6)
            for _ in range(21):
                self.assertEqual(desert.advance(0, self.state(8), self.record), [])
        self.assertEqual([stone.phase for stone in desert.stones], [0] * 6)
        self.assertEqual(desert.advance(0, self.state(8), self.record), [52] * 6)
        self.assertEqual([stone.phase for stone in desert.stones], [1] * 6)

    def test_room_reentry_rearms_sunken_stones_and_clears_puzzle_failure(self):
        desert = DesertState(marked_stone=2, room=0, failed=True)
        desert.stones[0] = Stone(13, 0, 0)
        desert.stones[1] = Stone(5, 0, -1)
        desert.enter_room(1)
        with patch('pop2.desert_state.random.randint', return_value=31):
            desert.enter_room(0)
        self.assertFalse(desert.failed)
        self.assertEqual(desert.last_column, -1)
        self.assertEqual((desert.stones[0].phase, desert.stones[0].direction), (13, 0))
        self.assertEqual((desert.stones[1].phase, desert.stones[1].direction), (5, -1))
        self.assertEqual([(s.phase, s.delay, s.direction) for s in desert.stones[2:]],
                         [(0, 31, 1)] * 4)

    def test_activated_stones_animate_offscreen_and_dead_delays_wait(self):
        desert = DesertState(room=1)
        desert.stones[0] = Stone(2, 0, 1)
        desert.stones[1] = Stone(0, 21, 1)
        desert.advance(1, self.state(8), self.record, alive=False)
        self.assertEqual(desert.stones[0].phase, 3)
        self.assertEqual(desert.stones[1].delay, 21)
        desert.advance(1, self.state(8), self.record)
        self.assertEqual((desert.stones[0].phase, desert.stones[1].delay), (4, 20))

    def test_gate_movement_sound_waits_for_puzzle_effect_and_stops_at_twenty(self):
        desert = DesertState(room=0, gate_active=True)
        audio = Mock()
        audio.sound_playing.return_value = True
        self.assertEqual(desert.advance(0, self.state(8), self.record, audio=audio), [])
        self.assertEqual(desert.gate, 1)
        audio.sound_playing.return_value = False
        self.assertEqual(desert.advance(0, self.state(8), self.record, audio=audio), [17])
        for _ in range(18):
            desert.advance(0, self.state(8), self.record, audio=audio)
        self.assertTrue(desert.exit_open)
        audio.stop_sound.assert_not_called()
        desert.advance(0, self.state(8), self.record, audio=audio)
        audio.stop_sound.assert_called_once_with(17)
        self.assertFalse(desert.gate_active)

    def test_sequence_twenty_seven_freezes_rise_delays_across_animation_links(self):
        desert = DesertState(room=0)
        desert.stones[0] = Stone(0, 21, 1)
        state = self.state(8)
        state.sequence_id, state.source_sequence_id = 2, 27
        desert.advance(0, state, self.record)
        self.assertEqual(desert.stones[0].delay, 21)
        state.source_sequence_id = 2
        desert.advance(0, state, self.record)
        self.assertEqual(desert.stones[0].delay, 20)

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
                     'SHAP': {8000 + i: {'data': b''} for i in range(15)},
                     'NFNT': {24878: {'data': b''}}}
        with patch('pop2.copy_protection.decode_ctbl', return_value={}), \
                patch('pop2.copy_protection.decode_shap', return_value=Image.new('RGBA', (50, 50))), \
                patch('pop2.copy_protection.indexed_shape', return_value=Image.new('L', (2, 2))), \
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

    def test_native_symbol_rectangles_start_without_a_selection(self):
        challenge = self.challenge()
        self.assertEqual(challenge.hit(80, 131), 0)
        self.assertEqual(challenge.hit(384, 207), 9)
        self.assertIsNone(challenge.hit(0, 0))
        self.assertIsNone(challenge.focus)

    def test_symbol_outline_uses_native_color_and_exclusive_bounds(self):
        class PixelFont:
            def text(self, _text, color=(255, 255, 255, 255)):
                return Image.new('RGBA', (1, 1), color)

        challenge = CopyProtection.__new__(CopyProtection)
        challenge.border = Image.new('RGBA', (512, 384), (123, 0, 0, 255))
        challenge.message = 'Select the symbol on page %d'
        challenge.answers = ((8, 0),)
        challenge.challenge = 0
        challenge.font = PixelFont()
        challenge.palette = {16: (238, 135, 33, 255), 27: (245, 220, 140, 255)}
        challenge.symbols = ()
        challenge.focus = 0

        image = challenge.draw(None, None)

        self.assertEqual(image.getpixel((75, 126)), challenge.palette[27])
        self.assertEqual(image.getpixel((134, 185)), challenge.palette[27])
        self.assertEqual(image.getpixel((135, 185)), (123, 0, 0, 255))

    def test_copy_protection_text_shadow_uses_macintosh_offsets(self):
        class PixelFont:
            def text(self, _text, color=(255, 255, 255, 255)):
                return Image.new('RGBA', (1, 1), color)

        challenge = CopyProtection.__new__(CopyProtection)
        challenge.border = Image.new('RGBA', (512, 384), (123, 0, 0, 255))
        challenge.message = 'Select the symbol on page %d'
        challenge.answers = ((8, 0),)
        challenge.challenge = 0
        challenge.font = PixelFont()
        challenge.palette = {16: (238, 135, 33, 255), 27: (245, 220, 140, 255)}
        challenge.symbols = ()
        challenge.focus = None

        image = challenge.draw(None, None)

        self.assertEqual(image.getpixel((255, 50)), challenge.palette[27])
        self.assertEqual(image.getpixel((256, 50)), challenge.palette[16])
        self.assertEqual(image.getpixel((258, 50)), (0, 0, 0, 255))
        self.assertNotEqual(image.getpixel((255, 51)), challenge.palette[27])

    def test_fullscreen_cursor_is_visible_for_copy_challenge_only(self):
        host = WindowControls()
        host.canvas = Mock()
        host.fullscreen = True
        host.game_menu = host.dev_menu = None
        host.copy_challenge = object()
        host.copy_pointer_held = False

        host.update_cursor_visibility()
        self.assertEqual(host.canvas.configure.call_args.kwargs, {'cursor': ''})

        host.copy_challenge = None
        host.update_cursor_visibility()
        self.assertEqual(host.canvas.configure.call_args.kwargs, {'cursor': 'none'})

    def test_copy_symbol_highlight_tracks_only_while_button_held_and_selects_on_release(self):
        class Challenge:
            focus = None

            @staticmethod
            def hit(x, _y):
                return x if x in (0, 1) else None

            def choose(self, symbol):
                self.chosen = symbol

        host = WindowControls()
        host.copy_challenge = Challenge()
        host.copy_pointer_held = False
        host.game_menu = host.dev_menu = None
        host.paused = False
        host.canvas = Mock()
        host.render = Mock()
        host.resolve_copy_challenge = Mock()
        event = SimpleNamespace(num=1, x=0, y=0)

        with patch.object(host, 'dev_pointer', return_value=(0, 0)):
            host.dev_hover(event)
        self.assertIsNone(host.copy_challenge.focus)

        with patch.object(host, 'dev_pointer', return_value=(0, 0)):
            host.dev_click(event)
        self.assertTrue(host.copy_pointer_held)
        self.assertEqual(host.copy_challenge.focus, 0)
        self.assertFalse(hasattr(host.copy_challenge, 'chosen'))
        host.resolve_copy_challenge.assert_not_called()

        with patch.object(host, 'dev_pointer', return_value=(1, 0)):
            host.dev_hover(event)
        self.assertEqual(host.copy_challenge.focus, 1)

        with patch.object(host, 'dev_pointer', return_value=(1, 0)):
            host.dev_release(event)
        self.assertFalse(host.copy_pointer_held)
        self.assertEqual(host.copy_challenge.chosen, 1)
        host.resolve_copy_challenge.assert_called_once_with()

    def test_paused_dialog_ignores_keys_without_selecting_an_answer(self):
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
        host.set_paused.assert_not_called()
        host.resolve_copy_challenge.assert_not_called()
        self.assertFalse(host.copy_challenge.accepted)
        self.assertNotIn('Return', host.pause_resume_keys)

    def test_dialog_consumes_keyboard_input_and_disables_development(self):
        host = WindowControls()
        host.copy_challenge = self.challenge()
        host.game_menu = host.dev_menu = None
        host.paused = False
        host.level_map = object()
        host.window_keys_down = set()
        host.pause_resume_keys = set()
        self.assertFalse(host.development_available())
        self.assertEqual(host.dev_key_press(SimpleNamespace(keysym='Escape', state=0, char='')),
                         'break')


@unittest.skipUnless((ASSET_DIR / 'Caverns.rsrc').is_file(), 'Imported game resources required')
class OriginalDesertTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.load_level(2)
        self.scene.peaceful = True

    def test_cave_entry_has_no_ground_symbol_and_keeps_the_foreground_cliff(self):
        scene = self.scene
        scene.jump_to_room(0, x=440)
        art = scene.level_renderer.desert_rooms[0]
        back = art.draw(art.room.background.copy(), 0, scene.game.desert)
        ground = (100, 200, 445, 250)
        self.assertIsNone(ImageChops.difference(back.convert('RGB'),
                                              art.room.background.convert('RGB')).crop(ground).getbbox())
        self.assertIsNotNone(art.room.foreground.getbbox())

    def test_door_and_symbol_use_native_horizontal_offsets_in_the_background(self):
        scene = self.scene
        scene.jump_to_room(0, x=440)
        art = scene.level_renderer.desert_rooms[0]
        desert = scene.game.desert
        desert.symbol = 1
        for phase in (0, 1, 10, 20):
            with self.subTest(phase=phase):
                desert.gate = phase
                back = art.draw(art.room.background.copy(), 0, desert)
                expected = art.room.background.copy()
                # DrawDsrtExit 18:074c-0788: recovered CUST 2 and 16 calls.
                for shape_id, bottom, x in ((4002, 248, 13 - phase * 3),
                                             (4017, 158, 41 - phase * 3)):
                    sprite = art.shapes[shape_id]
                    expected.paste(sprite, (x, bottom - sprite.height), sprite)
                self.assertIsNone(ImageChops.difference(back.convert('RGB'),
                                                      expected.convert('RGB')).getbbox())
                front = art.draw(back.copy(), 0, desert, front=True)
                self.assertIsNone(ImageChops.difference(front.convert('RGB'),
                                                      back.convert('RGB')).getbbox())

    def test_marked_stone_symbol_appears_at_nine_then_uses_the_raised_variant(self):
        scene = self.scene
        scene.jump_to_room(0, x=440)
        art = scene.level_renderer.desert_rooms[0]
        desert = scene.game.desert
        desert.symbol, desert.marked_stone = 1, 2
        blank = art.draw(art.room.background.copy(), 0, desert)
        for phase, symbol_id, symbol_bottom in ((8, None, None), (9, 4023, 241),
                                                  (10, 4020, 238), (13, 4020, 234)):
            with self.subTest(phase=phase):
                desert.stones[2].phase = phase
                actual = art.draw(art.room.background.copy(), 0, desert)
                expected = blank.copy()
                record = art.records[phase + 2]
                sprite = art.shapes[4000 + record[0]]
                expected.paste(sprite, (204 + record[2], 240 + record[1] - sprite.height), sprite)
                if symbol_id is not None:
                    symbol = art.shapes[symbol_id]
                    expected.paste(symbol, (234, symbol_bottom - symbol.height), symbol)
                self.assertIsNone(ImageChops.difference(actual.convert('RGB'),
                                                      expected.convert('RGB')).getbbox())

    def test_actual_controls_solve_stones_and_open_the_cavern(self):
        from tests.test_terrain import RooftopSceneTests

        scene = self.scene
        scene.jump_to_room(0, x=440, facing=0)
        desert = scene.game.desert
        desert.marked_stone = 2
        RooftopSceneTests.tick(self, 45)
        scene.horizontal_key(None, -1, True)
        RooftopSceneTests.tick(self, 7)
        scene.horizontal_key(None, -1, False)
        RooftopSceneTests.tick(self, 40)
        self.assertEqual(desert.last_column, 5)
        scene.up_key(None)
        scene.horizontal_key(None, -1, True)
        scene.set_key_state('up', False)
        scene.horizontal_key(None, -1, False)
        RooftopSceneTests.tick(self, 35)
        self.assertFalse(desert.failed)
        self.assertEqual(desert.last_column, 2)
        scene.set_key_state('shift', True)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        RooftopSceneTests.tick(self, 70)
        self.assertTrue(desert.exit_open)
        self.assertEqual([stone.phase for stone in desert.stones], [0] * 6)
        self.assertFalse(scene.terrain_motion.dead)

    def test_supplied_manual_matches_every_original_answer(self):
        challenge = CopyProtection(self.scene.resources.prince)
        pages = ((5, 7), (2, 12), (1, 19), (8, 17), (4, 16),
                 (6, 15), (11, 14), (3,), (9, 13), (10, 18))
        self.assertEqual(set(challenge.answers), {(page, symbol) for symbol, group in enumerate(pages)
                                                for page in group})

    def test_challenge_blocks_world_and_acceptance_preserves_puzzle_state(self):
        scene = self.scene
        scene.jump_to_room(0, x=440)
        scene.game.desert.gate = 20
        scene.player_x = -1
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
