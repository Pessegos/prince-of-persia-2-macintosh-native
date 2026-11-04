import json
import os
import unittest
from unittest.mock import patch
import wave

import numpy as np

from pop2.audio import AudioEngine, MixerPlayback, scene_sound_key
from pop2.music_transition import fade_pcm, horse_music_ending
from pop2.paths import ASSET_DIR
from tests.test_audio import TimedPlayback


class MusicEnvelopeTests(unittest.TestCase):
    def test_fades_keep_unaffected_pcm_and_channel_balance(self):
        samples = np.tile(np.array([10000, -10000], dtype='<i2'), (4000, 1))
        raw = samples.tobytes()
        faded = np.frombuffer(fade_pcm(raw, 1000, 2, into=1, out=1.25), dtype='<i2').reshape(-1, 2)
        self.assertEqual(len(faded), len(samples))
        np.testing.assert_array_equal(faded[1000:2750], samples[1000:2750])
        np.testing.assert_array_equal(faded[0], [0, 0])
        np.testing.assert_array_equal(faded[-1], [0, 0])
        np.testing.assert_array_equal(faded[:, 0], -faded[:, 1])
        self.assertLess(np.abs(np.diff(faded[:1000, 0].astype('i4'))).max(), 20)
        self.assertEqual(raw, samples.tobytes())

    def test_horse_ending_removes_padding_and_fades_only_the_last_phrase(self):
        samples = np.concatenate((np.full((3000, 2), 10000, dtype='<i2'),
                                  np.zeros((5000, 2), dtype='<i2')))
        ending = np.frombuffer(horse_music_ending(samples.tobytes(), 1000, 2), dtype='<i2').reshape(-1, 2)
        self.assertEqual(len(ending), 3100)
        np.testing.assert_array_equal(ending[:1850], samples[:1850])
        self.assertGreater(ending[2000, 0], ending[2500, 0])
        self.assertGreater(ending[2500, 0], ending[2999, 0])
        self.assertFalse(ending[-100:].any())
        silent = bytes(800)
        self.assertEqual(horse_music_ending(silent, 1000, 2), silent)


class RecordingPlayback(TimedPlayback):
    def __init__(self, cues):
        super().__init__(cues)
        self.plays = []

    def play(self, bus, cue, *, fade_in=0):
        super().play(bus, cue)
        self.plays.append((bus, cue, fade_in))


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'temple.json', 'Temple.rsrc', 'audio/scene-0-25006.wav', 'audio/manifest.json'))


@unittest.skipUnless(INSTALLED, 'Imported horse and temple music required')
class HorseMusicHandoffTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        manifest = json.loads((ASSET_DIR / 'audio/manifest.json').read_text())
        cues = {int(key): dict(value) for key, value in manifest['cues'].items()}
        cues.update({key: dict(value) for key, value in manifest['scene_cues'].items()})
        with wave.open(str(ASSET_DIR / 'audio/scene-0-25006.wav'), 'rb') as stream:
            raw = stream.readframes(stream.getnframes())
            rate, channels = stream.getframerate(), stream.getnchannels()
        # Supply the actual mixer's transformed duration to the deterministic
        # clock; the SDL test below independently checks that PCM transform.
        cues[scene_sound_key(25006, 0)]['duration'] = len(horse_music_ending(raw, rate, channels)) / (2 * channels * rate)
        self.playback = RecordingPlayback(cues)
        self.scene.audio = self.audio = AudioEngine(playback=self.playback)
        self.scene.load_level(9)

    def ride(self, until=None):
        from pop2.environments import Ruins

        Ruins(self.scene).finish_exit()
        player = self.scene.intro
        while not player.done and (until is None or player.time < until):
            delta = max(0, player.wait_until - player.time)
            self.playback.advance(delta)
            player.advance(delta)
        return player

    def test_natural_finish_carries_the_ending_then_fades_in_ambience_once(self):
        self.ride()
        music_plays = [play for play in self.playback.plays if play[0] == 'music']
        self.scene.finish_tree()
        self.assertEqual((self.scene.game.level.number, self.scene.room_id), (10, 21))
        self.assertEqual(self.audio.current_music, 25006)
        remaining = self.playback.remaining['music']
        self.assertGreater(remaining, 8)
        self.assertLess(remaining, 10)
        self.scene.advance_audio()
        self.assertEqual([p for p in self.playback.plays if p[0] == 'music'], music_plays)
        self.audio.pause(True)
        self.playback.advance(20)
        self.assertEqual(self.playback.remaining['music'], remaining)
        self.audio.pause(False)
        self.playback.advance(remaining - .01)
        self.scene.advance_audio()
        self.assertEqual(self.audio.current_music, 25006)
        self.playback.advance(.01)
        self.scene.advance_audio()
        self.assertIn(self.audio.current_music, range(200, 232))
        self.assertEqual(self.playback.plays[-1], ('music', self.audio.current_music, 1.0))
        self.playback.advance(60)
        self.scene.advance_audio()
        self.assertEqual(self.playback.plays[-1][2], 0)

    def test_skip_does_not_carry_or_delay_the_temple_music(self):
        self.ride(until=17)
        self.scene.finish_tree(skipped=True)
        self.assertIsNone(self.audio.current_music)
        self.assertFalse(self.audio.music_fade_in_pending)
        self.scene.advance_audio()
        self.assertIn(self.audio.current_music, range(200, 232))
        self.assertEqual(self.playback.plays[-1][2], 0)

    def test_restart_cancels_the_retained_theme_and_its_pending_fade(self):
        self.ride()
        self.scene.finish_tree()
        self.scene.load_level(10)
        self.assertIsNone(self.audio.current_music)
        self.assertFalse(self.audio.music_fade_in_pending)
        self.scene.advance_audio()
        self.assertEqual(self.playback.plays[-1][2], 0)

    def test_a_foreground_song_can_interrupt_the_retained_theme(self):
        self.ride()
        self.scene.finish_tree()
        self.audio.add_song(253)
        self.audio.flush()
        self.assertEqual(self.audio.current_music, 253)
        self.assertEqual(self.playback.plays[-1], ('music', 253, 0))
        self.assertFalse(self.audio.music_fade_in_pending)


@unittest.skipUnless(INSTALLED, 'Imported horse and temple music required')
class MixerMusicEnvelopeTests(unittest.TestCase):
    def test_sdl_uses_the_trimmed_ending_and_pcm_fade_without_changing_bus_volume(self):
        key = scene_sound_key(25006, 0)
        with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
            playback = MixerPlayback(ASSET_DIR / 'audio', {
                key: {'file': 'scene-0-25006.wav'}, 200: {'file': 'cue-200.wav'}})
            try:
                rate, _bits, channels = playback.mixer.get_init()
                original = playback.mixer.Sound(str(ASSET_DIR / 'audio/scene-0-25006.wav')).get_raw()
                self.assertEqual(playback.sounds[key].get_raw(), horse_music_ending(original, rate, channels))
                self.assertGreater(playback.sounds[key].get_length(), 26)
                self.assertLess(playback.sounds[key].get_length(), 27)
                playback.set_volume('music', .5)
                playback.play('music', 200, fade_in=1)
                played = playback.channels['music'].get_sound()
                self.assertEqual(played.get_raw(), fade_pcm(playback.sounds[200].get_raw(), rate, channels, into=1))
                self.assertEqual(playback.channels['music'].get_volume(), .5)
            finally:
                playback.close()
