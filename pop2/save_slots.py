"""Local save slots and their resolution-aware in-game browser."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from pop2.save_game import SAVE_DIRECTORY, decode_preview, read_document


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


def read_slot(path, name):
    if not path.exists():
        return SaveSlot(path, name)
    try:
        document = read_document(path)
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
                        decode_preview(document.get('preview')), modified=path.stat().st_mtime)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return SaveSlot(path, name, True, error='Save unavailable')


def list_slots(directory=SAVE_DIRECTORY):
    directory = Path(directory)
    paths = [directory / f'slot-{index:02}.pop2save' for index in range(1, 13)]
    entries = [read_slot(path, f'Slot {index:02}') for index, path in enumerate(paths, 1)]
    if directory.exists():
        legacy = sorted((path for path in directory.glob('*.pop2save') if path not in paths),
                        key=lambda path: path.name.casefold())[:100]
        entries.extend(read_slot(path, path.stem) for path in legacy)
    return tuple(entries)


@dataclass
class SaveBrowser:
    slots: tuple
    mode: str = 'load'
    selected: int = 0
    focus: int = 10
    save_available: bool = True
    confirmation: str | None = None
    error: str = ''
    status: str = ''
    current: SaveSlot | None = None

    PANEL = (28, 16, 484, 368)
    TABS = ((40, 53, 144, 79), (150, 53, 254, 79))
    PREVIEW = (238, 99, 472, 267)
    FOOTER = ((40, 328, 140, 356), (148, 328, 248, 356), (260, 328, 472, 356))
    PAGES = ((40, 299, 68, 321), (200, 299, 228, 321))
    CONFIRM = ((100, 222, 246, 252), (258, 222, 412, 252))

    @property
    def page(self):
        return self.selected // 6

    @property
    def entry(self):
        return self.slots[self.selected]

    @property
    def primary_enabled(self):
        return self.save_available if self.mode == 'save' else self.entry.exists and not self.entry.error

    @staticmethod
    def contains(rect, x, y):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]

    @staticmethod
    def row_rect(row):
        return 40, 99 + row * 32, 228, 128 + row * 32

    def hit(self, x, y):
        if self.confirmation:
            return next((30 + index for index, rect in enumerate(self.CONFIRM)
                         if self.contains(rect, x, y)), None)
        controls = dict(enumerate(self.TABS))
        controls.update({10 + row: self.row_rect(row)
                         for row in range(min(6, len(self.slots) - self.page * 6))})
        controls.update(zip((20, 21), self.PAGES))
        controls.update(zip((28, 26, 27), self.FOOTER))
        return next((index for index, rect in controls.items() if self.contains(rect, x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        if index is None or index == self.focus:
            return False
        self.focus = index
        return True

    def switch(self, mode):
        self.mode = mode
        if mode == 'load' and not self.primary_enabled:
            self.selected = max((index for index, slot in enumerate(self.slots)
                                 if slot.exists and not slot.error),
                                key=lambda index: self.slots[index].modified, default=self.selected)
        self.error = self.status = ''

    def activate(self):
        if not self.confirmation and 10 <= self.focus < 16:
            self.selected = self.page * 6 + self.focus - 10
        if self.confirmation:
            if self.focus == 31:
                return 'slot_' + self.confirmation
            self.confirmation = None
            self.focus = 27
        elif self.focus in (0, 1):
            self.switch('save' if self.focus == 0 else 'load')
        elif self.focus in (20, 21):
            pages = (len(self.slots) + 5) // 6
            self.selected = ((self.page + (-1 if self.focus == 20 else 1)) % pages) * 6
            self.error = self.status = ''
        elif self.focus == 28:
            return 'save_back'
        elif self.focus == 26 and self.entry.exists:
            self.confirmation, self.focus = 'delete', 30
        elif (self.focus == 27 or 10 <= self.focus < 16) and self.primary_enabled:
            if self.mode == 'load' or self.entry.exists:
                self.confirmation, self.focus = self.mode, 30
            else:
                return 'slot_save'
        return 'changed'

    def click(self, x, y):
        index = self.hit(x, y)
        if index is None:
            return 'changed'
        self.focus = index
        if not self.confirmation and 10 <= index < 16:
            self.selected = self.page * 6 + index - 10
            self.error = self.status = ''
            return 'changed'
        return self.activate()

    def key(self, key, backwards=False):
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
            self.selected = (self.selected + (-1 if key == 'Up' else 1)) % len(self.slots)
            self.focus = 10 + self.selected % 6
            self.error = self.status = ''
        elif key in ('Left', 'Right', 'Prior', 'Next'):
            self.focus = 20 if key in ('Left', 'Prior') else 21
            return self.activate()
        elif key == 'Tab':
            controls = (0, 1, 10 + self.selected % 6, 20, 21, 28, 26, 27)
            position = controls.index(self.focus) if self.focus in controls else 2
            self.focus = controls[(position + (-1 if backwards else 1)) % len(controls)]
        elif key == 'Delete' and self.entry.exists:
            self.confirmation, self.focus = 'delete', 30
        return 'changed'

    def draw(self, viewport, font, *, visible=False):
        image = Image.alpha_composite(viewport, Image.new('RGBA', viewport.size, (0, 0, 0, 150)))
        draw = ImageDraw.Draw(image)
        gold, white, muted, cyan = '#f4d873', '#eeeeee', '#999999', '#77c9dc'
        sx, sy = viewport.width / (510 if visible else 512), viewport.height / 384

        def point(x, y):
            return round((x - int(visible)) * sx), round(y * sy)

        def rectangle(rect, **colors):
            draw.rectangle((*point(*rect[:2]), *point(*rect[2:])),
                           width=max(1, round(min(sx, sy))), **colors)

        def line(points, color, width=1):
            draw.line([point(x, y) for x, y in points], fill=color,
                      width=max(1, round(width * min(sx, sy))))

        def text(value, x, y, color=white, width=190, small=False):
            if not value:
                return
            encoded = str(value).encode('mac_roman', errors='replace')
            value = bytes(code if code in font.glyphs else 63 for code in encoded).decode('mac_roman')
            glyph = font.text(value, color)
            ink = glyph.getbbox()
            if ink:
                glyph = glyph.crop((0, ink[1], glyph.width, ink[3]))
            scale = min(0.7 if small else 1, width / max(1, glyph.width))
            size = (max(1, round(glyph.width * scale * sx)),
                    max(1, round(glyph.height * scale * sy)))
            if glyph.size != size:
                glyph = glyph.resize(size, Image.Resampling.NEAREST)
            image.paste(glyph, point(x, y), glyph)

        def button(rect, label, index, enabled=True, active=False):
            rectangle(rect, fill='#303030' if self.focus == index else '#222222',
                      outline=gold if self.focus == index else cyan if active else '#626262')
            text(label, rect[0] + 10, rect[1] + 7, white if enabled else muted, rect[2] - rect[0] - 20)

        rectangle(self.PANEL, fill='#181818', outline='#858585')
        text('Saved Games', 40, 29, gold)
        text(f'{self.selected + 1:02} / {len(self.slots):02}', 390, 32, muted, 82, True)
        for index, (rect, label) in enumerate(zip(self.TABS, ('Save', 'Load'))):
            button(rect, label, index, active=self.mode == label.lower())
        line(((40, 88), (472, 88)), '#404040')
        for row, slot in enumerate(self.slots[self.page * 6:self.page * 6 + 6]):
            rect = self.row_rect(row)
            selected = self.selected == self.page * 6 + row
            rectangle(rect, fill='#253033' if selected else '#222222',
                      outline=gold if self.focus == 10 + row else cyan if selected else '#404040')
            text(slot.name, rect[0] + 9, rect[1] + 7, cyan if selected else white, 112)
            text(f'L{slot.level}' if slot.level else '---' if slot.exists else 'Empty',
                 rect[2] - 48, rect[1] + 10, muted, 40, True)
        slot = self.current if self.mode == 'save' and not self.entry.exists and self.current else self.entry
        left, top, right, bottom = self.PREVIEW
        rectangle(self.PREVIEW, fill='#0c0c0c', outline='#626262')
        if slot.preview is not None:
            origin = point(left + 1, top + 1)
            edge = point(right - 1, bottom - 1)
            preview = slot.preview.resize((max(1, edge[0] - origin[0]),
                                           max(1, edge[1] - origin[1])), Image.Resampling.NEAREST)
            image.paste(preview, origin)
        else:
            text(slot.error or ('No preview' if slot.exists else 'Empty slot'), left + 28, top + 74,
                 muted, right - left - 50)
        text(f'Level {slot.level}' if slot.level else slot.name, 238, 278, gold, 234)
        text(slot.resume, 238, 300, muted, 124, True)
        if slot.capacity is not None:
            text(f'Life {slot.capacity}', 400, 300, muted, 72, True)
        for index, (rect, label) in zip((28, 26, 27), zip(self.FOOTER,
                ('Back', 'Delete', 'Save game' if self.mode == 'save' else 'Load game'))):
            button(rect, label, index, slot.exists if index == 26 else self.primary_enabled if index == 27 else True)
        text(self.error or self.status or slot.date, 238, 315,
             '#ff9b9b' if self.error else muted, 234, True)
        for index, rect in zip((20, 21), self.PAGES):
            rectangle(rect, fill='#222222', outline=gold if self.focus == index else '#626262')
            x, y = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
            delta = -1 if index == 20 else 1
            line(((x - delta * 3, y - 5), (x + delta * 3, y), (x - delta * 3, y + 5)), white, 2)
        text(f'{self.page + 1} / {(len(self.slots) + 5) // 6}', 108, 305, muted, 80, True)
        if self.confirmation:
            image = Image.alpha_composite(image, Image.new('RGBA', image.size, (0, 0, 0, 140)))
            draw = ImageDraw.Draw(image)
            rectangle((80, 121, 432, 270), fill='#181818', outline='#858585')
            title = {'save': 'Replace this save?', 'load': 'Load this game?', 'delete': 'Delete this save?'}[self.confirmation]
            text(title, 100, 142, gold, 312)
            text(slot.name, 100, 171, white, 312)
            text('Current progress will be lost.' if self.confirmation == 'load' else
                 'This cannot be undone.', 100, 195, muted, 312, True)
            for index, (rect, label) in enumerate(zip(self.CONFIRM, ('Cancel',
                    {'save': 'Replace', 'load': 'Load', 'delete': 'Delete'}[self.confirmation]))):
                button(rect, label, 30 + index)
        return image
