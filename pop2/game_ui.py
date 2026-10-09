import struct
from dataclasses import dataclass

from PIL import Image, ImageDraw

from pop2.playback_navigation import PlaybackGroup


# GetFullScreenRect (CODE 17:1ada) is 510x384. The host's 512-wide
# composition buffer centers the room with one padding column on each side.
VISIBLE_VIEWPORT = (1, 0, 511, 384)
VISIBLE_SIZE = (510, 384)


def fit_viewport(width, height, native_width=510, native_height=384):
    scale = min(max(1, width) / native_width, max(1, height) / native_height)
    size = (max(1, int(native_width * scale)), max(1, int(native_height * scale)))
    return size, ((width - size[0]) // 2, (height - size[1]) // 2)


def viewport_point(x, y, width, height):
    size, origin = fit_viewport(width, height)
    if not (origin[0] <= x < origin[0] + size[0]
            and origin[1] <= y < origin[1] + size[1]):
        return None
    return (VISIBLE_VIEWPORT[0] + (x - origin[0]) * VISIBLE_SIZE[0] / size[0],
            (y - origin[1]) * VISIBLE_SIZE[1] / size[1])


@dataclass
class DevelopmentMenu:
    screens: tuple
    screen_index: int
    peaceful: bool
    focus: int = 0
    dropdown: bool = False
    option_index: int = 0
    popup_start: int = 0
    error: str = ""
    tab: int = 0
    sections: tuple = ()
    section_index: int = 0
    debug_status: bool = False
    level_available: bool = True
    section_groups: tuple = ()
    dropdown_control: int = 0

    CONTROLS = ((200, 138, 392, 166), (120, 180, 392, 210),
                (120, 231, 252, 263), (264, 231, 392, 263))
    PANEL = (100, 70, 412, 328)
    OPTION_HEIGHT = 19
    TABS = ((120, 106, 207, 127), (211, 106, 298, 127), (302, 106, 392, 127))
    PLAYBACK_CONTROLS = {
        0: (212, 138, 392, 166), 4: (212, 180, 392, 208),
        1: (120, 220, 392, 248),
        2: (120, 269, 252, 301), 3: (264, 269, 392, 301),
    }

    @property
    def groups(self):
        return self.section_groups or ((PlaybackGroup("Playback", tuple(range(len(self.sections)))),)
                                       if self.sections else ())

    @property
    def group_index(self):
        return next((i for i, group in enumerate(self.groups)
                     if self.section_index in group.part_indices), 0)

    @property
    def part_indices(self):
        return self.groups[self.group_index].part_indices if self.groups else ()

    @property
    def next_section_index(self):
        return (self.section_index + 1) % len(self.sections)

    def field_options(self, control):
        if self.tab != 1:
            return self.screens
        return (tuple(group.label for group in self.groups) if control == 0 else
                tuple(self.sections[i] for i in self.part_indices))

    def field_selected_index(self, control):
        if self.tab != 1:
            return self.screen_index
        return self.group_index if control == 0 else self.part_indices.index(self.section_index)

    @property
    def options(self):
        return self.field_options(self.dropdown_control if self.dropdown else self.focus)

    @property
    def selected_index(self):
        return self.field_selected_index(self.dropdown_control if self.dropdown else self.focus)

    def control_rect(self, index):
        return self.PLAYBACK_CONTROLS[index] if self.tab == 1 else self.CONTROLS[index]

    @property
    def popup_count(self):
        bottom = self.control_rect(self.dropdown_control)[3]
        return min(10, len(self.options), (374 - bottom) // self.OPTION_HEIGHT)

    @property
    def controls(self):
        if self.tab == 2:
            return (1, 3)
        if ((self.tab == 0 and not self.level_available)
                or (self.tab == 1 and not self.sections)):
            return (3,)
        return (0, 4, 1, 2, 3) if self.tab == 1 else (0, 1, 2, 3)

    def change_tab(self, index):
        self.tab = index % 3
        self.dropdown = False
        self.focus = self.controls[0]
        self.error = ""

    @property
    def screen(self):
        return self.screens[self.screen_index]

    def open_dropdown(self):
        self.dropdown_control = self.focus
        self.dropdown = True
        self.option_index = self.selected_index
        self.center_popup()

    def center_popup(self):
        count = self.popup_count
        self.popup_start = max(0, min(self.option_index - count // 2, len(self.options) - count))

    def scroll(self, delta):
        if not self.dropdown:
            return False
        self.option_index = max(0, min(self.option_index + delta, len(self.options) - 1))
        self.center_popup()
        return True

    def select(self, index):
        if self.tab == 1:
            control = self.dropdown_control if self.dropdown else self.focus
            self.section_index = (self.groups[index].part_indices[0] if control == 0
                                  else self.part_indices[index])
        else:
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
            order = (-1, *self.controls)
            self.focus = order[(order.index(self.focus) + (-1 if backwards else 1)) % len(order)]
        elif self.dropdown:
            if key in ("Up", "Down", "Left", "Right"):
                delta = -1 if key in ("Up", "Left") else 1
                self.option_index = (self.option_index + delta) % len(self.options)
                self.center_popup()
            elif key in ("Return", "KP_Enter", "space"):
                self.select(self.option_index)
        elif key in ("Up", "Down"):
            order = (-1, *self.controls)
            self.focus = order[(order.index(self.focus) + (-1 if key == "Up" else 1)) % len(order)]
        elif key in ("Left", "Right") and self.focus == -1:
            self.change_tab(self.tab + (-1 if key == "Left" else 1))
            self.focus = -1
        elif key in ("Left", "Right") and self.focus in (0, 4):
            self.select((self.selected_index + (-1 if key == "Left" else 1)) % len(self.options))
        elif key in ("Left", "Right") and self.focus in (2, 3):
            destination = 2 if key == "Left" else 3
            if destination in self.controls:
                self.focus = destination
        elif key in ("Return", "KP_Enter", "space"):
            return self.activate()
        return "changed"

    def activate(self):
        if self.focus not in self.controls:
            return "changed"
        if self.focus in (0, 4):
            self.open_dropdown()
        elif self.focus == 1:
            if self.tab == 2:
                self.debug_status = not self.debug_status
                return "debug_status"
            if self.tab == 1:
                return "next_part"
            self.peaceful = not self.peaceful
            return "peaceful"
        else:
            return ("seek" if self.tab == 1 else "go") if self.focus == 2 else "resume"
        return "changed"

    @staticmethod
    def contains(rect, x, y):
        left, top, right, bottom = rect
        return left <= x < right and top <= y < bottom

    def hit(self, x, y):
        if self.dropdown:
            left, _top, right, bottom = self.control_rect(self.dropdown_control)
            popup = (left, bottom, right, bottom + self.popup_count * self.OPTION_HEIGHT)
            if self.contains(popup, x, y):
                return self.popup_start + int((y - bottom) // self.OPTION_HEIGHT)
            return None
        return next((i for i in self.controls if self.contains(self.control_rect(i), x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        if index is None:
            return False
        field = "option_index" if self.dropdown else "focus"
        changed = getattr(self, field) != index
        setattr(self, field, index)
        return changed

    def click(self, x, y):
        if not self.dropdown:
            tab = next((i for i, rect in enumerate(self.TABS) if self.contains(rect, x, y)), None)
            if tab is not None:
                self.change_tab(tab)
                return "changed"
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

        def text(value, x, y, color=white, centered=False, max_width=None):
            glyphs = font.text(value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            ink = glyphs.getbbox()
            top = y - (ink[1] if ink else 0)
            image.paste(glyphs, (int(x - glyphs.width // 2) if centered else x, top), glyphs)

        text("Dev Mode", 256, 86, gold, centered=True)
        for i, (label, rect) in enumerate(zip(("Level", "Playback", "Display"), self.TABS)):
            draw.rectangle(rect, fill="#353535" if i == self.tab else "#222222",
                           outline=gold if i == self.tab and self.focus == -1 else "#626262")
            text(label, (rect[0] + rect[2]) // 2, 112, gold if i == self.tab else muted,
                 centered=True, max_width=rect[2] - rect[0] - 8)
        available = len(self.controls) > 1
        if self.tab == 0:
            text("Screen", 120, 146)
        elif self.tab == 1:
            text("Sequence", 120, 146)
            if available:
                text("Part", 120, 188)
        for i in self.controls:
            rect = self.control_rect(i)
            draw.rectangle(rect, fill="#303030" if i == self.focus else "#222222",
                           outline=gold if i == self.focus else "#626262")
        if available and self.tab != 2:
            for control in ((0, 4) if self.tab == 1 else (0,)):
                left, top, right, _bottom = self.control_rect(control)
                text(self.field_options(control)[self.field_selected_index(control)],
                     left + 10, top + 8, max_width=right - left - 34)
                draw.polygon(((right - 15, top + 12), (right - 7, top + 12),
                              (right - 11, top + 16)), fill=white)
            text("Go to part" if self.tab == 1 else "Go to screen", 186,
                 self.control_rect(2)[1] + 10,
                 centered=True, max_width=118)
        if available and self.tab in (0, 2):
            draw.rectangle((130, 189, 141, 200), fill="#121212", outline=muted)
            checked = self.debug_status if self.tab == 2 else self.peaceful
            if checked:
                draw.line(((132, 194), (135, 197), (139, 191)), fill=gold, width=2)
            text("Debug status bar" if self.tab == 2 else "Peaceful (no guards)",
                 151, 190, max_width=231)
        elif available:
            text("Next part", 256, 230, centered=True)
        else:
            text("Unavailable during playback" if self.tab == 0 else "No playback data",
                 256, 190, muted, centered=True, max_width=272)
        text("Resume", 328, self.control_rect(3)[1] + 10, centered=True)
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
            left, _top, right, bottom = self.control_rect(self.dropdown_control)
            count = self.popup_count
            draw.rectangle((left, bottom, right, bottom + count * self.OPTION_HEIGHT),
                           fill="#222222", outline=gold)
            for i in range(self.popup_start, self.popup_start + count):
                label = self.options[i]
                y = bottom + (i - self.popup_start) * self.OPTION_HEIGHT
                if i == self.option_index:
                    draw.rectangle((left + 1, y + 1, right - 1, y + self.OPTION_HEIGHT - 1),
                                   fill="#454545")
                text(label, left + 10, y + 4, gold if i == self.selected_index else white,
                     max_width=right - left - 20)
            if len(self.options) > count:
                track = count * self.OPTION_HEIGHT - 4
                thumb = max(8, track * count // len(self.options))
                top = bottom + 2 + (track - thumb) * self.popup_start // (len(self.options) - count)
                draw.rectangle((right - 5, bottom + 2, right - 3, bottom + track + 1), fill="#454545")
                draw.rectangle((right - 5, top, right - 3, top + thumb - 1), fill=muted)
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
