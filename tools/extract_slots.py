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

from pop2.bridge import BRIDGE_LEVEL, BRIDGE_ROOM, BRIDGE_ROW, BRIDGE_TILE
from pop2.crevices import CREVICE_TILE
from pop2.slot_drawing import PLANK_STATES, compose_list
from pop2.terrain import LevelMap

SCHEMA = 2


def slot_fragments(scene):
    """{slot: [[command, kind], ...]} in admission order."""
    fragments = {}
    for command, (slot, kind) in zip(scene['commands'], scene['slots']):
        fragments.setdefault(tuple(slot), []).append([command, kind])
    return fragments


class LazyScenes(dict):
    """{list name: recover_room result}, each drawn on first use."""

    def __init__(self, makers):
        super().__init__()
        self.makers = makers

    def __missing__(self, name):
        self[name] = self.makers[name]()
        return self[name]

    def items(self):
        return [(name, self[name]) for name in self.makers]


def single_states(counts):
    """(unit, state) for every render that changes one unit from rest."""
    return [(unit, state) for unit, count in enumerate(counts) for state in range(1, count)]


def slot_dependencies(render, counts, unit_cells=None, singles=None):
    """Rest fragments and, per list, the units each slot depends on.

    A slot depends on a unit when its drawers read one of the unit's cells
    (`unit_cells`, the result's 'reads') in the rest or a single-unit render,
    or when changing that unit alone changes its fragment. `singles` limits
    the single-unit renders (default `single_states(counts)`); the union over
    a partition of them equals the whole (`merge_dependencies`).
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
    for unit, state in single_states(counts) if singles is None else singles:
        states = list(rest)
        states[unit] = state
        add_reads(render(tuple(states)))
        for name, scene in render(tuple(states)).items():
            fragments = slot_fragments(scene)
            for slot in set(base[name]) | set(fragments):
                if fragments.get(slot) != base[name].get(slot):
                    dependencies[name].setdefault(slot, set()).add(unit)
    return base, {name: {slot: tuple(sorted(units)) for slot, units in slots.items()}
                  for name, slots in dependencies.items()}


def merge_dependencies(parts):
    """The union of `slot_dependencies` results over parts of the singles."""
    merged = {}
    for dependencies in parts:
        for name, slots in dependencies.items():
            merged.setdefault(name, {})
            for slot, units in slots.items():
                merged[name].setdefault(slot, set()).update(units)
    return {name: {slot: tuple(sorted(units)) for slot, units in slots.items()}
            for name, slots in merged.items()}


def combination_jobs(counts, dependencies):
    """(list name, units, member slots, combinations) for every dependency set."""
    jobs = []
    for name, slots in dependencies.items():
        by_set = {}
        for slot, depends in slots.items():
            by_set.setdefault(depends, []).append(slot)
        for depends, members in sorted(by_set.items()):
            jobs.append((name, depends, sorted(members),
                         list(product(*(range(counts[unit]) for unit in depends)))))
    return jobs


def render_combinations(render, counts, name, depends, members, combinations):
    """{combination key: {slot: fragment}} for one dependency set."""
    rest = (0,) * len(counts)
    result = {}
    for combination in combinations:
        states = list(rest)
        for unit, state in zip(depends, combination):
            states[unit] = state
        fragments = slot_fragments(render(tuple(states), frozenset(members))[name])
        result[','.join(map(str, combination))] = {slot: fragments.get(slot, []) for slot in members}
    return result


def assemble_lists(base, dependencies, rendered):
    """The exported lists from rest fragments and rendered combinations.

    `rendered` maps (list name, units) to {combination key: {slot: fragment}}.
    """
    lists = {}
    for name, slots in dependencies.items():
        tables = []
        by_set = {}
        for slot, depends in slots.items():
            by_set.setdefault(depends, []).append(slot)
        for depends, members in sorted(by_set.items()):
            combinations = rendered[name, depends]
            tables.extend([list(slot), list(depends), {key: fragments[slot] for key, fragments
                                                       in combinations.items()}]
                          for slot in sorted(members))
        lists[name] = {'base': [[list(slot), fragment] for slot, fragment in sorted(base[name].items())
                                if slot not in slots],
                       'tables': tables}
    return lists


def room_slot_lists(render, counts, unit_cells=None):
    """Exported lists as a function of unit states.

    `render(states)` returns {list name: recover_room result} for one state
    index per unit (0 is the rest state). Each list becomes {'base': [[slot,
    fragment]...], 'tables': [[slot, units, {states: fragment}]...]}.
    """
    base, dependencies = slot_dependencies(render, counts, unit_cells)
    rendered = {(name, depends): render_combinations(render, counts, name, depends, members, combinations)
                for name, depends, members, combinations in combination_jobs(counts, dependencies)}
    return assemble_lists(base, dependencies, rendered)


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


def slot_context(program, caverns, prince, level, base):
    """What every room of one level's slot export needs (picklable)."""
    from tools.extract_caverns import (
        climbing_bounds, cleared_below_cell, crevice_groups, loose_floor_cells)
    from tools.extract_scythes import scythe_pairs

    terrain = LevelMap(level)
    choices = loose_floor_cells(terrain)
    clears = {key: below for key in choices if choices[key][0][0] == 11
              and (below := cleared_below_cell(terrain, *key)) is not None}
    source, rects = climbing_bounds(program, caverns, prince)
    # Level five's bridge planks (tile 44, native room 10): rest, wobbling
    # up/down (foreground nibble 1/2, OffsetBrgFloorY 8:0772) and fallen
    # (TriggerBrgFloorMob 8:0c3e-0c54: empty, foreground 0xc000).
    planks = [(tile.room, tile.row * 10 + tile.column) for column in range(10)
              if (tile := terrain.tile(BRIDGE_ROOM, column, BRIDGE_ROW)).kind == BRIDGE_TILE
              and struct.unpack_from('>H', level, 0x218a)[0] == BRIDGE_LEVEL]
    return {'program': program, 'caverns': caverns, 'prince': prince, 'level': level,
            'choices': choices, 'clears': clears, 'source': source, 'rects': rects,
            'entry': base.get('entry_exit'), 'groups': crevice_groups(terrain), 'planks': planks,
            'pairs': scythe_pairs(terrain) if struct.unpack_from('>H', level, 0x2186)[0] == 4 else []}


