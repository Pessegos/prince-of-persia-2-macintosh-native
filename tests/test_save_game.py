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
        for number in (1, 2, 3, 4):
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

    def test_inactive_guard_record_roundtrip_resumes_native_cold_reload(self):
        from pop2.combat import select_sequence

        original = GameSession.load(self.resources, 1)
        original.place(3, 1, 250, 0)
        actor = original.combat.guards[0]
        actor.max_life, actor.life, actor.sword_drawn = 3, 2, True
        select_sequence(actor, 227)
        actor.runtime.next_frame()
        original.combat.enter_room(31, 1)
        original.room_id = original.motion.room = 31
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        restored = loaded.combat.room_encounters[3][0][0]
        self.assertEqual(restored.guard_record, actor.guard_record)
        loaded.combat.enter_room(3, 1)
        self.assertEqual((restored.life, restored.selected_sequence, restored.sword_drawn), (3, 77, False))
        self.assertFalse(restored.guard_record.pending)

    def test_legacy_guard_actor_without_record_or_native_alive_still_loads(self):
        original = GameSession.load(self.resources, 1)
        value = capture(original)

        def remove_fields(item):
            if isinstance(item, dict):
                if item.get('record') == 'Fighter':
                    item['fields'].pop('guard_record', None)
                    item['fields'].pop('native_alive', None)
                for child in item.values():
                    remove_fields(child)
            elif isinstance(item, list):
                for child in item:
                    remove_fields(child)

        remove_fields(value)
        write_save(self.path, value)
        loaded, _saved = read_save(self.path, self.resources)
        self.assertIsNone(loaded.combat.guards[0].guard_record)
        self.assertIsNone(loaded.combat.guards[0].native_alive)

    def test_corrupt_guard_room_records_are_rejected(self):
        from dataclasses import replace
        from pop2.opponent_records import GuardRoomRecord

        for invalid in ({'sequence': 99999}, {'cursor': 999}, {'life': 2},
                        {'height': 10001}, {'cell': 90}):
            with self.subTest(invalid=invalid):
                original = GameSession.load(self.resources, 1)
                original.combat.guards[0].guard_record = replace(
                    GuardRoomRecord(77, 0, 1, False, 12), **invalid)
                write_save(self.path, capture(original))
                with self.assertRaises(SaveGameError):
                    read_save(self.path, self.resources)

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

    def test_inactive_skeleton_room_record_survives_snapshot_and_resumes_native_reload(self):
        original = GameSession.load(self.resources, 3)
        original.place(10, 2, 230, 1)
        actor = original.combat.guards[0]
        actor.life, actor.sword_drawn, actor.skeleton.phase = 2, True, 'active'
        original.combat.enter_room(0, 2)
        original.room_id = original.motion.room = 0
        self.assertEqual(actor.skeleton.room_record.cursor, 0)
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        restored = loaded.combat.room_encounters[10][0][0]
        self.assertEqual(restored.skeleton.room_record, actor.skeleton.room_record)
        loaded.combat.enter_room(10, 2)
        self.assertEqual((restored.life, restored.selected_sequence, restored.skeleton.timer), (0, 112, 0))
        self.assertIsNone(restored.skeleton.room_record)

    def test_legacy_skeleton_records_default_to_no_pending_reload(self):
        original = GameSession.load(self.resources, 3)
        original.place(10, 2, 230, 1)
        value = capture(original)

        def remove_fields(item):
            if isinstance(item, dict):
                if item.get('record') == 'Skeleton':
                    item['fields'].pop('room_record', None)
                    item['fields'].pop('native_alive', None)
                for child in item.values():
                    remove_fields(child)
            elif isinstance(item, list):
                for child in item:
                    remove_fields(child)

        remove_fields(value)
        write_save(self.path, value)
        loaded, _saved = read_save(self.path, self.resources)
        skeleton = loaded.combat.guards[0].skeleton
        self.assertIsNone(skeleton.room_record)
        self.assertFalse(skeleton.native_alive)

    def test_corrupt_skeleton_room_record_fields_are_rejected(self):
        from pop2.skeleton import SkeletonRoomRecord

        for sequence, cursor, life in ((99999, 0, 0), (119, -1, 0), (119, 999, 0), (119, 1, 4)):
            with self.subTest(sequence=sequence, cursor=cursor, life=life):
                original = GameSession.load(self.resources, 3)
                original.place(10, 2, 230, 1)
                original.combat.guards[0].skeleton.room_record = SkeletonRoomRecord(
                    sequence, cursor, life, False)
                write_save(self.path, capture(original))
                with self.assertRaises(SaveGameError):
                    read_save(self.path, self.resources)

    def test_saved_skeleton_cell_is_validated_without_breaking_older_snapshots(self):
        from pop2.skeleton import SkeletonRoomRecord

        for cell in (-20, 90, 999):
            with self.subTest(cell=cell):
                original = GameSession.load(self.resources, 3)
                original.place(10, 2, 230, 1)
                original.combat.guards[0].skeleton.room_record = SkeletonRoomRecord(119, 1, 0, False, cell)
                write_save(self.path, capture(original))
                with self.assertRaises(SaveGameError):
                    read_save(self.path, self.resources)

    def test_valid_saved_skeleton_cells_survive_snapshot_and_restore_the_native_row(self):
        from pop2.skeleton import SkeletonRoomRecord

        for cell in (-19, -10, -1, 0, 29, 30, 89):
            with self.subTest(cell=cell):
                original = GameSession.load(self.resources, 3)
                original.place(10, 2, 230, 1)
                original.combat.guards[0].skeleton.room_record = SkeletonRoomRecord(119, 1, 0, False, cell)
                write_save(self.path, capture(original))
                loaded, _saved = read_save(self.path, self.resources)
                actor = loaded.combat.guards[0]
                self.assertEqual(actor.skeleton.room_record.cell, cell)
                actor.skeleton.restore_room(actor, 0)
                expected = abs(cell) // 10 * (-1 if cell < 0 else 1) - int(cell < 0)
                self.assertEqual(actor.row, expected)

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

    def create_save(self, name='My journey'):
        scene = self.scene
        if scene.game_menu is None or scene.game_menu.page != 'saves':
            scene.apply_game_action('save')
        browser = scene.game_menu.save_browser
        browser.selected, browser.focus = 0, 29
        scene.apply_game_action(browser.activate())
        self.assertEqual(browser.editing, 'create')
        browser.draft = name
        scene.apply_game_action(browser.key('Return'))
        self.assertFalse(browser.error, browser.error)
        return browser.entry.path

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
        with patch('tkinter.filedialog.asksaveasfilename') as picker:
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
        path = self.create_save()
        self.assertTrue(path.is_file())
        self.assertTrue(scene.paused)
        scene.apply_game_action(scene.game_menu.key('Escape'))
        self.assertTrue(scene.paused)

    def test_save_and_load_slots_use_integrated_confirmation_and_resume_play(self):
        scene = self.scene
        scene.apply_game_action('save')
        path = self.create_save()
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
        scene.game_menu.save_browser.edit_name('create')
        with patch.object(scene, 'save_game_to', side_effect=OSError('Read only')):
            scene.apply_game_action('slot_create')
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
        self.create_save()
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
        self.create_save()
        browser = scene.game_menu.save_browser
        path, current = browser.entry.path, scene.game
        browser.key('Delete')
        browser.key('Right')
        scene.apply_game_action(browser.key('Return'))
        self.assertFalse(path.exists())
        self.assertIs(scene.game, current)
        self.assertEqual(browser.status, 'Save deleted')
        self.assertIsNone(scene.active_save_path)
        self.assertIsNone(browser.active_path)

    def test_active_save_is_selected_and_scrolled_into_view_in_both_modes(self):
        scene = self.scene
        paths = [self.path.with_name(f'journey-{i:02}.pop2save') for i in range(20)]
        for i, path in enumerate(paths):
            scene.save_game_to(path, f'Journey {i}')
        scene.load_game_from(paths[0])
        self.assertEqual(scene.active_save_path, paths[0])
        for load in (False, True):
            scene.open_save_browser(load=load)
            browser = scene.game_menu.save_browser
            self.assertEqual(browser.entry.path, paths[0])
            self.assertEqual(browser.active_path, paths[0])
            self.assertEqual(browser.focus, 100 + browser.selected)
            self.assertGreater(browser.scroll, 0)
            rect = browser.row_rect(browser.selected)
            self.assertGreaterEqual(rect[1], browser.LIST[1])
            self.assertLessEqual(rect[3], browser.LIST[3])
            browser.selected = 0
            browser.switch('save' if load else 'load')
            self.assertEqual(browser.entry.path, paths[0])
            self.assertGreater(browser.scroll, 0)

    def test_active_save_changes_only_after_successful_save_or_load(self):
        scene = self.scene
        first = self.create_save('First journey')
        self.assertEqual(scene.active_save_path, first)
        second = self.create_save('Second journey')
        self.assertEqual(scene.active_save_path, second)
        scene.close_game_menu(resume=True)
        scene.load_game_from(first)
        self.assertEqual(scene.active_save_path, first)
        with patch('pop2.save_game.os.replace', side_effect=OSError('Unavailable')):
            with self.assertRaises(OSError):
                scene.save_game_to(second)
        self.assertEqual(scene.active_save_path, first)
        second.write_text('corrupt')
        with self.assertRaises(SaveGameError):
            scene.load_game_from(second)
        self.assertEqual(scene.active_save_path, first)
        scene.open_save_browser()
        browser = scene.game_menu.save_browser
        browser.edit_name('rename')
        browser.draft = 'Renamed journey'
        scene.apply_save_action('slot_rename')
        self.assertEqual(scene.active_save_path, first)
        self.assertEqual(browser.active_path, first)

    def test_restarts_keep_active_save_but_new_game_clears_it(self):
        scene = self.scene
        scene.save_game_to(self.path)
        scene.restart_level()
        self.assertEqual(scene.active_save_path, self.path)
        scene.new_game()
        self.assertIsNone(scene.active_save_path)
        scene.open_save_browser()
        self.assertIsNone(scene.game_menu.save_browser.active_path)

    def test_missing_active_save_does_not_select_an_unrelated_row_as_current(self):
        scene = self.scene
        self.create_save('My journey')
        self.path = scene.active_save_path
        scene.close_game_menu(resume=True)
        self.path.unlink()
        scene.open_save_browser()
        browser = scene.game_menu.save_browser
        self.assertFalse(browser.entry.exists)
        self.assertEqual(browser.focus, 29)
        self.assertFalse(any(slot.path == browser.active_path for slot in browser.slots))

    def test_save_confirmation_blocks_alt_new_game_shortcut(self):
        scene = self.scene
        scene.apply_game_action('save')
        self.create_save()
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
        self.create_save()
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

    def test_saved_preview_matches_real_resume_and_never_mutates_live_world(self):
        from pop2.save_game import decode_preview, read_document

        scene = self.scene
        for level, checkpoint in ((1, False), (1, True), (2, False), (3, False)):
            with self.subTest(level=level, checkpoint=checkpoint):
                scene.load_level(level)
                if checkpoint:
                    scene.jump_to_room(14, row=0, x=277, facing=0)
                    self.tick()
                    self.assertIsNotNone(scene.checkpoint)
                scene.sequence_state.target_x += 30
                scene.render()
                before = capture(scene.game)['state']
                game = scene.game
                rng = random.getstate()
                scene.save_game_to(self.path, 'My destination')
                self.assertIs(scene.game, game)
                self.assertEqual(capture(scene.game)['state'], before)
                self.assertEqual(random.getstate(), rng)
                document = read_document(self.path)
                self.assertTrue(document['preview_at_resume'])
                self.assertEqual(document['name'], 'My destination')
                preview = decode_preview(document['preview'])
                scene.load_game_from(self.path)
                if level == 3 and not checkpoint:
                    self.assertEqual(scene.action, 45)
                    # Advance only the same native entry script, without
                    # independently randomizing torch/ambient animation.
                    for _ in range(8):
                        scene.sequence_runtime.next_frame()
                        scene.game.caverns.advance()
                    self.assertEqual(scene.sequence_state.action, 15)
                    scene.action = scene.sequence_state.action
                    scene.player_x = scene.sequence_state.target_x
                    scene.sequence_state.current_x = scene.player_x
                    room = scene.level_renderer.enter_room(scene.room_id, scene.game.caverns)
                    scene.background, scene.foreground = room.background, room.foreground
                    scene.render()
                expected = scene.screenshot_viewport.crop((1, 0, 511, 365)).convert('RGB')
                self.assertEqual(preview.tobytes(), expected.tobytes())

    def test_create_duplicate_names_and_rename_preserve_distinct_saves_and_progress(self):
        scene = self.scene
        first = self.create_save('My journey')
        second = self.create_save('My journey')
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file())
        original = json.loads(second.read_text())
        browser = scene.game_menu.save_browser
        browser.focus = 25
        scene.apply_game_action(browser.activate())
        browser.draft = 'Renamed journey'
        scene.apply_game_action(browser.key('Return'))
        changed = json.loads(second.read_text())
        self.assertEqual(changed.pop('name'), 'Renamed journey')
        original.pop('name')
        self.assertEqual(changed, original)
        self.assertEqual(browser.entry.path, second)
        self.assertEqual(browser.entry.name, 'Renamed journey')

    def test_name_editing_supports_paste_and_blocks_game_shortcuts(self):
        scene = self.scene
        scene.apply_game_action('save')
        browser = scene.game_menu.save_browser
        scene.apply_game_action(browser.key('Return'))
        with patch.object(scene.root, 'clipboard_get', return_value='Caverns / second try'), \
                patch.object(scene, 'new_game') as new_game:
            for key, state, char in (('a', 4, ''), ('v', 4, ''), ('n', 0x20000, 'n')):
                event = SimpleNamespace(keysym=key, state=state, char=char)
                scene.dev_key_press(event)
                scene.dev_key_release(event)
            new_game.assert_not_called()
        self.assertEqual(browser.draft, 'Caverns / second try')
        scene.apply_game_action(browser.key('Return'))
        self.assertEqual(browser.entry.name, 'Caverns / second try')
        self.assertEqual(browser.entry.path.parent, self.path.parent)

    def test_editor_handles_empty_long_and_non_macintosh_characters_without_new_widgets(self):
        scene = self.scene
        scene.apply_game_action('save')
        browser = scene.game_menu.save_browser
        children = scene.root.winfo_children()
        for name in ('', 'A' * 48, 'N\u00edvel 3 \U0001f31f'):
            with self.subTest(name=name):
                browser.edit_name('create')
                browser.draft, browser.caret, browser.anchor = name, len(name), 0
                scene.render()
                self.assertEqual(scene.root.winfo_children(), children)
                self.assertEqual(browser.draft, name)
                self.assertTrue(scene.paused)
                if not name:
                    self.assertEqual(browser.key('Return'), 'changed')

    def test_old_thumbnail_is_reconstructed_from_progress_without_rewriting_file(self):
        from pop2.save_game import encode_preview
        from PIL import Image

        scene = self.scene
        scene.save_game_to(self.path)
        document = json.loads(self.path.read_text())
        document.pop('preview_at_resume')
        document['preview'] = encode_preview(Image.new('RGB', (512, 384), 'magenta'))
        self.path.write_text(json.dumps(document))
        before = self.path.read_bytes()
        scene.apply_game_action('open')
        slot = scene.game_menu.save_browser.entry
        self.assertIsNone(slot.preview)
        image = scene.save_slot_preview(slot)
        self.assertNotEqual(image.getcolors(), [(510 * 365, (255, 0, 255))])
        self.assertEqual(self.path.read_bytes(), before)

    def test_scroll_animation_redraws_only_the_menu_and_cancels_after_it_closes(self):
        from dataclasses import replace

        scene = self.scene
        self.create_save()
        browser = scene.game_menu.save_browser
        browser.slots = tuple(replace(browser.entry, name=f'Journey {i}') for i in range(20))
        pending = []
        clock = iter(i / 60 for i in range(200))
        before = capture(scene.game)['state']
        with patch.object(scene.root, 'after', side_effect=lambda delay, fn: pending.append(fn) or 'scroll'), \
                patch.object(scene, 'dev_pointer', return_value=(100, 140)), \
                patch.object(scene, 'present_viewport') as present, \
                patch('pop2.window_controls.time.perf_counter', side_effect=lambda: next(clock)):
            scene.dev_scroll(SimpleNamespace(delta=-240))
            self.assertEqual(browser.scroll_target, 84)
            while pending:
                pending.pop(0)()
            self.assertEqual(browser.scroll, 84)
            self.assertGreater(present.call_count, 1)
            self.assertEqual(capture(scene.game)['state'], before)
            scene.dev_scroll(SimpleNamespace(delta=-120))
            scene.game_menu = None
            pending.pop(0)()
            self.assertIsNone(scene.save_scroll_after_id)

    def test_rename_tooltip_is_erased_from_the_real_tk_image_after_leaving_hover(self):
        from PIL import ImageChops, ImageTk

        scene = self.scene
        scene.save_game_to(self.path, 'My journey')
        scene.open_save_browser()
        browser = scene.game_menu.save_browser
        for width, height in ((1020, 768), (3440, 1440), (800, 900)):
            with self.subTest(window=(width, height)), \
                    patch.object(scene.canvas, 'winfo_width', return_value=width), \
                    patch.object(scene.canvas, 'winfo_height', return_value=height):
                scene.redraw_save_menu()
                photo = scene.image_ref
                for point in ((300, 302), (-1, -1), (60, 60)):
                    self.assertTrue(browser.hover(258, 280))
                    scene.redraw_save_menu()
                    hovered = ImageTk.getimage(photo).convert('RGB')
                    self.assertIsNone(ImageChops.difference(hovered, scene.save_menu_frame[1]).getbbox())
                    self.assertFalse(browser.hover(350, 280))
                    self.assertTrue(browser.hover(*point))
                    scene.redraw_save_menu()
                    actual = ImageTk.getimage(photo).convert('RGB')
                    self.assertIsNone(ImageChops.difference(actual, scene.save_menu_frame[1]).getbbox())
                    self.assertNotEqual(actual.tobytes(), hovered.tobytes())
                self.assertIs(scene.image_ref, photo)

    def test_old_snapshot_preview_is_a_resume_image_and_keeps_the_file_untouched(self):
        scene = self.scene
        write_save(self.path, capture(scene.game))
        before = self.path.read_bytes()
        scene.apply_game_action('open')
        slot = scene.game_menu.save_browser.entry
        image = scene.save_slot_preview(slot)
        self.assertEqual(image.size, (510, 365))
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
