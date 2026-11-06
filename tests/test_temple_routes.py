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


# Level 12 is not finished: see the audit. This far, three loose floors hold
# gates 3:2, 5:0 and 2:9 open for good.
LEVEL_12_GATES = ['leapR11', 'leapcatchL20', 'leapL5', 'runR5', 'runL5', 'hopcatchL', 'crawlL',
                  'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'tapL', 'stepL',
                  'crawlL', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8', 'creepL8',
                  'runL8', 'hopcatchR', 'climb', 'hopcatchR', 'climb', 'climb', 'leapcatchR11',
                  'climb', 'climb', 'climb', 'climb', 'hopcatchR', 'leapcatchL11', 'tapL',
                  'hopcatchR', 'runL5', 'leapcatchR5', 'leapR11', 'jump', 'tapL', 'climb',
                  'hopR', 'runR11', 'hopcatchL', 'leapcatchL20', 'tapL', 'leapcatchL20',
                  'climb', 'leapcatchR5']

def blades_exported(number):
    path = ASSET_DIR / f'temple_level{number}.json'
    return path.is_file() and '"scythes"' in path.read_text(encoding='ascii')


# The way east and back. Plate 16:7 reopens gate 16:28 after 16:1 shut it, and the
# flask's genie reopens gate 18:19 after 24:22 shut it behind the Prince.
LEVEL_12_GENIE = ['leapR11', 'leapcatchL20', 'leapL5', 'runL11', 'leapcatchR5', 'runL5', 'runR20',
                  'leapcatchR11', 'leapL20', 'leapR11', 'descendhangR', 'descendhangR',
                  'leapcatchR20', 'climb', 'tapR', 'leapcatchR20', 'hopR', 'leapR20', 'crawlL',
                  'descendhangL', 'runL20', 'hopcatchL', 'runR5']

INSTALLED = all(blades_exported(number) for number in (10, 11, 12, 13))


@unittest.skipUnless(INSTALLED, 'Temple levels imported with their blades required')
class TempleRouteTests(unittest.TestCase):
    def test_each_level_can_be_finished_from_a_fresh_load(self):
        for number, route in ROUTES.items():
            with self.subTest(level=number):
                reached, trace, harness = replay(number, route, draw=False)
                harness.close()
                self.assertTrue(reached, trace[-3:])

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
