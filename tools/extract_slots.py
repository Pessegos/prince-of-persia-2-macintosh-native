"""Per-drawer-slot room drawing: dynamic cells without whole-room variants.

The export harness (`recover_room`) calls the original piece drawers once per
(row, column, pass) slot and then orders the admitted commands with DumpTable's
rule. A room's drawing is therefore the concatenation of its slots' fragments,
re-ordered by that stable rule (`pop2.slot_drawing`). A dynamic cell (a loose
floor, a crevice run, the entrance door) changes only the fragments of the
slots whose drawers read it. Rendering each cell alone finds those slots;
rendering the product of states only over the cells one slot depends on
replaces the product over every cell of the room. Whole-room renders of the
original renderer remain the oracle (`check_room_slots`).
"""

from itertools import product
import struct

from pop2.slot_drawing import compose_list
from pop2.terrain import LevelMap

SCHEMA = 2


def slot_fragments(scene):
    """{slot: [[command, kind], ...]} in admission order."""
    fragments = {}
    for command, (slot, kind) in zip(scene['commands'], scene['slots']):
        fragments.setdefault(tuple(slot), []).append([command, kind])
    return fragments


def room_slot_lists(render, counts, unit_cells=None):
    """Exported lists as a function of unit states.

    `render(states)` returns {list name: recover_room result} for one state
    index per unit (0 is the rest state). Each list becomes {'base': [[slot,
    fragment]...], 'tables': [[slot, units, {states: fragment}]...]}.

    A slot depends on a unit when its drawers read one of the unit's cells
    (`unit_cells`, the result's 'reads') in the rest or a single-unit render,
    or when changing that unit alone changes its fragment.
    """
    rest = (0,) * len(counts)
    base = {name: slot_fragments(scene) for name, scene in render(rest).items()}
    dependencies = {name: {} for name in base}

    def add_reads(scenes):
        for name, scene in scenes.items():
            for slot, cells in scene.get('reads', {}).items():
                for unit, owned in enumerate(unit_cells or ()):
                    if cells & owned:
                        dependencies[name].setdefault(tuple(slot), set()).add(unit)

    add_reads(render(rest))
    for unit, count in enumerate(counts):
        for state in range(1, count):
            states = list(rest)
            states[unit] = state
            add_reads(render(tuple(states)))
            for name, scene in render(tuple(states)).items():
                fragments = slot_fragments(scene)
                for slot in set(base[name]) | set(fragments):
                    if fragments.get(slot) != base[name].get(slot):
                        dependencies[name].setdefault(slot, set()).add(unit)
    lists = {}
    for name, slots in dependencies.items():
        tables = []
        by_set = {}
        for slot, depends in slots.items():
            by_set.setdefault(tuple(sorted(depends)), []).append(slot)
        for depends, members in sorted(by_set.items()):
            table = {slot: {} for slot in members}
            for combination in product(*(range(counts[unit]) for unit in depends)):
                states = list(rest)
                for unit, state in zip(depends, combination):
                    states[unit] = state
                fragments = slot_fragments(render(tuple(states))[name])
                key = ','.join(map(str, combination))
                for slot in members:
                    table[slot][key] = fragments.get(slot, [])
            tables.extend([list(slot), list(depends), table[slot]] for slot in sorted(members))
        lists[name] = {'base': [[list(slot), fragment] for slot, fragment in sorted(base[name].items())
                                if slot not in slots],
                       'tables': tables}
    return lists


def check_room_slots(lists, render, states):
    """The composed lists equal the original renderer's for these states."""
    scenes = render(tuple(states))
    return all(compose_list(record, states) == scenes[name]['commands'] for name, record in lists.items())


def loose_units(choices, keys, groups):
    """Units over a room's loose cells: a crevice run (7:332a) moves together."""
    units, members, seen = [], [], set()
    for index, key in enumerate(keys):
        if index in seen:
            continue
        group = next((group for group in groups if index in group), (index,))
        seen.update(group)
        members.append(list(group))
        units.append(len(choices[key]))
    return units, members


