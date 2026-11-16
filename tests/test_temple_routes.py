"""Whole temple routes, run by tools/audit_temple_routes.py's real-key harness.

docs/research/temple-route-audit.md explains them. Each route is an exact key
script found by the audit's search. When a deliberate physics change breaks
one, run the audit again rather than editing its keys by hand.
"""

import unittest

from pop2.paths import ASSET_DIR
from pop2.scythes import CUT_SEQUENCE, CUT_SOUND, START_SOUND
from tools.audit_temple_routes import Harness, MACROS, altar_death, play, press, replay, settle

ROUTES = {
    10: ['runR20', 'leapcatchR20', 'runR8', 'climb', 'hopR', 'leapR20', 'hopcatchR', 'leapR5',
         'hopcatchL'],
    11: ['runL20', 'leapcatchL5', 'hopcatchL', 'hopcatchL', 'hopcatchL', 'descendL', 'tapR',
         'climb', 'tapL', 'jump', 'tapR', 'climb', 'hopL', 'leapcatchR5', 'leapcatchR11',
         'climb', 'climb', 'hopcatchR', 'leapcatchL14', 'climb', 'climb', 'climb', 'tapL',
         'stepL', 'leapR5', 'rushcatchL', 'hopcatchL', 'tapL', 'tapR', 'climb', 'climb',
         'climb', 'climb', 'climb', 'hopcatchR', 'leapcatchL5', 'runL20', 'runL20', 'hopcatchR',
         'climb', 'climb', 'hopcatchR', 'climb', 'climb', 'climb', 'stepR', 'runR20',
         'leapcatchL20', 'leapL14', 'climb', 'crawlL', 'descendhangR', 'runL5', 'leapcatchL11',
         'climb', 'hopcatchR', 'descendhangR', 'hopcatchR', 'climb', 'hopcatchR', 'climb',
         'climb', 'leapR8', 'runR20', 'climb', 'leapcatchR11', 'tapR', 'tapL', 'tapL', 'stepL',
         'crawlL', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8',
         'leapcatchL11', 'leapcatchL20', 'leapcatchL8', 'crawlL', 'tapL', 'descendhangL',
         'descendL', 'hopR', 'hopR', 'hopcatchR'],
    13: ['runL8', 'hopcatchR', 'descendhangL', 'tapL', 'climb', 'leapL5', 'hopcatchL', 'leapL5',
         'leapL20', 'leapcatchL14', 'leapcatchL8', 'stepL', 'tapL', 'leapL14', 'leapL20',
         'leapL11', 'leapL14', 'leapL11', 'drink', 'leapR20', 'leapcatchR5', 'stepR', 'leapR8',
         'descendR', 'runL5', 'leapL11', 'leapcatchL11', 'runL8', 'leapcatchL11', 'altar',
         'leapR11', 'leapcatchR20', 'runR8', 'leapR20', 'leapcatchR20'],
}


# An earlier, peaceful partial search of level 12 (see the audit). This far,
# three loose floors hold gates 3:2, 5:0 and 2:9 open for good.
LEVEL_12_GATES = ['leapR11', 'leapcatchL20', 'leapL5', 'runR5', 'runL5', 'hopcatchL', 'crawlL',
                  'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'tapL', 'stepL',
                  'crawlL', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8',
                  'runL8', 'hopcatchR', 'climb', 'hopcatchR', 'climb', 'climb', 'leapcatchR11',
                  'climb', 'climb', 'climb', 'climb', 'hopcatchR', 'leapcatchL11', 'tapL',
                  'hopcatchR', 'runL5', 'leapcatchR5', 'leapR11', 'jump', 'tapL', 'climb',
                  'hopR', 'runR11', 'hopcatchL', 'leapcatchL20', 'tapL', 'runL8',
                  'leapcatchL11', 'hopcatchL', 'leapcatchR5']

def blades_exported(number):
    path = ASSET_DIR / f'temple_level{number}.json'
    return path.is_file() and '"scythes"' in path.read_text(encoding='ascii')


