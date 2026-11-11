"""Macintosh room-6 copies use Prince-shaped artwork in the final tower."""

import unittest
import struct

from pop2.paths import ASSET_DIR


@unittest.skipUnless(all((ASSET_DIR / name).is_file()
                         for name in ('Prince.rsrc', 'Kid.rsrc', 'Guard.rsrc')),
                     'Imported Macintosh character resources required')
class FinalCloneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.game_session import GameResources

        cls.resources = GameResources.load()

    def test_raw_kinds_distinguish_scripted_copies_and_room_ten_guard(self):
        from pop2.combat import GuardSpawn
        from pop2.game_session import GameSession

        game = GameSession.load(self.resources, 14)
        level = game.level.data
        self.assertEqual([struct.unpack_from('>h', level, 0x20e6 + 6 * 0xc0 + 2
                                             + index * 38 + 0x18)[0]
                          for index in range(4)], [3] * 4)
        self.assertEqual(struct.unpack_from('>h', level, 0x20e6 + 10 * 0xc0 + 2 + 0x18)[0], 0)
        self.assertEqual(struct.unpack_from('>h', level, 0x20e6 + 11 * 0xc0 + 2 + 0x18)[0], 3)
        self.assertEqual([spawn.actor_type for spawn in GuardSpawn.all_from_level(level, 10)], [6])
        game.place(5, 1, 250, 0)
        self.assertEqual([actor.guard_record.cell for actor in game.combat.guards],
                         [25, 3, 7, 14])
        self.assertTrue(all(actor.final_clone and actor.state.actor_type == 6
                            and actor.state.sequence_id == 2 and actor.state.action == 15
                            for actor in game.combat.guards))
        game.place(9, 1, 250, 0)
        self.assertTrue(all(not actor.final_clone and actor.state.actor_type == 2
                            for actor in game.combat.guards))

    def test_clone_body_uses_kid_frame_and_final_palette(self):
        from dataclasses import replace
        from pop2.development_map import map_enemies

        art, actors = map_enemies(self.resources.level(14), {5: (0, 0)})
        self.assertEqual(len(actors[5]), 4)
        actor = actors[5][0]
        clone = art.final_clones.body(actor.state)
        guard = art.body(replace(actor.state, actor_type=2, action=166), actor.palette_variant)
        self.assertEqual(clone.size, (18, 79))
        self.assertEqual(clone.getpixel((7, 20)), (168, 4, 63, 255))
        self.assertNotEqual(clone.tobytes(), guard.tobytes())

    def test_room_six_live_render_uses_false_prince_palette(self):
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
                             (41, 8, 24, 255))
            scene.schedule_next_animation = lambda: None
            for _ in range(8):
                scene.advance_animation()
            self.assertEqual([(actor.state.actor_type, actor.state.source_sequence_id)
                              for actor in scene.combat.room_encounters[5][0]], [(6, 2)] * 4)
        finally:
            scene.root.destroy()

    def test_scripted_actor_type_and_sequence_survive_snapshot(self):
        from pathlib import Path
        import tempfile
        from pop2.game_session import GameSession
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        game = GameSession.load(self.resources, 14)
        game.place(5, 1, 250, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'false-princes.pop2save'
            write_save(path, capture_snapshot(game))
            restored, _ = read_snapshot(path, self.resources)
        self.assertEqual([(actor.state.actor_type, actor.state.sequence_id,
                           actor.state.action, actor.final_clone)
                          for actor in restored.combat.guards], [(6, 2, 15, True)] * 4)

    def test_snapshot_from_first_visual_patch_migrates_marked_guard_type(self):
        from pathlib import Path
        import tempfile
        from pop2.game_session import GameSession
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        game = GameSession.load(self.resources, 14)
        game.place(5, 1, 250, 0)
        for actor in game.combat.guards:
            actor.state.actor_type = 2
            actor.state.select(77)
            actor.runtime.next_frame()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'first-visual-patch.pop2save'
            write_save(path, capture_snapshot(game))
            restored, _ = read_snapshot(path, self.resources)
        self.assertTrue(all(actor.state.actor_type == 6 and actor.final_clone
                            for actor in restored.combat.guards))

    def test_older_snapshot_without_copy_marker_still_loads(self):
        from pathlib import Path
        import tempfile
        from pop2.game_session import GameSession
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        def remove_marker(item):
            if isinstance(item, dict):
                if item.get('record') == 'Fighter':
                    item['fields'].pop('final_clone', None)
                for value in item.values():
                    remove_marker(value)
            elif isinstance(item, list):
                for value in item:
                    remove_marker(value)

        game = GameSession.load(self.resources, 14)
        game.place(9, 0, 250, 0)
        document = capture_snapshot(game)
        remove_marker(document)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'older.pop2save'
            write_save(path, document)
            restored, _ = read_snapshot(path, self.resources)
        self.assertEqual(restored.combat.guards[0].state.actor_type, 2)
