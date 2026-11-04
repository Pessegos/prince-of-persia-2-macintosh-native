"""Compare the five horse SCRPs with original CODE 16 runScript.

Object/resource handles, virtual sound/notify sinks and HLock/HUnlock are
supplied. This does not execute native drawing, audio, maintain or FrameAdv.
TransFunc5 and GetHorsePtInPlane are separate bounded original calls.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from pop2.intro import ScriptAnimation
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeHorseScene(NativeRules):
    RANGES = {16: ((0x08ee, 0x0ada),), 15: ((0x64ee, 0x655a),),
              3: ((0x4572, 0x45f0),)}
    SUPPLIED = {(15, 0x042a): 'flip_horses', (17, 0x4fe4): 'copy',
                (15, 0x26fc): 'palette'}
    OBJECT, HANDLE, SCRIPT, VTABLE, SINK = 0xb0000, 0xb1000, 0xc0000, 0xd0000, 0xe0000

    def dispatch(self, cpu, address, size, user):
        if address == self.SINK:
            sp = cpu.reg_read(self.registers['a7'])
            destination, _object, command = struct.unpack('>3I', cpu.mem_read(sp, 12))
            opcode, _length, argument = struct.unpack('>BBh', cpu.mem_read(command, 4))
            self.events.append((opcode, argument))
            cpu.reg_write(self.registers['a7'], sp + 12)
            cpu.reg_write(self.registers['pc'], destination)
        elif (self.address(16, 0x08ee) <= address <= self.address(16, 0x0ada)
              and bytes(cpu.mem_read(address, 2)) in (b'\xa0\x29', b'\xa0\x2a')):
            cpu.reg_write(self.registers['pc'], address + 2)
        else:
            super().dispatch(cpu, address, size, user)

    def start_script(self, data, layers):
        self.cpu.mem_write(self.OBJECT, bytes(0x300))
        self.cpu.mem_write(self.OBJECT, struct.pack('>I', self.VTABLE))
        self.cpu.mem_write(self.OBJECT + 8, struct.pack('>h', 1))
        self.cpu.mem_write(self.OBJECT + 12, struct.pack('>h', 3))
        self.cpu.mem_write(self.OBJECT + 18, struct.pack('>I', self.HANDLE))
        self.cpu.mem_write(self.OBJECT + 34, struct.pack('>I', layers))
        for layer in range(layers):
            self.cpu.mem_write(self.OBJECT + 38 + layer * 28 + 24, struct.pack('>I', 16))
        self.cpu.mem_write(self.VTABLE + 0x40, struct.pack('>I', self.SINK))
        self.cpu.mem_write(self.VTABLE + 0x4c, struct.pack('>I', self.SINK))
        self.cpu.mem_write(self.HANDLE, struct.pack('>I', self.SCRIPT))
        self.cpu.mem_write(self.SCRIPT, data)
        self.events = []

    def step_script(self, layers):
        self.events = []
        self.call(16, 0x08ee, arg_bytes=struct.pack('>IhI', self.OBJECT, 0, 1), stop=(16, 0x0ada))
        running = struct.unpack('>h', self.cpu.mem_read(self.OBJECT + 8, 2))[0]
        interval = struct.unpack('>h', self.cpu.mem_read(self.OBJECT + 12, 2))[0]
        result = []
        for layer in range(layers):
            x, y, shape, flags = struct.unpack('>4i', self.cpu.mem_read(self.OBJECT + 50 + layer * 28, 16))
            result.append([shape, x, y, flags])
        return bool(running), interval, result


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    resources = parse_resource_fork((directory / 'TempleNIS.rsrc.bin').read_bytes())
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    level = prince['LEVL'][2008]['data']
    if struct.unpack_from('>3h', level, 0x2186)[::2] != (4, 9):
        raise ValueError('Expected original level-nine ruins header')
    machine = NativeHorseScene(program)
    digest, scripts = hashlib.sha256(), []
    for index in range(11, 16):
        header = struct.unpack('>9h', resources['ANI '][25000 + index]['data'])
        layers, script_id = header[4:6]
        data = resources['SCRP'][script_id]['data']
        machine.reset(level)
        machine.start_script(data, layers)
        model = ScriptAnimation(data, layers)
        frames = ticks = 0
        while not model.done:
            model.step()
            running, interval, actual = machine.step_script(layers)
            if (running != (not model.done) or interval != model.interval
                    or actual != model.layers or machine.events != model.events):
                raise AssertionError((index, frames, running, interval, machine.events))
            digest.update(struct.pack('>3h', index, frames, interval))
            digest.update(json.dumps([actual, machine.events, running]).encode('ascii'))
            model.events.clear()
            if running:
                frames += 1
                ticks += interval
        scripts.append(dict(ani=25000 + index, frames=frames, ticks=ticks, running_at_end=False))
    callbacks = []
    for frame in (0, 1, 76, 77):
        for cue in (0, 96, 97, 98):
            machine.reset(level)
            machine.put_word(-0x1f6e, cue)
            result = machine.call(15, 0x64ee, args=(frame,))
            if result != (65535 if cue >= 97 else 0):
                raise AssertionError((frame, cue, result))
            callbacks.append(dict(frame=frame, cue=cue, result=-1 if result else 0))
    arrival_level = prince['LEVL'][2009]['data']
    if struct.unpack_from('>3h', arrival_level, 0x2186)[::2] != (2, 10):
        raise ValueError('Expected original level-ten temple header')
    machine.reset(arrival_level)
    machine.put_word(-0x5000, -1)
    # This helper returns a pointer, while NativeRules.call returns D0's
    # low word. Read the complete register to inspect the native point.
    machine.call(3, 0x4572, args=(22, 1))
    point = machine.cpu.reg_read(machine.registers['d0'])
    y, x = struct.unpack('>2h', machine.cpu.mem_read(point, 4))
    if (x, y) != (74, 198):
        raise AssertionError((x, y))
    return dict(scripts=scripts, callback_cases=len(callbacks), callbacks=callbacks,
                arrival_point=[x, y], mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(), outputs_sha256=digest.hexdigest(),
                supplied=['Original SCRPs/ANI headers; constructed animation object, vtable and handles',
                          'HLock/HUnlock no-ops; sound/notify virtual methods record opcode and argument',
                          'TransFunc5 flip/copy/palette sinks; supplied frame and music marker globals',
                          'GetHorsePtInPlane: original level-ten header and plane1/global -1'],
                exclusions=['Native drawing/pixels, sound synthesis, Resource Manager and maintain/event timing',
                            'Callback return is checked separately, not a full PlayTheAnimation execution',
                            'No native input/FrameAdv replay; existing scene regression covers the column leap'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
