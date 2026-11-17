"""Random play through level 14 with the opponents on, looking for faults.

The known whole route (tests.test_final_whole_route) is replayed once and a
snapshot is kept after every move. Each episode restores one snapshot, may
change the Prince (life, a lost sword) and plays random moves from the route
tool's macros, the sword moves and waits. After every move it checks:

- an exception from the frame;
- a Prince who never comes to rest, or a cutscene that never ends;
- the opponents' bookkeeping: each figure listed once, in its own room, with
  a row of 0-2 and an X near its room;
- life outside 0..max;
- the final Jaffar repeating the same frames while the Prince stands still
  (a loop that never reaches its position or casts);
- a death that does not lead to a retry at the checkpoint;
- a save and load at that moment (the checkpoint) that fails.

Findings are faults to explain, not divergences in themselves: each needs the
original's code read before anything is changed. A finding records the
snapshot, the change and the moves, so it can be replayed exactly.
"""

import argparse
import json
import random
import sys
import tempfile
import time
import traceback
from pathlib import Path
from unittest.mock import patch

from tools import audit_temple_routes as audit

PALACE = (6, 7)
IDLE_TICKS = 240
CYCLE_WINDOW = 160
REST_LIMIT = 400
CUTSCENE_LIMIT = 3000


def sword_macros():
    from tests import test_final_whole_route as route

    keys = route.keys
    return {'stab': keys('c....c....'), 'sheathe': keys('d.....'),
            'drawstab': keys('c..........c..........'), 'draw': keys('c........'),
            'thirdcopy': route.third_copy,
            'turnL': [(('L',), (), 2), ((), ('L',), 4)], 'turnR': [(('R',), (), 2), ((), ('R',), 4)]}


RAW_KEYS = ('L', 'R', 'up', 'down', 'shift', 'ctrl')
RAW_COMBOS = (('L',), ('R',), ('up',), ('down',), ('shift',), ('R', 'up'), ('L', 'up'),
              ('R', 'shift'), ('L', 'shift'), ('R', 'down'), ('L', 'down'), ('up', 'shift'),
              ('down', 'shift'), ('ctrl',))


def raw_step(name):
    """'key:R+up:7:3' holds R and up for 7 ticks, then releases and waits 3:
    a player's own timing, not the route tool's."""
    _key, keys, held, wait = name.split(':')
    keys = tuple(keys.split('+'))
    return [(keys, (), int(held)), ((), keys, int(wait))]


def random_raw(draw):
    keys = draw.choice(RAW_COMBOS)
    return f"key:{'+'.join(keys)}:{draw.randint(1, 18)}:{draw.randint(0, 9)}"


def pool():
    names = sorted(name for name in audit.SEARCHED if name not in ('altar', 'wake'))
    return names + ['stab', 'sheathe', 'drawstab', 'draw', 'turnL', 'turnR'] * 3