# The way east and back. Plate 16:7 reopens gate 16:28 after 16:1 shut it, and the
# flask's genie reopens gate 18:19 after 24:22 shut it behind the Prince.
LEVEL_12_GENIE = ['leapR11', 'leapcatchL20', 'leapL5', 'runL11', 'leapcatchR5', 'runL5', 'runR20',
                  'leapcatchR11', 'leapL20', 'leapR11', 'descendhangR', 'descendhangR',
                  'leapcatchR20', 'climb', 'tapR', 'leapcatchR20', 'hopR', 'leapR20', 'crawlL',
                  'descendhangL', 'runL20', 'hopcatchL', 'runR5']

# The player's Macintosh recording (docs/research/level12-video-route.md), with
# opponents on from a fresh load: up through loose 1:26 from room 8, slabs on
# 19:20, 5:28, 9:0 and 2:22, the room-9 guard fought off his platform onto
# plate 9:24, the flaming sword parried down, plate 14:8 and back west through
# rooms 14, 16, 6, 17, 10, 9, 8 and 19 to the stairway in room 7.
LEVEL_12_VIDEO = [
    'tapR', 'runR20', 'leapL11', 'tapL', 'climb', 'climb', 'tapR', 'jump', 'wait20', 'wait20', 'tapL',
    'climb', 'tapR', 'hopshortR', 'nudgeR', 'nudgeR', 'tapL', 'jump', 'tapR', 'jump', 'tapL', 'jump',
    'stepL', 'hopL', 'leapL5', 'stepL', 'stepL', 'tapR', 'climb', 'tapL', 'stepL', 'hopL', 'strike',
    'descendL', 'leapR8', 'leapcatchL5', 'climb', 'hopcatchR', 'climb', 'leapcatchR20', 'stepL',
    'hopcatchL', 'tapL', 'tapR', 'climb', 'climb', 'tapR', 'down', 'runL5', 'hopL', 'runL11', 'runR5',
    'leapcatchL5', 'descendhangL', 'drink', 'leapR5', 'crawlL', 'leapcatchR5', 'climb', 'climb', 'climb',
    'climb', 'runR11', 'hopR', 'leapcatchR11', 'leapR14', 'swordduel', 'down', 'runR20', 'leapR5', 'tapR',
    'leapL11', 'runL11', 'runR5', 'runL5', 'crawlL', 'crawlL', 'crawlL', 'crawlL', 'crawlL', 'crawlL',
    'duel', 'down', 'runL11', 'leapcatchL14', 'leapL20', 'runL20', 'descendL', 'crawlL', 'crawlL',
    'crawlL', 'crawlL', 'duelfar', 'down', 'stepL', 'crawlL', 'runL20', 'descendhangL', 'hopcatchR',
    'climb', 'climb', 'climb', 'leapcatchR11', 'climb', 'leapcatchR11', 'runR8', 'runR20', 'runR20',
    'hopcatchR']
# The recording's life bar shows twelve flasks on arrival; a level loaded on
# its own starts with three, too few for the flaming sword.
LEVEL_12_VIDEO_LIFE = 12

# Searched with opponents on (2026-11-16, life 12 supplied as for level 12):
# past the room-11 birdhead, which follows him into room 8, then the route's
# second half. It costs six life points; with three he dies in room 11.
LEVEL_10_HOSTILE = ['leapL5', 'runR20', 'leapR20', 'leapR5', 'crawlL', 'crawlR', 'crawlR', 'crawlL',
                    'hopL', 'leapcatchR5', 'leapcatchR5', 'leapR5', 'hopcatchR', 'leapR5', 'hopcatchL']

INSTALLED = all(blades_exported(number) for number in (10, 11, 12, 13))


