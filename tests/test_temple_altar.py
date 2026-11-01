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


class ShadowRuleTests(unittest.TestCase):
    def setUp(self):
        from pop2.sequence_runtime import SequenceState

        self.state = SequenceState(15, action=15, actor_type=1)
        self.steps = []

    def control(self, column, kid_x=600, kid_facing=0, step_result=44):
        from pop2.temple_shadow import auto_ctrl

        def step(distance):
            self.steps.append(distance)
            return step_result

        def run_jump():
            self.steps.append('run jump')

        return auto_ctrl(self.state, column, kid_x, kid_facing, step, run_jump)

    def test_the_shadow_rises_only_from_an_unburned_death_right_of_the_flame(self):
        # 10:2af0-2b0e: pose 185, X > 375, row 1, mode != 12, a5-0x4fd4 = 1.
        from pop2.temple_shadow import shadow_rises

        self.assertTrue(shadow_rises(1, 376, 185, 0, 1))
        self.assertFalse(shadow_rises(1, 375, 185, 0, 1))
        self.assertFalse(shadow_rises(2, 600, 185, 0, 1))
        self.assertFalse(shadow_rises(1, 600, 184, 0, 1))
        self.assertFalse(shadow_rises(1, 600, 185, 12, 1))
        # Before the death message (0) and once risen (-1).
        self.assertFalse(shadow_rises(1, 600, 185, 0, 0))
        self.assertFalse(shadow_rises(1, 600, 185, 0, -1))

    def test_facing_left_it_runs_steps_and_jumps_toward_the_flame(self):
        # 10:2860-28a0: column >= 8 runs (SEQS 1); 6-7 DoStepFwd(0), and its
        # warning step (SEQS 44) becomes the standing jump (SEQS 3).
        self.assertEqual(self.control(9), (1, None))
        self.assertEqual(self.control(7), (3, None))
        self.assertEqual(self.control(6, step_result=31), (None, None))
        self.assertEqual(self.steps, [0, 0])
        # Running poses at column >= 6 try DoRunJump(4).
        self.state.action = 9
        self.assertEqual(self.control(7), (None, None))
        self.assertEqual(self.steps[-1], 'run jump')

    def test_at_the_flame_it_takes_it_then_turns_with_song_251(self):
        from pop2.temple_shadow import IMBUED_MODE, TAKE_FLAME_SEQUENCE

        self.assertEqual(self.control(2), (TAKE_FLAME_SEQUENCE, None))
        self.state.selected_sequence_id = TAKE_FLAME_SEQUENCE
        self.assertEqual(self.control(2), (5, 'turn'))
        self.state.selected_sequence_id, self.state.sequence_mode = 5, IMBUED_MODE
        self.assertEqual(self.control(2), (5, 'turn'))
        # Facing right without the flame it only turns back (10:28d4).
        self.state.facing, self.state.sequence_mode = 1, 0
        self.assertEqual(self.control(2), (5, None))

    def test_with_the_flame_it_jumps_back_and_lies_down_on_the_body(self):
        from pop2.coordinates import scene_x
        from pop2.temple_shadow import IMBUED_MODE

        self.state.facing, self.state.sequence_mode = 1, IMBUED_MODE
        # 10:2942-2958: the warning step becomes the long jump (SEQS 247).
        self.assertEqual(self.control(2), (247, None))
        # 10:28e2-293e: d = Kid X - (X - 10), +12 * a5-0x4b94[facing] when
        # both face the same way; d > 4 steps DoStepFwd(d).
        self.state.target_x = scene_x(550)
        self.assertEqual(self.control(7, kid_x=600, kid_facing=0), (None, None))
        self.assertEqual(self.steps[-1], 60)
        self.assertEqual(self.control(7, kid_x=600, kid_facing=1), (None, None))
        self.assertEqual(self.steps[-1], 48)
        # d <= 4: AddCharX(d), then SEQS 71 (same facing) or a turn.
        self.state.target_x = scene_x(606)
        self.assertEqual(self.control(7, kid_x=600, kid_facing=0), (5, None))
        self.assertEqual(self.state.target_x, scene_x(610))
        self.state.facing = 0
        self.assertEqual(self.control(7), (71, None))

    def test_pose_events(self):
        from pop2.temple_shadow import IMBUED_MODE

        for pose, event in ((103, 'catch'), (106, 'catch'), (91, 'hang'), (154, 'flare'),
                            (153, None), (185, None)):
            self.state.action = pose
            self.assertEqual(self.control(2), (None, event), pose)
        self.state.sequence_mode = IMBUED_MODE
        self.state.action = 153
        self.assertEqual(self.control(2), (None, 'palette'))
        self.state.action = 185
        self.assertEqual(self.control(7), (None, 'merge'))
        # 10:2a36: pose 44 -> SEQS 13 and AddCharX(-12) (facing left: +12).
        self.state.action, x = 44, self.state.target_x
        self.assertEqual(self.control(2), (13, None))
        self.assertEqual(self.state.target_x, x + 12)

    def test_the_flame_cycles_nine_shapes_and_the_shadow_has_footsteps(self):
        # SetupShadowFlame 4:2650; AnimCharTap callback 1 for any actor type.
        # Before, a type-1 footstep raised an unsupported opcode.
        from pop2.sequence_runtime import SequenceRuntime, SequenceState
        from pop2.temple_shadow import flame_shape

        self.assertEqual([flame_shape(frame) for frame in (0, 8, 9, 13)], [4102, 4110, 4102, 4106])
        runtime = SequenceRuntime({1: (-15, 1, 5, -1, 1)}, SequenceState(1, actor_type=1, level_kind=2))
        runtime.next_frame()
        self.assertEqual(runtime.state.sound_events, [0x127])

    def test_the_shadow_is_saved(self):
        from pop2.cavern_state import CavernState
        from pop2.save_game import _pack, _unpack
        from pop2.sequence_runtime import SequenceState
        from pop2.temple_shadow import TempleShadow
        from pop2.terrain import TerrainMotion

        shadow = TempleShadow(SequenceState(231, action=185, actor_type=1), TerrainMotion(3, 1),
                              True, 4077)
        self.assertEqual(_unpack(_pack(shadow), None, None), shadow)
        fields = _pack(CavernState())['fields']
        self.assertIn('shadow', fields)
        self.assertIn('altar', fields)


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

    def test_the_shadow_takes_the_flame_and_revives_the_prince(self):
        from pop2.coordinates import native_x, scene_x
        from pop2.temple_shadow import FLAME_PALETTE, IMBUED_MODE, TAKE_FLAME_SEQUENCE

        scene = self.scene
        scene.load_level(13)
        scene.jump_to_room(3, row=1, x=scene_x(600), facing=0)
        state, caverns = scene.sequence_state, scene.game.caverns
        # A death right of the chasm (SEQS 213 lays the Prince at pose 185).
        scene.combat.player.life = 0
        scene.terrain_motion.dead = True
        state.select(213)
        scene.death.begin(1)
        sequences, rows, flares, palettes = set(), set(), set(), set()
        risen = None
        for frame in range(300):
            self.tick()
            shadow = caverns.shadow
            if shadow is None:
                if risen is not None:
                    break
                continue
            if risen is None:
                # 10:2b32 after KeepTime's message: a5-0x4fd4 = -1.
                risen = frame
                self.assertTrue(scene.death.prompt_visible)
                self.assertEqual(caverns.altar, -1)
                self.assertEqual(shadow.state.actor_type, 1)
            sequences.add(shadow.state.selected_sequence_id)
            rows.add(shadow.motion.row)
            flares.add(bool(caverns.flame & 0x80))
            palettes.add(shadow.palette)
            if frame % 25 == 0:
                scene.render()
        self.assertIsNotNone(risen)
        self.assertIsNone(caverns.shadow)
        # The standing jump falls short of the altar: the catch and climb
        # (SEQS 15/10), the flame (232), the long jump back (247), lying down (71).
        self.assertTrue({3, 15, 10, TAKE_FLAME_SEQUENCE, 5, 247, 71} <= sequences, sequences)
        self.assertIn(2, rows)
        self.assertIn(True, flares)
        self.assertIn(FLAME_PALETTE, palettes)
        # 10:27d8: the Prince rises (SEQS 231) alive, imbued, the message gone.
        self.assertEqual(state.selected_sequence_id, 231)
        self.assertEqual(state.sequence_mode, IMBUED_MODE)
        self.assertFalse(scene.terrain_motion.dead)
        self.assertEqual(scene.combat.player.life, scene.combat.player.max_life)
        self.assertFalse(scene.death.prompt_visible)
        self.assertEqual(native_x(state.target_x), 599)
        scene.render()

    def test_restarting_clears_the_altar(self):
        scene = self.scene
        scene.load_level(13)
        scene.game.caverns.altar = -1
        scene.restart_level_now(redraw=False)
        self.assertEqual(scene.game.caverns.altar, 0)
        self.assertIsNone(scene.game.caverns.shadow)



if __name__ == '__main__':
    unittest.main()
