import unittest

from pop2.paths import ASSET_DIR


class AltarRuleTests(unittest.TestCase):
    def test_the_flare_counts_down_then_returns_to_the_ordinary_cycle(self):
        # 10:2cc2 with bit 0x80: low bits down to 0x80, then 0 (record 2).
        # DrawTempSacredFlame draws a5-0x2b7c[counter & 0x7f]. Before, a
        # flare counter was treated as an ordinary one (record 0x85 + 2).
        from pop2.caverns import FLARE, advance_flame, flame_record

        counters = [FLARE]
        for _ in range(6):
            counters.append(advance_flame(counters[-1]))
        self.assertEqual(counters, [0x85, 0x84, 0x83, 0x82, 0x81, 0x80, 0])
        self.assertEqual([flame_record(counter) for counter in counters], [14, 16, 16, 15, 14, 14, 2])
        self.assertEqual(advance_flame(11), 0)
        self.assertEqual(flame_record(11), 13)

    def test_the_altar_burns_at_347_and_plays_its_song_up_to_375(self):
        from pop2.temple_altar import altar_event

        self.assertEqual(altar_event(13, 3, 1, 347, 2, False), 'burn')
        self.assertEqual(altar_event(13, 3, 1, 348, 2, False), 'song')
        self.assertIsNone(altar_event(13, 3, 1, 348, 2, True))
        self.assertEqual(altar_event(13, 3, 1, 375, 1, False), 'song')
        self.assertIsNone(altar_event(13, 3, 1, 376, 2, False))
        # Another row, room or level, or the burn already selected.
        self.assertIsNone(altar_event(13, 3, 2, 300, 2, False))
        self.assertIsNone(altar_event(13, 4, 1, 300, 2, False))
        self.assertIsNone(altar_event(12, 3, 1, 300, 2, False))
        self.assertIsNone(altar_event(13, 3, 1, 300, 230, False))

    def test_opcode_minus_24_flashes_and_restores_the_palette(self):
        # AnimChar 4:2fb0. Before, SEQS 230/232 raised an unsupported opcode.
        from pop2.sequence_runtime import SequenceRuntime, SequenceState

        sequences = {230: (-7, 1, -21, 0, -24, 1, 225, 50, 51, -24, 0, -5, 4, 306, -23),
                     244: (-24, 1, 225, 153, -1, 244)}
        runtime = SequenceRuntime(sequences, SequenceState(230, actor_type=0, level_kind=2))
        self.assertEqual(runtime.next_frame().action, 50)
        self.assertEqual(runtime.state.sequence_events, [(-24, (225,))])
        runtime.state.sequence_events.clear()
        self.assertEqual(runtime.next_frame().action, 51)
        self.assertEqual(runtime.next_frame().action, 306)
        self.assertEqual(runtime.state.sequence_events, [(-24, ())])
        final = SequenceRuntime(sequences, SequenceState(244, actor_type=0, level_kind=6))
        final.next_frame()
        self.assertEqual(final.state.sequence_events, [(-24, (209,))])

    def test_the_burn_death_song_is_the_seventeenth_entry(self):
        # AddKidDeathSong 5:4afc reads a5-0x4396[16] = 250 for method 16.
        from pop2.audio import AudioEngine

        engine = AudioEngine.__new__(AudioEngine)
        engine.manifest = {'death_cues': [38] * 16}
        added = []
        engine.add_song = added.append
        engine.death_song(16)
        engine.death_song(3)
        self.assertEqual(added, [250, 38])


@unittest.skipUnless((ASSET_DIR / 'temple_level13.json').is_file()
                     and (ASSET_DIR / 'Temple.rsrc').is_file(), 'Imported level-13 scenery required')
class AltarSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_walking_into_the_flame_burns_the_prince(self):
        from pop2.coordinates import native_x, scene_x
        from pop2.temple_altar import BURN_DEATH_METHOD, BURN_SEQUENCE

        scene = self.scene
        scene.load_level(13)
        scene.jump_to_room(3, row=1, x=scene_x(352), facing=0)
        self.assertEqual(scene.room_id, 3)
        flashes, poses = [], []
        for _ in range(40):
            if scene.sequence_state.selected_sequence_id == BURN_SEQUENCE:
                break
            scene.sequence_state.target_x = scene.sequence_state.current_x = scene_x(346)
            scene.player_x = scene.sequence_state.target_x
            self.tick()
        self.assertEqual(scene.sequence_state.selected_sequence_id, BURN_SEQUENCE)
        self.assertEqual(native_x(scene.sequence_state.target_x), 335)
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(scene.death.method, BURN_DEATH_METHOD)
        self.assertTrue(scene.game.caverns.flame & 0x80)
        for _ in range(30):
            self.tick()
            flashes.append(getattr(scene, 'palette_flash', None))
            poses.append(scene.sequence_state.action)
        # SEQS 230: white flash over poses 50/51, burning 306-315, then 185.
        self.assertIn(225, flashes)
        self.assertIsNone(flashes[-1])
        self.assertIn(306, poses)
        self.assertEqual(poses[-1], 185)
        self.assertEqual(scene.sequence_state.sequence_mode, 12)


if __name__ == '__main__':
    unittest.main()