def room_renderer(context, room, recover, progress=lambda _text: None):
    """(room record without lists, render, counts, unit cells), or None."""
    from pop2.scythes import SCYTHE_STATES

    program, caverns, prince, level = (context[key] for key in ('program', 'caverns', 'prince', 'level'))
    choices, clears, entry, pairs = (context[key] for key in ('choices', 'clears', 'entry', 'pairs'))
    source, actions = context['source'], list(context['rects'])
    terrain = LevelMap(level)
    visible = {(tile.room, tile.row * 10 + tile.column)
               for row in range(-1, 4) for column in range(-1, 11)
               if (tile := terrain.tile(room, column, row)).room is not None}
    keys = sorted(visible & choices.keys())
    keys = sorted(set(keys) | {key for key, below in clears.items() if below in visible})
    scythes = [index for index, (key, partner) in enumerate(pairs) if {key, partner} & visible]
    bridge = [key for key in context['planks'] if key in visible]
    if not keys and not scythes and not bridge:
        return None
    groups = [tuple(keys.index(key) for key in group if key in keys)
              for group in context['groups'] if set(group) & set(keys)]
    counts, members = loose_units(choices, keys, groups)
    counts.extend(len(SCYTHE_STATES) for _index in scythes)
    counts.extend(PLANK_STATES for _key in bridge)
    door = entry is not None and room == entry['room']
    if door:
        counts.append(len(entry['frames']))
    cache = {}

    def render(states, only=None):
        """{list name: scene}; with `only` (a set of slots), just those slots, untracked."""
        if only is not None or states not in cache:
            progress(f'Cavern floor slots: room {room + 1}/32, renders {len(cache) + 1}')
            loose = states[:len(members)]
            mutable = mutate_level(level, choices, keys, members, loose, clears)
            for index, state in zip(scythes, states[len(members):]):
                for source_room, cell in pairs[index]:
                    offset = 0x780 + source_room * 120 + cell * 4
                    foreground = struct.unpack_from('>H', mutable, offset)[0] & 0xff00
                    struct.pack_into('>H', mutable, offset, foreground | SCYTHE_STATES[state])
            for (source_room, cell), state in zip(bridge, states[len(members) + len(scythes):]):
                offset = 0x780 + source_room * 120 + cell * 4
                foreground = struct.unpack_from('>H', mutable, offset)[0]
                if state == 3:
                    struct.pack_into('>H', mutable, source_room * 60 + cell * 2, 0)
                    struct.pack_into('>H', mutable, offset, 0xc000)
                else:
                    struct.pack_into('>H', mutable, offset, (foreground & 0xfff0) | state)

            def draw(*args, mutable=bytes(mutable), **options):
                if only is not None:
                    return recover(program, caverns, mutable, room, prince, *args, only=only, **options)
                reads = {}
                scene = recover(program, caverns, mutable, room, prince, *args, reads=reads, **options)
                scene['reads'] = reads
                return scene

            lists = {'floor_redraw': lambda: draw(floor_redraw=True)}
            if source is not None:
                lists['climb_source'] = lambda: draw(source)
                lists['climb_141'] = lambda: draw(141)
            else:
                for action in actions:
                    lists[f'climb:{action}'] = lambda action=action: draw(action)
            if door:
                offset = 0x780 + room * 120 + entry['cell'] * 4
                foreground = struct.unpack_from('>H', level, offset)[0] & 0xff00
                struct.pack_into('>H', mutable, offset, foreground | entry['frames'][states[-1]]['phase'])
            lists['commands'] = lambda mutable=bytes(mutable): draw(mutable=mutable)
            if only is not None:
                return LazyScenes(lists)
            cache[states] = LazyScenes(lists)
        return cache[states]

    unit_cells = [{keys[index] for index in group} | {clears[keys[index]] for index in group
                                                      if keys[index] in clears}
                  for group in members]
    unit_cells.extend(set(pairs[index]) for index in scythes)
    unit_cells.extend({key} for key in bridge)
    if door:
        unit_cells.append({(room, entry['cell'])})
    record = {'cells': [list(key) for key in keys], 'units': members,
              'scythes': [list(pairs[index][0]) for index in scythes],
              'planks': [list(key) for key in bridge],
              'counts': counts, 'door': door}
    crevices = [unit for unit, group in enumerate(members) if choices[keys[group[0]]][0][0] == CREVICE_TILE]
    if crevices:
        record['crevices'] = crevices
    return record, render, counts, unit_cells


