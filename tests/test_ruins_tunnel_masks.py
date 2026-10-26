"""Every imported ruins tunnel must erase old actor occlusion on reveal."""

import unittest

from PIL import ImageChops

from pop2.caverns import cavern_assets, cavern_room, cavern_scene_signature
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from tools.audit_ruins_tunnels import merged_cell_mask, reveal_cases, tunnel_inventory


@unittest.skipUnless(all((ASSET_DIR / f'ruins_level{n}.json').is_file() for n in range(6, 10)),
                     'Imported ruins6-9 required')
class RuinsTunnelMaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prince = load_resource_file('Prince.rsrc')

    def test_all_real_crevice_cells_have_exported_reveal_units(self):
        totals = [0, 0]
        for number in range(6, 10):
            _terrain, cells, groups = tunnel_inventory(self.prince['LEVL'][1999 + number]['data'])
            program, *_ = cavern_assets(number)
            exported = set()
            for room in program['loose_floors']['rooms'].values():
                for unit in room.get('crevices', ()):
                    exported.update(tuple(room['cells'][i]) for i in room['units'][unit])
            self.assertTrue(cells <= exported, (number, cells - exported))
            totals[0] += len(cells)
            totals[1] += len(groups)
        self.assertEqual(totals, [45, 11])

    def test_all_reveal_combinations_and_reentries_remove_unpainted_wall_masks(self):
        checked = 0
        for number in range(6, 10):
            terrain, _cells, _groups = tunnel_inventory(self.prince['LEVL'][1999 + number]['data'])
            program, *_ = cavern_assets(number)
            for room, units, state in reveal_cases(program, terrain):
                key = cavern_scene_signature(program, room, state)
                for incremental in (False, True):
                    with self.subTest(level=number, room=room + 1, units=units, incremental=incremental):
                        art = cavern_room(room, animated=True, level_number=number, loose_key=key,
                            redrawn=frozenset(state.loose.redrawn) if incremental else frozenset())
                        ghosts = ImageChops.subtract(merged_cell_mask(art), art.foreground.getchannel('A'))
                        self.assertIsNone(ghosts.getbbox())
                        checked += 1
        self.assertEqual(checked, 62)

    def test_actual_actor_mask_selection_is_clear_through_every_tunnel_cell(self):
        checked = set()
        for number in range(6, 10):
            terrain, _cells, _groups = tunnel_inventory(self.prince['LEVL'][1999 + number]['data'])
            program, *_ = cavern_assets(number)
            for room, _units, state in reveal_cases(program, terrain):
                own_cells = [cell for source, cell in state.loose.redrawn if source == room]
                if not own_cells:
                    continue  # Neighbor-only drawing dependency, not an actor in a tunnel.
                key = cavern_scene_signature(program, room, state)
                art = cavern_room(room, animated=True, level_number=number, loose_key=key,
                                  redrawn=frozenset(state.loose.redrawn))
                for cell in own_cells:
                    row, column = divmod(cell, 10)
                    bottom = row * 120 + 106
                    for offset in (-15, 0, 15):
                        bounds = (column * 51 + offset, bottom - 33, column * 51 + offset + 50, bottom)
                        mask = art.actor_mask(row, bounds=bounds)
                        ghosts = ImageChops.subtract(mask, art.foreground.getchannel('A'))
                        self.assertIsNone(ghosts.getbbox(), (number, room + 1, cell, offset))
                    checked.add((number, room, cell))
        self.assertEqual(len(checked), 45)
