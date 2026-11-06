"""Execute the shadow's AutoCtrl 10:2850 and the opponents' bow 6:4ffa, 4:07fe.

Real bodies: 10:2850 with AddCharX 4:2bae, and AutoCtrl's armed branch 6:4ffa-501a
with 4:07fe. Sinks that record their calls: DoStepFwd 6:1276 (it writes a
supplied selected SEQS to -502e, as a step does), DoRunJump 6:1c14, Catch 4:37ca,
DoJumpHang 6:1b7e (supplied result), the climb 6:1998, GetCharEdges 4:5cbc,
5:19f8, the palette 3:508a, the merge 10:27d8, the song 5:4d58 and JumpSeq
6:0006. GetBarrDist 4:5eae returns a supplied distance. Compared with
`temple_shadow.auto_ctrl` and `CombatEncounter._bow_guard`. Single decisions: no
AnimChar, no terrain and no whole flight of the shadow.
"""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.combat import CombatEncounter
from pop2.mac_resources import parse_resource_fork
from pop2.temple_shadow import auto_ctrl
from tools.probe_level7_rules import NativeRules

SINKS = {(6, 0x1276): 'step', (6, 0x1c14): 'run_jump', (4, 0x37ca): 'catch', (6, 0x1b7e): 'hang',
         (6, 0x1998): 'climb', (4, 0x5cbc): 'edges', (5, 0x19f8): 'redraw', (3, 0x508a): 'palette',
         (10, 0x27d8): 'merge', (5, 0x4d58): 'song', (6, 0x0006): 'jump_seq', (4, 0x5eae): 'distance',
         (4, 0x098c): 'engarde'}
FLARE_OFFSET = 0x914


class NativeShadow(NativeRules):
    RANGES = {4: ((0x07fe, 0x0832), (0x2bae, 0x2bcc)), 6: ((0x4ffa, 0x5020),),
              10: ((0x2850, 0x2a60),)}
    SUPPLIED = {}
    step_result = 0
    hang_result = 0
    distance = 0

    def dispatch(self, cpu, address, size, user):
        key = divmod(address - self.CODE_BASE, 0x10000)
        name = SINKS.get(key)
        if name and address != self.stop_at:
            stack = cpu.reg_read(self.registers['a7'])
            argument = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            self.events.append((name, argument))
            result = self.hang_result if name == 'hang' else self.distance if name == 'distance' else 0
            if name == 'step':
                self.put_word(-0x502e, self.step_result)
            cpu.reg_write(self.registers['d0'], result & 0xffff)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            cpu.reg_write(self.registers['a7'], stack + 4)
            return
        super().dispatch(cpu, address, size, user)


