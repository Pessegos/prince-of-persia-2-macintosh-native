"""Native playback of the Macintosh opening scene program."""

import json
from pathlib import Path
import random
import struct

import numpy as np
from PIL import Image

from pop2.game_ui import MacintoshFont
from pop2.mac_resources import parse_resource_fork
from pop2.paths import ASSET_DIR


SIZE = (512, 384)
STORY_RECT = (62, 64, 292, 448)
OPERATIONS = {
    "shape": 4, "fill": 2, "copy": 1, "clip": 1, "dissolve": 1,
    "text": 5, "sound": 2, "wait_sound": 2, "wait_current": 1,
    "timer": 2, "wait_timer": 1, "wait": 1, "cue": 1, "palette": 3,
    "brightness": 2, "fade": 3, "fade_both": 1, "flash": 5, "stop": 1,
    "title": 0,
}


def read_program(path):
    data = json.loads(Path(path).read_text(encoding="ascii"))
    if data.get("schema") != 1 or not isinstance(data.get("audio"), dict):
        raise ValueError("Intro data needs to be imported again")
    operations = data.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("Intro scene program is empty")
    for item in operations:
        if (not isinstance(item, dict) or item.get("op") not in OPERATIONS
                or not isinstance(item.get("args"), list)
                or len(item["args"]) != OPERATIONS[item["op"]]):
            raise ValueError("Invalid intro scene instruction")
    return data


def indexed_shape(data):
    flags, stride, width, height = struct.unpack_from(">HhhH", data)
    if not 0 < width <= 2048 or not 0 < height <= 2048:
        raise ValueError("Invalid intro SHAP dimensions")
    compression = flags >> 8 & 15
    body = data[12:]
    if compression == 1:
        cursor, pixels = 0, bytearray()
        for _ in range(height):
            size = struct.unpack_from(">H", body, cursor)[0]
            cursor += 2
            end, row = cursor + size, bytearray()
            while cursor < end:
                token = body[cursor]
                cursor += 1
                count = (token & 127) + 1
                if token & 128:
                    row.extend([body[cursor]] * count)
                    cursor += 1
                else:
                    row.extend(body[cursor:cursor + count])
                    cursor += count
            if cursor != end or len(row) != width:
                raise ValueError("Invalid intro SHAP row")
            pixels.extend(row)
        if len(body) - cursor not in (0, 2):
            raise ValueError("Trailing intro SHAP data")
    elif compression == 0 and stride >= width and len(body) == stride * height:
        pixels = b"".join(body[y * stride:y * stride + width] for y in range(height))
    else:
        raise ValueError("Unsupported intro SHAP encoding")
    return Image.frombytes("L", (width, height), bytes(pixels))


def palette_colors(data):
    count = struct.unpack_from(">H", data)[0]
    if len(data) != 2 + count * 4:
        raise ValueError("Invalid intro CTBL")
    return {data[i + 3]: tuple(data[i:i + 3]) for i in range(2, len(data), 4)}


def text_strings(data):
    count = data[0]
    strings = data[1:].split(b"\0")
    if len(strings) <= count:
        raise ValueError("Truncated intro TEXT")
    return [value.decode("mac_roman") for value in strings[:count]]


