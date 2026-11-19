import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pop2.game_session import GameResources, GameSession
from pop2.story_progress import MAX_STORY_MINUTES
from pop2.save_game import (MAX_BYTES, SaveGameError, capture as capture_progress,
                           capture_snapshot as capture, read_snapshot as read_save,
                           restore_progress, write_save)
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

    def test_cheat_extended_story_clock_roundtrips_in_progress_saves(self):
        game = GameSession.load(self.resources, 4)
        game.story.select_scene(4, 4)
        self.assertTrue(game.story.adjust_minutes(1))
        restored, _saved = restore_progress(capture_progress(game), self.resources)
        self.assertEqual(restored.story.minutes, 76)
        self.assertEqual(restored.story.tree_stage, 0)

    def test_maximum_story_clock_roundtrips_in_progress_saves(self):
        game = GameSession.load(self.resources, 4)
        game.story.select_scene(4, 4)
        game.story.minutes = MAX_STORY_MINUTES - 1
        self.assertTrue(game.story.adjust_minutes(1))
        restored, _saved = restore_progress(capture_progress(game), self.resources)
        self.assertEqual(restored.story.minutes, MAX_STORY_MINUTES)
        self.assertEqual(restored.story.tree_stage, 0)

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

    def test_saved_target_is_the_persistent_prince_target_not_the_frame_opponent(self):
        # The native Prince target (+0x3a) persists while Main may use a
        # different opponent for one frame; only the persistent one is saved.
        original = GameSession.load(self.resources, 3)
        original.place(10, 2, 230, 1)
        cached = original.combat.guards[0]
        original.combat.guard = cached
        original.combat._effective_guard = None
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertIs(loaded.combat.target_cache, loaded.combat.guards[0])
        self.assertIs(loaded.combat.guard, loaded.combat.guards[0])

    def test_selected_sequence_cleared_by_animchar_minus18_roundtrips(self):
        # AnimChar -18 (4:2d7e) leaves the selected ID at 0, not a SEQS ID.
        original = GameSession.load(self.resources, 3)
        original.place(10, 2, 230, 1)
        original.combat.guards[0].state.selected_sequence_id = 0
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertEqual(loaded.combat.guards[0].state.source_sequence_id, 0)

    def test_transient_bone_shake_notifications_are_not_replayed_after_loading(self):
        original = GameSession.load(self.resources, 3)
        original.caverns.loose.shake_events.append((14, 2))
        write_save(self.path, capture(original))
        restored, _saved = read_save(self.path, self.resources)
        self.assertEqual(restored.caverns.loose.shake_events, [])

    def test_gate_audio_attribution_is_transient_and_does_not_change_save_fields(self):
        from pop2.mechanism_audio import GateSound

        original = GameSession.load(self.resources, 3)
        before = capture(original)
        original.caverns.plates.gate_sounds.append(GateSound(17, True, (0, 15)))
        self.assertEqual(capture(original), before)
        write_save(self.path, capture(original))
        restored, _saved = read_save(self.path, self.resources)
        self.assertEqual(restored.caverns.plates.gate_sounds, [])

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
                    item['fields'].pop('sword_lost', None)
                    item['fields'].pop('death_song_frames', None)
                    item['fields'].pop('death_song_pending', None)
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
        self.assertFalse(loaded.combat.player.sword_lost)
        self.assertEqual(loaded.combat.guards[0].death_song_frames, -1)
        self.assertFalse(loaded.combat.guards[0].death_song_pending)

    def test_pending_guard_kill_song_count_survives_a_save(self):
        from pop2.combat import select_sequence

        original = GameSession.load(self.resources, 12)
        original.place(8, 0, 100, 1)
        guard = original.combat.guards[0]
        guard.life, guard.native_alive, guard.death_registered = 0, False, True
        select_sequence(guard, 22)
        guard.runtime.next_frame()
        guard.death_song_frames, guard.death_song_pending = 3, True
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        restored = loaded.combat.guards[0]
        self.assertEqual((restored.death_song_frames, restored.death_song_pending), (3, True))
        for _ in range(3):
            loaded.combat.choose_guard_action(restored)
        self.assertFalse(loaded.combat.songs)
        loaded.combat.choose_guard_action(restored)
        self.assertEqual(loaded.combat.songs, [189])

    def test_scythe_corpse_can_be_saved_after_its_victory_request_is_consumed(self):
        from pop2.combat import select_sequence
        from pop2.terrain import TerrainMotion

        original = GameSession.load(self.resources, 12)
        original.place(8, 0, 100, 1)
        guard = original.combat.guards[0]
        guard.life, guard.native_alive, guard.death_registered = 0, False, True
        guard.terrain_motion = TerrainMotion(8, 0, dead=True)
        select_sequence(guard, 190)
        for _ in range(10):
            guard.runtime.next_frame()
        self.assertEqual(guard.state.action, 256)
        guard.death_song_frames, guard.death_song_pending = 6, False
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertEqual(loaded.combat.guards[0].state.action, 256)
        loaded.combat.choose_guard_action(loaded.combat.guards[0])
        self.assertFalse(loaded.combat.songs)

    def test_invalid_guard_kill_song_counter_is_rejected(self):
        original = GameSession.load(self.resources, 1)
        original.combat.guards[0].death_song_frames = 7
        write_save(self.path, capture(original))
        with self.assertRaises(SaveGameError):
            read_save(self.path, self.resources)

    def test_a_lost_sword_survives_a_save(self):
        original = GameSession.load(self.resources, 1)
        original.combat.player.sword_lost = True
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertTrue(loaded.combat.player.sword_lost)

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

    def test_legacy_special_flag_merges_into_the_single_native_word(self):
        # Native +0x34 (a5-0x5022) is one word; old saves stored two fields.
        original = GameSession.load(self.resources, 3)
        original.place(10, 2, 230, 1)
        original.combat.guards[0].state.sequence_mode = 0
        original.runtime.state.sequence_mode = 4
        value = capture(original)
        states = []

        def collect(item):
            if isinstance(item, dict):
                if item.get('record') == 'SequenceState':
                    states.append(item['fields'])
                for child in item.values():
                    collect(child)
            elif isinstance(item, list):
                for child in item:
                    collect(child)

        collect(value)
        self.assertTrue(states)
        for fields in states:
            self.assertNotIn('special_flag', fields)
            fields['special_flag'] = 5 if fields['sequence_mode'] == 0 else 13
        write_save(self.path, value)
        loaded, _saved = read_save(self.path, self.resources)
        self.assertEqual(loaded.combat.guards[0].state.sequence_mode, 5)
        self.assertEqual(loaded.runtime.state.sequence_mode, 4)
        self.assertFalse(hasattr(loaded.runtime.state, 'special_flag'))

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
        original.motion.gate_passages = ((3, 25),)
        original.runtime.state.select(5)
        original.runtime.next_frame()
        write_save(self.path, capture(original))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertEqual(loaded.motion.gate_contact_bounds, original.motion.gate_contact_bounds)
        self.assertEqual(loaded.motion.gate_passages, ((3, 25),))
        self.assertEqual(loaded.runtime.state.animation_state, 7)
        self.assertEqual(vars(loaded.runtime.state), vars(original.runtime.state))
        value = json.loads(self.path.read_text())

        def remove_contact(item):
            if isinstance(item, dict):
                if item.get('record') == 'TerrainMotion':
                    item['fields'].pop('gate_contact_bounds', None)
                    item['fields'].pop('gate_passages', None)
                for child in item.values():
                    remove_contact(child)
            elif isinstance(item, list):
                for child in item:
                    remove_contact(child)

        remove_contact(value)
        self.path.write_text(json.dumps(value))
        loaded, _saved = read_save(self.path, self.resources)
        self.assertIsNone(loaded.motion.gate_contact_bounds)
        self.assertEqual(loaded.motion.gate_passages, ())

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
        scene.jump_to_screen('Room 1')
        scene.up_key(None)
        self.tick(2)
        scene.save_game_to(self.path)
        scene.load_level(3)
        scene.load_game_from(self.path)
        self.assertEqual(scene.room_id, scene.game.level.start_room)
        self.assertTrue(scene.opening.active)

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

    def test_backspace_edits_new_and_existing_save_names_through_keyboard_events(self):
        scene = self.scene
        scene.apply_game_action('save')
        browser = scene.game_menu.save_browser
        browser.edit_name('create')
        browser.draft = 'Journey'
        browser.caret = browser.anchor = len(browser.draft)
        event = SimpleNamespace(keysym='BackSpace', state=0, char='\b')
        self.assertEqual(scene.dev_key_press(event), 'break')
        scene.dev_key_release(event)
        self.assertEqual(browser.draft, 'Journe')

        browser.key('Escape')
        scene.save_game_to(self.path, 'Journey')
        scene.apply_game_action('save')
        browser = scene.game_menu.save_browser
        browser.edit_name('rename')
        self.assertEqual(scene.dev_key_press(event), 'break')
        scene.dev_key_release(event)
        self.assertEqual(browser.draft, '')  # Rename starts with the whole name selected.
        browser.draft = 'Journey'
        browser.caret = browser.anchor = len(browser.draft)
        self.assertEqual(scene.dev_key_press(event), 'break')
        scene.dev_key_release(event)
        self.assertEqual(browser.draft, 'Journe')

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
                # The name stands under the preview, or beside it on the wide page.
                left, top, _right, bottom = browser.RENAME
                self.assertEqual(browser.RENAME == (238, 270, 472, 292), width != 3440)
                for point in ((left + 62, bottom + 6), (-1, -1), (60, 60)):
                    self.assertTrue(browser.hover(left + 20, top + 10))
                    scene.redraw_save_menu()
                    hovered = ImageTk.getimage(photo).convert('RGB')
                    self.assertIsNone(ImageChops.difference(hovered, scene.save_menu_frame[1].convert('RGB')).getbbox())
                    self.assertFalse(browser.hover(left + 112, top + 10))
                    self.assertTrue(browser.hover(*point))
                    scene.redraw_save_menu()
                    actual = ImageTk.getimage(photo).convert('RGB')
                    self.assertIsNone(ImageChops.difference(actual, scene.save_menu_frame[1].convert('RGB')).getbbox())
                    self.assertNotEqual(actual.tobytes(), hovered.tobytes())
                self.assertIs(scene.image_ref, photo)

    def test_passing_over_the_saves_page_s_buttons_draws_and_sends_only_what_changed(self):
        # The page was kept for each focus: each button or save the pointer reached drew all
        # of it again and compared the whole window (about 60 ms at 3440x1440), then the
        # whole list. After that it copied the window-sized page it kept, over which it drew
        # the buttons and the list (about 7 ms): the page shown is now drawn over where the
        # focus changed, and a save's outline goes to Tk as its four sides. The Rename
        # highlight and its tip were the page's own: reaching or leaving the save's name drew
        # the whole page again, the window's and the game's resolution's, and compared the
        # whole window (70-85 ms); only the name's part is now drawn and compared.
        from PIL import Image, ImageChops, ImageTk
        from pop2 import menu_theme
        from pop2.window_controls import put_patch

        scene = self.scene
        self.addCleanup(menu_theme.use, menu_theme.current())
        for index, name in enumerate(('My journey', 'Second', 'Third')):
            scene.save_game_to(self.path.with_name(f'{index}.pop2save'), name)
        scene.open_save_browser()
        browser = scene.game_menu.save_browser
        copied = []
        copy = Image.Image.copy

        def counted(image):
            copied.append(image.size)
            return copy(image)

        def fresh():
            caches = browser.list_base_cache, browser.modal_cache
            browser.list_base_cache, browser.modal_cache = {}, {}
            try:
                return browser.draw(scene.save_menu_source[2], scene.ui_font, visible=True,
                                    background_key=id(scene.screenshot_viewport)).convert('RGB')
            finally:
                browser.list_base_cache, browser.modal_cache = caches

        with patch.object(scene, 'dev_pointer', side_effect=lambda event: (event.x, event.y)), \
                patch.object(scene.canvas, 'winfo_width', return_value=3440), \
                patch.object(scene.canvas, 'winfo_height', return_value=1440):
            scene.redraw_save_menu()
            targets = {}
            for y in range(0, 384, 3):
                for x in range(-200, 900, 4):
                    index = browser.hit(x, y)
                    if index is not None and (index in (0, 1, 25, 26, 27, 28, 29) or 100 <= index < 103):
                        targets.setdefault(index, (x, y))
            self.assertEqual(set(targets), {0, 1, 25, 26, 27, 28, 29, 100, 101, 102})
            order = (100, 101, 25, 102, 0, 28, 101, 25, 27, 29, 1, 102, 26, 25, 100)
            route = [targets[index] for index in order] + [(-1, -1)]
            left, top, right, bottom = browser.pixel_rect(browser.LIST, (3440, 1440))
            listed = (right - left) * (bottom - top)
            named = browser.pixel_rect(browser.NAME_AREA, (3440, 1440))
            for theme in menu_theme.THEMES.values():
                with self.subTest(theme=theme.name):
                    menu_theme.use(theme)
                    # A level's theme is chosen as the game is drawn, before the page opens:
                    # here the page is shown again from the start in this one.
                    scene.save_menu_frame = None
                    scene.redraw_save_menu()
                    photo, page = scene.image_ref, scene.save_menu_frame[1]
                    bases, steps = dict(browser.list_base_cache), 0
                    for step, (x, y) in enumerate(route):
                        copied.clear()
                        with patch('pop2.window_controls.put_patch', wraps=put_patch) as sent, \
                                patch.object(Image.Image, 'copy', counted):
                            scene.dev_hover(SimpleNamespace(x=x, y=y))
                        # No copy of the window-sized page (the game's resolution's is small).
                        self.assertFalse([size for size in copied if size[0] * size[1] * 4 > 3440 * 1440], (x, y))
                        sizes = [call.args[1].size for call in sent.call_args_list]
                        steps += bool(sizes)
                        self.assertTrue(all(width * height * 8 < listed for width, height in sizes), (x, y, sizes))
                        if step and order[step - 1] >= 100 and step < len(order) and order[step] >= 100:
                            # From a save to another: only their outlines, by their sides.
                            self.assertTrue(sizes, (x, y))
                            self.assertTrue(all(min(size) <= 8 for size in sizes), (x, y, sizes))
                        if 25 in order[max(0, step - 1):step + 1]:
                            # Reaching or leaving the name: its highlight and tip, and the
                            # outline the focus left or reached, nothing of the page between.
                            boxes = [(*call.args[2:4], call.args[2] + call.args[1].width,
                                      call.args[3] + call.args[1].height) for call in sent.call_args_list]
                            self.assertTrue([box for box in boxes if box[2] > named[0] and box[3] > named[1]
                                             and box[0] < named[2] and box[1] < named[3]], (x, y, boxes))
                            for box in boxes:
                                inside = (named[0] - 4 <= box[0] and named[1] - 4 <= box[1]
                                          and box[2] <= named[2] + 4 and box[3] <= named[3] + 4)
                                apart = (box[2] <= named[0] or box[3] <= named[1]
                                         or box[0] >= named[2] or box[1] >= named[3])
                                self.assertTrue(inside or apart, (x, y, box, named))
                        shown = ImageTk.getimage(scene.image_ref).convert('RGB')
                        self.assertIsNone(ImageChops.difference(shown, fresh()).getbbox(), (x, y))
                        self.assertIs(scene.save_menu_frame[1], page)
                    self.assertIs(scene.image_ref, photo)
                    self.assertGreater(steps, len(route) // 2)
                    # The page under the list and the buttons was not drawn again.
                    self.assertEqual(browser.list_base_cache.keys(), bases.keys())
                    self.assertTrue(all(browser.list_base_cache[key] is base for key, base in bases.items()))

    def test_the_saves_page_drawn_in_place_scrolls_and_shows_a_toast_as_drawn_afresh(self):
        # The page shown is drawn over again where the scroll or the focus changed; a toast
        # makes a new picture of it, after which the page shown is not the one drawn over.
        from PIL import Image, ImageChops, ImageTk
        from pop2 import menu_theme

        scene = self.scene
        self.addCleanup(menu_theme.use, menu_theme.current())
        for index in range(12):
            scene.save_game_to(self.path.with_name(f'{index}.pop2save'), f'Journey {index}')
        scene.open_save_browser()
        browser = scene.game_menu.save_browser
        self.assertGreater(browser.max_scroll, 0)

        def check(label):
            caches = browser.list_base_cache, browser.modal_cache
            browser.list_base_cache, browser.modal_cache = {}, {}
            try:
                page = browser.draw(scene.save_menu_source[2], scene.ui_font, visible=True,
                                    background_key=id(scene.screenshot_viewport))
            finally:
                browser.list_base_cache, browser.modal_cache = caches
            expected = scene.draw_screenshot_notice(page, visible=True, uniform=bool(browser.spread)).convert('RGB')
            shown = ImageTk.getimage(scene.image_ref).convert('RGB')
            self.assertIsNone(ImageChops.difference(shown, expected).getbbox(), label)

        for width, height, theme in ((3440, 1440, 'spider'), (1020, 768, 'ruins'), (800, 900, 'palace')):
            menu_theme.use(menu_theme.THEMES[theme])
            with self.subTest(window=(width, height), theme=theme), \
                    patch.object(scene, 'dev_pointer', side_effect=lambda event: (event.x, event.y)), \
                    patch.object(scene.canvas, 'winfo_width', return_value=width), \
                    patch.object(scene.canvas, 'winfo_height', return_value=height):
                browser.scroll = browser.scroll_target = 0
                scene.save_menu_frame = None
                scene.redraw_save_menu()
                photo = scene.image_ref
                found = {}
                for y in range(100, 320, 7):
                    for x in range(30, 260, 9):
                        if (browser.hit(x, y) or 0) >= 100:
                            found.setdefault(browser.hit(x, y), (x, y))
                rows = list(found.values())   # one point in each save in sight
                self.assertGreater(len(rows), 3)
                for x, y in rows[:4]:
                    scene.dev_hover(SimpleNamespace(x=x, y=y))
                    check(('hover', x, y))
                browser.wheel(3)
                for _ in range(8):
                    browser.animate(1 / 60)
                    scene.redraw_save_menu()
                    check(('scroll', browser.scroll))
                for x, y in rows[1:4]:
                    scene.dev_hover(SimpleNamespace(x=x, y=y))
                    check(('scrolled hover', x, y))
                # A toast that comes with a new focus: the page shown was drawn over in the
                # same drawing that gave the window a new picture of it.
                scene.screenshot_toast = 'Saved screenshot as a.png'
                scene.dev_hover(SimpleNamespace(x=rows[0][0], y=rows[0][1]))
                check('toast with a new focus')
                for x, y in rows[1:3]:
                    scene.dev_hover(SimpleNamespace(x=x, y=y))
                    check(('toast', x, y))
                # The name's highlight and tip with a toast: the window compares the name's part.
                left, top = browser.RENAME[:2]
                for x, y in ((left + 20, top + 10), rows[0], (left + 20, top + 10), (-1, -1)):
                    scene.dev_hover(SimpleNamespace(x=x, y=y))
                    check(('toast, name', x, y))
                scene.clear_screenshot_toast()
                check('toast gone')
                scene.show_screenshot_toast('b.png')
                check('another toast')
                scene.clear_screenshot_toast()
                for x, y in rows[2:4] + [(-1, -1)]:
                    scene.dev_hover(SimpleNamespace(x=x, y=y))
                    check(('after the toast', x, y))
                self.assertIs(scene.image_ref, photo)
                self.assertIsInstance(scene.save_menu_frame[1], Image.Image)

    def test_a_saves_dialog_drawn_in_place_redraws_only_the_buttons_lit_or_left(self):
        # A confirmation or the name's dialog is drawn over the page shown where the pointer
        # or the keys lit or left a button: neither the rest of the dialog nor the darkened
        # page under it is drawn again, and the page shows what a fresh drawing shows.
        from PIL import ImageChops, ImageTk
        from pop2 import menu_theme

        scene = self.scene
        self.addCleanup(menu_theme.use, menu_theme.current())
        for index in range(3):
            scene.save_game_to(self.path.with_name(f'{index}.pop2save'), f'Journey {index}')
        scene.open_save_browser()
        browser = scene.game_menu.save_browser

        def check(label, lit=True):
            if lit:   # drawn over the same page, in no more than the two buttons
                self.assertIs(scene.save_menu_frame[1], page, label)
                self.assertIsNotNone(browser.redrawn, label)
                self.assertTrue(browser.redrawn, label)
                self.assertLessEqual(len(browser.redrawn), 2, label)
                for box, _before in browser.redrawn:
                    self.assertLess((box[2] - box[0]) * (box[3] - box[1]) * 30, width * height, (label, box))
            caches = browser.list_base_cache, browser.modal_cache
            browser.list_base_cache, browser.modal_cache = {}, {}
            try:
                fresh = browser.draw(scene.save_menu_source[2], scene.ui_font, visible=True,
                                     background_key=id(scene.screenshot_viewport))
            finally:
                browser.list_base_cache, browser.modal_cache = caches
            expected = scene.draw_screenshot_notice(fresh, visible=True, uniform=bool(browser.spread)).convert('RGB')
            shown = ImageTk.getimage(scene.image_ref).convert('RGB')
            self.assertIsNone(ImageChops.difference(shown, expected).getbbox(), label)

        def centre(rect):
            return SimpleNamespace(x=(rect[0] + rect[2]) / 2, y=(rect[1] + rect[3]) / 2)

        for width, height, theme in ((3440, 1440, 'spider'), (1020, 768, 'ruins')):
            menu_theme.use(menu_theme.THEMES[theme])
            with self.subTest(window=(width, height), theme=theme), \
                    patch.object(scene, 'dev_pointer', side_effect=lambda event: (event.x, event.y)), \
                    patch.object(scene.canvas, 'winfo_width', return_value=width), \
                    patch.object(scene.canvas, 'winfo_height', return_value=height):
                browser.confirmation = browser.editing = None
                browser.selected, browser.focus = 0, 26
                scene.save_menu_frame = None
                scene.redraw_save_menu()
                self.assertEqual(browser.activate(), 'changed')
                self.assertEqual(browser.confirmation, 'delete')
                scene.redraw_save_menu()
                page = scene.save_menu_frame[1]
                check('confirmation opened', lit=False)
                cancel, delete = browser.CONFIRM
                for name, event in (('delete', centre(delete)), ('cancel', centre(cancel)),
                                    ('delete again', centre(delete))):
                    scene.dev_hover(event)
                    check(name)
                browser.key('Tab')
                scene.redraw_save_menu()
                check('Tab')
                browser.key('Escape')
                scene.redraw_save_menu()
                check('confirmation closed', lit=False)
                # The name's dialog lights a button the pointer is over as well as the focus.
                browser.focus = 25
                browser.activate()
                self.assertEqual(browser.editing, 'rename')
                scene.redraw_save_menu()
                browser.key('Tab')   # from the name, whose caret is gone, to Cancel
                scene.redraw_save_menu()
                page = scene.save_menu_frame[1]
                check('name dialog', lit=False)
                rename = browser.CONFIRM[1]
                for name, event in (('rename', centre(rename)), ('away', SimpleNamespace(x=5, y=5)),
                                    ('rename again', centre(rename))):   # Cancel has the focus
                    scene.dev_hover(event)
                    check(name)
                browser.focus = 32
                browser.key('a', char='b')   # the name changed: the dialog is drawn afresh
                scene.redraw_save_menu()
                check('typed', lit=False)
                browser.key('Escape')
                scene.redraw_save_menu()

    def test_a_saves_dialog_opens_over_the_page_kept_and_goes_to_the_window_whole(self):
        # A dialog darkens the page kept under the list, which is not drawn again from the
        # game's picture, and opening or closing it sends the whole window without
        # comparing it with the page before: at 3440x1440 the two took about 80 ms of the
        # 150 a dialog took to open.
        from PIL import ImageChops, ImageTk
        from pop2 import menu_theme

        scene = self.scene
        for index in range(3):
            scene.save_game_to(self.path.with_name(f'{index}.pop2save'), f'Journey {index}')
        scene.open_save_browser()
        browser = scene.game_menu.save_browser
        panels, compared = [], []
        scaled, difference = menu_theme.panel_scaled, ImageChops.difference

        def counted_panel(image, rect, *args, **options):
            panels.append(rect)
            return scaled(image, rect, *args, **options)

        def counted_difference(first, second):
            compared.append(first.size)
            return difference(first, second)

        def check(label):
            caches = browser.list_base_cache, browser.modal_cache
            browser.list_base_cache, browser.modal_cache = {}, {}
            try:
                fresh = browser.draw(scene.save_menu_source[2], scene.ui_font, visible=True,
                                     background_key=id(scene.screenshot_viewport))
            finally:
                browser.list_base_cache, browser.modal_cache = caches
            expected = scene.draw_screenshot_notice(fresh, visible=True, uniform=bool(browser.spread)).convert('RGB')
            shown = ImageTk.getimage(scene.image_ref).convert('RGB')
            self.assertIsNone(ImageChops.difference(shown, expected).getbbox(), label)

        with patch.object(scene, 'dev_pointer', side_effect=lambda event: (event.x, event.y)), \
                patch.object(scene.canvas, 'winfo_width', return_value=3440), \
                patch.object(scene.canvas, 'winfo_height', return_value=1440):
            scene.save_menu_frame = None
            scene.redraw_save_menu()
            for focus, opened in ((26, 'delete'), (25, 'rename'), (27, 'save')):
                browser.selected, browser.focus = 0, focus
                scene.redraw_save_menu()
                panels.clear()
                with patch('pop2.menu_theme.panel_scaled', counted_panel), \
                        patch('pop2.window_controls.ImageChops.difference', counted_difference):
                    self.assertEqual(browser.activate(), 'changed')
                    scene.redraw_save_menu()
                    self.assertEqual(compared, [], opened)
                    self.assertIn(opened, (browser.confirmation, browser.editing))
                    self.assertIn(browser.DIALOG, panels)
                    self.assertNotIn(browser.PANEL, panels, opened)   # the page kept, darkened
                    check(f'{opened} open')
                    compared.clear()
                    browser.key('Escape')
                    scene.redraw_save_menu()
                    self.assertFalse(browser.confirmation or browser.editing)
                    self.assertEqual(compared, [], opened)
                check(opened)

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
