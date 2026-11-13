from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageChops, ImageDraw, ImageFont

from pop2.cutscenes import CHAPTERS, CHAPTER_KEYS, OPENING_KEYS, CutsceneCollection
from pop2 import menu_theme
from pop2.cutscene_gallery import CutsceneGallery
from pop2.cutscene_viewer import ReplayAudio
from pop2.game_menu import GameMenu
from pop2.paths import ASSET_DIR


class CollectionTests(unittest.TestCase):
    def test_whole_story_catalog_includes_recent_films_and_excludes_tree_and_gameplay(self):
        self.assertEqual([chapter.program for chapter in CHAPTERS],
                         ['intro.json', 'intro.json', 'intro.json', 'ending.json', 'discovery.json', 'carpet.json',
                          'throne.json', 'temple.json', 'tower.json'])
        self.assertEqual(len(CHAPTER_KEYS), len(CHAPTERS))
        self.assertEqual(len({chapter.program for chapter in CHAPTERS}), 7)

    def test_collections_keep_independent_chronological_progress(self):
        first, second = CutsceneCollection(), CutsceneCollection()
        first.unlock('voyage', 'unknown')
        second.unlock('discovery', 'carpet')
        self.assertEqual(first.seen, OPENING_KEYS | {'voyage'})
        self.assertEqual(second.seen, set(OPENING_KEYS))
        second.unlock('voyage', 'discovery', 'carpet')
        self.assertEqual(second.seen, OPENING_KEYS | {'voyage', 'discovery', 'carpet'})
        self.assertEqual(first.seen, OPENING_KEYS | {'voyage'})

    def test_isolated_horse_record_is_locked_again(self):
        collection = CutsceneCollection.from_saved(OPENING_KEYS | {'horse'})
        self.assertEqual(collection.seen, OPENING_KEYS)
        collection.unlock('horse')
        self.assertNotIn('horse', collection.seen)
        collection.unlock('voyage', 'discovery', 'carpet', 'vision', 'horse')
        self.assertEqual(collection.seen, OPENING_KEYS | {
            'voyage', 'discovery', 'carpet', 'vision', 'horse'})
        keys = [chapter.key for chapter in CHAPTERS]
        self.assertLess(keys.index('vision'), keys.index('horse'))
        self.assertLess(keys.index('horse'), keys.index('tower'))

    def test_legacy_saves_admit_only_preceding_mandatory_chapters(self):
        collection = CutsceneCollection()
        game = SimpleNamespace(level=SimpleNamespace(number=8),
                               caverns=SimpleNamespace(throne_seen=False, throne_done=False))
        collection.admit_saved_progress(game)
        self.assertEqual(collection.seen, OPENING_KEYS | {'voyage', 'discovery', 'carpet'})
        game.caverns.throne_seen = True
        collection.admit_saved_progress(game)
        self.assertIn('vision', collection.seen)
        game.level.number = 13
        collection.admit_saved_progress(game)
        self.assertIn('horse', collection.seen)
        self.assertNotIn('tower', collection.seen)


class CaptionFont:
    height = 12

    def __init__(self):
        self.values = []

    def text(self, value, color='white'):
        self.values.append(value)
        image = Image.new('RGBA', (max(1, len(value) * 7), 14))
        ImageDraw.Draw(image).text((0, 0), value, font=ImageFont.load_default(), fill=color)
        return image


