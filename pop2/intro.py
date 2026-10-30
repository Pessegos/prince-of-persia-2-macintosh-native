"""Native playback of the Macintosh opening scene program."""

import json
import math
from pathlib import Path
import random
import struct

import numpy as np
from PIL import Image, ImageOps

from pop2.audio import scene_sound_key
from pop2.game_ui import MacintoshFont
from pop2.mac_resources import parse_resource_fork
from pop2.paths import ASSET_DIR


SIZE = (512, 384)
# Classic Macintosh VBL clock, also used by Mini vMac's host timer.
MAC_TICKS_PER_SECOND = 60.14742
STORY_RECT = (62, 64, 292, 448)
OPERATIONS = {
    "shape": 4, "fill": 2, "copy": 1, "clip": 1, "dissolve": 1,
    "text": 5, "sound": 2, "wait_sound": 2, "wait_current": 1,
    "timer": 2, "wait_timer": 1, "wait": 1, "cue": 1, "palette": 3,
    "brightness": 2, "fade": 3, "fade_both": 1, "flash": 5, "stop": 1,
    "title": 0, "fade_in_both": 1, "palette_at": 2, "save_background": 0, "restore": 1,
    # The vision at the throne (NIS 6).
    "rgb": 4, "set_palette": 2, "remap": 2, "combine": 0, "fade_out_all": 1,
    "save_rect": 2, "restore_rect": 1, "ensure_sound": 2, "dissolve_area": 1, "text_panel": 1,
    "blit": 2,
}


def read_program(path):
    data = json.loads(Path(path).read_text(encoding="ascii"))
    if data.get("schema") != 1 or not isinstance(data.get("audio"), dict):
        raise ValueError("Intro data needs to be imported again")
    programs = [data.get("operations"), *(data.get("variants") or {}).values()]
    for operations in programs:
        if not isinstance(operations, list) or not operations:
            raise ValueError("Intro scene program is empty")
        for item in operations:
            if (not isinstance(item, dict) or item.get("op") not in OPERATIONS
                    or not isinstance(item.get("args"), list)
                    or len(item["args"]) != OPERATIONS[item["op"]]):
                raise ValueError("Invalid intro scene instruction")
    return data


def indexed_shape(data, allow_trailing=False):
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
        if not allow_trailing and len(body) - cursor not in (0, 2):
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
    # D7 advances for every group: the first pass alternates word offsets
    # 0, 2, 0, 2; the second copies their complements in the same order.
    offsets = np.arange(count, dtype=np.intp) % 2 * 2
    words = np.concatenate((starts + offsets, starts + 2 - offsets))
    return np.column_stack((words, words + 1))


class IntroAssets:
    def __init__(self, directory=ASSET_DIR, program_name="intro.json"):
        directory = Path(directory)
        self.program = read_program(directory / program_name)
        resources = parse_resource_fork((directory / "NIS.rsrc").read_bytes())
        tree = directory / "NISTree.rsrc"
        if tree.is_file():
            # Tree scenes overlay their SHAP/CTBL on NIS; TEXT 26000 stays there.
            for kind, items in parse_resource_fork(tree.read_bytes()).items():
                resources.setdefault(kind, {}).update(items)
        # Scenes that open other resource files (the carpet scene) refer to
        # their SHAP/CTBL as id + offset.
        # The throne scene also draws a few of the game's own shapes: only the
        # drawn ones are decoded.
        drawn = None
        if self.program.get("kind") == "throne":
            drawn = {item["args"][0] for operations in self.program["variants"].values()
                     for item in operations if item["op"] == "shape"}
        for name, offset in self.program.get("resource_files", {}).items():
            for kind, items in parse_resource_fork((directory / name).read_bytes()).items():
                if kind in ("SHAP", "CTBL"):
                    resources.setdefault(kind, {}).update({
                        offset + key: value for key, value in items.items()
                        if kind == "CTBL" or drawn is None or offset + key in drawn})
        kid = parse_resource_fork((directory / "Kid.rsrc").read_bytes())
        self.kid_palettes = {key: palette_colors(value["data"]) for key, value in kid["CTBL"].items()}
        self.shapes = {key: indexed_shape(value["data"]) for key, value in resources["SHAP"].items()}
        kid_offset = self.program.get('resource_files', {}).get('Kid.rsrc')
        if kid_offset is not None:
            # Resident Kid shapes use local inks 1..16. SetKidPalette puts
            # these colours at 16..31 in the shared game/NIS palette.
            for key in kid['SHAP']:
                if kid_offset + key in self.shapes:
                    self.shapes[kid_offset + key] = self.shapes[kid_offset + key].point(
                        lambda ink: ink + 15 if ink else 0)
        self.palettes = {key: palette_colors(value["data"]) for key, value in resources["CTBL"].items()}
        self.strings = {key: text_strings(value["data"]) for key, value in resources["TEXT"].items()}
        prince = parse_resource_fork((directory / "Prince.rsrc").read_bytes())
        self.font = MacintoshFont(prince["NFNT"][24878]["data"])
        title = parse_resource_fork((directory / "Title.rsrc").read_bytes())
        self.title_shapes = {key: indexed_shape(value["data"]) for key, value in title["SHAP"].items()}
        self.title_palette = palette_colors(title["CTBL"][25001]["data"])
        self.title_script = title["SCRP"][25004]["data"]


