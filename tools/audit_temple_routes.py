"""Search the temple levels for entrance-to-exit routes with the port's engine.

Offscreen and headless: a hidden ScenePrototype runs the real game loop (real
keys, sequences, terrain, plates, gates, trap doors, rocks, loose floors) with
drawing disabled. A best-first search over short key macros keeps deep copies
of the session as its nodes. A route that reaches the exit is a list of
macros, which ``replay`` runs again from a fresh level load, with drawing on
and without any copied state.

It audits the port, not the original: a route found here shows that the port
can be finished, and that the LEVL data allows it under the port's rules. It
is no native-equivalence claim. See docs/research/temple-route-audit.md.
"""

import argparse
from collections import Counter
import copy
import heapq
import itertools
import json
from pathlib import Path
import random
import sys
import time
import tkinter as tk
import traceback
from unittest.mock import patch

import pop2.scene_prototype as prototype
from pop2.scene_prototype import ScenePrototype
from pop2.terrain import floor_contact_x

REST_TIMEOUT = 150
DIRECTIONS = {'L': -1, 'R': 1}
PRONE_REST = 251  # GenCtrl's crawl pose under a low cell.


class Clock:
    """Stands in for the scene module's ``time``: only ticks advance it."""

    def __init__(self):
        self.now = 100.0

    def perf_counter(self):
        return self.now

    def __getattr__(self, name):
        return getattr(time, name)