class GalleryTests(unittest.TestCase):
    def setUp(self):
        # Model cards use the supplied mock previews, independently of whether
        # this checkout has the real game's story programs imported.
        available = patch('pop2.cutscene_gallery.chapter_available', return_value=True)
        available.start()
        self.addCleanup(available.stop)

    def gallery(self):
        return CutsceneGallery(CutsceneCollection(seen={'opening'}),
                               Mock(return_value=Image.new('RGB', (510, 384), '#773311')))

    def test_horizontal_navigation_and_explicit_activation(self):
        gallery = self.gallery()
        self.assertEqual(list(gallery.visible), [0, 1, 2, 3, 4, 5])
        self.assertEqual(gallery.key('Return'), 'cutscene_play')
        gallery.key('Right')
        self.assertEqual(gallery.key('Return'), 'changed')
        gallery.key('End')
        self.assertEqual(gallery.index, 8)
        gallery.advance(1)
        self.assertEqual(list(gallery.visible), [4, 5, 6, 7, 8])
        gallery.key('Right')
        self.assertEqual(gallery.index, 8)
        gallery.key('Home')
        gallery.key('Tab')
        self.assertEqual(gallery.index, 1)
        gallery.key('Tab', backwards=True)
        self.assertEqual(gallery.key('Return'), 'cutscene_play')
        self.assertEqual(gallery.key('Escape'), 'cutscene_back')

    def test_one_click_plays_an_unlocked_card_but_not_a_locked_one_or_a_drag(self):
        # The user asked for one click instead of the earlier double click.
        gallery = self.gallery()
        rect = gallery.card_rect(0)
        point = (rect[0] + 20, rect[1] + 20)
        gallery.index = 3
        self.assertEqual(gallery.click(*point), 'cutscene_play')
        self.assertEqual(gallery.index, 0)
        gallery.begin_drag(*point)                                    # press and release in place
        self.assertEqual(gallery.end_drag(*point), 'cutscene_play')
        self.assertEqual(gallery.double_click(*point), 'cutscene_play')
        locked = gallery.card_rect(1)
        locked_point = locked[0] + 20, locked[1] + 20
        self.assertEqual(gallery.click(*locked_point), 'changed')     # selected, with its message
        self.assertEqual(gallery.index, 1)
        self.assertEqual(gallery.double_click(*locked_point), 'changed')
        gallery.begin_drag(*point)
        self.assertEqual(gallery.end_drag(point[0] - 20, point[1]), 'changed')   # a drag only scrolls
        self.assertEqual(gallery.index, 1)

    def test_gallery_has_no_play_back_buttons_or_keyboard_hint(self):
        gallery, font = self.gallery(), CaptionFont()
        gallery.draw(Image.new('RGBA', (1024, 768)), font)
        self.assertIn('Cutscene Viewer', font.values)
        self.assertNotIn('Play', font.values)
        self.assertNotIn('Back', font.values)
        self.assertFalse(any('Enter:' in value for value in font.values))
        self.assertIsNone(gallery.hit(50, 35))
        self.assertIsNone(gallery.hit(gallery.PANEL[2] - 40, 35))

    def test_a_click_on_a_different_locked_card_only_selects_it(self):
        gallery = self.gallery()
        first, second = gallery.card_rect(0), gallery.card_rect(2)
        gallery.click(first[0] + 20, first[1] + 20)
        self.assertEqual(gallery.double_click(second[0] + 20, second[1] + 20), 'changed')
        self.assertEqual(gallery.index, 2)

    def test_locked_chapters_show_only_large_dark_blocks_of_their_cover_and_no_title(self):
        gallery = self.gallery()
        font = CaptionFont()
        # A cover with fine detail: thin stripes that only an unveiled card can show.
        cover = Image.new('RGB', (510, 384), '#204080')
        for x in range(0, 510, 6):
            ImageDraw.Draw(cover).line((x, 0, x, 384), fill='#ffe040', width=2)
        gallery.preview = Mock(return_value=cover)
        with patch('pop2.cutscene_gallery.chapter_available', return_value=True):
            gallery.draw(Image.new('RGBA', (1024, 768)), font)
            open_card = gallery.card_image(0, font, 2, 2).convert('RGB')
            locked_card = gallery.card_image(1, font, 2, 2).convert('RGB')
        self.assertNotIn(CHAPTERS[1].title, font.values)
        self.assertNotIn(CHAPTERS[2].title, font.values)
        self.assertIn('Chapter 2', font.values)
        self.assertEqual(gallery.index, 0)
        width = round(gallery.CARD_WIDTH * 2)
        thumb = (4, 4, width - 4, round((2 + (gallery.CARD_WIDTH - 4) * 9 / 16) * 2))
        shown, veiled = open_card.crop(thumb), locked_card.crop(thumb)
        self.assertGreater(max(max(colour) for _n, colour in shown.getcolors(1 << 16)), 0xe0)   # bright stripes
        colours = veiled.getcolors(1 << 16)
        self.assertLessEqual(len(colours), gallery.VEIL_COLUMNS * 10)          # one colour for each block
        self.assertTrue(all(max(colour) < 0x90 for _n, colour in colours))    # darkened; no stripe survives
        # Each block is a flat rectangle many pixels wide.
        row = [veiled.getpixel((x, 20)) for x in range(veiled.width)]
        runs = [x for x in range(1, len(row)) if row[x] != row[x - 1]]
        self.assertLessEqual(len(runs), gallery.VEIL_COLUMNS)

    def striped_gallery(self):
        gallery = self.gallery()
        cover = Image.new('RGB', (510, 384), '#204080')
        for x in range(0, 510, 6):
            ImageDraw.Draw(cover).line((x, 0, x, 384), fill='#ffe040', width=2)
        gallery.preview = Mock(return_value=cover)
        gallery.collection.seen.add(CHAPTERS[1].key)
        return gallery

    def test_newly_unlocked_chapter_resolves_out_of_its_veil_in_whole_frames(self):
        gallery, font = self.striped_gallery(), CaptionFont()
        gallery.begin_reveal([1, 2])                                          # 2 is still locked: ignored
        self.assertEqual((set(gallery.reveal), gallery.index), ({1}, 1))
        self.assertEqual((gallery.reveal_stage(1), gallery.reveal_glow(1)), (0, None))
        with patch('pop2.cutscene_gallery.chapter_available', return_value=True):
            def card():
                return gallery.card_image(1, font, 2, 2).convert('RGB')

            def locked():
                gallery.collection.seen.discard(CHAPTERS[1].key)
                picture = card()
                gallery.collection.seen.add(CHAPTERS[1].key)
                return picture

            self.assertEqual(card().tobytes(), locked().tobytes())            # it starts exactly as it was
            self.assertNotIn(CHAPTERS[1].title, font.values)
            self.assertFalse(gallery.reveal_cue)
            self.assertTrue(gallery.advance(gallery.REVEAL_DELAY))            # keeps the page animating
            self.assertTrue(gallery.reveal_cue)                               # the scene plays the sound now
            gallery.reveal_cue = False
            # Drawn at a display's pace, the card still moves in whole frames, fifteen a second,
            # one stage of blocks a frame, nothing blended: an old game's animation. Eight
            # stages at nine a second looked choppy; a dissolve at 60 a second, and then
            # twenty whole frames a second, too smooth.
            self.assertEqual((gallery.REVEAL_RATE, gallery.reveal_stages), (15, 17))
            frames, stages = [card()], [gallery.reveal_stage(1)]
            while gallery.reveal_glow(1) is None:
                gallery.advance(1 / 60)
                frames.append(card())
                stages.append(gallery.reveal_stage(1))
            self.assertFalse(gallery.reveal_cue)                              # once for each chapter
            self.assertEqual(sorted(set(stages)), list(range(gallery.reveal_stages + 1)))
            self.assertEqual(stages, sorted(stages))
            pictures = [frame.tobytes() for frame in frames]
            distinct = [pictures[0]] + [after for before, after in zip(pictures, pictures[1:]) if after != before]
            self.assertEqual(len(distinct), gallery.reveal_stages + 1)        # one picture for each stage
            self.assertEqual(len(set(distinct)), len(distinct))
            held = len(frames) / len(distinct)
            self.assertTrue(3.5 < held < 4.5)                                 # each held for four 60 Hz frames
            # Blocks only, never a blend of two stages: a stage's picture is exactly its own veil.
            thumb = (4, 4, frames[0].width - 4, 150)
            cover = gallery.image_cache[1, (frames[0].width - 8, round((gallery.CARD_WIDTH - 4) * 9 / 16 * 2))]
            middle = stages.index(8)
            self.assertEqual(frames[middle].crop(thumb).tobytes(),
                             gallery.veil(1, cover, 8).crop((0, 0, thumb[2] - 4, 146)).tobytes())
            self.assertIn(CHAPTERS[1].title, font.values)                     # the title arrives on the way
            # A card in the middle of its reveal is never kept.
            self.assertFalse(any(key[0] == 1 and key[3] for key in gallery.card_cache if key[4]))

    def test_revealed_cover_glows_at_its_ordinary_thickness_while_light_crosses_it(self):
        gallery, font = self.striped_gallery(), CaptionFont()
        gallery.begin_reveal([1])
        with patch('pop2.cutscene_gallery.chapter_available', return_value=True):
            gallery.advance(gallery.REVEAL_DELAY + gallery.reveal_stages * gallery.REVEAL_STEP + .001)
            self.assertEqual(gallery.reveal_glow(1), 0)
            bright, accent = (tuple(int(menu_theme.c(colour)[i:i + 2], 16) for i in (1, 3, 5))
                              for colour in ('#eeeeee', '#f4d873'))
            glow, moments = [], []
            while gallery.reveal:
                moments.append(gallery.reveal_glow(1))
                glow.append(gallery.card_image(1, font, 2, 2).convert('RGB'))
                gallery.advance(1 / 30)
            settled = gallery.card_image(1, font, 2, 2).convert('RGB')
            self.assertGreaterEqual(moments[-1], 1.2)                         # seconds: not a flash
            # The border keeps the selected card's two pixels (at this scale four) throughout:
            # the user disliked it growing fat and shrinking back.
            height = settled.height
            for frame in glow:
                self.assertEqual(frame.getpixel((3, 40)), frame.getpixel((0, 40)))
                self.assertNotEqual(frame.getpixel((5, 40)), frame.getpixel((0, 40)))
            edge = [frame.getpixel((1, 40)) for frame in glow]
            self.assertEqual(settled.getpixel((1, 40)), accent)
            # It fades in as it fades out: the user disliked the border turning white at once.
            peak = edge.index(bright)
            rising = [colour for n, colour in enumerate(edge[:peak]) if n == 0 or colour != edge[n - 1]]
            self.assertGreaterEqual(len(rising), 3)
            self.assertNotIn(edge[0], (bright, accent))                       # already on its way up
            blue = [colour[2] for colour in rising] + [bright[2]]             # accent has little blue, bright much
            self.assertEqual(blue, sorted(blue))
            self.assertGreater(moments[peak], .15)
            falling = edge[peak:]
            self.assertGreaterEqual(len(set(falling)), 8)                     # cooling through many shades
            self.assertEqual([colour[2] for colour in falling], sorted((colour[2] for colour in falling), reverse=True))
            self.assertEqual(edge[-1], accent)
            # The border lies over the title's band, at the bottom as on every side.
            for frame in (*glow[:1], settled):
                self.assertEqual(frame.getpixel((frame.width // 2, height - 3)), frame.getpixel((1, 40)))
                self.assertEqual(frame.getpixel((frame.width - 3, height - 12)), frame.getpixel((1, 40)))
            # Meanwhile a band of light crosses the cover itself, left to right, then is gone.
            crop = (10, 10, settled.width - 10, 150)
            plain = settled.crop(crop)
            centres = []
            for moment, frame in zip(moments, glow):
                box = ImageChops.difference(frame.crop(crop), plain).getbbox()
                if moment >= gallery.GLOW_SWEEP:
                    self.assertIsNone(box)
                elif box is not None:
                    centres.append((box[0] + box[2]) / 2)
            self.assertGreater(len(centres), 20)
            self.assertEqual(centres, sorted(centres))
            self.assertGreater(centres[-1] - centres[0], plain.width / 2)
            moves = [b - a for a, b in zip(centres, centres[1:]) if b != a]
            self.assertGreaterEqual(len(moves), 9)                            # in many steps...
            self.assertLess(max(moves), plain.width / 6)                      # ...none of them a leap

    def test_reveal_redraws_only_its_card_in_the_cached_grid(self):
        gallery, font = self.striped_gallery(), CaptionFont()
        source = Image.new('RGBA', (1024, 768))
        with patch('pop2.cutscene_gallery.chapter_available', return_value=True):
            gallery.draw(source, font)
            gallery.begin_reveal([1])
            gallery.draw(source, font)
            grid = gallery.grid_cache[1]
            key = gallery.grid_cache[0]
            self.assertEqual(gallery.take_reveal_patches(), ())               # nothing has moved yet
            gallery.advance(gallery.REVEAL_DELAY + .3)
            before = grid.copy()
            with patch.object(gallery, 'card_image', wraps=gallery.card_image) as card_image:
                gallery.refresh_reveal(font, 2, 2)
            self.assertEqual([call.args[0] for call in card_image.call_args_list], [1])   # one card, not the shelf
            self.assertIs(gallery.grid_cache[1], grid)                        # the same picture, changed in place
            self.assertEqual(gallery.grid_cache[0], key)
            (x, y, card), = gallery.take_reveal_patches()
            changed = ImageChops.difference(before, grid).getbbox()
            self.assertTrue(x <= changed[0] and y <= changed[1]
                            and changed[2] <= x + card.width and changed[3] <= y + card.height)
            self.assertEqual(grid.crop((x, y, x + card.width, y + card.height)).tobytes(), card.tobytes())
            self.assertEqual(gallery.take_reveal_patches(), ())
            gallery.refresh_reveal(font, 2, 2)                                # no progress, nothing redrawn
            self.assertEqual(gallery.take_reveal_patches(), ())
            # A full draw shows the same thing, and the settled card when the reveal ends.
            self.assertIs(gallery.draw(source, font) and gallery.grid_cache[1], grid)
            gallery.advance(gallery.reveal_seconds)
            self.assertEqual(gallery.reveal, {})
            gallery.draw(source, font)
            settled = gallery.card_image(1, font, 2, 2).convert('RGB')
            (x, y, card), = gallery.take_reveal_patches()
            self.assertEqual(card.tobytes(), settled.tobytes())
            self.assertEqual(gallery.reveal_drawn, {})

    def test_developer_viewer_never_animates_but_r_replays_the_selected_reveal(self):
        gallery = self.gallery()
        gallery.developer = True
        gallery.begin_reveal([])
        self.assertEqual(gallery.reveal, {})
        seen_before = set(gallery.collection.seen)
        gallery.index = 4
        self.assertEqual(gallery.key('r'), 'changed')
        self.assertEqual(gallery.reveal, {4: -gallery.REVEAL_DELAY})
        self.assertEqual(gallery.collection.seen, seen_before)
        gallery.developer = False
        gallery.reveal = {}
        gallery.key('r')
        self.assertEqual(gallery.reveal, {})

    def test_developer_access_is_read_only_and_caches_do_not_leak_to_normal_mode(self):
        gallery = self.gallery()
        seen = gallery.collection.seen.copy()
        gallery.developer = True
        with patch('pop2.cutscene_gallery.chapter_available', return_value=True):
            font = CaptionFont()
            gallery.draw(Image.new('RGBA', (1024, 768)), font)
            self.assertIn('Cutscene Viewer - Dev Tools', font.values)
            self.assertEqual(gallery.preview.call_count, len(CHAPTERS))
            gallery.key('End')
            self.assertEqual(gallery.activate(), 'cutscene_play')
            gallery.developer = False
            gallery.preview.reset_mock()
            font = CaptionFont()
            gallery.draw(Image.new('RGBA', (1024, 768)), font)
            self.assertIn('Cutscene Viewer', font.values)
            self.assertNotIn(CHAPTERS[-1].title, font.values)
            self.assertEqual(gallery.activate(), 'changed')
            gallery.preview.assert_not_called()
        self.assertEqual(gallery.collection.seen, seen)

    def test_wheel_is_continuous_eased_and_independent_of_selection(self):
        gallery = self.gallery()
        gallery.wheel(.25)
        self.assertEqual(gallery.scroll, 0)
        self.assertGreater(gallery.scroll_target, 0)
        self.assertLess(gallery.scroll_target, gallery.PITCH)
        self.assertTrue(gallery.advance(1 / 60))
        self.assertGreater(gallery.scroll, 0)
        self.assertLess(gallery.scroll, gallery.scroll_target)
        self.assertEqual(gallery.index, 0)
        gallery.wheel(100)
        gallery.advance(1)
        self.assertEqual(gallery.scroll, gallery.max_scroll)
        gallery.wheel(-100)
        gallery.advance(1)
        self.assertEqual(gallery.scroll, 0)

    def test_drag_browses_without_selecting_and_click_selects_on_release(self):
        gallery = self.gallery()
        self.assertTrue(gallery.begin_drag(200, 150))
        gallery.move_drag(164.5)
        gallery.end_drag(164.5, 150)
        self.assertEqual(gallery.scroll, 35.5)
        self.assertEqual(gallery.index, 0)
        rect = gallery.card_rect(2)
        x, y = (rect[0] + rect[2]) / 2, 150
        gallery.begin_drag(x, y)
        gallery.end_drag(x, y)
        self.assertEqual(gallery.index, 2)

    def test_scroll_edges_react_on_the_first_frame_with_a_wider_soft_return(self):
        gallery = self.gallery()
        for edge, direction in ((0, -1), (gallery.max_scroll, 1)):
            gallery.scroll = gallery.scroll_target = edge
            gallery.wheel(direction)
            positions = []
            for _ in range(240):
                moving = gallery.advance(1 / 120)
                positions.append(gallery.display_scroll)
            self.assertGreater((positions[0] - edge) * direction, .5)
            self.assertGreater(max((p - edge) * direction for p in positions), 16)
            self.assertGreater((positions[60] - edge) * direction, 1)
            self.assertTrue(all(abs(p - edge) <= gallery.BOUNCE_LIMIT for p in positions))
            self.assertFalse(moving)
            self.assertEqual(gallery.display_scroll, edge)
            self.assertEqual(gallery.index, 0)

    def test_elastic_drag_stays_bounded_and_returns_after_release(self):
        gallery = self.gallery()
        gallery.begin_drag(100, 150)
        gallery.move_drag(220)
        held = gallery.display_scroll
        self.assertLess(held, 0)
        self.assertGreaterEqual(held, -gallery.BOUNCE_LIMIT)
        self.assertFalse(gallery.advance(.1))
        self.assertEqual(gallery.display_scroll, held)
        gallery.end_drag(220, 150)
        for _ in range(150):
            moving = gallery.advance(1 / 120)
        self.assertFalse(moving)
        self.assertEqual(gallery.display_scroll, 0)

    def test_reversing_before_the_edge_cancels_a_queued_bounce(self):
        gallery = self.gallery()
        gallery.wheel(100)
        self.assertTrue(gallery.edge_target)
        gallery.wheel(-.5)
        self.assertFalse(gallery.edge_target)
        for _ in range(150):
            gallery.advance(1 / 120)
            self.assertEqual(gallery.bounce, 0)

    def test_moving_into_the_end_flows_through_without_stopping_before_the_bounce(self):
        gallery = self.gallery()
        gallery.scroll = gallery.scroll_target = gallery.max_scroll - 40
        gallery.wheel(1)
        for _ in range(120):
            before = gallery.display_scroll
            velocity = gallery.scroll_velocity
            gallery.advance(1 / 120)
            if gallery.display_scroll > gallery.max_scroll:
                self.assertLess(before, gallery.max_scroll)
                self.assertGreater(velocity, 50)
                self.assertGreater(gallery.scroll_velocity, 50)
                break
        else:
            self.fail('No continuous crossing into the edge bounce')

    def test_a_shelf_that_fits_has_no_unnecessary_bounce(self):
        gallery = self.gallery()
        gallery.chapters = CHAPTERS[:4]
        gallery.wheel(100)
        self.assertFalse(gallery.advance(1 / 120))
        self.assertEqual(gallery.display_scroll, 0)

    def test_hd_thumbnail_uses_source_pixels_instead_of_a_small_upscaled_card(self):
        from PIL import ImageChops, ImageOps

        gallery = self.gallery()
        source = Image.effect_noise((510, 384), 100).convert('RGB')
        gallery.preview.return_value = source
        image = gallery.draw(Image.new('RGBA', (2048, 1536)), CaptionFont())
        rect = gallery.card_rect(0)
        width = round((gallery.CARD_WIDTH - 2) * 4) - 8
        height = round((2 + (gallery.CARD_WIDTH - 4) * 9 / 16) * 4) - 8
        thumb = round(rect[0] * 4) + 8, round(rect[1] * 4) + 8
        thumb = *thumb, thumb[0] + width, thumb[1] + height
        expected = ImageOps.fit(source, (width, height), method=Image.Resampling.NEAREST)
        self.assertIsNone(ImageChops.difference(image.crop(thumb).convert('RGB'), expected).getbbox())


    def test_two_rows_stay_dense_and_arrow_keys_follow_the_grid(self):
        gallery = self.gallery()
        first = [gallery.card_rect(i) for i in range(6)]
        self.assertEqual([rect[1] for rect in first], [88.375, 202.5, 88.375, 202.5, 88.375, 202.5])
        self.assertEqual([rect[0] for rect in first], [21, 21, 181, 181, 341, 341])
        self.assertGreater(first[0][2] - first[0][0], 140)
        gallery.key('Down')
        self.assertEqual(gallery.index, 1)
        gallery.key('Up')
        self.assertEqual(gallery.index, 0)
        for _ in range(3):
            gallery.key('Right')
        self.assertEqual(gallery.index, 6)
        self.assertGreater(gallery.scroll_target, 0)
        gallery.key('Left')
        self.assertEqual(gallery.index, 4)

    def test_wide_layout_adds_columns_without_stretching_covers_or_text(self):
        gallery, font = self.gallery(), CaptionFont()
        for size, columns in (((1020, 768), 3), ((1920, 1080), 3),
                              ((2560, 1080), 4), ((3840, 1080), 6)):
            with self.subTest(size=size):
                gallery.draw(Image.new('RGBA', size), font, visible=True)
                self.assertEqual(gallery.COLUMNS, columns)
                self.assertEqual(gallery.ROWS, 2)
                self.assertAlmostEqual((gallery.CARD_WIDTH - 4) /
                                       (gallery.CARD_HEIGHT - 22), 16 / 9)
                self.assertLessEqual(gallery.card_rect(columns * 2 - 2)[2], gallery.STRIP[2])
                self.assertGreaterEqual(gallery.card_rect(0)[1], gallery.STRIP[1])
                self.assertLessEqual(gallery.card_rect(1)[3], gallery.STRIP[3])
                self.assertIsNone(gallery.hit(gallery.PANEL[2] - 40, 35))
        gallery.key('End')
        gallery.advance(1)
        gallery.draw(Image.new('RGBA', (1020, 768)), font, visible=True)
        self.assertLessEqual(gallery.scroll, gallery.max_scroll)
        self.assertEqual(gallery.index, 8)

    def test_scroll_frames_do_not_load_redraw_fonts_or_resample_images(self):
        gallery, font = self.gallery(), CaptionFont()
        viewport = Image.new('RGBA', (1530, 1152))
        gallery.draw(viewport, font)
        grid = gallery.grid_cache[1]
        with patch.object(gallery, 'preview', side_effect=AssertionError('Loaded during scroll')), \
                patch.object(font, 'text', side_effect=AssertionError('Drew text during scroll')), \
                patch.object(Image.Image, 'resize', side_effect=AssertionError('Resized during scroll')):
            gallery.wheel(.5)
            for _ in range(20):
                gallery.advance(1 / 60)
                gallery.draw(viewport, font)
                self.assertIs(gallery.grid_cache[1], grid)



class ReplayAudioTests(unittest.TestCase):
    def test_replay_uses_private_channels_and_never_resets_the_game_engine(self):
        count = [8]
        mixer = Mock()
        mixer.get_num_channels.side_effect = lambda: count[0]
        mixer.set_num_channels.side_effect = lambda value: count.__setitem__(0, value)
        mixer.get_init.return_value = (48000, -16, 2)
        channels = {8: Mock(), 9: Mock()}
        mixer.Channel.side_effect = channels.__getitem__
        sound = Mock()
        engine = Mock(playback=SimpleNamespace(mixer=mixer, sounds={'scene-0-25006': sound}))
        replay = ReplayAudio(engine)
        self.assertEqual(count[0], 10)
        replay.play_intro(25006, 0)
        channels[8].play.assert_called_once_with(sound)
        replay.pause(True)
        channels[8].pause.assert_called_once_with()
        channels[9].pause.assert_called_once_with()
        replay.close()
        self.assertEqual(count[0], 8)
        engine.reset.assert_not_called()
        engine.pause.assert_not_called()
        self.assertEqual([call.args[0] for call in mixer.Channel.call_args_list], [8, 9])

    def test_real_sdl_channels_leave_the_paused_music_and_effects_in_place(self):
        from pop2.audio import MixerPlayback

        with TemporaryDirectory() as directory, patch.dict('os.environ', {'SDL_AUDIODRIVER': 'dummy'}):
            backend = MixerPlayback(directory, {})
            replay = None
            try:
                sound = backend.mixer.Sound(buffer=bytes(48000 * 4 * 2))
                backend.sounds['scene-0-25006'] = sound
                backend.channels['music'].play(sound)
                backend.channels['effect'].play(sound)
                backend.pause(True)
                count = backend.mixer.get_num_channels()
                replay = ReplayAudio(SimpleNamespace(playback=backend))
                replay.play_intro(25006, 0)
                self.assertIs(backend.channels['music'].get_sound(), sound)
                self.assertIs(backend.channels['effect'].get_sound(), sound)
                self.assertTrue(backend.channels['music'].get_busy())
                self.assertTrue(replay.channels['music'].get_busy())
                replay.pause(True)
                replay.pause(False)
                replay.close()
                self.assertEqual(backend.mixer.get_num_channels(), count)
                self.assertIs(backend.channels['music'].get_sound(), sound)
            finally:
                if replay is not None:
                    replay.close()
                backend.close()


@unittest.skipUnless(all((ASSET_DIR / c.program).is_file() for c in CHAPTERS), 'Imported story programs required')
class ViewerSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.scene.cutscene_collection = CutsceneCollection()

    def snapshot(self):
        from pop2.save_game import capture_snapshot

        return capture_snapshot(self.scene.game)

    def open_viewer(self):
        self.scene.open_game_menu()
        self.scene.apply_game_action('cutscenes')
        return self.scene.game_menu.cutscene_viewer

    def displayed_gallery(self):
        """Read the retained Tk photos and item coordinates, not the gallery model."""
        from PIL import ImageTk

        scene = self.scene
        image = ImageTk.getimage(scene.image_ref).convert('RGB')
        strip = getattr(scene, '_cutscene_gallery_strip', None)
        if strip is not None and strip.shown:
            parent = scene.canvas.coords(scene.canvas.find_all()[0])
            left, top, right, bottom = strip.region
            offset = round(-strip.canvas.coords(strip.item)[0])
            source = ImageTk.getimage(strip.photo).convert('RGB')
            visible = source.crop((offset, 0, offset + right - left, bottom - top))
            draw = ImageDraw.Draw(visible)
            for item in strip.borders:
                if strip.canvas.itemcget(item, 'state') != 'hidden':
                    x1, y1, x2, y2 = map(round, strip.canvas.coords(item))
                    draw.rectangle((x1, y1, x2 - 1, y2 - 1), fill=strip.canvas.itemcget(item, 'fill'))
            image.paste(visible,
                        (round(left - parent[0]), round(top - parent[1])))
        return image

    def test_f1_keeps_progress_and_f3_offers_the_same_chapters_with_developer_access(self):
        scene = self.scene
        self.assertIn('cutscenes', {item.action for item in GameMenu().items})
        gallery = self.open_viewer()
        self.assertEqual(gallery.chapters, CHAPTERS)
        self.assertFalse(gallery.developer)
        self.assertFalse(gallery.chapter_unlocked(len(CHAPTERS) - 1))
        scene.close_game_menu()
        scene.open_dev_mode()
        scene.dev_menu.focus = 8
        scene.apply_dev_action(scene.dev_menu.activate())
        self.assertIsNone(scene.dev_menu)
        self.assertEqual(scene.game_menu.page, 'cutscenes')
        developer = scene.game_menu.cutscene_viewer
        self.assertTrue(developer.developer)
        self.assertEqual(developer.chapters, CHAPTERS)
        self.assertTrue(all(developer.chapter_unlocked(i) for i in range(len(CHAPTERS))))

    def test_chapter_unlocked_by_playing_resolves_with_a_sound_the_next_time_the_viewer_opens(self):
        scene = self.scene
        scene.audio = Mock()
        key = next(chapter.key for chapter in CHAPTERS if chapter.key not in OPENING_KEYS)
        index = next(i for i, chapter in enumerate(CHAPTERS) if chapter.key == key)
        scene.mark_cutscene_seen(key)
        self.assertEqual(scene.cutscene_fresh, {key})
        gallery = self.open_viewer()
        self.assertEqual((set(gallery.reveal), gallery.index), ({index}, index))
        self.assertEqual(scene.cutscene_fresh, set())
        self.assertIsNotNone(scene.cutscene_gallery_after_id)          # the page is animating
        scene.audio.play_ui.assert_not_called()
        # Drive the tick as the scheduler would.
        pending = []
        with patch.object(scene.root, 'after', side_effect=lambda _delay, callback: pending.append(callback) or 'id'),                 patch.object(scene.root, 'after_idle', side_effect=lambda callback: pending.append(callback) or 'id'),                 patch.object(scene.root, 'after_cancel'),                 patch('pop2.cutscene_viewer.time.perf_counter', side_effect=(n * .05 for n in range(10000))):
            scene.cancel_cutscene_gallery_tick()
            scene.schedule_cutscene_gallery()
            checked = rebuilt = 0
            with patch.object(scene, 'cutscene_gallery_frame', wraps=scene.cutscene_gallery_frame) as frame:
                for _ in range(400):
                    if not pending or not gallery.reveal:
                        break
                    pending.pop(0)()
                    stage = gallery.reveal_stage(index)
                    if stage is not None and 2 < stage < gallery.reveal_stages and not checked:
                        # What the window shows is the half-resolved card, brought there
                        # without rebuilding the page.
                        rebuilt = frame.call_count
                        shown = self.displayed_gallery()
                        checked = 1
                rebuilds = frame.call_count
            self.assertEqual((checked, rebuilt, rebuilds), (1, 0, 0))
            size = shown.size
            model = scene.cutscene_gallery_frame(size)
            self.assertEqual(self.displayed_gallery().tobytes(), model.tobytes())      # settled, glow over
            self.assertNotEqual(shown.tobytes(), model.tobytes())
        self.assertEqual(gallery.reveal, {})
        scene.audio.play_ui.assert_called_once_with('reveal')
        scene.close_game_menu()
        again = self.open_viewer()                                      # only the first visit animates
        self.assertEqual(again.reveal, {})
        scene.close_game_menu()
        # A chapter admitted from a loaded save, or seen in the developer viewer, does not animate.
        scene.cutscene_collection.unlock(*CHAPTER_KEYS)
        self.assertEqual(self.open_viewer().reveal, {})

    def test_a_game_s_introduction_reveals_the_three_opening_chapters_once_with_one_sound(self):
        scene = self.scene
        self.assertEqual(self.open_viewer().reveal, {})                 # open from the start: nothing to reveal yet
        scene.close_game_menu()
        scene.mark_cutscene_seen('opening')                            # the introduction has played
        self.assertEqual(scene.cutscene_fresh, set(OPENING_KEYS))
        gallery = self.open_viewer()
        opening = [index for index, chapter in enumerate(CHAPTERS) if chapter.key in OPENING_KEYS]
        self.assertEqual((sorted(gallery.reveal), gallery.index), (opening, opening[0]))
        waits = [gallery.reveal[index] for index in opening]
        self.assertEqual(waits, sorted(waits, reverse=True))           # one after another
        cues = 0
        for _ in range(400):
            gallery.advance(1 / 30)
            cues += gallery.reveal_cue
            gallery.reveal_cue = False
        self.assertEqual((gallery.reveal, cues), ({}, 1))              # three chapters, one sound
        scene.close_game_menu()
        scene.mark_cutscene_seen('opening')                            # the introduction again, same game
        self.assertEqual(scene.cutscene_fresh, set())
        self.assertEqual(self.open_viewer().reveal, {})
        scene.close_game_menu()
        scene.cutscene_collection = CutsceneCollection()               # a new game reveals them again
        scene.mark_cutscene_seen('opening')
        self.assertEqual(sorted(self.open_viewer().reveal), opening)

    def test_developer_replay_leaves_profile_world_and_normal_shortcut_locks_unchanged(self):
        scene = self.scene
        collection = scene.cutscene_collection
        seen = collection.seen.copy()
        before = self.snapshot()
        scene.open_dev_mode()
        scene.dev_menu.focus = 8
        scene.apply_dev_action(scene.dev_menu.activate())
        gallery = scene.game_menu.cutscene_viewer
        gallery.key('End')
        scene.start_cutscene_replay()
        self.assertIsNotNone(scene.cutscene_replay)
        self.assertEqual(scene.cutscene_replay.chapter.key, 'tower')
        scene.cutscene_replay.player.advance(1200)
        scene.advance_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertEqual(collection.seen, seen)
        self.assertTrue(scene.cutscene_campaign_active)
        scene.close_game_menu()
        event = SimpleNamespace(keysym='c', state=0x20000)
        scene.dev_key_press(event)
        scene.dev_key_release(event)
        normal = scene.game_menu.cutscene_viewer
        self.assertFalse(normal.developer)
        normal.key('End')
        scene.start_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(collection.seen, seen)

    def test_alt_c_opens_the_same_viewer_and_is_listed_in_f1(self):
        scene = self.scene
        self.assertEqual(next(item.shortcut for item in GameMenu().items if item.action == 'cutscenes'), 'Alt+C')
        event = SimpleNamespace(keysym='c', state=0x20000)
        scene.dev_key_press(event)
        gallery = scene.game_menu.cutscene_viewer
        self.assertFalse(gallery.developer)
        scene.dev_key_press(event)
        self.assertIs(scene.game_menu.cutscene_viewer, gallery)
        self.assertTrue(scene.paused)
        self.assertEqual(scene.game_menu.page, 'cutscenes')
        scene.dev_key_release(event)

    def test_intro_parts_reconstruct_silently_and_stop_at_their_own_boundaries(self):
        from pop2.cutscenes import chapter_range
        from pop2.cutscene_viewer import chapter_player
        from pop2.intro import IntroAssets

        assets = IntroAssets()
        operations = assets.program['operations']
        bounds = [chapter_range(chapter, assets.program) for chapter in CHAPTERS[:3]]
        self.assertEqual(bounds[0][0], 0)
        self.assertEqual(bounds[0][1], bounds[1][0])
        handoff = operations[bounds[1][1]:bounds[2][0]]
        self.assertFalse(any(op['op'] == 'text' and op['args'][1] for op in handoff))
        self.assertIsNone(bounds[2][1])
        for chapter, (_start, end) in zip(CHAPTERS[:3], bounds):
            with self.subTest(chapter=chapter.key):
                audio = Mock()
                player = chapter_player(chapter, assets, audio)
                # Seeking never dispatches prior narration to the audio adapter.
                self.assertLessEqual(audio.play_intro.call_count, 2)
                player.advance(1200)
                self.assertTrue(player.done)
                self.assertEqual(player.position, end or len(operations))
                self.assertEqual(assets.program['operations'], operations)

    def test_device_presentation_reuses_the_photo_and_keeps_the_world_paused_while_scrolling(self):
        from PIL import ImageChops

        scene = self.scene
        gallery = self.open_viewer()
        before = self.snapshot()
        with patch.object(scene.canvas, 'winfo_width', return_value=1920), \
                patch.object(scene.canvas, 'winfo_height', return_value=1080):
            scene.present_viewport()
            size = (1920, 1080)
            source = scene._cutscene_gallery_source[2]
            expected = gallery.draw(source, scene.ui_font, visible=True).convert('RGB')
            actual = self.displayed_gallery()
            self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
            self.assertEqual(actual.size, size)
            self.assertEqual(tuple(scene.canvas.coords(scene.canvas.find_all()[0])), (0, 0))
            photo = scene.image_ref
            strip_photo = scene._cutscene_gallery_grid_photo[1]
            scene.dev_scroll(SimpleNamespace(delta=-60, num=None))
            self.assertGreater(gallery.scroll_target, 0)
            self.assertEqual(gallery.index, 0)
            gallery.advance(1 / 60)
            scene.present_viewport()
            self.assertIs(scene.image_ref, photo)
            self.assertIs(scene._cutscene_gallery_grid_photo[1], strip_photo)
        self.assertTrue(scene.paused)
        self.assertEqual(self.snapshot(), before)

    def test_tall_window_keeps_ui_usable_and_rejects_pointer_in_the_bars(self):
        from PIL import ImageTk
        from pop2.game_ui import fit_menu_viewport

        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene.canvas, 'winfo_width', return_value=1020), \
                patch.object(scene.canvas, 'winfo_height', return_value=1200):
            scene.present_viewport()
            size, origin = fit_menu_viewport(1020, 1200)
            self.assertEqual(size, (1020, 768))
            self.assertEqual(origin, (0, 216))
            self.assertEqual(ImageTk.getimage(scene.image_ref).size, size)
            self.assertEqual(gallery.COLUMNS, 3)
            self.assertIsNone(scene.dev_pointer(SimpleNamespace(x=500, y=10)))
            self.assertIsNone(scene.dev_pointer(SimpleNamespace(x=500, y=1190)))
            x, y = scene.dev_pointer(SimpleNamespace(x=500, y=600))
            self.assertAlmostEqual(x, 251)
            self.assertAlmostEqual(y, 192)

    def test_incremental_scroll_pixels_match_full_render_in_both_directions_and_after_toast(self):
        from PIL import ImageChops

        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene.canvas, 'winfo_width', return_value=1280), \
                patch.object(scene.canvas, 'winfo_height', return_value=960):
            scene.present_viewport()
            photo = scene.image_ref
            for step in (1, 1, -1, -1, 20, -20):
                gallery.wheel(step)
                for _ in range(3):
                    gallery.advance(1 / 60)
                    with patch('PIL.ImageChops.difference', side_effect=AssertionError('Compared full frame during scroll')):
                        scene.present_viewport()
                    source = scene._cutscene_gallery_source[2]
                    expected = gallery.draw(source, scene.ui_font, visible=True,
                                            background_key=id(scene.screenshot_viewport)).convert('RGB')
                    actual = self.displayed_gallery()
                    self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
                    self.assertIs(scene.image_ref, photo)
            scene.screenshot_toast = 'Saved screenshot'
            scene.present_viewport()
            gallery.wheel(1)
            gallery.advance(1 / 60)
            scene.present_viewport()
            expected = scene.draw_screenshot_notice(gallery.draw(source, scene.ui_font, visible=True,
                background_key=id(scene.screenshot_viewport)), visible=True, uniform=True).convert('RGB')
            self.assertIsNone(ImageChops.difference(self.displayed_gallery(), expected).getbbox())

    def test_fast_scroll_and_bounce_skip_full_composition_and_match_all_pixels(self):
        from PIL import ImageChops

        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene.canvas, 'winfo_width', return_value=1280), \
                patch.object(scene.canvas, 'winfo_height', return_value=960):
            scene.present_viewport()
            for step in (-1, 1, 20, -20):
                gallery.wheel(step)
                for _ in range(45):
                    gallery.advance(1 / 120)
                    with patch.object(scene, 'cutscene_gallery_frame',
                                      side_effect=AssertionError('Full image composed during scrolling')):
                        scene.present_viewport()
                    source = scene._cutscene_gallery_source[2]
                    expected = gallery.draw(source, scene.ui_font, visible=True,
                        background_key=id(scene.screenshot_viewport)).convert('RGB')
                    self.assertIsNone(ImageChops.difference(self.displayed_gallery(), expected).getbbox())
            # A hover after fast movement must not compare against stale PIL pixels.
            gallery.hovered = 100 + gallery.index
            scene.present_viewport()
            expected = gallery.draw(source, scene.ui_font, visible=True,
                background_key=id(scene.screenshot_viewport)).convert('RGB')
            self.assertIsNone(ImageChops.difference(self.displayed_gallery(), expected).getbbox())

    def test_retained_strip_maps_input_in_a_tall_window_and_disposes_before_replay(self):
        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene.canvas, 'winfo_width', return_value=1020), \
                patch.object(scene.canvas, 'winfo_height', return_value=1200):
            scene.present_viewport()
            strip = scene._cutscene_gallery_strip
            self.assertIn('DevelopmentInput', strip.canvas.bindtags())
            rect = gallery.card_rect(0)
            x, y = (rect[0] + 20 - 1) * 2, (rect[1] + 20) * 2 + 216
            event = SimpleNamespace(x=x - strip.region[0], y=y - strip.region[1], num=1)
            strip.forward(scene.dev_click)(event)
            self.assertIsNone(scene.cutscene_replay)                  # the press alone starts nothing
            self.assertIs(scene._cutscene_gallery_strip, strip)
            strip.forward(scene.dev_release)(event)                   # one click plays the card
            self.assertEqual(gallery.last_clicked, 0)
            self.assertIsNotNone(scene.cutscene_replay)
            self.assertIsNone(scene._cutscene_gallery_strip)
            self.assertFalse(strip.canvas.winfo_exists())
            scene.stop_cutscene_replay()
            self.assertTrue(scene._cutscene_gallery_strip.shown)
            scene.close_game_menu()
            self.assertIsNone(scene._cutscene_gallery_strip)

    def test_strip_leave_preserves_a_held_drag_and_parent_photo_is_not_copied_during_motion(self):
        scene = self.scene
        gallery = self.open_viewer()
        strip = scene._cutscene_gallery_strip
        with patch.object(scene, 'dev_pointer_leave') as leave:
            strip.leave(SimpleNamespace(state=0x100))
            leave.assert_not_called()
            strip.leave(SimpleNamespace(state=0))
            leave.assert_called_once()
        gallery.wheel(.5)
        with patch.object(scene.image_ref, 'paste', side_effect=AssertionError('Copied frame pixels')):
            for _ in range(10):
                gallery.advance(1 / 120)
                scene.present_viewport()
        self.assertLess(strip.canvas.coords(strip.item)[0], 0)

    def test_scrolling_does_not_invalidate_the_static_background_by_reassigning_its_coordinates(self):
        scene = self.scene
        gallery = self.open_viewer()
        gallery.wheel(.5)
        with patch.object(scene.canvas, 'coords', wraps=scene.canvas.coords) as coords:
            for _ in range(10):
                gallery.advance(1 / 120)
                scene.present_viewport()
        self.assertFalse(any(len(call.args) > 1 for call in coords.call_args_list))

    def test_animation_accounts_for_tk_idle_paint_and_rechecks_monitor_rate(self):
        from pop2.menu_animation import MenuFrameClock

        scene = self.scene
        gallery = self.open_viewer()
        scene.cancel_cutscene_gallery_tick()
        gallery.wheel(1)
        now, clocks = [10.0], []

        def clock(*args, **kwargs):
            value = MenuFrameClock(*args, **kwargs)
            clocks.append(value)
            return value

        with patch('pop2.cutscene_viewer.time.perf_counter', side_effect=lambda: now[0]), \
                patch('pop2.display_refresh.window_refresh_rate', side_effect=(120, 240)) as rate, \
                patch('pop2.menu_animation.MenuFrameClock', side_effect=clock), \
                patch.object(gallery, 'advance', return_value=True), \
                patch.object(scene, 'present_viewport'), \
                patch.object(scene.root, 'after', return_value='timer') as timer, \
                patch.object(scene.root, 'after_idle', return_value='paint') as idle, \
                patch.object(scene.root, 'after_cancel') as cancel:
            scene.schedule_cutscene_gallery()
            self.assertEqual(clocks[0].refresh_hz, 120)
            tick = timer.call_args.args[1]
            now[0] += .009
            tick()
            self.assertEqual(timer.call_count, 1)  # No next frame before Tk paints.
            self.assertEqual(scene.cutscene_gallery_after_id, 'paint')
            now[0] += .004
            idle.call_args.args[0]()
            self.assertGreater(clocks[0].cost, .0005)
            self.assertEqual(timer.call_count, 2)
            now[0] += 1.1
            gallery.wheel(1)
            timer.call_args.args[1]()
            self.assertEqual(clocks[0].refresh_hz, 240)
            self.assertEqual(rate.call_count, 2)
            scene.cancel_cutscene_gallery_tick()
            cancel.assert_called_once_with('paint')
            self.assertIsNone(scene.cutscene_gallery_after_id)

    def test_wide_pointer_resize_and_replay_use_their_own_viewports(self):
        from PIL import ImageTk
        from pop2.game_ui import fit_viewport

        scene = self.scene
        gallery = self.open_viewer()
        before = self.snapshot()
        with patch.object(scene.canvas, 'winfo_width', return_value=2560), \
                patch.object(scene.canvas, 'winfo_height', return_value=1080):
            scene.present_viewport()
            self.assertEqual(ImageTk.getimage(scene.image_ref).size, (2560, 1080))
            self.assertFalse(scene.window_aspect_locked())
            scale = 1080 / 384
            rect = gallery.card_rect(0)
            x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            event = SimpleNamespace(x=(x - 1) * scale, y=y * scale, num=1)
            self.assertEqual(gallery.hit(*scene.dev_pointer(event)), 100)
            scene.dev_click(event)
            self.assertIsNone(scene.cutscene_replay)
            scene.dev_release(event)
            self.assertIsNotNone(scene.cutscene_replay)
            size, position = fit_viewport(2560, 1080)
            self.assertEqual(ImageTk.getimage(scene.image_ref).size, size)
            self.assertEqual(tuple(scene.canvas.coords(scene.canvas.find_all()[0])), position)
            self.assertIsNone(scene.dev_pointer(SimpleNamespace(x=10, y=500)))
            scene.stop_cutscene_replay()
            self.assertEqual(ImageTk.getimage(scene.image_ref).size, (2560, 1080))
            self.assertEqual(gallery.COLUMNS, 4)
            scene.close_game_menu()
            self.assertTrue(scene.window_aspect_locked())
            self.assertEqual(ImageTk.getimage(scene.image_ref).size, size)
            self.assertEqual(tuple(scene.canvas.coords(scene.canvas.find_all()[0])), position)
        self.assertEqual(self.snapshot(), before)

    def test_wide_ui_capture_preserves_aspect_without_mutating_live_gallery(self):
        from pop2.screenshots import ScreenshotSettings

        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene.canvas, 'winfo_width', return_value=1920), \
                patch.object(scene.canvas, 'winfo_height', return_value=1080):
            scene.present_viewport()
            gallery.begin_drag(200, 150)
            gallery.hovered = 100
            state = (gallery.layout_size, gallery.drag, gallery.hovered,
                     gallery.scroll, gallery.background_cache, gallery.grid_cache)
            expected = scene.cutscene_gallery_frame((2048, 1152), capture=True)
            self.assertEqual((gallery.layout_size, gallery.drag, gallery.hovered,
                              gallery.scroll, gallery.background_cache, gallery.grid_cache), state)
            scene.screenshot_settings = ScreenshotSettings(Path(self.directory.name), 3)
            path = scene.capture_screenshot(include_ui=True)
            with Image.open(path) as actual:
                self.assertEqual(actual.size, (2048, 1152))
                self.assertEqual(actual.tobytes(), expected.tobytes())
            # The success toast redraws the live cache, but cannot change input.
            self.assertEqual((gallery.layout_size, gallery.drag, gallery.hovered,
                              gallery.scroll), state[:4])

    def test_hover_and_tk_redraw_keep_a_retained_image_in_both_window_modes(self):
        from PIL import ImageChops

        scene = self.scene
        # Exercise the real production path, including hover and Tk invalidation.
        gallery = self.open_viewer()
        with patch.object(scene.canvas, 'winfo_width', return_value=1280), \
                patch.object(scene.canvas, 'winfo_height', return_value=960):
            for fullscreen in (False, True):
                scene.fullscreen = fullscreen  # Hidden fixture, never map/focus.
                scene.present_viewport()
                for point in ((70, 100), (230, 240), (450, 35), (300, 100), (-1, -1)):
                    with patch.object(scene, 'dev_pointer', return_value=point):
                        scene.dev_hover(SimpleNamespace())
                    scene.root.update_idletasks()
                    self.assertIsNone(scene.bitmap_presenter)
                    self.assertIsNotNone(scene.image_ref)
                    item = scene.canvas.find_all()[0]
                    self.assertEqual(scene.canvas.itemcget(item, 'image'), str(scene.image_ref))
                    # Tk can redisplay this same retained image after cursor,
                    # hover, expose or item invalidation; no direct paint is lost.
                    scene.canvas.itemconfigure(item, state='hidden')
                    scene.root.update_idletasks()
                    scene.canvas.itemconfigure(item, state='normal')
                    scene.canvas.event_generate('<Expose>')
                    scene.root.update_idletasks()
                    source = scene._cutscene_gallery_source[2]
                    expected = gallery.draw(source, scene.ui_font, visible=True,
                        background_key=id(scene.screenshot_viewport)).convert('RGB')
                    actual = self.displayed_gallery()
                    self.assertIsNone(ImageChops.difference(actual, expected).getbbox())

    def test_hover_within_the_same_card_does_not_reconfigure_or_redraw_the_canvas(self):
        scene = self.scene
        self.open_viewer()
        with patch.object(scene, 'dev_pointer', return_value=(70, 100)):
            scene.dev_hover(SimpleNamespace())
            with patch.object(scene.canvas, 'configure', wraps=scene.canvas.configure) as configure, \
                    patch.object(scene, 'redraw_cutscene_gallery', wraps=scene.redraw_cutscene_gallery) as redraw:
                for _ in range(20):
                    scene.dev_hover(SimpleNamespace())
        configure.assert_not_called()
        redraw.assert_not_called()
        self.assertIsNotNone(scene.image_ref)
        self.assertTrue(scene.paused)

    def test_crossing_cards_changes_only_the_retained_hover_border_without_loading_or_painting_images(self):
        from PIL import ImageChops

        scene = self.scene
        gallery = self.open_viewer()
        photo = scene._cutscene_gallery_strip.photo
        grid = gallery.grid_cache[1]
        with patch.object(scene, 'cutscene_gallery_frame', side_effect=AssertionError('Composed hover frame')), \
                patch('PIL.ImageTk.PhotoImage', side_effect=AssertionError('Uploaded hover photo')), \
                patch.object(scene.ui_font, 'text', side_effect=AssertionError('Drew hover text')):
            for index in (1, 2, 3, 4, 5, 0, 4):
                rect = gallery.card_rect(index)
                with patch.object(scene, 'dev_pointer', return_value=(rect[0] + 10, rect[1] + 10)):
                    scene.dev_hover(SimpleNamespace())
                self.assertEqual(gallery.hovered, index + 100)
                self.assertIs(scene._cutscene_gallery_strip.photo, photo)
                self.assertIs(gallery.grid_cache[1], grid)
        source = scene._cutscene_gallery_source[2]
        expected = gallery.draw(source, scene.ui_font, visible=True,
            background_key=id(scene.screenshot_viewport)).convert('RGB')
        self.assertIsNone(ImageChops.difference(self.displayed_gallery(), expected).getbbox())

    def test_pointer_drag_does_not_play_or_select_and_leave_cancels_the_drag(self):
        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene, 'dev_pointer', return_value=(220, 150)):
            scene.dev_click(SimpleNamespace(num=1))
        with patch.object(scene, 'dev_pointer', return_value=(180, 150)):
            scene.dev_hover(SimpleNamespace())
            scene.dev_release(SimpleNamespace(num=1))
        self.assertEqual(gallery.scroll, 40)
        self.assertEqual(gallery.index, 0)
        self.assertIsNone(scene.cutscene_replay)
        with patch.object(scene, 'dev_pointer', return_value=(220, 150)):
            scene.dev_click(SimpleNamespace(num=1))
        scene.pause_if_unfocused()
        self.assertIsNone(gallery.drag)
        with patch.object(scene, 'dev_pointer', return_value=(220, 150)):
            scene.dev_click(SimpleNamespace(num=1))
        scene.dev_pointer_leave(SimpleNamespace())
        self.assertIsNone(gallery.drag)

    def test_one_click_starts_the_film_and_a_habitual_double_click_does_not_pause_it(self):
        scene = self.scene
        scene.audio = Mock()
        gallery = self.open_viewer()
        self.assertIn('dev_double_click', scene.canvas.bind('<Double-Button-1>'))
        before = self.snapshot()
        rect = gallery.card_rect(0)
        point = rect[0] + 20, rect[1] + 20
        with patch.object(scene, 'dev_pointer', return_value=point):
            scene.dev_click(SimpleNamespace(num=1))
            self.assertIsNone(scene.cutscene_replay)
            scene.dev_release(SimpleNamespace(num=1))
            replay = scene.cutscene_replay
            self.assertIsNotNone(replay)
            scene.audio.play_ui.assert_called_with('click')
            # The second press and release of a double click arrive while the film is already playing.
            scene.dev_double_click(SimpleNamespace(num=1))
            scene.dev_release(SimpleNamespace(num=1))
            self.assertIs(scene.cutscene_replay, replay)
            self.assertFalse(replay.paused)
            # Later, a click pauses it as before.
            replay.started_at -= 1
            scene.dev_click(SimpleNamespace(num=1))
            self.assertTrue(replay.paused)
        self.assertEqual(self.snapshot(), before)

    def test_every_chapter_finishes_in_the_gallery_without_touching_the_live_world(self):
        scene = self.scene
        scene.cutscene_collection.seen.update(CHAPTER_KEYS)
        before, game, combat = self.snapshot(), scene.game, scene.combat
        gallery = self.open_viewer()
        self.assertEqual(self.snapshot(), before)
        for index, chapter in enumerate(CHAPTERS):
            with self.subTest(chapter=chapter.key):
                gallery.index = index
                scene.start_cutscene_replay()
                self.assertIsNotNone(scene.cutscene_replay, gallery.error)
                player = scene.cutscene_replay.player
                player.advance(1200)
                self.assertTrue(player.done)
                scene.advance_cutscene_replay()
                self.assertIsNone(scene.cutscene_replay)
                self.assertEqual(scene.game_menu.page, 'cutscenes')
                self.assertTrue(scene.paused)
                self.assertIs(scene.game, game)
                self.assertIs(scene.combat, combat)
                self.assertEqual(self.snapshot(), before)

    def test_escape_focus_loss_and_stop_preserve_an_interrupted_campaign_cutscene(self):
        scene = self.scene
        scene.start_intro()
        original = scene.intro
        original.advance(3)
        position = original.position, original.time
        gallery = self.open_viewer()
        scene.start_cutscene_replay()
        self.assertIsNot(scene.cutscene_replay.player, original)
        scene.cutscene_replay.player.advance(2)
        scene.pause_cutscene_replay(True)
        self.assertTrue(scene.cutscene_replay.paused)
        self.assertIsNone(scene.cutscene_after_id)
        scene.pause_cutscene_replay(False)
        self.assertIsNotNone(scene.cutscene_after_id)
        scene.pause_if_unfocused()
        self.assertTrue(scene.cutscene_replay.paused)
        scene.stop_cutscene_replay()
        self.assertEqual((original.position, original.time), position)
        self.assertIs(scene.intro, original)
        self.assertEqual(gallery.index, 0)
        scene.close_game_menu()
        self.assertIs(scene.intro, original)

    def test_locked_play_and_replay_navigation_never_unlock_future_scenes(self):
        scene = self.scene
        gallery = self.open_viewer()
        gallery.index = 5
        scene.start_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))

        scene.close_game_menu()
        scene.with_intro = True
        scene.seek_playback_part(next(part for part in scene.development_parts() if part.stage == 'temple'))
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))

    def test_replay_input_blocks_game_commands_escape_pauses_and_space_skips(self):
        scene = self.scene
        self.open_viewer()
        scene.start_cutscene_replay()
        original = scene.cutscene_replay
        before = self.snapshot()
        for key in ('Left', 'Down', 'F3', 'F2'):
            event = SimpleNamespace(keysym=key, state=0)
            scene.dev_key_press(event)
            scene.dev_key_release(event)
        with patch.object(scene, 'new_game') as new_game:
            event = SimpleNamespace(keysym='n', state=0x20000)
            scene.dev_key_press(event)
            scene.dev_key_release(event)
            new_game.assert_not_called()
        self.assertIs(scene.cutscene_replay, original)
        self.assertEqual(self.snapshot(), before)
        event = SimpleNamespace(keysym='Escape', state=0)
        scene.dev_key_press(event)
        self.assertTrue(original.paused)
        scene.dev_key_press(event)
        self.assertTrue(original.paused)
        scene.dev_key_release(event)
        scene.dev_key_press(event)
        self.assertFalse(original.paused)
        scene.dev_key_release(event)
        original.started_at -= 1                                      # past the double-click grace
        with patch.object(scene, 'dev_pointer', return_value=(400, 375)):
            scene.dev_click(SimpleNamespace(num=1))
        self.assertIs(scene.cutscene_replay, original)
        self.assertTrue(original.paused)
        event = SimpleNamespace(keysym='space', state=0)
        scene.dev_key_press(event)
        self.assertIsNone(scene.cutscene_replay)
        self.assertEqual(scene.game_menu.page, 'cutscenes')
        # Auto-repeat from the skip gesture must not activate the selected card.
        scene.dev_key_press(event)
        self.assertIsNone(scene.cutscene_replay)
        scene.dev_key_release(event)
        self.assertEqual(self.snapshot(), before)

    def test_space_skips_a_playing_film_and_escape_keeps_the_same_gallery_and_private_player(self):
        scene = self.scene
        gallery = self.open_viewer()
        scene.start_cutscene_replay()
        replay = scene.cutscene_replay
        event = SimpleNamespace(keysym='Escape', state=0)
        for paused in (True, False):
            scene.dev_key_press(event)
            self.assertIs(scene.cutscene_replay, replay)
            self.assertEqual(replay.paused, paused)
            self.assertIs(scene.game_menu.cutscene_viewer, gallery)
            self.assertEqual(scene.game_menu.page, 'cutscenes')
            scene.dev_key_release(event)
        scene.dev_key_press(SimpleNamespace(keysym='space', state=0))
        self.assertIsNone(scene.cutscene_replay)
        self.assertIs(scene.game_menu.cutscene_viewer, gallery)
        self.assertEqual(scene.game_menu.page, 'cutscenes')

    def test_replay_renders_no_key_legends_in_play_or_pause(self):
        scene = self.scene
        self.open_viewer()
        scene.start_cutscene_replay()
        for paused in (False, True):
            scene.pause_cutscene_replay(paused)
            with patch.object(scene.ui_font, 'text', wraps=scene.ui_font.text) as text:
                scene.render_cutscene_replay()
            self.assertFalse(any('Esc:' in call.args[0] or 'Space:' in call.args[0]
                                 for call in text.call_args_list))
            if not paused:
                self.assertEqual(scene.native_viewport.convert('RGB').tobytes(),
                                 scene.screenshot_viewport.convert('RGB').tobytes())

    def test_failed_film_open_is_reported_without_destroying_the_live_session(self):
        scene = self.scene
        self.open_viewer()
        before = self.snapshot()
        provider = scene.cutscene_preview_provider()
        provider.assets.clear()
        with patch('pop2.intro.IntroAssets', side_effect=ValueError('Missing import')), \
                self.assertLogs('pop2.cutscene_viewer', level='ERROR') as logs:
            scene.start_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertIn('importing the game again', scene.game_menu.cutscene_viewer.error)
        self.assertIn('Missing import', '\n'.join(logs.output))
        self.assertEqual(self.snapshot(), before)

    def test_error_during_playback_returns_safely_and_cancels_the_viewer_tick(self):
        scene = self.scene
        self.open_viewer()
        before = self.snapshot()
        scene.start_cutscene_replay()
        with patch.object(scene.cutscene_replay.player, 'advance', side_effect=ValueError('Broken scene')), \
                self.assertLogs('pop2.cutscene_viewer', level='ERROR'):
            scene.advance_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertIsNone(scene.cutscene_after_id)
        self.assertTrue(scene.game_menu.cutscene_viewer.error)
        self.assertTrue(scene.paused)
        self.assertEqual(self.snapshot(), before)

    def test_loading_an_older_save_backfills_chapters_but_warping_and_saving_do_not(self):
        from pop2.save_game import capture, write_save

        scene = self.scene
        scene.load_level(6)
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))
        path = Path(self.directory.name) / 'old-save.pop2save'
        write_save(path, capture(scene.game))
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))
        scene.load_game_from(path)
        self.assertEqual(scene.cutscene_collection.seen, OPENING_KEYS | {'voyage', 'discovery', 'carpet'})

    def test_each_save_restores_its_own_cutscenes_and_new_game_starts_fresh(self):
        from pop2.save_game import read_document

        scene = self.scene
        early = Path(self.directory.name) / 'early.pop2save'
        advanced = Path(self.directory.name) / 'advanced.pop2save'
        scene.mark_cutscene_seen('voyage')
        scene.save_game_to(early)
        scene.mark_cutscene_seen('discovery')
        scene.save_game_to(advanced)
        self.assertEqual(read_document(early)['cutscenes'], sorted(OPENING_KEYS | {'voyage'}))
        self.assertEqual(read_document(advanced)['cutscenes'],
                         sorted(OPENING_KEYS | {'voyage', 'discovery'}))
        scene.new_game()
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))
        scene.load_game_from(advanced)
        self.assertEqual(scene.cutscene_collection.seen, OPENING_KEYS | {'voyage', 'discovery'})
        scene.load_game_from(early)
        self.assertEqual(scene.cutscene_collection.seen, OPENING_KEYS | {'voyage'})

    def test_viewer_over_a_copy_challenge_pauses_on_focus_loss_and_resets_its_clock_on_return(self):
        scene = self.scene
        from pop2.copy_protection import CopyProtection

        scene.copy_challenge = CopyProtection(scene.resources.prince)
        scene.last_copy_at = 1.0
        self.open_viewer()
        scene.start_cutscene_replay()
        scene.pause_if_unfocused()
        self.assertTrue(scene.cutscene_replay.paused)
        scene.stop_cutscene_replay()
        with patch('pop2.window_controls.time.perf_counter', return_value=1000.0):
            scene.close_game_menu(resume=True)
        self.assertEqual(scene.last_copy_at, 1000.0)

    def test_actual_f3_warp_then_horse_trigger_does_not_unlock_campaign_chapters(self):
        scene = self.scene
        scene.cutscene_collection.unlock('voyage', 'discovery', 'carpet', 'vision')
        scene.load_level(9)
        scene.open_dev_mode()
        scene.apply_dev_action('go')
        self.assertFalse(scene.cutscene_campaign_active)
        scene.start_temple_ride(lambda: None)
        self.assertNotIn('horse', scene.cutscene_collection.seen)
        scene.new_game()
        self.assertTrue(scene.cutscene_campaign_active)
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))
        scene.start_temple_ride(lambda: None)
        self.assertNotIn('horse', scene.cutscene_collection.seen)

    def test_natural_story_starts_unlock_each_chapter_and_new_game_resets_the_collection(self):
        scene = self.scene
        for start, expected in ((scene.start_ending, 'voyage'), (scene.start_discovery, 'discovery'),
                                (scene.start_carpet, 'carpet'), (lambda: scene.start_vision(lambda: None), 'vision'),
                                (lambda: scene.start_temple_ride(lambda: None), 'horse'),
                                (lambda: scene.start_tower_flight(lambda: None), 'tower')):
            start()
            self.assertIn(expected, scene.cutscene_collection.seen)
        scene.new_game()
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))


if __name__ == '__main__':
    unittest.main()
