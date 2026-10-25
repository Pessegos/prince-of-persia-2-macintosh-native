"""Versioned, resource-free native-port saves; never deserialize executable objects."""

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import base64
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import random
import tempfile
import types
from typing import get_args, get_origin, get_type_hints

from PIL import Image

from pop2.cavern_state import CavernState
from pop2.paths import USER_DATA_DIR
from pop2.bridge import Bridge
from pop2.carpet import Carpet
from pop2.darts import Dart, Darts
from pop2.desert_state import DesertState, Stone
from pop2.game_session import GameSession, level_sword_type
from pop2.gate_crush import GateCrush
from pop2.harbor import Harbor, WaterEntry
from pop2.lava import Lava, LavaPool
from pop2.loose_floors import FallingFloor, LooseFloors
from pop2.opponent_generation import OpponentGenerationPoint
from pop2.opponent_records import GuardRoomRecord
from pop2.potions import Potions
from pop2.pressure_plates import PressurePlates
from pop2.rebirth import Checkpoint, DeathState, RebirthSnapshot
from pop2.ruins_ai import RuinsMind
from pop2.story_progress import FRAMES_PER_MINUTE, StoryProgress
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.skeleton import Skeleton, SkeletonRoomRecord
from pop2.terrain import TerrainMotion
from pop2.scythes import SCYTHE_STATES, Scythes
from pop2.wall_spikes import WallSpikes


FORMAT = 'pop2-macintosh-native-save'
VERSION = 2
MAX_BYTES = 2 * 1024 * 1024
SAVE_DIRECTORY = (USER_DATA_DIR / 'saves' if USER_DATA_DIR is not None
                  else Path.home() / 'Saved Games' / 'PoP2 Macintosh Native')
CLASSES = {cls.__name__: cls for cls in (
    Bridge, Carpet, CavernState, Dart, Darts, DesertState, Stone, GateCrush, Harbor,
    WaterEntry, Lava, LavaPool, FallingFloor, LooseFloors, OpponentGenerationPoint,
    Potions, PressurePlates, Checkpoint, DeathState, RebirthSnapshot, SequenceState,
    Skeleton, SkeletonRoomRecord, GuardRoomRecord, TerrainMotion, WallSpikes, Scythes,
    RuinsMind,
)}
OMIT = {Lava: {'tables'}, LavaPool: {'tables'}, GateCrush: {'last_updated_at'},
        LooseFloors: {'shake_events'}, PressurePlates: {'slams', 'slam_sounds', 'gate_sounds'}}
GAME_FIELDS = ('room_id', 'checkpoint', 'death', 'complete', 'harbor', 'desert', 'caverns')
CONTROL_FIELDS = (
    'run_active', 'run_stop_requested', 'run_direction', 'run_start_x',
    'run_cycle_boundary_pending', 'running_jump_controls_cleared', 'sword_drawn',
    'sword_sheathing', 'step_cautious', 'step_warning_direction', 'shift_turn_direction',
    'ledge_hanging', 'ledge_climbing', 'ledge_climb_requested', 'ledge_action_consumed',
    'native_ledge', 'ledge_grip_delay', 'ledge_test_active', 'down_sheathe_consumed',
)


class SaveGameError(ValueError):
    pass


def _pack(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, SequenceRuntime):
        return {'runtime': _pack(value.state)}
    if is_dataclass(value) and (type(value).__name__ in CLASSES or type(value).__name__ == 'Fighter'):
        return {'record': type(value).__name__, 'fields': {
            field.name: _pack(getattr(value, field.name)) for field in fields(value)
            if field.name not in OMIT.get(type(value), ())}}
    if isinstance(value, dict):
        return {'map': [[_pack(key), _pack(item)] for key, item in value.items()]}
    if isinstance(value, (tuple, set)):
        return {'tuple' if isinstance(value, tuple) else 'set': [_pack(item) for item in value]}
    if isinstance(value, list):
        return [_pack(item) for item in value]
    raise SaveGameError(f'Unsupported save value: {type(value).__name__}')


