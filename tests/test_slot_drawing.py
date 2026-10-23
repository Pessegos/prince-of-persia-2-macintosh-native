import unittest


def scene(commands):
    """A fake recover_room result: [(slot, layer, shape, kind), ...]."""
    return {'commands': [[layer, shape, 0, 0, 16, 0, [0, 0, 1, 1], 4, slot[1], slot[0]]
                         for slot, layer, shape, _kind in commands],
            'slots': [[list(slot), kind] for slot, _layer, _shape, kind in commands]}


class SlotDrawingTests(unittest.TestCase):
    def test_compose_keeps_drawer_order_then_dumptable_layers(self):
        from pop2.slot_drawing import compose

        fragments = {(0, 0, 1): [[['front', 1], 3]], (0, 0, 0): [[['back', 2], 5], [['back', 3], 0]],
                     (2, 4, 0): [[['back', 4], 5]]}
        # Rows 2 before 0; back-wall records (kind 0) before other back items.
        self.assertEqual(compose(fragments), [['back', 3], ['back', 4], ['back', 2], ['front', 1]])

    def test_slot_tables_reproduce_an_interaction_of_two_cells(self):
        from pop2.slot_drawing import compose_list
        from tools.extract_slots import room_slot_lists

        def render(states):
            a, b = states
            items = [((2, 0, 0), 'back', 10, 5), ((1, 3, 0), 'back', 20 + a, 5)]
            if a and b:
                # A lip drawn only when both cells change, read from both.
                items.append(((0, 5, 1), 'front', 30, 3))
            result = scene(items)
            result['reads'] = {(0, 5, 1): {(0, 1), (0, 2)}, (1, 3, 0): {(0, 1)}}
            return {'commands': result}

        lists = room_slot_lists(render, [2, 3], [{(0, 1)}, {(0, 2)}])
        for states in ((0, 0), (1, 0), (0, 2), (1, 1), (1, 2)):
            self.assertEqual(compose_list(lists['commands'], states), render(states)['commands']['commands'],
                             states)

    def test_rest_and_unknown_rooms_use_the_base_drawing(self):
        from pop2.caverns import slot_variant

        self.assertIsNone(slot_variant({}, None, '01'))
        room = {'units': [[0], [1]], 'counts': [3, 3], 'door': False, 'cells': [[0, 1], [0, 2]], 'lists': {}}
        self.assertIsNone(slot_variant({}, room, '00'))


if __name__ == '__main__':
    unittest.main()
