import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.audio import AudioEngine
from pop2.rebirth import Checkpoint, DeathState, level_checkpoints
from pop2.render_opening import load_resource_file, ROOM_HEIGHT
from pop2.scene_prototype import BufferedCommand
from pop2.terrain import floor_contact_x
import tests.test_terrain as terrain_tests
from tests.test_audio import TimedPlayback


class RebirthRulesTests(unittest.TestCase):
    def test_checkpoint_slots_are_not_renumbered_when_disabled(self):
        level = bytearray(0x39ae)
        struct.pack_into(">4h", level, 0x39a6, 0, 90, 15, 5)
        self.assertEqual(level_checkpoints(level), (Checkpoint(2, 14, 5),))
        struct.pack_into(">4h", level, 0x39a6, 90, 0, 2, 30)
        self.assertEqual(level_checkpoints(level), ())

    def test_original_level_checkpoint_table(self):
        resources = load_resource_file("Prince.rsrc")["LEVL"]
        expected = {
            1: ((2, 15, 5),), 5: ((1, 16, 20), (2, 12, 11)),
            7: ((2, 3, 0),), 8: ((1, 9, 25), (2, 12, 15)),
            11: ((2, 6, 17),), 12: ((1, 11, 10), (2, 2, 9)),
            13: ((1, 32, 19),), 14: ((2, 4, 14),),
        }
        for number in range(1, 15):
            with self.subTest(level=number):
                actual = level_checkpoints(resources[1999 + number]["data"])
                self.assertEqual(tuple((p.slot, p.room + 1, p.tile) for p in actual),
                                 expected.get(number, ()))

    def test_checkpoint_requires_the_native_contact_cell_and_live_nonfall_mode(self):
        point = Checkpoint(2, 14, 5)
        self.assertTrue(point.matches(14, 0, point.x + 4, 1, True))
        self.assertTrue(point.matches(14, 0, point.x + 4, 5, True))
        for room, row, x, mode, alive in ((13, 0, 277, 1, True),
                                         (14, 1, 277, 1, True),
                                         (14, 0, 200, 1, True),
                                         (14, 0, 281, 4, True),
                                         (14, 0, 281, 1, False)):
            self.assertFalse(point.matches(room, row, x, mode, alive))
        self.assertEqual((point.row, point.x), (0, 277))

    def test_level_eight_first_checkpoint_has_a_story_flag_gate(self):
        point = Checkpoint(1, 8, 25)
        self.assertFalse(point.matches(8, 2, point.x + 4, 1, True, 8, 0))
        self.assertTrue(point.matches(8, 2, point.x + 4, 1, True, 8, 1))

    def test_death_counter_waits_for_the_dead_pose_and_seventh_update(self):
        death = DeathState()
        death.begin(15)
        death.begin(2)
        for _ in range(50):
            death.advance(177, 1 / 12)
        self.assertEqual((death.counter, death.method), (0, 15))
        for _ in range(6):
            death.advance(185, 1 / 12)
            self.assertFalse(death.can_restart)
        death.advance(185, 1 / 12)
        self.assertTrue(death.can_restart)
        self.assertFalse(death.prompt_visible)
        death.advance(185, 1 / 12)
        self.assertTrue(death.prompt_visible)  # No audio attached in a silent harness.

    def test_prompt_waits_for_the_water_cue_but_retry_does_not(self):
        audio = AudioEngine(playback=object())
        audio.playback = TimedPlayback(audio.cues)
        death = DeathState()
        death.begin(15)
        for _ in range(7 + 111):
            audio.playback.advance(1 / 12)
            death.advance(185, 1 / 12, audio)
            audio.flush()
        self.assertTrue(death.can_restart)
        self.assertFalse(death.prompt_visible)
        audio.playback.advance(1 / 12)
        death.advance(185, 1 / 12, audio)
        self.assertTrue(death.prompt_visible)
        self.assertEqual(death.counter, 8)