def mutate_level(level, choices, keys, members, states, clears):
    """The level bytes for loose-unit states, as the whole-room export did."""
    mutable = bytearray(level)
    indices = [0] * len(keys)
    for group, state in zip(members, states):
        for index in group:
            indices[index] = state
    for key, index in zip(keys, indices):
        kind, foreground = choices[key][index]
        room, cell = key
        struct.pack_into('>H', mutable, room * 60 + cell * 2, kind)
        struct.pack_into('>H', mutable, 0x780 + room * 120 + cell * 4, foreground)
    for key, index in zip(keys, indices):
        if index == 2 and key in clears:
            room, cell = clears[key]
            offset = 0x780 + room * 120 + cell * 4
            struct.pack_into('>H', mutable, offset, struct.unpack_from('>H', mutable, offset)[0] & 0xf0ff)
    return mutable


def loose_floor_slot_scenery(program, caverns, prince, level, base, progress=lambda _text: None,
                             *, recover=None):
    """The loose-floor/crevice/entrance drawing of every room, by slots."""
    from tools.extract_caverns import (
        climbing_bounds, cleared_below_cell, crevice_groups, loose_floor_cells, loose_shift_tables,
        recover_room)

    recover = recover or recover_room
    terrain = LevelMap(level)
    choices = loose_floor_cells(terrain)
    clears = {key: below for key in choices if choices[key][0][0] == 11
              and (below := cleared_below_cell(terrain, *key)) is not None}
    source, rects = climbing_bounds(program, caverns, prince)
    actions = list(rects)
    entry = base.get('entry_exit')
    result = {'schema': SCHEMA, 'shifts': loose_shift_tables(program, level),
              'cells': {f'{room}:{cell}': values for (room, cell), values in choices.items()},
              'climb': {'source': source, 'rects': {str(action): list(rect) for action, rect in rects.items()}},
              'rooms': {}}
    groups_all = crevice_groups(terrain)
    for room in range(32):
        visible = {(tile.room, tile.row * 10 + tile.column)
                   for row in range(-1, 4) for column in range(-1, 11)
                   if (tile := terrain.tile(room, column, row)).room is not None}
        keys = sorted(visible & choices.keys())
        keys = sorted(set(keys) | {key for key, below in clears.items() if below in visible})
        if not keys:
            continue
        groups = [tuple(keys.index(key) for key in group if key in keys)
                  for group in groups_all if set(group) & set(keys)]
        counts, members = loose_units(choices, keys, groups)
        door = entry is not None and room == entry['room']
        if door:
            counts.append(len(entry['frames']))
        cache = {}

        def render(states, room=room, keys=keys, members=members, door=door, counts=counts):
            if states not in cache:
                progress(f'Cavern floor slots: room {room + 1}/32, renders {len(cache) + 1}')
                loose = states[:len(members)]
                mutable = mutate_level(level, choices, keys, members, loose, clears)

                def draw(*args, **options):
                    reads = {}
                    scene = recover(program, caverns, bytes(mutable), room, prince, *args,
                                    reads=reads, **options)
                    scene['reads'] = reads
                    return scene

                scenes = {'floor_redraw': draw(floor_redraw=True)}
                if source is not None:
                    scenes['climb_source'] = draw(source)
                    scenes['climb_141'] = draw(141)
                else:
                    for action in actions:
                        scenes[f'climb:{action}'] = draw(action)
                if door:
                    offset = 0x780 + room * 120 + entry['cell'] * 4
                    foreground = struct.unpack_from('>H', level, offset)[0] & 0xff00
                    struct.pack_into('>H', mutable, offset, foreground | entry['frames'][states[-1]]['phase'])
                scenes['commands'] = draw()
                cache[states] = scenes
            return cache[states]

        unit_cells = [{keys[index] for index in group} | {clears[keys[index]] for index in group
                                                          if keys[index] in clears}
                      for group in members]
        if door:
            unit_cells.append({(room, entry['cell'])})
        result['rooms'][str(room)] = {'cells': [list(key) for key in keys], 'units': members,
                                      'counts': counts, 'door': door,
                                      'lists': room_slot_lists(render, counts, unit_cells)}
    return result
