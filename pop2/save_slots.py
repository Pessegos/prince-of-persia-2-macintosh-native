"""Local save slots and their resolution-aware in-game browser."""

from dataclasses import dataclass, field
from datetime import datetime
import math
from pathlib import Path

from PIL import Image, ImageDraw

from pop2.save_game import SAVE_DIRECTORY, decode_preview, read_document, save_name


def remember(cache, key, value, limit=256):
    if len(cache) >= limit:
        del cache[next(iter(cache))]
    cache[key] = value
    return value


@dataclass(frozen=True)
class SaveSlot:
    path: Path
    name: str
    exists: bool = False
    level: int | None = None
    resume: str = ""
    capacity: int | None = None
    date: str = ""
    preview: object = None
    error: str = ""
    modified: float = 0.0
    document: dict | None = field(default=None, repr=False, compare=False)


def read_slot(path, name):
    if not path.exists():
        return SaveSlot(path, name)
    try:
        document = read_document(path)
        name = save_name(document['name']) if 'name' in document else name
        legacy = document['version'] == 1
        progress = document.get('resume', {})
        if not legacy and (not isinstance(progress, dict)
                           or set(progress) != {'checkpoint', 'max_life'}
                           or type(progress['max_life']) is not int
                           or not 1 <= progress['max_life'] <= 12):
            raise ValueError('Invalid save progress')
        date = (datetime.fromisoformat(document['created_at']).astimezone()
                if 'created_at' in document else datetime.fromtimestamp(path.stat().st_mtime))
        return SaveSlot(path, name, True, document['level'],
                        'Legacy save' if legacy else 'Checkpoint' if progress['checkpoint'] else 'Level start',
                        progress.get('max_life'), date.strftime('%d %b %Y  %H:%M'),
                        decode_preview(document.get('preview')) if document.get('preview_at_resume')
                        and document.get('preview_version') == 2 else None,
                        modified=path.stat().st_mtime, document=document)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return SaveSlot(path, name, True, error='Save unavailable')


def list_slots(directory=SAVE_DIRECTORY):
    directory = Path(directory)
    entries = [read_slot(path, path.stem) for path in directory.glob('*.pop2save') if path.is_file()]
    return tuple(sorted(entries, key=lambda slot: (-slot.modified, slot.path.name.casefold())))


