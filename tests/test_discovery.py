import io
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import mido
from PIL import Image, ImageChops

from pop2.audio import AudioEngine, scene_sound_key
from pop2.audio_formats import Sample
from pop2.intro import IntroAssets, IntroPlayer
from pop2.paths import ASSET_DIR
from pop2.playback_navigation import discovery_parts, playback_groups
from tests.test_intro import instruction, script
from tools import extract_intro as extractor


class DiscoveryFormatTests(unittest.TestCase):
    def test_animation_uses_absolute_origin_layer_order_native_interval_and_sound_bank(self):
        animation = script(
            instruction(4, 6), instruction(5, 1, 1), instruction(6, 1, -2, 3),
            instruction(7, 1, 16), instruction(3, 29100), instruction(1),
            instruction(5, 1, 0), instruction(5, 2, 2), instruction(6, 2, 5, 7),
            instruction(7, 2, 0), instruction(1), instruction(0))
        resources = {'ANI ': {29001: {'data': struct.pack('>9h', 80, 86, 312, 472, 2,
                                                        29001, 29001, 29001, 29001)}},
                     'SCRP': {29001: {'data': animation}},
                     'SHAP': {number: {'data': struct.pack('>HhhH', 0, 2, 2, 1)}
                              for number in (29001, 29002)}}
        with patch.object(extractor, 'parse_resource_fork', return_value=resources):
            result = extractor.expand_animations([
                {'op': 'animation', 'args': [29000, 1, 63, 61], 'pc': 0x237c}], b'nis')
        self.assertEqual([(op['op'], op['args']) for op in result], [
            ('sound', [29100, 1]), ('shape', [29001, 61, 64, 16]),
            ('copy', [[64, 61, 65, 63]]), ('wait', [6]),
            ('shape', [29002, 68, 68, 0]), ('copy', [[68, 68, 69, 70]]), ('wait', [6])])
        self.assertEqual({op['pc'] for op in result}, {0x237c})

    def test_banked_import_preserves_same_resource_number_in_music_and_pcm(self):
        midi = mido.MidiFile()
        midi.tracks.append(mido.MidiTrack([mido.MetaMessage('cue_marker', text='a', time=480),
                                          mido.MetaMessage('end_of_track', time=480)]))
        stream = io.BytesIO()
        midi.save(file=stream)
        banks = {b'NISMIDI.dat': {'MIDI': {29100: stream.getvalue()}},
                 b'NISDIGI.dat': {'snd ': {29100: b'pcm'}}, b'DigiSnd.dat': {'snd ': {}}}
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'audio').mkdir()
            (directory / 'audio/manifest.json').write_text(json.dumps(
                {'schema': 1, 'cues': {'29100': {'file': 'legacy.wav'}}}))

            def render(_directory, _name, output):
                output.write_bytes(Sample(bytes(8), 8, 1, 2).wav())
                return 0.5

            with (patch.object(extractor, 'get_data_fork', side_effect=lambda _, n: n.encode()),
                  patch.object(extractor, 'mohawk_resources', side_effect=banks.__getitem__),
                  patch.object(extractor, 'digitized_sound', return_value=Sample(bytes(8), 8)),
                  patch.object(extractor, 'render_midi', side_effect=render)):
                sounds = extractor.extract_scene_audio(b'image', [
                    {'op': 'sound', 'args': [29100, kind]} for kind in (0, 1)], directory, banked=True)
            manifest = json.loads((directory / 'audio/manifest.json').read_text())
            self.assertEqual(manifest['cues']['29100'], {'file': 'legacy.wav'})
            keys = {scene_sound_key(29100, kind) for kind in (0, 1)}
            self.assertEqual(set(sounds), keys)
            self.assertEqual(set(manifest['scene_cues']), keys)
            self.assertNotEqual(sounds[scene_sound_key(29100, 0)]['duration'],
                                sounds[scene_sound_key(29100, 1)]['duration'])
            playback = Mock()
            audio = AudioEngine(directory / 'audio', playback=playback)
            for kind, bus in ((0, 'music'), (1, 'effect')):
                audio.play_intro(29100, kind, offset=0.1)
                playback.play.assert_called_with(bus, scene_sound_key(29100, kind), offset=0.1)
                self.assertTrue((directory / 'audio' / manifest['scene_cues'][
                    scene_sound_key(29100, kind)]['file']).is_file())
            assets = SimpleNamespace(program={'operations': [{'op': 'wait', 'args': [1]}],
                                             'audio': sounds})
            player = IntroPlayer(assets)
            player.sound(29100, 0)
            player.sound(29100, 1)
            self.assertNotEqual(player.sound_end(0), player.sound_end(1))

    def test_developer_parts_are_grouped_after_level_three_with_level_four_destination(self):
        parts = discovery_parts({'operations': [{'op': 'palette', 'args': [identifier]}
                                               for identifier in (29022, 29002, 29006, 29002, 29009)]})
        self.assertEqual([p.label for p in parts],
                         ['Meanwhile', 'The Letter', 'The Impostor', 'The Spell', 'Caverns'])
        self.assertEqual((parts[-1].stage, parts[-1].index), ('level', 4))
        self.assertEqual(len(playback_groups(parts)), 1)
        self.assertEqual(playback_groups(parts)[0].label, 'After Level 3')


