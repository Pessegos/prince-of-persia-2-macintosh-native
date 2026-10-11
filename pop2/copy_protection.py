"""The original COPY page/symbol challenge, independent of the desert puzzle."""

import random
import struct

from PIL import ImageDraw

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
        self.attempts = 0
        self.focus = 0
        self.accepted = False
        self.failed = False
        self.challenge = self.rng.randrange(count)

    def choose(self, symbol):
        if self.accepted or self.failed:
            return
        if symbol == self.answers[self.challenge][1]:
            self.accepted = True
        else:
            self.attempts += 1
            if self.attempts == 3:
                self.failed = True
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

    def key(self, key):
        if key in ('Left', 'Right', 'Up', 'Down'):
            self.focus = (self.focus + {'Left': -1, 'Right': 1, 'Up': -5, 'Down': 5}[key]) % 10
        elif key in ('Return', 'KP_Enter', 'space'):
            self.choose(self.focus)

    def draw(self, viewport, font):
        image = viewport.copy()
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 511, 383), fill=self.palette[25])
        words = (self.message % self.answers[self.challenge][0]).split()
        lines = ['']
        for word in words:
            candidate = (lines[-1] + ' ' + word).strip()
            if self.font.text(candidate).width > 400 and lines[-1]:
                lines.append(word)
            else:
                lines[-1] = candidate
        for row, line in enumerate(lines):
            for offset, color in ((3, (0, 0, 0, 255)), (1, self.palette[16]), (0, self.palette[27])):
                text = self.font.text(line, color)
                image.paste(text, (55 + offset, 40 + row * 24 + offset), text)
        for i, sprite in enumerate(self.symbols):
            x, y = 80 + i % 5 * 76, 131 + i // 5 * 76
            image.paste(sprite, (x, y), sprite)
        draw.rectangle(self.rectangle(self.focus), outline=(255, 255, 0, 255), width=1)
        return image