def _matches(value, annotation):
    if annotation is object:
        return True
    origin, arguments = get_origin(annotation), get_args(annotation)
    if origin is types.UnionType:
        return any(_matches(value, choice) for choice in arguments)
    if origin in (list, tuple, dict, set):
        if not isinstance(value, origin):
            return False
        if not arguments:
            return True
        if origin is dict:
            return all(_matches(k, arguments[0]) and _matches(v, arguments[1]) for k, v in value.items())
        if origin is tuple and (len(arguments) < 2 or arguments[-1] is not Ellipsis):
            return len(value) == len(arguments) and all(_matches(v, t) for v, t in zip(value, arguments))
        return all(_matches(item, arguments[0]) for item in value)
    if annotation in (int, bool, str):
        return type(value) is annotation
    if annotation is float:
        return type(value) in (int, float)
    return isinstance(value, annotation)


def _unpack(value, resources, lava_tables, depth=0):
    if depth > 48:
        raise SaveGameError('Save nesting is too deep')
    if value is None or type(value) in (bool, int, str):
        if type(value) is str and len(value) > 8192:
            raise SaveGameError('Save string is too long')
        if type(value) is int and abs(value) > 2**64:
            raise SaveGameError('Save number is out of range')
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise SaveGameError('Invalid save number')
        return value
    decode = lambda item: _unpack(item, resources, lava_tables, depth + 1)
    if type(value) is list:
        return [decode(item) for item in value]
    if type(value) is not dict:
        raise SaveGameError('Invalid save value')
    if set(value) == {'runtime'}:
        state = decode(value['runtime'])
        if not isinstance(state, SequenceState):
            raise SaveGameError('Invalid animation state')
        return SequenceRuntime(resources.sequences, state)
    if set(value) in ({'tuple'}, {'set'}):
        kind = next(iter(value))
        if not isinstance(value[kind], list):
            raise SaveGameError('Invalid save collection')
        return (tuple if kind == 'tuple' else set)(decode(item) for item in value[kind])
    if set(value) == {'map'}:
        if not isinstance(value['map'], list):
            raise SaveGameError('Invalid save mapping')
        result = {}
        for pair in value['map']:
            if not isinstance(pair, list) or len(pair) != 2:
                raise SaveGameError('Invalid save mapping entry')
            key, item = map(decode, pair)
            if key in result:
                raise SaveGameError('Duplicate save mapping entry')
            result[key] = item
        return result
    if set(value) != {'record', 'fields'} or value['record'] not in (*CLASSES, 'Fighter'):
        raise SaveGameError('Unknown save record')
    if value['record'] == 'Fighter':
        # Actor records need imported AI data; progress-only saves and UI do not.
        from pop2.combat import Fighter

        cls = Fighter
    else:
        cls = CLASSES[value['record']]
    record = value['fields']
    allowed = {field.name for field in fields(cls)} - OMIT.get(cls, set())
    # Earlier snapshots predate turning-contact history and explicit NPC banks.
    optional = {'gate_contact_bounds'} if cls is TerrainMotion else set()
    if cls is GateCrush:
        optional.add('life_before_crush')
    if cls is RebirthSnapshot:
        optional.add('caverns')
    if cls is SequenceState:
        optional.add('floating')
    if cls.__name__ == 'Fighter':
        optional.update(('bank_room', 'bank_slot', 'guard_record', 'native_alive', 'sword_lost',
                         'ruins'))
    if cls is RebirthSnapshot:
        optional.add('ruins_rooms')
    if cls is Skeleton:
        optional.update(('room_record', 'native_alive', 'rise_song_pending'))
    if cls is SkeletonRoomRecord:
        optional.add('cell')
    if cls is Potions:
        optional.update(('fatal', 'float_timer', 'flip_timer'))
    if cls is CavernState:
        optional.update(('bridge', 'carpet', 'phew_countdown', 'scythes', 'alternate_entry',
                         'throne_done', 'throne_seen'))
    if cls is Bridge:
        optional.update(('tension_level', 'tension', 'marks', 'wobble'))
    if (not isinstance(record, dict) or set(record) - allowed
            or allowed - set(record) - optional):
        raise SaveGameError(f'Invalid {cls.__name__} fields')
    arguments = {name: decode(item) for name, item in record.items()}
    for name, annotation in get_type_hints(cls).items():
        if name in arguments and not _matches(arguments[name], annotation):
            raise SaveGameError(f'Invalid {cls.__name__}.{name}')
    if cls in (Lava, LavaPool):
        arguments['tables'] = lava_tables
    return cls(**arguments)


