"""Asset-free checks that each bounded native call must reach its own stop."""

import unittest
from unittest.mock import Mock

from tools.probe_level7_rules import NativeRules


class NativeCallGuardTests(unittest.TestCase):
    def machine(self):
        machine = NativeRules.__new__(NativeRules)
        machine.cpu = Mock()
        machine.cpu.reg_read.return_value = 0x1234
        machine.registers = dict(a7=1, pc=2, d0=3)
        machine.reached = True
        machine.failure = None
        return machine

    def test_previous_success_cannot_hide_instruction_limit_without_a_new_stop(self):
        machine = self.machine()
        with self.assertRaisesRegex(RuntimeError, 'did not reach stop'):
            machine.call(10, 0x1d5c)
        self.assertFalse(machine.reached)

    def test_each_success_requires_a_new_stop_and_returns_the_word(self):
        machine = self.machine()
        machine.cpu.emu_start.side_effect = lambda *a, **k: setattr(machine, 'reached', True)
        self.assertEqual(machine.call(10, 0x1d5c), 0x1234)
        machine.cpu.emu_start.side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'did not reach stop'):
            machine.call(10, 0x1d5c)

    def test_old_failure_is_reset_but_new_failure_is_not_ignored(self):
        machine = self.machine()
        machine.failure = 'old failure'
        machine.cpu.emu_start.side_effect = lambda *a, **k: setattr(machine, 'reached', True)
        self.assertEqual(machine.call(10, 0x1d5c), 0x1234)
        machine.cpu.emu_start.side_effect = lambda *a, **k: setattr(machine, 'failure', 'new failure')
        with self.assertRaisesRegex(RuntimeError, 'new failure'):
            machine.call(10, 0x1d5c)


if __name__ == '__main__':
    unittest.main()
