"""Recover the opening scene program and audio during game import.

Only the CODE 15 coordinators execute here. Their drawing, sound and timing
calls become a portable scene program; no Macintosh CPU runs in the game.
"""

import io
import json
from pathlib import Path
import struct

import mido
import numpy as np

from pop2.audio_formats import Sample, digitized_sound, mohawk_resources
from pop2.audio import scene_sound_key
from pop2.mac_resources import get_data_fork, parse_resource_fork
from pop2.mac_resources import get_resource_fork
from pop2.intro import STORY_RECT, ScriptAnimation
from tools.extract_audio import render_midi
from tools.extract_enemy_profiles import expand_a5_data


def recover_dissolve(data):
    """Recover pixel order from the game's cached DSLV pointer offsets."""
    if len(data) < 28:
        raise ValueError("Truncated intro dissolve table")
    top, left, bottom, right = struct.unpack_from(">4h", data, 4)
    columns = (right - left + 1) // 4
    count = columns * (bottom - top)
    if columns < 1 or bottom <= top or len(data) != 20 + (count + 1) * 8:
        raise ValueError("Invalid intro dissolve table size")
    sources = [source for source, _destination in struct.iter_unpack(">2I", data[20:-8])]
    sorted_sources = sorted(sources)
    if len(sources) <= columns:
        raise ValueError("Intro dissolve table needs at least two rows")
    stride = sorted_sources[columns] - sorted_sources[0]
    if stride < columns * 4:
        raise ValueError("Invalid intro dissolve source stride")
    base = top * stride + left
    order = []
    for source in sources:
        row, x = divmod(source - base, stride)
        if not 0 <= row < bottom - top or x % 4 or not 0 <= x < columns * 4:
            raise ValueError("Invalid intro dissolve source offset")
        order.append(row * columns + x // 4)
    if set(order) != set(range(count)):
        raise ValueError("Intro dissolve table is not a permutation")
    return {"rect": [top, left, bottom, left + columns * 4], "order": order}


def extract_dissolve(image):
    # Prince2.opt is optional: the Macintosh game creates it on first run.
    try:
        cache = parse_resource_fork(get_resource_fork(image, "Prince2.opt", None))
    except (FileNotFoundError, ValueError):
        return None
    for resource in cache.get("DSLV", {}).values():
        try:
            pattern = recover_dissolve(resource["data"])
        except (ValueError, struct.error):
            continue
        if tuple(pattern["rect"]) == STORY_RECT:
            return pattern
    return None


def recover_scenes(program, nis, entries=(0x45c2, 0x4ee8), arguments=(), a5_words=None,
                   callbacks=None, files=None):
    """Run CODE 15 coordinators. ``arguments`` are the Pascal word arguments
    after the return address, ``a5_words`` preset A5-relative globals and
    ``callbacks`` maps an A5 jump-table offset to an animation callback name.

    ``files`` maps the A5 offset of a resource-file record to (id offset,
    parsed resources). While the coordinator has such a file open (open
    17:3260, close 17:322e) its SHAP/CTBL take precedence, like the Resource
    Manager's search order, and are emitted as id + offset."""
    from unicorn import Uc, UcError, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.m68k_const import (
        UC_M68K_REG_A5, UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_D0,
        UC_M68K_REG_D1, UC_CPU_M68K_M68000,
    )

    resources = parse_resource_fork(program)
    code = resources["CODE"][15]["data"]
    data = expand_a5_data(resources)
    resources_all = nis if isinstance(nis, dict) else parse_resource_fork(nis)
    files = files or {}
    shapes = dict(resources_all["SHAP"])
    for offset, extra in files.values():
        shapes.update({offset + key: value for key, value in extra.get("SHAP", {}).items()})
    callbacks = callbacks or {}
    opened = []
    files_by_offset = {offset: extra for offset, extra in files.values()}

    def resolve(kind, resource_id):
        for record in reversed(opened):
            offset, extra = files[record]
            if resource_id in extra.get(kind, {}):
                return offset + resource_id
        return resource_id
    scenes = []
    for entry in entries:
        if code[entry:entry + 2] != b"\x4e\x56":
            raise ValueError("Unsupported Macintosh opening coordinator")
        if entry == 0x4ee8:
            scenes.append({"op": "title", "args": [], "pc": 0x6f1a})
            scenes.append({"op": "fade_both", "args": [0x90001], "pc": 0x6fac})
        base, a5, stack, end = 0x10000, 0x80000, 0xf0000, 0xff000
        cpu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        cpu.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        cpu.mem_map(0, 0x1000000)
        cpu.mem_write(base, code)
        cpu.mem_write(a5 - len(data), data)
        cpu.mem_write(a5 - 0x521e, b"\1")
        cpu.mem_write(stack, struct.pack(">I", end))
        for index, value in enumerate(arguments):
            cpu.mem_write(stack + 4 + index * 2, struct.pack(">h", value))
        for offset, value in (a5_words or {}).items():
            cpu.mem_write(a5 - offset, struct.pack(">h", value))
        cpu.reg_write(UC_M68K_REG_A5, a5)
        cpu.reg_write(UC_M68K_REG_A7, stack)
        pointers, handles, palettes = {}, {}, {0x900000 + 25001 * 8: 25001}
        cpu.mem_write(a5 - 0x2454, struct.pack(">I", 0x900000 + 25001 * 8))
        pool = 0x200000
        operations = []

        def word(address):
            return struct.unpack(">h", cpu.mem_read(address, 2))[0]

        def long(address):
            return struct.unpack(">I", cpu.mem_read(address, 4))[0]

        def rectangle(pointer):
            return list(struct.unpack(">4h", cpu.mem_read(pointer, 8)))

        def emit(op, *args):
            operations.append({"op": op, "args": list(args), "pc": address_now - base})

        address_now = base

        def hook(cpu, address, size, user):
            nonlocal pool, address_now
            address_now = address
            instruction = bytes(cpu.mem_read(address, 4))
            opcode = instruction[:2]
            if instruction[0] & 0xf0 == 0xa0:
                cpu.reg_write(UC_M68K_REG_PC, address + 2)
                return
            if opcode not in (b"\x4e\xad", b"\x4e\xba", b"\x4e\x90"):
                return
            sp = cpu.reg_read(UC_M68K_REG_A7)
            w = lambda offset=0: word(sp + offset)
            l = lambda offset=0: long(sp + offset)
            result = 0
            if opcode == b"\x4e\x90":
                # Pascal SetClip(Rect*) removes its own argument.
                emit("clip", rectangle(l()))
                cpu.reg_write(UC_M68K_REG_A7, sp + 4)
                cpu.reg_write(UC_M68K_REG_PC, address + 2)
                return
            displacement = struct.unpack(">h", instruction[2:4])[0]
            if opcode == b"\x4e\xba":
                target = address + 2 + displacement - base
                if target in (0x331e, 0x0c98):
                    # 15:0c98 draws a SHAP of an open file, as AddNIS does.
                    emit("shape", resolve("SHAP", w()), w(2), w(4), w(6))
                elif target == 0x0b32:
                    emit("fill", w(4) & 255, rectangle(l(6)))
                elif target == 0x32f4:
                    emit("copy", rectangle(l()))
                elif target == 0x0bce:
                    emit("dissolve", w())
                elif target == 0x0170:
                    initial = word(a5 - 0x2460) if word(a5 - 0x245e) else 0
                    emit("text", w(), w(2), initial, word(a5 - 0x2462), word(a5 - 0x2464))
                    cpu.mem_write(a5 - 0x245e, b"\0\0")
                elif target == 0x0bf4:
                    emit("sound", w(4), 1)
                    initial = word(a5 - 0x2460) if word(a5 - 0x245e) else 0
                    emit("text", w(), w(2), initial, word(a5 - 0x2462), word(a5 - 0x2464))
                    cpu.mem_write(a5 - 0x245e, b"\0\0")
                    emit("wait_sound", w(4), 1)
                elif target == 0x26fc:
                    palette_id = resolve("CTBL", w())
                    emit("palette", palette_id, w(2), l(4))
                    for flag, offset in ((1, 0x2454), (2, 0x2450)):
                        if w(2) & flag:
                            pointer = 0x900000 + palette_id * 8
                            palettes[pointer] = palette_id
                            cpu.mem_write(a5 - offset, struct.pack(">I", pointer))
                elif target == 0x24a0:
                    emit("brightness", w(), w(2))
                elif target == 0x2a3e:
                    emit("fade_both", l())
                elif target == 0x29ea:
                    emit("fade_in_both", l())
                elif target == 0x2a90:
                    emit("flash", w(), l(2), l(6), l(10), l(14))
                elif target == 0x2b70:
                    emit("wait_current", w())
                elif target not in (0x0c36, 0x0c82, 0x29a0):
                    raise ValueError(f"Unrecognized opening helper {target:#x}")
            else:
                target = displacement
                if target == 0x10f2:
                    cpu.mem_write(l(), struct.pack(">4h", 0, 0, 384, 510))
                elif target == 0x10fa:
                    top, left, bottom, right = rectangle(l())
                    dx, dy = w(4), w(6)
                    cpu.mem_write(l(), struct.pack(">4h", top + dy, left + dx, bottom + dy, right + dx))
                elif target == 0x1262:
                    resource_id = resolve("SHAP", w())
                    if resource_id not in shapes:
                        raise ValueError(f"Opening SHAP {resource_id} is missing")
                    if resource_id not in handles:
                        shape = shapes[resource_id]["data"]
                        handle, pointer = pool, pool + 4
                        pool += (len(shape) + 7) & ~3
                        cpu.mem_write(handle, struct.pack(">I", pointer))
                        cpu.mem_write(pointer, shape)
                        pointers[pointer] = resource_id
                        handles[resource_id] = handle
                    result = handles[resource_id]
                elif target == 0x125a:
                    emit("shape", pointers[l()], w(8), w(10), w(12))
                    if l(16):
                        _, _, width, height = struct.unpack(">HhhH", shapes[pointers[l()]]["data"][:8])
                        cpu.mem_write(l(16), struct.pack(">4h", w(10), w(8), w(10) + height, w(8) + width))
                elif target == 0x1172:
                    emit("timer", w(), l(2))
                elif target == 0x117a:
                    emit("wait_timer", w())
                elif target == 0x118a:
                    emit("wait", w(2))
                elif target in (0xfa2, 0xfda):
                    emit("sound", w(2) if target == 0xfa2 else w(), l(4) if target == 0xfa2 else w(2))
                elif target == 0x1002:
                    emit("cue", w())
                elif target == 0x100a:
                    emit("wait_sound", w(), w(2))
                elif target == 0xf5a:
                    callback = callbacks.get(l(6) - a5) if l(6) else None
                    if (l(6) and callback is None) or w(16) not in (6, 0x0c, 0x1c):
                        raise ValueError("Unsupported scene animation callback or flags")
                    # PlayTheAnimation 16:10ba-10e8: flag 2 places the
                    # animation at the given point, flag 16 at the ANI
                    # bounds' top-left, otherwise at the origin.
                    # An animation of an open scene file keeps its id offset.
                    animation_id = resolve("ANI ", w() + w(2))
                    first = animation_id - w(2)
                    header = (resources_all["ANI "] if animation_id == w() + w(2)
                              else files_by_offset[animation_id - w() - w(2)]["ANI "])[w() + w(2)]
                    top, left, bottom, right = struct.unpack_from('>4h', header['data'])
                    if w(16) & 2:
                        x, y = w(20), w(22)
                    elif w(16) & 16:
                        x, y = left, top
                    else:
                        x = y = 0
                    if w(18):
                        # 16:11b8-11ce: PaintRect of the animation's bounds
                        # within the screen in palette index $1a.
                        emit("fill", w(18) & 255, [max(0, y), max(0, x), min(384, y + bottom - top),
                                                   min(512, x + right - left)])
                    emit("animation", first, w(2), x, y, *([callback] if callback else []))
                    if w(16) & 8:
                        operations[-1]["flags"] = w(16)
                    if opened:
                        # The Resource Manager's search order for its shapes.
                        operations[-1]["search"] = [files[record][0] for record in reversed(opened)] + [0]
                elif target in (0x1332, 0x133a):
                    emit("fade", palettes.get(l(), 0), target == 0x1332, l(8))
                elif target == 0xfc2:
                    emit("stop", w())
                elif target == 0xfb2:
                    emit("stop", 1)
                elif target == 0x13d2:
                    # Runtime signed long division 19:4bb0: d0 / d1 -> d0.
                    signed = lambda value: value - (1 << 32) if value & (1 << 31) else value
                    dividend = signed(cpu.reg_read(UC_M68K_REG_D0))
                    divisor = signed(cpu.reg_read(UC_M68K_REG_D1))
                    quotient = abs(dividend) // abs(divisor)
                    result = (-quotient if (dividend < 0) != (divisor < 0) else quotient) & 0xffffffff
                elif target in (0x11a2, 0x119a) and a5 - l() in files:
                    # Open (17:3260) or close (17:322e) a scene resource file.
                    record = a5 - l()
                    if record in opened:
                        opened.remove(record)
                    if target == 0x11a2:
                        opened.append(record)
                elif target == 0x2e2:
                    # SetKidPalette 3:5f1c: Kid CTBL 25000 + environment at 16.
                    emit("palette_at", 25000 + w(), 16)
                elif target == 0x1222:
                    # 17:4fe4 CopyBits: show the given rectangle.
                    emit("copy", rectangle(l(8)))
                elif target == 0x12da:
                    # 17:6dd6: PaintRect(rect) in palette index `color`.
                    emit("fill", w(4) & 255, rectangle(l()))
                elif target == 0x132a:
                    # SetSHAPColors 17:0a52 prepares the offscreen colour
                    # table; indexed drawing is unaffected by it.
                    pass
                elif target not in (0xf8a, 0xfea, 0x1012, 0x11fa, 0x1202, 0x11a2, 0x119a):
                    raise ValueError(f"Unrecognized opening API {target:#x}")
            cpu.reg_write(UC_M68K_REG_D0, result)
            cpu.reg_write(UC_M68K_REG_PC, address + 4)

        cpu.hook_add(UC_HOOK_CODE, hook)
        try:
            cpu.emu_start(base + entry, end, count=100000)
        except UcError as error:
            raise ValueError("Unsupported Macintosh opening code") from error
        if cpu.reg_read(UC_M68K_REG_PC) != end:
            raise ValueError("Opening coordinator did not terminate")
        scenes.extend(operations)
    return scenes


def expand_animations(operations, nis, callbacks=None):
    """Flatten persistent-background PlayTheAnimation flags 6.

    PlayTheAnimation 16:13d4-13f8 draws a frame, then calls the callback with
    the displayed frame number before copying it to the screen (16:140a).
    ``callbacks`` maps a callback name to {frame: operations}; frames without
    operations return zero, as TreeFunc does for every frame except two."""
    resources = nis if isinstance(nis, dict) else parse_resource_fork(nis)
    callbacks = callbacks or {}
    result = []
    for item in operations:
        if item['op'] != 'animation':
            result.append(item)
            continue
        base, index, x, y, *callback = item['args']
        frame_operations = callbacks[callback[0]] if callback else {}
        frame = 0
        header = resources['ANI '][base + index]['data']
        if len(header) != 18:
            raise ValueError('Unsupported scene ANI header')
        _top, _left, _bottom, _right, layers, script_id, *_rest = struct.unpack('>9h', header)
        if not 1 <= layers <= 24:
            raise ValueError('Unsupported scene animation layer count')
        # Resources of an opened scene file carry an id offset of 100000 * n.
        offset = base - base % 100000
        animation = ScriptAnimation(resources['SCRP'][script_id + offset]['data'], layers)

        def emit(op, *args):
            result.append({'op': op, 'args': list(args), 'pc': item['pc']})

        # Flag 8 (16:121c, 16:1378-13bc): the background is saved before the
        # first frame, and each frame first restores it under the previous
        # frame's layers; the copy to the screen then covers both.
        restore = bool(item.get('flags', 0) & 8)
        previous = []
        if restore:
            emit('save_background')
        while not animation.done:
            animation.step()
            for opcode, argument in animation.events:
                if opcode == 3 and argument:
                    emit('sound', argument, 1)
                elif opcode == 2:
                    raise ValueError('Scene animation notify requires a callback')
            animation.events.clear()
            if animation.done:
                break
            rectangles = []
            for rectangle in previous:
                emit('restore', rectangle)
            for shape, dx, dy, flags in animation.layers:
                if not shape:
                    continue
                shape_id = next((offset + base % 100000 + shape
                                 for offset in item.get('search', (base - base % 100000,))
                                 if offset + base % 100000 + shape in resources['SHAP']),
                                base + shape)
                data = resources['SHAP'][shape_id]['data']
                _encoding, _stride, width, height = struct.unpack_from('>HhhH', data)
                emit('shape', shape_id, x + dx, y + dy, flags)
                rectangles.append([y + dy, x + dx, y + dy + height, x + dx + width])
            frame += 1
            result.extend(frame_operations.get(frame, ()))
            for rectangle in previous + rectangles:
                emit('copy', rectangle)
            if restore:
                previous = rectangles
            emit('wait', animation.interval)
    return result


def extract_scene_audio(image, operations, directory, progress=lambda _text: None, *, banked=False):
    directory = Path(directory).resolve()
    banks = {
        0: mohawk_resources(get_data_fork(image, "NISMIDI.dat"))["MIDI"],
        1: mohawk_resources(get_data_fork(image, "NISDIGI.dat"))["snd "],
    }
    native_voices = set(banks[1])
    fallback = mohawk_resources(get_data_fork(image, "DigiSnd.dat"))["snd "]
    banks[1] = {**fallback, **banks[1]}
    manifest_path = directory / "audio/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    audio = {}
    for resource_id, kind in sorted({tuple(item["args"]) for item in operations if item["op"] == "sound"}):
        progress(f"Preparing intro audio {resource_id}...")
        key = scene_sound_key(resource_id, kind) if banked else str(resource_id)
        stem = key if banked else f"intro-{resource_id}"
        filename = f"{stem}.wav"
        output = directory / "audio" / filename
        data = banks[kind][resource_id]
        markers = {}
        entry = {"file": filename, "priority": 0, "mode": 2,
                 "kind": "midi" if kind == 0 else "pcm", "resource_id": resource_id}
        if kind == 0:
            midi = mido.MidiFile(file=io.BytesIO(data))
            entry.update(source_archive="NISMIDI.dat", duration=midi.length)
            elapsed = 0.0
            for event in midi:
                elapsed += event.time
                if event.type == "cue_marker":
                    markers[event.text.strip()] = elapsed
            midi_path = directory / "audio" / f"{stem}.mid"
            midi_path.write_bytes(data)
            duration = render_midi(directory / "audio", midi_path.name, output)
            entry["playback_duration"] = duration
        else:
            sample = digitized_sound(data)
            pcm = ((np.frombuffer(sample.pcm, dtype=np.uint8).astype(np.int16) - 128) * 64).astype("<i2").tobytes()
            output.write_bytes(Sample(pcm, sample.rate, sample.channels, 2).wav())
            duration = len(sample.pcm) / sample.channels / sample.rate
            entry.update(duration=duration, source_archive=(
                "NISDIGI.dat" if resource_id in native_voices else "DigiSnd.dat"))
        audio[key] = {"duration": duration, "markers": markers, "kind": kind}
        manifest.setdefault('scene_cues' if banked else 'cues', {})[key] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")
    (directory / "audio/playback.mid").unlink(missing_ok=True)
    return audio


def extract_intro(image, program, nis, directory, progress=lambda _text: None):
    directory = Path(directory)
    operations = recover_scenes(program, nis)
    audio = extract_scene_audio(image, operations, directory, progress)
    a5 = expand_a5_data(parse_resource_fork(program))
    title_rects = [list(struct.unpack_from(">4h", a5, len(a5) - offset)) for offset in (0x22f4, 0x22ec)]
    result = {"schema": 1, "operations": operations, "audio": audio, "title_rects": title_rects}
    pattern = extract_dissolve(image)
    if pattern is not None:
        result["dissolve"] = pattern
    (directory / "intro.json").write_text(json.dumps(result, indent=2) + "\n", encoding="ascii")


def extract_ending(image, program, nis, directory, progress=lambda _text: None):
    """CheckPlayNIS selects NIS 9 for the level 1 -> 2 transition."""
    directory = Path(directory)
    operations = recover_scenes(program, nis, entries=(0x0cf2,))
    audio = extract_scene_audio(image, operations, directory, progress)
    result = {"schema": 1, "operations": operations, "audio": audio}
    (directory / "ending.json").write_text(json.dumps(result, indent=2) + "\n", encoding="ascii")


def extract_discovery(image, program, nis, directory, progress=lambda _text: None):
    """CheckPlayNIS selects Discovery (NIS 10) when leaving level 3."""
    directory = Path(directory)
    operations = expand_animations(recover_scenes(program, nis, entries=(0x1a76,)), nis)
    audio = extract_scene_audio(image, operations, directory, progress, banked=True)
    result = {'schema': 1, 'operations': operations, 'audio': audio}
    (directory / 'discovery.json').write_text(json.dumps(result, indent=2) + '\n', encoding='ascii')


# NISCarpet (NIS 1, CheckPlayNIS(5, 6)) opens these files (A5 file records)
# over NIS.rsrc; the scene program shows their resources as id + offset.
CARPET_FILES = {0x26ce: ('TNIS1.rsrc', 100000), 0x26c8: ('TNIS2.rsrc', 200000),
                0x26c2: ('TNIS3.rsrc', 300000), 0x470c: ('Ruins.rsrc', 400000),
                0x4712: ('Caverns.rsrc', 500000)}
CARPET_CALLBACKS = {0xe7a: ('carpet1', 0x19c2), 0xe82: ('carpet2', 0x1a44)}


def carpet_resources(nis, files):
    """NIS.rsrc plus each carpet file's resources at its id offset."""
    merged = {kind: dict(items) for kind, items in parse_resource_fork(nis).items()}
    for name, offset in CARPET_FILES.values():
        for kind, items in parse_resource_fork(files[name]).items():
            merged.setdefault(kind, {}).update({offset + key: value for key, value in items.items()})
    return merged


def recover_carpet(program, nis, files):
    """NISCarpet 15:1630 (the 15:07c8 dispatcher's NIS 1) and its callbacks.

    TransFunc1 15:19c2 shows the drawn screen on frame 1, then waits for music
    cue 97 and fades in the current palette on frame 2; TransFunc3 15:1a44
    waits for cue 99 on frame 1. Their fade reads the palette the coordinator
    last loaded (a5-0x2450), so each animation gets its own copy.
    """
    parsed = {record: (offset, parse_resource_fork(files[name]))
              for record, (name, offset) in CARPET_FILES.items()}
    names = {offset: name for offset, (name, _entry) in CARPET_CALLBACKS.items()}
    operations = recover_scenes(program, nis, entries=(0x1630,), callbacks=names, files=parsed)
    callbacks, palette = {}, 0
    for item in operations:
        if item['op'] == 'palette' and item['args'][1] & 2:
            palette = item['args'][0]
        if item['op'] == 'animation' and len(item['args']) == 5:
            name = f"{item['args'][4]}:{palette}"
            entry = next(entry for callback, entry in CARPET_CALLBACKS.values() if callback == item['args'][4])
            frames = {}
            for frame in (1, 2):
                frame_operations = recover_scenes(program, nis, entries=(entry,), arguments=(frame,),
                                                  files=parsed)
                for operation in frame_operations:
                    if operation['op'] == 'fade' and operation['args'][0] == 0:
                        operation['args'][0] = palette
                if frame_operations:
                    frames[frame] = frame_operations
            callbacks[name] = frames
            item['args'][4] = name
    return expand_animations(operations, carpet_resources(nis, files), callbacks)


def extract_carpet(image, program, nis, files, directory, progress=lambda _text: None):
    """Write the carpet scene shown between levels five and six."""
    directory = Path(directory)
    operations = recover_carpet(program, nis, files)
    audio = extract_scene_audio(image, operations, directory, progress, banked=True)
    result = {'schema': 1, 'resource_files': {name: offset for name, offset in CARPET_FILES.values()},
              'operations': operations, 'audio': audio}
    (directory / 'carpet.json').write_text(json.dumps(result, indent=2) + '\n', encoding='ascii')


TREE_VARIANTS = range(1, 10)


def tree_resources(nis, nistree):
    """Overlay NISTree's SHAP/CTBL/ANI/SCRP on NIS; TEXT 26000 stays in NIS."""
    merged = {kind: dict(items) for kind, items in parse_resource_fork(nis).items()}
    for kind, items in parse_resource_fork(nistree).items():
        overlap = set(merged.get(kind, {})) & set(items)
        if overlap:
            raise ValueError(f"NISTree {kind} resources collide with NIS: {sorted(overlap)}")
        merged.setdefault(kind, {}).update(items)
    return merged


def recover_tree(program, resources, variant):
    """TreeCheck 15:0568 for one variant (NIS 12..20 -> 1..9, 15:0102).

    TreeFunc 15:04d0 runs from PlayTheAnimation with the displayed frame
    number. Only frame 2 does work, reading the variant from a5-0x245c."""
    a5_words = {0x245c: variant}
    callback = recover_scenes(program, resources, entries=(0x04d0,), arguments=(2,),
                              a5_words=a5_words)
    operations = recover_scenes(program, resources, entries=(0x0568,), arguments=(variant,),
                                a5_words=a5_words, callbacks={0xf02: 'tree'})
    return expand_animations(operations, resources, {'tree': {2: callback}})


def extract_trees(image, program, nis, nistree, directory, progress=lambda _text: None):
    """Write the nine native tree scenes as portable scene programs."""
    directory = Path(directory)
    resources = tree_resources(nis, nistree)
    for variant in TREE_VARIANTS:
        progress(f'Preparing tree scene {variant}...')
        operations = recover_tree(program, resources, variant)
        audio = extract_scene_audio(image, operations, directory, progress, banked=True)
        result = {'schema': 1, 'operations': operations, 'audio': audio}
        (directory / f'tree-{variant}.json').write_text(json.dumps(result, indent=2) + '\n',
                                                         encoding='ascii')
