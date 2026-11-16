"""Level 14 from its first room to the happy ending, with real keys.

One hidden run with the opponents on: the descent to the spell (NIS 5),
room 4 en garde, the false Princes of native room 6, the climb into the
palace, eight turns into the shadow, the fire and NIS 11. Two false Princes
are struck with the keys; the third is supplied (`combat._hurt`, the
port's own hit), since its floor leaves no room to draw on it. The fourth
then shimmers away and becomes the palace's Jaffar (9:19fa).
"""

import unittest
from unittest.mock import patch

from pop2.paths import ASSET_DIR

INSTALLED = all((ASSET_DIR / name).is_file() for name in ('Final.rsrc', 'final_level14.json'))

COPY_ROOM, LEFT_PALACE, RIGHT_PALACE = 5, 6, 7
ROUTE = ('crawlL', 'descendL', 'stepL', 'leapR5', 'runL5', 'leapcatchR20', 'tapR',
         'stab', 'sheathe', 'descendR', 'drawstab', 'sheathe', 'thirdcopy',
         'stepL', 'climb', 'climb', 'hopR', 'hopcatchL', 'hopcatchR', 'stepL', 'stepL', 'hopL')


def keys(text):
    """One tick per character: press, one tick released ('.' waits)."""
    script = []
    for character in text:
        key = {'c': 'ctrl', 'd': 'down', '.': None}[character]
        script += [((key,), (), 1), ((), (key,), 1)] if key else [((), (), 2)]
    return script


def third_copy(harness):
    combat = harness.scene.combat
    for figure in [guard for guard in combat.room_encounters[COPY_ROOM][0] if guard.row == 2]:
        combat._hurt('guard', figure, combat.player)
    harness.tick(60)


def settle_after_spell(audit):
    """The route tool's settle, which also waits out the spell scene and
    sheathes the sword SEQS 55 leaves drawn (9:05ec)."""
    original = audit.settle

    def settle(harness, limit=audit.REST_TIMEOUT):
        scene = harness.scene
        spell = False
        for _ in range(400):
            if scene.intro is None:
                break
            spell = True
            harness.tick()
        else:
            return False
        if spell and scene.sword_drawn and scene.combat.player.alive:
            for tick in range(60):
                audit.press(harness, 'down', tick % 4 == 0)
                harness.tick()
                if not scene.sword_drawn and scene._is_resting():
                    break
            audit.press(harness, 'down', False)
        return original(harness, limit)

    return settle


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class WholeRouteTests(unittest.TestCase):
    def test_from_the_roof_to_the_happy_ending(self):
        from tools import audit_temple_routes as audit

        macros = {'stab': keys('c....c....'), 'sheathe': keys('d.....'),
                  'drawstab': keys('c..........c..........'), 'thirdcopy': third_copy}
        seen = []

        def log(harness, name, moment):
            scene = harness.scene
            if moment == 'end':
                bank = scene.combat.room_encounters.get(COPY_ROOM, ([], []))[0]
                seen.append((scene.room_id, len(bank)))

        with patch.object(audit, 'settle', settle_after_spell(audit)), \
                patch.dict(audit.MACROS, macros):
            reached, trace, harness = audit.replay(14, ROUTE, draw=False, peaceful=False,
                                                   life=12, log=log)
        self.addCleanup(harness.close)
        self.assertFalse(reached)
        self.assertEqual(len(trace), len(ROUTE), trace)
        self.assertTrue(all(step[-1] for step in trace), trace)
        scene, combat = harness.scene, harness.scene.combat
        # The spell scene returned to native room 4; the stabs took one
        # false Prince each. He climbs down to the second: a false Prince
        # (actor 6) never stops a jump (FrameAdv 2:6cb4), so a leap onto
        # its floor carries him past it and over the next edge.
        self.assertEqual(seen[ROUTE.index('stepL')][0], 3)
        self.assertEqual(seen[ROUTE.index('stab')], (COPY_ROOM, 3))
        self.assertEqual(seen[ROUTE.index('drawstab')], (COPY_ROOM, 2))
        # The last one left room 6 as the palace's Jaffar.
        self.assertEqual(combat.room_encounters[COPY_ROOM][0], [])
        jaffar = combat.room_encounters[RIGHT_PALACE][0]
        self.assertEqual([(figure.row, figure.final_path) for figure in jaffar], [(0, True)])
        info = harness.player()
        self.assertEqual((info['room'], info['row']), (LEFT_PALACE, 0))

        # Eight standing turns leave the body; the shadow faces him and casts.
        magic = None
        for _ in range(60):
            magic = scene.game.caverns.final_magic
            if magic is not None and magic.shadow:
                break
            key = 'L' if scene.sequence_state.facing else 'R'
            audit.press(harness, key, True)
            harness.tick()
            audit.press(harness, key, False)
        self.assertTrue(magic.shadow)
        harness.tick(8)
        self.assertEqual(scene.sequence_state.facing, 1)
        audit.press(harness, 'ctrl', True)
        harness.tick(2)
        audit.press(harness, 'ctrl', False)
        self.assertEqual(scene.sequence_state.selected_sequence_id, 242)
        for _ in range(120):
            harness.tick()
            if scene.intro is not None:
                break
        self.assertFalse(jaffar[0].alive)
        self.assertEqual(jaffar[0].state.selected_sequence_id, 230)
        self.assertEqual(getattr(scene.intro, 'program_kind', None), 'happy')


if __name__ == '__main__':
    unittest.main()
