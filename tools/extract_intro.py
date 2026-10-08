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
from pop2.mac_resources import get_data_fork, parse_resource_fork
from pop2.mac_resources import get_resource_fork
from pop2.intro import STORY_RECT
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


def recover_scenes(program, nis):
    from unicorn import Uc, UcError, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.m68k_const import (
        UC_M68K_REG_A5, UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_D0,
        UC_CPU_M68K_M68000,
    )

    resources = parse_resource_fork(program)
    code = resources["CODE"][15]["data"]
    data = expand_a5_data(resources)
    shapes = parse_resource_fork(nis)["SHAP"]
    scenes = []
    for entry in (0x45c2, 0x4ee8):
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
        cpu.mem_write(stack, struct.pack(">I", end))
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
                if target == 0x331e:
                    emit("shape", w(), w(2), w(4), w(6))
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
                    emit("text", w(), w(2), 0, 0, 0)
                    emit("wait_sound", w(4), 1)
                elif target == 0x26fc:
                    emit("palette", w(), w(2), l(4))
                    for flag, offset in ((1, 0x2454), (2, 0x2450)):
                        if w(2) & flag:
                            pointer = 0x900000 + w() * 8
                            palettes[pointer] = w()
                            cpu.mem_write(a5 - offset, struct.pack(">I", pointer))
                elif target == 0x24a0:
                    emit("brightness", w(), w(2))
                elif target == 0x2a3e:
                    emit("fade_both", l())
                elif target == 0x2a90:
                    emit("flash", w(), l(2), l(6), l(10), l(14))
                elif target == 0x2b70:
                    emit("wait_current", w())
                elif target not in (0x0c36, 0x0c82, 0x29a0):
                    raise ValueError(f"Unrecognized opening helper {target:#x}")
            else:
                target = displacement
                if target == 0x10f2:
                    cpu.mem_write(l(), struct.pack(">4h", 0, 0, 384, 512))
                elif target == 0x10fa:
                    top, left, bottom, right = rectangle(l())
                    dx, dy = w(4), w(6)
                    cpu.mem_write(l(), struct.pack(">4h", top + dy, left + dx, bottom + dy, right + dx))
                elif target == 0x1262:
                    resource_id = w()
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
                elif target in (0x1332, 0x133a):
                    emit("fade", palettes.get(l(), 0), target == 0x1332, l(8))
                elif target == 0xfc2:
                    emit("stop", w())
                elif target == 0xfb2:
                    emit("stop", 1)
                elif target not in (0xf8a, 0x1012, 0x11fa, 0x1202):
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


def extract_intro(image, program, nis, directory, progress=lambda _text: None):
    directory = Path(directory)
    operations = recover_scenes(program, nis)
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
        filename = f"intro-{resource_id}.wav"
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
            midi_path = directory / "audio" / f"intro-{resource_id}.mid"
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
        audio[str(resource_id)] = {"duration": duration, "markers": markers, "kind": kind}
        manifest["cues"][str(resource_id)] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")
    (directory / "audio/playback.mid").unlink(missing_ok=True)
    a5 = expand_a5_data(parse_resource_fork(program))
    title_rects = [list(struct.unpack_from(">4h", a5, len(a5) - offset)) for offset in (0x22f4, 0x22ec)]
    result = {"schema": 1, "operations": operations, "audio": audio, "title_rects": title_rects}
    pattern = extract_dissolve(image)
    if pattern is not None:
        result["dissolve"] = pattern
    (directory / "intro.json").write_text(json.dumps(result, indent=2) + "\n", encoding="ascii")
