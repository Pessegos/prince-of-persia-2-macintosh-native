import unittest

from pop2.paths import ASSET_DIR


class WorldPhaseTableTests(unittest.TestCase):
    def test_each_tick_mode_keeps_the_existing_phase_order(self):
        # docs/research/frame-phase-order.md records the port's order before
        # the orchestrator; changes need original evidence.
        from pop2.frame_phases import WORLD_PHASES

        # 'environment' (2:7124, after the opponents) holds the bridge check;
        # 'entry' (CutAllOpponents 6:4382, PrepCut 2:532c) follows the hook.
        full = ('terrain', 'combat', 'environment', 'harbor', 'entry', 'level_events', 'rebirth',
                'audio', 'render')
        self.assertEqual(WORLD_PHASES, {
            'potion': ('terrain', 'combat', 'environment', 'entry', 'level_events', 'rebirth',
                       'audio', 'render'),
            'falling': full, 'locked': full, 'opening': ('combat', 'audio', 'render'),
            'ordinary': full})


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported resources required')
class WorldPhaseTraceTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def modes(self):
        return [mode for mode, phase in self.scene.frame_trace if phase == 'terrain'
                or mode == 'opening' and phase == 'combat']

    def test_standing_runs_the_ordinary_phases_once_per_tick(self):
        scene = self.scene
        self.tick(20)
        scene.frame_trace = []
        self.tick(3)
        self.assertEqual(self.modes(), ['ordinary'] * 3)
        self.assertEqual([phase for _mode, phase in scene.frame_trace[:9]],
                         ['terrain', 'combat', 'environment', 'harbor', 'entry', 'level_events',
                          'rebirth', 'audio', 'render'])

    def test_the_bridge_check_runs_after_the_opponents(self):
        # FrameAdv 2:6224: the opponents (2:626c) and strikes (2:627c-6280)
        # precede the environment hook 2:628c (2:7124) -> 8:3b92 (BridgeCheckBreak).
        from unittest.mock import patch
        from pop2.environments import Caverns

        scene = self.scene
        self.tick(20)
        calls = []
        combat = scene.advance_combat
        scene.advance_combat = lambda *args: (calls.append('combat'), combat(*args))[1]
        bridge = Caverns.advance_bridge
        with patch.object(Caverns, 'advance_bridge',
                          lambda environment: (calls.append('bridge'), bridge(environment))[1]):
            scene.jump_to_room(9, 1, 200, 1)
            self.tick()
        self.assertEqual(calls, ['combat', 'bridge'])

    def test_a_falling_prince_runs_the_falling_phases(self):
        scene = self.scene
        self.tick(20)
        scene.terrain_motion.falling = True
        scene.frame_trace = []
        self.tick()
        self.assertEqual(self.modes()[0], 'falling')


@unittest.skipUnless((ASSET_DIR / 'Skeleton.rsrc').is_file(), 'Imported skeleton artwork required')
class RoomCrossingTickTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def test_the_crossing_frame_steps_the_room_left_before_the_cut(self):
        # FrameAdv 2:6224: the Prince (2:625c), the opponent pass of the room
        # he is leaving (2:626c), strikes and CheckAlert, and only then
        # CutAllOpponents 6:4382 (CutChar, X -510 at 6:48ba) and PrepCut's
        # InitOpps for the new room. Before, the port entered the new room in
        # its terrain phase, so the crossing frame stepped room 16's
        # opponents with the Prince already at X 23 there.
        import random
        from unittest.mock import patch
        from tests.test_terrain import RooftopSceneTests

        scene = self.scene
        scene.load_level(3)
        scene.peaceful = False
        scene.combat.rng = random.Random(17)
        scene.jump_to_room(14, row=2, x=300, facing=1)
        scene.in_animation_tick = True
        heap = scene.combat.guards[0]
        seen = []
        advance = type(scene.combat).advance_guard

        def record(combat):
            seen.append((scene.room_id, combat.player.room, combat.player.state.target_x,
                         [guard.room for guard in combat.active_guards()]))
            advance(combat)

        scene.horizontal_key(None, 1, True)
        with patch.object(scene, 'render'), patch.object(type(scene.combat), 'advance_guard', record):
            for _ in range(30):
                RooftopSceneTests.tick(self)
                if scene.room_id == 16:
                    break
        self.assertEqual(scene.room_id, 16)
        room, combat_room, x, rooms = seen[-1]
        # The scene has moved on, the opponent pass has not: room 14 with the
        # Prince at 533, outside it; the cut follows the pass.
        self.assertEqual((room, combat_room, x, rooms), (16, 14, 533, [14]))
        self.assertEqual((scene.combat.player.room, scene.sequence_state.target_x), (16, 23))
        # The heap 2f4e moved into room 16 was not stepped in that frame.
        self.assertEqual((heap.room, heap.skeleton.phase, heap.alive), (16, 'dormant', False))

    def test_the_environment_hook_sees_the_room_left_before_the_cut(self):
        # FrameAdv 2:6284-6290: the environment hook 2:7124 runs before
        # CutAllOpponents 6:4382, so -0x4fc2 is still the room being left
        # and the Kid's X is outside it. The port ran the hook (and the
        # rooftops' harbor phase) after the entry, in the new room's terms.
        from unittest.mock import patch
        from tests.test_terrain import RooftopSceneTests

        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(14, row=2, x=300, facing=1)
        scene.in_animation_tick = True
        seen = []
        hook = scene.advance_environment

        def record():
            seen.append((scene.room_id, scene.terrain_motion.room, scene.terrain_motion.row,
                         scene.sequence_state.target_x, scene.player_x, scene.combat.player.room))
            # A hook that redraws draws the room it sees.
            room = scene.level_renderer.enter_room(scene.room_id, scene.game.caverns)
            scene.background, scene.foreground = room.background, room.foreground
            hook()

        scene.horizontal_key(None, 1, True)
        with patch.object(scene, 'render'), patch.object(scene, 'advance_environment', record):
            for _ in range(30):
                RooftopSceneTests.tick(self)
                if scene.room_id == 16:
                    break
        self.assertEqual(scene.room_id, 16)
        self.assertEqual(seen[-1], (14, 14, 2, 533, 533, 14))
        self.assertEqual((scene.terrain_motion.room, scene.sequence_state.target_x, scene.player_x,
                          scene.combat.player.room), (16, 23, 23, 16))
        # The new room's scenery is back after the hook redrew the room left.
        drawn = scene.level_renderer.enter_room(16, scene.game.caverns)
        self.assertIs(scene.background, drawn.background)


if __name__ == '__main__':
    unittest.main()
