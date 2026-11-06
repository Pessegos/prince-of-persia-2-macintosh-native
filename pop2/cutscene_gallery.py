"""A device-resolution story shelf with continuous horizontal scrolling."""

from dataclasses import dataclass, field
import math

from PIL import Image, ImageDraw

from pop2.cutscenes import CHAPTERS, chapter_available


@dataclass
class CutsceneGallery:
    collection: object
    preview: object
    index: int = 0
    focus: int = 0
    hovered: int | None = None
    error: str = ''
    chapters: tuple = CHAPTERS
    scroll: float = 0
    scroll_target: float = 0
    drag: tuple | None = None
    dragged: bool = False
    text_cache: dict = field(default_factory=dict, repr=False)
    image_cache: dict = field(default_factory=dict, repr=False)
    background_cache: tuple | None = field(default=None, repr=False)
    grid_cache: tuple | None = field(default=None, repr=False)
    card_cache: dict = field(default_factory=dict, repr=False)

    PANEL = (8, 10, 504, 363)
    STRIP = (20, 61, 492, 334)
    TRACK = (24, 342, 488, 348)
    PREVIOUS = (8, 175, 20, 211)
    NEXT = (492, 175, 504, 211)
    BACK = (22, 22, 87, 48)
    PLAY = (425, 22, 490, 48)
    PITCH = 160
    CARD_WIDTH = 150
    CARD_HEIGHT = 130
    COLUMNS = 3
    ROWS = 2

    @classmethod
    def cell(cls, index):
        # Fill down each column, then continue to the right. A continuous
        # grid stays dense even between the first six and the last chapters.
        return divmod(index, cls.ROWS)

    @property
    def chapter(self):
        return self.chapters[self.index]

    @property
    def unlocked(self):
        return self.chapter.key in self.collection.seen

    @property
    def max_scroll(self):
        columns = max((self.cell(i)[0] + 1 for i in range(len(self.chapters))), default=0)
        return max(0, (columns - self.COLUMNS) * self.PITCH)

    @property
    def first(self):
        return max(0, int(self.scroll // self.PITCH))

    @property
    def visible(self):
        return tuple(i for i in range(len(self.chapters))
                     if self.card_rect(i)[2] > self.STRIP[0] and self.card_rect(i)[0] < self.STRIP[2])

    def card_rect(self, index, *, offset=None):
        column, row = self.cell(index)
        x = self.STRIP[0] + 1 + column * self.PITCH - (self.scroll if offset is None else offset)
        y = 63 + row * 138
        return x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT

    @staticmethod
    def contains(rect, x, y):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]

    def move(self, delta):
        self.index = max(0, min(len(self.chapters) - 1, self.index + delta))
        left = self.cell(self.index)[0] * self.PITCH
        self.scroll_target = max(left - (self.COLUMNS - 1) * self.PITCH, min(self.scroll_target, left))
        self.scroll_target = max(0, min(self.max_scroll, self.scroll_target))
        self.focus = 0
        self.error = ''
        return 'changed'

    def wheel(self, steps):
        # Scrolling moves the shelf, not the selected chapter. Preserve partial
        # wheel deltas from touchpads rather than snapping to cards/pages.
        self.scroll_target = max(0, min(self.max_scroll, self.scroll_target + steps * self.PITCH * .8))

    def advance(self, seconds):
        difference = self.scroll_target - self.scroll
        self.scroll += difference * (1 - math.exp(-18 * max(0, seconds)))
        if abs(self.scroll_target - self.scroll) < .02:
            self.scroll = self.scroll_target
        return self.scroll != self.scroll_target

    def begin_drag(self, x, y):
        if not self.contains(self.STRIP, x, y):
            return False
        self.drag = (x, self.scroll)
        self.dragged = False
        self.scroll_target = self.scroll
        return True

    def move_drag(self, x):
        if self.drag is None:
            return False
        start, scroll = self.drag
        if abs(x - start) > 2:
            self.dragged = True
        if self.dragged:
            self.scroll = self.scroll_target = max(0, min(self.max_scroll, scroll + start - x))
        return self.dragged

    def end_drag(self, x, y):
        if self.drag is None:
            return 'changed'
        self.move_drag(x)
        dragged = self.dragged
        self.drag = None
        self.dragged = False
        return 'changed' if dragged else self.click(x, y)

    def activate(self):
        if self.focus == 2:
            return 'cutscene_back'
        return 'cutscene_play' if self.unlocked else 'changed'

    def key(self, key, backwards=False, char='', control=False):
        if key == 'Escape':
            return 'cutscene_back'
        if key in ('Left', 'Right', 'Up', 'Down'):
            column, row = self.cell(self.index)
            column += (key == 'Right') - (key == 'Left')
            row += (key == 'Down') - (key == 'Up')
            target = next((i for i in range(len(self.chapters)) if self.cell(i) == (column, row)), self.index)
            return self.move(target - self.index)
        if key == 'Home':
            return self.move(-len(self.chapters))
        if key == 'End':
            return self.move(len(self.chapters))
        if key == 'Tab':
            self.focus = (self.focus + (-1 if backwards else 1)) % 3
        elif key in ('Return', 'KP_Enter', 'space'):
            return self.activate()
        return 'changed'

    def hit(self, x, y):
        for code, rect in ((3, self.PREVIOUS), (4, self.NEXT), (2, self.BACK), (1, self.PLAY), (5, self.TRACK)):
            if self.contains(rect, x, y):
                return code
        if self.contains(self.STRIP, x, y):
            return next((100 + index for index in self.visible
                         if self.contains(self.card_rect(index), x, y)), None)
        return None

    def hover(self, x, y):
        target = self.hit(x, y)
        changed = target != self.hovered
        self.hovered = target
        return changed

    def click(self, x, y):
        target = self.hit(x, y)
        if target is None:
            return 'changed'
        if target >= 100:
            self.index = target - 100
            self.focus = 0
            self.error = ''
            return 'changed'
        if target in (3, 4):
            self.wheel(-1 if target == 3 else 1)
            return 'changed'
        if target == 5:
            fraction = (x - self.TRACK[0]) / (self.TRACK[2] - self.TRACK[0])
            self.scroll_target = max(0, min(self.max_scroll, fraction * self.max_scroll))
            return 'changed'
        self.focus = target
        return self.activate()

    def caption(self, image, font, value, rect, color, scale, sx, sy, *, wrap=False):
        def glyph(value):
            key = id(font), value, color
            if key not in self.text_cache:
                self.text_cache[key] = font.text(value, color)
            return self.text_cache[key]

        lines, line = [], ''
        for word in value.split():
            candidate = f'{line} {word}'.strip()
            if wrap and line and glyph(candidate).width * scale > rect[2] - rect[0] - 4:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        if not lines:
            return
        raw = [glyph(line) for line in lines]
        scale = min(scale, (rect[2] - rect[0] - 4) / max(g.width for g in raw),
                    (rect[3] - rect[1] - 2) / (len(raw) * font.height))
        height = font.height * scale
        y = (rect[1] + rect[3] - len(raw) * height) / 2
        for line, g in zip(lines, raw):
            key = id(font), line, color, round(scale * sx, 4), round(scale * sy, 4)
            if key not in self.text_cache:
                self.text_cache[key] = g.resize((max(1, round(g.width * scale * sx)),
                    max(1, round(g.height * scale * sy))), Image.Resampling.NEAREST)
            g = self.text_cache[key]
            x = round((rect[0] + rect[2]) / 2 * sx - g.width / 2)
            image.alpha_composite(g, (x, round(y * sy)))
            y += height

    def card_image(self, index, font, sx, sy):
        chapter = self.chapters[index]
        selected, hovered = self.index == index, self.hovered == 100 + index
        unlocked = chapter.key in self.collection.seen
        size = round(self.CARD_WIDTH * sx), round(self.CARD_HEIGHT * sy)
        key = index, id(font), size, selected, hovered, unlocked
        if key in self.card_cache:
            return self.card_cache[key]
        image = Image.new('RGBA', size, '#252525')
        draw = ImageDraw.Draw(image)
        stroke = max(1, round(min(sx, sy)))
        outline = '#f4d873' if selected else '#c6b58c' if hovered else '#626262'
        draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=outline, width=stroke * (2 if selected else 1))
        thumb = (round(2 * sx), round(2 * sy), round(148 * sx), round(112 * sy))
        if unlocked and chapter_available(chapter):
            try:
                thumb_size = thumb[2] - thumb[0], thumb[3] - thumb[1]
                image_key = index, thumb_size
                if image_key not in self.image_cache:
                    frame = self.preview(index)
                    self.image_cache[image_key] = frame.convert('RGBA').resize(thumb_size,
                        Image.Resampling.LANCZOS if thumb_size[0] < frame.width else Image.Resampling.NEAREST)
                image.alpha_composite(self.image_cache[image_key], thumb[:2])
            except (OSError, ValueError, KeyError, RuntimeError):
                self.caption(image, font, 'Unavailable', (2, 2, 148, 112), '#999999', .7, sx, sy)
        else:
            draw.rectangle(thumb, fill='#101010')
            cx, cy = size[0] / 2, 55 * sy
            draw.arc((cx - 7 * sx, cy - 15 * sy, cx + 7 * sx, cy + 4 * sy), 180, 360,
                     fill='#999999', width=stroke)
            draw.rectangle((cx - 11 * sx, cy - 2 * sy, cx + 11 * sx, cy + 14 * sy),
                           fill='#101010', outline='#999999', width=stroke)
        band = '#493c25' if selected else '#252525'
        draw.rectangle((stroke, round(113 * sy), size[0] - stroke - 1, size[1] - stroke - 1), fill=band)
        label = chapter.title if unlocked else f'Chapter {index + 1} - Locked'
        self.caption(image, font, label, (2, 113, 148, 129), '#f4d873' if selected else '#eeeeee', .72, sx, sy)
        self.card_cache[key] = image
        return image

    def draw(self, viewport, font, *, visible=False, background_key=None):
        sx, sy = viewport.width / (510 if visible else 512), viewport.height / 384
        ox = int(visible)
        stroke = max(1, round(min(sx, sy)))

        def point(x, y):
            return round((x - ox) * sx), round(y * sy)

        def bounds(rect):
            return *point(*rect[:2]), *point(*rect[2:])

        # The moving region and static frame are composed once per UI state.
        # Animation only crops/pastes the cached grid and updates its scrollbar;
        # there is no font drawing, asset IO or thumbnail resampling per frame.
        key = (viewport.size, visible, background_key or id(viewport), id(font), self.unlocked,
               self.focus, self.hovered if self.hovered in (1, 2) else None, self.error, self.collection.error)
        if self.background_cache is None or self.background_cache[0] != key:
            base = Image.alpha_composite(viewport.convert('RGBA'), Image.new('RGBA', viewport.size, (0, 0, 0, 145)))
            draw = ImageDraw.Draw(base)
            draw.rectangle(bounds(self.PANEL), fill='#181818', outline='#8c7954', width=stroke)
            self.caption(base, font, 'Cutscene Viewer', (95 - ox, 19, 417 - ox, 51), '#f4d873', 1, sx, sy)
            for code, rect, label in ((2, self.BACK, 'Back'), (1, self.PLAY, 'Play')):
                draw.rectangle(bounds(rect), fill='#303030' if self.focus == code else '#222222',
                               outline='#f4d873' if self.focus == code or self.hovered == code else '#626262', width=stroke)
                local = rect[0] - ox, rect[1], rect[2] - ox, rect[3]
                self.caption(base, font, label, local, '#eeeeee' if code == 2 or self.unlocked else '#666666', .75, sx, sy)
            message = self.error or self.collection.error or (
                'Continue the story to unlock this chapter.' if not self.unlocked else 'Enter: Play   Scroll or drag to browse')
            self.caption(base, font, message, (24 - ox, 350, 488 - ox, 362),
                         '#ff9b9b' if self.error else '#999999', .45, sx, sy)
            self.background_cache = key, base
        image = self.background_cache[1].copy()
        region = bounds(self.STRIP)
        width, height = region[2] - region[0], region[3] - region[1]
        grid_key = (viewport.size, visible, id(font), self.index, self.hovered if self.hovered is not None and self.hovered >= 100 else None,
                    tuple(sorted(self.collection.seen)), self.chapters)
        if self.grid_cache is None or self.grid_cache[0] != grid_key:
            grid = Image.new('RGBA', (width + round(self.max_scroll * sx), height), '#181818')
            for index in range(len(self.chapters)):
                rect = self.card_rect(index, offset=0)
                card = self.card_image(index, font, sx, sy)
                grid.alpha_composite(card, (round((rect[0] - self.STRIP[0]) * sx),
                                             round((rect[1] - self.STRIP[1]) * sy)))
            self.grid_cache = grid_key, grid
        left = round(self.scroll * sx)
        image.paste(self.grid_cache[1].crop((left, 0, left + width, height)), region[:2])
        draw = ImageDraw.Draw(image)
        for rect, direction, enabled in ((self.PREVIOUS, -1, self.scroll_target > 0),
                                         (self.NEXT, 1, self.scroll_target < self.max_scroll)):
            x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            draw.line((point(x - direction * 2, y - 5), point(x + direction * 2, y),
                       point(x - direction * 2, y + 5)), fill='#f4d873' if enabled else '#505050', width=stroke)
        draw.rectangle(bounds(self.TRACK), fill='#282828')
        track_width = self.TRACK[2] - self.TRACK[0]
        fraction = self.STRIP[2] - self.STRIP[0]
        thumb_width = track_width * fraction / (fraction + self.max_scroll)
        start = self.TRACK[0] + (track_width - thumb_width) * (self.scroll / self.max_scroll if self.max_scroll else 0)
        draw.rectangle(bounds((start, self.TRACK[1] + 1, start + thumb_width, self.TRACK[3] - 1)), fill='#999076')
        if len(self.text_cache) > 600:
            self.text_cache.clear()
        if len(self.image_cache) > 60:
            self.image_cache.clear()
        if len(self.card_cache) > 90:
            self.card_cache.clear()
        return image
