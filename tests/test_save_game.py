import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pop2.game_session import GameResources, GameSession
from pop2.save_game import (MAX_BYTES, SaveGameError, capture_snapshot as capture,
                           read_snapshot as read_save, write_save)
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

    def test_transient_bone_shake_notifications_are_not_replayed_after_loading(self):
        original = GameSession.load(self.resources, 3)
        original.caverns.loose.shake_events.append((14, 2))
        write_save(self.path, capture(original))
        restored, _saved = read_save(self.path, self.resources)
        self.assertEqual(restored.caverns.loose.shake_events, [])

    def test_side_room_skeleton_bank_roundtrip_keeps_selection_and_order(self):
        original = GameSession.load(self.resources, 3)
        original.place(16, 2, 40, 0)
        actor, = original.combat.room_encounters[14][0]
        # Already imported actors remain active even after moving out of the
        # region that permits a fresh import on the next room entry.
        actor.state.target_x = actor.state.current_x = 300
        actor.skeleton.timer = 99
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        restored, = loaded.combat.room_encounters[14][0]
        self.assertEqual((restored.bank_room, restored.bank_slot), (16, 0))
        self.assertIn(restored, loaded.combat.active_guards())
        loaded.combat.advance_guard()
        self.assertEqual(restored.skeleton.timer, 98)

    def test_legacy_actor_records_without_bank_fields_still_load(self):
        original = GameSession.load(self.resources, 3)
        original.place(10, 2, 230, 1)
        value = capture(original)

        def remove_bank(item):
            if isinstance(item, dict):
                if item.get('record') == 'Fighter':
                    item['fields'].pop('bank_room', None)
                    item['fields'].pop('bank_slot', None)
                for child in item.values():
                    remove_bank(child)
            elif isinstance(item, list):
                for child in item:
                    remove_bank(child)

        remove_bank(value)
        write_save(self.path, value)
        loaded, _saved = read_save(self.path, self.resources)
        self.assertEqual((loaded.combat.guards[0].bank_room, loaded.combat.guards[0].bank_slot),
                         (None, 0))
        self.assertIn(loaded.combat.guards[0], loaded.combat.active_guards())

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
        slots = patch('pop2.save_slots.SAVE_DIRECTORY', Path(directory.name))
        slots.start()
        self.addCleanup(slots.stop)

    def tick(self, count=1):
        terrain_tests.RooftopSceneTests.tick(self, count)

    def test_loading_restarts_level_and_rolls_back_unbanked_mega_potion(self):
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(19, row=2, x=180, facing=1)
        scene.combat.player.max_life = scene.combat.player.life = 5
        scene.game.caverns.potions.starting_max_life = 3
        scene.game.caverns.potions.tiles[19, 18] = (1, 0)
        self.tick(3)
        scene.save_game_to(self.path)
        scene.load_level(1)
        scene.load_game_from(self.path)
        self.assertEqual(scene.game.level.number, 3)
        self.assertEqual((scene.combat.player.life, scene.combat.player.max_life), (3, 3))
        self.assertEqual(scene.game.caverns.potions.tiles, {})
        self.assertEqual(scene.room_id, scene.game.level.start_room)
        self.tick(15)
        self.assertTrue(scene.combat.player.alive)

    def test_loading_corrupt_save_does_not_replace_live_session(self):
        before = self.scene.game
        self.path.write_text('not a save')
        with self.assertRaises(SaveGameError):
            self.scene.load_game_from(self.path)
        self.assertIs(self.scene.game, before)

    def test_loading_does_not_restore_route_dependent_pixels_or_room_28(self):
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(26, row=2, x=180, facing=1)
        scene.jump_to_room(27, row=2, x=80, facing=1)
        scene.save_game_to(self.path)
        scene.load_level(1)
        scene.load_game_from(self.path)
        self.assertEqual(scene.room_id, scene.game.level.start_room)
        self.assertNotIn('retained_background', json.loads(self.path.read_text()))

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

    def test_airborne_save_returns_to_entry_without_motion_or_queued_inputs(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_screen('1')
        scene.up_key(None)
        self.tick(2)
        scene.save_game_to(self.path)
        scene.load_level(3)
        scene.load_game_from(self.path)
        self.assertEqual(scene.room_id, scene.game.level.start_room)
        self.assertTrue(scene.opening.active)
        self.assertIsNone(scene.pending_action)

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
        scene.apply_game_action('open')
        browser = scene.game_menu.save_browser
        browser.focus = 27
        self.assertEqual(browser.activate(), 'changed')
        self.assertEqual(browser.confirmation, 'load')
        self.assertEqual(browser.key('Escape'), 'changed')
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

    def test_browser_uses_no_native_dialog_and_cancel_preserves_progress(self):
        scene = self.scene
        before = scene.game
        with patch('pop2.window_controls.filedialog.asksaveasfilename') as picker:
            scene.apply_game_action('save')
        picker.assert_not_called()
        self.assertIs(scene.game, before)
        self.assertTrue(scene.paused)
        self.assertIsNotNone(scene.game_menu)
        scene.apply_game_action(scene.game_menu.key('Escape'))
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)

    def test_successful_save_preserves_an_existing_user_pause(self):
        scene = self.scene
        scene.set_paused(True)
        scene.apply_game_action('save')
        path = scene.game_menu.save_browser.entry.path
        scene.apply_game_action('slot_save')
        self.assertTrue(path.is_file())
        self.assertTrue(scene.paused)
        scene.apply_game_action(scene.game_menu.key('Escape'))
        self.assertTrue(scene.paused)

    def test_save_and_load_slots_use_integrated_confirmation_and_resume_play(self):
        scene = self.scene
        scene.apply_game_action('save')
        path = scene.game_menu.save_browser.entry.path
        scene.apply_game_action(scene.game_menu.key('Return'))
        self.assertTrue(path.is_file())
        self.assertEqual(scene.game_menu.save_browser.status, 'Game saved')
        scene.close_game_menu(resume=True)
        scene.load_level(3)
        scene.apply_game_action('open')
        scene.game_menu.save_browser.focus = 27
        scene.apply_game_action(scene.game_menu.key('Return'))
        scene.apply_game_action(scene.game_menu.key('Right'))
        scene.apply_game_action(scene.game_menu.key('Return'))
        self.assertEqual(scene.game.level.number, 1)
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)

    def test_failed_save_remains_in_browser_without_replacing_progress(self):
        scene = self.scene
        before = scene.game
        scene.apply_game_action('save')
        with patch.object(scene, 'save_game_to', side_effect=OSError('Read only')):
            scene.apply_game_action('slot_save')
        self.assertIs(scene.game, before)
        self.assertTrue(scene.game_menu.save_browser.error)
        self.assertTrue(scene.paused)

    def test_old_snapshot_loads_at_checkpoint_without_rewriting_original_file(self):
        scene = self.scene
        scene.jump_to_room(14, row=0, x=277, facing=0)
        self.tick()
        scene.sequence_state.target_x += 20
        write_save(self.path, capture(scene.game))
        original = self.path.read_bytes()
        scene.load_level(3)
        scene.load_game_from(self.path)
        self.assertEqual((scene.room_id, scene.player_x), (14, 277))
        self.assertEqual(self.path.read_bytes(), original)

    def test_f1_browser_back_returns_to_menu_and_never_resumes_by_accident(self):
        scene = self.scene
        scene.open_game_menu()
        scene.apply_game_action('save')
        scene.apply_game_action(scene.game_menu.key('Escape'))
        self.assertEqual(scene.game_menu.page, 'menu')
        self.assertTrue(scene.paused)

    def test_failed_or_cancelled_overwrite_does_not_change_existing_save(self):
        scene = self.scene
        scene.apply_game_action('save')
        scene.apply_game_action('slot_save')
        browser = scene.game_menu.save_browser
        path = browser.entry.path
        original = path.read_bytes()
        browser.focus = 27
        scene.apply_game_action(browser.activate())
        self.assertEqual(browser.confirmation, 'save')
        scene.apply_game_action(browser.key('Escape'))
        self.assertEqual(path.read_bytes(), original)
        with patch('pop2.save_game.os.replace', side_effect=OSError('Unavailable')):
            scene.apply_game_action('slot_save')
        self.assertEqual(path.read_bytes(), original)

    def test_delete_works_in_browser_and_does_not_touch_current_game(self):
        scene = self.scene
        scene.apply_game_action('save')
        scene.apply_game_action('slot_save')
        browser = scene.game_menu.save_browser
        path, current = browser.entry.path, scene.game
        browser.key('Delete')
        browser.key('Right')
        scene.apply_game_action(browser.key('Return'))
        self.assertFalse(path.exists())
        self.assertIs(scene.game, current)
        self.assertEqual(browser.status, 'Save deleted')

    def test_save_confirmation_blocks_alt_new_game_shortcut(self):
        scene = self.scene
        scene.apply_game_action('save')
        scene.apply_game_action('slot_save')
        browser = scene.game_menu.save_browser
        browser.focus = 27
        browser.activate()
        with patch.object(scene, 'new_game') as new_game:
            event = SimpleNamespace(keysym='n', state=0x20000, char='n')
            self.assertEqual(scene.dev_key_press(event), 'break')
            new_game.assert_not_called()
        self.assertEqual(browser.confirmation, 'save')

    def test_file_changed_since_opening_browser_cannot_replace_live_game(self):
        scene = self.scene
        scene.apply_game_action('save')
        scene.apply_game_action('slot_save')
        browser = scene.game_menu.save_browser
        current = scene.game
        browser.entry.path.write_text('now corrupt')
        scene.apply_game_action('slot_load')
        self.assertIs(scene.game, current)
        self.assertTrue(scene.paused)
        self.assertEqual(browser.error, 'Could not load this save.')

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
