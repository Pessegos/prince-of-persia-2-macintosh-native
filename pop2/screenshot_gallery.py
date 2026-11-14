"""In-game PNG library and folder picker; filesystem reads stay off Tk's thread."""

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import math
import os
from pathlib import Path
from queue import Empty, PriorityQueue, Queue
from threading import Thread
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageOps

from pop2.bitmap_labels import label_text
from pop2 import menu_theme
from pop2.menu_theme import c
from pop2.save_slots import remember
from pop2.screenshots import ScreenshotSettings


@dataclass(frozen=True)
class Capture:
    path: Path
    modified: int
    size: int

    @property
    def date(self):
        try:
            return datetime.fromtimestamp(self.modified / 1e9).strftime('%d %b  %H:%M')
        except (OSError, ValueError, OverflowError):
            return 'Unknown date'


@dataclass
class ReadResult:
    value: object = None
    error: str = ''


def scan_captures(folder):
    if not folder.exists():
        return ()
    entries = []
    with os.scandir(folder) as directory:
        for entry in directory:
            if entry.name.lower().endswith('.png') and entry.is_file():
                try:
                    stat = entry.stat()
                    entries.append(Capture(Path(entry.path), stat.st_mtime_ns, stat.st_size))
                except OSError:
                    continue
    return tuple(sorted(entries, key=lambda entry: (-entry.modified, entry.path.name.casefold())))


def read_capture(entry, bounds=(2040, 1536)):
    if entry.size > 128 * 1024 * 1024:
        raise ValueError('Image is too large')
    with Image.open(entry.path) as image:
        if image.format != 'PNG' or image.width * image.height > 32_000_000:
            raise ValueError('Unsupported image')
        original_size = image.size
        image.thumbnail(bounds, Image.Resampling.NEAREST)
        return image.convert('RGB'), original_size


def scan_folders(folder):
    if not folder.exists():
        return ()
    with os.scandir(folder) as directory:
        return tuple(sorted((Path(entry.path) for entry in directory if entry.is_dir()),
                            key=lambda path: path.name.casefold()))


@lru_cache(maxsize=1)
def lava_delete_frames():
    from pop2.caverns import cavern_assets, split_lava_bubble
    from pop2.lava import LavaPool
    from pop2.render_opening import decode_shap

    program, resources, palette, _shapes = cavern_assets()
    with Image.open(Path(__file__).with_name('screenshot_lava.png')) as image:
        edited = image.convert('RGBA')
    # The edited PNG trims (22, 3) from the native 140 x 33 surface.
    base = Image.new('RGBA', (140, 60))
    base.paste(edited, (22, 30))
    liquid = base.getchannel('A')
    pool = LavaPool(program['lava'], enhanced=True)
    pool.initialize(0)
    for _ in range(44):
        pool.advance()
    frames, shapes = [], {}
    for _ in range(22):
        pool.advance()
        frame = base.copy()
        raised = []
        for shape, x, bottom, _mirrored in pool.drawings():
            if shape == 3614:
                continue
            if shape not in shapes:
                shapes[shape] = split_lava_bubble(decode_shap(resources['SHAP'][shape]['data'], palette), shape)
            surface, airborne = shapes[shape]
            y = bottom - surface.height + 60
            clipped = surface.copy()
            clipped.putalpha(ImageChops.multiply(surface.getchannel('A'),
                liquid.crop((x, y, x + surface.width, y + surface.height))))
            frame.alpha_composite(clipped, (x, y))
            raised.append((airborne, (x, y)))
        for airborne, position in raised:
            frame.alpha_composite(airborne, position)
        frames.append(frame)
    bounds = frames[0].getbbox()
    for frame in frames[1:]:
        left, top, right, bottom = frame.getbbox()
        bounds = min(bounds[0], left), min(bounds[1], top), max(bounds[2], right), max(bounds[3], bottom)
    return tuple(frame.crop(bounds) for frame in frames)


def wrap(value, width, measure):
    """Break ``value`` at spaces into lines no wider than ``width``; a long word keeps its own line."""
    lines = []
    for word in value.split():
        if lines and measure(f'{lines[-1]} {word}') <= width:
            lines[-1] = f'{lines[-1]} {word}'
        else:
            lines.append(word)
    return lines


def open_capture_folder(folder):
    if not folder.is_dir():
        raise NotADirectoryError(str(folder))
    if sys.platform == 'win32':
        os.startfile(str(folder))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(folder)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class GalleryReads:
    def __init__(self):
        self.jobs, self.results = PriorityQueue(), Queue()
        self.pending, self.cache = set(), {}
        self.closed, self.serial, self.thread = False, 0, None
        self.wanted = None

    def request(self, key, function, priority=0):
        if key in self.cache:
            result = self.cache.pop(key)
            self.cache[key] = result
            return result
        if not self.closed and key not in self.pending and (
                key[0] not in ('image', 'thumb') or priority < 0 or len(self.pending) < 12):
            self.pending.add(key)
            self.serial += 1
            self.jobs.put((priority, self.serial, key, function))
            if self.thread is None:
                self.thread = Thread(target=self.work, daemon=True, name='PNG gallery reads')
                self.thread.start()
        return None

    def work(self):
        while not self.closed:
            _priority, _serial, key, function = self.jobs.get()
            if self.closed or function is None:
                return
            if key[0] in ('image', 'thumb') and self.wanted is not None and key not in self.wanted:
                self.results.put((key, None))
                continue
            try:
                result = ReadResult(function())
            except (OSError, ValueError, SyntaxError, OverflowError, MemoryError, Image.DecompressionBombError):
                result = ReadResult(error='Unavailable')
            if not self.closed:
                self.results.put((key, result))

    def poll(self):
        changed = False
        while True:
            try:
                key, result = self.results.get_nowait()
            except Empty:
                return changed
            self.pending.discard(key)
            if result is None:
                changed = True
                continue
            kind = key[0]
            quota = 3 if kind == 'image' else 64 if kind == 'thumb' else 8
            category = [item for item in self.cache if item[0] == kind]
            if len(category) >= quota:
                del self.cache[category[0]]
            remember(self.cache, key, result, 96)
            changed = True

    def close(self):
        self.closed = True
        self.jobs.put((-100, 0, None, None))
        self.pending.clear()
        self.cache.clear()