def _fighter_valid(actor, resources):
    from pop2.combat import Fighter

    if not isinstance(actor, Fighter) or not isinstance(actor.runtime, SequenceRuntime):
        raise SaveGameError('Invalid saved actor')
    state = actor.state
    if (type(actor.room) is not int or not 0 <= actor.room < 32 or not -2 <= actor.row <= 8
            or actor.bank_room is not None and not 0 <= actor.bank_room < 32
            or not 0 <= actor.bank_slot < 5
            or not 0 <= actor.life <= actor.max_life <= 120 or not 0 <= actor.skill < 12
            or actor.skeleton is not None and not isinstance(actor.skeleton, Skeleton)
            or state.facing not in (0, 1) or state.actor_type not in (0, 2, 4)
            or state.sequence_id not in resources.sequences
            or state.source_sequence_id not in resources.sequences and state.source_sequence_id != 0
            or not 0 <= state.cursor <= len(resources.sequences[state.sequence_id])
            or not 0 <= state.action <= (len(resources.frames) - 1 if state.actor_type == 0 else
                                         229 if state.actor_type == 4 else 254)
            or state.actor_type != 0 and not (149 <= state.action or 102 <= state.action <= 106)
            or abs(state.target_x) > 10000 or abs(state.current_y) > 10000):
        raise SaveGameError('Saved actor is out of range')
    record = actor.skeleton.room_record if actor.skeleton is not None else None
    if record is not None and (
            record.sequence not in resources.sequences
            or not 0 <= record.cursor < len(resources.sequences[record.sequence])
            or not 0 <= record.life <= actor.max_life
            or record.cell is not None and not -19 <= record.cell < 90):
        raise SaveGameError('Saved skeleton room record is out of range')
    record = actor.guard_record
    if record is not None and (
            actor.state.actor_type != 2 or record.sequence not in resources.sequences
            or not 0 <= record.cursor < len(resources.sequences[record.sequence])
            or not 0 <= record.life <= actor.max_life
            or record.cell is not None and not -19 <= record.cell < 90
            or abs(record.height) > 10000):
        raise SaveGameError('Saved guard room record is out of range')


def _ruins_rooms_valid(rooms, resources):
    from pop2.combat import Fighter

    if not isinstance(rooms, dict) or len(rooms) > 32:
        raise SaveGameError('Invalid saved ruins rooms')
    for room, actors in rooms.items():
        if type(room) is not int or not 0 <= room < 32 or not isinstance(actors, list) or len(actors) > 10:
            raise SaveGameError('Invalid saved ruins room')
        for actor in actors:
            if not isinstance(actor, Fighter) or not isinstance(actor.ruins, RuinsMind):
                raise SaveGameError('Invalid saved ruins actor')
            state, mind = actor.state, actor.ruins
            if (actor.room != room or not -2 <= actor.row <= 8
                    or state.actor_type not in (7, 8, 11) or mind.actor_type != state.actor_type
                    or not 0 <= actor.life <= actor.max_life <= 120 or not 0 <= mind.skill < 12
                    or state.facing not in (0, 1) or state.sequence_id not in resources.sequences
                    or not 0 <= state.cursor <= len(resources.sequences[state.sequence_id])
                    or not 149 <= state.action <= 289
                    or abs(state.target_x) > 10000 or abs(state.current_y) > 10000):
                raise SaveGameError('Saved ruins actor is out of range')


