"""Synthetic checks for the research initializer and native stack boundary."""

import struct
from types import SimpleNamespace
import unittest

from tools.probe_level7_initialization import initialization_reference
from tools.probe_level7_rules import NativeRules


def inputs(actor=7, alive=-1, mode=0):
    record = [0] * 19
    record[4], record[5], record[12], record[14] = 999, 33, 5, mode
    state = dict(actor=actor, row=1, column=4, alive=alive,
                 x=600, y=333, facing=0, armed=9, special=4)
    return record, state


class InitializationReferenceTests(unittest.TestCase):
    def test_head_types_align_and_restart_without_a_sound(self):
        for actor in (7, 8):
            record, state = inputs(actor=actor, mode=3)
            words, working, sounds = initialization_reference(record, state)
            self.assertEqual((working['x'], working['y'], working['facing']), (458, 333, -1))
            self.assertEqual((words[4], words[5], words[14], working['armed']), (130, 0, 0, 0))
            self.assertEqual(working['special'], 4)
            self.assertEqual(sounds, [])

    def test_dormant_living_snake_uses_170_and_negative_mode(self):
        for mode in (-1, 0):
            record, state = inputs(actor=11, mode=mode)
            words, working, sounds = initialization_reference(record, state)
            self.assertEqual((words[4], words[5], words[14]), (170, 0, -1))
            self.assertEqual((working['x'], working['facing'], working['special']), (600, 0, 4))
            self.assertEqual((working['armed'], sounds), (1, [128]))

    def test_active_living_snake_retains_mode_and_selects_175(self):
        for mode in (1, 3):
            record, state = inputs(actor=11, mode=mode)
            words, working, sounds = initialization_reference(record, state)
            self.assertEqual((words[4], words[5], words[14]), (175, 0, mode))
            self.assertEqual((working['special'], working['armed'], sounds), (6, 1, [128]))

    def test_nonnegative_native_alive_preserves_snake_record(self):
        for alive in (0, 1):
            record, state = inputs(actor=11, alive=alive, mode=3)
            words, working, sounds = initialization_reference(record, state)
            self.assertEqual(words, record)
            self.assertEqual(working, dict(state, armed=0))
            self.assertEqual(sounds, [])

    def test_kind_zero_fallback_changes_type_and_uses_head_floor(self):
        record, state = inputs(actor=11)
        record[12] = 0
        words, working, sounds = initialization_reference(record, state)
        self.assertEqual((words[12], working['actor'], working['y']), (5, 7, 193))
        self.assertEqual(words[4], 130)
        self.assertEqual(sounds, [])

    def test_source_objects_are_not_modified(self):
        record, state = inputs(mode=3)
        original_record, original_state = record[:], dict(state)
        initialization_reference(record, state)
        self.assertEqual((record, state), (original_record, original_state))


class ProbeCallStackTests(unittest.TestCase):
    def test_word_and_pointer_stack_arguments_keep_their_width(self):
        machine = NativeRules.__new__(NativeRules)
        writes = []
        machine.registers = dict(a7=1, d0=2, pc=3)
        machine.failure = None
        machine.reached = False
        machine.cpu = SimpleNamespace(
            mem_write=lambda address, data: writes.append((address, bytes(data))),
            reg_write=lambda _register, _value: None,
            reg_read=lambda _register: 42,
            emu_start=lambda *args, **kwargs: setattr(machine, 'reached', True))
        self.assertEqual(machine.call(7, 0x0574, (1, -1)), 42)
        self.assertEqual(writes[-1], (machine.STACK, struct.pack('>IHH', machine.END, 1, 65535)))
        pointer = struct.pack('>I', 0xa1234)
        self.assertEqual(machine.call(7, 0x0574, arg_bytes=pointer), 42)
        self.assertEqual(writes[-1], (machine.STACK, struct.pack('>I', machine.END) + pointer))

    def test_mixed_argument_formats_are_rejected(self):
        machine = NativeRules.__new__(NativeRules)
        with self.assertRaisesRegex(ValueError, 'either'):
            machine.call(7, 0x0574, (1,), arg_bytes=b'\0\0')


if __name__ == '__main__':
    unittest.main()
