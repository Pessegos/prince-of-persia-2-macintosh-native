from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np
from PIL import Image

from pop2.attract import CreditsPlayer, DemoEncounter, DemoPlayer, actor_state, read_attract
from pop2.intro import MAC_TICKS_PER_SECOND
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceRuntime, SequenceState


def fixture():
    actor = [0] * 31
    actor[0], actor[2], actor[3], actor[5] = 10, 556, 226, 15
    actor[7], actor[11], actor[15], actor[16] = 1, 4, 3, 3
    return {"schema": 1, "recording": 250,
            "frames": [{"ticks": 5, "room": 4, "actors": [[0] * 31 for _ in range(5)] + [actor],
                        "sounds": []}],
            "credits": {"pages": [[["Credits", 10, 10]]] * 4, "hold_ticks": 465,
                        "dissolve_ticks": 90, "fade_ticks": 25, "song": 10019}}


class AttractDataTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "attract.json")
            path.write_text(json.dumps(data), encoding="ascii")
            return read_attract(path)

    def test_valid_trace_is_loaded(self):
        self.assertEqual(self.read(fixture()), fixture())

    def test_bad_actor_or_clock_is_rejected(self):
        for key, value in (("ticks", 0), ("room", 33), ("actors", []),
                           ("sounds", [["bad", 1, 0]])):
            data = fixture()
            data["frames"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.read(data)

    def test_bad_credits_are_rejected(self):
        for key, value in (("pages", []), ("hold_ticks", 0), ("song", "10019")):
            data = fixture()
            data["credits"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.read(data)

    def test_actor_projection_uses_native_coordinates_and_facing(self):
        words = fixture()["frames"][0]["actors"][5]
        words[1], words[18] = -1, 14
        state = actor_state(words, 0)
        self.assertEqual((state.target_x, state.current_y, state.facing, state.cursor), (349, 0, 0, 7))

    def test_read_only_encounter_projects_neighbor_without_mutating_actor(self):
        data = fixture()["frames"][0]
        guard = data["actors"][0]
        guard[:] = data["actors"][5]
        guard[0], guard[2], guard[11] = 0, 707, 2
        level = SimpleNamespace(start_room=3, neighbor=lambda room, direction: 1 if direction == "left" else None)
        encounter = DemoEncounter(level, SequenceRuntime({}, SequenceState(2)))
        encounter.apply(data, 10)
        self.assertEqual(encounter.visible_guards()[0].state.target_x, -10)
        self.assertEqual(encounter.guards[0].state.target_x, 500)
        self.assertEqual(guard[2], 707)

    def test_selected_opponent_is_not_replaced_by_nearer_corpse(self):
        frame = fixture()["frames"][0]
        player = frame["actors"][5]
        player[29] = 1
        for slot, x, life in ((0, 550, 0), (1, 400, 1)):
            frame["actors"][slot] = player.copy()
            frame["actors"][slot][0] = slot
            frame["actors"][slot][2] = x
            frame["actors"][slot][15] = life
        level = SimpleNamespace(start_room=3, neighbor=lambda *_: None)
        encounter = DemoEncounter(level, SequenceRuntime({}, SequenceState(2)))
        encounter.apply(frame, 0)
        self.assertEqual(encounter.guard.state.target_x, 193)
        self.assertTrue(encounter.guard.alive)


class DemoClockTests(unittest.TestCase):
    def test_clock_and_audio_are_independent_of_host_frame_step(self):
        data = fixture()
        data["frames"] = [deepcopy(data["frames"][0]) for _ in range(3)]
        data["frames"][1]["ticks"] = 6
        data["frames"][1]["sounds"] = [["sound", 7, 0], ["song", 38, 0]]
        audio = Mock()
        direct = DemoPlayer(data, audio)
        incremental = DemoPlayer(data)
        direct.advance(10 / MAC_TICKS_PER_SECOND)
        for _ in range(10):
            incremental.advance(1 / MAC_TICKS_PER_SECOND)
        self.assertEqual(direct.index, incremental.index)
        self.assertEqual(direct.index, 1)
        audio.add_sound.assert_called_once_with(7, 0)
        audio.add_song.assert_called_once_with(38)
        self.assertEqual(audio.ambient.call_count, 2)
        direct.advance(6 / MAC_TICKS_PER_SECOND)
        self.assertTrue(direct.done)

    def test_negative_time_does_not_rewind(self):
        demo = DemoPlayer(fixture())
        demo.advance(-100)
        self.assertEqual((demo.index, demo.time), (0, 0))


class CreditsClockTests(unittest.TestCase):
    def assets(self):
        return SimpleNamespace(program=fixture()["credits"], palette=[(i, i, i) for i in range(256)],
                               pages=[Image.new("L", (512, 384), value) for value in (25, 50, 75, 100)])

    def test_first_page_fades_in_and_holds_for_original_interval(self):
        player = CreditsPlayer(self.assets())
        player.advance(25 / MAC_TICKS_PER_SECOND)
        self.assertEqual(player.frame().getpixel((30, 30)), (25, 25, 25, 255))
        player.advance(464 / MAC_TICKS_PER_SECOND)
        self.assertEqual(player.display.getpixel((30, 30)), 25)
        self.assertFalse(player.done)

    def test_only_inner_rectangle_dissolves_and_loop_reaches_black(self):
        player = CreditsPlayer(self.assets())
        player.advance((25 + 465 + 45) / MAC_TICKS_PER_SECOND)
        values = set(np.asarray(player.display.crop((14, 14, 494, 370))).reshape(-1))
        self.assertEqual(values, {25, 50})
        self.assertEqual(player.display.getpixel((0, 0)), 25)
        player.advance(100)
        self.assertTrue(player.done)
        self.assertEqual(player.frame().getpixel((30, 30)), (0, 0, 0, 255))

    def test_direct_and_incremental_credits_frames_match(self):
        direct, incremental = CreditsPlayer(self.assets()), CreditsPlayer(self.assets())
        direct.advance(9)
        for _ in range(90):
            incremental.advance(.1)
        self.assertEqual(direct.frame().tobytes(), incremental.frame().tobytes())

    def test_credits_play_the_original_music(self):
        audio = Mock()
        CreditsPlayer(self.assets(), audio)
        audio.reset.assert_called_once()
        audio.play_intro.assert_called_once_with(10019, 0)


@unittest.skipUnless((ASSET_DIR / "attract.json").is_file(), "Imported demo resources required")
class ImportedDemoTests(unittest.TestCase):
    def test_recording_reaches_screen_five_and_dies(self):
        data = read_attract(ASSET_DIR / "attract.json")
        self.assertEqual(len(data["frames"]), 522)
        self.assertEqual({frame["room"] for frame in data["frames"]}, {4, 2, 3, 1, 10})
        self.assertEqual(data["frames"][-1]["actors"][5][15], 0)
        self.assertEqual(data["frames"][-1]["room"], 10)
        self.assertEqual(data["recordings"], {"250": {"level": 1, "last_frame": 521},
                                            "251": {"level": 4, "last_frame": 608},
                                            "252": {"level": 8, "last_frame": 506}})

    def test_every_recorded_cue_and_credits_song_is_prepared(self):
        data = read_attract(ASSET_DIR / "attract.json")
        manifest = json.loads((ASSET_DIR / "audio/manifest.json").read_text())
        cues = {event[1] for frame in data["frames"] for event in frame["sounds"]}
        cues.add(data["credits"]["song"])
        for cue in cues:
            self.assertTrue((ASSET_DIR / "audio" / manifest["cues"][str(cue)]["file"]).is_file())
