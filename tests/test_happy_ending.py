"""Macintosh NIS 11 (HappyEnding 15:3c76) and the Hall of Fame (CODE 2)."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pop2.audio import scene_sound_key
from pop2.paths import ASSET_DIR
from pop2.hall_of_fame import (
    MAX_ENTRIES, NAME_LIMIT, Entry, HallOfFamePage, add_player, load_hall, save_hall,
)


FORKS = Path(__file__).resolve().parents[2] / 'PoP2-Mac-Code-Recovery' / 'resource_forks'
ORIGINAL = all((FORKS / name).is_file() for name in (
    'Prince of Persia 2.bin', 'NIS.rsrc.bin', 'Happy.rsrc.bin',
    'Prince.rsrc.bin', 'Kid.rsrc.bin', 'Title.rsrc.bin'))


@unittest.skipUnless(ORIGINAL, 'Preserved Macintosh resource forks required')
class HappyEndingRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.extract_intro import recover_happy

        cls.operations, cls.table = recover_happy(*(
            (FORKS / name).read_bytes() for name in (
                'Prince of Persia 2.bin', 'NIS.rsrc.bin', 'Happy.rsrc.bin')))

    def test_coordinator_bedroom_and_epilogue_frames(self):
        operations, table = self.operations, self.table
        self.assertFalse(any(item['op'] == 'animation' for item in operations))
        # ANI 30004 has 286 frames, each handed to HappyFunc 15:411a; the
        # table keeps those whose callback draws or sounds (142.. after cue 102).
        self.assertTrue(set(table) <= set(range(286)))
        self.assertTrue({2, 142, 182, 193} <= set(table))
        self.assertEqual(sum(item['op'] == 'happy_frame' for item in operations), 286)
        self.assertEqual([item['op'] for item in operations].count('happy_end'), 1)
        # TransFuncSetCTABframe1 15:09c0: the bedroom's first frame at 0x51 percent.
        self.assertIn('brightness', {item['op'] for item in operations})
        sounds = {item['args'][0] for item in operations if item['op'] == 'sound'}
        self.assertIn(30010, sounds)
        # The closing song starts from the epilogue's frame 182.
        self.assertIn({'op': 'sound', 'args': [30020, 0]},
                      [{'op': item['op'], 'args': item['args']} for item in table[182]])
        # The drawing colour of the panels comes from SetForeColor 17:0eae.
        self.assertTrue(any(item['op'] == 'fill' for item in operations))

    def play(self):
        from pop2.intro import IntroAssets, IntroPlayer

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        destination = Path(directory.name)
        for name in ('NIS', 'Happy', 'Prince', 'Kid', 'Title'):
            (destination / f'{name}.rsrc').write_bytes((FORKS / f'{name}.rsrc.bin').read_bytes())
        sounds = [*self.operations, *(item for items in self.table.values() for item in items),
                  *({'op': 'sound', 'args': [30004 + line, 1]} for line in range(5))]
        audio = {scene_sound_key(item['args'][0], item['args'][1]): {'duration': 1.0, 'markers': {}}
                 for item in sounds if item['op'] == 'sound'}
        # The song's cue markers as the importer reads them (a..f = 97..102).
        audio[scene_sound_key(30010, 0)] = {'duration': 48.5, 'markers': dict(zip(
            'abcdef', (2.73, 6.55, 13.36, 22.09, 24.55, 40.31)))}
        # A short closing song: HappyFunc's -1 past frame 182 (15:447e-4496)
        # ends the animation before its last frames.
        audio[scene_sound_key(30020, 0)] = {'duration': 1.0, 'markers': {}}
        (destination / 'happy.json').write_text(json.dumps({
            'schema': 1, 'kind': 'happy', 'resource_files': {'Happy.rsrc': 1000000},
            'operations': self.operations,
            'happy_frames': {str(frame): items for frame, items in self.table.items()},
            'audio': audio}), encoding='ascii')
        assets = IntroAssets(directory=destination, program_name='happy.json')
        return IntroPlayer(assets)

    def test_dialog_lines_follow_their_voices_and_the_song_ends_the_scene(self):
        player = self.play()
        lines, voices = [], []
        text, sound = player.text, player.sound

        def record_text(resource, index, *args, dialog=False):
            if dialog:
                lines.append((resource, index))
            return text(resource, index, *args, dialog=dialog)

        def record_sound(cue, kind, *args):
            if kind == 1 and 30004 <= cue <= 30008:
                voices.append(cue)
            return sound(cue, kind, *args)

        frames = []
        happy_frame = player.happy_frame

        def record_frame(frame):
            frames.append(frame)
            return happy_frame(frame)

        with (patch.object(player, 'text', record_text), patch.object(player, 'sound', record_sound),
              patch.object(player, 'happy_frame', record_frame)):
            player.advance(120)
        self.assertTrue(player.done)
        # HappyDialog 15:44b0: text 30000 entries 4..8, each with its voice,
        # then the panel is cleared.
        self.assertEqual(lines, [(30000, 4 + line) for line in range(5)] + [(0, 0)])
        self.assertEqual(voices, list(range(30004, 30009)))
        self.assertEqual(player.happy['line'], 100)
        self.assertTrue(player.happy['ending'])
        self.assertLess(max(frames), 200)
        self.assertIsNotNone(player.frame().getbbox())


class HallOfFameTableTests(unittest.TestCase):
    def table(self, *minutes):
        return [Entry(f'P{index}', value) for index, value in enumerate(minutes)]

    def test_a_score_goes_before_the_first_it_equals_or_beats(self):
        entries, position = add_player(self.table(60, 40, 20), 40)
        self.assertEqual(position, 1)
        self.assertEqual([entry.minutes for entry in entries], [60, 40, 40, 20])
        self.assertEqual(add_player([], 3), ([Entry('', 3)], 0))

    def test_a_full_table_drops_its_last_and_a_low_score_still_takes_fifth(self):
        full = self.table(50, 40, 30, 20, 10)
        entries, position = add_player(full, 35)
        self.assertEqual((position, [entry.minutes for entry in entries]), (2, [50, 40, 35, 30, 20]))
        entries, position = add_player(full, 1)
        self.assertEqual((position, len(entries), entries[-1].minutes), (4, MAX_ENTRIES, 1))

    def test_names_refuse_angle_brackets_and_stay_short(self):
        page = HallOfFamePage.after_victory(12, path=Path(tempfile.gettempdir()) / 'missing-hall.json')
        self.assertTrue(page.editing)
        for char in 'A<b>' + 'x' * 40:
            page.key(char, char)
        self.assertEqual(page.draft, 'Ab' + 'x' * (NAME_LIMIT - 2))
        page.key('Home')
        page.key('Delete')
        self.assertEqual(page.draft[:2], 'bx')

    def test_return_asks_and_yes_names_the_row(self):
        page = HallOfFamePage(self.table(30), None)
        page = HallOfFamePage(*add_player(page.entries, 45))
        for char in 'Kid':
            page.key(char, char)
        self.assertEqual(page.key('Return'), 'changed')
        self.assertTrue(page.confirming)
        page.key('Left')
        self.assertEqual(page.activate(), 'changed')     # No: keep typing
        self.assertTrue(page.editing)
        page.key('Return')
        self.assertEqual(page.activate(), 'hall_saved')
        self.assertEqual(page.table(), [Entry('Kid', 45), Entry('P0', 30)])
        self.assertEqual(page.key('Return'), 'hall_close')

    def test_an_empty_name_is_not_written(self):
        page = HallOfFamePage(*add_player(self.table(30), 45))
        self.assertEqual(page.key('Return'), 'hall_close')
        self.assertEqual(page.table(), self.table(30))

    def test_saved_table_round_trips_and_bad_files_are_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hall.json'
            save_hall(self.table(9, 8), path)
            self.assertEqual(load_hall(path), self.table(9, 8))
            path.write_text(json.dumps({'entries': [{'name': 'A', 'minutes': 1}] * 6}), encoding='utf-8')
            self.assertEqual(load_hall(path), [])
            path.write_text('not json', encoding='utf-8')
            self.assertEqual(load_hall(path), [])
            path.write_text(json.dumps({'entries': [{'name': 'A', 'minutes': True}]}), encoding='utf-8')
            self.assertEqual(load_hall(path), [])


class HallOfFameMenuTests(unittest.TestCase):
    def test_menu_entry_is_enabled_and_delegates_typing(self):
        from pop2.game_menu import GameMenu

        menu = GameMenu()
        item = next(item for item in menu.items if item.action == 'hall')
        self.assertTrue(item.enabled)
        menu.show_page('hall')
        menu.hall_page = HallOfFamePage(*add_player([], 20))
        self.assertEqual(menu.key('a', char='a'), 'changed')
        self.assertEqual(menu.key('v', char='v', control=True), 'changed')
        self.assertEqual(menu.hall_page.draft, 'a')
        self.assertEqual(menu.activate(), 'changed')
        self.assertTrue(menu.hall_page.confirming)
        yes = menu.BUTTONS[1]
        self.assertEqual(menu.click((yes[0] + yes[2]) // 2, (yes[1] + yes[3]) // 2), 'hall_saved')
        button = menu.HALL_BUTTON
        self.assertEqual(menu.click((button[0] + button[2]) // 2, (button[1] + button[3]) // 2), 'hall_close')

    def test_viewing_page_closes_with_escape(self):
        from pop2.game_menu import GameMenu

        menu = GameMenu(page='hall', return_to_menu=False)
        menu.hall_page = HallOfFamePage([Entry('A', 3)])
        self.assertFalse(menu.hall_page.editing)
        self.assertEqual(menu.key('Escape'), 'hall_close')


class FinalVictoryFlowTests(unittest.TestCase):
    def scene(self, minutes):
        from types import SimpleNamespace

        calls = []
        scene = SimpleNamespace(
            game=SimpleNamespace(exit=object(), story=SimpleNamespace(minutes=minutes)),
            level_complete=True,
            start_story_scene=lambda name, finish, status: calls.append(('nis', name)) or (
                finish() or True),
            start_intro=lambda: calls.append(('intro',)),
            open_hall_of_fame=lambda value: calls.append(('hall', value)))
        return scene, calls

    def test_victory_plays_nis_eleven_then_the_hall_with_the_minutes_left(self):
        from pop2.environments import Final

        scene, calls = self.scene(37)
        Final(scene).finish_exit()
        self.assertEqual(calls, [('nis', 'happy.json'), ('intro',), ('hall', 37)])
        self.assertIsNone(scene.game.exit)

    def test_without_minutes_the_presentation_restarts_at_once(self):
        from pop2.environments import Final

        scene, calls = self.scene(0)
        Final(scene).finish_exit()
        self.assertEqual(calls, [('intro',)])

    def test_missing_scene_still_reaches_the_hall(self):
        from pop2.environments import Final

        scene, calls = self.scene(5)
        scene.start_story_scene = lambda *_args: False
        Final(scene).finish_exit()
        self.assertEqual(calls, [('intro',), ('hall', 5)])


INSTALLED = all((ASSET_DIR / name).is_file() for name in ('Final.rsrc', 'final_level14.json', 'intro.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final scenery required')
class HallOfFameWindowTests(unittest.TestCase):
    def setUp(self):
        from pop2.scene_prototype import ScenePrototype

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'hall.json'
        hall_path = patch('pop2.hall_of_fame.HALL_PATH', self.path)
        hall_path.start()
        self.addCleanup(hall_path.stop)
        self.scene = ScenePrototype(peaceful=True, level_number=14)
        self.scene.root.withdraw()
        if self.scene.animation_after_id is not None:
            self.scene.root.after_cancel(self.scene.animation_after_id)
            self.scene.animation_after_id = None

    def tearDown(self):
        self.scene.root.destroy()

    def press(self, keysym, char=None):
        from types import SimpleNamespace

        event = SimpleNamespace(keysym=keysym, state=0, char=keysym if char is None else char)
        self.scene.dev_key_press(event)
        self.scene.dev_key_release(event)

    def test_victory_names_the_row_saves_and_starts_the_presentation(self):
        scene = self.scene
        save_hall([Entry('Old', 50), Entry('Low', 3)], self.path)
        scene.start_intro()
        scene.open_hall_of_fame(20)
        self.assertEqual(scene.game_menu.page, 'hall')
        self.assertEqual(scene.input_context(), 'text')
        # Letters that are game shortcuts elsewhere are only text here.
        for char in 'Kid h':
            self.press('space' if char == ' ' else char, char)
        self.assertEqual(scene.game_menu.hall_page.draft, 'Kid h')
        self.press('Return')
        self.assertTrue(scene.game_menu.hall_page.confirming)
        self.press('Return')
        self.assertEqual(load_hall(self.path), [Entry('Old', 50), Entry('Kid h', 20), Entry('Low', 3)])
        self.assertIsNotNone(scene.hall_after_id)
        self.press('Return')
        self.assertIsNone(scene.game_menu)
        self.assertIsNone(scene.hall_after_id)
        self.assertIsNotNone(scene.intro)
        self.assertFalse(scene.paused)

    def test_menu_command_shows_the_table_and_returns_to_the_menu(self):
        scene = self.scene
        save_hall([Entry('Old', 50)], self.path)
        scene.open_game_menu()
        scene.apply_game_action('hall')
        self.assertEqual(scene.game_menu.page, 'hall')
        self.assertEqual(scene.game_menu.hall_page.entries, [Entry('Old', 50)])
        self.assertEqual(scene.input_context(), 'menu')
        self.press('Escape')
        self.assertEqual(scene.game_menu.page, 'menu')
        self.assertIsNone(scene.game_menu.hall_page)


@unittest.skipUnless(INSTALLED and (ASSET_DIR / 'happy.json').is_file(), 'Imported NIS 11 required')
class HappyEndingChapterTests(HallOfFameWindowTests):
    """The last chapter unlocks when NIS 11 plays; the game after the victory
    keeps the campaign's cutscenes (New Game+); Alt+N leaves them."""

    def press(self, keysym, char=None, state=0):
        from types import SimpleNamespace

        event = SimpleNamespace(keysym=keysym, state=state, char=keysym if char is None else char)
        self.scene.dev_key_press(event)
        self.scene.dev_key_release(event)

    def win(self):
        from pop2.cutscenes import CHAPTERS
        from pop2.environments import Final

        scene = self.scene
        scene.mark_cutscene_seen('tower')
        scene.game_menu = None
        scene.game.story.minutes = 33
        Final(scene).finish_exit()
        self.assertEqual(scene.intro.program_kind, 'happy')
        self.assertNotIn('happy', scene.cutscene_collection.seen)   # only once it has played
        return [chapter.key for chapter in CHAPTERS].index('happy')

    def finish_scene(self):
        scene = self.scene
        scene.intro.advance(100)
        scene.finish_attract_stage()
        self.assertEqual(scene.game_menu.page, 'hall')

    def viewer(self):
        self.press('c', state=0x20000)
        return self.scene.game_menu.cutscene_viewer

    def test_alt_c_during_the_ending_reveals_it_only_after_it_and_once(self):
        index = self.win()
        self.assertNotIn(index, self.viewer().reveal)   # still playing
        self.scene.close_game_menu()
        self.finish_scene()
        self.press('Escape')
        self.assertIn(index, self.viewer().reveal)
        self.scene.close_game_menu()
        self.assertNotIn(index, self.viewer().reveal)

    def test_after_the_victory_a_fresh_game_keeps_the_cutscenes_and_reveals_the_ending(self):
        scene = self.scene
        index = self.win()
        self.finish_scene()
        self.press('Escape')
        self.assertIsNone(scene.game_menu)
        self.assertEqual(scene.game.level.number, 1)
        self.assertEqual(scene.game.story.minutes, 75)
        self.assertIsNone(scene.active_save_path)
        self.assertIn('happy', scene.cutscene_collection.seen)
        gallery = self.viewer()
        self.assertIn(index, gallery.reveal)
        self.assertTrue(gallery.chapter_unlocked(index))
        scene.close_game_menu()
        scene.new_game()
        self.assertNotIn('happy', scene.cutscene_collection.seen)
        gallery = self.viewer()
        self.assertEqual(gallery.reveal.keys() & {index}, set())
        self.assertFalse(gallery.chapter_unlocked(index))


if __name__ == '__main__':
    unittest.main()
