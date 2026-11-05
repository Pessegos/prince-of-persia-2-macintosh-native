"""Whole temple routes, run by tools/audit_temple_routes.py's real-key harness.

docs/research/temple-route-audit.md explains them. Each route is an exact key
script found by the audit's search. When a deliberate physics change breaks
one, run the audit again rather than editing its keys by hand.
"""

import unittest

from pop2.paths import ASSET_DIR
from tools.audit_temple_routes import Harness, MACROS, altar_death, play, replay, settle

ROUTES = {
    10: ['runR20', 'leapcatchR20', 'runR8', 'climb', 'hopR', 'leapR20', 'hopcatchR', 'leapR5',
         'hopcatchL'],
    13: ['runL8', 'hopcatchR', 'descendhangL', 'leapcatchL11', 'hopcatchL', 'leapcatchL5', 'leapL14',
         'leapcatchL20', 'leapcatchL8', 'stepL', 'tapL', 'leapL14', 'leapL20', 'leapL11', 'leapL14',
         'leapL11', 'altar', 'runR5', 'leapR11', 'leapcatchR5', 'stepR', 'leapR8', 'leapR20',
         'leapcatchR8', 'leapcatchL5'],
}

INSTALLED = all((ASSET_DIR / f'temple_level{number}.json').is_file() for number in (10, 11, 12, 13))


@unittest.skipUnless(INSTALLED, 'Imported temple levels required')
class TempleRouteTests(unittest.TestCase):
    def test_each_level_can_be_finished_from_a_fresh_load(self):
        for number, route in ROUTES.items():
            with self.subTest(level=number):
                reached, trace, harness = replay(number, route, draw=False)
                harness.close()
                self.assertTrue(reached, trace[-3:])

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
