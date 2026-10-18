import struct
from dataclasses import dataclass, field

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
    page: str = 'tools'
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
    map_open: bool = False
    hovered_control: int | None = None
    return_screens: dict = field(default_factory=dict)
    playback_provider: object = None
    gallery_page: int = 0
    hovered_part: int | None = None
    gallery_pages: dict = field(default_factory=dict, repr=False)
    current_section: int | None = None
    current_level: int | None = None
    current_screen: str | None = None
    preview_keyboard_selection: bool = False

    CONTROLS = ((200, 138, 392, 166), (120, 180, 392, 210),
                (120, 231, 252, 263), (264, 231, 392, 263))
    LEVEL_CONTROLS = {0: (200, 138, 392, 166), 1: (120, 220, 392, 246),
                      2: (120, 282, 252, 314), 3: (264, 282, 392, 314),
                      4: (200, 179, 392, 207)}
    # Control templates use this reference panel; each page is positioned as a unit.
    PANEL = (100, 70, 412, 350)
    OPTION_HEIGHT = 19
    PLAYBACK_CONTROLS = {
        0: (212, 138, 392, 166), 4: (212, 180, 392, 208),
        1: (120, 220, 392, 248),
        2: (120, 269, 252, 301), 3: (264, 269, 392, 301),
        7: (120, 80, 146, 106), 8: (120, 316, 392, 342),
    }
    MAP_CONTROLS = {
        7: (14, 14, 40, 40), 5: (130, 14, 156, 40),
        0: (164, 14, 348, 40), 6: (356, 14, 382, 40),
        4: (12, 52, 500, 330), 1: (16, 348, 292, 372),
        2: (310, 348, 386, 372), 3: (394, 348, 494, 372),
    }
    GAME_CONTROLS = {4: (120, 126, 392, 166), 8: (120, 174, 392, 210),
                     1: (120, 218, 392, 248), 3: (120, 270, 392, 300)}
    GALLERY_CONTROLS = {**MAP_CONTROLS, 9: (420, 14, 446, 40), 10: (460, 14, 486, 40),
                        8: (14, 348, 40, 372), 1: (52, 348, 202, 372),
                        2: (214, 348, 350, 372), 3: (362, 348, 498, 372)}

    def __post_init__(self):
        if self.focus not in self.controls:
            self.focus = self.controls[0]

    @property
    def map_available(self):
        return self.page == 'tools' and self.level_available and self.map_provider is not None

    @property
    def map_enabled(self):
        return self.map_available and self.map_open

    @property
    def gallery_enabled(self):
        return self.page == 'playback' and bool(self.sections) and self.playback_provider is not None

    @property
    def preview_enabled(self):
        return self.map_enabled or self.gallery_enabled

    @property
    def gallery_count(self):
        return (len(self.part_indices) + 5) // 6

    @property
    def gallery_preview(self):
        from pop2.playback_preview import gallery_preview

        key = tuple(self.part_indices[self.gallery_page * 6:(self.gallery_page + 1) * 6])
        if key not in self.gallery_pages:
            frames = self.playback_provider(key)
            if len(self.gallery_pages) >= 4:
                del self.gallery_pages[next(iter(self.gallery_pages))]
            self.gallery_pages[key] = gallery_preview(frames, key)
        preview = self.gallery_pages.pop(key)
        self.gallery_pages[key] = preview
        return preview

    def gallery_hit(self, x, y):
        from pop2.playback_preview import gallery_caption_rect

        left, top, right, bottom = self.control_rect(4)
        scale, (ox, oy) = self.gallery_preview.transform((right - left, bottom - top))
        px, py = (x - left - ox) / scale, (y - top - oy) / scale
        label = self.gallery_preview.hit(px, py)
        if label is None:
            label = next((label for label, rect in self.gallery_preview.rooms.items()
                          if self.contains(gallery_caption_rect(rect, len(self.gallery_preview.rooms) == 1),
                                           px, py)), None)
        return int(label) if label is not None else None

    def turn_gallery_page(self, delta):
        self.gallery_page = (self.gallery_page + delta) % self.gallery_count
        self.section_index = self.part_indices[self.gallery_page * 6]
        self.hovered_part = None
        self.preview_keyboard_selection = False

    @property
    def map_preview(self):
        return self.map_provider(self.level_number) if self.map_available else None

    @property
    def return_screen(self):
        label = self.return_screens.get(self.level_number)
        return label if label in self.screen_options else None

    def map_hit(self, x, y):
        left, top, right, bottom = self.control_rect(4)
        scale, (ox, oy) = self.map_preview.transform((right - left, bottom - top))
        return self.map_preview.hit((x - left - ox) / scale, (y - top - oy) / scale)

    def open_map(self):
        self.map_open = True
        self.focus = 4
        self.dropdown = False
        self.hovered_screen = None
        self.hovered_control = None
        self.error = ''
        self.preview_keyboard_selection = False

    def close_map(self):
        self.map_open = False
        self.focus = 4
        self.dropdown = False
        self.hovered_screen = None
        self.hovered_control = None
        self.error = ''

    def cycle_level(self, delta):
        focus = self.focus
        self.focus = 0
        self.select((self.level_index + delta) % len(self.level_options))
        self.focus = focus

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
        if self.page == 'tools' and self.level_options:
            return (tuple(option[1] for option in self.level_options) if control == 0
                    else self.screen_options)
        if self.page != 'playback':
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
        if self.page == 'tools' and self.level_options:
            return self.level_index if control == 0 else self.screen_index
        if self.page != 'playback':
            return self.screen_index
        return self.group_index if control == 0 else self.part_indices.index(self.section_index)

    @property
    def options(self):
        return self.field_options(self.dropdown_control if self.dropdown else self.focus)

    @property
    def selected_index(self):
        return self.field_selected_index(self.dropdown_control if self.dropdown else self.focus)

    def control_rect(self, index):
        if self.gallery_enabled:
            return self.GALLERY_CONTROLS[index]
        if self.map_enabled:
            return self.MAP_CONTROLS[index]
        if self.page == 'tools' and (self.map_available or not self.level_available):
            return self.position_rect(self.GAME_CONTROLS[index])
        if self.page == 'tools' and self.level_options:
            rect = self.LEVEL_CONTROLS[index]
        else:
            rect = self.PLAYBACK_CONTROLS[index] if self.page == 'playback' else self.CONTROLS[index]
        return self.position_rect(rect)

    @property
    def panel_rect(self):
        if self.preview_enabled:
            return VISIBLE_VIEWPORT
        if self.page == 'tools' and (self.map_available or not self.level_available):
            return centered_panel(312, 250)
        return centered_panel(312, 280)

    @property
    def layout_offset(self):
        return self.panel_rect[1] - self.PANEL[1]

    def position_rect(self, rect):
        left, top, right, bottom = rect
        return left, top + self.layout_offset, right, bottom + self.layout_offset

    @property
    def popup_count(self):
        bottom = self.control_rect(self.dropdown_control)[3]
        return min(10, len(self.options), (374 - bottom) // self.OPTION_HEIGHT)

    @property
    def controls(self):
        if self.gallery_enabled:
            return tuple(control for control in (7, 5, 0, 6, 9, 10, 4, 8, 1, 2, 3)
                         if control not in (9, 10) or self.gallery_count > 1)
        if self.map_enabled:
            return tuple(control for control in (7, 5, 0, 6, 4, 1, 2, 3)
                         if (control not in (5, 6) or len(self.level_options) > 1)
                         and (control != 1 or self.return_screen is not None))
        if self.map_available:
            return (4, 8, 1, 3)
        if self.page == 'tools' and not self.level_available:
            return (8, 3)
        if self.page == 'playback':
            return (7, 0, 4, 1, 2, 3, 8) if self.sections else (7, 3, 8)
        if self.page == 'tools' and self.level_options:
            return (0, 4, 1, 2, 3)
        return (0, 1, 2, 3)

    @property
    def focus_order(self):
        return self.controls

    def show_page(self, page):
        self.page = page
        self.map_open = False
        self.dropdown = False
        self.hovered_screen = None
        self.hovered_control = None
        self.hovered_part = None
        self.preview_keyboard_selection = False
        self.gallery_page = self.part_indices.index(self.section_index) // 6 if self.gallery_enabled else 0
        self.focus = (4 if self.gallery_enabled else
                      0 if page == 'playback' and self.sections else self.controls[0])
        self.error = ""

    @property
    def screen(self):
        return self.screen_options[self.screen_index]

    def open_dropdown(self):
        if (self.map_available or self.gallery_enabled) and self.focus == 4:
            return
        self.hovered_screen = None
        self.hovered_part = None
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
        self.preview_keyboard_selection = False
        if self.page == 'playback':
            control = self.dropdown_control if self.dropdown else self.focus
            self.section_index = (self.groups[index].part_indices[0] if control == 0
                                  else self.part_indices[index])
            self.gallery_page = self.part_indices.index(self.section_index) // 6
            self.hovered_part = None
        elif (self.page == 'tools' and self.level_options
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
        self.hovered_control = None
        if key == "Escape":
            if self.dropdown:
                self.dropdown = False
                return "changed"
            if self.map_enabled:
                self.close_map()
                return "changed"
            if self.page == 'playback':
                self.show_page('tools')
                if 8 in self.controls:
                    self.focus = 8
                return 'changed'
            return "resume"
        if key == "Tab":
            self.dropdown = False
            order = self.focus_order
            self.focus = order[(order.index(self.focus) + (-1 if backwards else 1)) % len(order)]
        elif self.dropdown:
            if key in ("Up", "Down", "Left", "Right"):
                delta = -1 if key in ("Up", "Left") else 1
                self.option_index = (self.option_index + delta) % len(self.options)
                self.center_popup()
            elif key in ("Return", "KP_Enter", "space"):
                self.select(self.option_index)
        elif self.gallery_enabled and self.focus == 4 and key in ('Up', 'Down', 'Left', 'Right'):
            delta = {'Left': -1, 'Right': 1, 'Up': -3, 'Down': 3}[key]
            index = max(0, min(len(self.part_indices) - 1,
                              self.part_indices.index(self.section_index) + delta))
            self.section_index = self.part_indices[index]
            self.gallery_page = index // 6
            self.hovered_part = None
            self.preview_keyboard_selection = True
        elif self.map_enabled and self.focus == 4 and key in ("Up", "Down", "Left", "Right"):
            label = self.map_preview.move(self.screen, key.lower())
            self.screen_index = self.screen_options.index(label)
            self.hovered_screen = None
            self.error = ""
            self.preview_keyboard_selection = True
        elif key in ("Up", "Down"):
            order = self.focus_order
            self.focus = order[(order.index(self.focus) + (-1 if key == "Up" else 1)) % len(order)]
        elif key in ("Left", "Right") and self.focus in (0, 4) and not (
                self.map_available and not self.map_enabled):
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
        if self.gallery_enabled and self.focus == 4:
            return 'seek'
        if self.gallery_enabled and self.focus in (5, 6):
            focus = self.focus
            self.focus = 0
            self.select((self.group_index + (-1 if focus == 5 else 1)) % len(self.groups))
            self.focus = focus
            return 'changed'
        if self.gallery_enabled and self.focus in (9, 10):
            self.turn_gallery_page(-1 if self.focus == 9 else 1)
            return 'changed'
        if self.focus == 8:
            if self.page == 'playback':
                self.debug_status = not self.debug_status
                return 'debug_status'
            self.show_page('playback')
            return 'changed'
        if self.page == 'playback' and self.focus == 7:
            self.show_page('tools')
            self.focus = 8 if 8 in self.controls else self.controls[0]
            return 'changed'
        if self.map_available and not self.map_enabled and self.focus == 4:
            self.open_map()
            return 'changed'
        if self.map_enabled and self.focus == 7:
            self.close_map()
            return 'changed'
        if self.map_enabled and self.focus in (5, 6):
            self.cycle_level(-1 if self.focus == 5 else 1)
            return 'changed'
        if self.map_enabled and self.focus == 4:
            return "go"
        if self.map_enabled and self.focus == 1:
            return 'return_room'
        if self.focus in (0, 4):
            self.open_dropdown()
        elif self.focus == 1:
            if self.page == 'playback':
                return "next_part"
            self.peaceful = not self.peaceful
            return "peaceful"
        else:
            return ("seek" if self.page == 'playback' else "go") if self.focus == 2 else "resume"
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
        if self.gallery_enabled and not self.dropdown:
            before = self.focus, self.hovered_part, self.hovered_control, self.preview_keyboard_selection
            self.preview_keyboard_selection = False
            self.hovered_part = self.gallery_hit(x, y) if index == 4 else None
            self.hovered_control = index if index in (5, 6, 7, 8, 9, 10) else None
            if index is not None:
                self.focus = index
            return before != (self.focus, self.hovered_part, self.hovered_control, self.preview_keyboard_selection)
        if self.map_enabled and not self.dropdown:
            before = self.focus, self.hovered_screen, self.hovered_control, self.preview_keyboard_selection
            self.preview_keyboard_selection = False
            self.hovered_screen = self.map_hit(x, y) if index == 4 else None
            self.hovered_control = index if index in (5, 6, 7) else None
            if index is not None:
                self.focus = index
            return before != (self.focus, self.hovered_screen, self.hovered_control, self.preview_keyboard_selection)
        if index is None:
            return False
        field = "option_index" if self.dropdown else "focus"
        changed = getattr(self, field) != index
        setattr(self, field, index)
        return changed

    def click(self, x, y):
        index = self.hit(x, y)
        if self.gallery_enabled and not self.dropdown and index == 4:
            part = self.gallery_hit(x, y)
            if part is not None:
                self.section_index = part
                self.focus = 4
                return 'seek'
            return 'changed'
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

        def text(value, x, y, color=white, centered=False, max_width=None):
            glyphs = font.text(value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            ink = glyphs.getbbox()
            top = y - (ink[1] if ink else 0)
            image.paste(glyphs, (int(x - glyphs.width // 2) if centered else x, top), glyphs)

        if self.gallery_enabled:
            self.draw_gallery(image, draw, font, text)
            self.draw_popup(draw, text)
            return image
        if self.map_enabled:
            self.draw_map(image, draw, font, text)
            self.draw_popup(draw, text)
            return image
        draw.rectangle(self.panel_rect, fill="#181818", outline="#858585")
        text('Playback' if self.page == 'playback' else 'Developer Tools',
             264 if self.page == 'playback' else 256, 86 + offset, gold, centered=True)
        if self.page == 'tools' and (self.map_available or not self.level_available):
            self.draw_game_tools(draw, text)
            return image
        available = self.page != 'playback' or bool(self.sections)
        if self.page == 'tools':
            text("Level" if self.level_options else "Screen", 120, 146 + offset)
            if self.level_options:
                text("Screen", 120, 187 + offset)
        elif available:
            text("Sequence", 120, 146 + offset)
            text("Part", 120, 188 + offset)
        for i in self.controls:
            rect = self.control_rect(i)
            draw.rectangle(rect, fill="#303030" if i == self.focus else "#222222",
                           outline=gold if i == self.focus else "#626262")
        if self.page == 'playback':
            left, top, right, bottom = self.control_rect(7)
            cx, cy = (left + right) // 2, (top + bottom) // 2
            draw.line(((cx + 7, cy), (cx - 6, cy), (cx, cy - 6)), fill=white, width=2)
            draw.line(((cx - 6, cy), (cx, cy + 6)), fill=white, width=2)
            top = self.control_rect(8)[1]
            draw.rectangle((130, top + 7, 141, top + 18), fill='#121212', outline=muted)
            if self.debug_status:
                draw.line(((132, top + 12), (135, top + 15), (139, top + 9)), fill=gold, width=2)
            text('Debug status bar', 151, top + 7, muted, max_width=231)
        if available:
            selectors = ((0, 4) if self.page == 'playback' or self.level_options
                         else (0,))
            for control in selectors:
                left, top, right, _bottom = self.control_rect(control)
                text(self.field_options(control)[self.field_selected_index(control)],
                     left + 10, top + 8, max_width=right - left - 34)
                draw.polygon(((right - 15, top + 12), (right - 7, top + 12),
                              (right - 11, top + 16)), fill=white)
            text("Go to part" if self.page == 'playback' else "Go to screen", 186,
                 self.control_rect(2)[1] + 10,
                 centered=True, max_width=118)
        if available and self.page == 'tools':
            checkbox_y = self.control_rect(1)[1] + (8 if self.level_options else 9)
            draw.rectangle((130, checkbox_y, 141, checkbox_y + 11), fill="#121212", outline=muted)
            if self.peaceful:
                draw.line(((132, checkbox_y + 5), (135, checkbox_y + 8),
                           (139, checkbox_y + 2)), fill=gold, width=2)
            text("Peaceful (no guards)",
                 151, checkbox_y + (1 if self.level_options else 0), max_width=231)
        elif available:
            text("Next part", 256, 230 + offset, centered=True)
        else:
            text("No playback data",
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
            compact = self.page == 'tools' and self.level_options
            error_y = (318 if compact else 277) + offset
            line_limit = 2 if compact else 3
            for i, line in enumerate(lines[:line_limit]):
                text(line, 120, error_y + i * 14, "#ff9b9b", max_width=272)
        self.draw_popup(draw, text)
        return image

    def draw_game_tools(self, draw, text):
        gold = '#f4d873'
        for control in self.controls:
            draw.rectangle(self.control_rect(control),
                           fill='#303030' if self.focus == control else '#222222',
                           outline=gold if self.focus == control else '#626262')
        for control, label in ((4, 'Open map'), (8, 'Playback')):
            if control not in self.controls:
                continue
            left, top, right, bottom = self.control_rect(control)
            cy = (top + bottom) // 2
            text(label, 246, cy - 6, centered=True, max_width=220)
            draw.line(((right - 23, cy - 5), (right - 18, cy),
                       (right - 23, cy + 5)), fill=gold, width=2)
        if 1 in self.controls:
            top = self.control_rect(1)[1]
            draw.rectangle((130, top + 9, 141, top + 20), fill='#121212', outline='#b9b9b9')
            if self.peaceful:
                draw.line(((132, top + 14), (135, top + 17), (139, top + 11)), fill=gold, width=2)
            text('Peaceful mode', 151, top + 9, max_width=231)
        text('Resume', 256, self.control_rect(3)[1] + 10, centered=True)

    def draw_map(self, image, draw, font, text):
        gold, white = '#f4d873', '#eeeeee'
        draw.rectangle((1, 0, 510, 383), fill='#101010')
        draw.line((12, 47, 500, 47), fill='#383838')
        draw.line((12, 340, 500, 340), fill='#383838')
        for control in (7, 5, 0, 6, 1, 2, 3):
            if control not in self.controls and control != 1:
                continue
            rect = self.control_rect(control)
            draw.rectangle(rect, fill='#303030' if self.focus == control else '#222222',
                           outline=gold if self.focus == control else '#626262')
        left, top, right, _bottom = self.control_rect(0)
        text(self.field_options(0)[self.level_index], 250, top + 7,
             centered=True, max_width=right - left - 34)
        draw.polygon(((right - 15, top + 10), (right - 7, top + 10),
                      (right - 11, top + 14)), fill=white)
        left, top, right, bottom = self.control_rect(4)
        image.paste(self.map_layer(font), (left, top))
        for control in (5, 6, 7):
            if control not in self.controls:
                continue
            x1, y1, x2, y2 = self.control_rect(control)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            if control == 7:
                draw.line(((cx + 7, cy), (cx - 6, cy)), fill=white, width=2)
                draw.line(((cx, cy - 6), (cx - 6, cy), (cx, cy + 6)), fill=white, width=2)
            else:
                direction = 1 if control == 6 else -1
                draw.line(((cx - direction * 3, cy - 5), (cx + direction * 3, cy),
                           (cx - direction * 3, cy + 5)), fill=white, width=2)
        destination = self.return_screen
        label = (f'Return to {destination}' if destination is not None else 'Return to last room')
        text(label, 154, 355, white if destination is not None else '#777777',
             centered=True, max_width=256)
        text('Go', 348, 355, centered=True, max_width=64)
        text('Resume', 444, 355, centered=True, max_width=88)
        if self.error:
            text(self.error, 12, 332, '#ff9b9b', max_width=488)
        tooltip = self.map_tooltip(font)
        if tooltip is not None:
            label, rect = tooltip
            draw.rectangle(rect, fill='#181818', outline=gold)
            text(label, rect[0] + 6, rect[1] + 4, gold)

    def map_tooltip(self, font):
        labels = ({5: 'Previous sequence', 6: 'Next sequence', 7: 'Developer Tools',
                   8: 'Debug status bar', 9: 'Previous page', 10: 'Next page'}
                  if self.gallery_enabled else
                  {5: 'Previous level', 6: 'Next level', 7: 'Developer Tools'})
        if self.dropdown or self.hovered_control not in labels:
            return None
        label = labels[self.hovered_control]
        x1, _y1, _x2, y2 = self.control_rect(self.hovered_control)
        width = font.text(label).width + 12
        x1 = min(x1, 500 - width)
        y1 = y2 + 3 if y2 < 300 else self.control_rect(self.hovered_control)[1] - 22
        return label, (x1, y1, x1 + width, y1 + 18)

    def draw_gallery(self, image, draw, font, text):
        gold, white = '#f4d873', '#eeeeee'
        draw.rectangle((1, 0, 510, 383), fill='#101010')
        draw.line((12, 47, 500, 47), fill='#383838')
        draw.line((12, 340, 500, 340), fill='#383838')
        for control in self.controls:
            if control == 4:
                continue
            rect = self.control_rect(control)
            draw.rectangle(rect, fill='#303030' if self.focus == control else '#222222',
                           outline=gold if self.focus == control else '#626262')
        left, top, right, _bottom = self.control_rect(0)
        text(self.groups[self.group_index].label, 250, top + 7,
             centered=True, max_width=right - left - 34)
        if self.gallery_count > 1:
            text(f'{self.gallery_page + 1}/{self.gallery_count}', 401, top + 8,
                 '#b9b9b9', centered=True, max_width=30)
        draw.polygon(((right - 15, top + 10), (right - 7, top + 10),
                      (right - 11, top + 14)), fill=white)
        left, top, _right, _bottom = self.control_rect(4)
        image.paste(self.gallery_layer(font), (left, top))
        for control in (7, 5, 6, 9, 10):
            if control not in self.controls:
                continue
            x1, y1, x2, y2 = self.control_rect(control)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            if control == 7:
                draw.line(((cx + 7, cy), (cx - 6, cy)), fill=white, width=2)
                draw.line(((cx, cy - 6), (cx - 6, cy), (cx, cy + 6)), fill=white, width=2)
            else:
                direction = 1 if control in (6, 10) else -1
                draw.line(((cx - direction * 3, cy - 5), (cx + direction * 3, cy),
                           (cx - direction * 3, cy + 5)), fill=white, width=2)
                if control in (9, 10):
                    draw.line((cx + direction * 7, cy - 5, cx + direction * 7, cy + 5),
                              fill=white, width=2)
        left, top, _right, _bottom = self.control_rect(8)
        draw.rectangle((left + 7, top + 6, left + 18, top + 17), fill='#121212', outline='#b9b9b9')
        if self.debug_status:
            draw.line(((left + 9, top + 11), (left + 12, top + 14), (left + 16, top + 8)),
                      fill=gold, width=2)
        text('Next part', 127, 355, centered=True, max_width=138)
        text('Play', 282, 355, centered=True, max_width=124)
        text('Resume', 430, 355, centered=True, max_width=124)
        tooltip = self.map_tooltip(font)
        if tooltip is not None:
            label, rect = tooltip
            draw.rectangle(rect, fill='#181818', outline=gold)
            text(label, rect[0] + 6, rect[1] + 4, gold)

    def gallery_layer(self, font, size=None):
        from pop2.playback_preview import gallery_caption, gallery_caption_rect

        preview = self.gallery_preview
        left, top, right, bottom = self.control_rect(4)
        size = size or (right - left, bottom - top)
        image = preview.detail(size).convert('RGBA')
        draw = ImageDraw.Draw(image)
        scale, (ox, oy) = preview.transform(size)
        for label, (x1, y1, x2, y2) in preview.rooms.items():
            index = int(label)
            rect = (round(x1 * scale + ox), round(y1 * scale + oy),
                    round(x2 * scale + ox), round(y2 * scale + oy))
            hovered = index == self.hovered_part
            selected = (index == self.section_index and self.focus == 4
                        and self.preview_keyboard_selection)
            current = index == self.current_section
            color = ('#f4d873' if hovered else '#63c8e5' if current else
                     '#eeeeee' if selected else '#b9b9b9')
            if hovered:
                image.paste(ImageEnhance.Brightness(image.crop(rect)).enhance(1.2), rect[:2])
            if hovered or current or selected:
                draw.rectangle((rect[0], rect[1], rect[2] - 1, rect[3] - 1), outline=color,
                               width=max(1, round(2 * scale)))
            cx1, cy1, cx2, cy2 = gallery_caption_rect((x1, y1, x2, y2), len(preview.rooms) == 1)
            caption_size = (max(1, round((cx2 - cx1) * scale)),
                            max(1, round((cy2 - cy1) * scale)))
            caption = gallery_caption(font, self.sections[index], caption_size, color, scale=0.75 * scale)
            image.paste(caption, (round(cx1 * scale + ox), round(cy1 * scale + oy)), caption)
        return image

    def map_layer(self, font, size=None):
        preview = self.map_preview
        left, top, right, bottom = self.control_rect(4)
        size = size or (right - left, bottom - top)
        image = preview.detail(size).convert('RGBA')
        draw = ImageDraw.Draw(image)
        scale, (ox, oy) = preview.transform(size)
        sx = sy = scale
        gold = '#f4d873'

        def room_rect(label):
            x1, y1, x2, y2 = preview.rooms[label]
            return (round(x1 * sx + ox), round(y1 * sy + oy),
                    round(x2 * sx + ox) - 1, round(y2 * sy + oy) - 1)

        markers = ([(preview.start, 'Start', (127, 223, 170))]
                   if preview.start in preview.rooms else [])
        markers += [(label, 'End', (255, 157, 122))
                    for label in sorted(preview.exits) if label in preview.rooms]
        if self.screen in preview.rooms and self.focus == 4 and self.preview_keyboard_selection:
            draw.rectangle(room_rect(self.screen), outline='#eeeeee', width=max(1, round(min(sx, sy))))
        if self.current_level == self.level_number and self.current_screen in preview.rooms:
            draw.rectangle(room_rect(self.current_screen), outline='#63c8e5',
                           width=max(1, round(min(sx, sy))))
        tooltip = None
        if self.hovered_screen in preview.rooms:
            label = self.hovered_screen
            x1, y1, x2, y2 = room_rect(label)
            rect = x1, y1, x2 + 1, y2 + 1
            image.paste(ImageEnhance.Brightness(image.crop(rect)).enhance(1.35), (x1, y1))
            draw.rectangle((x1, y1, x2, y2), outline=gold, width=max(1, round(2 * min(sx, sy))))
            caption = label if label.startswith('Room ') else f'Screen {label}'
            if label == preview.start:
                caption += ' - Start'
            if label in preview.exits:
                caption += ' - End'
            glyphs = font.text(caption, gold)
            width = min(round((glyphs.width + 12) * sx), size[0] - 1)
            tx = max(0, min((x1 + x2 - width) // 2, size[0] - width - 1))
            ty = y1 - round(20 * sy) if y1 >= round(20 * sy) else y2 + round(3 * sy)
            ty = min(ty, size[1] - round(19 * sy))
            ink = glyphs.getbbox()
            if ink:
                glyphs = glyphs.crop((0, ink[1], glyphs.width, ink[3]))
                glyphs = glyphs.resize((min(round(glyphs.width * sx), width - round(12 * sx)),
                                        max(1, round(glyphs.height * sy))), Image.Resampling.NEAREST)
                tooltip = (tx, ty, width, glyphs)
        overlay = Image.new('RGBA', size)
        marker_draw = ImageDraw.Draw(overlay)
        for label, caption, color in markers:
            x1, y1, x2, y2 = room_rect(label)
            active = (label == self.hovered_screen or
                      (self.current_level == self.level_number and label == self.current_screen) or
                      (self.focus == 4 and self.preview_keyboard_selection and label == self.screen))
            if not active:
                marker_draw.rectangle((x1, y1, x2, y2), outline=(*color, 85),
                                      width=max(1, round(scale)))
            glyphs = font.text(caption, '#%02x%02x%02x' % color)
            ink = glyphs.getbbox()
            if ink is None:
                continue
            glyphs = glyphs.crop(ink)
            pad = max(1, round(1.5 * scale))
            room_width = (preview.rooms[label][2] - preview.rooms[label][0]) * scale
            factor = min(0.46 * scale, max(1, room_width - pad * 4) / glyphs.width)
            glyphs = glyphs.resize((max(1, round(glyphs.width * factor)),
                                    max(1, round(glyphs.height * factor))), Image.Resampling.NEAREST)
            glyphs.putalpha(glyphs.getchannel('A').point(lambda alpha: round(alpha * 0.62)))
            x1 += pad
            top = y2 + 1 - glyphs.height - pad * 3 if caption == 'End' else y1 + pad
            marker_draw.rectangle((x1, top, x1 + glyphs.width + pad * 2, top + glyphs.height + pad * 2),
                                  fill=(12, 15, 13, 130))
            overlay.alpha_composite(glyphs, (x1 + pad, top + pad))
        image = Image.alpha_composite(image, overlay)
        draw = ImageDraw.Draw(image)
        if tooltip is not None:
            tx, ty, width, glyphs = tooltip
            draw.rectangle((tx, ty, tx + width, ty + round(18 * sy)),
                           fill='#181818', outline=gold, width=max(1, round(min(sx, sy))))
            image.paste(glyphs, (tx + round(6 * sx), ty + round(4 * sy)), glyphs)
        return image

    def present_map(self, frame, font):
        if not self.preview_enabled:
            return frame
        sx, sy = frame.width / VISIBLE_SIZE[0], frame.height / VISIBLE_SIZE[1]

        def projected(rect):
            left, top, right, bottom = rect
            return round((left - 1) * sx), round(top * sy), round((right - 1) * sx), round(bottom * sy)

        overlay = None
        if self.dropdown:
            x1, _y1, x2, y2 = self.control_rect(self.dropdown_control)
            rect = (x1, y2, x2 + 1, y2 + self.popup_count * self.OPTION_HEIGHT + 1)
            overlay_rect = projected(rect)
            overlay = frame.crop(overlay_rect)
        elif self.map_tooltip(font) is not None:
            _label, (x1, y1, x2, y2) = self.map_tooltip(font)
            overlay_rect = projected((x1, y1, x2 + 1, y2 + 1))
            overlay = frame.crop(overlay_rect)
        left, top, right, bottom = projected(self.control_rect(4))
        layer = self.gallery_layer if self.gallery_enabled else self.map_layer
        frame.paste(layer(font, (right - left, bottom - top)), (left, top))
        if overlay is not None:
            frame.paste(overlay, overlay_rect[:2])
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
