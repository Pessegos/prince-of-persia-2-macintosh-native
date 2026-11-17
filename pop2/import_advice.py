"""What the game-files window tells the player about an import.

Why the window opened (a first import, or files this version prepares
differently) and, when an import cannot go ahead, what kind of file was
chosen and what to do about it. The kinds come from the file's own
signatures, the volume reader and the operating system's error codes.
"""

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import re
import shutil

from pop2.mac_resources import VOLUME_SEARCH, has_hfs_volume

ISSUES_URL = 'https://github.com/Pessegos/prince-of-persia-2-macintosh-native/issues'
# A complete import writes about 510 MB (mostly the prepared music). The
# files are staged on the same drive before they replace the installed ones.
REQUIRED_SPACE = 550 * 1024 * 1024


@dataclass(frozen=True)
class Problem:
    title: str
    advice: str
    # Whether choosing the same file again can succeed once the advice is
    # followed (space freed, drive reconnected...).
    retry: bool = False


PROBLEMS = {
    'unreadable': Problem(
        'The image could not be read.',
        'Check that the file is still there, that no other program has it open and that its drive '
        'is connected, then try again.', retry=True),
    'archive': Problem(
        'This file is an archive.',
        'Extract the disk image from it first (an archive tool such as 7-Zip opens most archives), '
        'then choose the extracted image.'),
    'compressed_dmg': Problem(
        'This DMG image is compressed.',
        'Convert it to an uncompressed image first (HFSExplorer or dmg2img can do this), then choose '
        'the converted file.'),
    'raw_cd': Problem(
        'This is a raw CD dump.',
        'Save the CD as an ISO image with 2,048-byte sectors instead; most CD imaging tools offer this.'),
    'hfs_plus': Problem(
        'This image uses Mac OS Extended (HFS+).',
        'The port reads the original Mac OS Standard (HFS) disks. Choose an image of the original '
        'disk or CD rather than a copy of its files.'),
    'pc_only': Problem(
        'This disc has no Macintosh part.',
        'It looks like a PC (DOS or Windows) CD. The port needs the Macintosh version of Prince of '
        'Persia 2: a Macintosh disk image or a hybrid PC/Mac CD.'),
    'not_mac': Problem(
        'This is not a Macintosh disk image.',
        'Choose an image of the Macintosh Prince of Persia 2 disk or CD.'),
    'no_game': Problem(
        'This Macintosh disk does not contain Prince of Persia 2.',
        'Choose the image that holds the installed game: the Prince of Persia 2 application and its '
        'resource files.'),
    'unsupported': Problem(
        'This copy of the game is not supported.',
        'Some of the files the port needs are missing or different. It may be a demo, another '
        'edition or an incomplete copy.'),
    'damaged': Problem(
        'The image seems to be damaged.',
        'Its Macintosh volume could not be read. If you can, make the image again from the original '
        'disk.'),
    'no_space': Problem(
        'There is not enough free disk space.',
        f'The prepared game files need about {REQUIRED_SPACE // 2**20} MB on this drive. Free some '
        'space, then try again.', retry=True),
    'not_writable': Problem(
        'The game folder cannot be written to.',
        'Move the game folder to a place where you can save files, such as Documents, then open the '
        'game again.'),
    'failed': Problem(
        'The import stopped unexpectedly.',
        "Please report it on the project's GitHub page and attach the import log.", retry=True),
}


def problem(kind):
    return PROBLEMS.get(kind, PROBLEMS['failed'])


