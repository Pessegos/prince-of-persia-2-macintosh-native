"""Recover the level-one RECG demo and credits during game import.

The original simulation resolves its recorded controller latches into a
portable actor trace. No Macintosh instructions execute during playback.
"""

import io
import json
from pathlib import Path
import struct

from pop2.game_ui import MacintoshFont
from pop2.intro import fade_ticks
from pop2.mac_resources import get_data_fork, parse_resource_fork
from pop2.audio_formats import mohawk_resources
from pop2.recorded_game import RecordedGame
from tools.extract_enemy_profiles import expand_a5_data
from tools.extract_audio import render_midi


def jump_targets(code_zero, segments):
    if len(code_zero) < 16:
        raise ValueError("Truncated Macintosh jump table")
    _above, _below, size, offset = struct.unpack_from(">4I", code_zero)
    if size % 8 or len(code_zero) != 16 + size:
        raise ValueError("Invalid Macintosh jump table size")
    targets = []
    for index in range(size // 8):
        displacement, push, segment, trap = struct.unpack_from(">4H", code_zero, 16 + index * 8)
        if push != 0x3f3c or trap != 0xa9f0 or segment not in segments:
            raise ValueError("Unsupported Macintosh jump table entry")
        if displacement + 4 >= len(segments[segment]["data"]):
            raise ValueError("Macintosh jump target is outside its segment")
        targets.append((offset + index * 8 + 2, segment * 0x10000 + displacement + 4))
    return targets


class RecordedSimulation:
    A5, STACK, END = 0x400000, 0x4f0000, 0x4ff000
    SECT_RECT = 0xa00000
    # Display/audio services and object families unused by the rooftop demo.
    DEVICE_SEGMENTS = {8, 10, 15, 16, 20, 21, 22, 23, 24}
    DEVICE_CALLS = {(2, 0x3a38), (2, 0x7194), (2, 0x51f4), (5, 0x4e76),
                    *((17, offset) for offset in (0x3032, 0x31b8, 0x3136, 0x31f2,
                                                  0x31d4, 0x4cf4, 0x4d4a, 0x685e, 0x67f4))}

    def __init__(self, program, banks):
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
        from unicorn.m68k_const import (UC_CPU_M68K_M68000, UC_M68K_REG_A5,
                                       UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_PC)

        self.registers = UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_PC
        self.resources = parse_resource_fork(program)
        for segment, offset, signature in ((2, 0x6224, b"\x2f\x03\x30\x2d"),
                                            (2, 0x5cf4, b"\x48\xe7\x1c\x20"),
                                            (5, 0x638a, b"\x4e\x56\xff\xfc"),
                                            (3, 0x1ab0, b"\x48\xe7\x10\x20")):
            if self.resources["CODE"][segment]["data"][offset:offset + 4] != signature:
                raise ValueError("Unsupported Macintosh recorded-game routines")
        self.banks = {name: parse_resource_fork(data) for name, data in banks.items()}
        self.cpu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.cpu.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        self.cpu.mem_map(0, 0x1000000)
        data = expand_a5_data(self.resources)
        self.cpu.mem_write(self.A5 - len(data), data)
        for segment, resource in self.resources["CODE"].items():
            if segment:
                self.cpu.mem_write(segment * 0x10000, resource["data"])
        for offset, target in jump_targets(self.resources["CODE"][0]["data"], self.resources["CODE"]):
            self.cpu.mem_write(self.A5 + offset, b"\x4e\xf9" + struct.pack(">I", target))
        self.cpu.reg_write(UC_M68K_REG_A5, self.A5)
        self.pool, self.handles, self.sounds = 0x500000, {}, []
        self.pen, self.credit_lines = [0, 0], None
        self.font = MacintoshFont(self.banks["Prince"]["NFNT"][24878]["data"])
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)

    def word(self, address):
        return struct.unpack(">h", self.cpu.mem_read(address, 2))[0]

    def long(self, address):
        return struct.unpack(">I", self.cpu.mem_read(address, 4))[0]

    def write_word(self, offset, value):
        self.cpu.mem_write(self.A5 + offset, struct.pack(">H", value & 65535))

    def write_long(self, offset, value):
        self.cpu.mem_write(self.A5 + offset, struct.pack(">I", value))

    def allocate(self, data):
        pointer = self.pool
        self.pool += (len(data) + 3) & ~3
        if self.pool >= self.SECT_RECT:
            raise ValueError("Recorded-game resource budget exceeded")
        self.cpu.mem_write(pointer, bytes(data))
        return pointer

    def resource(self, kind, resource_id, bank=None):
        key = kind, resource_id, bank
        if key not in self.handles:
            source = (self.banks[bank] if bank else
                      next((b for b in self.banks.values() if resource_id in b.get(kind, {})),
                           self.resources))
            raw = source.get(kind, {}).get(resource_id, {}).get("data")
            if raw is None:
                return 0
            pointer = self.allocate(raw)
            self.handles[key] = self.allocate(struct.pack(">I", pointer))
        return self.handles[key]

    def call(self, segment, offset, args=b""):
        a7, _d0, pc = self.registers
        self.cpu.mem_write(self.STACK, struct.pack(">I", self.END) + args)
        self.cpu.reg_write(a7, self.STACK)
        self.cpu.emu_start(segment * 0x10000 + offset, self.END, count=2000000)
        if self.cpu.reg_read(pc) != self.END:
            raise ValueError("Recorded-game instruction budget exceeded")

    def hook(self, cpu, address, _size, _user):
        a7, d0, pc = self.registers
        sp = cpu.reg_read(a7)
        segment, offset = divmod(address, 0x10000)
        entry = segment, offset

        def finish(value=0):
            cpu.reg_write(d0, value & 0xffffffff)
            cpu.reg_write(a7, sp + 4)
            cpu.reg_write(pc, self.long(sp))

        if address == self.SECT_RECT:
            source = struct.unpack(">4h", cpu.mem_read(self.long(sp + 8), 8))
            clip = struct.unpack(">4h", cpu.mem_read(self.long(sp + 12), 8))
            top, left = max(source[0], clip[0]), max(source[1], clip[1])
            bottom, right = min(source[2], clip[2]), min(source[3], clip[3])
            valid = top < bottom and left < right
            rect = (top, left, bottom, right) if valid else (0, 0, 0, 0)
            cpu.mem_write(self.long(sp + 4), struct.pack(">4h", *rect))
            cpu.mem_write(sp + 16, bytes((int(valid), 0)))
            cpu.reg_write(a7, sp + 16)
            cpu.reg_write(pc, self.long(sp))
            return
        if entry == (17, 0x330e):
            kind = bytes(cpu.mem_read(sp + 4, 4)).decode("ascii")
            finish(self.resource(kind, self.word(sp + 8)))
            return
        if entry == (4, 0x3098):
            finish(self.resource("SEQS", self.word(sp + 4)))
            return
        if entry == (3, 0x5278):
            finish()
            return
        if entry == (3, 0x5f58):
            self.write_word(-0x46dc, self.word(sp + 4))
            finish()
            return
        if entry == (17, 0x6e06):
            seed = (self.long(self.A5 - 0x18fc) or 1) * 16807 % 2147483647
            self.write_long(-0x18fc, seed)
            value = seed & 65535
            finish((0 if value == 0x8000 else value) % (self.word(sp + 4) + 1))
            return
        if entry == (2, 0x532c):
            finish(-2)
            return
        if entry == (2, 0x55d2):
            for field in (-0x3498, -0x3496, -0x3494):
                self.write_word(field, 0)
            finish()
            return
        if entry in ((5, 0x4d84), (5, 0x4d58)):
            self.sounds.append(["sound" if offset == 0x4d84 else "song", self.word(sp + 4),
                                0 if self.word(self.A5 - 0x5056) == 10 else 2])
            finish()
            return
        if self.credit_lines is not None and entry == (2, 0x0546):
            self.credit_text(sp)
            finish()
            return
        if self.credit_lines is not None and entry == (17, 0x275a):
            pointer = self.long(self.long(sp + 4)) + 1
            index = cpu.mem_read(sp + 8, 1)[0]
            for _ in range(index - 1):
                while cpu.mem_read(pointer, 1)[0]:
                    pointer += 1
                pointer += 1
            finish(pointer)
            return
        if segment in self.DEVICE_SEGMENTS or entry in self.DEVICE_CALLS:
            finish()
            return
        opcode = int.from_bytes(cpu.mem_read(address, 2), "big")
        if opcode & 0xf000 == 0xa000:
            if opcode in (0xa029, 0xa02a, 0xa049, 0xa04a, 0xa069, 0xa06a):
                cpu.reg_write(d0, 0)
            elif self.credit_lines is not None and opcode in (0xa893, 0xa894):
                y, x = self.word(sp), self.word(sp + 2)
                self.pen = [x, y] if opcode == 0xa893 else [self.pen[0] + x, self.pen[1] + y]
                cpu.reg_write(a7, sp + 4)
            elif self.credit_lines is not None and opcode == 0xa898:
                cpu.mem_write(self.long(sp), struct.pack(">2h", self.pen[1], self.pen[0]))
                cpu.reg_write(a7, sp + 4)
            elif self.credit_lines is not None and opcode in (0xa8a8, 0xa8a9):
                dy, dx, pointer = self.word(sp), self.word(sp + 2), self.long(sp + 4)
                top, left, bottom, right = struct.unpack(">4h", cpu.mem_read(pointer, 8))
                if opcode == 0xa8a9:
                    bottom, right = bottom - dy, right - dx
                else:
                    bottom, right = bottom + dy, right + dx
                cpu.mem_write(pointer, struct.pack(">4h", top + dy, left + dx, bottom, right))
                cpu.reg_write(a7, sp + 8)
            else:
                raise ValueError(f"Unsupported recorded-game Toolbox trap {opcode:#x}")
            cpu.reg_write(pc, address + 2)
        elif address < 0x10000:
            raise ValueError("Invalid recorded-game code pointer")

    def credit_text(self, sp):
        pointer = self.long(sp + 4)
        raw = bytearray()
        while self.cpu.mem_read(pointer, 1)[0] and len(raw) < 2048:
            raw.extend(self.cpu.mem_read(pointer, 1))
            pointer += 1
        top, left, bottom, right = struct.unpack(">4h", self.cpu.mem_read(self.long(sp + 12), 8))
        vertical, horizontal = struct.unpack(">2h", self.cpu.mem_read(self.long(sp + 16), 4))
        lines = raw.decode("mac_roman").rstrip("\r").split("\r")
        height = len(lines) * self.font.height
        y = top if vertical == -1 else bottom - height if vertical == 0 else top + (bottom - top) // 2 - height // 2
        for line in lines:
            width = self.font.text(line).width
            available = right - left - 2
            x = left + 1 + max(0, (available - width) // 2 if horizontal == 1 else
                               available - width if horizontal == 255 else 0)
            baseline = y + self.font.height - 4
            self.credit_lines.append([line, x, baseline - self.font.ascent])
            self.pen = [x + width + 5, baseline]
            y += self.font.height

    def demo(self, progress):
        recording = RecordedGame.read(self.banks["Prince"]["RECG"][250]["data"])
        if recording.level != 1 or recording.last_frame > 5000:
            raise ValueError("Unsupported attract-mode recording")
        level = self.banks["Prince"]["LEVL"][2000]["data"]
        start_room = struct.unpack_from(">H", level, 0x2198)[0]
        self.write_long(-0x5014, self.long(self.resource("LEVL", 2000)))
        for offset, value in ((-0x4fd2, 1), (-0x4f92, 1), (-0x4f98, 3), (-0x4fee, 1),
                              (-0x4ffe, 1), (-0x43b6, 3), (-0x43a0, 250)):
            self.write_word(offset, value)
        for offset, kind, bank in ((-0x3472, "FRAM", "Kid"), (-0x3476, "AFRM", "Kid"),
                                   (-0x347a, "FRAM", "Guard"), (-0x347e, "AFRM", "Guard")):
            self.write_long(offset, self.resource(kind, 750 if bank == "Guard" else 25001, bank))
        for index, bank in ((2, "Kid"), (3, "Guard")):
            first, count = struct.unpack(">2H", next(iter(self.banks[bank]["SHPL"].values()))["data"])
            table = bytearray(8 + (count + 1) * 10)
            for i in range(count):
                struct.pack_into(">I", table, 8 + (i + 1) * 10 - 4, self.resource("SHAP", first + i, bank))
            self.write_long(-0x4a98 + index * 4, self.allocate(table))
        self.write_long(-0x1f58, self.SECT_RECT)
        self.cpu.mem_write(self.A5 - 0x4fec, struct.pack(">4h", 0, 0, 384, 510))
        # Relocate the original level-specific callback table in initialized DATA.
        for offset in range(-0x46f8, -0x46c0, 4):
            value = self.long(self.A5 + offset)
            if 0 < value < 0x3000:
                self.write_long(offset, value + self.A5)
        self.call(5, 0x0004, struct.pack(">h", start_room))
        self.call(4, 0x66ae)
        self.call(2, 0x5cf4)
        self.write_word(-0x5056, 10)
        self.cpu.mem_write(self.A5 - 0x50d2, bytes(self.cpu.mem_read(self.A5 - 0x5056, 62)))
        self.write_word(-0x4fc2, start_room)
        self.call(3, 0x1ab0)
        self.call(6, 0x2b7e)
        self.call(5, 0x638a)
        frames = []
        for index in range(recording.last_frame + 1):
            self.sounds.clear()
            ticks = 6 if self.word(self.A5 - 0x50b8) == 1 else 5
            self.write_word(-0x4fee, 1)
            self.write_word(-0x349a, index)
            self.call(2, 0x68c0)
            self.call(2, 0x6224)
            room = self.word(self.A5 - 0x4fc4)
            if room != self.word(self.A5 - 0x4fc2):
                self.write_word(-0x4fc2, room)
                self.call(3, 0x1ab0)
                self.call(6, 0x2b7e)
            actors = [list(struct.unpack(">31h", self.cpu.mem_read(self.A5 + offset, 62)))
                      for offset in (*range(-0x5208, -0x50d2, 62), -0x50d2)]
            frames.append({"ticks": ticks, "room": room, "actors": actors, "sounds": self.sounds.copy()})
            if index % 100 == 0:
                progress(f"Recovering the recorded demo: {index}/{recording.last_frame + 1} frames...")
        if frames[-1]["actors"][5][15] != 0 or frames[-1]["room"] != 10:
            raise ValueError("The recorded demo did not reach its original ending")
        return frames

    def credits(self):
        self.credit_lines = []
        self.cpu.mem_write(self.A5 - 0x1dfc, struct.pack(">4h", 0, 0, 384, 510))
        starts = struct.unpack(">4H", self.cpu.mem_read(self.A5 - 0x55ba, 8))
        ends = struct.unpack(">4H", self.cpu.mem_read(self.A5 - 0x55b2, 8))
        pages = []
        for first, last in zip(starts, ends):
            if any(i not in self.banks["Prince"]["TEXT"] for i in range(first, last + 1)):
                raise ValueError("Missing original credits text")
            self.credit_lines = []
            self.call(2, 0x2d20, struct.pack(">2H", first, last))
            pages.append(self.credit_lines)
        self.credit_lines = None
        code = self.resources["CODE"][2]["data"]
        if (code[0x2c36:0x2c38] != b"\x3f\x3c" or code[0x2c0c] != 0x70
                or code[0x0774:0x0776] != b"\x2f\x3c" or code[0x2b88:0x2b8a] != b"\x3f\x3c"):
            raise ValueError("Unsupported credits coordinator")
        return {"pages": pages, "hold_ticks": struct.unpack_from(">H", code, 0x2c38)[0],
                "dissolve_ticks": code[0x2c0d],
                "fade_ticks": fade_ticks(struct.unpack_from(">I", code, 0x0776)[0]),
                "song": struct.unpack_from(">H", code, 0x2b8a)[0]}


