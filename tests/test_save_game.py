import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from PIL import ImageChops

from pop2.game_session import GameResources, GameSession
from pop2.save_game import MAX_BYTES, SaveGameError, capture, read_save, write_save
import tests.test_terrain as terrain_tests


class SaveFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = GameResources.load()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'roundtrip.pop2save'

    def test_all_supported_levels_restore_live_player_runtime_and_world_references(self):
        for number in (1, 2, 3):
            with self.subTest(level=number):
                original = GameSession.load(self.resources, number)
                original.combat.player.max_life = 5
                original.combat.player.life = 4
                original.combat.world_frame = 77
                seed = original.combat.rng.seed
                write_save(self.path, capture(original))
                restored, saved = read_save(self.path, self.resources)
                self.assertEqual(restored.level.number, number)
                self.assertEqual(vars(restored.runtime.state), vars(original.runtime.state))
                self.assertEqual((restored.combat.player.life, restored.combat.player.max_life), (4, 5))
                self.assertEqual(restored.combat.world_frame, 77)
                self.assertEqual(restored.combat.rng.seed, seed)
                self.assertIs(restored.runtime, restored.combat.player.runtime)
                self.assertIs(restored.motion, restored.combat.player.terrain_motion)
                self.assertIs(restored.level_map.caverns, restored.caverns)
                self.assertIs(restored.level_map.desert, restored.desert)
                if number == 1:
                    self.assertIs(restored.opening.runtime, restored.runtime)

    def test_restored_enemy_rng_repeats_the_same_combat_decisions(self):
        original = GameSession.load(self.resources, 3)
        original.place(10, 2, 230, 1)
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        for _ in range(100):
            for game in (original, loaded):
                game.combat.update_guard_alerts()
                game.combat.advance_guard()
                game.combat.resolve_contacts()
            self.assertEqual(vars(original.combat.guards[0].state), vars(loaded.combat.guards[0].state))
            self.assertEqual(original.combat.rng.seed, loaded.combat.rng.seed)

    def test_cavern_potions_gates_debris_and_skeleton_recovery_survive_roundtrip(self):
        original = GameSession.load(self.resources, 3)
        original.place(19, 2, 200, 1)
        world = original.caverns
        world.potions.tiles[19, 18] = (1, 0)
        world.plates.foreground[16, 27] = 0x300 | 192
        world.plates.active[16, 27] = 2
        world.loose.tiles[3, 24] = (0, 3)
        skeleton = original.combat.guards[0]
        skeleton.skeleton.phase = 'collapsing'
        skeleton.skeleton.timer = 87
        write_save(self.path, capture(original, {'sword_drawn': True}, True))
        loaded, saved = read_save(self.path, self.resources)
        self.assertEqual(loaded.caverns.potions.tiles, world.potions.tiles)
        self.assertEqual(loaded.caverns.plates.foreground, world.plates.foreground)
        self.assertEqual(loaded.caverns.plates.active, world.plates.active)
        self.assertEqual(loaded.caverns.loose.tiles, world.loose.tiles)
        self.assertEqual(loaded.combat.guards[0].skeleton.timer, 87)
        self.assertIsNot(loaded.combat.guards[0], skeleton)
        self.assertTrue(saved['controls']['sword_drawn'])
        self.assertTrue(saved['copy_verified'])

    def test_turning_gate_contact_survives_save_and_legacy_saves_use_empty_history(self):
        original = GameSession.load(self.resources, 3)
        original.place(3, 2, 35, 0)
        bounds = (31, 268, 48, 346)
        original.motion.gate_contact_bounds = (3, 2, bounds, bounds)
        original.runtime.state.select(5)
        original.runtime.next_frame()
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertEqual(loaded.motion.gate_contact_bounds, original.motion.gate_contact_bounds)
        self.assertEqual(loaded.runtime.state.animation_state, 7)
        self.assertEqual(vars(loaded.runtime.state), vars(original.runtime.state))
        value = json.loads(self.path.read_text())

        def remove_contact(item):
            if isinstance(item, dict):
                if item.get('record') == 'TerrainMotion':
                    item['fields'].pop('gate_contact_bounds', None)
                for child in item.values():
                    remove_contact(child)
            elif isinstance(item, list):
                for child in item:
                    remove_contact(child)

        remove_contact(value)
        self.path.write_text(json.dumps(value))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertIsNone(loaded.motion.gate_contact_bounds)

    def test_failed_atomic_replace_preserves_previous_save_and_removes_temporary(self):
        self.path.write_bytes(b'old-save')
        with patch('pop2.save_game.os.replace', side_effect=OSError('Disk unavailable')):
            with self.assertRaises(OSError):
                write_save(self.path, {'example': 1})
        self.assertEqual(self.path.read_bytes(), b'old-save')
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_bad_versions_wrong_originals_unknown_records_and_truncation_are_rejected(self):
        original = capture(GameSession.load(self.resources, 3))
        for mutation in ('version', 'hash', 'record', 'truncated', 'oversized'):
            with self.subTest(mutation=mutation):
                value = json.loads(json.dumps(original))
                if mutation == 'version':
                    value['version'] = 999
                elif mutation == 'hash':
                    value['level_sha256'] = 'bad'
                elif mutation == 'record':
                    value['state'] = {'record': 'Path', 'fields': {'name': 'anything'}}
                self.path.write_text(json.dumps(value))
                if mutation == 'truncated':
                    self.path.write_text('{"format":')
                elif mutation == 'oversized':
                    self.path.write_bytes(b'x' * (MAX_BYTES + 1))
                before = random.getstate()
                with self.assertRaises(SaveGameError):
                    read_save(self.path, self.resources)
                self.assertEqual(random.getstate(), before)

    def test_saved_files_contain_no_resource_banks_or_executable_serialization(self):
        game = GameSession.load(self.resources, 3)
        write_save(self.path, capture(game))
        data = self.path.read_text()
        self.assertNotIn('tables', data)
        self.assertNotIn('pickle', data)
        self.assertNotIn('SHAP', data)
        self.assertLess(self.path.stat().st_size, 100000)

    def test_dead_or_completed_sessions_cannot_replace_a_playable_save(self):
        game = GameSession.load(self.resources, 3)
        for dead in (False, True):
            game.combat.player.life = 0 if dead else 3
            game.complete = not dead
            with self.assertRaises(SaveGameError):
                capture(game)