def shadow_cases(machine, level):
    totals, bad = Counter(), []
    poses = (15, 1, 14, 49, 56, 57, 44, 102, 103, 106, 107, 91, 153, 154, 185, 200)
    for pose, facing, column, mode, selected, step_to, x, kid_x, kid_facing, hang in product(
            poses, (-1, 0), (0, 5, 6, 7, 8, 9), (0, 13), (0, 232), (0, 44), (300, 316), (320, 338),
            (-1, 0), (0, 1)):
        machine.reset(level)
        machine.events = []
        machine.step_result, machine.hang_result = step_to, hang
        for offset, value in ((-0x504c, pose), (-0x5054, facing), (-0x504a, column), (-0x5022, mode),
                              (-0x502e, selected), (-0x5052, x), (-0x50ce, kid_x), (-0x50d0, kid_facing),
                              (-0x5050, 500)):
            machine.put_word(offset, value)
        machine.call(10, 0x2850)
        calls = [event for event in machine.events if event[0] != 'edges' and event[0] != 'redraw']
        flare = struct.unpack_from('>H', machine.level_bytes(FLARE_OFFSET + 2), FLARE_OFFSET)[0] == 0x85
        native_x = machine.word(-0x5052)

        state = SimpleNamespace(action=pose, facing=int(facing == 0), sequence_mode=mode,
                                selected_sequence_id=selected, target_x=x - 207, current_x=x - 207)
        steps = []

        def step(distance):
            steps.append(('step', distance))
            return step_to

        jumps = []
        sequence, event = auto_ctrl(state, column, kid_x, int(kid_facing == 0), step,
                                    lambda: jumps.append(('run_jump', 4)))
        port = [*steps, *jumps]
        if event == 'turn':
            port.append(('song', 251))
        elif event == 'catch':
            port.append(('catch', None))
        elif event == 'hang':
            port.append(('hang', None))
            if not hang:
                port.append(('climb', None))
        elif event == 'palette':
            port.append(('palette', 4077))
        elif event == 'merge':
            port.append(('merge', None))
        if sequence is not None:
            port.append(('jump_seq', sequence))
        native_calls = [(name, None if name in ('catch', 'hang', 'climb', 'merge') else value)
                        for name, value in calls]
        totals[event or 'plain'] += 1
        if (native_calls != port or flare != (event == 'flare')
                or native_x != state.target_x + 207):
            bad.append(dict(pose=pose, facing=facing, column=column, mode=mode, selected=selected,
                            step_to=step_to, x=x, kid_x=kid_x, kid_facing=kid_facing, hang=hang,
                            native=native_calls, port=port, native_x=native_x,
                            port_x=state.target_x + 207, flare=flare))
    return totals, bad


def bow_cases(machine, level):
    totals, bad = Counter(), []
    for mode, byte, selected, distance, barrier, facing in product(
            (0, 13), (0, 1), (86, 110), (-5, 0, 40, 67, 68, 90), (0, 1, 2), (-1, 0)):
        supplied = bytearray(level)
        supplied[0x2196] = byte
        machine.reset(supplied)
        machine.events = []
        machine.distance = distance
        for offset, value in ((-0x509e, mode), (-0x502e, selected), (-0x3576, barrier),
                              (-0x5054, facing), (-0x5052, 400), (-0x503c, 1)):
            machine.put_word(offset, value)
        machine.call(6, 0x4ffa, stop=(6, 0x501e))
        native = ('jump_seq', 110) in machine.events
        native_x = machine.word(-0x5052)

        state = SimpleNamespace(action=150, facing=int(facing == 0), target_x=193, current_x=193)
        guard = SimpleNamespace(state=state, room=0, row=0, selected_sequence=selected)
        chosen = []
        port_self = SimpleNamespace(
            level=bytes(supplied), guard_art=None, terrain=None)
        boundary = SimpleNamespace(clearance=distance, barrier_type=barrier)
        port_self.guard_art = SimpleNamespace(frames={1: None}, bounds=lambda *_: None)
        port_self.terrain = SimpleNamespace(step_boundary=lambda *_: boundary)
        if mode == 13 and selected != 110:
            from unittest.mock import patch

            with patch('pop2.combat.select_sequence', lambda _guard, sequence: chosen.append(sequence)):
                CombatEncounter._bow_guard(port_self, guard)
        port = 110 in chosen
        totals['bows' if native else 'keeps'] += 1
        if native != port or (mode == 13 and native_x != state.target_x + 207):
            bad.append(dict(mode=mode, byte=byte, selected=selected, distance=distance, barrier=barrier,
                            facing=facing, native=native, port=port, native_x=native_x,
                            port_x=state.target_x + 207))
    return totals, bad


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    machine = NativeShadow(parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes()))
    level = bytes(parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2012]['data'])
    report = {}
    for name, (totals, bad) in (('shadow', shadow_cases(machine, level)), ('bow', bow_cases(machine, level))):
        report[name] = dict(cases=dict(totals), mismatches=len(bad), examples=bad[:6])
    report['supplied'] = __doc__
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'supplied'})[:2600])


if __name__ == '__main__':
    main()