class Harness:
    """A hidden scene whose whole mutable game state can be copied."""

    def __init__(self, number, *, peaceful=True, draw=False, god=False):
        original_tk = tk.Tk

        def hidden_root():
            root = original_tk()
            root.withdraw()
            return root

        with patch('pop2.window_controls.tk.Tk', hidden_root):
            self.scene = scene = ScenePrototype()
        scene.root.after_cancel(scene.animation_after_id)
        scene.animation_after_id = None
        scene.schedule_next_animation = lambda: None
        scene.copy_protection_enabled = False
        self.clock = Clock()
        self.real_time = prototype.time
        prototype.time = self.clock
        self.pending = []
        original_after = scene.root.after

        def after(delay, callback=None, *args):
            # press_up's short deferred jump; other timers stay with Tk.
            if getattr(callback, '__name__', '') == 'start_jump_if_needed':
                self.pending.append(callback)
                return 'audit'
            return original_after(delay, callback, *args)

        scene.root.after = after
        self.draw = draw
        self.real_render = scene.render
        if not draw:
            scene.render = lambda: None
        scene.load_level(number)
        if not draw:
            # Room images are drawing only; level events ask for one per tick.
            room = scene.level_renderer.enter_room(scene.room_id, scene.game.caverns)
            scene.level_renderer.enter_room = lambda *_args, **_options: room
            scene.level_renderer.room = lambda *_args, **_options: room
        scene.animation_after_id = None
        scene.peaceful = peaceful
        scene.god_mode = god
        scene.combat.rng = random.Random(1)
        self.ticks = 0

    def close(self):
        prototype.time = self.real_time
        self.scene.root.destroy()

    def tick(self, count=1):
        scene = self.scene
        for _ in range(count):
            self.clock.now += 0.101
            self.ticks += 1
            for callback in self.pending:
                callback()
            self.pending.clear()
            scene.advance_animation()
            scene.animation_after_id = None

    # Scene attributes that are plain control state, not resources or widgets.
    PLAIN = (bool, int, float, str, type(None), tuple, list, dict, set)
    SKIP = frozenset({
        'render', 'schedule_next_animation', 'next_animation_at', 'room_cache', 'sprite_cache',
        'sword_sprite_cache', 'resources', 'sequences', 'frames', 'palette', 'sword_palette',
        'background', 'foreground', 'status', 'canvas', 'root', 'level_map', 'physics',
        'sequence_runtime', 'sequence_state', 'game', 'guard_art', 'health_art', 'hit_art',
        'kid', 'sword_shapes', 'audio', 'attachment_frames', 'ordinary_attachment_frames',
        'development_level_options', 'attract_data', 'curtain_sprites', 'glass_sprites', 'screenshot_settings', 'level_renderer',
    })

    def controls(self):
        result = {}
        for key, value in vars(self.scene).items():
            if key in self.SKIP:
                continue
            if isinstance(value, self.PLAIN) or type(value).__module__.startswith('pop2.mac_input'):
                result[key] = copy.deepcopy(value)
        return result

    def shared(self):
        # Read-only data the copies keep sharing.
        scene = self.scene
        return {id(item): item for item in (
            scene.guard_art, scene.resources, scene.sequences, scene.frames)}

    def save(self):
        return copy.deepcopy(self.scene.game, self.shared()), self.controls()

    def restore(self, saved):
        scene = self.scene
        game = copy.deepcopy(saved[0], self.shared())
        vars(scene).update(copy.deepcopy(saved[1]))
        scene.game = game
        scene.level_map, scene.physics = game.level_map, game.physics
        scene.sequence_runtime, scene.sequence_state = game.runtime, game.runtime.state
        self.pending.clear()

    # Queries.

    def player(self):
        scene = self.scene
        state, motion = scene.sequence_state, scene.terrain_motion
        record = scene.frames[state.action]
        contact = floor_contact_x(state.target_x, state.facing, record)
        return dict(room=motion.room, row=motion.row, column=int(contact // 51), x=state.target_x,
                    facing=state.facing, action=state.action, sequence=state.source_sequence_id,
                    falling=motion.falling, life=scene.combat.player.life,
                    alive=scene.combat.player.alive)

    def goal(self):
        scene = self.scene
        return scene.game.exit is not None or scene.level_complete or scene.game.level.number != self.number

    def mechanisms(self):
        """The state that decides what can be reached, coarsely."""
        scene = self.scene
        caverns = scene.game.caverns
        plates = caverns.plates
        terrain = scene.level_map
        gates = []
        for room in range(32):
            for cell in range(30):
                tile = terrain.tile(room, cell % 10, cell // 10)
                if tile.kind in (4, 17) and tile.foreground & 255:
                    gates.append((room, cell, (tile.foreground & 255) >= 184,
                                  (tile.foreground & 255) == 255))
        return (frozenset(gates),
                frozenset((key, value[0], (value[1] >> 4) & 3) for key, value in caverns.loose.tiles.items()),
                frozenset((mob[2], mob[6], mob[4] == 0, mob[0] // 51) for mob in caverns.rocks.bank),
                frozenset(key for key, value in plates.timers.items() if value == 31),
                frozenset(caverns.potions.tiles), caverns.potions.floating)


def press(harness, key, pressed):
    scene = harness.scene
    if key in DIRECTIONS:
        scene.horizontal_key(None, DIRECTIONS[key], pressed)
    else:
        scene.set_key_state(key, pressed)


def altar_death(harness):
    """Level 13's scripted death: a birdhead kills the Prince east of the
    chasm, the shadow takes the flame and revives him. The waking opponent is
    supplied (turned to face him, one life left); the kill, the rise and the
    merge are the port's own. No effect anywhere else."""
    scene = harness.scene
    info = harness.player()
    guards = scene.combat.active_guards()
    if (harness.number != 13 or info['room'] != 3 or info['row'] != 1 or info['column'] < 7
            or not guards):
        return
    guards[0].state.facing = 1
    scene.combat.player.life = 1
    scene.peaceful = False
    press(harness, 'ctrl', True)
    harness.tick(2)
    press(harness, 'ctrl', False)
    for _ in range(600):
        harness.tick()
        if scene.combat.player.alive and scene.game.caverns.altar == -1:
            break
    scene.peaceful = True


def play(harness, script):
    """Runs (keys down, keys up, ticks) steps, or a scripted event."""
    if callable(script):
        script(harness)
        return
    for down, up, ticks in script:
        for key in up:
            press(harness, key, False)
        for key in down:
            press(harness, key, True)
        harness.tick(ticks)


def release_all(harness):
    scene = harness.scene
    for key in ('L', 'R', 'up', 'down', 'shift', 'ctrl'):
        held = (DIRECTIONS[key] in scene.held_directions if key in DIRECTIONS
                else getattr(scene, f'{key}_held'))
        if held:
            press(harness, key, False)


def settle(harness, limit=REST_TIMEOUT):
    """Ticks until the Prince stands, or dies; False when he never settles."""
    scene = harness.scene
    for _ in range(limit):
        if harness.goal() or not scene.combat.player.alive:
            return True
        motion = scene.terrain_motion
        if scene._is_resting() and not motion.falling and not scene.ledge_hanging:
            return True
        if scene.sequence_state.action == PRONE_REST:
            return True  # Lying under a blade waits for the next key.
        harness.tick()
    return False


def macros():
    """Named key scripts; each ends with every key released."""
    result = {}
    for side in 'LR':
        other = 'R' if side == 'L' else 'L'
        result[f'tap{side}'] = [((side,), (), 2), ((), (side,), 1)]
        result[f'step{side}'] = [(('shift', side), (), 12), ((), (side, 'shift'), 1)]
        result[f'nudge{side}'] = [(('shift', side), (), 3), ((), (side, 'shift'), 1)]
        for ticks in (5, 8, 11, 15, 20, 28):
            result[f'run{side}{ticks}'] = [((side,), (), ticks), ((), (side,), 1)]
        result[f'hop{side}'] = [(('up', side), (), 3), ((), ('up',), 12), ((), (side,), 1)]
        result[f'hopcatch{side}'] = [(('shift', 'up', side), (), 3), ((), ('up',), 14),
                                     ((), (side,), 4), (('up',), (), 24), ((), ('up', 'shift'), 1)]
        for ticks in (5, 7, 8, 9, 11, 13, 14, 16, 20):
            result[f'leap{side}{ticks}'] = [((side,), (), ticks), (('up',), (), 3), ((), ('up',), 14),
                                            ((), (side,), 1)]
            result[f'leapcatch{side}{ticks}'] = [((side,), (), ticks), (('shift', 'up'), (), 3),
                                                 ((), ('up',), 14), ((), (side,), 4),
                                                 (('up',), (), 24), ((), ('up', 'shift'), 1)]
        result[f'descend{side}'] = [((side,), (), 2), ((), (side,), 1), (('down',), (), 8),
                                    ((), ('down',), 1)]
        result[f'descendhang{side}'] = [(('shift', 'down'), (), 10), ((), ('down',), 10),
                                        ((side,), (), 8), (('up',), (), 24),
                                        ((), ('up', side, 'shift'), 1)]
        result[f'crawl{side}'] = [(('down',), (), 6), ((side,), (), 8), ((), (side, 'down'), 1)]
        for ticks in (4, 8, 16, 24, 32):
            result[f'creep{side}{ticks}'] = [((side,), (), ticks), ((), (side,), 1)]
        del other
    result['jump'] = [(('up',), (), 3), ((), ('up',), 1)]
    result['rise'] = [(('up',), (), 10), ((), ('up',), 1)]
    result['climb'] = [(('shift', 'up'), (), 34), ((), ('up', 'shift'), 1)]
    result['down'] = [(('down',), (), 10), ((), ('down',), 1)]
    result['hangdown'] = [(('shift', 'down'), (), 16), ((), ('down', 'shift'), 1)]
    result['wait'] = [((), (), 30)]
    for ticks in (4, 8, 12, 16, 20):
        result[f'wait{ticks}'] = [((), (), ticks)]
    result['altar'] = altar_death
    result['drink'] = [(('shift',), (), 26), ((), ('shift',), 1)]
    # Level 11's plate 12:4 gives about a hundred frames to reach gate 6:19,
    # with a blade just past it: a return without stopping, jumping twice
    # and catching the far ledge. Replays only: the search stops between moves.
    result['rushcatchL'] = [(('L',), (), 11), (('up',), (), 3), ((), ('up',), 9),
                            (('shift', 'up'), (), 3), ((), ('up',), 12), ((), (), 3),
                            (('up',), (), 26), ((), ('up', 'shift', 'L'), 1)]
    return result


MACROS = macros()
# Fewer run lengths for the search; a replay can name any of MACROS.
SEARCHED = {name: script for name, script in MACROS.items()
            if not name.startswith('rush')
            and not any(name.endswith(suffix) for suffix in ('R7', 'L7', 'R9', 'L9', 'R13', 'L13',
                                                             'R15', 'L15', 'R16', 'L16', 'R28', 'L28'))}


class Search:
    def __init__(self, number, *, peaceful=True, deadline=600.0, per_cell=4, waypoints=(), prefix=()):
        self.number = number
        self.harness = harness = Harness(number, peaceful=peaceful)
        harness.number = number
        self.deadline = deadline
        self.per_cell = per_cell
        self.order = itertools.count()
        self.heap = []
        self.seen = Counter()
        self.exact = set()
        self.cells = set()
        self.mech_seen = set()
        self.deaths = Counter()
        self.stuck = Counter()
        self.errors = Counter()
        self.error_samples = {}
        self.parents = []
        self.expansions = 0
        self.goal_node = None
        self.plate_press = Counter()
        self.mob_events = Counter()
        self.output = None
        self.waypoints = list(waypoints)
        self.prefix = list(prefix)
        self.stage_cells = set()
        self.stage_rooms = set()

    def key(self, info, mechanisms):
        return info['room'], info['row'], info['column'], info['facing'], mechanisms

    def admit(self, parent, name):
        harness = self.harness
        info = harness.player()
        mechanisms = harness.mechanisms()
        cell = info['room'], info['row'], info['column']
        new_cell = cell not in self.stage_cells
        new_room = info['room'] not in self.stage_rooms
        self.stage_cells.add(cell)
        self.stage_rooms.add(info['room'])
        new_mech = mechanisms not in self.mech_seen
        key = self.key(info, mechanisms)
        exact = key + (info['x'],)
        if exact in self.exact or (self.seen[key] >= self.per_cell and not new_cell and not new_mech):
            return None
        self.exact.add(exact)
        self.seen[key] += 1
        self.cells.add(cell)
        self.mech_seen.add(mechanisms)
        node = len(self.parents)
        self.parents.append((parent, name, info))
        depth = 0 if parent is None else self.parents[parent][2].get('depth', 0) + 1
        info['depth'] = depth
        saved = harness.save()
        rank = 0 if new_room else 1 if new_cell else 2 if new_mech else 3
        if self.reached_waypoint(info):
            # Search on from here alone: the waypoint is a hint, never a warp.
            print(f'L{self.number} waypoint {self.waypoints[0]} at node {node}', flush=True)
            self.waypoints = self.waypoints[1:]
            self.heap.clear()
            self.seen.clear()
            self.exact.clear()
            self.stage_rooms = set()
            self.stage_cells = set()
            rank = 0
        priority = (rank, self.seen[key], depth)
        heapq.heappush(self.heap, (priority, next(self.order), node, saved))
        return node

    def reached_waypoint(self, info):
        if not self.waypoints:
            return False
        target = self.waypoints[0]
        if target == 'altar':
            return self.harness.scene.game.caverns.altar == -1 and info['alive']
        if target.startswith('open:'):
            _name, room, cell = target.split(':')
            cell = int(cell)
            tile = self.harness.scene.level_map.tile(int(room) - 1, cell % 10, cell // 10)
            return tile.foreground & 255 >= (184 if tile.kind == 4 else 1)
        room, *rest = (int(part) for part in target.split(':'))
        return (info['room'] + 1 == room and (len(rest) < 1 or info['row'] == rest[0])
                and (len(rest) < 2 or info['column'] == rest[1]))

    def route(self, node):
        names = []
        while node is not None:
            parent, name, _info = self.parents[node]
            if name is not None:
                names.append(name)
            node = parent
        return names[::-1]

    def expand(self, node, saved):
        harness = self.harness
        for name, script in SEARCHED.items():
            harness.restore(saved)
            self.expansions += 1
            try:
                play(harness, script)
                release_all(harness)
                settled = settle(harness)
            except Exception as error:
                signature = traceback.format_exc(limit=-3)
                self.errors[repr(error)[:160]] += 1
                self.error_samples.setdefault(repr(error)[:160], dict(
                    route=self.route(node), macro=name, trace=signature))
                continue
            if harness.goal():
                self.goal_node = len(self.parents)
                self.parents.append((node, name, harness.player()))
                return True
            info = harness.player()
            if not info['alive']:
                self.deaths[info['room'], info['row'], info['column'], info['sequence']] += 1
                continue
            if not settled:
                self.stuck[info['room'], info['row'], info['column'], info['sequence'],
                           info['action']] += 1
                continue
            self.admit(node, name)
        return False

    def run(self):
        started = time.time()
        harness = self.harness
        settle(harness, 300)
        node = self.admit(None, None)
        for name in self.prefix:
            # A known route start; it is replayed with the rest of the route.
            play(harness, MACROS[name])
            release_all(harness)
            settle(harness)
            node = len(self.parents)
            self.parents.append((node - 1, name, harness.player()))
        if self.prefix:
            self.heap.clear()
            self.exact.clear()
            self.seen.clear()
            self.admit(node, None)
        last = started
        while self.heap and time.time() - started < self.deadline:
            _priority, _order, node, saved = heapq.heappop(self.heap)
            if self.expand(node, saved):
                break
            if time.time() - last > 30:
                last = time.time()
                print(f'L{self.number} {last - started:.0f}s nodes {len(self.parents)} open {len(self.heap)}'
                      f' cells {len(self.cells)} rooms {len({c[0] for c in self.cells})}'
                      f' mech {len(self.mech_seen)} runs {self.expansions} ticks {harness.ticks}'
                      f' errors {sum(self.errors.values())}', flush=True)
                if self.output is not None:
                    self.output.write_text(json.dumps(self.report(last - started), indent=1, default=str),
                                           encoding='utf8')
        return self.report(time.time() - started)

    def report(self, elapsed):
        rooms = sorted({cell[0] + 1 for cell in self.cells})
        result = dict(
            level=self.number, seconds=round(elapsed, 1), nodes=len(self.parents),
            open=len(self.heap), macro_runs=self.expansions, ticks=self.harness.ticks,
            reached_exit=self.goal_node is not None,
            route=self.route(self.goal_node) if self.goal_node is not None else None,
            rooms_native=rooms, cells=len(self.cells), mechanism_states=len(self.mech_seen),
            deaths=[[*key, count] for key, count in self.deaths.most_common(40)],
            stuck=[[*key, count] for key, count in self.stuck.most_common(40)],
            errors=[[key, count, self.error_samples[key]] for key, count in self.errors.most_common()],
        )
        result['visited_cells'] = sorted([room + 1, row, column] for room, row, column in self.cells)
        rooms = {}
        for node, (_parent, _name, info) in enumerate(self.parents):
            rooms.setdefault(f"{info['room'] + 1}:{info['row']}", node)
        result['first_routes'] = {key: self.route(node) for key, node in rooms.items()}
        return result


def replay(number, route, *, draw=True, peaceful=True, god=False, log=None):
    """Runs a route from a fresh load, without copied state."""
    harness = Harness(number, peaceful=peaceful, draw=draw, god=god)
    harness.number = number
    settle(harness, 300)
    trace = []
    for name in route:
        if log is not None:
            log(harness, name, 'start')
        play(harness, MACROS[name])
        release_all(harness)
        settle(harness)
        info = harness.player()
        if log is not None:
            log(harness, name, 'end')
        trace.append((name, info['room'] + 1, info['row'], info['column'], info['x'], info['life'],
                      info['alive']))
        if harness.goal() or not info['alive']:
            break
    return harness.goal(), trace, harness


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('level', type=int, choices=(10, 11, 12, 13))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline', type=float, default=600)
    parser.add_argument('--per-cell', type=int, default=4)
    parser.add_argument('--prefix', default='', help='Comma-separated macros that start the route')
    parser.add_argument('--waypoints', default='',
                        help='Comma-separated hints, in order: native ROOM, ROOM:ROW, ROOM:ROW:COLUMN, '
                             '"altar" or open:ROOM:CELL (a gate lifted clear)')
    args = parser.parse_args(argv)
    waypoints = [item for item in args.waypoints.split(',') if item]
    search = Search(args.level, deadline=args.deadline, per_cell=args.per_cell, waypoints=waypoints,
                    prefix=[item for item in args.prefix.split(',') if item])
    search.output = args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = search.run()
    if report['reached_exit']:
        args.output.write_text(json.dumps(report, indent=1, default=str), encoding='utf8')
        search.harness.close()
        reached, trace, harness = replay(args.level, report['route'], draw=False)
        harness.close()
        report['fresh_replay_reached_exit'] = reached
        report['fresh_replay_trace'] = trace
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1, default=str), encoding='utf8')
    print({key: report[key] for key in ('level', 'reached_exit', 'seconds', 'nodes', 'cells',
                                        'mechanism_states', 'rooms_native')}, flush=True)
    if report['errors']:
        print('ERRORS', json.dumps(report['errors'][:3], indent=1, default=str), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
