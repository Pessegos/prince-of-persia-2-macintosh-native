import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from pop2.preview_cache import preview_fingerprint, read_preview, write_preview


class PreviewCacheTests(unittest.TestCase):
    def test_round_trip_is_lossless_and_stale_or_broken_cache_is_a_miss(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'preview.zip'
            image = Image.new('RGB', (510, 360), (18, 103, 254))
            self.assertIsNone(read_preview(path, 'first'))
            write_preview(path, 'first', {'rooms': [1, 2]}, {'Room 1': image})
            metadata, images = read_preview(path, 'first')
            self.assertEqual(metadata, {'rooms': [1, 2]})
            self.assertEqual(images['Room 1'].tobytes(), image.tobytes())
            self.assertIsNone(read_preview(path, 'second'))
            with path.open('wb') as stream:
                stream.write(b'broken')
            self.assertIsNone(read_preview(path, 'first'))

    def test_oversized_cache_entries_are_rejected_before_image_allocation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'preview.zip'
            with ZipFile(path, 'w') as archive:
                manifest = dict(
                    schema=1, fingerprint='first', metadata={},
                    images=[dict(key='bad', size=[9000, 9000])])
                archive.writestr('manifest.json', json.dumps(manifest))
            with patch.object(Image, 'frombytes', side_effect=AssertionError('Unsafe allocation')):
                self.assertIsNone(read_preview(path, 'first'))

    def test_unwritable_cache_does_not_stop_preview_generation(self):
        with TemporaryDirectory() as directory:
            with patch('pop2.preview_cache.os.replace', side_effect=PermissionError):
                write_preview(Path(directory) / 'preview.zip', 'key', {}, {'one': Image.new('RGB', (2, 2))})
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_fingerprint_tracks_asset_and_render_code_changes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = preview_fingerprint(root, root)
            with (root / 'scene.json').open('w') as stream:
                stream.write('{}')
            second = preview_fingerprint(root, root)
            self.assertNotEqual(first, second)
            with (root / 'renderer.py').open('w') as stream:
                stream.write('changed = True')
            self.assertNotEqual(second, preview_fingerprint(root, root))

    def test_fingerprint_tracks_bundled_cavern_retouch_artwork(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'assets'
            assets.mkdir()
            first = preview_fingerprint(assets, root)
            Image.new('RGBA', (2, 2), 'red').save(root / 'cavern_retouch.png')
            second = preview_fingerprint(assets, root)
            self.assertNotEqual(first, second)
            Image.new('RGBA', (2, 2), 'blue').save(root / 'cavern_retouch.png')
            third = preview_fingerprint(assets, root)
            self.assertNotEqual(second, third)
            (root / 'cavern_retouch.json').write_text('{"schema":1}', encoding='ascii')
            self.assertNotEqual(third, preview_fingerprint(assets, root))