def fade_ticks(flags):
    # FadeInColors/FadeOutColors 17:0ab6/0d0e: percent step and tick delay.
    step = ((flags >> 16) & 7) if flags > 65535 else 9
    return (100 // max(1, step)) * (flags & 31)


def dissolve_words(pattern=None):
    """DrawDisolveData 15:31ba copies the two words of each shuffled long."""
    top, left, bottom, right = pattern["rect"] if pattern else STORY_RECT
    if not (0 <= left < right <= SIZE[0] and 0 <= top < bottom <= SIZE[1]
            and (right - left) % 4 == 0):
        raise ValueError("Invalid intro dissolve rectangle")
    columns = (right - left) // 4
    count = columns * (bottom - top)
    if pattern:
        order = pattern["order"]
        if (len(order) != count or any(type(value) is not int for value in order)
                or set(order) != set(range(count))):
            raise ValueError("Invalid intro dissolve order")
    else:
        order = list(range(count))
        random.Random(0).shuffle(order)
    groups = np.asarray(order, dtype=np.intp)
    starts = (top + groups // columns) * SIZE[0] + left + (groups % columns) * 4
    words = np.concatenate((starts, starts + 2))
    return np.column_stack((words, words + 1))


class IntroAssets:
    def __init__(self, directory=ASSET_DIR):
        directory = Path(directory)
        self.program = read_program(directory / "intro.json")
        resources = parse_resource_fork((directory / "NIS.rsrc").read_bytes())
        self.shapes = {key: indexed_shape(value["data"]) for key, value in resources["SHAP"].items()}
        self.palettes = {key: palette_colors(value["data"]) for key, value in resources["CTBL"].items()}
        self.strings = {key: text_strings(value["data"]) for key, value in resources["TEXT"].items()}
        prince = parse_resource_fork((directory / "Prince.rsrc").read_bytes())
        self.font = MacintoshFont(prince["NFNT"][24878]["data"])
        title = parse_resource_fork((directory / "Title.rsrc").read_bytes())
        self.title_shapes = {key: indexed_shape(value["data"]) for key, value in title["SHAP"].items()}
        self.title_palette = palette_colors(title["CTBL"][25001]["data"])
        self.title_script = title["SCRP"][25004]["data"]


class ScriptAnimation:
    """ANI/SCRP layer state, with timing in Macintosh 60 Hz ticks."""

    LENGTHS = {0: 2, 1: 2, 2: 4, 3: 4, 4: 4, 5: 6, 6: 8, 7: 6}

    def __init__(self, data, layers=24):
        if len(data) < 4 or struct.unpack_from(">I", data)[0] != len(data) - 4:
            raise ValueError("Invalid intro SCRP length")
        self.data, self.cursor, self.interval = data, 4, 3
        self.layers = [[0, 0, 0, 16] for _ in range(layers)]
        self.next_tick = 0
        self.done = False
        self.events = []

    def step(self):
        while self.cursor < len(self.data):
            opcode, length = self.data[self.cursor:self.cursor + 2]
            if self.LENGTHS.get(opcode) != length or self.cursor + length > len(self.data):
                raise ValueError("Invalid intro SCRP instruction")
            args = struct.unpack_from(f">{(length - 2) // 2}h", self.data, self.cursor + 2)
            self.cursor += length
            if opcode == 0:
                self.done = True
                return
            if opcode == 1:
                return
            if opcode == 4:
                if args[0] <= 0:
                    raise ValueError("Invalid intro animation interval")
                self.interval = args[0]
            elif opcode in (2, 3):
                self.events.append((opcode, args[0]))
            elif opcode in (5, 6, 7):
                if not 1 <= args[0] <= len(self.layers):
                    raise ValueError("Invalid intro animation layer")
                layer = self.layers[args[0] - 1]
                if opcode == 5:
                    layer[0] = args[1]
                elif opcode == 6:
                    layer[1:3] = args[1:3]
                else:
                    layer[3] = args[1]
        if not self.done:
            raise ValueError("Intro animation has no terminator")

    def advance(self, tick):
        while not self.done and self.next_tick <= tick:
            self.step()
            self.next_tick += self.interval


class IntroPlayer:
    def __init__(self, assets, audio=None):
        self.assets, self.audio = assets, audio
        self.operations = assets.program["operations"]
        self.sounds = assets.program["audio"]
        self.position = 0
        self.time = 0.0
        self.done = False
        self.wait_until = 0.0
        self.timers, self.playing = {}, {}
        self.palette = [(0, 0, 0)] * 256
        self.loaded = {}
        self.target = Image.new("L", SIZE, 1)
        self.display = self.target.copy()
        self.clip = (0, 0, *SIZE)
        self.transition = None
        self.deferred_palette = None
        self.title_animation = None
        self.revision = 0
        self.frame_cache = None
        self.dissolve_words = dissolve_words(assets.program.get("dissolve"))
        self.advance(0)

    @staticmethod
    def box(rect):
        top, left, bottom, right = rect
        return left, top, right, bottom

    def changed(self):
        self.revision += 1
        self.frame_cache = None

    def sound(self, resource_id, kind):
        metadata = self.sounds[str(resource_id)]
        self.playing[kind] = (resource_id, self.time, metadata["duration"])
        if self.audio:
            self.audio.play_intro(resource_id, kind)

    def sound_end(self, kind, resource_id=None):
        playing = self.playing.get(kind)
        if playing is None or (resource_id is not None and playing[0] != resource_id):
            return self.time
        return playing[1] + playing[2]

    def draw_shape(self, resource_id, x, y, flags):
        shape = self.assets.shapes[resource_id]
        region = (max(x, self.clip[0]), max(y, self.clip[1]),
                  min(x + shape.width, self.clip[2]), min(y + shape.height, self.clip[3]))
        if region[0] >= region[2] or region[1] >= region[3]:
            return
        crop = shape.crop((region[0] - x, region[1] - y, region[2] - x, region[3] - y))
        mask = crop.point([0] + [255] * 255) if flags & 16 else None
        self.target.paste(crop, region[:2], mask)

    def text(self, resource_id, index, initial, dx, dy):
        if 25002 in self.assets.shapes:
            self.target.paste(self.assets.shapes[25002], (0, 297))
        if index:
            lines = self.assets.strings[resource_id][index - 1].split("\r")
            font = self.assets.font
            # NISTextDraw 15:0302 and TextInRect 17:28de/2b9a use a
            # baseline, not the top of the NFNT bitmap, to center the lines.
            top = 297 + 87 // 2 - len(lines) * font.height // 2 + font.height - 4 - font.ascent
            for n, line in enumerate(lines):
                mask = font.text(line).getchannel("A")
                left = 1 + max(0, (508 - mask.width) // 2)
                for offset, color in ((8, 255), (6, 3), (5, 14)):
                    self.target.paste(color, (left + offset, top + n * font.height), mask)
            if initial:
                clip, self.clip = self.clip, (0, 0, *SIZE)
                self.draw_shape(initial, 8 + dx, 297 + 30 + dy, 16)
                self.clip = clip
        rect = (0, 297, 512, 384)
        self.display.paste(self.target.crop(rect), rect)
        self.changed()

    def fade(self, colors, into, flags):
        duration = fade_ticks(flags) / 60
        target = dict(colors) if into else {index: (0, 0, 0) for index in colors}
        source = {index: self.palette[index] for index in colors}
        self.transition = ("fade", self.time, duration, source, target)
        self.wait_until = self.time + duration

    def update_transition(self):
        if self.transition is None:
            return
        kind, start, duration, source, target = self.transition
        progress = min(1, (self.time - start) / duration) if duration else 1
        if kind == "title":
            tick = (self.time - start) * 60
            animation = self.title_animation
            if animation.done:
                self.title_started += animation.next_tick / 60
                self.title_animation = animation = ScriptAnimation(self.assets.title_script)
            animation.advance((self.time - self.title_started) * 60)
            frame = self.title_background.copy()
            for shape, x, y, flags in animation.layers:
                if shape:
                    image = self.assets.title_shapes[25000 + shape]
                    frame.paste(image, (x, y), image.point([0] + [255] * 255) if flags & 16 else None)
            music = self.playing[0]
            markers = self.sounds[str(music[0])]["markers"]
            elapsed = self.time - music[1]
            if markers["e"] <= elapsed < markers["f"]:
                image = self.assets.title_shapes[25373]
                frame.paste(image, self.title_text_positions[0], image.point([0] + [255] * 255))
            if markers["g"] <= elapsed < markers["h"]:
                image = self.assets.title_shapes[25374]
                frame.paste(image, self.title_text_positions[1], image.point([0] + [255] * 255))
            self.display = frame
            for index, color in self.assets.title_palette.items():
                self.palette[index] = tuple(round(channel * min(1, tick / 25)) for channel in color)
        elif kind == "fade":
            for index, color in target.items():
                self.palette[index] = tuple(round(a + (b - a) * progress) for a, b in zip(source[index], color))
        else:
            count = int(progress * len(self.dissolve_words))
            indices = self.dissolve_words[source[0]:count].ravel()
            source[1][indices] = target[indices]
            self.display = Image.fromarray(source[1].reshape(SIZE[1], SIZE[0]))
            source[0] = count
        if progress >= 1:
            self.transition = None
        self.changed()

    def start_title(self):
        self.title_animation = ScriptAnimation(self.assets.title_script)
        self.title_started = self.time
        self.title_background = Image.new("L", SIZE, 160)
        for resource_id, x, y in ((25365, 172, 237), (25360, 235, 128),
                                   (25361, 140, 58), (25360, 283, 197), (25361, 96, 163)):
            image = self.assets.title_shapes[resource_id]
            self.title_background.paste(image, (x, y), image.point([0] + [255] * 255))
        # TitleFunc uses these two rectangles to save/restore title overlays.
        self.title_text_positions = [(rect[1], rect[0]) for rect in self.assets.program["title_rects"]]
        self.loaded[2] = self.assets.title_palette
        music = self.playing[0]
        markers = self.sounds[str(music[0])]["markers"]
        duration = max(0, music[1] + markers["i"] - self.time)
        self.transition = ("title", self.time, duration, None, None)
        self.wait_until = self.time + duration

    def execute(self, op, args):
        if op == "shape":
            self.draw_shape(*args)
        elif op == "fill":
            self.target.paste(args[0], self.box(args[1]))
        elif op == "copy":
            box = self.box(args[0])
            self.display.paste(self.target.crop(box), box)
            self.changed()
        elif op == "clip":
            self.clip = self.box(args[0])
        elif op == "dissolve":
            duration = args[0] / 60
            self.transition = ("dissolve", self.time, duration,
                               [0, np.array(self.display).ravel()], np.array(self.target).ravel())
            self.wait_until = self.time + duration
        elif op == "text":
            self.text(*args)
        elif op == "sound":
            self.sound(*args)
        elif op == "stop":
            self.playing.pop(args[0], None)
            if self.audio:
                self.audio.playback.stop("music" if args[0] == 0 else "effect")
        elif op == "wait_sound":
            self.wait_until = max(self.time, self.sound_end(args[1], args[0]))
        elif op == "wait_current":
            self.wait_until = max(self.time, self.sound_end(args[0]))
        elif op == "timer":
            self.timers[args[0]] = self.time + args[1] / 60
        elif op == "wait_timer":
            self.wait_until = max(self.time, self.timers[args[0]])
        elif op == "wait":
            self.wait_until = self.time + args[0] / 60
        elif op == "cue":
            playing = self.playing.get(0)
            if playing is None:
                raise ValueError("Intro cue without music")
            marker = self.sounds[str(playing[0])]["markers"].get(chr(args[0]))
            if marker is None:
                raise ValueError(f"Missing cue {args[0]} in intro music {playing[0]}")
            self.wait_until = max(self.time, playing[1] + marker)
        elif op == "palette":
            resource_id, flags, fade_flags = args
            colors = self.assets.palettes[resource_id]
            if flags & 32:
                old = self.loaded.get(2, {})
                self.fade(old, False, fade_flags)
                self.deferred_palette = (resource_id, flags & ~32, fade_flags)
                return
            for flag in (1, 2):
                if flags & flag:
                    self.loaded[flag] = colors
            if flags & 64:
                for index, color in colors.items():
                    self.palette[index] = (0, 0, 0) if flags & 4 else color
                self.changed()
        elif op == "fade":
            self.fade(self.assets.palettes.get(args[0], {}), args[1], args[2])
        elif op == "fade_both":
            colors = {index: color for colors in self.loaded.values() for index, color in colors.items()}
            self.fade(colors, False, args[0])
        elif op == "brightness":
            flags, percent = args
            for flag, colors in self.loaded.items():
                if flags & flag:
                    for index, color in colors.items():
                        self.palette[index] = tuple(channel * min(100, percent) // 100 for channel in color)
            self.changed()
        elif op == "flash":
            # FadeIndex 15:2a90: 95 down to 0 percent, steps of five.
            index, red, green, blue, delay = args
            source = {index: tuple(channel * 95 // 100 for channel in (red, green, blue))}
            duration = 20 * delay / 60
            self.transition = ("fade", self.time, duration, source, {index: (0, 0, 0)})
            self.wait_until = self.time + duration
        elif op == "title":
            self.start_title()

    def advance(self, seconds):
        if seconds < 0:
            raise ValueError("Intro cannot run backwards")
        end = self.time + seconds
        while not self.done:
            if self.wait_until > end + 1e-9:
                self.time = end
                self.update_transition()
                return
            self.time = max(self.time, self.wait_until)
            self.update_transition()
            if self.deferred_palette is not None:
                args = self.deferred_palette
                self.deferred_palette = None
                self.execute("palette", args)
            if self.position >= len(self.operations):
                self.done = True
                return
            item = self.operations[self.position]
            self.position += 1
            self.execute(item["op"], item["args"])

    def frame(self):
        if self.frame_cache is None:
            frame = self.display.convert("P")
            frame.putpalette([value for color in self.palette for value in color])
            self.frame_cache = frame.convert("RGBA")
        return self.frame_cache.copy()