def capture_snapshot(game, controls=None, copy_verified=False):
    """Version-one fixture/compatibility encoder; new saves use capture()."""
    from pop2.enemy_profiles import QuickDrawRandom

    if (game.combat is None or not game.combat.player.alive or game.exit is not None
            or game.complete):
        raise SaveGameError('Save is unavailable during death or level transitions')
    combat = game.combat
    if isinstance(combat.rng, QuickDrawRandom):
        rng = ('quickdraw', combat.rng.seed)
    elif isinstance(combat.rng, random.Random):
        rng = ('python', combat.rng.getstate())
    else:
        raise SaveGameError('Unsupported enemy random generator')
    opening = ({key: getattr(game.opening, key) for key in ('active', 'phase', 'tick')}
               if game.opening is not None else None)
    state = {'game': {name: getattr(game, name) for name in GAME_FIELDS},
             'player': combat.player, 'rooms': combat.room_encounters,
             # Persistent Prince target (native +0x3a), not the frame opponent.
             'target': next((i for i, actor in enumerate(combat.guards)
                             if actor is getattr(combat, 'target_cache', combat.guard)), None),
             'clock': {name: getattr(combat, name)
                       for name in ('world_frame', 'parry_timer', 'advance_pause', 'attack_pause')},
             'rng': rng, 'random': random.getstate(), 'opening': opening,
             'npc_ids': {id(actor): (room, index) for room, (actors, _points) in combat.room_encounters.items()
                         for index, actor in enumerate(actors)},
             'controls': controls or {}, 'copy_verified': copy_verified}
    document = {'format': FORMAT, 'version': 1, 'level': game.level.number,
                'level_sha256': hashlib.sha256(game.level.data).hexdigest(), 'state': _pack(state)}
    _put_sword(document, game)
    return document


def _put_sword(document, game):
    # Optional: a sword picked up in a level that started without one.
    if game.sword_type != level_sword_type(game.level.number):
        document['sword_type'] = game.sword_type
    if game.ruins_entry != 1:
        document['ruins_entry'] = game.ruins_entry


def _load_session(resources, document):
    entry = _ruins_entry(document)
    if entry == 1:
        return GameSession.load(resources, document['level'])
    return GameSession.load(resources, document['level'], ruins_entry=entry)


def _ruins_entry(document):
    entry = document.get('ruins_entry', 1)
    if type(entry) is not int or entry not in (1, 2):
        raise SaveGameError('Invalid saved level entrance')
    return entry


def _take_sword(document, game):
    if 'sword_type' in document:
        if type(document['sword_type']) is not int or document['sword_type'] not in (-1, 1, 2, 3):
            raise SaveGameError('Invalid saved sword')
        game.sword_type = document['sword_type']


