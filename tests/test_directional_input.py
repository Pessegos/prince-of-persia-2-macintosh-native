"""Production bank and ready selector against independent native-verified models."""

from itertools import product
import unittest

from pop2.mac_input import DirectionalInput, standing_input_request
from tools.reference_input_bank import InputBank
from tools.reference_input_routes import unarmed_route


class DirectionalBankTests(unittest.TestCase):
    def banks(self):
        return (InputBank(*directions, modifier)
                for directions in product((-1, 0, 1), repeat=4)
                for modifier in (-2, -1, 0, 1, 2))

    def test_production_sampling_matches_the_independent_native_verified_model(self):
        for reference in self.banks():
            runtime = DirectionalInput(*reference.words())
            for axes in product((-1, 0, 1), (-1, 0, 1), (-2, -1, 0)):
                self.assertEqual(runtime.sample(*axes).words(), reference.sample(*axes).words())
            self.assertEqual(runtime.clear_directions().words(), reference.clear_directions().words())
            for facing, inverted in product((False, True), repeat=2):
                self.assertEqual(runtime.remap(facing_right=facing, inverted=inverted).words(),
                                 reference.remap(facing_right=facing, inverted=inverted).words())

    def test_production_ready_priority_matches_the_independent_native_router(self):
        names = {'turn': 'turn', 'run': 'run', 'up': 'up', 'down': 'down',
                 'forward_jump': 'forward_jump', 'step': 'step', 'draw': 'draw', 'sequence': 'turn_run'}
        for bank, pose, mode, sequence, sword in product(
                self.banks(), (15, *range(45, 53), 120, 121), (0, 5), (2, 27), (False, True)):
            expected, events = unarmed_route(bank, pose, mode=mode, sequence=sequence, sword=0 if sword else -1)
            actual, request = standing_input_request(DirectionalInput(*bank.words()), pose,
                                                      mode=mode, sequence=sequence, sword=sword)
            self.assertEqual(actual.words(), expected.words())
            self.assertEqual(request, names[events[0][0]] if events else None)


if __name__ == '__main__':
    unittest.main()
