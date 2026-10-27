"""Audit stone-gate source loop metadata and original cue arbitration.

Executes bounded native header/block/reset/admission bodies. Audio start/stop
services are supplied sinks; this is not a Sound Manager or emulator recording.
Original audio bytes and native reports stay local.
"""

import argparse
from pathlib import Path
import hashlib
import json
import struct

from unicorn.m68k_const import UC_M68K_REG_A6

from pop2.audio_formats import mohawk_resources
from pop2.mac_resources import parse_resource_fork
from tools.extract_audio import audio_tables
from tools.probe_level7_rules import NativeRules


class GateAudioNative(NativeRules):
    RANGES = {
        5: ((0x4D84, 0x4DEA), (0x5122, 0x5156), (0x5252, 0x5378)),
        16: ((0x25FE, 0x264A),),
        20: ((0x3B2A, 0x3B9A), (0x37A8, 0x396C), (0x467C, 0x46C2)),
    }
    SUPPLIED = {}
    OBJ, PAYLOAD, FRAME = 0xB0000, 0xC0000, 0xD0000

    def reset(self, level=b""):
        super().reset(level)
        self.events = []
        self.put_word(-0x439E, -1)
        self.put_word(-0x439A, -1)
        self.put_word(-0x4FA6, 0)
        self.put_word(-0x504E, 0)
        self.put_word(-0x1F7A, 0)
        self.put_word(-0x1F7C, 0)
        self.put_word(-0x1F7E, 400)
        self.put_word(-0x409C - 8, 0)
        for cue in range(301):
            self.put_word(-0x409C + cue * 8, cue + 1)
        self.cpu.mem_write(self.OBJ, bytes(2048))

    def dispatch(self, cpu, address, size, user):
        key = divmod(address - self.CODE_BASE, 0x10000)
        if key in ((19, 0x2FF0), (16, 0x2200), (16, 0x23CC)):
            stack = cpu.reg_read(self.registers["a7"])
            if key == (19, 0x2FF0):
                dest, value, count = struct.unpack(">3I", cpu.mem_read(stack + 4, 12))
                cpu.mem_write(dest, bytes([value & 255]) * count)
                cpu.reg_write(self.registers["d0"], dest)
            else:
                handle = struct.unpack(">h", cpu.mem_read(stack + 4, 2))[0]
                self.events.append(
                    ("stop" if key[1] == 0x2200 else "start", handle - 1)
                )
                if key[1] == 0x23CC:
                    self.put_word(-0x1F7A, handle)
                elif not handle or self.word(-0x1F7A) == handle:
                    self.put_word(-0x1F7A, 0)
                cpu.reg_write(self.registers["d0"], 0)
            cpu.reg_write(self.registers["a7"], stack + 4)
            cpu.reg_write(
                self.registers["pc"], struct.unpack(">I", cpu.mem_read(stack, 4))[0]
            )
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    source = Path(source)
    program_bytes = (source / "resource_forks/Prince of Persia 2.bin").read_bytes()
    program = parse_resource_fork(program_bytes)
    archive = mohawk_resources((source / "data_forks/DigiSnd.dat.bin").read_bytes())[
        "snd "
    ]
    tables = audio_tables(program)["cues"]
    machine = GateAudioNative(program)
    loop_report = {}
    for cue in (17, 18, 20, 27, 60, 61):
        machine.reset()
        payload = archive[9752 + cue]
        machine.cpu.mem_write(machine.PAYLOAD, payload)
        machine.cpu.reg_write(UC_M68K_REG_A6, machine.FRAME)
        chunk = machine.PAYLOAD + payload.find(b"Data")
        machine.cpu.mem_write(machine.FRAME - 0x68, struct.pack(">I", chunk))
        machine.cpu.mem_write(machine.FRAME - 0x6C, struct.pack(">I", machine.OBJ))
        machine.call(20, 0x3B2A, stop=(20, 0x3B9A))
        obj = bytes(machine.cpu.mem_read(machine.OBJ, 2048))
        rate = struct.unpack_from(">H", obj, 0x72)[0]
        frames = struct.unpack_from(">I", obj, 0x74)[0]
        count = struct.unpack_from(">H", obj, 0x7C)[0]
        start, end = struct.unpack_from(">2I", obj, 0x7E)
        fields = struct.unpack(
            ">HIBBHHII", payload[payload.find(b"Data") + 8 : payload.find(b"Data") + 28]
        )
        assert (rate, frames, count, start, end) == (
            fields[0],
            fields[1],
            fields[5],
            fields[6],
            fields[7],
        )
        machine.cpu.mem_write(machine.OBJ + 0x2C, struct.pack(">I", machine.PAYLOAD))
        machine.call(20, 0x37A8, arg_bytes=struct.pack(">I", machine.OBJ))
        obj = bytes(machine.cpu.mem_read(machine.OBJ, 2048))
        n = struct.unpack_from(">H", obj, 0x8A)[0]
        blocks = []
        for index in range(n):
            p = 0x8C + index * 44
            a, b = struct.unpack_from(">2I", obj, p)
            flags = struct.unpack_from(">I", obj, p + 0x1C)[0]
            blocks.append(dict(start=a, length=b, end=a + b, flags=flags))
        if cue == 17:
            assert any(
                b["start"] == 5025 and b["end"] == 11520 and b["flags"] & 12 == 12
                for b in blocks
            )
            machine.call(20, 0x467C, arg_bytes=struct.pack(">I", machine.OBJ))
            loop_ptr = struct.unpack(">I", machine.cpu.mem_read(machine.OBJ + 0x4E, 4))[
                0
            ]
            repeats = struct.unpack(">i", machine.cpu.mem_read(loop_ptr + 0x20, 4))[0]
            assert repeats == -1
        else:
            assert not any(b["flags"] & 12 for b in blocks)
            repeats = 0
        loop_report[cue] = dict(
            rate=rate,
            frames=frames,
            loop_count_raw=count,
            loop_start=start,
            loop_end=end,
            native_blocks=blocks,
            repeat_count=repeats,
        )

    results = []
    for cue in sorted(map(int, tables)):
        for busy in (False, True):
            machine.reset()
            machine.put_word(-0x439A, 17)
            machine.put_word(-0x1F7A, 18 if busy else 0)
            actual = machine.call(5, 0x530A, (cue, 17))
            rule = tables["17"]
            expected = int(
                not busy
                or (cue != 17 and tables[str(cue)]["priority"] <= rule["priority"])
            )
            assert actual == expected, (cue, busy, actual, expected)
            results.append((cue, busy, actual))

    traces = {}
    for name, requests in [
        ("isolated", [17] * 50),
        ("bones", [17] * 5 + [61] + [17] * 10),
        ("rattle", [17] * 5 + [60] + [17] * 10),
        ("stop", [17] * 5 + [18]),
    ]:
        machine.reset()
        trace = []
        for tick, cue in enumerate(requests):
            if name == "bones" and tick == 10:
                # Supplied playback completion, not an emulated audio clock.
                machine.put_word(-0x1F7A, 0)
            machine.events = []
            machine.call(5, 0x4D84, (17,))
            if cue != 17:
                machine.call(5, 0x4D84, (cue,))
            pending = machine.word(-0x439E)
            machine.call(5, 0x5122, stop=(5, 0x5156))
            if machine.events:
                trace.append(
                    dict(
                        tick=tick,
                        requested=cue,
                        pending=pending,
                        events=machine.events.copy(),
                    )
                )
            # Playback status remains live until a supplied endpoint ends it.
        traces[name] = trace
    assert traces["isolated"] == [
        dict(tick=0, requested=17, pending=17, events=[("start", 17)])
    ]
    assert [t["pending"] for t in traces["bones"]] == [17, 61, 17]
    assert [t["pending"] for t in traces["rattle"]] == [17]

    return dict(
        sample_headers_and_native_blocks=loop_report,
        admission_cases=len(results),
        mismatches=0,
        traces=traces,
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        outputs_sha256=hashlib.sha256(
            json.dumps([loop_report, results, traces], sort_keys=True).encode()
        ).hexdigest(),
        supplied=[
            "wave object pointer/raw payload/fake resource handles and known initial channel state",
            "19:2ff0 memset equivalent",
            "16:2200 reset and16:23cc play sinks update supplied channel status",
            "bones trace marks the supplied effect complete at tick10",
        ],
        actual=[
            "20:3b2a header field loads",
            "20:37a8 calcBlocks",
            "20:467c resetLoop",
            "5:4d84 AddSound",
            "5:530a SetCueSnd",
            "5:52c8 PrinceSndOn",
            "16:25fe SoundItemOn",
            "5:5122 effect dispatch through5:5156",
        ],
        exclusions="No physical Sound Manager/emulator or full gate/frame loop. Playback completion timing supplied; native loop blocks and priority admission executed independently.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