@unittest.skipUnless((ASSET_DIR / 'discovery.json').is_file(), 'Imported discovery resources required')
class ImportedDiscoveryTests(unittest.TestCase):
    def test_original_program_contains_all_three_animations_and_both_sound_banks(self):
        assets = IntroAssets(program_name='discovery.json')
        operations = assets.program['operations']
        for pc in (0x237c, 0x23f6, 0x2456):
            frames = [op for op in operations if op.get('pc') == pc and op['op'] == 'wait']
            self.assertEqual(len(frames), {0x237c: 2, 0x23f6: 5, 0x2456: 62}[pc])
            self.assertTrue(all(op['args'] == [6] for op in frames))
        self.assertIn(scene_sound_key(29100, 0), assets.program['audio'])
        self.assertIn(scene_sound_key(29100, 1), assets.program['audio'])
        fast, stepped = IntroPlayer(assets), IntroPlayer(assets)
        fast.advance(100)
        for _ in range(6000):
            stepped.advance(1 / 60)
            if stepped.done:
                break
        self.assertTrue(fast.done and stepped.done)
        self.assertAlmostEqual(fast.time, stepped.time, places=6)
        self.assertEqual(fast.frame().tobytes(), stepped.frame().tobytes())

    def test_native_mouse_animation_changes_pixels_without_destroying_its_background(self):
        player = IntroPlayer(IntroAssets(program_name='discovery.json'))
        player.advance(71)
        before = player.frame().copy()
        player.advance(1)
        after = player.frame()
        difference = ImageChops.difference(before.convert('RGB'), after.convert('RGB')).getbbox()
        self.assertIsNotNone(difference)
        self.assertGreaterEqual(difference[0], 306)
        self.assertLessEqual(difference[2], 425)
        self.assertEqual(before.crop((64, 62, 220, 250)).tobytes(),
                         after.crop((64, 62, 220, 250)).tobytes())
        self.assertGreater(len(after.getcolors(512 * 384)), 100)
        self.assertEqual(after.size, (512, 384))


@unittest.skipUnless((ASSET_DIR / 'discovery.json').is_file(), 'Imported discovery resources required')
class DiscoveryHostTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def test_level_three_completion_starts_discovery_once_then_enters_four_with_health(self):
        scene = self.scene
        scene.load_level(3)
        scene.combat.player.max_life = 5
        scene.sequence_state.sequence_events.append((-16, ()))
        scene.advance_level_events()
        self.assertTrue(scene.game.complete)
        self.assertEqual(scene.game.exit.song, 32)
        scene.advance_animation()
        self.assertIsNone(scene.intro)
        scene.game.exit.elapsed = scene.game.exit.duration
        scene.advance_animation()
        self.assertEqual(scene.attract_stage, 'discovery')
        player = scene.intro
        self.assertFalse(scene.game.complete)
        self.assertIsNone(scene.game.exit)
        scene.advance_level_events()
        self.assertIs(scene.intro, player)
        player.advance(100)
        scene.finish_attract_stage()
        self.assertEqual((scene.game.level.number, scene.room_id, scene.terrain_motion.row), (4, 0, 2))
        self.assertEqual((scene.combat.player.life, scene.combat.player.max_life), (5, 5))
        self.assertIsNone(scene.intro)
        self.assertIsNone(scene.attract_stage)
        self.assertIsNone(scene.demo)
        self.assertIsNone(scene.checkpoint)

    def test_exit_music_gate_waits_for_song_and_effect_before_discovery(self):
        scene = self.scene
        scene.load_level(3)
        scene.sequence_state.sequence_events.append((-16, ()))
        scene.audio = Mock()
        scene.audio.cues = {32: {'duration': 7}}
        scene.audio.available.return_value = True
        scene.audio.current_music = 32
        scene.audio.music_busy = True
        scene.audio.death_ready.return_value = True
        scene.advance_level_events()
        scene.audio.add_song.assert_called_once_with(32)
        scene.game.exit.elapsed = 8
        scene.advance_animation()
        self.assertIsNone(scene.intro)
        scene.audio.music_busy = False
        scene.audio.death_ready.return_value = False
        scene.advance_animation()
        self.assertIsNone(scene.intro)
        scene.audio.death_ready.return_value = True
        scene.advance_animation()
        self.assertEqual(scene.attract_stage, 'discovery')

    def test_pause_freezes_discovery_and_skip_does_not_leak_the_held_key_to_level_four(self):
        scene = self.scene
        scene.load_level(3)
        scene.start_discovery()
        clock = scene.intro.time
        scene.set_paused(True)
        scene.advance_animation()
        self.assertEqual(scene.intro.time, clock)
        scene.set_paused(False)
        scene.window_keys_down.add('space')
        scene.finish_intro()
        self.assertEqual(scene.game.level.number, 4)
        self.assertIn('space', scene.pause_resume_keys)
        self.assertIsNone(scene.intro)

    def test_developer_seek_preview_and_destination_remain_isolated(self):
        from pop2.playback_preview import PlaybackPreviews

        scene = self.scene
        scene.with_intro = True
        parts = scene.development_parts()
        indices = [i for i, part in enumerate(parts) if part.stage == 'discovery']
        scene.seek_playback_part(parts[indices[2]])
        player = scene.intro
        preview = PlaybackPreviews(scene.resources, parts, scene.attract_data, 'discovery-test')
        frame = preview.snapshot(indices[2])
        self.assertIs(scene.intro, player)
        self.assertIsInstance(frame, Image.Image)
        self.assertEqual(frame.size, (510, 384))
        self.assertGreater(len(frame.getcolors(510 * 384)), 100)
        destination = next(p for p in parts if p.stage == 'level' and p.index == 4)
        scene.seek_playback_part(destination)
        self.assertEqual(scene.game.level.number, 4)
        self.assertEqual(parts[scene.current_playback_part()], destination)


if __name__ == '__main__':
    unittest.main()
