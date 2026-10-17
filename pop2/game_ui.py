import struct
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageEnhance

from pop2.playback_navigation import PlaybackGroup


# GetFullScreenRect (CODE 17:1ada) is 510x384. The host's 512-wide
# composition buffer centers the room with one padding column on each side.
VISIBLE_VIEWPORT = (1, 0, 511, 384)
VISIBLE_SIZE = (510, 384)
# Menus are centered over the room, above the 19-pixel health/status strip.
PLAYFIELD_VIEWPORT = (1, 0, 511, 365)


def centered_panel(width, height):
    left, top, right, bottom = PLAYFIELD_VIEWPORT
    left += (right - left - width) // 2
    top += (bottom - top - height) // 2
    return left, top, left + width, top + height


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
    level_options: tuple = ()
    level_index: int = 0
    map_provider: object = None
    hovered_screen: str | None = None

    CONTROLS = ((200, 138, 392, 166), (120, 180, 392, 210),
                (120, 231, 252, 263), (264, 231, 392, 263))
    LEVEL_CONTROLS = {0: (200, 138, 392, 166), 1: (120, 220, 392, 246),
                      2: (120, 282, 252, 314), 3: (264, 282, 392, 314),
                      4: (200, 179, 392, 207)}
    # Control templates use this reference panel; each tab is positioned as a unit.
    PANEL = (100, 70, 412, 350)
    OPTION_HEIGHT = 19
    TABS = ((120, 106, 207, 127), (211, 106, 298, 127), (302, 106, 392, 127))
    PLAYBACK_CONTROLS = {
        0: (212, 138, 392, 166), 4: (212, 180, 392, 208),
        1: (120, 220, 392, 248),
        2: (120, 269, 252, 301), 3: (264, 269, 392, 301),
    }
    MAP_CONTROLS = {
        0: (200, 69, 488, 93), 4: (24, 100, 488, 294),
        1: (24, 306, 300, 330), 2: (310, 306, 392, 330), 3: (400, 306, 488, 330),
    }

    @property
    def map_enabled(self):
        return self.tab == 0 and self.level_available and self.map_provider is not None

    @property
    def map_preview(self):
        return self.map_provider(self.level_number) if self.map_enabled else None

    def map_hit(self, x, y):
        left, top, _right, _bottom = self.control_rect(4)
        return self.map_preview.hit(x - left, y - top)

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
        if self.tab == 0 and self.level_options:
            return (tuple(option[1] for option in self.level_options) if control == 0
                    else self.screen_options)
        if self.tab != 1:
            return self.screens
        return (tuple(group.label for group in self.groups) if control == 0 else
                tuple(self.sections[i] for i in self.part_indices))

    @property
    def screen_options(self):
        return self.level_options[self.level_index][2] if self.level_options else self.screens

    @property
    def level_number(self):
        return self.level_options[self.level_index][0] if self.level_options else None

    def field_selected_index(self, control):
        if self.tab == 0 and self.level_options:
            return self.level_index if control == 0 else self.screen_index
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
        if self.map_enabled:
            return self.MAP_CONTROLS[index]
        if self.tab == 0 and self.level_options:
            rect = self.LEVEL_CONTROLS[index]
        else:
            rect = self.PLAYBACK_CONTROLS[index] if self.tab == 1 else self.CONTROLS[index]
        return self.position_rect(rect)

    @property
    def panel_rect(self):
        if self.map_enabled:
            return centered_panel(488, 348)
        return centered_panel(312, 280 if self.tab == 0 and self.level_options else 258)

    @property
    def layout_offset(self):
        return self.panel_rect[1] - self.PANEL[1]

    def position_rect(self, rect):
        left, top, right, bottom = rect
        return left, top + self.layout_offset, right, bottom + self.layout_offset

    def tab_rect(self, index):
        return self.position_rect(self.TABS[index])

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
        if self.tab == 1:
            return (0, 4, 1, 2, 3)
        if self.tab == 0 and self.level_options:
            return (0, 4, 1, 2, 3)
        return (0, 1, 2, 3)

    def change_tab(self, index):
        self.tab = index % 3
        self.dropdown = False
        self.hovered_screen = None
        self.focus = self.controls[0]
        self.error = ""

    @property
    def screen(self):
        return self.screen_options[self.screen_index]

    def open_dropdown(self):
        if self.map_enabled and self.focus == 4:
            return
        self.hovered_screen = None
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
        elif (self.tab == 0 and self.level_options
              and (self.dropdown_control if self.dropdown else self.focus) == 0):
            self.level_index = index
            self.screens = self.screen_options
            self.screen_index = 0
            self.hovered_screen = None
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
        elif self.map_enabled and self.focus == 4 and key in ("Up", "Down", "Left", "Right"):
            label = self.map_preview.move(self.screen, key.lower())
            self.screen_index = self.screen_options.index(label)
            self.hovered_screen = None
            self.error = ""
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
        if self.map_enabled and self.focus == 4:
            return "go"
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
        if self.map_enabled and not self.dropdown:
            before = self.focus, self.hovered_screen
            self.hovered_screen = self.map_hit(x, y) if index == 4 else None
            if index is not None:
                self.focus = index
            return before != (self.focus, self.hovered_screen)
        if index is None:
            return False
        field = "option_index" if self.dropdown else "focus"
        changed = getattr(self, field) != index
        setattr(self, field, index)
        return changed

    def click(self, x, y):
        if not self.dropdown:
            tab = next((i for i in range(len(self.TABS))
                        if self.contains(self.tab_rect(i), x, y)), None)
            if tab is not None:
                self.change_tab(tab)
                return "changed"
        index = self.hit(x, y)
        if self.map_enabled and not self.dropdown and index == 4:
            label = self.map_hit(x, y)
            if label is not None:
                self.screen_index = self.screen_options.index(label)
                self.hovered_screen = label
                self.focus = 4
                self.error = ""
                return "go"
            return "changed"
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
        offset = self.layout_offset
        draw.rectangle(self.panel_rect, fill="#181818", outline="#858585")

        def text(value, x, y, color=white, centered=False, max_width=None):
            glyphs = font.text(value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            ink = glyphs.getbbox()
            top = y - (ink[1] if ink else 0)
            image.paste(glyphs, (int(x - glyphs.width // 2) if centered else x, top), glyphs)

        text("Developer Tools", 256, 86 + offset, gold, centered=True)
        for i, label in enumerate(("Level", "Playback", "Display")):
            rect = self.tab_rect(i)
            draw.rectangle(rect, fill="#353535" if i == self.tab else "#222222",
                           outline=gold if i == self.tab and self.focus == -1 else "#626262")
            text(label, (rect[0] + rect[2]) // 2, rect[1] + 6, gold if i == self.tab else muted,
                 centered=True, max_width=rect[2] - rect[0] - 8)
        if self.map_enabled:
            self.draw_map(image, draw, font, text)
            self.draw_popup(draw, text)
            return image
        available = len(self.controls) > 1
        if self.tab == 0:
            text("Level" if self.level_options else "Screen", 120, 146 + offset)
            if self.level_options:
                text("Screen", 120, 187 + offset)
        elif self.tab == 1:
            text("Sequence", 120, 146 + offset)
            if available:
                text("Part", 120, 188 + offset)
        for i in self.controls:
            rect = self.control_rect(i)
            draw.rectangle(rect, fill="#303030" if i == self.focus else "#222222",
                           outline=gold if i == self.focus else "#626262")
        if available and self.tab != 2:
            selectors = ((0, 4) if self.tab == 1 or self.tab == 0 and self.level_options
                         else (0,))
            for control in selectors:
                left, top, right, _bottom = self.control_rect(control)
                text(self.field_options(control)[self.field_selected_index(control)],
                     left + 10, top + 8, max_width=right - left - 34)
                draw.polygon(((right - 15, top + 12), (right - 7, top + 12),
                              (right - 11, top + 16)), fill=white)
            text("Go to part" if self.tab == 1 else "Go to screen", 186,
                 self.control_rect(2)[1] + 10,
                 centered=True, max_width=118)
        if available and self.tab in (0, 2):
            checkbox_y = self.control_rect(1)[1] + (8 if self.tab == 0 and self.level_options else 9)
            draw.rectangle((130, checkbox_y, 141, checkbox_y + 11), fill="#121212", outline=muted)
            checked = self.debug_status if self.tab == 2 else self.peaceful
            if checked:
                draw.line(((132, checkbox_y + 5), (135, checkbox_y + 8),
                           (139, checkbox_y + 2)), fill=gold, width=2)
            text("Debug status bar" if self.tab == 2 else "Peaceful (no guards)",
                 151, checkbox_y + (1 if self.tab == 0 and self.level_options else 0), max_width=231)
        elif available:
            text("Next part", 256, 230 + offset, centered=True)
        else:
            text("Unavailable during playback" if self.tab == 0 else "No playback data",
                 256, 190 + offset, muted, centered=True, max_width=272)
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
            compact = self.tab == 0 and self.level_options
            error_y = (318 if compact else 277) + offset
            line_limit = 2 if compact else 3
            for i, line in enumerate(lines[:line_limit]):
                text(line, 120, error_y + i * 14, "#ff9b9b", max_width=272)
        self.draw_popup(draw, text)
        return image

    def draw_map(self, image, draw, font, text):
        gold, white, muted = '#f4d873', '#eeeeee', '#b9b9b9'
        text('Level', 24, 77)
        for control in (0, 1, 2, 3):
            rect = self.control_rect(control)
            draw.rectangle(rect, fill='#303030' if self.focus == control else '#222222',
                           outline=gold if self.focus == control else '#626262')
        left, top, right, _bottom = self.control_rect(0)
        text(self.field_options(0)[self.level_index], left + 10, top + 7,
             max_width=right - left - 34)
        draw.polygon(((right - 15, top + 10), (right - 7, top + 10),
                      (right - 11, top + 14)), fill=white)
        left, top, right, bottom = self.control_rect(4)
        image.paste(self.map_layer(font), (left, top))
        draw.rectangle((left - 1, top - 1, right, bottom),
                       outline=muted if self.focus == 4 else '#454545')
        checkbox_y = self.control_rect(1)[1] + 6
        draw.rectangle((34, checkbox_y, 45, checkbox_y + 11), fill='#121212', outline=muted)
        if self.peaceful:
            draw.line(((36, checkbox_y + 5), (39, checkbox_y + 8),
                       (43, checkbox_y + 2)), fill=gold, width=2)
        text('Peaceful (no guards)', 55, checkbox_y + 1, max_width=235)
        text('Go', 351, 313, centered=True, max_width=70)
        text('Resume', 444, 313, centered=True, max_width=76)
        if self.error:
            text(self.error, 24, 338, '#ff9b9b', max_width=464)

    def map_layer(self, font, size=None):
        preview = self.map_preview
        size = size or preview.image.size
        image = preview.detail(size).convert('RGBA')
        draw = ImageDraw.Draw(image)
        sx, sy = size[0] / preview.image.width, size[1] / preview.image.height
        gold = '#f4d873'

        def room_rect(label):
            x1, y1, x2, y2 = preview.rooms[label]
            return round(x1 * sx), round(y1 * sy), round(x2 * sx) - 1, round(y2 * sy) - 1

        if self.screen in preview.rooms:
            draw.rectangle(room_rect(self.screen), outline='#63c8e5', width=max(1, round(min(sx, sy))))
        if self.hovered_screen in preview.rooms:
            label = self.hovered_screen
            x1, y1, x2, y2 = room_rect(label)
            rect = x1, y1, x2 + 1, y2 + 1
            image.paste(ImageEnhance.Brightness(image.crop(rect)).enhance(1.35), (x1, y1))
            draw.rectangle((x1, y1, x2, y2), outline=gold, width=max(1, round(2 * min(sx, sy))))
            label = label if label.startswith('Room ') else f'Screen {label}'
            glyphs = font.text(label, gold)
            width = min(round((glyphs.width + 12) * sx), size[0] - 1)
            tx = max(0, min((x1 + x2 - width) // 2, size[0] - width - 1))
            ty = y1 - round(20 * sy) if y1 >= round(20 * sy) else y2 + round(3 * sy)
            ty = min(ty, size[1] - round(19 * sy))
            draw.rectangle((tx, ty, tx + width, ty + round(18 * sy)),
                           fill='#181818', outline=gold, width=max(1, round(min(sx, sy))))
            ink = glyphs.getbbox()
            if ink:
                glyphs = glyphs.crop((0, ink[1], glyphs.width, ink[3]))
                glyphs = glyphs.resize((min(round(glyphs.width * sx), width - round(12 * sx)),
                                        max(1, round(glyphs.height * sy))), Image.Resampling.NEAREST)
                image.paste(glyphs, (tx + round(6 * sx), ty + round(4 * sy)), glyphs)
        return image

    def present_map(self, frame, font):
        if not self.map_enabled:
            return frame
        sx, sy = frame.width / VISIBLE_SIZE[0], frame.height / VISIBLE_SIZE[1]

        def projected(rect):
            left, top, right, bottom = rect
            return round((left - 1) * sx), round(top * sy), round((right - 1) * sx), round(bottom * sy)

        popup = None
        if self.dropdown:
            x1, _y1, x2, y2 = self.control_rect(self.dropdown_control)
            rect = (x1, y2, x2 + 1, y2 + self.popup_count * self.OPTION_HEIGHT + 1)
            popup_rect = projected(rect)
            popup = frame.crop(popup_rect)
        left, top, right, bottom = projected(self.control_rect(4))
        frame.paste(self.map_layer(font, (right - left, bottom - top)), (left, top))
        if popup is not None:
            frame.paste(popup, popup_rect[:2])
        return frame

    def draw_popup(self, draw, text):
        gold, white, muted = '#f4d873', '#eeeeee', '#b9b9b9'
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
