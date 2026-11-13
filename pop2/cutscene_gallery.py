"""A device-resolution story shelf with continuous horizontal scrolling."""

import math
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageOps

from pop2 import menu_theme
from pop2.cutscenes import CHAPTERS, chapter_available
from pop2.menu_theme import c
from pop2.menu_animation import spring_step


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
    scroll_velocity: float = 0
    bounce: float = 0
    edge_target: float = 0
    drag: tuple | None = None
    dragged: bool = False
    last_clicked: int | None = None
    developer: bool = False
    text_cache: dict = field(default_factory=dict, repr=False)
    image_cache: dict = field(default_factory=dict, repr=False)
    background_cache: tuple | None = field(default=None, repr=False)
    grid_cache: tuple | None = field(default=None, repr=False)
    card_cache: dict = field(default_factory=dict, repr=False)
    layout_size: tuple | None = field(default=None, repr=False)
    # Chapters unlocked since the viewer was last open, as index -> seconds
    # into their reveal (negative while it waits to start).
    reveal: dict = field(default_factory=dict, repr=False)

    PANEL = (8, 10, 504, 363)
    STRIP = (20, 61, 492, 334)
    TRACK = (24, 342, 488, 348)
    PREVIOUS = (8, 175, 20, 211)
    NEXT = (492, 175, 504, 211)
    PITCH = 160
    CARD_WIDTH = 150
    CARD_HEIGHT = 104.125
    COLUMNS = 3
    ROWS = 2
    GRID_PADDING = 48
    BOUNCE_LIMIT = 40
    # A locked chapter shows its own cover as a few large dark blocks: its
    # colours, nothing that can be recognised. Unlocking refines the blocks
    # step by step until the cover is whole, like a console's mosaic fade.
    VEIL_COLUMNS = 9
    VEIL_DEPTH = .6
    REVEAL_COLUMNS = (12, 16, 22, 30, 42, 58, 80, 110)
    REVEAL_STEP = .11
    REVEAL_DELAY = .6

    def layout(self, size, *, visible=False):
        """Uniform UI scale; extra width changes layout rather than stretching it."""
        logical_width = size[0] * 384 / size[1] + (2 if visible else 0)
        theme = menu_theme.current()
        if self.layout_size == (logical_width, theme.name):
            return
        scroll, target = self.scroll / self.PITCH, self.scroll_target / self.PITCH
        self.layout_size = logical_width, theme.name
        # A theme's frame stands outside the panel: leave it room at the sides
        # and below, where the plain page only has a thin outline.
        edge = max(8, theme.frame_width + 2) if theme.frame else 8
        self.PANEL = (edge, 10, logical_width - edge, 368 if theme.frame else 363)
        self.STRIP = (edge + 12, 61, logical_width - edge - 12, 334)
        self.TRACK = (edge + 16, 342, logical_width - edge - 16, 348)
        self.PREVIOUS = (edge, 175, edge + 12, 211)
        self.NEXT = (logical_width - edge - 12, 175, logical_width - edge, 211)
        available = self.STRIP[2] - self.STRIP[0] - 2
        row_height = (self.STRIP[3] - self.STRIP[1] - 12) / self.ROWS
        maximum_width = (row_height - 22) * 16 / 9 + 4
        self.COLUMNS = max(3, int((available + 10) // (maximum_width + 10)))
        self.CARD_WIDTH = min(maximum_width, (available - (self.COLUMNS - 1) * 10) / self.COLUMNS)
        self.CARD_HEIGHT = (self.CARD_WIDTH - 4) * 9 / 16 + 22
        self.PITCH = (available - self.CARD_WIDTH) / (self.COLUMNS - 1)
        self.scroll = max(0, min(self.max_scroll, scroll * self.PITCH))
        self.scroll_target = max(0, min(self.max_scroll, target * self.PITCH))
        self.scroll_velocity = self.bounce = self.edge_target = 0
        self.drag = None
        self.dragged = False
        self.hovered = None
        self.last_clicked = None
        self.background_cache = self.grid_cache = None
        self.card_cache.clear()
        self.image_cache.clear()

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
        return self.chapter_unlocked(self.index)

    def chapter_unlocked(self, index):
        return self.developer or self.chapters[index].key in self.collection.seen

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
        x = self.STRIP[0] + 1 + column * self.PITCH - (self.display_scroll if offset is None else offset)
        grid_height = self.ROWS * self.CARD_HEIGHT + 10 * (self.ROWS - 1)
        y = (self.STRIP[1] + self.STRIP[3] - grid_height) / 2 + row * (self.CARD_HEIGHT + 10)
        return x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT

    @staticmethod
    def contains(rect, x, y):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]

    def move(self, delta):
        self.last_clicked = None
        self.edge_target = 0
        self.index = max(0, min(len(self.chapters) - 1, self.index + delta))
        left = self.cell(self.index)[0] * self.PITCH
        self.scroll_target = max(left - (self.COLUMNS - 1) * self.PITCH, min(self.scroll_target, left))
        self.scroll_target = max(0, min(self.max_scroll, self.scroll_target))
        self.focus = 0
        self.error = ''
        return 'changed'

    def wheel(self, steps):
        self.last_clicked = None
        self.edge_target = 0
        # Scrolling moves the shelf, not the selected chapter. Preserve partial
        # wheel deltas from touchpads rather than snapping to cards/pages.
        desired = self.scroll_target + steps * self.PITCH * .55
        self.scroll_target = max(0, min(self.max_scroll, desired))
        if self.max_scroll and desired != self.scroll_target:
            direction = 1 if desired > self.max_scroll else -1
            self.edge_target = direction * min(28, abs(steps) * 24)
            if abs(self.display_scroll - self.scroll_target) < .5:
                self.scroll_velocity = direction * max(110, direction * self.scroll_velocity)

    @property
    def display_scroll(self):
        return self.scroll + self.bounce

    def reveal_step(self, index):
        """None for a settled card, -1 while a reveal waits, then the step it has reached."""
        elapsed = self.reveal.get(index)
        if elapsed is None:
            return None
        return -1 if elapsed < 0 else min(len(self.REVEAL_COLUMNS) - 1, int(elapsed / self.REVEAL_STEP))

    @property
    def reveal_state(self):
        return tuple(sorted((index, self.reveal_step(index)) for index in self.reveal))

    def begin_reveal(self, indices):
        """Show these newly unlocked chapters resolving out of their veil, the first one selected."""
        indices = sorted(index for index in indices if self.chapter_unlocked(index))
        if not indices:
            return
        self.reveal = {index: -self.REVEAL_DELAY - order * self.REVEAL_STEP * 3 for order, index in enumerate(indices)}
        self.index = indices[0]
        self.move(0)
        self.scroll = self.scroll_target

    def advance(self, seconds):
        for index in tuple(self.reveal):
            self.reveal[index] += seconds
            if self.reveal[index] >= len(self.REVEAL_COLUMNS) * self.REVEAL_STEP:
                del self.reveal[index]
        return self.advance_scroll(seconds) or bool(self.reveal)

    def advance_scroll(self, seconds):
        if self.drag is not None:
            return False
        # A single position and velocity carry the shelf through the edge.
        # Waiting for a clamped scroll to settle before a second kick felt late.
        frequency = 14 if self.edge_target else 10 if self.bounce else 24
        position, self.scroll_velocity = spring_step(
            self.display_scroll, self.scroll_velocity, self.scroll_target + self.edge_target,
            seconds, frequency=frequency)
        if (self.edge_target and
                (position - self.scroll_target) / self.edge_target >= .6):
            self.edge_target = 0
        bounded = max(-self.BOUNCE_LIMIT, min(self.max_scroll + self.BOUNCE_LIMIT, position))
        if bounded != position:
            self.scroll_velocity = 0
        if not self.edge_target and abs(bounded - self.scroll_target) < .02 and abs(self.scroll_velocity) < .5:
            bounded, self.scroll_velocity = self.scroll_target, 0
        self.scroll = max(0, min(self.max_scroll, bounded))
        self.bounce = bounded - self.scroll
        return bool(bounded != self.scroll_target or self.scroll_velocity or self.edge_target)

    def begin_drag(self, x, y):
        if not self.contains(self.STRIP, x, y):
            return False
        self.drag = (x, self.display_scroll)
        self.dragged = False
        self.scroll_target = self.scroll
        self.scroll_velocity = self.edge_target = 0
        return True

    def move_drag(self, x):
        if self.drag is None:
            return False
        start, scroll = self.drag
        if abs(x - start) > 2:
            self.dragged = True
        if self.dragged:
            self.last_clicked = None
            desired = scroll + start - x
            self.scroll = self.scroll_target = max(0, min(self.max_scroll, desired))
            excess = desired - self.scroll
            self.bounce = excess * .4 / (1 + abs(excess) / (2.5 * self.BOUNCE_LIMIT)) if self.max_scroll else 0
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
        return 'cutscene_play' if self.unlocked else 'changed'

    def double_click(self, x, y):
        target = self.hit(x, y)
        if (target is not None and target >= 100 and self.drag is None
                and self.last_clicked == target - 100):
            self.index = target - 100
            self.last_clicked = None
            return self.activate()
        return self.click(x, y)

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
            return self.move(-1 if backwards else 1)
        elif key in ('Return', 'KP_Enter', 'space'):
            return self.activate()
        return 'changed'

    def hit(self, x, y):
        for code, rect in ((3, self.PREVIOUS), (4, self.NEXT), (5, self.TRACK)):
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
            self.last_clicked = None
            return 'changed'
        if target >= 100:
            self.index = target - 100
            self.last_clicked = self.index
            self.focus = 0
            self.error = ''
            return 'changed'
        if target in (3, 4):
            self.wheel(-1 if target == 3 else 1)
            return 'changed'
        if target == 5:
            self.last_clicked = None
            self.edge_target = 0
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
        selected = self.index == index
        unlocked = self.chapter_unlocked(index)
        size = round(self.CARD_WIDTH * sx), round(self.CARD_HEIGHT * sy)
        step = self.reveal_step(index) if unlocked else None
        key = index, id(font), size, selected, unlocked, menu_theme.current().name, step
        if key in self.card_cache:
            return self.card_cache[key]
        image = Image.new('RGBA', size, c('#252525'))
        draw = ImageDraw.Draw(image)
        stroke = max(1, round(min(sx, sy)))
        outline = c('#f4d873') if selected else c('#626262')
        draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=outline, width=stroke * (2 if selected else 1))
        thumb_bottom = 2 + (self.CARD_WIDTH - 4) * 9 / 16
        thumb_rect = (2, 2, self.CARD_WIDTH - 2, thumb_bottom)
        thumb = tuple(round(value * (sx if i % 2 == 0 else sy)) for i, value in enumerate(thumb_rect))
        cover = None
        if chapter_available(chapter):
            try:
                thumb_size = thumb[2] - thumb[0], thumb[3] - thumb[1]
                image_key = index, thumb_size
                if image_key not in self.image_cache:
                    frame = self.preview(index)
                    self.image_cache[image_key] = ImageOps.fit(frame.convert('RGBA'), thumb_size,
                        method=Image.Resampling.LANCZOS if thumb_size[0] < frame.width else Image.Resampling.NEAREST)
                cover = self.image_cache[image_key]
            except (OSError, ValueError, KeyError, RuntimeError):
                cover = None
        veiled = not unlocked or step is not None
        if cover is None:
            if unlocked:
                self.caption(image, font, 'Unavailable', thumb_rect, c('#999999'), .7, sx, sy)
            else:
                draw.rectangle(thumb, fill=c('#101010'))
        elif veiled:
            # Locked, or resolving after being unlocked: large blocks of the cover's own colours.
            stage = 0 if step is None else step + 1
            columns = (self.VEIL_COLUMNS, *self.REVEAL_COLUMNS)[stage]
            blocks = cover.convert('RGB').resize(
                (columns, max(1, round(columns * cover.height / cover.width))), Image.Resampling.BOX)
            depth = self.VEIL_DEPTH * (1 - stage / (len(self.REVEAL_COLUMNS) + 1))
            blocks = Image.blend(blocks, Image.new('RGB', blocks.size, c('#101010')), depth)
            image.paste(blocks.resize(cover.size, Image.Resampling.NEAREST), thumb[:2])
        else:
            image.alpha_composite(cover, thumb[:2])
        band = c('#493c25') if selected else c('#252525')
        draw.rectangle((stroke, round((thumb_bottom + 1) * sy), size[0] - stroke - 1, size[1] - stroke - 1), fill=band)
        # The title arrives halfway through a reveal; a locked chapter never shows it.
        named = unlocked and (step is None or step >= len(self.REVEAL_COLUMNS) // 2)
        label = chapter.title if named else f'Chapter {index + 1}'
        self.caption(image, font, label, (2, thumb_bottom + 1, self.CARD_WIDTH - 2, self.CARD_HEIGHT - 1),
                     c('#f4d873') if selected else c('#eeeeee') if named else c('#999999'), .72, sx, sy)
        self.card_cache[key] = image
        return image

    def hover_border(self, scale):
        """Grid-relative pixels, shared by captures and the retained Tk overlay."""
        index = self.hovered - 100 if self.hovered is not None else -1
        if not 0 <= index < len(self.chapters) or index == self.index:
            return None
        rect = self.card_rect(index, offset=0)
        x = round((rect[0] - self.STRIP[0] + self.GRID_PADDING) * scale)
        y = round((rect[1] - self.STRIP[1]) * scale)
        width, height = round(self.CARD_WIDTH * scale), round(self.CARD_HEIGHT * scale)
        stroke = max(1, round(scale))
        return ((x, y, x + width, y + stroke), (x, y + height - stroke, x + width, y + height),
                (x, y, x + stroke, y + height), (x + width - stroke, y, x + width, y + height))

    def draw(self, viewport, font, *, visible=False, background_key=None):
        self.layout(viewport.size, visible=visible)
        sx = sy = viewport.height / 384
        ox = int(visible)
        stroke = max(1, round(min(sx, sy)))

        def point(x, y):
            return round((x - ox) * sx), round(y * sy)

        def bounds(rect):
            return *point(*rect[:2]), *point(*rect[2:])

        # The moving region and static frame are composed once per UI state.
        # Animation only crops/pastes the cached grid and updates its scrollbar;
        # there is no font drawing, asset IO or thumbnail resampling per frame.
        theme = menu_theme.current()
        key = (viewport.size, visible, background_key or id(viewport), id(font), self.unlocked, self.developer,
               self.focus, self.hovered if self.hovered in (1, 2) else None, self.error, self.collection.error,
               theme.name)
        if self.background_cache is None or self.background_cache[0] != key:
            base = Image.alpha_composite(viewport.convert('RGBA'), Image.new(
                'RGBA', viewport.size, (0, 0, 0, max(145, theme.dim) if theme.frame else 145)))
            draw = ImageDraw.Draw(base)
            limit = (ox, 0, math.floor(viewport.width / sx) + ox - 1, 383)
            if not menu_theme.panel_scaled(base, tuple(round(value) for value in self.PANEL), point, limit):
                draw.rectangle(bounds(self.PANEL), fill=c('#181818'), outline=c('#8c7954'), width=stroke)
            title = 'Cutscene Viewer - Dev Tools' if self.developer else 'Cutscene Viewer'
            self.caption(base, font, title,
                         (self.STRIP[0] - ox, 19, self.STRIP[2] - ox, 51), c('#f4d873'), 1, sx, sy)
            message = self.error or self.collection.error or (
                'Continue the story to unlock this chapter.' if not self.unlocked else '')
            self.caption(base, font, message, (self.TRACK[0] - ox, 350, self.TRACK[2] - ox, 362),
                         c('#ff9b9b') if self.error else c('#999999'), .45, sx, sy)
            self.background_cache = key, base.convert('RGB')
        image = self.background_cache[1].copy()
        region = bounds(self.STRIP)
        width, height = region[2] - region[0], region[3] - region[1]
        grid_key = (viewport.size, visible, id(font), self.index,
                    tuple(sorted(self.collection.seen)), self.chapters, self.developer, theme.name,
                    self.reveal_state)
        if self.grid_cache is None or self.grid_cache[0] != grid_key:
            grid = Image.new('RGBA', (width + round((self.max_scroll + 2 * self.GRID_PADDING) * sx), height), c('#181818'))
            for index in range(len(self.chapters)):
                rect = self.card_rect(index, offset=0)
                card = self.card_image(index, font, sx, sy)
                grid.alpha_composite(card, (round((rect[0] - self.STRIP[0] + self.GRID_PADDING) * sx),
                                             round((rect[1] - self.STRIP[1]) * sy)))
            self.grid_cache = grid_key, grid.convert('RGB')
        left = round(self.display_scroll * sx) + round(self.GRID_PADDING * sx)
        strip = self.grid_cache[1].crop((left, 0, left + width, height))
        if border := self.hover_border(sx):
            draw = ImageDraw.Draw(strip)
            for x1, y1, x2, y2 in border:
                draw.rectangle((x1 - left, y1, x2 - left - 1, y2 - 1), fill=c('#c6b58c'))
        image.paste(strip, region[:2])
        self.draw_scroll_controls(image, sx, sy, ox=ox)
        if len(self.text_cache) > 600:
            self.text_cache.clear()
        if len(self.image_cache) > 60:
            self.image_cache.clear()
        if len(self.card_cache) > 90:
            self.card_cache.clear()
        return image

    def draw_scroll_controls(self, image, sx, sy, *, ox=0, origin=(0, 0)):
        """Also draw directly into small retained-photo patches during motion."""
        def point(x, y):
            return round((x - ox) * sx) - origin[0], round(y * sy) - origin[1]

        def bounds(rect):
            return *point(*rect[:2]), *point(*rect[2:])

        draw = ImageDraw.Draw(image)
        stroke = max(1, round(min(sx, sy)))
        for rect, direction, enabled in ((self.PREVIOUS, -1, self.scroll_target > 0),
                                         (self.NEXT, 1, self.scroll_target < self.max_scroll)):
            x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            draw.line((point(x - direction * 2, y - 5), point(x + direction * 2, y),
                       point(x - direction * 2, y + 5)), fill=c('#f4d873') if enabled else c('#505050'), width=stroke)
        draw.rectangle(bounds(self.TRACK), fill=c('#282828'))
        track_width = self.TRACK[2] - self.TRACK[0]
        fraction = self.STRIP[2] - self.STRIP[0]
        thumb_width = track_width * fraction / (fraction + self.max_scroll)
        start = self.TRACK[0] + (track_width - thumb_width) * (self.scroll / self.max_scroll if self.max_scroll else 0)
        draw.rectangle(bounds((start, self.TRACK[1] + 1, start + thumb_width, self.TRACK[3] - 1)), fill=c('#999076'))