@dataclass
class SaveBrowser:
    slots: tuple
    mode: str = 'load'
    selected: int = 0
    focus: int = 100
    save_available: bool = True
    confirmation: str | None = None
    error: str = ''
    status: str = ''
    current: SaveSlot | None = None
    active_path: Path | None = None
    preview_provider: object = field(default=None, repr=False)
    scroll: float = 0.0
    scroll_target: float = 0.0
    scroll_velocity: float = 0.0
    editing: str | None = None
    draft: str = ''
    caret: int = 0
    anchor: int = 0
    hovered: int | None = None
    glyph_cache: dict = field(default_factory=dict, repr=False, compare=False)
    text_cache: dict = field(default_factory=dict, repr=False, compare=False)
    preview_cache: dict = field(default_factory=dict, repr=False, compare=False)
    modal_cache: dict = field(default_factory=dict, repr=False, compare=False)
    list_base_cache: dict = field(default_factory=dict, repr=False, compare=False)

    PANEL = (28, 16, 484, 368)
    TABS = ((40, 53, 144, 79), (150, 53, 254, 79))
    PREVIEW = (238, 99, 472, 267)
    FOOTER = ((40, 328, 108, 356), (116, 328, 196, 356),
              (204, 328, 324, 356), (332, 328, 472, 356))
    LIST = (40, 99, 228, 321)
    ROW_HEIGHT = 42
    RENAME = (442, 274, 472, 294)
    NAME_FIELD = (100, 166, 412, 199)
    CONFIRM = ((100, 222, 246, 252), (258, 222, 412, 252))

    def __post_init__(self):
        if self.mode == 'save' and not self.slots and self.focus == 100:
            self.focus = 29

    @property
    def items(self):
        return self.slots

    @property
    def footer_rects(self):
        return self.FOOTER if self.mode == 'save' else (*self.FOOTER[:2], (204, 328, 472, 356))

    @property
    def entry(self):
        return self.items[self.selected] if self.items else SaveSlot(Path(), 'No saved games')

    @property
    def detail(self):
        return self.current if self.mode == 'save' and self.current and (
            not self.entry.exists or self.editing == 'create') else self.entry

    @property
    def max_scroll(self):
        return max(0, len(self.items) * self.ROW_HEIGHT - (self.LIST[3] - self.LIST[1]))

    def ensure_visible(self, immediate=False):
        top, bottom = self.selected * self.ROW_HEIGHT, (self.selected + 1) * self.ROW_HEIGHT
        height = self.LIST[3] - self.LIST[1]
        self.scroll_target = max(0, min(self.max_scroll,
            top if top < self.scroll_target else bottom - height if bottom > self.scroll_target + height
            else self.scroll_target))
        if immediate:
            self.scroll = self.scroll_target
            self.scroll_velocity = 0

    def wheel(self, steps):
        if self.confirmation or self.editing:
            return False
        target = max(0, min(self.max_scroll, self.scroll_target + steps * self.ROW_HEIGHT))
        changed = target != self.scroll_target
        self.scroll_target = target
        return changed

    def animate(self, seconds):
        if self.editing or self.confirmation:
            return False
        distance = self.scroll_target - self.scroll
        if abs(distance) < 0.025 and abs(self.scroll_velocity) < 0.1:
            self.scroll = self.scroll_target
            self.scroll_velocity = 0
            return False
        # Exact critically damped motion keeps both position and velocity
        # continuous when the wheel changes direction or frame rate varies.
        seconds = max(0, seconds)
        decay = math.exp(-24 * seconds)
        offset = -distance
        change = (self.scroll_velocity + 24 * offset) * seconds
        self.scroll = self.scroll_target + (offset + change) * decay
        self.scroll_velocity = (self.scroll_velocity - 24 * change) * decay
        if self.scroll < 0 or self.scroll > self.max_scroll:
            self.scroll = max(0, min(self.max_scroll, self.scroll))
            self.scroll_velocity = 0
        return True

    @property
    def primary_enabled(self):
        return self.entry.exists and (self.save_available if self.mode == 'save' else not self.entry.error)

    @staticmethod
    def contains(rect, x, y):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]

    def row_rect(self, row):
        top = self.LIST[1] + row * self.ROW_HEIGHT - self.scroll
        return 40, top, 222, top + self.ROW_HEIGHT - 3

    def hit(self, x, y):
        if self.confirmation or self.editing:
            if self.editing and self.contains(self.NAME_FIELD, x, y):
                return 32
            return next((30 + index for index, rect in enumerate(self.CONFIRM)
                         if self.contains(rect, x, y)), None)
        controls = dict(enumerate(self.TABS))
        if self.contains(self.LIST, x, y):
            if x >= 223 and self.max_scroll:
                return 24
            return next((100 + row for row in range(len(self.items))
                         if self.contains(self.row_rect(row), x, y)), None)
        if self.entry.exists and not self.entry.error:
            controls[25] = self.RENAME
        controls.update(zip((28, 26, 27, 29), self.footer_rects))
        return next((index for index, rect in controls.items() if self.contains(rect, x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        if self.editing:
            changed = index != self.hovered
            self.hovered = index
            return changed
        if index is None or index == self.focus:
            return False
        self.focus = index
        return True

    def switch(self, mode):
        self.mode = mode
        self.selected = 0
        if mode == 'load' and self.slots:
            self.selected = max((index for index, slot in enumerate(self.slots)
                                 if slot.exists and not slot.error),
                                key=lambda index: self.slots[index].modified, default=self.selected)
        self.selected = next((i for i, slot in enumerate(self.slots)
                              if slot.path == self.active_path and not slot.error), self.selected)
        self.error = self.status = ''
        self.scroll = self.scroll_target = 0
        self.scroll_velocity = 0
        self.ensure_visible(immediate=True)

    def edit_name(self, mode):
        self.editing = mode
        self.hovered = None
        self.draft = self.entry.name if mode == 'rename' else (
            f'Level {self.current.level} - {"Checkpoint" if self.current.resume == "Checkpoint" else "Start"}'
            if self.current else 'Saved game')
        self.caret, self.anchor, self.focus = len(self.draft), 0, 32

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
            char = ''.join(c for c in char if c.isprintable())[:48 - len(self.draft) + end - start]
            self.draft = self.draft[:start] + char + self.draft[end:]
            self.caret = self.anchor = start + len(char)

    def activate(self):
        if self.editing:
            if self.focus == 31:
                if self.draft.strip():
                    return 'slot_create' if self.editing == 'create' else 'slot_rename'
                self.focus = 32
            if self.focus == 30:
                self.editing, self.focus = None, 27
            return 'changed'
        if not self.confirmation and 100 <= self.focus < 100 + len(self.items):
            self.selected = self.focus - 100
        if self.confirmation:
            if self.focus == 31:
                return 'slot_' + self.confirmation
            self.confirmation = None
            self.focus = 27
        elif self.focus in (0, 1):
            self.switch('save' if self.focus == 0 else 'load')
        elif self.focus == 28:
            return 'save_back'
        elif self.focus == 29 and self.mode == 'save' and self.save_available:
            self.edit_name('create')
        elif self.focus == 25 and self.entry.exists:
            self.edit_name('rename')
        elif self.focus == 26 and self.entry.exists:
            self.confirmation, self.focus = 'delete', 30
        elif (self.focus == 27 or self.focus >= 100) and self.primary_enabled:
            if self.mode == 'load' or self.entry.exists:
                self.confirmation, self.focus = self.mode, 30
            else:
                self.edit_name('create')
        return 'changed'

    def click(self, x, y):
        index = self.hit(x, y)
        if index is None:
            return 'changed'
        self.focus = index
        if index == 24:
            self.scroll_target = self.max_scroll * (y - self.LIST[1]) / (self.LIST[3] - self.LIST[1])
            return 'changed'
        if not self.confirmation and not self.editing and index >= 100:
            self.selected = index - 100
            self.error = self.status = ''
            if not self.entry.exists and self.save_available:
                self.edit_name('create')
            return 'changed'
        return self.activate()

    def key(self, key, backwards=False, char='', control=False):
        if self.editing:
            if key == 'Escape':
                self.editing, self.focus = None, 27
            elif key in ('Return', 'KP_Enter') or key == 'space' and self.focus in (30, 31):
                if self.focus == 32:
                    self.focus = 31
                return self.activate()
            elif key == 'Tab':
                controls = (32, 30, 31)
                self.focus = controls[(controls.index(self.focus) + (-1 if backwards else 1)) % 3]
            elif self.focus == 32:
                self.edit_text(key, char, control, backwards)
            return 'changed'
        if key == 'Escape':
            if self.confirmation:
                self.confirmation, self.focus = None, 27
                return 'changed'
            return 'save_back'
        if key in ('Return', 'KP_Enter', 'space'):
            return self.activate()
        if self.confirmation:
            if key in ('Left', 'Right', 'Up', 'Down', 'Tab'):
                self.focus = 31 if self.focus == 30 else 30
        elif key in ('Up', 'Down'):
            self.selected = max(0, min(len(self.items) - 1, self.selected + (-1 if key == 'Up' else 1)))
            self.focus = 100 + self.selected
            self.ensure_visible()
            self.error = self.status = ''
        elif key in ('Prior', 'Next'):
            self.selected = max(0, min(len(self.items) - 1, self.selected + (-5 if key == 'Prior' else 5)))
            self.focus = 100 + self.selected
            self.ensure_visible()
        elif key == 'Tab':
            controls = (0, 1, 100 + self.selected, 25, 28, 26, 27) + ((29,) if self.mode == 'save' else ())
            position = controls.index(self.focus) if self.focus in controls else 2
            self.focus = controls[(position + (-1 if backwards else 1)) % len(controls)]
        elif key == 'Delete' and self.entry.exists:
            self.confirmation, self.focus = 'delete', 30
        return 'changed'

    def draw(self, viewport, font, *, visible=False, background_key=None):
        modal = self.confirmation or self.editing
        key = (viewport.size, visible, id(font), background_key if background_key is not None else id(viewport),
               self.mode, self.selected, id(self.slots), id(self.current), self.scroll,
               self.error, self.status, self.save_available, self.editing, self.active_path)
        cached = self.modal_cache.get(key) if modal else None
        list_key = key[:8] + key[9:] + (self.focus,)
        list_base = self.list_base_cache.get(list_key) if not modal else None
        if not modal:
            self.modal_cache.clear()
        image = (cached.copy() if cached is not None else list_base.copy() if list_base is not None else
                 Image.alpha_composite(viewport, Image.new('RGBA', viewport.size, (0, 0, 0, 150))))
        draw = ImageDraw.Draw(image)
        gold, white, muted, cyan = '#f4d873', '#eeeeee', '#999999', '#77c9dc'
        sx, sy = viewport.width / (510 if visible else 512), viewport.height / 384
        origin = (0, 0)

        def point(x, y):
            return round((x - int(visible)) * sx) - origin[0], round(y * sy) - origin[1]

        def rectangle(rect, **colors):
            draw.rectangle((*point(*rect[:2]), *point(*rect[2:])),
                           width=max(1, round(min(sx, sy))), **colors)

        def line(points, color, width=1):
            draw.line([point(x, y) for x, y in points], fill=color,
                      width=max(1, round(width * min(sx, sy))))

        def glyphs(value, color):
            encoded = str(value).encode('mac_roman', errors='replace')
            value = bytes(code if code in font.glyphs else 63 for code in encoded).decode('mac_roman')
            key = id(font), value, color
            if key not in self.glyph_cache:
                remember(self.glyph_cache, key, font.text(value, color))
            return self.glyph_cache[key]

        def text(value, x, y, color=white, width=190, small=False, ellipsize=False, align='left'):
            if not value:
                return
            key = id(font), str(value), color, width, small, ellipsize, sx, sy
            glyph = self.text_cache.get(key)
            if glyph is None:
                if ellipsize and glyphs(value, color).width * 0.7 > width:
                    while value and glyphs(value + '...', color).width * 0.7 > width:
                        value = value[:-1]
                    value += '...'
                glyph = glyphs(value, color)
                ink = glyph.getbbox()
                if ink:
                    glyph = glyph.crop((0, ink[1], glyph.width, ink[3]))
                scale = min(0.7 if small else 1, width / max(1, glyph.width))
                size = (max(1, round(glyph.width * scale * sx)),
                        max(1, round(glyph.height * scale * sy)))
                if glyph.size != size:
                    glyph = glyph.resize(size, Image.Resampling.NEAREST)
                remember(self.text_cache, key, glyph)
            x, y = point(x, y)
            image.paste(glyph, (x - glyph.width if align == 'right' else x, y), glyph)

        def button(rect, label, index, enabled=True, active=False):
            highlighted = self.focus == index or self.editing and self.hovered == index
            rectangle(rect, fill='#303030' if highlighted else '#222222',
                      outline=gold if highlighted else cyan if active else '#626262')
            text(label, rect[0] + 10, rect[1] + 7, white if enabled else muted, rect[2] - rect[0] - 20)

        def draw_list():
            nonlocal image, draw, origin
            rectangle(self.LIST, fill='#181818')
            # Allocate only the clipped list, not another full-window layer.
            background = image
            clip = (*point(*self.LIST[:2]), *point(*self.LIST[2:]))
            origin = clip[:2]
            image = Image.new('RGBA', (clip[2] - clip[0], clip[3] - clip[1]))
            draw = ImageDraw.Draw(image)
            for row, slot in enumerate(self.items):
                rect = self.row_rect(row)
                if rect[3] <= self.LIST[1] or rect[1] >= self.LIST[3]:
                    continue
                selected = self.selected == row
                current = slot.path == self.active_path
                rectangle(rect, fill='#253033' if selected else '#222222',
                          outline=gold if self.focus == 100 + row else cyan if selected else '#404040')
                text(slot.name, rect[0] + 8, rect[1] + 7, cyan if selected else white, 100, True, True)
                text(f'Level {slot.level}' if slot.level else '---', rect[2] - 8, rect[1] + 7,
                     muted, 59, True, align='right')
                if current:
                    line(((rect[0] + 2, rect[1] + 3), (rect[0] + 2, rect[3] - 3)), cyan)
                    text('Current', rect[0] + 8, rect[1] + 25, cyan, 42, True)
                text(slot.error or slot.date, rect[2] - 8, rect[1] + 25,
                     muted, 120 if current else 164, True, align='right')
            background.alpha_composite(image, origin)
            image, origin = background, (0, 0)
            draw = ImageDraw.Draw(image)
            if not self.items:
                text('No saved games', 50, 181, muted, 168, True)
            if self.max_scroll:
                height = self.LIST[3] - self.LIST[1]
                thumb = max(16, height * height / (len(self.items) * self.ROW_HEIGHT))
                top = self.LIST[1] + (height - thumb) * self.scroll / self.max_scroll
                rectangle((225, self.LIST[1], 227, self.LIST[3]), fill='#303030')
                rectangle((225, top, 227, top + thumb), fill='#858585')

        if list_base is not None:
            draw_list()
            return image

        if cached is None:
            rectangle(self.PANEL, fill='#181818', outline='#858585')
            text('Saved Games', 40, 29, gold)
            text(f'{len(self.slots)} {"save" if len(self.slots) == 1 else "saves"}', 472, 32,
                 muted, 82, True, align='right')
            for index, (rect, label) in enumerate(zip(self.TABS, ('Save', 'Load'))):
                button(rect, label, index, active=self.mode == label.lower())
            line(((40, 88), (472, 88)), '#404040')
            draw_list()
            slot = self.detail
            source_key = ('source', slot.path, slot.modified, id(slot.document), id(slot.preview), id(self.preview_provider))
            if source_key not in self.preview_cache:
                try:
                    preview = (self.preview_provider(slot) if slot.document is not None
                        and self.preview_provider is not None and slot.preview is None else slot.preview)
                except (OSError, ValueError):
                    preview = None
                remember(self.preview_cache, source_key, preview, 8)
            preview = self.preview_cache[source_key]
            left, top, right, bottom = self.PREVIEW
            rectangle(self.PREVIEW, fill='#0c0c0c', outline='#626262')
            if preview is not None:
                pos = point(left + 1, top + 1)
                edge = point(right - 1, bottom - 1)
                size = max(1, edge[0] - pos[0]), max(1, edge[1] - pos[1])
                fit_key = ('fit', source_key, size)
                if fit_key not in self.preview_cache:
                    remember(self.preview_cache, fit_key, preview.resize(size, Image.Resampling.NEAREST), 8)
                image.paste(self.preview_cache[fit_key], pos)
            else:
                text(slot.error or ('No preview' if self.items else 'No saved games'), left + 28, top + 74,
                     muted, right - left - 50)
            name_width = 194
            name_lines = [slot.name]
            if glyphs(slot.name, gold).width * 0.7 > name_width:
                positions = range(1, len(slot.name))
                word_breaks = [i for i in positions if slot.name[i].isspace()]
                candidates = word_breaks or positions
                split = min(candidates, key=lambda i: max(
                    glyphs(slot.name[:i].rstrip(), gold).width,
                    glyphs(slot.name[i:].lstrip(), gold).width))
                name_lines = [slot.name[:split].rstrip(), slot.name[split:].lstrip()]
            for index, value in enumerate(name_lines):
                text(value, 238, 276 + index * 11, gold, name_width, True)
            if self.entry.exists and not self.entry.error:
                rectangle(self.RENAME, fill='#222222', outline=gold if self.focus == 25 else '#626262')
                line(((451, 288), (461, 278)), white, 2)
                line(((450, 290), (454, 289)), white)
            resume = {'Level start': 'Resumes at level start',
                      'Checkpoint': 'Resumes at checkpoint'}.get(slot.resume, slot.resume)
            text(resume, 238, 300, muted, 234, True)
            if slot.capacity is not None:
                text(f'Life {slot.capacity}', 472, 315, muted, 64, True, align='right')
            for index, (rect, label) in zip((28, 26, 27, 29), zip(self.footer_rects,
                    ('Back', 'Delete', 'Overwrite' if self.mode == 'save' else 'Load game', 'New save'))):
                enabled = (self.entry.exists if index == 26 else self.primary_enabled if index == 27
                           else self.save_available if index == 29 else True)
                button(rect, label, index, enabled, active=index == 29 and enabled)
            text(self.error or self.status or slot.date, 238, 315,
                 '#ff9b9b' if self.error else muted, 164 if slot.capacity is not None else 234, True)
            if not modal:
                remember(self.list_base_cache, list_key, image.copy(), 3)
        if self.confirmation or self.editing:
            if cached is None:
                image = Image.alpha_composite(image, Image.new('RGBA', image.size, (0, 0, 0, 140)))
                remember(self.modal_cache, key, image.copy(), 3)
            draw = ImageDraw.Draw(image)
            rectangle((80, 121, 432, 270), fill='#181818', outline='#858585')
            title = ('New save' if self.editing == 'create' else 'Rename save') if self.editing else {
                'save': 'Replace this save?', 'load': 'Load this game?', 'delete': 'Delete this save?'}[self.confirmation]
            text(title, 100, 142, gold, 312)
            if self.editing:
                rectangle(self.NAME_FIELD, fill='#0c0c0c', outline=cyan if self.focus == 32 else '#626262')
                glyph = glyphs(self.draft, white)
                ink = glyph.getbbox()
                if ink:
                    glyph = glyph.crop((0, ink[1], glyph.width, ink[3]))
                cursor = glyphs(self.draft[:self.caret], white).width
                offset = max(0, cursor - 292)
                start, end = sorted((self.anchor, self.caret))
                if start != end:
                    a = max(106, 106 + glyphs(self.draft[:start], white).width - offset)
                    b = min(406, 106 + glyphs(self.draft[:end], white).width - offset)
                    rectangle((a, 172, b, 192), fill='#385462')
                glyph = glyph.crop((offset, 0, min(glyph.width, offset + 300), glyph.height))
                if glyph.width:
                    glyph = glyph.resize((max(1, round(glyph.width * sx)), max(1, round(glyph.height * sy))), Image.Resampling.NEAREST)
                    image.paste(glyph, point(106, 174), glyph)
                if self.focus == 32:
                    line(((106 + cursor - offset, 172), (106 + cursor - offset, 192)), cyan)
                text(self.error, 100, 205, '#ff9b9b', 312, True)
            else:
                text(self.entry.name, 100, 171, white, 312, ellipsize=True)
                text('Current progress will be lost.' if self.confirmation == 'load' else
                     'This cannot be undone.', 100, 195, muted, 312, True)
            for index, (rect, label) in enumerate(zip(self.CONFIRM, ('Cancel',
                    ('Save' if self.editing == 'create' else 'Rename') if self.editing else
                    {'save': 'Replace', 'load': 'Load', 'delete': 'Delete'}[self.confirmation]))):
                button(rect, label, 30 + index, index == 0 or not self.editing or bool(self.draft.strip()))
        return image
