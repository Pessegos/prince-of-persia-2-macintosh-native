import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pop2.import_advice as advice
from pop2.import_advice import (
    HEAD, PROBLEMS, REQUIRED_SPACE, describe_missing, image_format, os_problem, preflight, sniff_image,
    unreadable_volume)
from pop2.mac_resources import NoHfsVolume, VOLUME_SEARCH, get_resource_fork, has_hfs_volume
from tests.test_mac_resources import hfs_image


def iso(size=40 * 2048):
    image = bytearray(size)
    image[16 * 2048:16 * 2048 + 7] = b"\x01CD001\x01"
    return image


class ImageFormatTests(unittest.TestCase):
    def test_volumes_the_reader_finds_are_hfs_from_the_head_alone(self):
        for wrapper in (0, 84, 93 * 512):
            with self.subTest(wrapper=wrapper):
                image = hfs_image(wrapper)
                if wrapper:
                    image[16 * 2048:16 * 2048 + 7] = b"\x01CD001\x01"
                self.assertEqual(image_format(bytes(image[:HEAD])), 'hfs')
                self.assertEqual(get_resource_fork(image, 'Prince.rsrc'), b'abc')

    def test_the_head_decides_exactly_as_the_whole_image(self):
        # Beyond the reader's search a volume is not found in either.
        image = bytearray(VOLUME_SEARCH + 8192)
        image[VOLUME_SEARCH + 1024:VOLUME_SEARCH + 1026] = b'BD'
        self.assertFalse(has_hfs_volume(image))
        self.assertFalse(has_hfs_volume(image[:HEAD]))
        with self.assertRaises(NoHfsVolume):
            get_resource_fork(image, 'Prince.rsrc')

    def test_other_files_are_named_by_their_own_signatures(self):
        stuffit = bytearray(4096)
        stuffit[:4] = b'SIT!'
        binhex = b'\r\n(This file must be converted with BinHex 4.0)\r\n:' + bytes(4000)
        hfs_plus = bytearray(4096)
        hfs_plus[1024:1028] = b'H+\x00\x04'
        partitioned_plus = bytearray(80 * 512)
        partitioned_plus[64 * 512 + 1024:64 * 512 + 1028] = b'H+\x00\x04'
        raw = bytearray(4 * 2352)
        raw[:12] = b'\x00' + b'\xff' * 10 + b'\x00'
        cases = (
            (b'PK\x03\x04' + bytes(4000), b'', 'archive'),
            (b'7z\xbc\xaf\x27\x1c' + bytes(4000), b'', 'archive'),
            (b'Rar!\x1a\x07\x00' + bytes(4000), b'', 'archive'),
            (b'BZh9' + bytes(4000), b'', 'archive'),
            (bytes(stuffit), b'', 'archive'),
            (binhex, b'', 'archive'),
            (bytes(4096), b'koly' + bytes(508), 'compressed_dmg'),
            (bytes(raw), b'', 'raw_cd'),
            (bytes(hfs_plus), b'', 'hfs_plus'),
            (bytes(partitioned_plus), b'', 'hfs_plus'),
            (bytes(iso()), b'', 'pc_only'),
            (b'MZ' + bytes(9000), b'', 'not_mac'),
            (b'', b'', 'not_mac'),
        )
        for head, tail, kind in cases:
            with self.subTest(kind=kind, start=head[:8]):
                self.assertEqual(image_format(head, tail), kind)
                self.assertIn(kind, PROBLEMS)

    def test_a_volume_found_by_chance_in_compressed_data_is_not_called_damaged(self):
        self.assertEqual(unreadable_volume(b'PK\x03\x04' + bytes(100)), 'archive')
        self.assertEqual(unreadable_volume(bytes(100), b'koly' + bytes(508)), 'compressed_dmg')
        self.assertEqual(unreadable_volume(bytes(100), bytes(512)), 'damaged')

    def test_sniffing_a_file_reads_its_ends(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.dmg'
            path.write_bytes(bytes(HEAD + 10_000) + b'koly' + bytes(508))
            self.assertEqual(sniff_image(path), 'compressed_dmg')
            # A short file: the head and tail never overlap.
            path.write_bytes(b'koly' + bytes(508))
            self.assertEqual(sniff_image(path), 'not_mac')
            path.write_bytes(bytes(hfs_image(84)))
            self.assertEqual(sniff_image(path), 'hfs')


class PreflightTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.image = self.directory / 'game.hfs'
        self.image.write_bytes(bytes(hfs_image()))

    def test_a_readable_volume_with_room_to_import_goes_ahead(self):
        self.assertIsNone(preflight(self.image, self.directory))

    def test_missing_files_other_kinds_and_a_full_drive_stop_the_import(self):
        self.assertEqual(preflight(self.directory / 'gone.hfs', self.directory), 'unreadable')
        (self.directory / 'game.zip').write_bytes(b'PK\x03\x04' + bytes(100))
        self.assertEqual(preflight(self.directory / 'game.zip', self.directory), 'archive')
        usage = type('Usage', (), {'free': REQUIRED_SPACE - 1})()
        with patch.object(advice.shutil, 'disk_usage', return_value=usage):
            self.assertEqual(preflight(self.image, self.directory), 'no_space')


class OsProblemTests(unittest.TestCase):
    def test_errors_are_named_for_the_player(self):
        image = 'C:/Games/pop2.hfs'
        full = OSError(errno.ENOSPC, 'No space left on device')
        windows_full = OSError(None, 'There is not enough space on the disk')
        windows_full.winerror = 112
        self.assertEqual(os_problem(full), 'no_space')
        self.assertEqual(os_problem(windows_full), 'no_space')
        self.assertEqual(os_problem(PermissionError(13, 'Denied', image), image), 'unreadable')
        self.assertEqual(os_problem(FileNotFoundError(2, 'Gone', image), image), 'unreadable')
        self.assertEqual(os_problem(PermissionError(13, 'Denied', 'C:/Program Files/PoP2/assets'), image),
                         'not_writable')
        self.assertEqual(os_problem(OSError('Disk full')), 'failed')


class MissingFilesTests(unittest.TestCase):
    def test_missing_entries_are_described_by_the_part_of_the_game(self):
        self.assertEqual(describe_missing(['ruins_level7.json (needs full level-seven scenery)']),
                         'the level scenery (level 7)')
        self.assertEqual(
            describe_missing(['caverns_entry.json', 'caverns_level4.json', 'temple_level10.json',
                              'temple_level11.json (needs the temple blades)', 'temple_level12.json',
                              'temple_level13.json', 'audio/cue-40.wav', 'audio/manifest.json (needs reimport)',
                              'intro.json (needs reimport)', 'tree-3.json', 'Kid.rsrc', 'attract.json',
                              'enemy_profiles.json', 'final_level14.json (needs reimport)']),
            "the level scenery (levels 3, 4 and 10\u201314), the audio, the cutscenes, the game's "
            "resource files, the demo and credits and the opponents' data")
        self.assertEqual(describe_missing(['unknown.dat']), 'unknown.dat')
        self.assertEqual(describe_missing([]), '')


if __name__ == '__main__':
    unittest.main()
