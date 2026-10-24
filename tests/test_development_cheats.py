from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.development_map import DevelopmentMap, MAP_SIZE
from pop2.game_ui import DevelopmentMenu
from pop2.paths import ASSET_DIR
from pop2.environments import environment_for


class CheatMenuTests(unittest.TestCase):
    def menu(self):
        preview = DevelopmentMap(Image.new('RGB', MAP_SIZE), {'Room 1': (0, 0, 40, 40)},
                                 {'Room 1': (0, 0)})
        return DevelopmentMenu(('Room 1',), 0, False,
                               level_options=((3, 'Level 3', ('Room 1',)),),
                               map_provider=lambda _: preview)

    def test_independent_toggles_share_one_row_and_support_keyboard_and_click(self):
        menu = self.menu()
        peaceful, god = menu.control_rect(1), menu.control_rect(11)
        self.assertEqual(peaceful[1::2], god[1::2])
        self.assertLess(peaceful[2], god[0])
        menu.focus = 1
        menu.key('Right')
        self.assertEqual(menu.focus, 11)
        self.assertEqual(menu.key('space'), 'god_mode')
        self.assertTrue(menu.god_mode)
        self.assertFalse(menu.peaceful)
        menu.key('Left')
        self.assertEqual(menu.key('Return'), 'peaceful')
        self.assertTrue(menu.god_mode and menu.peaceful)
        self.assertEqual(menu.click(god[0] + 5, god[1] + 5), 'god_mode')
        self.assertFalse(menu.god_mode)
        self.assertTrue(menu.peaceful)

    def test_god_control_is_not_exposed_in_map_or_playback(self):
        menu = self.menu()
        menu.open_map()
        self.assertNotIn(11, menu.controls)
        menu.show_page('playback')
        self.assertNotIn(11, menu.controls)

    def test_god_control_is_not_available_in_attract_tools(self):
        menu = DevelopmentMenu(('Intro',), 0, False, level_available=False)
        self.assertNotIn(11, menu.controls)