class RebirthSceneTests(unittest.TestCase):
    def setUp(self):
        terrain_tests.RooftopSceneTests.setUp(self)
        self.scene.audio = AudioEngine(playback=object())
        self.scene.audio.playback = TimedPlayback(self.scene.audio.cues)

    def tick(self, count=1):
        for _ in range(count):
            interval = self.scene.current_animation_interval_ms() / 1000
            self.now += interval
            self.scene.audio.playback.advance(interval)
            with patch("pop2.scene_prototype.time.perf_counter", return_value=self.now):
                self.scene.advance_animation()

    def event(self, key, state=0):
        return SimpleNamespace(keysym=key, state=state)

    def checkpoint(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(14, row=0, x=277, facing=0)
        self.tick()
        self.assertIsNotNone(scene.checkpoint)
        return scene.checkpoint

    def die(self, method=15, settled=True):
        scene = self.scene
        scene.combat.player.life = 0
        scene.terrain_motion.dead = True
        scene.sequence_state.sequence_id, scene.sequence_state.cursor = 22, 0
        scene.sequence_state.action = scene.action = 185 if settled else 177
        scene.death.begin(method)

    def eligible(self):
        for _ in range(40):
            if self.scene.death.can_restart:
                return
            self.tick()
        self.fail("Death animation never reached the retry gate")

    def test_any_key_restarts_before_the_prompt_and_consumes_that_key(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_screen("1")
        self.die()
        self.eligible()
        self.assertFalse(scene.death.prompt_visible)
        self.assertEqual(scene.dev_key_press(self.event("Up")), "break")
        self.assertTrue(scene.opening.active)
        self.assertEqual(scene.combat.player.life, 3)
        self.assertEqual(scene.room_id, 3)
        self.assertEqual(scene.death.counter, -1)
        self.assertFalse(scene.up_held)
        self.assertIsNone(scene.pending_action)
        self.assertIn("Up", scene.pause_resume_keys)
        scene.dev_key_release(self.event("Up"))
        self.assertNotIn("Up", scene.pause_resume_keys)

    def test_held_space_restarts_at_the_first_eligible_poll(self):
        scene = self.scene
        self.checkpoint()
        self.die()
        scene.dev_key_press(self.event("space"))
        for _ in range(7):
            self.tick()
            self.assertFalse(scene.combat.player.alive)
        self.tick()
        self.assertTrue(scene.combat.player.alive)
        self.assertEqual((scene.room_id, scene.player_x), (14, 277))
        self.assertIn("space", scene.pause_resume_keys)
        self.assertFalse(scene.opening.active)

    def test_an_early_released_key_is_not_buffered_for_retry(self):
        scene = self.scene
        self.checkpoint()
        self.die()
        scene.dev_key_press(self.event("space"))
        scene.dev_key_release(self.event("space"))
        self.tick(25)
        self.assertFalse(scene.combat.player.alive)
        self.assertTrue(scene.death.can_restart)
        self.assertFalse(scene.death.prompt_visible)

    def test_checkpoint_restores_native_anchor_facing_full_health_and_world(self):
        scene = self.scene
        snapshot = self.checkpoint()
        scene.combat.player.max_life = 5
        scene.checkpoint = None
        scene.advance_rebirth()
        snapshot = scene.checkpoint
        guard = scene.combat.room_encounters[3][0][0]
        life = guard.life
        guard.life = 0
        scene.combat.room_encounters[3][1].clear()
        scene.combat.player.max_life = 6
        scene.sequence_state.facing = 1
        scene.pending_action = BufferedCommand("jump", 1)
        scene.harbor.ship_frame = 90
        self.die()
        self.eligible()
        self.assertTrue(scene.restart_after_death())
        self.assertIs(scene.checkpoint, snapshot)
        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x,
                          scene.sequence_state.facing, scene.action), (14, 0, 277, 0, 15))
        self.assertEqual((scene.combat.player.life, scene.combat.player.max_life), (5, 5))
        self.assertFalse(scene.opening.active)
        self.assertEqual(scene.harbor.ship_frame, 0)
        self.assertIsNone(scene.pending_action)
        self.assertEqual(scene.combat.room_encounters[3][0][0].life, life)
        self.assertTrue(scene.combat.room_encounters[3][1])
        restored = scene.combat.room_encounters[3][0][0]
        self.assertIs(restored.runtime.sequences, scene.sequences)
        restored.life = 0
        self.die()
        self.eligible()
        scene.restart_after_death()
        self.assertEqual(scene.combat.room_encounters[3][0][0].life, life)

    def test_revisiting_same_checkpoint_does_not_overwrite_it(self):
        scene = self.scene
        snapshot = self.checkpoint()
        scene.combat.player.max_life = 5
        scene.combat.room_encounters[3][0][0].life = 0
        self.tick(5)
        self.assertIs(scene.checkpoint, snapshot)
        self.assertEqual(snapshot.max_life, 3)
        self.assertTrue(snapshot.room_encounters[3][0][0].alive)

    def test_real_descent_from_screen_seven_captures_checkpoint_after_landing(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(11, row=1, x=340, facing=1)
        scene.set_key_state("shift", True)
        scene.set_key_state("down", True)
        for _ in range(100):
            if scene.action == 91:
                scene.set_key_state("shift", False)
                scene.set_key_state("down", False)
            self.tick()
            if scene.checkpoint is not None:
                break
        self.assertIsNotNone(scene.checkpoint)
        self.assertEqual(scene.checkpoint.checkpoint, Checkpoint(2, 14, 5))
        self.assertNotEqual(scene.sequence_state.animation_state, 4)
        contact = floor_contact_x(scene.player_x, scene.sequence_state.facing,
                                  scene.frames[scene.action])
        self.assertTrue(scene.checkpoint.checkpoint.matches(
            scene.room_id, scene.terrain_motion.row, contact,
            scene.sequence_state.animation_state, True))

    def test_water_death_reaches_prompt_and_restores_the_checkpoint(self):
        scene = self.scene
        snapshot = self.checkpoint()
        scene.jump_to_room(18, row=2, x=120, facing=0, preserve_checkpoint=True)
        scene.sequence_state.current_y = 40
        scene.sequence_state.animation_state = 4
        scene.terrain_motion.falling = True
        scene.physics.select(scene.sequence_runtime, 23)
        first_dead = False
        for _ in range(180):
            self.tick()
            if not scene.combat.player.alive and not first_dead:
                self.assertEqual(scene.death.counter, 0)
                first_dead = True
            if scene.death.prompt_visible:
                break
        self.assertTrue(first_dead)
        self.assertEqual(scene.death.method, 15)
        self.assertTrue(scene.death.prompt_visible)
        scene.dev_key_press(self.event("a"))
        self.assertIs(scene.checkpoint, snapshot)
        self.assertEqual((scene.room_id, scene.player_x, scene.action), (14, 277, 15))

    def test_prompt_is_centered_in_the_native_bottom_strip(self):
        scene = self.scene
        self.checkpoint()
        self.die()
        self.eligible()
        scene.render()
        before = scene.native_viewport.copy()
        scene.death.prompt_visible = True
        scene.render()
        difference = ImageChops.difference(before.convert("RGB"),
                                           scene.native_viewport.convert("RGB"))
        box = difference.getbbox()
        self.assertIsNotNone(box)
        self.assertLessEqual(abs((box[0] + box[2]) / 2 - 256), 1)
        self.assertLessEqual(abs((box[1] + box[3]) / 2 - (ROOM_HEIGHT + 384) / 2), 1)
        expected = Image.new("RGBA", (512, 384))
        text = scene.restart_text
        ink = text.getbbox()
        y = ROOM_HEIGHT + (19 - (ink[3] - ink[1])) // 2 - ink[1]
        expected.paste(text, ((512 - text.width) // 2, y), text)
        self.assertEqual(box, expected.getbbox())
        colors = {color for _count, color in text.getcolors()}
        self.assertEqual(colors - {(0, 0, 0, 0)}, {(253, 255, 168, 255)})

    def test_pause_freezes_the_death_clock_and_resume_does_not_also_retry(self):
        scene = self.scene
        self.checkpoint()
        self.die()
        self.eligible()
        scene.set_paused(True)
        before = scene.audio.playback.remaining.copy()
        self.tick(30)
        self.assertEqual(scene.audio.playback.remaining, before)
        scene.dev_key_press(self.event("space"))
        self.assertFalse(scene.paused)
        self.tick()
        self.assertFalse(scene.combat.player.alive)
        scene.dev_key_release(self.event("space"))
        scene.dev_key_press(self.event("space"))
        self.assertTrue(scene.combat.player.alive)

    def test_fullscreen_and_dev_keys_do_not_consume_death_as_retry(self):
        scene = self.scene
        self.checkpoint()
        self.die()
        self.eligible()
        for key, modifier in (("F2", 0), ("F5", 0),
                              ("Alt_L", 0), ("Return", 0x8), ("Return", 0x20000)):
            self.assertIsNone(scene.dev_key_press(self.event(key, modifier)))
            self.assertFalse(scene.combat.player.alive)
            scene.dev_key_release(self.event(key))

    def test_escape_also_retries_when_dead_instead_of_pausing(self):
        scene = self.scene
        self.checkpoint()
        self.die()
        self.eligible()
        self.assertEqual(scene.dev_key_press(self.event("Escape")), "break")
        self.assertTrue(scene.combat.player.alive)
        self.assertFalse(scene.paused)

    def test_held_modifier_can_retry_but_held_direction_alone_cannot(self):
        scene = self.scene
        self.checkpoint()
        self.die()
        scene.dev_key_press(self.event("Left"))
        self.tick(20)
        self.assertFalse(scene.combat.player.alive)
        scene.dev_key_press(self.event("Control_L"))
        self.assertTrue(scene.combat.player.alive)
        self.assertFalse(scene.ctrl_held)

    def test_combat_death_completes_its_sequence_before_retry(self):
        scene = self.scene
        scene.jump_to_screen("1")
        scene.peaceful = True
        scene.combat.player.life = 1
        scene.combat.player.sword_drawn = scene.sword_drawn = True
        guard = scene.combat.guard
        event = scene.combat._hurt("player", scene.combat.player, guard)
        scene.peaceful = False
        with patch.object(scene.combat, "step", return_value=[event]):
            scene.advance_combat()
        scene.peaceful = True
        self.assertEqual(scene.death.method, 14)
        self.assertFalse(scene.death.can_restart)
        self.assertFalse(scene.restart_after_death())
        self.eligible()
        self.assertIn(scene.action, (185, 242, 243, 271, 266))
        scene.dev_key_press(self.event("space"))
        self.assertTrue(scene.opening.active)
        self.assertTrue(scene.combat.player.alive)
        self.assertFalse(scene.sword_drawn)

    def test_fatal_landing_uses_fall_death_bookkeeping(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(1, row=1, x=180, facing=0)
        scene.physics.select(scene.sequence_runtime, 23)
        scene.sequence_state.current_y = -1
        scene.sequence_state.vertical_velocity = 63
        scene.terrain_motion.falling = True
        for _ in range(15):
            self.tick()
            if not scene.combat.player.alive:
                break
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(scene.death.method, 3)
        self.eligible()
        self.assertTrue(scene.restart_after_death())
        self.assertTrue(scene.opening.active)

    def test_fatal_jump_death_uses_guard_cue_and_unarmed_frame_gate(self):
        scene = self.scene
        scene.jump_to_room(3, row=1, x=411, facing=1)
        scene.combat.player.life = 1
        scene.sword_drawn = scene.combat.player.sword_drawn = False
        scene.sequence_state.sequence_id = 16
        with patch.object(scene.combat, "step", side_effect=lambda *args: [
                scene.combat._hurt("player", scene.combat.player, scene.combat.guard)]):
            scene.advance_combat()
        scene.peaceful = True
        start = self.now
        for _ in range(76):
            self.assertFalse(scene.death.prompt_visible)
            self.tick()
        self.assertTrue(scene.death.prompt_visible)
        self.assertAlmostEqual(self.now - start, 76 / 12)
        self.assertEqual(scene.death.method, 14)
        self.assertFalse(scene.sword_drawn)

    def test_player_corpse_alignment_and_roof_visibility_use_native_rules(self):
        scene = self.scene
        scene.jump_to_room(3, row=1, x=411, facing=1)
        scene.peaceful = True
        scene.combat.player.life = 1
        event = scene.combat._hurt("player", scene.combat.player, scene.combat.guard)
        self.assertEqual(scene.sequence_state.target_x, 404)
        scene.peaceful = False
        with patch.object(scene.combat, "step", return_value=[event]):
            scene.advance_combat()
        scene.peaceful = True
        self.tick(15)
        self.assertEqual(scene.action, 185)
        scene.render()
        with_body = scene.native_viewport.copy()
        with patch.object(scene, "composite_actor", side_effect=lambda frame, *args: frame):
            scene.render()
        self.assertEqual(with_body.tobytes(), scene.native_viewport.tobytes())

    def test_armed_guard_death_retains_six_tick_cadence(self):
        scene = self.scene
        scene.jump_to_room(3, row=1, x=411, facing=1)
        scene.combat.player.life = 1
        scene.sword_drawn = scene.combat.player.sword_drawn = True
        with patch.object(scene.combat, "step", side_effect=lambda *args: [
                scene.combat._hurt("player", scene.combat.player, scene.combat.guard)]):
            scene.advance_combat()
        scene.peaceful = True
        start = self.now
        for _ in range(66):
            self.assertAlmostEqual(scene.current_animation_interval_ms(), 100)
            self.assertFalse(scene.death.prompt_visible)
            self.tick()
        self.assertTrue(scene.death.prompt_visible)
        self.assertAlmostEqual(self.now - start, 6.6)

    def test_normal_fatal_hit_arms_player_and_uses_original_combat_cadence(self):
        scene = self.scene
        scene.jump_to_room(3, row=1, x=411, facing=1)
        scene.combat.player.life = 1
        scene.sword_drawn = scene.combat.player.sword_drawn = False
        with patch.object(scene.combat, "step", side_effect=lambda *args: [
                scene.combat._hurt("player", scene.combat.player, scene.combat.guard)]):
            scene.advance_combat()
        self.assertTrue(scene.sword_drawn)
        scene.peaceful = True
        start = self.now
        for _ in range(66):
            self.assertFalse(scene.death.prompt_visible)
            self.tick()
        self.assertTrue(scene.death.prompt_visible)
        # Fatal wound flash at 4.266667, prompt at 10.883333 in the reference.
        self.assertLessEqual(abs(self.now - start - 6.616666), 1 / 60)

    def test_fresh_restart_and_dev_warp_discard_checkpoint_and_death_state(self):
        scene = self.scene
        for reset in (scene.restart_opening, lambda: scene.jump_to_screen("3")):
            self.checkpoint()
            self.die()
            reset()
            self.assertIsNone(scene.checkpoint)
            self.assertEqual(scene.death.counter, -1)
            self.assertTrue(scene.combat.player.alive)
