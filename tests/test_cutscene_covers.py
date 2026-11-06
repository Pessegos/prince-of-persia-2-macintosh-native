import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.cutscene_covers import COVER_SHOTS, COVER_SIZE, selected_cover
from pop2.cutscene_viewer import ChapterPreviews
from pop2.cutscenes import CHAPTERS
from pop2.paths import ASSET_DIR
from pop2.playback_navigation import PlaybackPart


class CoverCompositionTests(unittest.TestCase):
    def test_the_supplied_four_three_title_is_contained_without_a_stretch(self):
        player = Mock()
        player.frame.return_value = Image.new('RGB', (512, 384), '#ff8844')
        cover = selected_cover(player, 'opening_titles')
        self.assertEqual(cover.size, COVER_SIZE)
        self.assertEqual(cover.getpixel((127, 100)), (16, 16, 16))
        self.assertEqual(cover.getpixel((128, 100)), (255, 136, 68))
        self.assertEqual(cover.getpixel((895, 100)), (255, 136, 68))
        self.assertEqual(cover.getpixel((896, 100)), (16, 16, 16))


@unittest.skipUnless(all((ASSET_DIR / c.program).is_file() for c in CHAPTERS),
                     'Imported story programs required')
class ImportedSelectedCoverTests(unittest.TestCase):
    def test_covers_match_the_users_nine_supplied_crops(self):
        # RGB hashes of the independently supplied PNGs fitted into 1024x576,
        # with only the 4:3 title contained. No game artwork is stored in tests.
        expected = {
            'opening': '8c2a1c8e0451f0a255ce330f96ccaa47f60733a31fb28d19e01dbe51bb60cf54',
            'opening_titles': '27b105d489dff83cda6bb7b119e5be1fb6438f6dec9a86b9f9d69fb63b0117bf',
            'opening_story': 'cb521138e947aaa4091bf525709d52767154d94bbcd366007cbc21874ebe6beb',
            'voyage': '47838e11ac0e73ad3398ff816e1c262ef4cf36f1db23112b85501976bc66d7bb',
            'discovery': '7a809b06ca73a7b7b2651915364c5b583260068df2b3af3c34bbc5bc57351df4',
            'carpet': 'dd0640e6b4bc449f69d4fa8671f23e453c312d107f33dd596f0e13d79e30cda6',
            'vision': '1e9d3b5622f8ab3ef2e6cef761bee08f3aa38fe5cefd607c257d9f2595762c13',
            'horse': '819555f6e2869d00d8e056c8561de5d499d47695d7d14f08999cb3f5fd9190b0',
            'tower': 'f367390ae6137ab0551769108e4f15146cbd07581789af9eb7fae9fd2bb24748',
        }
        self.assertEqual(set(COVER_SHOTS), {c.key for c in CHAPTERS})
        provider = ChapterPreviews(None, (), None, 'unused')
        for index, chapter in enumerate(CHAPTERS):
            with self.subTest(chapter=chapter.key):
                cover = provider.snapshot(index)
                self.assertEqual(cover.size, COVER_SIZE)
                self.assertEqual(hashlib.sha256(cover.tobytes()).hexdigest(), expected[chapter.key])

    def test_selected_cover_cache_is_reused_by_a_new_provider(self):
        from pop2.intro import IntroAssets

        parts = tuple(PlaybackPart(c.title, c.program.removesuffix('.json'),
                                  round(c.preview_seconds * 1000)) for c in CHAPTERS)
        with TemporaryDirectory() as directory:
            first = ChapterPreviews(None, parts, None, 'selected-cover-test', Path(directory))
            first.assets['intro'] = IntroAssets(program_name='intro.json')
            expected = first.group((0,))[0]
            second = ChapterPreviews(None, parts, None, 'selected-cover-test', Path(directory))
            with patch.object(second, 'snapshot', side_effect=AssertionError('Warm cover was rebuilt')):
                actual = second.group((0,))[0]
            self.assertEqual(actual.tobytes(), expected.tobytes())
