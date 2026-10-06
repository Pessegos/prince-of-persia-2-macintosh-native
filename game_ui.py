import struct
from dataclasses import dataclass

from PIL import Image, ImageDraw


def fit_viewport(width, height, native_width=512, native_height=384):
    scale = min(max(1, width) / native_width, max(1, height) / native_height)
    size = (max(1, int(native_width * scale)), max(1, int(native_height * scale)))
    return size, ((width - size[0]) // 2, (height - size[1]) // 2)


def viewport_point(x, y, width, height):
    size, origin = fit_viewport(width, height)
    if not (origin[0] <= x < origin[0] + size[0]
            and origin[1] <= y < origin[1] + size[1]):
        return None
    return ((x - origin[0]) * 512 / size[0], (y - origin[1]) * 384 / size[1])


@dataclass
class DevelopmentMenu:
    screens: tuple
    screen_index: int
    peaceful: bool
    focus: int = 0
    dropdown: bool = False
    option_index: int = 0
    error: str = ""

    CONTROLS = ((200, 138, 392, 166), (120, 180, 392, 210),
                (120, 231, 252, 263), (264, 231, 392, 263))
    PANEL = (100, 70, 412, 328)
    OPTION_HEIGHT = 19

    @property
    def screen(self):
        return self.screens[self.screen_index]

    def open_dropdown(self):
        self.dropdown = True
        self.option_index = self.screen_index

    def select(self, index):
        self.screen_index = index
        self.dropdown = False
        self.error = ""

    def key(self, key, backwards=False):
        if key == "Escape":
            if self.dropdown:
                self.dropdown = False
                return "changed"
            return "resume"
        if key == "Tab":
            self.dropdown = False
            self.focus = (self.focus + (-1 if backwards else 1)) % len(self.CONTROLS)
        elif self.dropdown:
            if key in ("Up", "Down", "Left", "Right"):
                delta = -1 if key in ("Up", "Left") else 1
                self.option_index = (self.option_index + delta) % len(self.screens)
            elif key in ("Return", "KP_Enter", "space"):
                self.select(self.option_index)
        elif key in ("Up", "Down"):
            self.focus = (self.focus + (-1 if key == "Up" else 1)) % len(self.CONTROLS)
        elif key in ("Left", "Right") and self.focus == 0:
            self.select((self.screen_index + (-1 if key == "Left" else 1)) % len(self.screens))
        elif key in ("Left", "Right") and self.focus in (2, 3):
            self.focus = 2 if key == "Left" else 3
        elif key in ("Return", "KP_Enter", "space"):
            return self.activate()
        return "changed"

    def activate(self):
        if self.focus == 0:
            self.open_dropdown()
        elif self.focus == 1:
            self.peaceful = not self.peaceful
            return "peaceful"
        else:
            return "go" if self.focus == 2 else "resume"
        return "changed"

    @staticmethod
    def contains(rect, x, y):
        left, top, right, bottom = rect
        return left <= x < right and top <= y < bottom

    def hit(self, x, y):
        if self.dropdown:
            left, _top, right, bottom = self.CONTROLS[0]
            popup = (left, bottom, right, bottom + len(self.screens) * self.OPTION_HEIGHT)
            if self.contains(popup, x, y):
                return int((y - bottom) // self.OPTION_HEIGHT)
            return None
        return next((i for i, rect in enumerate(self.CONTROLS)
                     if self.contains(rect, x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        if index is None:
            return False
        field = "option_index" if self.dropdown else "focus"
        changed = getattr(self, field) != index
        setattr(self, field, index)
        return changed

    def click(self, x, y):
        index = self.hit(x, y)
        if self.dropdown:
            if index is not None:
                self.select(index)
            else:
                self.dropdown = False
            return "changed"
        if index is None:
            return "changed"
        self.focus = index
        return self.activate()

    def draw(self, viewport, font):
        image = Image.alpha_composite(viewport, Image.new("RGBA", viewport.size, (0, 0, 0, 100)))
        draw = ImageDraw.Draw(image)
        gold, white, muted = "#f4d873", "#eeeeee", "#b9b9b9"
        draw.rectangle(self.PANEL, fill="#181818", outline="#858585")
        draw.line((120, 123, 392, 123), fill="#505050")

        def text(value, x, y, color=white, centered=False, max_width=None):
            glyphs = font.text(value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            ink = glyphs.getbbox()
            top = y - (ink[1] if ink else 0)
            image.paste(glyphs, (int(x - glyphs.width // 2) if centered else x, top), glyphs)

        text("Development", 256, 86, gold, centered=True)
        text("Level 1", 256, 108, muted, centered=True)
        text("Screen", 120, 146)
        for i, rect in enumerate(self.CONTROLS):
            draw.rectangle(rect, fill="#303030" if i == self.focus else "#222222",
                           outline=gold if i == self.focus else "#626262")
        text(self.screen, 210, 146, max_width=158)
        draw.polygon(((377, 150), (385, 150), (381, 154)), fill=white)
        draw.rectangle((130, 189, 141, 200), fill="#121212", outline=muted)
        if self.peaceful:
            draw.line(((132, 194), (135, 197), (139, 191)), fill=gold, width=2)
        text("Peaceful (no guards)", 151, 190, max_width=231)
        text("Go to screen", 186, 241, centered=True, max_width=118)
        text("Resume", 328, 241, centered=True)
        if self.error:
            words, line, lines = self.error.split(), "", []
            for word in words:
                candidate = (line + " " + word).strip()
                if line and font.text(candidate).width > 272:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
            for i, line in enumerate(lines[:3]):
                text(line, 120, 277 + i * 16, "#ff9b9b", max_width=272)
        if self.dropdown:
            left, _top, right, bottom = self.CONTROLS[0]
            draw.rectangle((left, bottom, right, bottom + len(self.screens) * self.OPTION_HEIGHT),
                           fill="#222222", outline=gold)
            for i, label in enumerate(self.screens):
                y = bottom + i * self.OPTION_HEIGHT
                if i == self.option_index:
                    draw.rectangle((left + 1, y + 1, right - 1, y + self.OPTION_HEIGHT - 1),
                                   fill="#454545")
                text(label, left + 10, y + 4, gold if i == self.screen_index else white)
        return image


class MacintoshFont:
    """Draw the game's NFNT bitmaps without substituting a Windows font."""

    def __init__(self, data):
        header = struct.unpack_from(">13h", data)
        self.first, self.last = header[1:3]
        self.height, self.ascent = header[7], header[9]
        row_bytes = header[12] * 2
        count = self.last - self.first + 2
        locations_at = 26 + row_bytes * self.height
        locations = struct.unpack_from(f">{count + 1}H", data, locations_at)
        widths_at = 16 + header[8] * 2
        self.glyphs = {}
        for index in range(count):
            offset, advance = struct.unpack_from(">BB", data, widths_at + index * 2)
            if (offset, advance) == (255, 255):
                continue
            left, right = locations[index:index + 2]
            mask = Image.new("L", (max(1, right - left), self.height))
            pixels = mask.load()
            for y in range(self.height):
                for x in range(right - left):
                    bit = left + x
                    if data[26 + y * row_bytes + bit // 8] & (128 >> (bit % 8)):
                        pixels[x, y] = 255
            self.glyphs[self.first + index] = (mask, offset + header[4], advance)

    def text(self, text, color=(255, 255, 85, 255)):
        glyphs = [self.glyphs[code] for code in text.encode("mac_roman")]
        image = Image.new("RGBA", (sum(glyph[2] for glyph in glyphs), self.height))
        x = 0
        for mask, offset, advance in glyphs:
            image.paste(color, (x + offset, 0), mask)
            x += advance
        return image
