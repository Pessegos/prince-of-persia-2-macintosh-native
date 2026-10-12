"""The original COPY page/symbol challenge, independent of the desert puzzle."""

import random
import math
import struct

from PIL import Image, ImageDraw

from pop2.intro import SIZE, indexed_shape, MAC_TICKS_PER_SECOND
from pop2.render_opening import decode_ctbl, decode_shap
from pop2.game_ui import MacintoshFont


class CopyProtection:
    def __init__(self, resources, rng=None):
        self.rng = rng or random.Random()
        data = resources['COPY'][8005]['data']
        count = struct.unpack_from('>H', data)[0]
        if len(data) != 2 + count * 4 or count < 2:
            raise ValueError('Invalid COPY challenge table')
        self.answers = tuple(struct.iter_unpack('>2H', data[2:]))
        if any(not 1 <= page <= 19 or not 0 <= symbol < 10 for page, symbol in self.answers):
            raise ValueError('Invalid COPY page or symbol')
        self.message = resources['TEXT'][8005]['data'][1:].split(b'\0')[0].decode('mac_roman')
        palette = decode_ctbl(resources['CTBL'][8000]['data'])
        self.palette = palette
        self.font = MacintoshFont(resources['NFNT'][24878]['data'])
        self.symbols = tuple(decode_shap(resources['SHAP'][8005 + i]['data'], palette) for i in range(10))
        border = Image.new('L', SIZE, 25)
        horizontal = indexed_shape(resources['SHAP'][8001]['data'])
        vertical = indexed_shape(resources['SHAP'][8000]['data'], allow_trailing=True)
        border.paste(horizontal, (vertical.width, 0))
        border.paste(horizontal.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
                     (vertical.width, SIZE[1] - horizontal.height))
        border.paste(vertical, (0, 0))
        border.paste(vertical.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (510 - vertical.width, 0))
        indexed_border = border.convert('P')
        indexed_border.putpalette(bytes(channel for index in range(256)
                                        for channel in palette.get(index, (0, 0, 0, 255))[:3]))
        self.border = indexed_border.convert('RGBA')
        self.attempts = 0
        self.focus = None
        self.accepted = False
        self.failed = False
        self.challenge = self.rng.randrange(count)
        # DialogFadeIn/Out 2:0774/07ee use flags 0x40001: 4% per VBL tick.
        self.fade = 'in'
        self.fade_time = 0.0

    @property
    def input_ready(self):
        return self.fade == 'ready'

    @property
    def closed(self):
        return self.fade == 'closed'

    def advance(self, interval):
        if self.fade not in ('in', 'out'):
            return
        self.fade_time += max(0, interval)
        if self.fade_time * MAC_TICKS_PER_SECOND >= 25:
            self.fade = 'ready' if self.fade == 'in' else 'closed'

    @property
    def brightness(self):
        if self.fade == 'ready':
            return 1.0
        if self.fade == 'closed':
            return 0.0
        percent = min(100, math.floor(self.fade_time * MAC_TICKS_PER_SECOND + 1e-9) * 4)
        return (percent if self.fade == 'in' else 100 - percent) / 100

    def choose(self, symbol):
        if self.accepted or self.failed:
            return
        if symbol == self.answers[self.challenge][1]:
            self.accepted = True
            self.fade, self.fade_time = 'out', 0.0
        else:
            self.focus = None
            self.attempts += 1
            if self.attempts == 3:
                self.failed = True
                self.fade, self.fade_time = 'out', 0.0
            else:
                previous = self.challenge
                self.challenge = (previous + 1 + self.rng.randrange(len(self.answers) - 1)) % len(self.answers)

    @staticmethod
    def rectangle(index):
        # ComputeSymbolRect 2:1c10/1c6e: five columns, 76-pixel pitch.
        x, y = 80 + index % 5 * 76, 131 + index // 5 * 76
        return x - 5, y - 5, x + 55, y + 55

    def hit(self, x, y):
        return next((i for i in range(10) if self.rectangle(i)[0] <= x < self.rectangle(i)[2]
                     and self.rectangle(i)[1] <= y < self.rectangle(i)[3]), None)

    def draw(self, viewport, font):
        image = self.border.copy()
        draw = ImageDraw.Draw(image)
        draw.rectangle((13, 13, 496, 370), outline=(0, 0, 0, 255), width=1)
        words = (self.message % self.answers[self.challenge][0]).split()
        lines = ['']
        for word in words:
            candidate = (lines[-1] + ' ' + word).strip()
            if self.font.text(candidate).width > 400 and lines[-1]:
                lines.append(word)
            else:
                lines[-1] = candidate
        for row, line in enumerate(lines):
            text_x = (SIZE[0] - self.font.text(line).width) // 2
            # DialogDrawStr uses three horizontal origins on the same baseline.
            for offset_x, color in ((3, (0, 0, 0, 255)), (1, self.palette[16]), (0, self.palette[27])):
                text = self.font.text(line, color)
                image.paste(text, (text_x + offset_x, 50 + row * 24), text)
        for i, sprite in enumerate(self.symbols):
            x, y = 80 + i % 5 * 76, 131 + i // 5 * 76
            image.paste(sprite, (x, y), sprite)
        if self.focus is not None:
            left, top, right, bottom = self.rectangle(self.focus)
            # DrawSymbolBox uses palette color 27; QuickDraw Rect excludes right/bottom.
            draw.rectangle((left, top, right - 1, bottom - 1),
                           outline=self.palette[27], width=1)
        brightness = self.brightness if hasattr(self, 'fade') else 1.0
        if brightness != 1:
            colors = [round(value * brightness) for value in range(256)]
            image = image.convert('RGB').point(colors * 3).convert('RGBA')
        return image