class SaveSceneTests(unittest.TestCase):
    def setUp(self):
        terrain_tests.RooftopSceneTests.setUp(self)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'scene.pop2save'

    def tick(self, count=1):
        terrain_tests.RooftopSceneTests.tick(self, count)

    def test_roundtrip_restores_mega_potion_and_exact_rendered_room(self):
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(19, row=2, x=180, facing=1)
        scene.combat.player.max_life = scene.combat.player.life = 5
        scene.game.caverns.potions.tiles[19, 18] = (1, 0)
        self.tick(3)
        scene.save_game_to(self.path)
        expected = scene.screenshot_viewport.copy()
        scene.load_level(1)
        scene.load_game_from(self.path)
        self.assertEqual(scene.game.level.number, 3)
        self.assertEqual((scene.combat.player.life, scene.combat.player.max_life), (5, 5))
        self.assertEqual(scene.game.caverns.potions.tiles[19, 18], (1, 0))
        self.assertIsNone(ImageChops.difference(expected, scene.screenshot_viewport).getbbox())
        self.tick(15)
        self.assertTrue(scene.combat.player.alive)

    def test_loading_corrupt_save_does_not_replace_live_session(self):
        before = self.scene.game
        self.path.write_text('not a save')
        with self.assertRaises(SaveGameError):
            self.scene.load_game_from(self.path)
        self.assertIs(self.scene.game, before)

    def test_native_retained_background_pixels_survive_loading_room_28(self):
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(26, row=2, x=180, facing=1)
        scene.jump_to_room(27, row=2, x=80, facing=1)
        scene.save_game_to(self.path)
        expected = scene.screenshot_viewport.copy()
        scene.load_level(1)
        scene.load_game_from(self.path)
        self.assertIsNone(ImageChops.difference(expected, scene.screenshot_viewport).getbbox())

    def test_checkpoint_restore_after_loading_keeps_the_saved_world_snapshot(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(14, row=0, x=277, facing=0)
        self.tick()
        self.assertIsNotNone(scene.checkpoint)
        checkpoint = scene.checkpoint.checkpoint
        scene.save_game_to(self.path)
        scene.load_level(3)
        scene.load_game_from(self.path)
        self.assertEqual(scene.checkpoint.checkpoint, checkpoint)
        scene.combat.player.life = 0
        scene.death.counter = 7
        self.assertTrue(scene.restart_after_death())
        self.assertEqual((scene.room_id, scene.player_x), (14, 277))

    def test_airborne_position_and_motion_continue_without_new_held_inputs(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_screen('1')
        scene.up_key(None)
        self.tick(2)
        state = vars(scene.sequence_state).copy()
        motion = vars(scene.terrain_motion).copy()
        scene.save_game_to(self.path)
        scene.load_level(3)
        scene.load_game_from(self.path)
        self.assertEqual(vars(scene.sequence_state), state)
        self.assertEqual(vars(scene.terrain_motion), motion)
        self.tick(30)
        self.assertEqual(scene.sequence_state.current_y, 0)

    def test_bad_retained_pixel_does_not_replace_live_game(self):
        scene = self.scene
        scene.save_game_to(self.path)
        value = json.loads(self.path.read_text())
        value['retained_background'] = [[0, 0, 255, 0, 0, 255]]
        self.path.write_text(json.dumps(value))
        before = scene.game
        with self.assertRaises(SaveGameError):
            scene.load_game_from(self.path)
        self.assertIs(scene.game, before)

    def test_cancelled_load_confirmation_does_not_discard_the_current_game(self):
        scene = self.scene
        scene.save_game_to(self.path)
        before = scene.game
        with (patch('pop2.window_controls.filedialog.askopenfilename', return_value=str(self.path)),
              patch('pop2.window_controls.messagebox.askyesno', return_value=False)):
            scene.apply_game_action('open')
        self.assertIs(scene.game, before)
        self.assertTrue(scene.paused)

    def test_save_is_disabled_during_death_but_open_is_available(self):
        scene = self.scene
        scene.combat.player.life = 0
        scene.open_game_menu()
        scene.refresh_game_menu()
        entries = {item.action: item.enabled for item in scene.game_menu.items}
        self.assertFalse(entries['save'])
        self.assertTrue(entries['open'])

    def test_cancelled_native_dialog_preserves_progress_and_menu_pause(self):
        scene = self.scene
        before = scene.game
        with patch('pop2.window_controls.filedialog.asksaveasfilename', return_value=''):
            scene.apply_game_action('save')
        self.assertIs(scene.game, before)
        self.assertTrue(scene.paused)
        self.assertIsNotNone(scene.game_menu)

    def test_successful_save_preserves_an_existing_user_pause(self):
        scene = self.scene
        scene.set_paused(True)
        with patch('pop2.window_controls.filedialog.asksaveasfilename', return_value=str(self.path)):
            scene.apply_game_action('save')
        self.assertTrue(self.path.is_file())
        self.assertTrue(scene.paused)
        self.assertIsNone(scene.game_menu)

    def test_save_and_open_commands_are_connected_to_file_dialogs(self):
        scene = self.scene
        with patch('pop2.window_controls.filedialog.asksaveasfilename', return_value=str(self.path)):
            scene.apply_game_action('save')
        self.assertTrue(self.path.is_file())
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)
        scene.load_level(3)
        with (patch('pop2.window_controls.filedialog.askopenfilename', return_value=str(self.path)),
              patch('pop2.window_controls.messagebox.askyesno', return_value=True)):
            scene.apply_game_action('open')
        self.assertEqual(scene.game.level.number, 1)
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)

    def test_load_clears_held_keys_and_buffered_actions(self):
        scene = self.scene
        scene.save_game_to(self.path)
        scene.up_held = scene.shift_held = True
        scene.window_keys_down.add('Up')
        scene.load_game_from(self.path)
        self.assertFalse(scene.up_held or scene.shift_held)
        self.assertIsNone(scene.pending_action)


if __name__ == '__main__':
    unittest.main()