def extract_attract(program, resources, output, progress=lambda _text: None):
    banks = {name: resources[f"{name}.rsrc"] for name in ("Prince", "Kid", "Guard", "Rooftops")}
    simulation = RecordedSimulation(program, banks)
    frames = simulation.demo(progress)
    credits = simulation.credits()
    recordings = {str(key): {"level": game.level, "last_frame": game.last_frame}
                  for key, resource in simulation.banks["Prince"]["RECG"].items()
                  for game in (RecordedGame.read(resource["data"]),)}
    result = {"schema": 1, "recording": 250, "recordings": recordings,
              "frames": frames, "credits": credits}
    Path(output, "attract.json").write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="ascii")
    return result


def extract_credits_music(image, output):
    import mido

    directory = Path(output) / "audio"
    data = mohawk_resources(get_data_fork(image, "MIDISnd.dat"))["MIDI"][10019]
    midi_path = directory / "credits-10019.mid"
    midi_path.write_bytes(data)
    duration = render_midi(directory, midi_path.name, "credits-10019.wav")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["cues"]["10019"] = {
        "file": "credits-10019.wav", "kind": "midi", "resource_id": 10019,
        "priority": 0, "mode": 2, "source_archive": "MIDISnd.dat",
        "duration": mido.MidiFile(file=io.BytesIO(data)).length, "playback_duration": duration,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")
    (directory / "playback.mid").unlink(missing_ok=True)
