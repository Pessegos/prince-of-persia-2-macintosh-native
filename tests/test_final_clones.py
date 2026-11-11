"""Macintosh room-6 copies use Prince-shaped artwork in the final tower."""

import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless(all((ASSET_DIR / name).is_file()
                         for name in ('Prince.rsrc', 'Kid.rsrc', 'Guard.rsrc')),
                     'Imported Macintosh character resources required')
class FinalCloneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.game_session import GameResources

        cls.resources = GameResources.load()

    def test_four_original_records_are_clones_only_in_room_six(self):
        from pop2.game_session import GameSession

        game = GameSession.load(self.resources, 14)
        game.place(5, 1, 250, 0)
        self.assertEqual([actor.guard_record.cell for actor in game.combat.guards],
                         [25, 3, 7, 14])
        self.assertTrue(all(actor.final_clone and actor.state.action == 166
                            for actor in game.combat.guards))
        game.place(9, 1, 250, 0)
        self.assertTrue(all(not actor.final_clone for actor in game.combat.guards))

    def test_clone_body_uses_kid_frame_and_final_palette(self):
        from pop2.development_map import map_enemies

        art, actors = map_enemies(self.resources.level(14), {5: (0, 0)})
        self.assertEqual(len(actors[5]), 4)
        actor = actors[5][0]
        clone = art.final_clones.body(actor.state)
        guard = art.body(actor.state, actor.palette_variant)
        self.assertEqual(clone.size, (18, 79))
        self.assertEqual(clone.getpixel((7, 20)), (249, 18, 6, 255))
        self.assertNotEqual(clone.tobytes(), guard.tobytes())

    def test_room_six_live_render_displays_red_shirt(self):
        from pop2.scene_prototype import ScenePrototype

        scene = ScenePrototype(level_number=14)
        try:
            scene.root.withdraw()
            if scene.animation_after_id is not None:
                scene.root.after_cancel(scene.animation_after_id)
                scene.animation_after_id = None
            scene.jump_to_room(5, row=1, x=120, redraw=False)
            scene.render()
            self.assertEqual(scene.native_viewport.getpixel((196, 50)),
                             (249, 18, 6, 255))
        finally:
            scene.root.destroy()
