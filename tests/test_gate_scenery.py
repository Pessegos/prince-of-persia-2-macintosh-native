import struct
import unittest

from pop2.paths import ASSET_DIR
from tools.extract_pressure_plates import pressure_scenery


class GateSceneryExportTests(unittest.TestCase):
    def export(self, phase, kind=4, environment=3):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2186, environment)
        struct.pack_into('>H', level, 0x218a, 5)
        struct.pack_into('>H', level, 0x2198, 1)
        # Use room 2 so an exit is not mistaken for the entrance animation.
        struct.pack_into('>H', level, 60 + 15 * 2, kind)
        struct.pack_into('>H', level, 0x780 + 120 + 15 * 4, 0x300 | phase)
        limit = 79 if kind == 17 else 184
        shape = 3566 if kind == 17 else 3563 if environment == 3 else 3542
        probes = []

        def recover(_program, _art, data, room, _prince):
            if room != 1:
                return {'commands': []}
            value = struct.unpack_from('>H', data, 0x780 + 120 + 15 * 4)[0]
            probes.append(value)
            position = min(value & 255, limit)
            shift = position if kind == 17 else position // 4 * 2
            return {'commands': [['back', shape, 306, 226 - shift, 16, 1,
                                  [89, 306, 226 - shift, 330], 4, 5, 1]]}

        base = {'rooms': {str(room): recover(None, None, level, room, None)['commands']
                          for room in range(32)}}
        probes.clear()
        result = pressure_scenery(None, None, None, bytes(level), base, recover=recover)
        return result['rooms']['1'], probes

    def test_gate_binding_survives_initial_open_and_closed_drawing_saturation(self):
        # DrawCaveGateMovable 8:1f92-1fb6: phases >=184 draw at the same height.
        for environment in (3, 4):
            for phase in (0, 56, 180, 183, 184, 200, 237, 255):
                with self.subTest(environment=environment, phase=phase):
                    records, probes = self.export(phase, environment=environment)
                    self.assertEqual(len(records), 1)
                    self.assertEqual((records[0]['room'], records[0]['cell'],
                                      records[0]['foreground']), (1, 15, 0x300 | phase))
                    self.assertTrue(records[0]['commands'])
                    self.assertEqual(probes, [0x300 | (0 if phase >= 184 else 184)])

    def test_exit_binding_also_compares_a_distinct_endpoint(self):
        for phase in (0, 40, 79, 255):
            with self.subTest(phase=phase):
                records, probes = self.export(phase, kind=17)
                self.assertEqual(len(records), 1)
                self.assertEqual(probes, [0x300 | (0 if phase >= 79 else 79)])


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported cavern scenery required')
class ImportedGateSceneryTests(unittest.TestCase):
    def test_level_five_initially_open_gates_close_and_reopen_with_their_real_buttons(self):
        from pop2.caverns import cavern_assets, cavern_pressure_signature, cavern_room
        from pop2.game_session import GameResources, GameSession
        from pop2.terrain import stone_gate_blocks

        resources = GameResources.load()
        program = cavern_assets(5)[0]
        for room, cell, button in ((1, 15, 14), (19, 0, 18)):
            with self.subTest(room=room + 1):
                game = GameSession.load(resources, 5)
                plates, terrain = game.caverns.plates, game.level_map
                row, column = divmod(cell, 10)
                records = program['pressure_plates']['rooms'][str(room)]
                index = next(i for i, record in enumerate(records)
                             if (record['room'], record['cell']) == (room, cell))

                def snapshot():
                    signature = cavern_pressure_signature(program, room, game.caverns)
                    image = cavern_room(room, pressure_key=signature, level_number=5).flattened()
                    crop = image.crop(((column + 1) * 51, row * 120 + 30,
                                       (column + 2) * 51, row * 120 + 106))
                    return signature[index], crop.tobytes()

                opened = snapshot()
                self.assertEqual(opened[0], 46)
                self.assertFalse(stone_gate_blocks(terrain.tile(room, column, row).foreground,
                                                  (0, 0, 20, 71)))
                plates.push(terrain, terrain.tile(room, button % 10, button // 10))
                for _ in range(8):
                    plates.advance(terrain)
                closed = snapshot()
                self.assertEqual(closed[0], 0)
                self.assertNotEqual(closed[1], opened[1])
                self.assertTrue(stone_gate_blocks(terrain.tile(room, column, row).foreground,
                                                 (0, 0, 20, 71)))
                plates.push(terrain, terrain.tile(room, button % 10, button // 10))
                for _ in range(46):
                    plates.advance(terrain)
                self.assertEqual(snapshot(), opened)
                self.assertFalse(stone_gate_blocks(terrain.tile(room, column, row).foreground,
                                                  (0, 0, 20, 71)))

    def test_all_twenty_two_cavern_gates_have_live_drawing_bindings(self):
        from pop2.caverns import cavern_assets
        from pop2.game_session import GameResources
        from pop2.terrain import LevelMap

        resources = GameResources.load()
        counts = []
        for number in (3, 4, 5):
            terrain = LevelMap(resources.level(number).data)
            program = cavern_assets(number)[0]
            gates = 0
            for room in range(32):
                bindings = {(record['room'], record['cell'])
                            for record in program['pressure_plates']['rooms'][str(room)]
                            if record['kind'] == 4 and record['commands']}
                for cell in range(30):
                    if terrain.tile(room, cell % 10, cell // 10).kind != 4:
                        continue
                    gates += 1
                    with self.subTest(level=number, room=room + 1, cell=cell):
                        self.assertIn((room, cell), bindings)
            counts.append(gates)
        self.assertEqual(counts, [9, 5, 8])


if __name__ == '__main__':
    unittest.main()