def crevice_dirty_cells(terrain, room, cells):
    """Cells of `room` whose redraw a crevice reveal marks (RuinSetCreviceRevealed).

    7:344a marks each revealed cell visible in the room (IsVisibleRoomCell
    5:3960: the room itself, the left room's last column) and the right
    neighbour of a run's end (low bits 0, not column 9) through 5:1936,
    which maps the left/right rooms by -9/+9 and the rooms above/below by
    -20/+20 (MarkRedraw 5:18f0 keeps indices 0-29).
    """
    offsets = {room: 0, terrain.neighbor(room, 'left'): -9, terrain.neighbor(room, 'right'): 9,
               terrain.neighbor(room, 'up'): -20, terrain.neighbor(room, 'down'): 20}

    def mark(source, cell):
        return cell + offsets[source] if source in offsets else cell

    dirty = set()
    for source, cell in cells:
        if source == room or source == terrain.neighbor(room, 'left') and cell % 10 == 9:
            dirty.add(mark(source, cell))
        if terrain.tile(source, cell % 10, cell // 10).foreground & 3 == 0 and cell % 10 != 9:
            dirty.add(mark(source, cell + 1))
    return sorted(cell for cell in dirty if 0 <= cell < 30)


def crevice_redraw(context, room, record, unit, recover):
    """The drawing a reveal adds over the displayed room: the dirty cells'
    drawers in per-cell redraw mode (RedrawCell 3:1d3a, a5-0x4832 = 0), all
    other units at rest."""
    keys = [tuple(key) for key in record['cells']]
    members = record['units']
    states = [0] * len(members)
    states[unit] = 1
    level = bytes(mutate_level(context['level'], context['choices'], keys, members, states, context['clears']))
    dirty = crevice_dirty_cells(LevelMap(level), room, [keys[index] for index in members[unit]])
    if not dirty:
        return []
    only = frozenset((cell // 10, cell % 10, draw_pass) for cell in dirty for draw_pass in (0, 5, 11, 1))
    return recover(context['program'], context['caverns'], level, room, context['prince'],
                   only=only, cell_redraw=True)['commands']


def room_slot_scenery(context, room, recover, progress=lambda _text: None):
    """One room's slot export, or None when nothing in it is dynamic."""
    prepared = room_renderer(context, room, recover, progress)
    if prepared is None:
        return None
    record, render, counts, unit_cells = prepared
    record = {**record, 'lists': room_slot_lists(render, counts, unit_cells)}
    if record.get('crevices'):
        record['redraws'] = {str(unit): crevice_redraw(context, room, record, unit, recover)
                             for unit in record['crevices']}
    return record


_worker = {}

# Combinations per worker job: small enough to share a large room's work.
CHUNK = 48


def _start_worker(contexts):
    from tools.workers import watch_parent

    watch_parent()
    _worker.update(contexts=contexts, machines={}, renderers={})


def _worker_renderer(level, room):
    from functools import partial
    from tools.extract_caverns import CavernRecovery, recover_room

    context = _worker['contexts'][level]
    if level not in _worker['machines']:
        _worker['machines'][level] = CavernRecovery(context['program'], context['caverns'], context['prince'],
                                                    track_reads=True)
    key = level, room
    if key not in _worker['renderers']:
        _worker['renderers'] = {key: room_renderer(context, room, partial(
            recover_room, _machine=_worker['machines'][level]))}
    return _worker['renderers'][key]


def _worker_dependencies(task):
    level, room, singles = task
    _record, render, counts, unit_cells = _worker_renderer(level, room)
    return task[:2], slot_dependencies(render, counts, unit_cells, singles)


def _worker_combinations(task):
    level, room, name, depends, members, combinations = task
    _record, render, counts, _cells = _worker_renderer(level, room)
    return task[:4], render_combinations(render, counts, name, depends, members, combinations)


def _worker_redraw(task):
    from functools import partial
    from tools.extract_caverns import recover_room

    level, room, record, unit = task
    _worker_renderer(level, room)  # The level's recovery machine.
    recover = partial(recover_room, _machine=_worker['machines'][level])
    return task[:2], unit, crevice_redraw(_worker['contexts'][level], room, record, unit, recover)


def parallel_slot_rooms(contexts, workers, progress=lambda _text: None):
    """{level: {room: record}} for several levels' contexts, by `workers` processes.

    The single-unit renders of every room are shared out first (dependencies),
    then the combinations of each dependency set, both in CHUNK-sized jobs.
    """
    from concurrent.futures import ProcessPoolExecutor

    records, tasks = {}, []
    for level, context in contexts.items():
        for room in range(32):
            # Without drawing anything: the room's units and state counts.
            prepared = room_renderer(context, room, recover=None)
            if prepared is not None:
                records[level, room] = prepared[0]
                singles = single_states(prepared[2])
                tasks.extend((level, room, singles[start:start + CHUNK // 4])
                             for start in range(0, max(len(singles), 1), CHUNK // 4))
    with ProcessPoolExecutor(workers, initializer=_start_worker, initargs=(contexts,)) as pool:
        bases, parts = {}, {}
        for done, (key, (base, dependencies)) in enumerate(pool.map(_worker_dependencies, tasks), 1):
            progress(f'Cavern floor slots: rooms {done}/{len(tasks)}')
            bases[key] = base
            parts.setdefault(key, []).append(dependencies)
        dependencies = {key: merge_dependencies(part) for key, part in parts.items()}
        jobs = []
        for (level, room), record in records.items():
            for name, depends, members, combinations in combination_jobs(record['counts'],
                                                                          dependencies[level, room]):
                for start in range(0, len(combinations), CHUNK):
                    jobs.append((level, room, name, depends, members, combinations[start:start + CHUNK]))
        rendered = {}
        for done, (key, result) in enumerate(pool.map(_worker_combinations, jobs), 1):
            progress(f'Cavern floor slots: combinations {done}/{len(jobs)}')
            rendered.setdefault(key[:2], {}).setdefault(key[2:], {}).update(result)
        redraws = {}
        for key, unit, commands in pool.map(_worker_redraw, [
                (level, room, record, unit) for (level, room), record in records.items()
                for unit in record.get('crevices', ())]):
            redraws.setdefault(key, {})[str(unit)] = commands
    rooms = {level: {} for level in contexts}
    for (level, room), record in records.items():
        rooms[level][room] = {**record, 'lists': assemble_lists(bases[level, room], dependencies[level, room],
                                                                 rendered.get((level, room), {}))}
        if record.get('crevices'):
            rooms[level][room]['redraws'] = redraws[level, room]
    return rooms


def loose_floor_slot_scenery(program, caverns, prince, level, base, progress=lambda _text: None,
                             *, recover=None, workers=1, rooms=None):
    """The loose-floor/crevice/scythe/plank/entrance drawing of every room.

    A room's units are its loose cells (crevice runs together), then its
    scythes (60 states each), its bridge planks, then the entrance door's
    closing frames in the entry room. With `workers` > 1 the rooms are drawn
    by that many processes; the result is identical. `rooms` supplies rooms
    already drawn by `parallel_slot_rooms`.
    """
    from tools.extract_caverns import loose_shift_tables, recover_room

    context = slot_context(program, caverns, prince, level, base)
    result = {'schema': SCHEMA, 'shifts': loose_shift_tables(program, level),
              'cells': {f'{room}:{cell}': values for (room, cell), values in context['choices'].items()},
              'climb': {'source': context['source'],
                        'rects': {str(action): list(rect) for action, rect in context['rects'].items()}},
              'scythe_units': True, 'plank_units': True, 'rooms': {}}
    if rooms is not None:
        pass
    elif workers > 1:
        rooms = parallel_slot_rooms({0: context}, workers, progress)[0]
    else:
        recover = recover or recover_room
        rooms = {room: room_slot_scenery(context, room, recover, progress) for room in range(32)}
    result['rooms'] = {str(room): scene for room, scene in sorted(rooms.items()) if scene is not None}
    return result