class ImageProblem(ValueError):
    """A chosen file the import cannot use; `kind` names its PROBLEMS entry."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


# Leading bytes of archives and encodings that hold a disk image rather
# than being one: zip, 7-Zip, RAR, gzip, bzip2, xz, cabinet, StuffIt.
ARCHIVE_SIGNATURES = (b'PK\x03\x04', b'PK\x05\x06', b'7z\xbc\xaf\x27\x1c', b'Rar!\x1a\x07',
                      b'\x1f\x8b\x08', b'\xfd7zXZ\x00', b'MSCF', b'SIT!', b'StuffIt')
BINHEX = b'(This file must be converted with BinHex'
# A raw (2,352-byte) CD sector starts with this synchronisation pattern.
CD_SYNC = b'\x00' + b'\xff' * 10 + b'\x00'
# The bytes of an image that decide its kind: the reader's volume search
# and an ISO 9660 descriptor (sector 16) lie in the head, a UDIF trailer
# in the last 512 bytes.
HEAD = VOLUME_SEARCH + 4096
TAIL = 512


def _archive(head):
    return (head.startswith(ARCHIVE_SIGNATURES) or re.match(rb'BZh[1-9]', head) is not None
            or BINHEX in head[:1024])


def _hfs_plus(head):
    # An HFS+ volume header, at 1024 bytes into its partition.
    for signature in (b'H+\x00\x04', b'HX\x00\x05'):
        position = head.find(signature, 1024)
        while position >= 0:
            if position % 512 == 0:
                return True
            position = head.find(signature, position + 1)
    return False


def image_format(head, tail=b''):
    """'hfs' when the volume reader finds an HFS volume in an image starting
    with `head` (its first HEAD bytes) and ending with `tail`; otherwise
    the PROBLEMS kind of file it looks like."""
    if has_hfs_volume(head):
        return 'hfs'
    if _archive(head):
        return 'archive'
    if tail[-TAIL:].startswith(b'koly'):
        return 'compressed_dmg'
    if head.startswith(CD_SYNC):
        return 'raw_cd'
    if _hfs_plus(head):
        return 'hfs_plus'
    if head[0x8001:0x8006] in (b'CD001', b'BEA01'):
        return 'pc_only'
    return 'not_mac'


def unreadable_volume(head, tail=b''):
    """The kind of an image whose HFS volume was found but could not be
    read: a compressed image can contain the volume's signature by chance."""
    if _archive(head):
        return 'archive'
    if tail[-TAIL:].startswith(b'koly'):
        return 'compressed_dmg'
    return 'damaged'


def sniff_image(path):
    """image_format of the file at `path`, reading only its ends (OSError
    when it cannot be read)."""
    with open(path, 'rb') as image:
        head = image.read(HEAD)
        image.seek(0, os.SEEK_END)
        size = image.tell()
        image.seek(max(len(head), size - TAIL))
        tail = image.read(TAIL)
    return image_format(head, tail)


# Windows error codes: ERROR_ACCESS_DENIED, ERROR_WRITE_PROTECT,
# ERROR_HANDLE_DISK_FULL and ERROR_DISK_FULL.
_DENIED, _DISK_FULL = {5, 19}, {39, 112}


def _same_file(first, second):
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


def os_problem(error, image=None):
    """The PROBLEMS kind of an operating-system error during an import."""
    if error.errno == errno.ENOSPC or getattr(error, 'winerror', None) in _DISK_FULL:
        return 'no_space'
    if image is not None and error.filename and _same_file(error.filename, image):
        return 'unreadable'
    if isinstance(error, PermissionError) or getattr(error, 'winerror', None) in _DENIED:
        return 'not_writable'
    return 'failed'


def preflight(image, project):
    """The PROBLEMS kind that stops an import of `image` into `project`
    before it starts, or None: the file's own kind, then the free space."""
    try:
        kind = sniff_image(image)
    except OSError:
        return 'unreadable'
    if kind != 'hfs':
        return kind
    try:
        free = shutil.disk_usage(Path(project)).free
    except OSError:
        return None
    return 'no_space' if free < REQUIRED_SPACE else None


# What a run_game.missing_assets entry is part of, for the player.
_SCENERY = re.compile(r'(?:caverns_level|ruins_level|temple_level|final_level)(\d+)\.json$')
_SCENES = {'intro.json', 'ending.json', 'discovery.json', 'carpet.json', 'throne.json', 'temple.json',
           'tower.json', 'final_spell.json', 'happy.json'}


def _levels(numbers):
    runs = []
    for number in sorted(numbers):
        if runs and number == runs[-1][1] + 1:
            runs[-1][1] = number
        else:
            runs.append([number, number])
    parts = []
    for first, last in runs:
        parts.extend([str(first)] if first == last else [str(first), str(last)] if last == first + 1
                     else [f'{first}–{last}'])
    noun = 'level' if len(numbers) == 1 else 'levels'
    return f'the level scenery ({noun} {_join(parts)})'


def _join(parts):
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]


def describe_missing(missing):
    """The parts of the game that `missing` (run_game.missing_assets
    entries, 'name' or 'name (reason)') belong to, as one phrase."""
    levels, parts = set(), []

    def add(part):
        if part not in parts:
            parts.append(part)

    for entry in missing:
        name = entry.split(' (', 1)[0]
        scenery = _SCENERY.search(name)
        if name == 'caverns_entry.json':
            levels.add(3)
        elif scenery:
            levels.add(int(scenery.group(1)))
        elif name.startswith('audio/'):
            add('the audio')
        elif name in _SCENES or re.fullmatch(r'tree-\d+\.json', name):
            add('the cutscenes')
        elif name == 'attract.json':
            add('the demo and credits')
        elif name == 'enemy_profiles.json':
            add("the opponents' data")
        elif name.endswith('.rsrc'):
            add("the game's resource files")
        else:
            add(name)
    if levels:
        parts.insert(0, _levels(levels))
    return _join(parts) if parts else ''