def write_save(path, data):
    payload = (json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n').encode('ascii')
    if len(payload) > MAX_BYTES:
        raise SaveGameError('Save exceeds the size limit')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.pop2-save-', delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path


def read_snapshot(path, resources):
    random_before = random.getstate()
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise SaveGameError('Save exceeds the size limit')
        document = json.loads(raw)
        if (not isinstance(document, dict) or document.get('format') != FORMAT
                or type(document.get('version')) is not int or document['version'] != 1
                or type(document.get('level')) is not int or document['level'] not in (1, 2, 3, 4, 5, 6, 7, 8, 9)):
            raise SaveGameError('Unsupported save format or version')
        game = _load_session(resources, document)
        if document.get('level_sha256') != hashlib.sha256(game.level.data).hexdigest():
            raise SaveGameError('Save belongs to different original game files')
        _take_sword(document, game)
        from pop2.caverns import cavern_assets
        from pop2.enemy_profiles import QuickDrawRandom

        tables = cavern_assets(game.level.number)[0]['lava'] if game.level.kind == 3 else None
        saved = _unpack(document['state'], resources, tables)
        if set(saved) != {'game', 'player', 'rooms', 'target', 'clock', 'rng', 'random',
                          'opening', 'npc_ids', 'controls', 'copy_verified'}:
            raise SaveGameError('Invalid saved session')
        if not isinstance(saved['game'], dict) or set(saved['game']) != set(GAME_FIELDS):
            raise SaveGameError('Invalid world fields')
        for name, value in saved['game'].items():
            setattr(game, name, value)
        if (not isinstance(game.death, DeathState) or type(game.complete) is not bool
                or game.checkpoint is not None and not isinstance(game.checkpoint, RebirthSnapshot)
                or game.harbor is not None and not isinstance(game.harbor, Harbor)
                or game.desert is not None and not isinstance(game.desert, DesertState)):
            raise SaveGameError('Invalid saved world')
        combat = game.combat
        combat.player = saved['player']
        _fighter_valid(combat.player, resources)
        if not combat.player.alive or combat.player.state.actor_type != 0 or game.complete:
            raise SaveGameError('Save does not contain a playable Prince')
        if not isinstance(saved['rooms'], dict) or len(saved['rooms']) > 32:
            raise SaveGameError('Invalid saved rooms')
        combat.room_encounters = saved['rooms']
        for room, entry in combat.room_encounters.items():
            if type(room) is not int or not 0 <= room < 32 or not isinstance(entry, tuple) or len(entry) != 2:
                raise SaveGameError('Invalid room encounter')
            actors, points = entry
            if not isinstance(actors, list) or not isinstance(points, list) or len(actors) > 5 or len(points) > 3:
                raise SaveGameError('Invalid room actors')
            for actor in actors:
                _fighter_valid(actor, resources)
                if actor.room != room or actor.state.actor_type not in (2, 4):
                    raise SaveGameError('Invalid enemy room')
            if any(not isinstance(point, OpponentGenerationPoint) for point in points):
                raise SaveGameError('Invalid generation point')
        if (type(game.room_id) is not int or game.room_id != combat.player.room
                or game.room_id not in combat.room_encounters):
            raise SaveGameError('Invalid current room')
        combat.guards, combat.generation_points = combat.room_encounters[game.room_id]
        target = saved['target']
        if target is not None and (type(target) is not int or not 0 <= target < len(combat.guards)):
            raise SaveGameError('Invalid combat target')
        combat.guard = combat.guards[target] if target is not None else None
        if set(saved['clock']) != {'world_frame', 'parry_timer', 'advance_pause', 'attack_pause'}:
            raise SaveGameError('Invalid simulation clock')
        for name, value in saved['clock'].items():
            if type(value) is not int or not 0 <= value < 2**32:
                raise SaveGameError('Invalid simulation clock value')
            setattr(combat, name, value)
        kind, rng = saved['rng']
        if kind == 'quickdraw':
            combat.rng = QuickDrawRandom(rng)
        elif kind == 'python':
            combat.rng = random.Random()
            combat.rng.setstate(rng)
        else:
            raise SaveGameError('Invalid enemy random state')
        random.Random().setstate(saved['random'])
        game.runtime = combat.player.runtime
        game.motion = combat.player.terrain_motion
        if not isinstance(game.motion, TerrainMotion) or game.motion.room != game.room_id:
            raise SaveGameError('Invalid saved movement')
        game.level_map.caverns, game.level_map.desert = game.caverns, game.desert
        if game.caverns is not None and not isinstance(game.caverns, CavernState):
            raise SaveGameError('Invalid cavern state')
        if game.level.kind == 3 and game.caverns is None:
            raise SaveGameError('Missing cavern state')
        bridge = game.caverns.bridge if game.caverns is not None else None
        if bridge is not None and (
                type(bridge.state) is not int or not -1 <= bridge.state <= 3
                or type(bridge.counter) is not int or abs(bridge.counter) > 2**31
                or any(type(column) is not int or not 3 <= column <= 7 or kind not in (1, 2)
                       for column, kind in bridge.pieces.items())
                or any(not isinstance(plank, list) or len(plank) != 2
                       or plank[0] not in bridge.pieces or type(plank[1]) is not int
                       or not 0 <= plank[1] <= 13 for plank in bridge.planks)
                or any(song != 121 for song in bridge.songs)
                or type(bridge.marks) is not int or not 0 <= bridge.marks <= 0xff
                or any(column not in range(1, 9) or nibble not in (1, 2)
                       for column, nibble in bridge.wobble.items())):
            raise SaveGameError('Invalid bridge state')
        carpet = game.caverns.carpet if game.caverns is not None else None
        if carpet is not None and (type(carpet.counter) is not int or not 0 <= carpet.counter < 2**31
                                   or type(carpet.crashed) is not bool):
            raise SaveGameError('Invalid carpet state')
        scythes = game.caverns.scythes if game.caverns is not None else None
        if scythes is not None and (
                any(not (isinstance(key, tuple) and len(key) == 2 and 0 <= key[0] < 32 and 0 <= key[1] < 30
                         and type(value) is int and value in SCYTHE_STATES)
                    for key, value in scythes.foreground.items())
                or any(key not in scythes.foreground for key in scythes.active)):
            raise SaveGameError('Invalid scythe state')
        if game.opening is not None:
            opening = saved['opening']
            if (not isinstance(opening, dict) or set(opening) != {'active', 'phase', 'tick'}
                    or type(opening['active']) is not bool or type(opening['tick']) is not int
                    or not 0 <= opening['tick'] < 2**32
                    or opening['phase'] not in ('window', 'fall', 'landing', 'rise', 'done')):
                raise SaveGameError('Invalid opening state')
            game.opening.runtime, game.opening.state = game.runtime, game.runtime.state
            game.opening.__dict__.update(opening)
        if game.harbor is not None:
            game.harbor.water = {
                (0 if key == 0 else id(combat.room_encounters[saved['npc_ids'][key][0]][0][saved['npc_ids'][key][1]])): value
                for key, value in game.harbor.water.items()}
        if not isinstance(saved['controls'], dict) or set(saved['controls']) - set(CONTROL_FIELDS):
            raise SaveGameError('Invalid saved controls')
        numeric_controls = {'run_direction', 'run_start_x', 'step_warning_direction',
                            'shift_turn_direction', 'ledge_grip_delay'}
        for name, value in saved['controls'].items():
            if name in numeric_controls:
                if not (name == 'run_start_x' and value is None) and type(value) is not int:
                    raise SaveGameError('Invalid saved movement control')
            elif type(value) is not bool:
                raise SaveGameError('Invalid saved control flag')
        if type(saved['copy_verified']) is not bool:
            raise SaveGameError('Invalid copy-protection state')
        retained = document.get('retained_background', [])
        if not isinstance(retained, list) or len(retained) > 510 * 365:
            raise SaveGameError('Invalid retained scenery')
        for pixel in retained:
            if (not isinstance(pixel, list) or len(pixel) != 6
                    or any(type(channel) is not int for channel in pixel)
                    or not 0 <= pixel[0] < 510 or not 0 <= pixel[1] < 365
                    or any(not 0 <= channel <= 255 for channel in pixel[2:])):
                raise SaveGameError('Invalid retained scenery pixel')
        saved['retained_background'] = retained
        return game, saved
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, RecursionError) as error:
        raise SaveGameError(f'Invalid or incompatible save: {error}') from error
    finally:
        random.setstate(random_before)


