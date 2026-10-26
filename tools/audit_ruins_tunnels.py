"""Audit all ruins crevice redraw masks, including neighbor dependencies.

Offscreen imported-game rendering, not native execution or a playthrough.
The old bug is simulated in memory by omitting only the cell-mask clearing
block from the current renderer; no game file or resource is modified.
"""

import argparse
from collections import defaultdict
import hashlib
import inspect
import json
from pathlib import Path
import struct

from PIL import Image, ImageChops

import pop2.caverns as scenery
from pop2.cavern_state import CavernState
from pop2.crevices import crevice_group, hide_crevices
from pop2.render_opening import load_resource_file
from pop2.terrain import LevelMap


def tunnel_inventory(level):
    terrain = LevelMap(hide_crevices(level))
    cells = {(room, cell) for room in range(32) for cell in range(30)
             if struct.unpack_from('>H', level, room * 60 + cell * 2)[0] == 7}
    groups = {crevice_group(terrain, room, cell % 10, cell // 10) for room, cell in cells}
    if set().union(*(set(group) for group in groups)) != cells:
        raise AssertionError('Runtime reveal groups do not cover every actual crevice cell')
    return terrain, cells, groups


def reveal_cases(program, terrain):
    metadata = program['loose_floors']
    for rid, room in metadata['rooms'].items():
        units = room.get('crevices', ())
        for bits in range(1, 1 << len(units)):
            selected = [unit for i, unit in enumerate(units) if bits & (1 << i)]
            state = CavernState()
            cells = set()
            for unit in selected:
                source_room, source_cell = room['cells'][room['units'][unit][0]]
                group = crevice_group(terrain, source_room, source_cell % 10, source_cell // 10)
                cells.update(group)
            for source_room, cell in cells:
                tile = terrain.tile(source_room, cell % 10, cell // 10)
                state.loose.tiles[source_room, cell] = 7, tile.foreground | 0x80
                state.loose.redrawn.add((source_room, cell))
            yield int(rid), tuple(selected), state


def merged_cell_mask(art):
    if art.actor_cell_occlusion is None:
        raise AssertionError('Imported scenery lacks per-cell actor masks')
    result = Image.new('L', art.background.size)
    for mask, position in art.actor_cell_occlusion.values():
        full = Image.new('L', result.size)
        full.paste(mask, position)
        result = ImageChops.lighter(result, full)
    return result


def nonzero_pixels(mask):
    return mask.width * mask.height - mask.histogram()[0]


def legacy_mask_renderer():
    source = inspect.getsource(scenery.cavern_room)
    start = source.index('            if cell_masks is not None:')
    end = source.index('            if custom_mask is not None:', start)
    removed = source[start:end]
    if removed.count('ImageChops.multiply') != 1 or 'del cell_masks[key]' not in removed:
        raise AssertionError('Cell-mask implementation changed; review legacy simulation')
    namespace = dict(vars(scenery))
    exec(compile(source[:start] + source[end:], '<old-tunnel-mask-simulation>', 'exec'), namespace)
    return namespace['cavern_room'], hashlib.sha256(source.encode()).hexdigest()


def run_audit():
    prince = load_resource_file('Prince.rsrc')
    legacy, source_hash = legacy_mask_renderer()
    records, levels = [], {}
    for number in range(6, 10):
        level = prince['LEVL'][1999 + number]['data']
        terrain, actual_cells, groups = tunnel_inventory(level)
        program, *_ = scenery.cavern_assets(number)
        actual_rooms = {room for room, _cell in actual_cells}
        affected, affected_dependencies = set(), set()
        cases = list(reveal_cases(program, terrain))
        for room, units, state in cases:
            key = scenery.cavern_scene_signature(program, room, state)
            options = dict(animated=True, level_number=number, loose_key=key,
                           redrawn=frozenset(state.loose.redrawn))
            current = scenery.cavern_room(room, **options)
            old = legacy(room, **options)
            if current.flattened().tobytes() != old.flattened().tobytes():
                raise AssertionError('Legacy simulation changed scenery pixels, not only actor masks')
            foreground = current.foreground.getchannel('A')
            old_mask, new_mask = merged_cell_mask(old), merged_cell_mask(current)
            old_ghost = ImageChops.subtract(old_mask, foreground)
            ghost = ImageChops.subtract(new_mask, foreground)
            if ghost.getbbox() is not None:
                raise AssertionError(f'Stale actor mask at level{number} room{room + 1} units{units}')
            options['redrawn'] = frozenset()
            entered = scenery.cavern_room(room, **options)
            old_entered = legacy(room, **options)
            if (merged_cell_mask(entered).tobytes() != merged_cell_mask(old_entered).tobytes()
                    or ImageChops.subtract(merged_cell_mask(entered), entered.foreground.getchannel('A')).getbbox()):
                raise AssertionError('Already-revealed room entry has stale/different actor masks')
            stale = nonzero_pixels(old_ghost)
            if stale:
                (affected if room in actual_rooms else affected_dependencies).add(room + 1)
            records.append(dict(level=number, room=room + 1, units=units,
                contains_tunnel=room in actual_rooms, old_stale_pixels=stale,
                current_stale_pixels=0, old_stale_bounds=old_ghost.getbbox(),
                entered_stale_pixels=0))
        levels[number] = dict(tunnel_groups=len(groups), tunnel_cells=len(actual_cells),
            tunnel_rooms=sorted(room + 1 for room in actual_rooms), redraw_states=len(cases),
            old_affected_tunnel_rooms=sorted(affected),
            old_affected_neighbor_drawing_rooms=sorted(affected_dependencies))
    totals = defaultdict(int)
    for level in levels.values():
        for key in ('tunnel_groups', 'tunnel_cells', 'redraw_states'):
            totals[key] += level[key]
        totals['tunnel_rooms'] += len(level['tunnel_rooms'])
    return dict(levels=levels, totals=dict(totals), records=records, current_stale_pixels=0,
                renderer_source_sha256=source_hash, scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'records'}, indent=2))
