"""In-game PNG library and folder picker; filesystem reads stay off Tk's thread."""

from dataclasses import dataclass
from datetime import datetime
import math
import os
from pathlib import Path
from queue import Empty, PriorityQueue, Queue
from threading import Thread

from PIL import Image, ImageDraw, ImageOps

from pop2.bitmap_labels import label_text
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
    PANEL = (20, 12, 492, 372)
    LIST = (36, 88, 160, 336)
    PREVIEW = (174, 88, 474, 303)
    SCALES = tuple((84 + i * 36, 52, 118 + i * 36, 74) for i in range(4))
    INCLUDE_UI = (358, 52, 474, 74)
    FOOTER = ((36, 344, 110, 368), (118, 344, 226, 368), (234, 344, 474, 368))
    PATH = (64, 88, 448, 116)
    FOLDER_LIST = (64, 156, 448, 280)
    FOLDER_TOOLS = ((64, 124, 156, 148), (164, 124, 252, 148), (260, 124, 348, 148), (356, 124, 448, 148))
    FOLDER_BUTTONS = ((64, 296, 242, 324), (254, 296, 448, 324))
    CONFIRM_BUTTONS = ((100, 220, 246, 256), (258, 220, 412, 256))
    DELETE = (450, 310, 474, 334)
    REFRESH = (386, 24, 474, 44)
    VIEWS = ((240, 24, 264, 44), (270, 24, 294, 44))
    ROW_HEIGHT = 98

    def __init__(self, folder, scale=3, include_ui=False, columns=2):
        self.folder, self.scale, self.include_ui = Path(folder), scale, include_ui
        self.entries, self.selected, self.focus = (), 0, 12
        self.columns = columns if columns in (1, 2) else 2
        self.error = self.status = ''
        self.scroll = self.scroll_target = self.velocity = 0.0
        self.choosing = self.deleting = False
        self.delete_target = None
        self.hovered = None
        self.draft, self.caret, self.anchor = '', 0, 0
        self.browsing, self.folders, self.folder_selected, self.folder_offset = self.folder, (), 0, 0
        self.folder_error, self.revision = '', 0
        self.reads = GalleryReads()
        self.text_cache, self.image_cache = {}, {}
        self.modal_cache, self.art_revision = {}, 0
        self.surface_cache = {}
        self.scan_key = self.folder_key = None
        self.applied_scan = self.applied_folder = None
        self.commit_key = self.delete_key = None
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
        rows = math.ceil(len(self.entries) / self.columns)
        return max(0, rows * self.row_height - (self.LIST[3] - self.LIST[1]))

    @property
    def row_height(self):
        return 64 if self.columns == 2 else self.ROW_HEIGHT

    @staticmethod
    def image_key(entry, thumb=False):
        return 'thumb' if thumb else 'image', entry.path, entry.modified, entry.size

    @property
    def visible_indices(self):
        start = max(0, int(self.scroll // self.row_height)) * self.columns
        end = (math.ceil((self.scroll + self.LIST[3] - self.LIST[1]) / self.row_height) + 1) * self.columns
        return range(start, min(len(self.entries), end))

    @property
    def surface_state(self):
        main_image = self.reads.cache.get(self.image_key(self.entry)) if self.entry else None
        return (self.folder, id(self.entries), self.selected, self.columns, self.scale, self.include_ui,
                self.error, self.status, -1 if self.choosing or self.deleting else min(self.focus, 100),
                id(main_image), self.applied_scan == self.scan_key, self.choosing, self.deleting,
                self.hovered if self.hovered in (13, 16, 17) else None)

    def refresh(self, selected_path=None):
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
            self.delete_key, self.deleting = None, False
            self.delete_target = None
            self.error = 'Could not delete this PNG. It may have changed.' if result.error else ''
            self.status = '' if result.error else 'PNG deleted'
            self.refresh()
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

    def confirm_delete(self):
        if self.entry is not None:
            self.delete_target = self.entry
            self.deleting, self.focus = True, 60

    def close(self):
        self.reads.close()
        self.text_cache.clear()
        self.image_cache.clear()
        self.modal_cache.clear()
        self.surface_cache.clear()

    def ensure_visible(self, immediate=False):
        row = self.selected // self.columns
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
        distance = self.scroll_target - self.scroll
        if abs(distance) < 0.025 and abs(self.velocity) < 0.1:
            self.scroll, self.velocity = self.scroll_target, 0
            return False
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
        top = 88 + (index // self.columns) * self.row_height - self.scroll
        left = 36 + (index % self.columns) * 62
        return left, top, left + (58 if self.columns == 2 else 120), top + self.row_height - 3

    def hit(self, x, y):
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
                        **dict(enumerate(self.VIEWS, 16))}
            if self.contains(self.LIST, x, y):
                if x >= 157 and self.max_scroll:
                    return 14
                row = int((y - self.LIST[1] + self.scroll) // self.row_height)
                column = int((x - self.LIST[0]) // 62) if self.columns == 2 else 0
                index = row * self.columns + column
                return 100 + index if index < len(self.entries) and column < self.columns and self.contains(
                    self.row_rect(index), x, y) else None
        return next((i for i, rect in controls.items() if self.contains(rect, x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        changed = index != self.hovered
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
        elif self.focus in (16, 17):
            self.columns = self.focus - 15
            self.scroll = self.scroll_target = self.velocity = 0
            self.ensure_visible(immediate=True)
        elif 100 <= self.focus < 100 + len(self.entries):
            self.selected = self.focus - 100
            self.ensure_visible()
        return 'changed'

    def path_value(self):
        value = Path(self.draft.strip()).expanduser()
        return value if value.is_absolute() else self.browsing / value

    def click(self, x, y):
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
        if self.commit_key is not None or self.delete_key is not None:
            return 'changed'
        if key == 'Escape':
            if self.deleting:
                self.deleting, self.focus = False, 13
                self.delete_target = None
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
                        (16, 17, 15, 0, 1, 2, 3, 4, 100 + self.selected, 13, 10, 11, 12))
            index = controls.index(self.focus) if self.focus in controls else -1
            self.focus = controls[(index + (-1 if backwards else 1)) % len(controls)]
        elif self.choosing and key in ('Up', 'Down') and self.folders:
            self.folder_selected = max(0, min(len(self.folders) - 1,
                                            self.folder_selected + (-1 if key == 'Up' else 1)))
            self.folder_offset = max(0, min(self.folder_selected, max(self.folder_offset, self.folder_selected - 5)))
            self.focus = 1000 + self.folder_selected
        elif not self.choosing and key in ('Up', 'Down', 'Prior', 'Next', 'Left', 'Right') and self.entries:
            step = (-self.columns if key == 'Up' else self.columns if key == 'Down' else
                    -1 if key == 'Left' else -3 * self.columns if key == 'Prior' else
                    3 * self.columns if key == 'Next' else 1)
            self.selected = max(0, min(len(self.entries) - 1, self.selected + step))
            self.focus = 100 + self.selected
            self.ensure_visible()
        elif not self.choosing and key == 'Delete' and self.entry:
            self.confirm_delete()
        return 'changed'

    def draw(self, viewport, font, *, visible=False, background_key=None):
        modal = self.choosing or self.deleting
        wanted = {self.image_key(self.entries[i], True) for i in self.visible_indices}
        if self.entry:
            wanted.add(self.image_key(self.entry))
        self.reads.wanted = frozenset(wanted)
        surface_key = (viewport.size, visible, id(font), background_key or id(viewport), self.surface_state)
        surface = self.surface_cache.get(surface_key) if not modal else None
        key = (viewport.size, visible, id(font), background_key or id(viewport), id(self.entries),
               self.selected, self.scroll, self.scale, self.include_ui, self.error, self.status,
               self.art_revision, self.choosing, self.deleting, self.columns)
        cached = self.modal_cache.get(key) if modal else None
        if not modal:
            self.modal_cache.clear()
        image = cached.copy() if cached is not None else surface.copy() if surface is not None else Image.alpha_composite(
            viewport, Image.new('RGBA', viewport.size, (0, 0, 0, 150)))
        draw = ImageDraw.Draw(image)
        sx, sy = viewport.width / (510 if visible else 512), viewport.height / 384
        origin = (0, 0)
        gold, white, muted, cyan = '#f4d873', '#eeeeee', '#999999', '#77c9dc'

        def point(x, y):
            return round((x - int(visible)) * sx) - origin[0], round(y * sy) - origin[1]

        def box(rect, fill='#222222', outline='#626262'):
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
            box(rect, '#303030' if highlighted else '#222222',
                gold if highlighted else cyan if active else '#626262')
            x, y = rect[0] + 8, rect[1] + 7
            if centered:
                raw = glyph(label)
                ink = raw.getbbox()
                x = (rect[0] + rect[2] - raw.width * scale) / 2
                y = (rect[1] + rect[3] - ((ink[3] - ink[1]) if ink else raw.height) * scale) / 2
            text(label, x, y, rect[2] - rect[0] - 16, white if enabled else muted, scale)

        def picture(entry, rect, thumb=False, outline='#626262'):
            key = self.image_key(entry, thumb)
            result = self.reads.request(key, lambda: read_capture(entry,
                (510, 384) if thumb else (2040, 1536)), 0 if thumb else -5)
            if result is None:
                box(rect, '#222222', outline)
                text('...', (rect[0] + rect[2]) / 2 - 6, (rect[1] + rect[3]) / 2, 30, muted)
                return None
            if result.error:
                box(rect, '#222222', outline)
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
            border = max(1, round(min(sx, sy)))
            draw.rectangle((pos[0] - border, pos[1] - border,
                            pos[0] + fitted.width + border - 1, pos[1] + fitted.height + border - 1),
                           outline=outline, width=border)
            return result.value[1]

        def draw_list():
            nonlocal image, draw, origin
            box(self.LIST, '#181818', None)
            base, base_draw = image, draw
            clip = (*point(*self.LIST[:2]), *point(*self.LIST[2:]))
            origin = clip[:2]
            image = Image.new('RGBA', (clip[2] - clip[0], clip[3] - clip[1]), '#181818')
            draw = ImageDraw.Draw(image)
            for index in self.visible_indices:
                entry = self.entries[index]
                rect = self.row_rect(index)
                height = 44 if self.columns == 2 else 82
                outline = gold if self.focus == 100 + index and not modal else cyan if self.selected == index else '#626262'
                picture(entry, (rect[0], rect[1], rect[2], rect[1] + height), True, outline)
                text(entry.date.replace('  ', ' '), rect[0] + 2, rect[1] + height + 5,
                     rect[2] - rect[0] - 4, cyan if self.selected == index else muted,
                     0.4 if self.columns == 2 else 0.55)
            base.paste(image, clip[:2])
            image, draw, origin = base, base_draw, (0, 0)
            if self.max_scroll:
                height = self.LIST[3] - self.LIST[1]
                thumb = max(16, height * height / (math.ceil(len(self.entries) / self.columns) * self.row_height))
                top = self.LIST[1] + (height - thumb) * self.scroll / self.max_scroll
                box((157, self.LIST[1], 159, self.LIST[3]), '#303030', None)
                box((157, top, 159, top + thumb), '#858585', None)

        if surface is not None:
            draw_list()
            return image

        if cached is None:
            box(self.PANEL, '#181818', '#858585')
            text('Screenshots', 36, 26, 250, gold, 1)
            text('Take screenshots with F8', 36, 43, 190, muted, 0.5)
            text(f'{len(self.entries)} PNG', 374, 29, 70, muted, right=True)
            for i, rect in enumerate(self.VIEWS):
                box(rect, '#253033' if self.columns == i + 1 else '#222222',
                    gold if self.focus == 16 + i else cyan if self.columns == i + 1 else '#626262')
                for column in range(i + 1):
                    for row in range(2):
                        x = rect[0] + 6 + column * 7
                        box((x, rect[1] + 5 + row * 6, x + (10 if i == 0 else 5), rect[1] + 9 + row * 6),
                            '#eeeeee', None)
            if not modal and self.hovered in (16, 17):
                text('Large thumbnails' if self.hovered == 16 else 'Small thumbnails', 238, 45, 114, muted, 0.4)
            button(self.REFRESH, 'Refresh', 15)
            text('Size', 36, 58, 44, muted)
            for i, rect in enumerate(self.SCALES):
                button(rect, f'{i + 1}x', i, active=self.scale == i + 1)
            text(f'{510 * self.scale} x {384 * self.scale}', 238, 58, 114, muted, 0.6)
            box(self.INCLUDE_UI, '#222222', gold if self.focus == 4 else '#626262')
            box((366, 58, 374, 66), cyan if self.include_ui else '#181818')
            if self.include_ui:
                draw.line([point(367, 62), point(369, 64), point(373, 59)], fill='#181818', width=max(1, round(sx)))
            text('With menus', 380, 58, 88)
            text(str(self.folder).replace('\\', '/'), 36, 77, 438, muted, 0.55, tail=True)
            draw_list()
            if self.entry:
                dimensions = picture(self.entry, self.PREVIEW)
                text(self.entry.path.name.replace('_', ' '), 174, 311, 268, gold, 0.6)
                if dimensions:
                    text(f'{dimensions[0]} x {dimensions[1]}', 174, 326, 175, muted, 0.6)
                text(f'{self.entry.size / 1024:.0f} KB', 440, 326, 80, muted, 0.6, right=True)
                box(self.DELETE, '#303030' if self.focus == 13 else '#222222',
                    gold if self.focus == 13 else '#626262')
                draw.line([point(458, 318), point(459, 329), point(465, 329), point(466, 318)],
                          fill=white, width=max(1, round(sx)))
                draw.line([point(457, 315), point(467, 315)], fill=white, width=max(1, round(sx)))
                draw.line([point(460, 315), point(460, 313), point(464, 313), point(464, 315)],
                          fill=white, width=max(1, round(sx)))
                for x in (461, 464):
                    draw.line([point(x, 320), point(x, 326)], fill=white, width=max(1, round(sx)))
            else:
                box(self.PREVIEW, '#0c0c0c')
                text('Reading folder...' if self.applied_scan != self.scan_key else 'No screenshots yet',
                     206, 186, 240, muted)
            for i, (rect, label) in enumerate(zip(self.FOOTER, ('Close', 'Folder', 'Capture PNG'))):
                button(rect, label, 10 + i, active=i == 2)
            if self.error or self.status:
                box((174, 323, 444, 339), '#181818', None)
                text(self.error or self.status, 174, 326, 270, '#ff9b9b' if self.error else gold, 0.6)
            if not modal and self.hovered == 13:
                box((350, 292, 474, 307), '#303030', '#858585')
                text('Delete screenshot', 356, 296, 112, white, 0.6)
            if modal:
                image = Image.alpha_composite(image, Image.new('RGBA', image.size, (0, 0, 0, 150)))
                draw = ImageDraw.Draw(image)
                remember(self.modal_cache, key, image.copy(), 3)
            else:
                remember(self.surface_cache, surface_key, image.copy(), 2)
        if self.choosing:
            box((48, 44, 464, 338), '#181818', '#858585')
            text('Screenshot folder', 64, 62, 384, gold, 1)
            box(self.PATH, '#0c0c0c', cyan if self.focus == 40 else '#626262')
            display_path = self.draft.replace('\\', '/')
            raw = glyph(display_path)
            offset = max(0, glyph(display_path[:self.caret]).width * 0.7 - 364)
            start, end = sorted((self.caret, self.anchor))
            if start != end:
                a = max(70, 70 + glyph(display_path[:start]).width * 0.7 - offset)
                b = min(442, 70 + glyph(display_path[:end]).width * 0.7 - offset)
                if b > a:
                    box((a, 95, b, 109), '#385462', None)
            raw = raw.resize((max(1, round(raw.width * 0.7 * sx)), max(1, round(raw.height * 0.7 * sy))),
                             Image.Resampling.NEAREST)
            raw = raw.crop((round(offset * sx), 0, min(raw.width, round((offset + 372) * sx)), raw.height))
            image.paste(raw, point(70, 95), raw)
            if self.focus == 40:
                x = 70 + glyph(display_path[:self.caret]).width * 0.7 - offset
                draw.line([point(x, 94), point(x, 109)], fill=cyan, width=max(1, round(sx)))
            for i, (rect, label) in enumerate(zip(self.FOLDER_TOOLS, ('Default', 'Home', 'Up', 'Drives'))):
                button(rect, label, 41 + i)
            box(self.FOLDER_LIST, '#0c0c0c')
            for i in range(self.folder_offset, min(len(self.folders), self.folder_offset + 6)):
                y = 156 + (i - self.folder_offset) * 20
                if self.focus == 1000 + i or self.hovered == 1000 + i:
                    box((65, y + 1, 447, y + 19), '#253033', None)
                box((72, y + 7, 80, y + 14), '#999999', None)
                box((72, y + 5, 76, y + 7), '#999999', None)
                text(self.folders[i].name or str(self.folders[i]).replace('\\', '/'), 86, y + 6, 354)
            if not self.folders:
                text('Unavailable' if self.folder_error else ('Reading folders...' if self.applied_folder != self.folder_key
                     else 'No subfolders'), 78, 202, 356, muted)
            if len(self.folders) > 6:
                height = max(6, 122 * 6 / len(self.folders))
                top = 157 + (122 - height) * self.folder_offset / (len(self.folders) - 6)
                box((444, 157, 447, 279), '#303030', None)
                box((444, top, 447, top + height), '#858585', None)
            text(self.folder_error, 64, 283, 384, '#ff9b9b', 0.6)
            for i, (rect, label) in enumerate(zip(self.FOLDER_BUTTONS,
                    ('Cancel', 'Working...' if self.commit_key is not None else 'Use folder'))):
                button(rect, label, 45 + i, active=i == 1)
        elif self.deleting:
            box((80, 121, 432, 270), '#181818', '#858585')
            text('Delete this screenshot?', 100, 142, 312, gold, 1)
            target = self.delete_target or self.entry
            text(target.path.name.replace('_', ' ') if target is not None else 'Unavailable', 100, 174, 312)
            text('This cannot be undone.', 100, 197, 312, muted)
            for i, (rect, label) in enumerate(zip(self.CONFIRM_BUTTONS, ('Cancel', 'Delete'))):
                button(rect, label, 60 + i, scale=1, centered=True)
        return image
