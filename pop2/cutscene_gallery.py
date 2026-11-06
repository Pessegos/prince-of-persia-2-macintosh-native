"""A horizontal collection of whole story chapters, without spoiler previews."""

from dataclasses import dataclass

from PIL import Image, ImageDraw

from pop2.cutscenes import CHAPTERS, chapter_available
from pop2.playback_preview import gallery_caption


@dataclass
class CutsceneGallery:
    collection: object
    preview: object
    index: int = 0
    focus: int = 0
    hovered: int | None = None
    error: str = ''
    chapters: tuple = CHAPTERS

    PANEL = (12, 32, 500, 338)
    PREVIOUS = (17, 145, 35, 183)
    NEXT = (477, 145, 495, 183)
    BACK = (40, 292, 164, 322)
    PLAY = (186, 292, 326, 322)

    @property
    def chapter(self):
        return self.chapters[self.index]

    @property
    def unlocked(self):
        return self.chapter.key in self.collection.seen

    @property
    def first(self):
        return max(0, min(self.index - 1, len(self.chapters) - 3))

    @property
    def visible(self):
        return range(self.first, min(self.first + 3, len(self.chapters)))

    def card_rect(self, index):
        x = 41 + (index - self.first) * 150
        return x, 105, x + 130, 246

    @staticmethod
    def contains(rect, x, y):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]

    def move(self, delta):
        self.index = max(0, min(len(self.chapters) - 1, self.index + delta))
        self.focus = 0
        self.error = ''
        return 'changed'

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
        for code, rect in ((3, self.PREVIOUS), (4, self.NEXT), (2, self.BACK), (1, self.PLAY)):
            if self.contains(rect, x, y):
                return code
        return next((100 + index for index in self.visible
                     if self.contains(self.card_rect(index), x, y)), None)

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
            return self.move(-1 if target == 3 else 1)
        self.focus = target
        return self.activate()

    def draw(self, viewport, font):
        image = Image.alpha_composite(viewport.convert('RGBA'), Image.new('RGBA', viewport.size, (0, 0, 0, 120)))
        draw = ImageDraw.Draw(image)
        gold, white, muted = '#f4d873', '#eeeeee', '#999999'
        draw.rectangle(self.PANEL, fill='#181818', outline='#858585')

        def caption(value, rect, color=white, scale=.8):
            glyphs = gallery_caption(font, value, (rect[2] - rect[0], rect[3] - rect[1]), color, scale)
            image.alpha_composite(glyphs, rect[:2])

        caption('Cutscene Viewer', (50, 45, 462, 76), gold, 1)
        for index in self.visible:
            chapter = self.chapters[index]
            rect = self.card_rect(index)
            selected = self.index == index
            outline = gold if selected else '#b8b8b8' if self.hovered == 100 + index else '#626262'
            draw.rectangle(rect, fill='#252525', outline=outline, width=2 if selected else 1)
            thumb = rect[0] + 3, rect[1] + 3, rect[2] - 3, rect[1] + 98
            unlocked = chapter.key in self.collection.seen
            if unlocked and chapter_available(chapter):
                try:
                    frame = self.preview(index).resize((thumb[2] - thumb[0], thumb[3] - thumb[1]), Image.Resampling.LANCZOS)
                    image.paste(frame.convert('RGBA'), thumb[:2])
                except (OSError, ValueError, KeyError, RuntimeError):
                    caption('Preview unavailable', thumb, muted)
            else:
                draw.rectangle(thumb, fill='#101010')
                cx, cy = (thumb[0] + thumb[2]) // 2, (thumb[1] + thumb[3]) // 2
                draw.arc((cx - 9, cy - 18, cx + 9, cy + 4), 180, 360, fill=muted, width=2)
                draw.rectangle((cx - 13, cy - 7, cx + 13, cy + 13), outline=muted, width=2)
                draw.line((cx, cy, cx, cy + 6), fill=muted, width=2)
            # Locked names and pictures are never requested from the provider.
            label = chapter.title if unlocked else f'Chapter {index + 1} - Locked'
            caption(label, (rect[0] + 2, rect[1] + 102, rect[2] - 2, rect[3] - 2), gold if selected else white, .72)
        for rect, direction, enabled in ((self.PREVIOUS, -1, self.index > 0),
                                         (self.NEXT, 1, self.index + 1 < len(self.chapters))):
            x, y = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
            draw.line(((x - direction * 3, y - 7), (x + direction * 3, y),
                       (x - direction * 3, y + 7)), fill=gold if enabled else '#505050', width=2)
        message = self.error or self.collection.error
        if not message and not self.unlocked:
            message = 'Continue the story to unlock this chapter.'
        elif not message and not chapter_available(self.chapter):
            message = 'This cutscene needs to be imported.'
        elif not message:
            message = 'Left/Right or scroll to browse.'
        caption(message, (36, 255, 476, 280), '#ff9b9b' if self.error else muted, .7)
        for code, rect, label in ((2, self.BACK, 'Back'), (1, self.PLAY, 'Play')):
            enabled = code == 2 or self.unlocked
            draw.rectangle(rect, fill='#303030' if self.focus == code else '#222222',
                           outline=gold if self.focus == code or self.hovered == code else '#626262')
            caption(label, rect, white if enabled else '#666666')
        caption(f'{self.index + 1} / {len(self.chapters)}', (340, 291, 475, 322), muted)
        return image
