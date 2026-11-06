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

    PANEL = (8, 24, 504, 355)
    STRIP = (26, 102, 486, 237)
    TRACK = (34, 249, 478, 260)
    PREVIOUS = (9, 146, 25, 185)
    NEXT = (487, 146, 503, 185)
    BACK = (32, 310, 146, 340)
    PLAY = (158, 310, 284, 340)
    PITCH = 78
    CARD_WIDTH = 70
    COLUMNS = 6

    @property
    def chapter(self):
        return self.chapters[self.index]

    @property
    def unlocked(self):
        return self.chapter.key in self.collection.seen

    @property
    def max_scroll(self):
        return max(0, (len(self.chapters) - self.COLUMNS) * self.PITCH)

    @property
    def first(self):
        return max(0, int(self.scroll // self.PITCH))

    @property
    def visible(self):
        # Include clipped edge cards while moving; there are six at rest.
        return range(self.first, min(len(self.chapters), math.ceil(self.scroll / self.PITCH) + self.COLUMNS))

    def card_rect(self, index):
        x = self.STRIP[0] + index * self.PITCH - self.scroll
        return x, 105, x + self.CARD_WIDTH, 234

    @staticmethod
    def contains(rect, x, y):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]

    def move(self, delta):
        self.index = max(0, min(len(self.chapters) - 1, self.index + delta))
        left = self.index * self.PITCH
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
        if key in ('Left', 'Right'):
            return self.move(-1 if key == 'Left' else 1)
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

    def draw(self, viewport, font, *, visible=False, background_key=None):
        sx, sy = viewport.width / (510 if visible else 512), viewport.height / 384
        ox = int(visible)
        key = viewport.size, background_key or id(viewport)
        if self.background_cache is None or self.background_cache[0] != key:
            base = Image.alpha_composite(viewport.convert('RGBA'), Image.new('RGBA', viewport.size, (0, 0, 0, 145)))
            self.background_cache = key, base
        image = self.background_cache[1].copy()
        draw = ImageDraw.Draw(image)
        gold, white, muted = '#f4d873', '#eeeeee', '#999999'
        line_width = max(1, round(min(sx, sy)))

        def point(x, y):
            return round((x - ox) * sx), round(y * sy)

        def rect_box(rect):
            return *point(*rect[:2]), *point(*rect[2:])

        def box(rect, fill, outline=None, selected=False):
            draw.rectangle(rect_box(rect), fill=fill, outline=outline, width=line_width * (2 if selected else 1))

        def glyph(value, color):
            key = id(font), value, color
            if key not in self.text_cache:
                self.text_cache[key] = font.text(value, color)
            return self.text_cache[key]

        def caption(value, rect, color=white, scale=.7):
            lines, line = [], ''
            for word in value.split():
                candidate = f'{line} {word}'.strip()
                if line and glyph(candidate, color).width * scale > rect[2] - rect[0] - 4:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                lines.append(line)
            if not lines:
                return
            raw = [glyph(line, color) for line in lines]
            scale = min(scale, (rect[2] - rect[0] - 4) / max(g.width for g in raw),
                        (rect[3] - rect[1] - 2) / (len(raw) * font.height))
            height = font.height * scale
            y = (rect[1] + rect[3] - len(raw) * height) / 2
            for line, g in zip(lines, raw):
                cache_key = id(font), line, color, round(scale * sx, 4), round(scale * sy, 4)
                if cache_key not in self.text_cache:
                    # Scale the original glyph once, directly to device pixels.
                    self.text_cache[cache_key] = g.resize((max(1, round(g.width * scale * sx)),
                        max(1, round(g.height * scale * sy))), Image.Resampling.NEAREST)
                g = self.text_cache[cache_key]
                x = round(((rect[0] + rect[2]) / 2 - ox) * sx - g.width / 2)
                image.alpha_composite(g, (x, round(y * sy)))
                y += height

        box(self.PANEL, '#181818', '#858585')
        caption('Cutscene Viewer', (30, 37, 482, 67), gold, 1)
        count = sum(chapter.key in self.collection.seen for chapter in self.chapters)
        caption(f'{count} / {len(self.chapters)} chapters unlocked', (30, 73, 482, 91), muted, .6)
        # Draw the shelf to a temporary surface and clip its moving edges.
        shelf_base = image.copy()
        for index in self.visible:
            chapter, rect = self.chapters[index], self.card_rect(index)
            selected = self.index == index
            outline = gold if selected else '#b8b8b8' if self.hovered == 100 + index else '#626262'
            box(rect, '#252525', outline, selected)
            thumb = rect[0] + 2, rect[1] + 2, rect[2] - 2, rect[1] + 52
            unlocked = chapter.key in self.collection.seen
            if unlocked and chapter_available(chapter):
                try:
                    bounds = rect_box(thumb)
                    size = bounds[2] - bounds[0], bounds[3] - bounds[1]
                    key = index, size
                    if key not in self.image_cache:
                        frame = self.preview(index)
                        self.image_cache[key] = frame.convert('RGBA').resize(size, Image.Resampling.LANCZOS
                            if size[0] < frame.width else Image.Resampling.NEAREST)
                    image.alpha_composite(self.image_cache[key], bounds[:2])
                except (OSError, ValueError, KeyError, RuntimeError):
                    caption('Unavailable', thumb, muted, .5)
            else:
                box(thumb, '#101010')
                cx, cy = (thumb[0] + thumb[2]) / 2, (thumb[1] + thumb[3]) / 2
                draw.arc(rect_box((cx - 5, cy - 11, cx + 5, cy + 3)), 180, 360, fill=muted, width=line_width)
                box((cx - 8, cy - 2, cx + 8, cy + 10), '#101010', muted)
            label = chapter.title if unlocked else f'Chapter {index + 1}\nLocked'
            caption(label, (rect[0] + 2, rect[1] + 58, rect[2] - 2, rect[3] - 15),
                    gold if selected else white, .62)
            caption(str(index + 1), (rect[0], rect[3] - 18, rect[2], rect[3] - 2), muted, .5)
        bounds = rect_box(self.STRIP)
        shelf_base.paste(image.crop(bounds), bounds[:2])
        image = shelf_base
        draw = ImageDraw.Draw(image)
        for rect, direction, enabled in ((self.PREVIOUS, -1, self.scroll_target > 0),
                                         (self.NEXT, 1, self.scroll_target < self.max_scroll)):
            x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            draw.line((point(x - direction * 3, y - 6), point(x + direction * 3, y),
                       point(x - direction * 3, y + 6)), fill=gold if enabled else '#505050', width=line_width)
        box(self.TRACK, '#282828')
        width = self.TRACK[2] - self.TRACK[0]
        thumb_width = width * min(1, self.COLUMNS / len(self.chapters))
        left = self.TRACK[0] + (width - thumb_width) * (self.scroll / self.max_scroll if self.max_scroll else 0)
        box((left, self.TRACK[1] + 3, left + thumb_width, self.TRACK[3] - 3), '#777777')
        message = self.error or self.collection.error
        if not message:
            message = 'Continue the story to unlock this chapter.' if not self.unlocked else 'Scroll or drag to browse. Left/Right to select.'
        selected = self.chapter.title if self.unlocked else f'Chapter {self.index + 1} - Locked'
        caption(selected, (28, 265, 484, 283), gold, .7)
        caption(message, (28, 286, 484, 303), '#ff9b9b' if self.error else muted, .5)
        for code, rect, label in ((2, self.BACK, 'Back'), (1, self.PLAY, 'Play')):
            box(rect, '#303030' if self.focus == code else '#222222',
                gold if self.focus == code or self.hovered == code else '#626262')
            caption(label, rect, white if code == 2 or self.unlocked else '#666666')
        caption(f'{self.index + 1} / {len(self.chapters)}', (312, 310, 480, 340), muted)
        # Size changes should not retain unlimited resampled text/thumbnails.
        if len(self.text_cache) > 600:
            self.text_cache.clear()
        if len(self.image_cache) > 60:
            self.image_cache.clear()
        return image
