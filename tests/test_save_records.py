"""Every record a save can reach must pack, and older records must still load.

A save keeps the rebirth snapshot: its rooms' actors and the level's
mechanisms. Records once refused: the genie (levels 12), the palace figure's
path record (level 14), and any cavern save older than a later field.
"""

from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
import tempfile
import unittest
from typing import get_args, get_type_hints

from pop2.paths import ASSET_DIR


# Fields typed ``object`` (a forward reference or optional record) and the
# record each one holds. A new opaque field must be listed here, and its
# record must be in save_game.CLASSES.
OPAQUE = {
    ('Fighter', 'skeleton'): 'Skeleton',
    ('Fighter', 'ruins'): 'RuinsMind',
    ('Fighter', 'flame_sword'): 'FlameSword',
    ('Fighter', 'final_info'): 'PathInfo',
    ('CavernState', 'jinnee'): 'Jinnee',
}

# Fields without a default: every save has had them. A new field needs a
# default, or older saves would be refused.
REQUIRED = {
    'Checkpoint': {'slot', 'room', 'tile'},
    'Dart': {'room', 'x', 'y', 'row'},
    'FallingFloor': {'room', 'column', 'row', 'y'},
    'Fighter': {'runtime', 'life', 'max_life', 'room', 'row'},
    'GuardRoomRecord': {'sequence', 'cursor', 'life', 'armed'},
    'Jinnee': {'state', 'motion'},
    'OpponentGenerationPoint': {'room', 'index', 'skill', 'row', 'column', 'countdown',
                                'repeat_wait', 'alternate_row', 'remaining', 'max_between',
                                'flags', 'life_word'},
    'RebirthSnapshot': {'checkpoint', 'facing', 'max_life', 'room_encounters'},
    'RuinsMind': {'actor_type', 'kind', 'skill', 'slot'},
    'SequenceState': {'sequence_id'},
    'Skeleton': {'marker', 'timer', 'shakes'},
    'SkeletonRoomRecord': {'sequence', 'cursor', 'life', 'armed'},
    'TempleShadow': {'state', 'motion'},
    'TerrainMotion': {'room', 'row'},
    'WaterEntry': {'room', 'x', 'tumble'},
}


def saved_classes():
    from pop2 import save_game
    from pop2.combat import Fighter

    return {**save_game.CLASSES, 'Fighter': Fighter}


def annotation_types(annotation):
    yield annotation
    for argument in get_args(annotation):
        yield from annotation_types(argument)


class SavedRecordTypeTests(unittest.TestCase):
    def test_every_record_a_save_reaches_is_a_saved_class(self):
        from pop2 import save_game

        classes = saved_classes()
        opaque, pending, seen = set(), list(classes.values()), set()
        while pending:
            cls = pending.pop()
            if cls in seen:
                continue
            seen.add(cls)
            hints = get_type_hints(cls)
            for field in fields(cls):
                if field.name in save_game.OMIT.get(cls, ()):
                    continue
                for kind in annotation_types(hints[field.name]):
                    if kind is object:
                        opaque.add((cls.__name__, field.name))
                    elif isinstance(kind, type) and is_dataclass(kind):
                        self.assertIn(kind.__name__, classes, f'{cls.__name__}.{field.name}')
                        pending.append(kind)
        self.assertEqual(opaque, set(OPAQUE))
        for record in OPAQUE.values():
            self.assertIn(record, classes)

    def test_saved_records_add_fields_only_with_defaults(self):
        from pop2 import save_game

        required = {}
        for name, cls in saved_classes().items():
            names = {field.name for field in fields(cls)
                     if field.default is MISSING and field.default_factory is MISSING
                     and field.name not in save_game.OMIT.get(cls, ())}
            if names:
                required[name] = names
        self.assertEqual(required, REQUIRED)

    def test_the_palace_path_record_and_the_genie_pack(self):
        from pop2.final_path import PathInfo
        from pop2.jinnee import Jinnee
        from pop2.save_game import _pack
        from pop2.sequence_runtime import SequenceState
        from pop2.terrain import TerrainMotion

        self.assertEqual(_pack(PathInfo(2, 3, 1))['record'], 'PathInfo')
        kid = SequenceState(1, action=15, target_x=194, facing=1, level_kind=5)
        self.assertEqual(_pack(Jinnee.released(kid, TerrainMotion(22, 2)))['record'], 'Jinnee')


def imported(*names):
    return all((ASSET_DIR / name).is_file() for name in names)


@unittest.skipUnless(imported('Temple.rsrc', 'temple_level12.json', 'Final.rsrc', 'final_level14.json'),
                     'Imported temple and final levels required')
class CheckpointRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.game_session import GameResources

        cls.resources = GameResources.load()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'records.pop2save'

    def game_at_checkpoint(self, level):
        from pop2.game_session import GameSession
        from pop2.rebirth import RebirthSnapshot

        game = GameSession.load(self.resources, level)
        point = game.level.checkpoints[0]
        game.place(point.room, point.row, point.x, 1)
        return game, lambda: setattr(game, 'checkpoint', RebirthSnapshot.capture(point, game.combat))

    def round_trip(self, game, edit=None):
        from pop2.save_game import capture, read_save, write_save

        document = capture(game)
        if edit is not None:
            edit(document)
        write_save(self.path, document)
        return read_save(self.path, self.resources)[0]

    def test_a_cavern_save_from_before_the_later_fields_loads(self):
        # 43f1fe5 added CavernState.jinnee without making it optional; the
        # temple's rocks, trap doors and flame came the same way.
        later = {'jinnee', 'rocks', 'trapdoors', 'flame', 'final_scenery',
                 'final_scenery_drawn', 'final_scenery_room', 'final_escher'}

        def strip(document):
            record = document['resume']['checkpoint']['fields']['caverns']
            self.assertEqual(record['record'], 'CavernState')
            for name in later:
                record['fields'].pop(name)

        for level in (5, 12):
            with self.subTest(level=level):
                game, save_checkpoint = self.game_at_checkpoint(level)
                save_checkpoint()
                loaded = self.round_trip(game, strip)
                self.assertIsNone(loaded.caverns.jinnee)
                self.assertEqual(loaded.caverns.flame, 0)
                self.assertEqual(loaded.room_id, game.checkpoint.checkpoint.room)

    def test_a_checkpoint_taken_while_the_genie_runs_keeps_him(self):
        from pop2.jinnee import Jinnee

        game, save_checkpoint = self.game_at_checkpoint(12)
        kid = game.runtime.state
        game.caverns.jinnee = Jinnee.released(kid, game.motion)
        game.caverns.jinnee.motion.room = 22
        game.caverns.jinnee.state.cursor = 7
        save_checkpoint()
        loaded = self.round_trip(game).caverns.jinnee
        self.assertIsInstance(loaded, Jinnee)
        self.assertEqual((loaded.motion.room, loaded.state.cursor, loaded.state.target_x),
                         (22, 7, game.caverns.jinnee.state.target_x))

    def test_a_checkpoint_after_the_palace_figure_moved_keeps_its_path(self):
        from pop2.combat import Fighter
        from pop2.final_path import PathInfo
        from pop2.sequence_runtime import SequenceRuntime, SequenceState

        game, save_checkpoint = self.game_at_checkpoint(14)
        combat = game.combat
        state = SequenceState(2, action=15, target_x=300, actor_type=6, level_kind=6)
        figure = Fighter(SequenceRuntime(combat.sequences, state), 3, 3, 7, 0)
        figure.final_clone = True
        figure.final_info = PathInfo(mode=1, pos=3, prev=2)
        combat.room_encounters[7] = ([figure], [])
        save_checkpoint()
        loaded = self.round_trip(game)
        restored, = loaded.combat.room_encounters[7][0]
        self.assertEqual(restored.final_info, PathInfo(1, 3, 2))

    def test_a_checkpoint_never_keeps_the_kids_magic(self):
        # SetKidDefaults 2:5cf4 clears a5-0x5004 (2:5e56) at every level
        # start and rebirth.
        from pop2.final_magic import FinalMagic

        game, save_checkpoint = self.game_at_checkpoint(14)
        game.caverns.final_magic = FinalMagic(turns=3)
        save_checkpoint()
        self.assertNotIn('final_magic', vars(game.checkpoint.caverns))
        game.checkpoint.restore_world(game.combat)
        self.assertIsNone(game.caverns.final_magic)


@unittest.skipUnless(imported('Final.rsrc', 'final_level14.json'),
                     'Imported Macintosh final level required')
class FinalRetryTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        self.addCleanup(self.harness.close)
        self.scene = self.harness.scene

    def test_the_retry_starts_without_the_turns_made_before_the_checkpoint(self):
        from pop2.environments import environment_for
        from tests.test_final_magic import ShadowSceneTests

        scene = self.scene
        scene.jump_to_room(3, row=1, x=218, facing=1, redraw=False)
        self.harness.tick(1)
        scene.combat.player.life = scene.combat.player.max_life = 12
        ShadowSceneTests.turn(self, 3)
        self.assertEqual(scene.game.caverns.final_magic.turns, 3)
        scene.capture_rebirth_checkpoint(scene.checkpoints[0])
        environment_for(scene).kill_prince()
        self.harness.tick(20)
        self.assertTrue(scene.restart_after_death())
        self.harness.tick(1)
        self.assertEqual(environment_for(scene).magic().turns, 0)

    def test_a_save_after_the_palace_figure_ran_loads(self):
        from pop2.final_path import PathInfo

        scene = self.scene
        # Room 6's figures (port 5) join the rooms the checkpoint keeps.
        scene.jump_to_room(5, row=2, x=420, facing=0, redraw=False)
        self.harness.tick(1)
        scene.jump_to_room(3, row=1, x=236, facing=1, reset_guards=False, redraw=False)
        self.harness.tick(1)
        figure = next(actor for actors, _points in scene.combat.room_encounters.values()
                      for actor in actors)
        figure.final_info = PathInfo(2, 1, 0)
        scene.checkpoint = None
        self.harness.tick(2)
        self.assertIsNotNone(scene.checkpoint)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'palace.pop2save'
        scene.save_game_to(path)
        scene.load_game_from(path)
        self.assertEqual(scene.room_id, 3)
        loaded = [actor.final_info for actors, _points in scene.combat.room_encounters.values()
                  for actor in actors if actor.final_info is not None]
        self.assertEqual(loaded, [PathInfo(2, 1, 0)])


if __name__ == '__main__':
    unittest.main()
