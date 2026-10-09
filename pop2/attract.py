"""Playback of imported demo states and the original credits pages."""

from dataclasses import dataclass, replace
import json
from pathlib import Path

import numpy as np
from PIL import Image

from pop2.game_ui import MacintoshFont
from pop2.intro import MAC_TICKS_PER_SECOND, SIZE, dissolve_words, indexed_shape, palette_colors
from pop2.mac_resources import parse_resource_fork
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import floor_y, ROOM_WIDTH


def read_attract(path):
    data = json.loads(Path(path).read_text(encoding="ascii"))
    if not isinstance(data, dict) or data.get("schema") != 1 or data.get("recording") != 250:
        raise ValueError("Demo data needs to be imported again")
    frames = data.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 5001:
        raise ValueError("Invalid recorded demo length")
    for frame in frames:
        if (not isinstance(frame, dict) or frame.get("ticks") not in (5, 6)
                or type(frame.get("room")) is not int or not 1 <= frame["room"] <= 32
                or not isinstance(frame.get("actors"), list) or len(frame["actors"]) != 6
                or any(not isinstance(actor, list) or len(actor) != 31
                       or any(type(word) is not int or not -32768 <= word <= 32767 for word in actor)
                       for actor in frame["actors"])
                or not isinstance(frame.get("sounds"), list)
                or any(not isinstance(event, list) or len(event) != 3
                       or event[0] not in ("sound", "song")
                       or any(type(value) is not int for value in event[1:]) for event in frame["sounds"])):
            raise ValueError("Invalid recorded demo frame")
    credits = data.get("credits", {})
    if (not isinstance(credits, dict) or not isinstance(credits.get("pages"), list)
            or len(credits["pages"]) != 4
            or any(type(credits.get(key)) is not int or not 0 < credits[key] <= 1000
                   for key in ("hold_ticks", "dissolve_ticks", "fade_ticks"))
            or type(credits.get("song")) is not int):
        raise ValueError("Invalid credits program")
    for page in credits["pages"]:
        if (not isinstance(page, list) or not 1 <= len(page) <= 100
                or any(not isinstance(line, list) or len(line) != 3
                       or not isinstance(line[0], str) or len(line[0]) > 2048
                       or any(type(value) is not int for value in line[1:]) for line in page)):
            raise ValueError("Invalid credits text")
    return data


def actor_state(words, actor_type):
    x, row = words[2] - 207, words[7]
    return SequenceState(words[19], cursor=words[18] // 2, action=words[5],
                         current_x=x, target_x=x, current_y=words[3] - floor_y(row),
                         facing=int(words[1] == 0), animation_state=words[8],
                         actor_type=actor_type, level_kind=5, callback_flag=words[12],
                         horizontal_velocity=words[9], vertical_velocity=words[4],
                         special_flag=words[26], engine_counter=words[27])


@dataclass
class DemoFighter:
    state: SequenceState
    life: int
    max_life: int
    room: int
    row: int
    sword_drawn: bool = False
    palette_variant: int = 1

    @property
    def alive(self):
        return self.life > 0


class DemoEncounter:
    """Render-only combat view; never runs or mutates the live encounter's AI."""

    def __init__(self, level_map, player_runtime):
        self.level_map, self.player_runtime = level_map, player_runtime
        self.player = DemoFighter(player_runtime.state, 3, 3, level_map.start_room, 1)
        self.guard, self.guards, self.world_frame = None, [], 0
        self.last_guard_at = None

    def apply(self, frame, index):
        words = frame["actors"][5]
        self.player_runtime.state.__dict__.update(actor_state(words, 0).__dict__)
        self.player = DemoFighter(self.player_runtime.state, words[15], words[16], words[11] - 1,
                                  words[7], sword_drawn=words[13] == 1)
        self.world_frame, self.guards, self.guard = index, [], None
        selected = words[29]
        for slot, words in enumerate(frame["actors"][:5]):
            if words[1] not in (0, -1) or words[11] <= 0:
                continue
            fighter = DemoFighter(actor_state(words, 2), words[15], words[16],
                                  words[11] - 1, words[7], sword_drawn=words[13] == 1)
            self.guards.append(fighter)
            if slot == selected:
                self.guard = self.project_guard(fighter)

    def project_guard(self, guard):
        room = self.player.room
        if guard.room == room:
            return guard
        for direction, offset in (("left", -ROOM_WIDTH), ("right", ROOM_WIDTH)):
            if guard.room == self.level_map.neighbor(room, direction):
                state = replace(guard.state, current_x=guard.state.current_x + offset,
                                target_x=guard.state.target_x + offset)
                return replace(guard, room=room, state=state)
        return None

    def visible_guards(self):
        return [view for guard in self.guards if (view := self.project_guard(guard)) is not None]