class ScriptAnimation:
    """ANI/SCRP layer state, with timing in Macintosh vertical-blank ticks."""

    LENGTHS = {0: 2, 1: 2, 2: 4, 3: 4, 4: 4, 5: 6, 6: 8, 7: 6}

    def __init__(self, data, layers=24):
        if len(data) < 4 or struct.unpack_from(">I", data)[0] != len(data) - 4:
            raise ValueError("Invalid intro SCRP length")
        self.data, self.cursor, self.interval = data, 4, 3
        self.layers = [[0, 0, 0, 16] for _ in range(layers)]
        self.next_tick = 0
        self.cycle_start = 0
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

    def advance(self, tick, repeat=False):
        while not self.done and self.next_tick <= tick + 1e-9:
            self.step()
            if self.done and repeat and self.next_tick > self.cycle_start:
                self.cycle_start = self.next_tick
                self.cursor = 4
                self.layers = [[0, 0, 0, 16] for _ in self.layers]
                self.events.clear()
                self.done = False
            elif not self.done:
                self.next_tick += self.interval


def game_song(cue, directory=ASSET_DIR):
    """Duration and cue markers of a prepared game song (its MIDI file)."""
    import mido

    directory = Path(directory) / "audio"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="ascii"))["cues"]
    elapsed, markers = 0.0, {}
    for event in mido.MidiFile(directory / f"cue-{cue}.mid"):
        elapsed += event.time
        if event.type == "cue_marker":
            markers[event.text.strip()] = elapsed
    return {"duration": manifest[str(cue)]["duration"], "markers": markers, "kind": 0}


# Drawing steps that may run while a carpet-scene fade changes the palette.
ANIMATION_OPS = frozenset(("shape", "copy", "restore", "wait", "fill", "clip"))


def animated_fade_outs(operations):
    """{wait index: (fade-out index, seconds into that wait)} for the QoL fades.

    A fade-out starts early by its own duration, over the drawing steps and
    fixed waits before it, so it ends where the Mac fade would begin.
    """
    starts = {}
    for index, item in enumerate(operations):
        if item["op"] != "fade" or item["args"][1]:
            continue
        duration, remaining = fade_ticks(item["args"][2]) / MAC_TICKS_PER_SECOND, 0.0
        for before in range(index - 1, -1, -1):
            step = operations[before]
            if step["op"] not in ANIMATION_OPS:
                break
            if step["op"] == "wait":
                remaining += step["args"][0] / MAC_TICKS_PER_SECOND
                if remaining >= duration - 1e-9:
                    starts[before] = index, remaining - duration
                    break
    return starts