@unittest.skipUnless(INSTALLED, 'Temple levels imported with their blades required')
class TempleRouteTests(unittest.TestCase):
    def test_each_level_can_be_finished_from_a_fresh_load(self):
        for number, route in ROUTES.items():
            with self.subTest(level=number):
                reached, trace, harness = replay(number, route, draw=False)
                harness.close()
                self.assertTrue(reached, trace[-3:])

    def test_a_restored_search_copy_plays_on_as_a_fresh_load_does(self):
        # With opponents on, Combat.step reads the clock against the saved
        # last_guard_at: a copy restored later must bring its clock back.
        route = ['leapcatchL8', 'hopR', 'leapR14', 'leapR11']

        def run(detour):
            harness = Harness(10, peaceful=False)
            try:
                harness.number = 10
                settle(harness, 300)
                for name in route:
                    if detour:
                        saved = harness.save()
                        play(harness, MACROS['runR20'])
                        harness.restore(saved)
                    play(harness, MACROS[name])
                    settle(harness)
                guards = harness.scene.combat.active_guards()
                return harness.player(), [(guard.state.target_x, guard.state.action)
                                          for guard in guards]
            finally:
                harness.close()

        self.assertEqual(run(True), run(False))

    def test_level_13s_birdhead_wakes_to_steps_and_the_flame_survives_the_climb(self):
        # The peaceful route to the altar room, then opponents on: three
        # steps behind the birdhead wake it (no supplied waking), it kills
        # the Prince, the shadow brings the flame, and the armed opponent of
        # native room 13 bows. A catch used to clear mode 13 (the hang
        # control 6:18e0 clears it only when letting go, 6:1916), and that
        # opponent then killed the Prince with one stroke.
        route = ROUTES[13]
        index = route.index('altar')
        _reached, _trace, harness = replay(13, route[:index], draw=False)
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.peaceful = False
        for name in ('stepL', 'stepL', 'stepL'):
            play(harness, MACROS[name])
        for _ in range(600):
            harness.tick()
            if scene.combat.player.alive and scene.game.caverns.altar == -1:
                break
        settle(harness)
        self.assertEqual(scene.game.caverns.altar, -1)
        self.assertEqual(scene.sequence_state.sequence_mode, 13)
        modes = []
        for name in route[index + 1:]:
            play(harness, MACROS[name])
            settle(harness)
            modes.append(scene.sequence_state.sequence_mode)
            if harness.goal() or not scene.combat.player.alive:
                break
        self.assertTrue(harness.goal(), harness.player())
        self.assertEqual(set(modes), {13})

    def test_level_10_is_finished_with_opponents_on(self):
        reached, trace, harness = replay(10, LEVEL_10_HOSTILE, draw=False, peaceful=False,
                                         life=LEVEL_12_VIDEO_LIFE)
        self.addCleanup(harness.close)
        self.assertTrue(reached, trace[-3:])
        self.assertEqual(trace[-1][1:3], (19, 1))

    def test_level_12s_loose_floors_hold_their_gates_open(self):
        _reached, trace, harness = replay(12, LEVEL_12_GATES, draw=False)
        self.addCleanup(harness.close)
        self.assertTrue(trace[-1][-1], trace[-3:])
        terrain, plates = harness.scene.level_map, harness.scene.game.caverns.plates
        for room, cell, link in ((3, 2, 103), (5, 0, 156), (2, 9, 154)):
            with self.subTest(room=room, cell=cell):
                self.assertEqual(plates.timers[link], 31)
                self.assertEqual(terrain.tile(room - 1, cell % 10, cell // 10).foreground & 255, 255)

    def test_level_12s_genie_reopens_the_gate_behind_the_prince(self):
        shut = []

        def before_the_flask(harness, name, phase):
            if (name, phase) == ('crawlL', 'start'):
                shut.append(harness.scene.level_map.tile(17, 9, 1).foreground & 255)

        _reached, trace, harness = replay(12, LEVEL_12_GENIE, draw=False, log=before_the_flask)
        self.addCleanup(harness.close)
        self.assertEqual(shut, [0])
        self.assertIn((22, 24), harness.scene.game.caverns.potions.tiles)
        self.assertEqual(trace[-1][1:4], (18, 1, 9))
        self.assertTrue(trace[-1][-1], trace[-3:])

    def test_level_12s_flaming_sword_can_be_passed_as_in_the_video(self):
        # The video (02:33-02:36) lands where the port lands, crouched just
        # left of the resting sword, and the sword wakes about as late. The
        # player draws and advances east over it while it rises, so it ends
        # behind him and he runs on to room 12. Parrying it down is only the
        # port route's choice.
        route = LEVEL_12_VIDEO[:LEVEL_12_VIDEO.index('swordduel')] + ['swordpass', 'runR20']
        _reached, trace, harness = replay(12, route, draw=False, peaceful=False, life=LEVEL_12_VIDEO_LIFE)
        self.addCleanup(harness.close)
        self.assertEqual(trace[-1][1:3], (12, 0), trace[-3:])
        self.assertTrue(trace[-1][-1])
        sword = next(guard for guards, _points in harness.scene.combat.room_encounters.values()
                     for guard in guards if guard.flame_sword is not None)
        self.assertEqual(sword.room + 1, 7)

    def test_level_12_is_finished_along_the_macintosh_video_route(self):
        corpse = []

        def after_the_fight(harness, name, phase):
            if (name, phase) == ('strike', 'end'):
                guards = harness.scene.combat.room_encounters[8][0]
                corpse.extend((guard.alive, guard.row) for guard in guards)

        reached, trace, harness = replay(12, LEVEL_12_VIDEO, draw=False, peaceful=False,
                                         life=LEVEL_12_VIDEO_LIFE, log=after_the_fight)
        self.addCleanup(harness.close)
        self.assertTrue(reached, trace[-3:])
        self.assertEqual(trace[-1][1:3], (7, 2))
        # The guard lies dead on the lower floor, his body holding gate 5:2.
        self.assertEqual(corpse, [(False, 2)])
        terrain, plates = harness.scene.level_map, harness.scene.game.caverns.plates
        for room, cell, link in ((3, 2, 103), (5, 0, 156), (5, 2, 106), (2, 9, 154), (1, 3, 159)):
            with self.subTest(room=room, cell=cell):
                self.assertEqual(plates.timers[link], 31)
                self.assertEqual(terrain.tile(room - 1, cell % 10, cell // 10).foreground & 255, 255)

    def test_a_temple_blade_starts_and_cuts_like_a_ruins_scythe(self):
        # FrameAdv's environment 2 case (2:63e2-63f0) falls through to 5:57bc
        # and CheckScytheHit 5:588a; the blade is drawn by 10:0772.
        harness = Harness(10)
        self.addCleanup(harness.close)
        harness.number = 10
        settle(harness, 300)
        scene = harness.scene
        self.assertIn('scythes', scene.level_renderer.cavern_program)
        scene.jump_to_room(20, 0, 150, 1, redraw=False)
        press(harness, 'R', True)
        sounds = []
        for _ in range(40):
            harness.tick()
            sounds.extend(scene.sequence_state.sound_events)
            if not scene.combat.player.alive:
                break
        press(harness, 'R', False)
        self.assertEqual(scene.sequence_state.selected_sequence_id, CUT_SEQUENCE)
        self.assertEqual(scene.death.method, 5)
        self.assertIn(START_SOUND, sounds)
        self.assertIn(CUT_SOUND, sounds)
        self.assertEqual(scene.game.caverns.scythes.foreground[20, 5] & 0x40, 0x40)

    def test_a_key_can_run_a_frame_that_clears_the_control_bank(self):
        # A fresh Shift during SEQS 11 ran a frame whose wall bump cleared the
        # bank; the airborne handler then sampled None (AttributeError).
        _reached, _trace, harness = replay(13, ['climb', 'leapL5', 'tapR', 'jump', 'jump'], draw=False)
        self.addCleanup(harness.close)
        play(harness, MACROS['descendhangL'])

    def test_a_sword_death_at_the_altar_raises_the_shadow_and_it_opens_the_door(self):
        # The shadow's CheckPress (2:6602) on plate 4:12 opens door 32:12, the
        # level's only exit, and a sword kill leaves terrain_motion alive.
        harness = Harness(13)
        self.addCleanup(harness.close)
        harness.number = 13
        settle(harness, 300)
        scene = harness.scene
        scene.jump_to_room(3, 1, 470, 0, redraw=False)
        door = scene.level_map.tile(31, 2, 1)
        self.assertEqual((door.kind, door.foreground & 255), (17, 0))
        altar_death(harness)
        self.assertTrue(scene.combat.player.alive)
        self.assertEqual(scene.game.caverns.altar, -1)
        self.assertIsNone(scene.game.caverns.shadow)
        self.assertEqual(scene.level_map.tile(31, 2, 1).foreground & 255, 79)