def encode_preview(viewport):
    output = BytesIO()
    viewport.crop((1, 0, 511, 365)).convert('RGB').save(output, format='PNG')
    return base64.b64encode(output.getvalue()).decode('ascii')


def decode_preview(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 1024 * 1024:
        raise SaveGameError('Invalid save preview')
    try:
        with Image.open(BytesIO(base64.b64decode(value, validate=True))) as image:
            if image.format != 'PNG' or image.size not in ((224, 160), (510, 365)):
                raise SaveGameError('Invalid save preview size')
            return image.convert('RGB')
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise SaveGameError('Invalid save preview') from error


def capture(game, controls=None, copy_verified=False):
    if (game.combat is None or not game.combat.player.alive or game.exit is not None
            or game.complete):
        raise SaveGameError('Save is unavailable during death or level transitions')
    checkpoint = game.checkpoint
    max_life = checkpoint.max_life if checkpoint is not None else game.combat.player.max_life
    if checkpoint is None and game.caverns is not None:
        initial = game.caverns.potions.starting_max_life
        if initial is not None:
            max_life = initial
    document = {'format': FORMAT, 'version': VERSION, 'level': game.level.number,
                'level_sha256': hashlib.sha256(game.level.data).hexdigest(),
                'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'resume': {'checkpoint': _pack(checkpoint), 'max_life': max_life},
                'copy_verified': bool(copy_verified)}
    _put_sword(document, game)
    story = game.story
    if story.clock_started or story != StoryProgress():
        # Optional: older saves and untouched campaigns omit the story clock.
        document['story'] = {'minutes': story.minutes, 'frames_remaining': story.frames_remaining,
                             'tree_stage': story.tree_stage}
    return document


def _story(value):
    if (not isinstance(value, dict) or set(value) != {'minutes', 'frames_remaining', 'tree_stage'}
            or any(type(item) is not int for item in value.values())
            or not 0 <= value['minutes'] <= 75
            or not 1 <= value['frames_remaining'] <= FRAMES_PER_MINUTE
            or not -1 <= value['tree_stage'] <= 7):
        raise SaveGameError('Invalid saved story clock')
    return StoryProgress(**value)


def read_document(path):
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise SaveGameError('Save exceeds the size limit')
        document = json.loads(raw)
        if (not isinstance(document, dict) or document.get('format') != FORMAT
                or type(document.get('version')) is not int or document['version'] not in (1, VERSION)
                or type(document.get('level')) is not int or document['level'] not in (1, 2, 3, 4, 5, 6, 7, 8, 9)):
            raise SaveGameError('Unsupported save format or version')
        return document
    except (ValueError, RecursionError) as error:
        raise SaveGameError(f'Invalid or incompatible save: {error}') from error


def read_save(path, resources):
    random_before = random.getstate()
    try:
        document = read_document(path)
        if document['version'] == 1:
            legacy, state = read_snapshot(path, resources)
            document = capture(legacy, copy_verified=state['copy_verified'])
        return restore_progress(document, resources)
    finally:
        random.setstate(random_before)


def save_name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 48 or not value.isprintable():
        raise SaveGameError('Invalid save name')
    return value.strip()


def restore_progress(document, resources):
    random_before = random.getstate()
    try:
        if set(document) - {'format', 'version', 'level', 'level_sha256', 'created_at',
                            'resume', 'copy_verified', 'preview', 'name', 'preview_at_resume', 'preview_version',
                            'story', 'sword_type', 'ruins_entry'}:
            raise SaveGameError('Unknown saved progress fields')
        if 'name' in document:
            save_name(document['name'])
        if 'preview_at_resume' in document and type(document['preview_at_resume']) is not bool:
            raise SaveGameError('Invalid save preview location')
        if 'preview_version' in document and (type(document['preview_version']) is not int
                                              or not 1 <= document['preview_version'] <= 1000):
            raise SaveGameError('Invalid save preview version')
        game = _load_session(resources, document)
        if document.get('level_sha256') != hashlib.sha256(game.level.data).hexdigest():
            raise SaveGameError('Save belongs to different original game files')
        _take_sword(document, game)
        resume = document['resume']
        if (not isinstance(resume, dict) or set(resume) != {'checkpoint', 'max_life'}
                or type(resume['max_life']) is not int or not 1 <= resume['max_life'] <= 12
                or type(document['copy_verified']) is not bool):
            raise SaveGameError('Invalid saved progress')
        decode_preview(document.get('preview'))
        snapshot = _unpack(resume['checkpoint'], resources, None)
        if snapshot is not None:
            if (not isinstance(snapshot, RebirthSnapshot)
                    or snapshot.checkpoint not in game.level.checkpoints
                    or type(snapshot.facing) is not int or snapshot.facing not in (0, 1)
                    or snapshot.max_life != resume['max_life']):
                raise SaveGameError('Invalid checkpoint')
            # Reuse the rebirth world, never the Prince's live position or motion.
            if not isinstance(snapshot.room_encounters, dict) or len(snapshot.room_encounters) > 32:
                raise SaveGameError('Invalid checkpoint world')
            for room, entry in snapshot.room_encounters.items():
                if (type(room) is not int or not 0 <= room < 32 or not isinstance(entry, tuple)
                        or len(entry) != 2 or not isinstance(entry[0], list) or len(entry[0]) > 5
                        or not isinstance(entry[1], list) or len(entry[1]) > 3):
                    raise SaveGameError('Invalid checkpoint room')
                for actor in entry[0]:
                    _fighter_valid(actor, resources)
                    if actor.room != room or actor.state.actor_type not in (2, 4):
                        raise SaveGameError('Invalid checkpoint opponent')
                if any(not isinstance(point, OpponentGenerationPoint) for point in entry[1]):
                    raise SaveGameError('Invalid checkpoint generation point')
            if snapshot.ruins_rooms is not None:
                _ruins_rooms_valid(snapshot.ruins_rooms, resources)
            game.checkpoint = snapshot
            snapshot.restore_world(game.combat)
            point = snapshot.checkpoint
            game.place(point.room, point.row, point.x, snapshot.facing,
                       reset_guards=False, preserve_checkpoint=True)
        game.arm_prince()
        game.combat.player.life = game.combat.player.max_life = resume['max_life']
        if 'story' in document:
            game.story = _story(document['story'])
        return game, {'copy_verified': document['copy_verified']}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, RecursionError) as error:
        raise SaveGameError(f'Invalid or incompatible save: {error}') from error
    finally:
        random.setstate(random_before)