def area_words(rect):
    """Pixel pairs of a dissolve rectangle in a fixed shuffled order. The
    Macintosh builds its own order for the area (15:3878); that exact
    pattern is not reproduced."""
    top, left, bottom, right = (max(0, rect[0]), max(0, rect[1]),
                                min(SIZE[1], rect[2]), min(SIZE[0], rect[3]))
    if top >= bottom or left >= right:
        return np.zeros((0, 2), dtype=np.intp)
    starts = np.array([y * SIZE[0] + x for y in range(top, bottom) for x in range(left, right, 2)],
                      dtype=np.intp)
    order = list(range(len(starts)))
    random.Random(0).shuffle(order)
    starts = starts[order]
    return np.column_stack((starts, np.minimum(starts + 1, starts // SIZE[0] * SIZE[0] + right - 1)))


class IntroPlayer:
    def __init__(self, assets, audio=None, music=None, variant=None, prince=None, status=None):
        """`music`: (cue, seconds played, game_song metadata) of a game song
        still playing when the scene starts; its cue markers pace the scene.
        `variant` picks one of the program's variants (the throne scene: the
        Prince's native facing) and `prince` his native X and Y, by which
        the operations tagged `follow` move."""
        self.assets, self.audio = assets, audio
        self.variant, self.prince = variant, prince
        program = assets.program
        self.operations = program["variants"][str(variant)] if variant is not None else program["operations"]
        self.follow = (0, 0)
        if prince is not None and "prince" in program:
            self.follow = (prince[0] - program["prince"][0], prince[1] - program["prince"][1])
        self.sounds = program["audio"]
        self.program_kind = program.get("kind") or ("carpet" if "resource_files" in program else None)
        self.status = status.copy() if status is not None else None
        if self.status is None and self.program_kind == 'throne':
            self.status = Image.new('RGBA', (SIZE[0], SIZE[1] - 365), 'black')
        self.position = 0
        self.time = 0.0
        self.done = False
        self.wait_until = 0.0
        self.timers, self.playing = {}, {}
        self.carried_music = {}
        if music is not None:
            cue, played, metadata = music
            self.sounds = {**self.sounds, str(cue): metadata}
            self.playing[0] = self.carried_music[0] = (cue, -played, metadata["duration"])
        self.palette = [(0, 0, 0)] * 256
        self.loaded = {}
        self.target = Image.new("L", SIZE, 1)
        self.display = self.target.copy()
        self.clip = (0, 0, *SIZE)
        self.transition = None
        self.deferred_palette = None
        self.title_animation = None
        self.title_started_at = None
        self.revision = 0
        self.frame_cache = None
        self.dissolve_words = dissolve_words(assets.program.get("dissolve"))
        self.saved_rects = {}
        self.text_panel = None
        # QoL (the carpet scene): the Mac fades block, freezing the clouds; here
        # fade-ins and fade-outs overlap the drawing steps, as in the DOS port.
        self.animated_fades = self.program_kind == "carpet"
        self.early_fades = animated_fade_outs(self.operations) if self.animated_fades else {}
        self.started_fades = set()
        self.advance(0)

    @staticmethod
    def box(rect):
        top, left, bottom, right = rect
        return left, top, right, bottom

    def changed(self):
        self.revision += 1
        self.frame_cache = None

    def sound(self, resource_id, kind):
        metadata = self.sound_metadata(resource_id, kind)
        self.playing[kind] = (resource_id, self.time, metadata["duration"])
        if self.audio:
            self.audio.play_intro(resource_id, kind)

    def sound_metadata(self, resource_id, kind):
        key = scene_sound_key(resource_id, kind)
        return self.sounds[key] if key in self.sounds else self.sounds[str(resource_id)]

    def sound_end(self, kind, resource_id=None):
        playing = self.playing.get(kind)
        if playing is None or (resource_id is not None and playing[0] != resource_id):
            return self.time
        return playing[1] + playing[2]

    def draw_shape(self, resource_id, x, y, flags):
        shape = self.assets.shapes[resource_id]
        if flags & 256:
            # FreeShpInfo 17:5fd0: the shape mirrored left to right.
            shape = ImageOps.mirror(shape)
        region = (max(x, self.clip[0]), max(y, self.clip[1]),
                  min(x + shape.width, self.clip[2]), min(y + shape.height, self.clip[3]))
        if region[0] >= region[2] or region[1] >= region[3]:
            return
        crop = shape.crop((region[0] - x, region[1] - y, region[2] - x, region[3] - y))
        mask = crop.point([0] + [255] * 255) if flags & 16 else None
        self.target.paste(crop, region[:2], mask)

    def text(self, resource_id, index, initial, dx, dy):
        colors = ((8, 255), (6, 3), (5, 14))
        panel = (0, 297, 512, 384)
        if self.text_panel is not None:
            # 15:026e-028c (NIS 6): the saved rectangle is the panel and the
            # text uses entries 1 and 2.
            panel, image = self.saved_rects[self.text_panel]
            self.target.paste(image, panel[:2])
            colors = ((8, 255), (6, 1), (5, 2))
        elif 25002 in self.assets.shapes:
            self.target.paste(self.assets.shapes[25002], (0, 297))
        if index:
            # TextInRect (17:294e-29ba) skips leading spaces on each line.
            lines = [line.lstrip(" ") for line in self.assets.strings[resource_id][index - 1].split("\r")]
            font = self.assets.font
            # NISTextDraw 15:0302 and TextInRect 17:28de/2b9a use a
            # baseline, not the top of the NFNT bitmap, to center the lines.
            top = panel[1] + (panel[3] - panel[1]) // 2 - len(lines) * font.height // 2
            top += font.height - 4 - font.ascent
            for n, line in enumerate(lines):
                mask = font.text(line).getchannel("A")
                left = panel[0] + 1 + max(0, (panel[2] - panel[0] - 4 - mask.width) // 2)
                for offset, color in colors:
                    self.target.paste(color, (left + offset, top + n * font.height), mask)
            if initial:
                clip, self.clip = self.clip, (0, 0, *SIZE)
                self.draw_shape(initial, panel[0] + 8 + dx, panel[1] + 30 + dy, 16)
                self.clip = clip
        rect = panel
        self.display.paste(self.target.crop(rect), rect)
        self.changed()

    def fade(self, colors, into, flags, start=None, blocking=True):
        duration = fade_ticks(flags) / MAC_TICKS_PER_SECOND
        target = dict(colors) if into else {index: (0, 0, 0) for index in colors}
        source = {index: self.palette[index] for index in colors}
        start = self.time if start is None else start
        self.transition = ("fade", start, duration, source, target)
        if blocking:
            self.wait_until = start + duration

    def update_transition(self):
        if self.transition is None:
            return
        kind, start, duration, source, target = self.transition
        progress = 1 if self.time + 1e-9 >= start + duration else max(0, (self.time - start) / duration)
        if kind == "title":
            tick = (self.time - start) * MAC_TICKS_PER_SECOND
            music = self.playing[0]
            markers = self.sound_metadata(music[0], 0)["markers"]
            elapsed = self.time - music[1]
            overlay = 0
            if markers["e"] <= elapsed < markers["f"]:
                overlay = 25373
            elif markers["g"] <= elapsed < markers["h"]:
                overlay = 25374
            brightness = min(1, max(0, (tick - self.title_fade_start) / self.title_fade_ticks))
            changed = self.draw_title(tick, overlay)
            colors = {index: tuple(round(channel * brightness) for channel in color)
                      for index, color in self.assets.title_palette.items()}
            if not changed and all(self.palette[index] == color for index, color in colors.items()) and progress < 1:
                return
            for index, color in colors.items():
                self.palette[index] = color
        elif kind == "fade":
            if self.title_started_at is not None:
                tick = (self.time - self.title_started_at) * MAC_TICKS_PER_SECOND
                self.draw_title(tick, self.title_frame_state[1])
            for index, color in target.items():
                self.palette[index] = tuple(round(a + (b - a) * progress) for a, b in zip(source[index], color))
            if progress >= 1:
                self.title_started_at = None
        else:
            count = int(progress * len(self.dissolve_words))
            indices = self.dissolve_words[source[0]:count].ravel()
            source[1][indices] = target[indices]
            self.display = Image.fromarray(source[1].reshape(SIZE[1], SIZE[0]))
            source[0] = count
        if progress >= 1:
            self.transition = None
        self.changed()

    def draw_title(self, tick, overlay):
        # QoL: unlike the blocking Mac fades, clouds keep their native cadence.
        # SCRP's two cycles are pixel-identical and repeat seamlessly.
        animation = self.title_animation
        animation.advance(tick, repeat=True)
        state = (animation.cursor, overlay)
        if state == self.title_frame_state:
            return False
        self.title_frame_state = state
        frame = self.title_background.copy()
        for shape, x, y, flags in animation.layers:
            if shape:
                image = self.assets.title_shapes[25000 + shape]
                frame.paste(image, (x, y), image.point([0] + [255] * 255) if flags & 16 else None)
        if overlay:
            image = self.assets.title_shapes[overlay]
            position = self.title_text_positions[overlay - 25373]
            frame.paste(image, position, image.point([0] + [255] * 255))
        self.display = frame
        return True

    def start_title(self):
        self.title_frame_state = None
        self.title_started_at = self.time
        self.title_animation = ScriptAnimation(self.assets.title_script)
        self.title_animation.advance(0)
        self.title_fade_start = self.title_animation.next_tick
        self.title_fade_ticks = fade_ticks(0x40001)
        self.title_clock_delay = max(0, self.title_fade_ticks - self.title_fade_start)
        self.title_background = Image.new("L", SIZE, 160)
        # TitleDrawBack (15:7178) uses signed MOVEQ coordinates.
        for resource_id, x, y in ((25365, 172, -19), (25360, -21, 128),
                                   (25361, -116, 58), (25360, 283, 197), (25361, 96, 163)):
            image = self.assets.title_shapes[resource_id]
            self.title_background.paste(image, (x, y), image.point([0] + [255] * 255))
        # TitleFunc uses these two rectangles to save/restore title overlays.
        self.title_text_positions = [(rect[1], rect[0]) for rect in self.assets.program["title_rects"]]
        self.loaded[2] = self.assets.title_palette
        music = self.playing[0]
        markers = self.sound_metadata(music[0], 0)["markers"]
        # Preserve the Mac scene/audio deadlines, including its blocking fade's
        # delay, independently of the continuously moving cloud clock.
        end = ScriptAnimation(self.assets.title_script)
        end.advance(float("inf"))
        duration = min((end.next_tick + self.title_clock_delay) / MAC_TICKS_PER_SECOND,
                       max(0, music[1] + markers["i"] - self.time))
        self.transition = ("title", self.time, duration, None, None)
        self.wait_until = self.time + duration

    def followed(self, item):
        """Arguments of an operation drawn at the Prince's position."""
        args, tag = item["args"], item.get("follow")
        if not tag or self.follow == (0, 0):
            return args
        dx, dy = self.follow[0], self.follow[1] if tag == "xy" else 0
        if item["op"] == "shape":
            return [args[0], args[1] + dx, args[2] + dy, args[3]]
        if item["op"] == "save_rect":
            top, left, bottom, right = args[1]
            return [args[0], [top + dy, left + dx, bottom + dy, right + dx]]
        if item["op"] == "dissolve_area":
            top, left, bottom, right = args[0]
            return [[top + dy, left + dx, bottom + dy, right + dx]]
        return args

    @staticmethod
    def renumbered(colors, first):
        # RemapCTBL 17:6a78 renumbers the entries first, first + 1, ...
        # unless the first one already has index `first`.
        if next(iter(colors), first) != first:
            colors = {first + offset: color for offset, color in enumerate(colors.values())}
        return colors

    def execute(self, op, args):
        if op == "rgb":
            # ShowNthvRGB 17:130e shows one entry at once.
            self.palette[args[0]] = tuple(args[1:])
            self.changed()
        elif op == "set_palette":
            for index, color in self.renumbered(self.assets.palettes[args[0]], args[1]).items():
                if 0 <= index < 256:
                    self.palette[index] = color
            self.changed()
        elif op == "remap":
            self.loaded[args[0]] = self.renumbered(self.loaded.get(args[0], {}), args[1])
        elif op == "combine":
            # CombineCtabs 17:1520 becomes the current table (a5-0x2454).
            self.loaded = {1: {**self.loaded.get(1, {}), **self.loaded.get(2, {})}}
        elif op == "fade_out_all":
            self.fade({index: (0, 0, 0) for index in range(256)}, False, args[0])
        elif op == "save_rect":
            box = self.box(args[1])
            self.saved_rects[args[0]] = box, self.target.crop(box)
        elif op == "restore_rect":
            box, image = self.saved_rects[args[0]]
            self.target.paste(image, box[:2])
        elif op == "ensure_sound":
            if self.sound_end(args[1], args[0]) <= self.time + 1e-9:
                self.sound(*args)
        elif op == "blit":
            # CopyBits 17:5048 within the offscreen picture.
            source, target = self.box(args[0]), self.box(args[1])
            self.target.paste(self.target.crop(source), target[:2])
        elif op == "text_panel":
            self.text_panel = args[0]
        elif op == "dissolve_area":
            self.dissolve_words = None if args[0] is None else area_words(args[0])
        elif op == "dissolve" and self.dissolve_words is None:
            # 15:2c06: without dissolve data the whole screen is copied.
            self.display = self.target.copy()
            self.changed()
        elif op == "shape":
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
            duration = args[0] / MAC_TICKS_PER_SECOND
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
            self.timers[args[0]] = self.time + args[1] / MAC_TICKS_PER_SECOND
        elif op == "wait_timer":
            self.wait_until = max(self.time, self.timers[args[0]])
        elif op == "wait":
            self.wait_until = self.time + args[0] / MAC_TICKS_PER_SECOND
            early = self.early_fades.get(self.position - 1)
            if early is not None:
                fade, offset = early
                fade_args = self.operations[fade]["args"]
                self.fade(self.assets.palettes.get(fade_args[0], {}), False, fade_args[2],
                          start=self.time + offset, blocking=False)
                self.started_fades.add(fade)
        elif op == "cue":
            playing = self.playing.get(0)
            if playing is None and self.program_kind == "carpet":
                return  # 16:26d0 returns at once when no music plays.
            if playing is None:
                raise ValueError("Intro cue without music")
            marker = self.sound_metadata(playing[0], 0)["markers"].get(chr(args[0]))
            if marker is None:
                raise ValueError(f"Missing cue {args[0]} in intro music {playing[0]}")
            self.wait_until = max(self.time, playing[1] + marker)
        elif op == "save_background":
            self.background = self.target.copy()
        elif op == "restore":
            box = self.box(args[0])
            self.target.paste(self.background.crop(box), box[:2])
        elif op == "palette_at":
            # SetKidPalette 3:5f1c -> PoPSetPalette 3:508a(id, 16): RemapCTBL
            # 17:6a78 renumbers the entries first, first + 1, ... unless the
            # first one already has index `first`. Kid CTBLs store 1-16.
            resource_id, first = args
            colors = self.assets.kid_palettes[resource_id]
            if next(iter(colors), first) != first:
                colors = {first + offset: color for offset, color in enumerate(colors.values())}
            for index, color in colors.items():
                if 0 <= index < 256:
                    self.palette[index] = color
            self.changed()
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
            if self.position - 1 in self.started_fades:
                # Started early (animated_fade_outs); it ends here.
                self.wait_until = max(self.time, self.transition[1] + self.transition[2]
                                      if self.transition is not None else self.time)
            else:
                self.fade(self.assets.palettes.get(args[0], {}), args[1], args[2],
                          blocking=not (self.animated_fades and args[1]))
        elif op in ("fade_both", "fade_in_both"):
            colors = {index: color for colors in self.loaded.values() for index, color in colors.items()}
            self.fade(colors, op == "fade_in_both", args[0])
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
            duration = 20 * delay / MAC_TICKS_PER_SECOND
            self.transition = ("fade", self.time, duration, source, {index: (0, 0, 0)})
            self.wait_until = self.time + duration
        elif op == "title":
            self.start_title()

    def seek_operation(self, index):
        if not 0 <= index < len(self.operations):
            raise ValueError("Intro part is outside the scene program")
        audio = self.audio
        self.__init__(self.assets)
        while not self.done and self.position <= index:
            self.advance(max(0, self.wait_until - self.time), stop_position=index + 1)
        self.advance(0)
        self.audio = audio
        if audio is not None:
            audio.reset()
            for kind, (cue, start, duration) in self.playing.items():
                elapsed = self.time - start
                if elapsed < duration:
                    audio.play_intro(cue, kind, offset=elapsed)

    def advance(self, seconds, stop_position=None):
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
            if stop_position is not None and self.position >= stop_position:
                return
            item = self.operations[self.position]
            if (self.animated_fades and item["op"] not in ANIMATION_OPS
                    and self.position not in self.started_fades and self.transition is not None
                    and self.transition[0] == "fade"
                    and self.time + 1e-9 < self.transition[1] + self.transition[2]):
                # Palette, sound and cue steps still follow the whole fade.
                self.wait_until = self.transition[1] + self.transition[2]
                continue
            self.position += 1
            self.execute(item["op"], self.followed(item))

    def next_update_delay(self):
        if self.transition is not None and self.transition[0] == "title":
            start = self.transition[1]
            tick = (self.time - start) * MAC_TICKS_PER_SECOND
            if tick >= self.title_fade_start + self.title_fade_ticks:
                next_tick = self.title_animation.next_tick
                deadline = min(start + next_tick / MAC_TICKS_PER_SECOND, self.wait_until)
                music = self.playing[0]
                markers = self.sound_metadata(music[0], 0)["markers"]
                for key in ("e", "f", "g", "h", "i"):
                    cue = music[1] + markers[key]
                    if cue > self.time + 1e-9:
                        deadline = min(deadline, cue)
                return max(0, deadline - self.time)
        if self.transition is not None:
            start = self.transition[1]
            frame = math.floor((self.time - start) * 60 + 1e-9) + 1
            return max(0, min(self.wait_until, start + frame / 60) - self.time)
        return 1 / 60

    def frame(self):
        if self.frame_cache is None:
            frame = self.display.convert("P")
            # ShowColors (17:0694), called with entries 1..254 by NIS,
            # leaves the display's black index 255 unchanged.
            frame.putpalette([value for color in self.palette[:255] for value in color] + [0, 0, 0])
            self.frame_cache = frame.convert("RGBA")
            if self.status is not None:
                self.frame_cache.paste(self.status, (0, 365))
        return self.frame_cache.copy()