@unittest.skipUnless((ASSET_DIR / 'enemy_profiles.json').is_file(), 'Imported game files required')
class ImportedCheatTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def test_god_toggle_is_session_only_does_not_heal_and_survives_level_restart(self):
        s = self.scene
        s.combat.player.life = 1
        s.open_dev_mode()
        s.dev_menu.focus = 11
        s.apply_dev_action(s.dev_menu.activate())
        self.assertTrue(s.god_mode)
        self.assertTrue(s.combat.god_mode)
        self.assertEqual(s.combat.player.life, 1)
        self.assertFalse(s.peaceful)
        s.close_dev_mode()
        s.load_level(3)
        s.restart_level()
        s.open_dev_mode()
        self.assertTrue(s.god_mode and s.dev_menu.god_mode)
        from pop2.save_game import capture

        self.assertNotIn('god_mode', repr(capture(s.game)))

    def test_sword_hits_keep_reactions_but_never_remove_life_in_god_mode(self):
        s = self.scene
        s.opening.active = False
        c = s.combat
        for sequence in (227, 10):
            c.player.life = 1
            c.player.state.sequence_id = sequence
            s.set_god_mode(True)
            event = c._hurt('player', c.player, c.guard)
            self.assertEqual((event.kind, c.player.life), ('hit', 1))
            self.assertTrue(c.player.recovering)
        s.set_god_mode(False)
        event = c._hurt('player', c.player, c.guard)
        self.assertEqual((event.kind, c.player.life), ('death', 0))

    def test_k_collapses_active_skeletons_disables_dormant_ones_and_leaves_other_rooms_alone(self):
        s = self.scene
        s.load_level(3)
        s.jump_to_room(14, row=2, x=100, facing=1)
        c = s.combat
        local = c.room_encounters[14][0]
        self.assertTrue(local)
        c._load_room(19)
        others = c.room_encounters[19][0]
        before = [(g.life, g.skeleton.marker, g.skeleton.phase) for g in others]
        for guard in local:
            guard.skeleton.marker = 1
            guard.skeleton.initialize(guard)
        s.set_god_mode(True)
        event = SimpleNamespace(keysym='k', state=0)
        with patch.object(c, 'kill_room_enemies', wraps=c.kill_room_enemies) as kill:
            s.dev_key_press(event)
            s.dev_key_press(event)
            self.assertEqual(kill.call_count, 1)
        s.dev_key_release(event)
        self.assertTrue(all(g.life == 0 and g.skeleton.marker == -1 for g in local))
        self.assertEqual(before, [(g.life, g.skeleton.marker, g.skeleton.phase) for g in others])
        for guard in local:
            self.assertFalse(guard.skeleton.can_wake(c, guard))
        s.load_level(3)
        s.jump_to_room(14, row=2, x=100, facing=1)
        s.combat.kill_room_enemies(14)
        self.assertTrue(all(g.skeleton.marker == -1 for g in s.combat.room_encounters[14][0]))

    def test_k_requires_god_mode_and_unpaused_gameplay_without_modifiers_or_menus(self):
        s = self.scene
        with patch.object(s.combat, 'kill_room_enemies') as kill:
            for enabled, paused, modifiers in ((False, False, 0), (True, True, 0),
                                                (True, False, 4), (True, False, 0x20000)):
                s.god_mode = enabled
                s.set_paused(paused)
                event = SimpleNamespace(keysym='k', state=modifiers)
                s.dev_key_press(event)
                s.dev_key_release(event)
            s.set_paused(False)
            s.open_dev_mode()
            event = SimpleNamespace(keysym='K', state=1)
            s.dev_key_press(event)
            s.dev_key_release(event)
            kill.assert_not_called()

    def test_god_mode_survives_projectiles_and_disabling_restores_damage(self):
        from pop2.darts import Dart

        s = self.scene
        s.load_level(3)
        s.jump_to_room(15, row=1, x=190, facing=1)
        s.start_sequence(1)
        s.combat.player.life = 1
        s.set_god_mode(True)
        darts = s.game.caverns.plates.darts
        darts.projectiles = [Dart(15, 175, 195, 1)]
        environment_for(s).check_darts()
        self.assertEqual(s.combat.player.life, 1)
        self.assertFalse(s.terrain_motion.dead)
        s.set_god_mode(False)
        darts.projectiles = [Dart(15, 175, 195, 1)]
        environment_for(s).check_darts()
        self.assertEqual(s.combat.player.life, 0)

    def test_k_also_kills_ordinary_guards(self):
        s = self.scene
        s.opening.active = False
        guard = s.combat.guard
        self.assertTrue(guard.alive)
        s.set_god_mode(True)
        event = SimpleNamespace(keysym='k', state=0)
        s.dev_key_press(event)
        s.dev_key_release(event)
        self.assertFalse(guard.alive)
        self.assertTrue(s.combat.player.alive)

    def test_god_mode_protects_against_falling_slabs_without_healing(self):
        s = self.scene
        s.load_level(3)
        s.jump_to_room(16, row=2, x=100, facing=1)
        s.combat.player.life = 1
        s.set_god_mode(True)
        hits_player = lambda block, motion, *_: motion is s.terrain_motion
        with patch('pop2.environments.floor_hits_actor', side_effect=hits_player), \
                patch.object(s.game.caverns.loose, 'advance_falling', return_value=((), (object(),))):
            environment_for(s).frame_start()
            self.assertEqual(s.combat.player.life, 1)
            s.set_god_mode(False)
            environment_for(s).frame_start()
            self.assertEqual(s.combat.player.life, 0)

    def test_god_mode_protects_lava_and_wall_spikes(self):
        s = self.scene
        s.load_level(3)
        s.set_god_mode(True)
        s.jump_to_room(5, row=2, x=420, facing=1)
        s.physics.select(s.sequence_runtime, 1)
        s.action = s.sequence_state.action
        s.advance_level_events()
        self.assertEqual(s.combat.player.life, 3)
        self.assertFalse(s.terrain_motion.dead)
        s.jump_to_room(20, row=2, x=300, facing=1)
        s.physics.select(s.sequence_runtime, 1)
        s.action = s.sequence_state.action
        environment_for(s).check_spikes()
        self.assertTrue(s.combat.player.alive)
        self.assertFalse(s.terrain_motion.dead)
        self.assertEqual(s.death.counter, -1)

    def test_god_mode_turns_a_fatal_landing_into_recovery_without_damage(self):
        s = self.scene
        s.load_level(3)
        s.jump_to_room(30, row=2, x=80, facing=1)
        s.set_god_mode(True)
        s.physics.select(s.sequence_runtime, 12)
        s.action = s.sequence_state.action
        s.sequence_state.current_y = -45
        s.sequence_state.vertical_velocity = 63
        s.terrain_motion.falling = True
        s.advance_terrain(s.sequence_state.target_x)
        self.assertTrue(s.combat.player.alive)
        self.assertEqual(s.combat.player.life, 3)
        self.assertFalse(s.terrain_motion.dead)
        self.assertFalse(s.terrain_motion.falling)

    def test_bottomless_fall_returns_to_safe_room_entry_without_losing_life(self):
        s = self.scene
        s.opening.active = False
        s.set_god_mode(True)
        s.combat.player.life = 2
        s.combat.player.max_life = 5
        s.terrain_motion.falling = True
        s.sequence_state.current_y = 1000
        s.sequence_state.animation_state = 4
        s.sequence_state.vertical_velocity = 63
        s.advance_terrain(s.sequence_state.target_x)
        self.assertEqual(s.combat.player.life, 2)
        self.assertEqual(s.combat.player.max_life, 5)
        self.assertFalse(s.terrain_motion.dead)
        self.assertFalse(s.terrain_motion.falling)
        self.assertEqual(s.death.counter, -1)