class ScreenshotGallery:
    PANEL = (20, 12, 492, 328)
    LIST = (36, 84, 188, 296)
    PREVIEW = (202, 84, 474, 272)
    SCALES = tuple((84 + i * 36, 48, 118 + i * 36, 70) for i in range(4))
    INCLUDE_UI = (358, 48, 474, 70)
    FOOTER = ((36, 300, 106, 322), (114, 300, 234, 322), (362, 300, 474, 322))
    OPEN_FOLDER = (242, 300, 354, 322)
    PATH = (64, 88, 448, 116)
    FOLDER_LIST = (64, 156, 448, 280)
    FOLDER_TOOLS = ((64, 124, 156, 148), (164, 124, 252, 148), (260, 124, 348, 148), (356, 124, 448, 148))
    FOLDER_BUTTONS = ((64, 296, 242, 324), (254, 296, 448, 324))
    CONFIRM_BUTTONS = ((100, 220, 246, 256), (258, 220, 412, 256))
    DELETE = (432, 274, 474, 298)
    REFRESH = (386, 24, 474, 44)
    COLUMNS = 2
    ROW_HEIGHT = 64

    @staticmethod
    def wide_layout(width, height, basis=510):
        """(spread, shift) for a picture of this size; (0, 0) keeps the classic page."""
        return menu_theme.wide_layout(width, height, basis)

    def lay_out(self, spread=0, shift=0.0):
        """Place the page's pieces for a page ``spread`` units wider than the classic one.

        The wide page gives the picture more room, with its name and details
        beside it, and moves the right-hand controls to its right edge. The
        dialogs stay centred on it. A wider window centres the page ``shift``
        units in.
        """
        self.spread, self.shift = spread, shift
        cls, right = type(self), 474 + spread
        self.right = right
        self.PANEL = cls.PANEL[:2] + (cls.PANEL[2] + spread, cls.PANEL[3])
        if spread:
            # The picture keeps a capture's own shape and reaches the list's foot.
            width = 281 - max(0, menu_theme.WIDE_SPREAD - spread)
            self.PREVIEW = (202, 84, 202 + width, 84 + round((width - 2) * 384 / 510) + 2)
            self.DELETE = (right - 42, self.PREVIEW[3] - 24, right, self.PREVIEW[3])
        else:
            self.PREVIEW, self.DELETE = cls.PREVIEW, cls.DELETE
        self.INCLUDE_UI = (right - 116, 48, right, 70)
        self.REFRESH = (right - 88, 24, right, 44)
        self.FOOTER = (*cls.FOOTER[:2], (362 + spread, 300, right, 322))
        self.OPEN_FOLDER = (242 + spread, 300, 354 + spread, 322)
        self.dialog_shift = spread // 2

    def pixel_rect(self, rect, size):
        """A rectangle of the page in the pixels of a visible picture of this size, as draw places it."""
        sy = size[1] / 384
        sx = sy if self.spread else size[0] / 510
        return (round((rect[0] - 1 + self.shift) * sx), round(rect[1] * sy),
                round((rect[2] - 1 + self.shift) * sx), round(rect[3] * sy))

    def __init__(self, folder, scale=3, include_ui=False):
        self.lay_out()
        self.folder, self.scale, self.include_ui = Path(folder), scale, include_ui
        self.entries, self.selected, self.focus = (), 0, 12
        self.error = self.status = ''
        self.scroll = self.scroll_target = self.velocity = 0.0
        self.choosing = self.deleting = False
        self.delete_target = None
        self.delete_from_drop, self.delete_art = False, None
        self.drag_target = self.drag_origin = self.drag_point = None
        self.dragging = False
        self.burn_seconds, self.burn_image = None, None
        self.burn_target = None
        self.hovered = None
        self.keyboard_navigation = False
        self.draft, self.caret, self.anchor = '', 0, 0
        self.browsing, self.folders, self.folder_selected, self.folder_offset = self.folder, (), 0, 0
        self.folder_error, self.revision = '', 0
        self.reads = GalleryReads()
        self.text_cache, self.image_cache = {}, {}
        self.modal_cache, self.art_revision = {}, 0
        self.surface_cache = {}
        self.icon_cache = {}
        self.icon_seconds = 0.0
        self.icon_frame = 0
        self.scan_key = self.folder_key = None
        self.applied_scan = self.applied_folder = None
        self.commit_key = self.delete_key = None
        self.open_key = None
        self.committed_folder = None
        self.refresh()

    @staticmethod
    def contains(rect, x, y):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]

    @property
    def entry(self):
        return self.entries[self.selected] if self.entries else None

    @property
    def max_scroll(self):
        rows = math.ceil(len(self.entries) / self.COLUMNS)
        return max(0, rows * self.row_height - (self.LIST[3] - self.LIST[1]))

    @property
    def row_height(self):
        return self.ROW_HEIGHT

    @staticmethod
    def image_key(entry, thumb=False):
        return 'thumb' if thumb else 'image', entry.path, entry.modified, entry.size

    @property
    def visible_indices(self):
        start = max(0, int(self.scroll // self.row_height)) * self.COLUMNS
        end = (math.ceil((self.scroll + self.LIST[3] - self.LIST[1]) / self.row_height) + 1) * self.COLUMNS
        return range(start, min(len(self.entries), end))

    @property
    def surface_state(self):
        main_image = self.reads.cache.get(self.image_key(self.entry)) if self.entry else None
        return (self.folder, id(self.entries), self.selected, self.scale, self.include_ui,
                self.error, self.status, -1 if self.choosing or self.deleting else min(self.focus, 100),
                id(main_image), self.applied_scan == self.scan_key, self.choosing, self.deleting,
                self.hovered == 13, self.focus == 13 and self.keyboard_navigation,
                id(self.reads.cache.get(('icon', 'lava'))))

    def refresh(self, selected_path=None):
        self.cancel_drag()
        self.revision += 1
        self.preferred_path = selected_path or (self.entry.path if self.entry else None)
        self.scan_key = ('scan', self.folder, self.revision)
        folder = self.folder
        self.reads.request(self.scan_key, lambda: scan_captures(folder), -10)

    def poll(self):
        changed = self.reads.poll()
        if changed:
            self.art_revision += 1
        result = self.reads.cache.get(self.commit_key)
        if result is not None:
            self.commit_key = None
            if result.error:
                self.folder_error = 'Could not use this folder. Check the path and permissions.'
            else:
                self.folder = self.committed_folder = result.value
                self.error = self.status = ''
                self.choosing, self.focus = False, 11
                self.scroll = self.scroll_target = self.velocity = 0
                self.entries, self.selected = (), 0
                self.refresh()
        result = self.reads.cache.get(self.delete_key)
        if result is not None:
            target = self.delete_target
            self.delete_key, self.deleting = None, False
            self.delete_target = None
            self.error = 'Could not delete this PNG. It may have changed.' if result.error else ''
            self.status = '' if result.error else 'PNG deleted'
            if not result.error and self.delete_from_drop:
                self.burn_seconds, self.burn_image = 0.0, self.delete_art
                self.burn_target = target
            self.delete_from_drop, self.delete_art = False, None
            self.refresh()
        result = self.reads.cache.get(self.open_key)
        if result is not None:
            self.open_key = None
            self.error = 'Could not open this folder. Capture a PNG first if it does not exist.' if result.error else ''
            self.status = '' if result.error else 'Folder opened'
        result = self.reads.cache.get(self.scan_key)
        if result is not None and self.applied_scan != self.scan_key:
            self.applied_scan = self.scan_key
            self.entries = result.value or ()
            self.selected = next((i for i, item in enumerate(self.entries)
                                  if item.path == self.preferred_path), 0)
            if result.error:
                self.error = 'Could not read this folder.'
            self.scroll = self.scroll_target = self.velocity = 0
            self.ensure_visible(immediate=True)
        result = self.reads.cache.get(self.folder_key)
        if result is not None and self.applied_folder != self.folder_key:
            self.applied_folder = self.folder_key
            self.folders = result.value or ()
            if result.error:
                self.folder_error = 'Could not read this folder.'
        return changed

    def browse(self, folder):
        self.hovered = None
        self.browsing = Path(folder).expanduser().absolute()
        self.draft = str(self.browsing)
        self.caret, self.anchor = len(self.draft), len(self.draft)
        self.folders, self.folder_offset, self.folder_selected = (), 0, 0
        self.folder_error = ''
        self.revision += 1
        self.folder_key = ('folders', self.browsing, self.revision)
        path = self.browsing
        self.reads.request(self.folder_key, lambda: scan_folders(path), -10)

    def choose_folder(self):
        self.cancel_drag()
        self.choosing, self.focus = True, 40
        self.browse(self.folder)

    def commit_folder(self):
        if self.commit_key is not None:
            return
        self.revision += 1
        path, scale = self.path_value(), self.scale
        def commit():
            selected = path.resolve()
            selected.mkdir(parents=True, exist_ok=True)
            ScreenshotSettings(selected, scale).save()
            return selected
        self.commit_key = ('commit', self.revision)
        self.reads.request(self.commit_key, commit, -20)

    def delete_capture(self):
        entry = self.delete_target or self.entry
        if entry is None or self.delete_key is not None:
            return
        def delete():
            stat = entry.path.stat()
            if (stat.st_mtime_ns, stat.st_size) != (entry.modified, entry.size):
                raise ValueError('File changed')
            entry.path.unlink()
        self.revision += 1
        self.delete_key = ('delete', self.revision)
        self.reads.request(self.delete_key, delete, -20)

    def confirm_delete(self, entry=None, *, dropped=False):
        entry = entry or self.entry
        if entry is not None:
            self.delete_target = entry
            self.delete_from_drop = dropped
            result = self.reads.cache.get(self.image_key(entry, True))
            self.delete_art = result.value[0] if result is not None and not result.error else None
            self.deleting, self.focus = True, 60

    def begin_drag(self, x, y):
        self.cancel_drag()
        if self.choosing or self.deleting or self.commit_key is not None or self.delete_key is not None:
            return False
        index = self.hit(x, y)
        if index is None or not 100 <= index < 100 + len(self.entries):
            return False
        self.drag_target = self.entries[index - 100]
        self.drag_origin = self.drag_point = (x, y)
        self.dragging = False
        return True

    def move_drag(self, x, y):
        if self.drag_target is None:
            return False
        if not self.dragging and math.dist(self.drag_origin, (x, y)) < 4:
            return False
        self.dragging = True
        self.drag_point = (x, y)
        self.scroll_target, self.velocity = self.scroll, 0
        self.hovered = 13 if self.contains(self.DELETE, x, y) else None
        return True

    def cancel_drag(self):
        active = self.dragging
        self.drag_target = self.drag_origin = self.drag_point = None
        self.dragging = False
        if active:
            self.hovered = None

    def release_drag(self, x, y):
        target = self.drag_target
        dropped = self.dragging and self.contains(self.DELETE, x, y)
        self.cancel_drag()
        if dropped and target is not None:
            self.confirm_delete(target, dropped=True)
        return 'changed'

    @property
    def overlay_active(self):
        return self.dragging or self.burn_seconds is not None

    def close(self):
        self.cancel_drag()
        self.burn_seconds, self.burn_image = None, None
        self.burn_target = None
        self.reads.close()
        self.text_cache.clear()
        self.image_cache.clear()
        self.modal_cache.clear()
        self.surface_cache.clear()
        self.icon_cache.clear()

    @property
    def animation_running(self):
        icon = self.reads.cache.get(('icon', 'lava'))
        return bool(not (self.choosing or self.deleting)
                    and icon is not None and not icon.error and len(icon.value) > 1)

    @property
    def scrolling(self):
        return abs(self.scroll_target - self.scroll) >= 0.025 or abs(self.velocity) >= 0.1

    def ensure_visible(self, immediate=False):
        row = self.selected // self.COLUMNS
        top, bottom = row * self.row_height, (row + 1) * self.row_height
        height = self.LIST[3] - self.LIST[1]
        self.scroll_target = max(0, min(self.max_scroll,
            top if top < self.scroll_target else bottom - height if bottom > self.scroll_target + height
            else self.scroll_target))
        if immediate:
            self.scroll, self.velocity = self.scroll_target, 0

    def animate(self, seconds):
        if self.choosing or self.deleting:
            return False
        icon_changed = self.burn_seconds is not None
        if self.burn_seconds is not None:
            self.burn_seconds += max(0, seconds)
            if self.burn_seconds >= 0.65:
                self.burn_seconds, self.burn_image = None, None
                self.burn_target = None
        if self.animation_running:
            self.icon_seconds += max(0, seconds)
            frame = math.floor(self.icon_seconds * 12 + 1e-9) % len(self.reads.cache['icon', 'lava'].value)
            icon_changed = icon_changed or frame != self.icon_frame
            self.icon_frame = frame
        distance = self.scroll_target - self.scroll
        if abs(distance) < 0.025 and abs(self.velocity) < 0.1:
            self.scroll, self.velocity = self.scroll_target, 0
            return icon_changed
        seconds = max(0, seconds)
        decay = math.exp(-24 * seconds)
        change = (self.velocity - 24 * distance) * seconds
        self.scroll = max(0, min(self.max_scroll, self.scroll_target + (-distance + change) * decay))
        self.velocity = (self.velocity - 24 * change) * decay
        return True

    def wheel(self, steps):
        if self.deleting:
            return False
        if self.choosing:
            self.folder_offset = max(0, min(max(0, len(self.folders) - 6), self.folder_offset + round(steps * 3)))
            return True
        self.scroll_target = max(0, min(self.max_scroll, self.scroll_target + steps * self.row_height))
        return True

    def row_rect(self, index):
        top = self.LIST[1] + (index // self.COLUMNS) * self.row_height - self.scroll
        left = self.LIST[0] + (index % self.COLUMNS) * 76
        return left, top, left + 70, top + self.row_height - 3

    def hit(self, x, y):
        if self.deleting or self.choosing:
            x -= self.dialog_shift   # the dialogs are laid out on the classic page, then centred
        if self.deleting:
            return next((60 + i for i, rect in enumerate(self.CONFIRM_BUTTONS) if self.contains(rect, x, y)), None)
        if self.choosing:
            controls = {40: self.PATH, **dict(enumerate(self.FOLDER_TOOLS, 41)),
                        45: self.FOLDER_BUTTONS[0], 46: self.FOLDER_BUTTONS[1]}
            if self.contains(self.FOLDER_LIST, x, y):
                if x >= 440 and len(self.folders) > 6:
                    return 47
                index = self.folder_offset + int((y - self.FOLDER_LIST[1]) // 20)
                return 1000 + index if index < len(self.folders) else None
        else:
            controls = {**dict(enumerate(self.SCALES)), 4: self.INCLUDE_UI,
                        **dict(enumerate(self.FOOTER, 10)), 13: self.DELETE, 15: self.REFRESH,
                        18: self.OPEN_FOLDER}
            if self.contains(self.LIST, x, y):
                if x >= 185 and self.max_scroll:
                    return 14
                row = int((y - self.LIST[1] + self.scroll) // self.row_height)
                column = int((x - self.LIST[0]) // 76)
                index = row * self.COLUMNS + column
                return 100 + index if index < len(self.entries) and column < self.COLUMNS and self.contains(
                    self.row_rect(index), x, y) else None
        return next((i for i, rect in controls.items() if self.contains(rect, x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        changed = index != self.hovered or self.keyboard_navigation and self.focus == 13
        self.keyboard_navigation = False
        self.hovered = index
        if self.choosing:
            return changed
        if index is None or index == self.focus:
            return changed
        self.focus = index
        return True

    def activate(self):
        if self.commit_key is not None or self.delete_key is not None:
            return 'changed'
        if self.deleting:
            if self.focus == 61:
                return 'gallery_delete'
            self.deleting, self.focus = False, 13
            self.delete_target = None
            self.delete_from_drop, self.delete_art = False, None
        elif self.choosing:
            if self.focus == 40:
                self.browse(self.path_value())
            elif self.focus >= 1000 and self.focus - 1000 < len(self.folders):
                self.browse(self.folders[self.focus - 1000])
            elif self.focus in (41, 42, 43):
                self.browse(ScreenshotSettings().folder if self.focus == 41 else
                            Path.home() if self.focus == 42 else self.browsing.parent)
            elif self.focus == 44:
                if os.name == 'nt':
                    self.revision += 1
                    self.folder_key = ('drives', self.revision)
                    self.reads.request(self.folder_key, lambda: tuple(Path(f'{letter}:/')
                        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.isdir(f'{letter}:/')), -10)
                    self.folders = ()
                    self.folder_offset, self.folder_selected = 0, 0
                else:
                    self.browse(Path('/'))
            elif self.focus == 45:
                self.choosing, self.focus = False, 11
            elif self.focus == 46:
                return 'gallery_folder'
        elif self.focus in range(4):
            self.scale = self.focus + 1
            return 'gallery_scale'
        elif self.focus == 4:
            self.include_ui = not self.include_ui
        elif self.focus == 10:
            return 'gallery_back'
        elif self.focus == 11:
            self.choose_folder()
        elif self.focus == 12:
            return 'gallery_capture'
        elif self.focus == 13 and self.entry is not None:
            self.confirm_delete()
        elif self.focus == 15:
            self.error = self.status = ''
            self.refresh()
        elif self.focus == 18:
            if self.open_key is None:
                self.revision += 1
                self.open_key = ('open', self.revision)
                folder = self.folder
                self.reads.request(self.open_key, lambda: open_capture_folder(folder), -20)
        elif 100 <= self.focus < 100 + len(self.entries):
            self.selected = self.focus - 100
            self.ensure_visible()
        return 'changed'

    def path_value(self):
        value = Path(self.draft.strip()).expanduser()
        return value if value.is_absolute() else self.browsing / value

    def click(self, x, y):
        self.keyboard_navigation = False
        if self.commit_key is not None or self.delete_key is not None:
            return 'changed'
        index = self.hit(x, y)
        if index is None:
            return 'changed'
        self.focus = index
        if index == 47:
            self.folder_offset = max(0, min(len(self.folders) - 6,
                round((len(self.folders) - 6) * (y - 156) / 124)))
        elif index == 14:
            self.scroll_target = self.max_scroll * (y - self.LIST[1]) / (self.LIST[3] - self.LIST[1])
        else:
            return self.activate() if index != 40 else 'changed'
        return 'changed'

    def edit_text(self, key, char='', control=False, backwards=False):
        start, end = sorted((self.caret, self.anchor))
        if control and key.lower() == 'a':
            self.anchor, self.caret = 0, len(self.draft)
        elif key in ('Left', 'Right', 'Home', 'End'):
            self.caret = (0 if key == 'Home' else len(self.draft) if key == 'End' else
                          max(0, self.caret - 1) if key == 'Left' else min(len(self.draft), self.caret + 1))
            if not backwards:
                self.anchor = self.caret
        elif key in ('BackSpace', 'Delete') or char:
            if start == end and not char:
                start, end = (max(0, start - 1), end) if key == 'BackSpace' else (start, min(len(self.draft), end + 1))
            char = ''.join(c for c in char if c.isprintable())[:2048 - len(self.draft) + end - start]
            self.draft = self.draft[:start] + char + self.draft[end:]
            self.caret = self.anchor = start + len(char)

    def key(self, key, backwards=False, char='', control=False):
        if self.drag_target is not None:
            self.cancel_drag()
            if key == 'Escape':
                return 'changed'
        self.keyboard_navigation = True
        if self.commit_key is not None or self.delete_key is not None:
            return 'changed'
        if key == 'Escape':
            if self.deleting:
                self.deleting, self.focus = False, 13
                self.delete_target = None
                self.delete_from_drop, self.delete_art = False, None
            elif self.choosing:
                self.choosing, self.focus = False, 11
            else:
                return 'gallery_back'
        elif self.choosing and self.focus == 40 and key not in ('Tab', 'Return', 'KP_Enter'):
            self.edit_text(key, char, control, backwards)
        elif key in ('Return', 'KP_Enter', 'space'):
            return self.activate()
        elif self.deleting:
            if key in ('Left', 'Right', 'Tab'):
                self.focus = 61 if self.focus == 60 else 60
        elif key == 'Tab':
            controls = ((40, 41, 42, 43, 44, 1000 + self.folder_selected, 45, 46) if self.choosing else
                        (15, 0, 1, 2, 3, 4, 100 + self.selected, 13, 10, 11, 18, 12))
            index = controls.index(self.focus) if self.focus in controls else -1
            self.focus = controls[(index + (-1 if backwards else 1)) % len(controls)]
        elif self.choosing and key in ('Up', 'Down') and self.folders:
            self.folder_selected = max(0, min(len(self.folders) - 1,
                                            self.folder_selected + (-1 if key == 'Up' else 1)))
            self.folder_offset = max(0, min(self.folder_selected, max(self.folder_offset, self.folder_selected - 5)))
            self.focus = 1000 + self.folder_selected
        elif not self.choosing and key in ('Up', 'Down', 'Prior', 'Next', 'Left', 'Right') and self.entries:
            step = (-self.COLUMNS if key == 'Up' else self.COLUMNS if key == 'Down' else
                    -1 if key == 'Left' else -3 * self.COLUMNS if key == 'Prior' else
                    3 * self.COLUMNS if key == 'Next' else 1)
            self.selected = max(0, min(len(self.entries) - 1, self.selected + step))
            self.focus = 100 + self.selected
            self.ensure_visible()
        elif not self.choosing and key == 'Delete' and self.entry:
            self.confirm_delete()
        return 'changed'

    def draw(self, viewport, font, *, visible=False, background_key=None):
        modal = self.choosing or self.deleting
        layout = self.wide_layout(*viewport.size, 510 if visible else 512)
        if layout != (self.spread, self.shift):
            self.lay_out(*layout)
        right = self.right
        # How far the wide page's frame may reach, in the page's own units.
        wide = (math.ceil(int(visible) - self.shift), 0,
                math.floor(int(visible) + 509 + self.spread + self.shift), 383) if self.spread else None
        wanted = {self.image_key(self.entries[i], True) for i in self.visible_indices}
        if self.drag_target is not None:
            wanted.add(self.image_key(self.drag_target, True))
        if self.entry:
            wanted.add(self.image_key(self.entry))
        self.reads.wanted = frozenset(wanted)
        surface_key = (viewport.size, visible, id(font), background_key or id(viewport), self.surface_state,
                       menu_theme.current().name)
        surface = self.surface_cache.get(surface_key) if not modal else None
        key = (viewport.size, visible, id(font), background_key or id(viewport), id(self.entries),
               self.selected, self.scroll, self.scale, self.include_ui, self.error, self.status,
               self.art_revision, self.choosing, self.deleting, self.icon_frame,
               menu_theme.current().name)
        cached = self.modal_cache.get(key) if modal else None
        if not modal:
            self.modal_cache.clear()
        image = cached.copy() if cached is not None else surface.copy() if surface is not None else Image.alpha_composite(
            viewport, Image.new('RGBA', viewport.size, (0, 0, 0, 150)))
        draw = ImageDraw.Draw(image)
        sx, sy = viewport.width / (510 if visible else 512), viewport.height / 384
        if self.spread:
            sx = sy   # the wide page is not stretched: it has more units across
        origin = (0, 0)
        dialog = 0    # the dialogs' own offset: they are centred on the wide page
        gold, white, muted, cyan = c('#f4d873'), c('#eeeeee'), c('#999999'), c('#77c9dc')

        def point(x, y):
            return (round((x - int(visible) + self.shift + dialog) * sx) - origin[0],
                    round(y * sy) - origin[1])

        def box(rect, fill=c('#222222'), outline=c('#626262')):
            draw.rectangle((*point(*rect[:2]), *point(*rect[2:])), fill=fill, outline=outline,
                           width=max(1, round(min(sx, sy))))

        def glyph(value, color=white):
            key = id(font), str(value), color
            if key not in self.text_cache:
                remember(self.text_cache, key, label_text(font, value, color))
            return self.text_cache[key]

        def text(value, x, y, width=200, color=white, scale=0.7, right=False, tail=False):
            if not value:
                return
            value = str(value)
            if glyph(value, color).width * scale > width:
                suffix = '...'
                low, high = 0, len(value)
                while low < high:
                    count = (low + high + 1) // 2
                    candidate = value[-count:] if tail else value[:count]
                    if glyph((suffix + candidate) if tail else (candidate + suffix), color).width * scale <= width:
                        low = count
                    else:
                        high = count - 1
                value = value[-low:] if tail and low else value[:low]
                value = suffix + value if tail else value + suffix
            raw = glyph(value, color)
            ink = raw.getbbox()
            if ink:
                raw = raw.crop((0, ink[1], raw.width, ink[3]))
            key = ('fit', id(font), value, color, scale, sx, sy)
            if key not in self.text_cache:
                remember(self.text_cache, key, raw.resize((max(1, round(raw.width * scale * sx)),
                    max(1, round(raw.height * scale * sy))), Image.Resampling.NEAREST))
            raw = self.text_cache[key]
            x, y = point(x, y)
            image.paste(raw, (x - raw.width if right else x, y), raw)

        def button(rect, label, index, enabled=True, active=False, scale=0.7, centered=False):
            highlighted = self.focus == index or self.choosing and self.hovered == index
            box(rect, c('#303030') if highlighted else c('#222222'),
                gold if highlighted else cyan if active else c('#626262'))
            x, y = rect[0] + 8, rect[1] + 7
            if centered:
                raw = glyph(label)
                ink = raw.getbbox()
                x = (rect[0] + rect[2] - raw.width * scale) / 2
                y = (rect[1] + rect[3] - ((ink[3] - ink[1]) if ink else raw.height) * scale) / 2
            text(label, x, y, rect[2] - rect[0] - 16, white if enabled else muted, scale)

        shown = []   # where pictures are, in pixels: the theme's sign keeps out of them

        def keep_clear(left, top, right, bottom):
            shown.append((left + origin[0], top + origin[1], right + origin[0], bottom + origin[1]))

        def picture(entry, rect, thumb=False, outline=c('#626262')):
            key = self.image_key(entry, thumb)
            result = self.reads.request(key, lambda: read_capture(entry,
                (510, 384) if thumb else (2040, 1536)), 0 if thumb else -5)
            if result is None:
                keep_clear(*point(*rect[:2]), *point(*rect[2:]))   # a slot still waiting for its picture
                box(rect, c('#222222'), outline)
                text('...', (rect[0] + rect[2]) / 2 - 6, (rect[1] + rect[3]) / 2, 30, muted)
                return None
            if result.error:
                box(rect, c('#222222'), outline)
                text('Unavailable', rect[0] + 8, (rect[1] + rect[3]) / 2, rect[2] - rect[0] - 16, muted)
                return None
            left, top = point(rect[0] + 1, rect[1] + 1)
            right, bottom = point(rect[2] - 1, rect[3] - 1)
            size = max(1, right - left), max(1, bottom - top)
            fit_key = key, size
            if fit_key not in self.image_cache:
                remember(self.image_cache, fit_key, ImageOps.contain(result.value[0], size,
                    method=Image.Resampling.NEAREST).convert('RGBA'), 48)
            fitted = self.image_cache[fit_key]
            pos = left + (size[0] - fitted.width) // 2, top + (size[1] - fitted.height) // 2
            image.paste(fitted, pos)
            keep_clear(*pos, pos[0] + fitted.width - 1, pos[1] + fitted.height - 1)
            border = max(1, round(min(sx, sy)))
            draw.rectangle((pos[0] - border, pos[1] - border,
                            pos[0] + fitted.width + border - 1, pos[1] + fitted.height + border - 1),
                           outline=outline, width=border)
            return result.value[1]

        def draw_list():
            nonlocal image, draw, origin
            box(self.LIST, c('#181818'), None)
            base, base_draw = image, draw
            clip = (*point(*self.LIST[:2]), *point(*self.LIST[2:]))
            origin = clip[:2]
            image = Image.new('RGBA', (clip[2] - clip[0], clip[3] - clip[1]), c('#181818'))
            draw = ImageDraw.Draw(image)
            first = len(shown)
            for index in self.visible_indices:
                entry = self.entries[index]
                rect = self.row_rect(index)
                height = 50
                outline = gold if self.focus == 100 + index and not modal else cyan if self.selected == index else c('#626262')
                picture(entry, (rect[0], rect[1], rect[2], rect[1] + height), True, outline)
                text(entry.date.replace('  ', ' '), rect[0] + 2, rect[1] + height + 5,
                     rect[2] - rect[0] - 4, cyan if self.selected == index else muted,
                     0.4)
            # Thumbnails scrolled partly out of the list are cut off at its edge.
            shown[first:] = [(max(left, clip[0]), max(top, clip[1]), min(right, clip[2] - 1), min(bottom, clip[3] - 1))
                             for left, top, right, bottom in shown[first:]]
            base.paste(image, clip[:2])
            image, draw, origin = base, base_draw, (0, 0)
            if self.max_scroll:
                height = self.LIST[3] - self.LIST[1]
                thumb = max(16, height * height / (math.ceil(len(self.entries) / self.COLUMNS) * self.row_height))
                top = self.LIST[1] + (height - thumb) * self.scroll / self.max_scroll
                box((185, self.LIST[1], 187, self.LIST[3]), c('#303030'), None)
                box((185, top, 187, top + thumb), c('#858585'), None)

        def draw_delete(clear=True):
            highlighted = self.hovered == 13 or self.focus == 13 and self.keyboard_navigation
            if clear:
                box(self.DELETE, c('#422622') if self.deleting or self.dragging and self.hovered == 13 else
                    c('#2b1d1b') if highlighted else c('#181818'), None)
            icon = self.reads.request(('icon', 'lava'), lava_delete_frames, -5)
            if icon is not None and not icon.error:
                icon_key = sx, sy
                if icon_key not in self.icon_cache:
                    size = max(1, round(36 * sx)), max(1, round(16 * sy))
                    remember(self.icon_cache, icon_key, tuple(ImageOps.contain(frame, size,
                        Image.Resampling.NEAREST) for frame in icon.value), 3)
                frames = self.icon_cache[icon_key]
                sprite = frames[self.icon_frame % len(frames)]
                x, y = point(self.DELETE[0] + 21, self.DELETE[1] + 12)
                image.paste(sprite, (x - sprite.width // 2, y - sprite.height // 2), sprite)
            else:
                text('Del', self.DELETE[0] + 8, self.DELETE[1] + 8, 30, white, 0.6)

        def draw_held_image():
            if modal or not self.overlay_active:
                return
            if self.dragging:
                entry = self.drag_target
                result = self.reads.request(self.image_key(entry, True), lambda: read_capture(entry, (510, 384)))
                raw = result.value[0] if result is not None and not result.error else None
                width, height = 56, 42
                x, y = self.drag_point
                x, y = max(30, min(self.PANEL[2] - 12, x)), max(24, min(358, y - 12))
                progress = 0
            else:
                raw = self.burn_image
                progress = min(1, self.burn_seconds / 0.65)
                fall = min(1, progress / 0.65)
                dissolve = max(0, (progress - 0.65) / 0.35)
                scale = (1 - 0.45 * fall) * (1 - dissolve)
                width, height = max(1, round(56 * scale)), max(1, round(42 * scale))
                x = self.DELETE[0] + 21 + math.sin(progress * math.pi * 2) * 2
                y = self.DELETE[1] - 24 + 36 * fall * fall + 3 * dissolve
            size = max(1, round(width * sx)), max(1, round(height * sy))
            fit_key = 'held', self.drag_target if self.dragging else self.burn_target, size
            if fit_key not in self.image_cache:
                sprite = (ImageOps.contain(raw, size, Image.Resampling.NEAREST).convert('RGBA') if raw is not None
                          else Image.new('RGBA', size, c('#999999')))
                remember(self.image_cache, fit_key, sprite, 48)
            sprite = self.image_cache[fit_key]
            left, top = point(x, y)
            left, top = left - sprite.width // 2, top - sprite.height // 2
            if progress > 0.65:
                sprite = sprite.copy()
                sprite.putalpha(round(255 * (1 - progress) / 0.35))
            if not self.dragging:
                surface = point(0, self.DELETE[1] + 13)[1]   # the lava's surface
                sprite = sprite.crop((0, 0, sprite.width, max(0, min(sprite.height, surface - top))))
            if sprite.height:
                image.paste(sprite, (left, top), sprite)
                if self.dragging:
                    draw.rectangle((left - 1, top - 1, left + sprite.width, top + sprite.height), outline=gold,
                                   width=max(1, round(sx)))
            if not self.dragging:
                # Only confirmed sinking goes behind the liquid; held thumbnails stay in front.
                draw_delete(clear=False)

        if surface is not None:
            draw_list()
            menu_theme.watermark(image, self.PANEL, point, shown)   # the list was repainted over it
            draw_delete()
            draw_held_image()
            return image

        if cached is None:
            if not menu_theme.panel_scaled(image, self.PANEL, point, wide):
                box(self.PANEL, c('#181818'), c('#858585'))
            text('Screenshots', 36, 26, 250, gold, 1)
            text(f'{len(self.entries)} PNG', self.REFRESH[0] - 12, 29, 70, muted, right=True)
            button(self.REFRESH, 'Refresh', 15)
            text('Size', 36, 54, 44, muted)
            for i, rect in enumerate(self.SCALES):
                button(rect, f'{i + 1}x', i, active=self.scale == i + 1)
            text(f'{510 * self.scale} x {384 * self.scale}', 238, 54, 114, muted, 0.6)
            check = self.INCLUDE_UI[0] + 8
            box(self.INCLUDE_UI, c('#222222'), gold if self.focus == 4 else c('#626262'))
            box((check, 54, check + 8, 62), cyan if self.include_ui else c('#181818'))
            if self.include_ui:
                draw.line([point(check + 1, 58), point(check + 3, 60), point(check + 7, 55)],
                          fill=c('#181818'), width=max(1, round(sx)))
            text('With menus', check + 14, 54, 88)
            text(str(self.folder).replace('\\', '/'), 36, 75, right - 36, muted, 0.45, tail=True)
            draw_list()
            message = self.error or self.status
            message_color = c('#ff9b9b') if self.error else gold
            if self.entry:
                dimensions = picture(self.entry, self.PREVIEW)
                name = self.entry.path.name.replace('_', ' ')
                kilobytes = f'{self.entry.size / 1024:.0f} KB'
                if self.spread:
                    # Beside the picture: one detail on each line, then any message.
                    column = self.PREVIEW[2] + 10
                    text(name, column, 87, right - column, gold, 0.55)
                    if dimensions:
                        text(f'{dimensions[0]} x {dimensions[1]}', column, 102, right - column, muted, 0.55)
                    text(kilobytes, column, 115, right - column, muted, 0.55)
                else:
                    text(name, 202, 277, 222, gold, 0.55)
                    if dimensions:
                        text(f'{dimensions[0]} x {dimensions[1]}', 202, 290, 145, muted, 0.55)
                    text(kilobytes, 424, 290, 70, muted, 0.55, right=True)
            else:
                box(self.PREVIEW, c('#0c0c0c'))
                text('Reading folder...' if self.applied_scan != self.scan_key else 'No screenshots yet',
                     (self.PREVIEW[0] + self.PREVIEW[2]) / 2 - 118, (self.PREVIEW[1] + self.PREVIEW[3]) / 2 - 4,
                     240, muted)
            draw_delete()
            for i, (rect, label) in enumerate(zip(self.FOOTER, ('Close', 'Change folder', 'Capture PNG'))):
                button(rect, label, 10 + i, active=i == 2, scale=0.6)
            button(self.OPEN_FOLDER, 'Open folder', 18, scale=0.6)
            if message and self.spread:
                column = self.PREVIEW[2] + 10
                for row, value in enumerate(wrap(message, right - column, lambda value: glyph(value).width * 0.5)):
                    text(value, column, 134 + row * 10, right - column, message_color, 0.5)
            elif message:
                box((202, 286, 426, 298), c('#181818'), None)
                text(message, 202, 289, 222, message_color, 0.5)
            if not modal and self.hovered == 13:
                edge = self.DELETE[2]
                box((edge - 124, self.DELETE[1] - 18, edge, self.DELETE[1] - 3), c('#303030'), c('#858585'))
                text('Delete screenshot', edge - 118, self.DELETE[1] - 14, 112, white, 0.6)
            menu_theme.watermark(image, self.PANEL, point, shown)
            if modal:
                image = Image.alpha_composite(image, Image.new('RGBA', image.size, (0, 0, 0, 150)))
                draw = ImageDraw.Draw(image)
                remember(self.modal_cache, key, image.copy(), 3)
            else:
                remember(self.surface_cache, surface_key, image.copy(), 2)
        dialog = self.dialog_shift if modal else 0
        if wide is not None:
            wide = (wide[0] - dialog, 0, wide[2] - dialog, 383)
        if self.choosing:
            if not menu_theme.panel_scaled(image, (48, 44, 464, 338), point, wide):
                box((48, 44, 464, 338), c('#181818'), c('#858585'))
            text('Screenshot folder', 64, 62, 384, gold, 1)
            box(self.PATH, c('#0c0c0c'), cyan if self.focus == 40 else c('#626262'))
            display_path = self.draft.replace('\\', '/')
            raw = glyph(display_path)
            offset = max(0, glyph(display_path[:self.caret]).width * 0.7 - 364)
            start, end = sorted((self.caret, self.anchor))
            if start != end:
                a = max(70, 70 + glyph(display_path[:start]).width * 0.7 - offset)
                b = min(442, 70 + glyph(display_path[:end]).width * 0.7 - offset)
                if b > a:
                    box((a, 95, b, 109), c('#385462'), None)
            raw = raw.resize((max(1, round(raw.width * 0.7 * sx)), max(1, round(raw.height * 0.7 * sy))),
                             Image.Resampling.NEAREST)
            raw = raw.crop((round(offset * sx), 0, min(raw.width, round((offset + 372) * sx)), raw.height))
            image.paste(raw, point(70, 95), raw)
            if self.focus == 40:
                x = 70 + glyph(display_path[:self.caret]).width * 0.7 - offset
                draw.line([point(x, 94), point(x, 109)], fill=cyan, width=max(1, round(sx)))
            for i, (rect, label) in enumerate(zip(self.FOLDER_TOOLS, ('Default', 'Home', 'Up', 'Drives'))):
                button(rect, label, 41 + i)
            box(self.FOLDER_LIST, c('#0c0c0c'))
            for i in range(self.folder_offset, min(len(self.folders), self.folder_offset + 6)):
                y = 156 + (i - self.folder_offset) * 20
                if self.focus == 1000 + i or self.hovered == 1000 + i:
                    box((65, y + 1, 447, y + 19), c('#253033'), None)
                box((72, y + 7, 80, y + 14), c('#999999'), None)
                box((72, y + 5, 76, y + 7), c('#999999'), None)
                text(self.folders[i].name or str(self.folders[i]).replace('\\', '/'), 86, y + 6, 354)
            if not self.folders:
                text('Unavailable' if self.folder_error else ('Reading folders...' if self.applied_folder != self.folder_key
                     else 'No subfolders'), 78, 202, 356, muted)
            if len(self.folders) > 6:
                height = max(6, 122 * 6 / len(self.folders))
                top = 157 + (122 - height) * self.folder_offset / (len(self.folders) - 6)
                box((444, 157, 447, 279), c('#303030'), None)
                box((444, top, 447, top + height), c('#858585'), None)
            text(self.folder_error, 64, 283, 384, c('#ff9b9b'), 0.6)
            for i, (rect, label) in enumerate(zip(self.FOLDER_BUTTONS,
                    ('Cancel', 'Working...' if self.commit_key is not None else 'Use folder'))):
                button(rect, label, 45 + i, active=i == 1)
        elif self.deleting:
            if not menu_theme.panel_scaled(image, (80, 121, 432, 270), point, wide):
                box((80, 121, 432, 270), c('#181818'), c('#858585'))
            text('Delete this screenshot?', 100, 142, 312, gold, 1)
            target = self.delete_target or self.entry
            text(target.path.name.replace('_', ' ') if target is not None else 'Unavailable', 100, 174, 312)
            text('This cannot be undone.', 100, 197, 312, muted)
            for i, (rect, label) in enumerate(zip(self.CONFIRM_BUTTONS, ('Cancel', 'Delete'))):
                button(rect, label, 60 + i, scale=1, centered=True)
        draw_held_image()
        return image