class Explorer:
    def __init__(self, seed=1, raw=0.0):
        from tests import test_final_whole_route as route

        self.route_module = route
        self.macros = {**audit.MACROS, **sword_macros()}
        self.names = pool()
        self.draw = random.Random(seed)
        self.findings = []
        self.signatures = set()
        self.episodes = 0
        self.moves = 0
        self.snapshots = []
        self.harness = None
        self.deaths = {}
        self.endings = 0
        self.save_refused = 0
        self.raw = raw

    # Setup.

    def build(self):
        route = self.route_module
        settle = route.settle_after_spell(audit)
        self.settle = settle
        with patch.object(audit, 'settle', settle):
            harness = audit.Harness(14, peaceful=False)
            harness.number = 14
            player = harness.scene.combat.player
            player.life = player.max_life = 12
            settle(harness, 300)
            self.snapshots.append(('start', harness.save()))
            for index, name in enumerate(route.ROUTE):
                audit.play(harness, self.macros[name])
                audit.release_all(harness)
                settle(harness)
                self.snapshots.append((f'{index + 1}:{name}', harness.save()))
        self.harness = harness

    # Queries.

    def figures(self):
        combat = self.harness.scene.combat
        return [(room, figure) for room, (figures, _points) in combat.room_encounters.items()
                for figure in figures]

    def jaffar(self):
        for room, figure in self.figures():
            if figure.final_path:
                return figure
        return None

    def where(self):
        info = self.harness.player()
        return {key: info[key] for key in ('room', 'row', 'column', 'x', 'facing', 'action',
                                           'sequence', 'life', 'alive')}

    def jaffar_view(self, figure):
        state, info = figure.state, figure.final_info
        return (figure.room, figure.row, state.target_x, state.action,
                state.selected_sequence_id, state.facing,
                None if info is None else (info.mode, info.pos, info.prev))

    # Checks.

    def report(self, kind, detail, history):
        signature = (kind, detail.get('signature'))
        if signature in self.signatures:
            return
        self.signatures.add(signature)
        detail = {key: value for key, value in detail.items() if key != 'signature'}
        self.findings.append({'kind': kind, 'snapshot': history[0], 'change': history[1],
                              'steps': list(history[2]), 'prince': self.where(), **detail})
        print('FINDING', kind, history[0], history[1], history[2][-4:], detail, flush=True)

    def en_garde(self):
        """A drawn sword never rests; it counts when the Prince stays put."""
        harness, scene = self.harness, self.harness.scene
        if not scene.sword_drawn:
            return False
        before = harness.player()
        harness.tick(12)
        after = harness.player()
        return all(before[key] == after[key] for key in ('room', 'row', 'x', 'action'))

    def check_world(self, history):
        scene = self.harness.scene
        player = scene.combat.player
        seen = {}
        for room, figure in self.figures():
            if id(figure) in seen:
                self.report('figure listed twice', {'rooms': [seen[id(figure)], room],
                                                    'signature': 'twice'}, history)
            seen[id(figure)] = room
            if figure.room != room:
                self.report('figure in another room\'s list',
                            {'list': room, 'room': figure.room, 'signature': ('list', room)}, history)
            x = figure.state.target_x
            if figure.alive and (figure.row not in (0, 1, 2) or not -80 <= x <= 590):
                self.report('figure out of its room', {'room': room, 'row': figure.row, 'x': x,
                                                       'signature': ('out', room, figure.row)},
                            history)
        if not 0 <= player.life <= max(player.max_life, 1):
            self.report('life out of range', {'life': player.life, 'max': player.max_life,
                                              'signature': 'life'}, history)

    def idle_watch(self, history):
        """The Prince stands still; a Jaffar in view must not loop forever."""
        harness, scene = self.harness, self.harness.scene
        views = []
        for _ in range(IDLE_TICKS):
            if harness.goal() or not scene.combat.player.alive or scene.intro is not None:
                return
            harness.tick()
            figure = self.jaffar()
            if figure is None or figure.room not in PALACE:
                return
            in_view = figure.room == scene.combat.player.room or figure.bank_room == scene.combat.player.room
            views.append(self.jaffar_view(figure) if in_view else None)
        tail = views[-CYCLE_WINDOW:]
        if None in tail or len(set(tail)) <= 1:
            return
        for period in range(2, CYCLE_WINDOW // 3):
            if all(tail[index] == tail[index - period] for index in range(period, len(tail))):
                figure = self.jaffar()
                info = figure.final_info
                self.report('Jaffar loops while the Prince stands still',
                            {'period': period, 'frames': tail[-period:],
                             'signature': ('loop', figure.room, figure.row,
                                           info and (info.mode, info.pos, info.prev),
                                           tuple(sorted({view[3] for view in tail})))},
                            history)
                return

    def check_death(self, history):
        harness, scene = self.harness, self.harness.scene
        for _ in range(200):
            if scene.death.can_restart:
                break
            harness.tick()
        else:
            self.report('death never offers a retry', {'signature': 'retry'}, history)
            return False
        if not scene.restart_after_death():
            self.report('retry refused', {'signature': 'refused'}, history)
            return False
        for _ in range(CUTSCENE_LIMIT):
            if scene.intro is None:
                break
            harness.tick()
        harness.tick(2)
        if not scene.combat.player.alive:
            self.report('dead after the retry', {'signature': 'dead retry'}, history)
        return False

    def check_save(self, history):
        scene = self.harness.scene
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'explore.pop2save'
            from pop2.save_game import SaveGameError

            try:
                scene.save_game_to(path)
            except SaveGameError as error:
                # The menu refuses a save in some scenes (the spell, a death).
                if 'unavailable' in str(error):
                    self.save_refused += 1
                    return True
                raise
            try:
                scene.load_game_from(path)
                self.harness.tick(2)
            except Exception as error:  # noqa: BLE001 - every failure is a finding
                self.report('save and load failed', {'error': repr(error),
                                                     'trace': traceback.format_exc()[-1500:],
                                                     'signature': ('save', type(error).__name__)},
                            history)
                return False
        return True

    # Episodes.

    def change(self, kind):
        scene = self.harness.scene
        player = scene.combat.player
        if kind.startswith('life'):
            player.life = int(kind[4:])
        elif kind == 'no sword':
            player.sword_lost, player.sword_drawn = True, False

    def plan(self, length):
        """A random episode: a snapshot, a change and its steps (moves, with
        '@idle' and '@save' between them)."""
        label = self.draw.choice(self.snapshots)[0]
        kind = self.draw.choice(('none', 'none', 'life1', 'life2', 'life3', 'no sword', 'life12'))
        steps = []
        for _ in range(length):
            if self.raw and self.draw.random() < self.raw:
                for _ in range(self.draw.randint(1, 4)):
                    steps.append(random_raw(self.draw))
            else:
                steps.append(self.draw.choice(self.names))
            if self.draw.random() < 0.3:
                steps.append('@idle')
            if self.draw.random() < 0.05:
                steps.append('@save')
        return label, kind, steps

    def episode(self, label, kind, steps):
        """Plays one episode exactly; the same arguments replay it."""
        harness, scene = self.harness, self.harness.scene
        harness.restore(dict(self.snapshots)[label])
        self.change(kind)
        history = (label, kind, [])
        self.episodes += 1
        for name in steps:
            history[2].append(name)
            try:
                if name == '@idle':
                    self.idle_watch(history)
                    continue
                if name == '@save':
                    if not self.check_save(history):
                        return
                    continue
                self.moves += 1
                audit.play(harness, raw_step(name) if name.startswith('key:') else self.macros[name])
                audit.release_all(harness)
                rested = self.settle(harness, REST_LIMIT) or self.en_garde()
                cutscene = 0
                while scene.intro is not None and cutscene < CUTSCENE_LIMIT:
                    harness.tick()
                    cutscene += 1
                if scene.intro is not None:
                    self.report('cutscene never ends', {'signature': 'cutscene'}, history)
                    return
                if harness.goal() or getattr(scene.game.level, 'number', 14) != 14:
                    self.endings += 1
                    return
                self.check_world(history)
                if not scene.combat.player.alive:
                    room = self.where()['room']
                    self.deaths[room] = self.deaths.get(room, 0) + 1
                    self.check_death(history)
                    return
                if not rested:
                    self.report('Prince never comes to rest',
                                {'signature': ('rest', self.where()['room'], self.where()['action'])},
                                history)
                    return
            except Exception as error:  # noqa: BLE001 - every failure is a finding
                self.report('exception', {'error': repr(error),
                                          'trace': traceback.format_exc()[-2000:],
                                          'signature': ('exception', type(error).__name__,
                                                        traceback.format_exc()[-300:])},
                            history)
                return

    def run(self, deadline, length):
        start = time.monotonic()
        while time.monotonic() - start < deadline:
            self.episode(*self.plan(self.draw.randint(3, length)))
        return {'episodes': self.episodes, 'moves': self.moves,
                'seconds': round(time.monotonic() - start, 1), 'deaths_by_room': self.deaths,
                'endings': self.endings, 'save_refused': self.save_refused,
                'findings': self.findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline', type=float, default=600)
    parser.add_argument('--length', type=int, default=12)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--raw', type=float, default=0.0,
                        help='Chance of a burst of raw keys with random timing per move')
    parser.add_argument('--replay', type=Path, help='A report: replay its findings exactly')
    args = parser.parse_args(argv)
    explorer = Explorer(args.seed, args.raw)
    explorer.build()
    try:
        if args.replay:
            for finding in json.loads(args.replay.read_text(encoding='utf8'))['findings']:
                explorer.episode(finding['snapshot'], finding['change'], finding['steps'])
            report = {'episodes': explorer.episodes, 'moves': explorer.moves, 'seconds': 0,
                      'deaths_by_room': explorer.deaths, 'findings': explorer.findings}
        else:
            report = explorer.run(args.deadline, args.length)
    finally:
        explorer.harness.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1, default=str), encoding='utf8')
    print({key: report[key] for key in ('episodes', 'moves', 'seconds', 'deaths_by_room')},
          len(report['findings']), 'findings', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