class DemoPlayer:
    def __init__(self, data, audio=None):
        self.frames, self.audio = data["frames"], audio
        self.index, self.time, self.deadline = -1, 0.0, 0.0
        self.done = False
        self.advance(0)

    @property
    def frame(self):
        return self.frames[self.index]

    def advance(self, seconds):
        self.time += max(0, seconds)
        while not self.done and self.deadline <= self.time + 1e-9:
            if self.index + 1 == len(self.frames):
                self.done = True
                break
            self.index += 1
            frame = self.frame
            self.deadline += frame["ticks"] / MAC_TICKS_PER_SECOND
            if self.audio is not None:
                for kind, cue, actor in frame["sounds"]:
                    if kind == "sound":
                        self.audio.add_sound(cue, actor)
                    else:
                        self.audio.add_song(cue)
                player = frame["actors"][5]
                self.audio.ambient(frame["room"] - 1, player[7], max(0, min(9, player[6])),
                                   player[13] == 1, player[15] > 0)
                self.audio.flush()

    def next_update_delay(self):
        return max(0, self.deadline - self.time)


class CreditsAssets:
    def __init__(self, data, directory=ASSET_DIR):
        self.program = data["credits"]
        prince = parse_resource_fork(Path(directory, "Prince.rsrc").read_bytes())
        self.font = MacintoshFont(prince["NFNT"][24878]["data"])
        colors = palette_colors(prince["CTBL"][8000]["data"])
        self.palette = [colors.get(index, (0, 0, 0)) for index in range(256)]
        self.palette[1] = (0, 0, 0)
        border = Image.new("L", SIZE, 25)
        horizontal = indexed_shape(prince["SHAP"][8001]["data"])
        # This resource retains unrelated bytes after its final compressed row.
        vertical = indexed_shape(prince["SHAP"][8000]["data"], allow_trailing=True)
        border.paste(horizontal, (vertical.width, 0))
        border.paste(horizontal.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
                     (vertical.width, SIZE[1] - horizontal.height))
        border.paste(vertical, (0, 0))
        border.paste(vertical.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (510 - vertical.width, 0))
        self.pages = []
        for lines in self.program["pages"]:
            page = border.copy()
            for text, x, y in lines:
                mask = self.font.text(text).getchannel("A")
                for dx, ink in ((8, 1), (6, 16), (5, 27)):
                    page.paste(ink, (x + dx, y), mask)
            self.pages.append(page)


class CreditsPlayer:
    def __init__(self, assets, audio=None):
        self.assets = assets
        self.time, self.revision, self.done = 0.0, 0, False
        self.display = Image.new("L", SIZE, 1)
        self.brightness = 0.0
        self.words = dissolve_words({"rect": [14, 14, 370, 494],
                                     "order": self._dissolve_order()})
        self._signature = None
        if audio is not None:
            audio.reset()
            audio.play_intro(assets.program["song"], 0)
        self.advance(0)

    @staticmethod
    def _dissolve_order():
        import random

        order = list(range(120 * 356))
        random.Random(0).shuffle(order)
        return order

    def advance(self, seconds):
        self.time += max(0, seconds)
        ticks = self.time * MAC_TICKS_PER_SECOND
        fade, hold, dissolve = (self.assets.program[key] for key in
                                ("fade_ticks", "hold_ticks", "dissolve_ticks"))
        self.brightness = min(1, ticks / fade)
        page, progress = 0, 1.0
        position = ticks - fade - hold
        while page < 3 and position >= 0:
            page += 1
            progress = min(1, position / dissolve)
            if position < dissolve + hold:
                break
            position -= dissolve + hold
        end = fade + hold * 4 + dissolve * 3
        if ticks >= end:
            self.brightness = max(0, 1 - (ticks - end) / fade)
            self.done = ticks >= end + fade
        signature = (page, int(progress * len(self.words)), int(self.brightness * 255))
        if signature != self._signature:
            self._signature = signature
            self.revision += 1
            self.display = self.assets.pages[page].copy()
            if page and progress < 1:
                self.display = self.assets.pages[page - 1].copy()
                destination = np.asarray(self.assets.pages[page]).reshape(-1)
                pixels = np.array(self.display).reshape(-1)
                indices = self.words[:signature[1]].reshape(-1)
                pixels[indices] = destination[indices]
                self.display = Image.fromarray(pixels.reshape(SIZE[1], SIZE[0]))

    def frame(self):
        colors = [round(channel * self.brightness) for color in self.assets.palette for channel in color]
        image = self.display.convert("P")
        image.putpalette(colors)
        return image.convert("RGBA")

    def next_update_delay(self):
        return 1 / MAC_TICKS_PER_SECOND
