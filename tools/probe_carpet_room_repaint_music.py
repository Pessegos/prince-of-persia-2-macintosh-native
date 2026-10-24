"""Check native dirty CUST foreground and ambient admission in the carpet room."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from PIL import Image, ImageChops

from pop2.caverns import (
    cavern_command_sprite, cavern_room, clipped_sprite, custom_foreground_records, room_assets,
)
from pop2.mac_resources import parse_resource_fork
from tools.extract_caverns import CavernRecovery, recover_room
from tools.probe_level7_rules import NativeRules


class NativeCarpetAmbient(NativeRules):
    RANGES = {5: ((0x4e0c, 0x4e42), (0x4e76, 0x4e9a), (0x5388, 0x56c8)),
              8: ((0x0d50, 0x0d5a),)}
    SUPPLIED = {}
    RECORD = 0xb0000

    def reset(self, level):
        super().reset(level)
        self.playing, self.events = False, []

    def dispatch(self, cpu, address, size, user):
        key = divmod(address - self.CODE_BASE, 0x10000)
        if key in ((5, 0x52c8), (5, 0x4d58), (6, 0x2392), (6, 0x3d28)):
            stack = cpu.reg_read(self.registers['a7'])
            value = 0
            if key == (5, 0x52c8):
                cue = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.events.append(('playing', cue))
                value = int(self.playing and cue == self.current_cue)
            elif key == (5, 0x4d58):
                self.events.append(('song', struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
            elif key == (6, 0x2392):
                self.events.append(('fighting',))
            else:
                self.events.append(('opponents',))
            cpu.reg_write(self.registers['d0'], value)
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    executable, caverns, prince = ((directory / name).read_bytes() for name in
                                  ('Prince of Persia 2.bin', 'Caverns.rsrc.bin', 'Prince.rsrc.bin'))
    resources = parse_resource_fork(executable)
    level = parse_resource_fork(prince)['LEVL'][2004]['data']
    machine = NativeCarpetAmbient(resources)
    digest, outcomes = hashlib.sha256(), Counter()
    comparisons = 0
    for cue, room, playing, enabled, alive, pending in product(
            (114, 115), (1, 3, 4), (False, True), (0, 1), (-1, 0), (0, 1)):
        machine.reset(level)
        machine.playing, machine.current_cue = playing, cue
        for offset, value in ((-0x4fc2, room), (-0x50bc, room), (-0x503a, alive),
                              (-0x50b6, pending), (-0x524a, 0)):
            machine.put_word(offset, value)
        record = struct.pack('>3h', enabled, 0, cue)
        machine.cpu.mem_write(machine.RECORD, record)
        before = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        actual = machine.call(5, 0x550c, arg_bytes=struct.pack('>I', machine.RECORD))
        expected = int(enabled and alive < 0 and not pending and not playing)
        if (actual != expected or machine.services or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.RECORD, 6)) != record
                or bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data))) != before):
            raise AssertionError(dict(inputs=(cue, room, playing, enabled, alive, pending),
                                      actual=actual, expected=expected, events=machine.events))
        comparisons += 1
        outcomes[str(actual)] += 1
        digest.update(struct.pack('>7h', cue, room, playing, enabled, alive, pending, actual))
        digest.update(json.dumps(machine.events).encode('ascii'))
    machine.reset(level)
    machine.call(8, 0x0d50)
    if machine.events != [('song', 114)]:
        raise AssertionError('Room enter hook did not request exactly114')

    # Run the original foreground drawer with its per-dirty-cell clip. The
    # static export tagged all CUST front pieces with clean-cut caller (9,0).
    _program, scenery, palette, shapes = room_assets(5, 2)
    custom = custom_foreground_records(scenery, 2)
    art = cavern_room(2, level_number=5)
    dirty_cases, dirty_shapes = 0, Counter()
    with CavernRecovery(executable, caverns, prince) as recovery:
        for row, column in product(range(3), range(10)):
            commands = recover_room(executable, caverns, level, 2, prince, _machine=recovery,
                                    cell_redraw=True, only={(row, column, 1)})['commands']
            native = Image.new('L', (510, 365))
            for command in commands:
                if command[0] != 'front' or (command[1], command[2], command[3], command[4]) not in custom:
                    continue
                decoded = clipped_sprite(cavern_command_sprite(command, scenery, palette, shapes), command)
                if decoded is not None:
                    sprite, point = decoded
                    mask = Image.new('L', native.size)
                    mask.paste(sprite.getchannel('A'), point)
                    native = ImageChops.lighter(native, mask)
                    dirty_shapes[str(command[1])] += 1
            rect = (column * 51, row * 120 + 5, (column + 1) * 51, (row + 1) * 120 + 5)
            actual = art.custom_occlusion.crop(rect)
            expected = native.crop(rect)
            if ImageChops.difference(actual, expected).getbbox():
                raise AssertionError(dict(cell=(column, row), native_commands=commands))
            digest.update(expected.tobytes())
            dirty_cases += 1
    return dict(ambient_comparisons=comparisons, ambient_results=dict(outcomes),
                entry_song_requests=machine.events, dirty_foreground_comparisons=dirty_cases,
                dirty_custom_shapes=dict(dirty_shapes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256=hashlib.sha256(level).hexdigest(), outputs_sha256=digest.hexdigest(),
                supplied=['5:52c8 sound status;6:2392 no combat;6:3d28 no opponent obstruction;5:4d58 song sink',
                          'Prepared enabled/group/current-cue record, ALIVE/pending/view fields',
                          'CavernRecovery drawing/shape services; supplied dirty-cell clips, shared SHAP decoder'],
                scope='Actual5:550c ambient admission,5:5478 blockers and8:0d50 entry request; '
                      'actual3:2598/2324 dirty CUST foreground scheduling with recorded shape/clip commands. '
                      'Not full audio playback, QuickDraw rasterization, FrameAdv or whole-game visual parity.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
