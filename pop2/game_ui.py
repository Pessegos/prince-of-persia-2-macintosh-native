import struct
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageEnhance

from pop2 import menu_theme
from pop2.menu_theme import c


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


def fit_menu_viewport(width, height):
    """Use wide windows for UI, keeping a usable minimum aspect in tall ones."""
    width, height = max(1, width), max(1, height)
    if width * 384 < height * 510:
        return fit_viewport(width, height)
    return (width, height), (0, 0)


def menu_viewport_point(x, y, width, height):
    size, origin = fit_menu_viewport(width, height)
    if not (origin[0] <= x < origin[0] + size[0]
            and origin[1] <= y < origin[1] + size[1]):
        return None
    scale = size[1] / 384
    return 1 + (x - origin[0]) / scale, (y - origin[1]) / scale


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
    level_available: bool = True
    dropdown_control: int = 0
    level_options: tuple = ()
    level_index: int = 0
    map_provider: object = None
    hovered_screen: str | None = None
    map_open: bool = False
    hovered_control: int | None = None
    return_screens: dict = field(default_factory=dict)
    current_level: int | None = None
    current_screen: str | None = None
    preview_keyboard_selection: bool = False
    god_mode: bool = False
    # Finished map pictures by size: the native menu and the HD view each keep one.
    map_layers: dict = field(default_factory=dict, repr=False, compare=False)
    # The plain map on the theme's ground by size, before any marker or highlight.
    map_bases: dict = field(default_factory=dict, repr=False, compare=False)
    # How many units across the map page is: a window wider than 4:3 gets a wider
    # page (set by the window), the map growing to fill it. The tools hub stays 510.
    page_width: int = 510

    CONTROLS = ((200, 138, 392, 166), (120, 180, 392, 210),
                (120, 231, 252, 263), (264, 231, 392, 263))
    LEVEL_CONTROLS = {0: (200, 138, 392, 166), 1: (120, 220, 392, 246),
                      2: (120, 282, 252, 314), 3: (264, 282, 392, 314),
                      4: (200, 179, 392, 207)}
    # Control templates use this reference panel; each page is positioned as a unit.
    PANEL = (100, 70, 412, 350)
    OPTION_HEIGHT = 19
    MAP_CONTROLS = {
        7: (12, 14, 38, 40), 5: (130, 14, 156, 40),
        0: (164, 14, 348, 40), 6: (356, 14, 382, 40),
        4: (12, 52, 500, 330), 1: (12, 348, 308, 372),
        2: (316, 348, 392, 372), 3: (400, 348, 500, 372),
    }
    GAME_CONTROLS = {4: (120, 128, 392, 164), 8: (120, 172, 392, 208),
                     1: (120, 216, 252, 246), 11: (264, 216, 392, 246),
                     3: (120, 270, 392, 300)}

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
    def preview_enabled(self):
        return self.map_enabled

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

    def field_options(self, control):
        if self.page == 'tools' and self.level_options:
            return (tuple(option[1] for option in self.level_options) if control == 0
                    else self.screen_options)
        return self.screens

    @property
    def screen_options(self):
        return self.level_options[self.level_index][2] if self.level_options else self.screens

    @property
    def level_number(self):
        return self.level_options[self.level_index][0] if self.level_options else None

    def field_selected_index(self, control):
        if self.page == 'tools' and self.level_options:
            return self.level_index if control == 0 else self.screen_index
        return self.screen_index

    @property
    def options(self):
        return self.field_options(self.dropdown_control if self.dropdown else self.focus)

    @property
    def selected_index(self):
        return self.field_selected_index(self.dropdown_control if self.dropdown else self.focus)

    @property
    def map_width(self):
        """Units across the page the map is shown on (510 but for a wide window's map)."""
        return max(510, self.page_width) if self.map_enabled else 510

    def control_rect(self, index):
        if self.map_enabled:
            left, top, right, bottom = self.MAP_CONTROLS[index]
            extra = self.map_width - 510
            # A wide page keeps the classic arrangement: the back arrow and Return at
            # the left, the level's controls centred, Go and Resume at the right edge,
            # and the map between the toolbar and the footer as wide as the page.
            shift = {5: extra // 2, 0: extra // 2, 6: extra // 2, 2: extra, 3: extra}.get(index, 0)
            if index == 4:
                return self.map_area(self.map_width)
            return left + shift, top, right + shift, bottom
        if self.page == 'tools' and (self.map_available or not self.level_available):
            return self.position_rect(self.GAME_CONTROLS[index])
        if self.page == 'tools' and self.level_options:
            rect = self.LEVEL_CONTROLS[index]
        else:
            rect = self.CONTROLS[index]
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
        if self.map_enabled:
            return tuple(control for control in (7, 5, 0, 6, 4, 1, 2, 3)
                         if (control not in (5, 6) or len(self.level_options) > 1)
                         and (control != 1 or self.return_screen is not None))
        if self.map_available:
            return (4, 8, 1, 11, 3)
        if self.page == 'tools' and not self.level_available:
            return (8, 3)
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
        self.preview_keyboard_selection = False
        self.focus = self.controls[0]
        self.error = ""

    @property
    def screen(self):
        return self.screen_options[self.screen_index]

    def open_dropdown(self):
        if self.map_available and self.focus == 4:
            return
        self.hovered_screen = None
        self.dropdown_control = self.focus
        self.dropdown = True
        self.option_index = self.selected_index
        self.center_popup()

    def center_popup(self):
        count = self.popup_count
        self.popup_start = max(0, min(self.option_index - count // 2, len(self.options) - count))

    def scroll(self, delta, point=None):
        """Move the open list's rows; the highlight stays on the row under the pointer."""
        if not self.dropdown:
            return False
        before = self.popup_start, self.option_index
        self.popup_start = max(0, min(self.popup_start + delta, len(self.options) - self.popup_count))
        index = self.hit(*point) if point is not None else None
        if index is not None:
            self.option_index = index
        return (self.popup_start, self.option_index) != before

    def popup_rect(self):
        """The open list's box in menu coordinates, its outline included."""
        x1, _y1, x2, y2 = self.control_rect(self.dropdown_control)
        return x1, y2, x2 + 1, y2 + self.popup_count * self.OPTION_HEIGHT + 1

    def map_area(self, width=510):
        """The map's box on a map page ``width`` units across."""
        left, top, right, bottom = self.MAP_CONTROLS[4]
        return left, top, right + max(510, width) - 510, bottom

    def projected_rect(self, rect, size, width=None):
        """A menu rectangle in the pixels of a visible frame of this size (of a page
        ``width`` units across; the page shown, by default)."""
        sx, sy = size[0] / (width or self.map_width), size[1] / VISIBLE_SIZE[1]
        left, top, right, bottom = rect
        return round((left - 1) * sx), round(top * sy), round((right - 1) * sx), round(bottom * sy)

    def select(self, index):
        self.preview_keyboard_selection = False
        if (self.page == 'tools' and self.level_options
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
        elif key in ('Left', 'Right') and self.map_available and self.focus in (1, 11):
            self.focus = 1 if key == 'Left' else 11
        elif key in ("Return", "KP_Enter", "space"):
            return self.activate()
        return "changed"

    def activate(self):
        if self.focus not in self.controls:
            return "changed"
        if self.focus == 11 and self.map_available and not self.map_enabled:
            self.god_mode = not self.god_mode
            return 'god_mode'
        if self.focus == 8:
            return 'cutscenes'
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
            left, _top, right, bottom = self.control_rect(self.dropdown_control)
            popup = (left, bottom, right, bottom + self.popup_count * self.OPTION_HEIGHT)
            if self.contains(popup, x, y):
                return self.popup_start + int((y - bottom) // self.OPTION_HEIGHT)
            return None
        return next((i for i in self.controls if self.contains(self.control_rect(i), x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
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
        if self.map_width != 510:
            # The wide map page is drawn over all of itself: it needs no picture under it.
            image = Image.new('RGBA', (self.map_width + 2, viewport.height), (0, 0, 0, 255))
        else:
            image = menu_theme.ground(viewport, None if self.map_enabled else self.panel_rect)
        draw = ImageDraw.Draw(image)
        gold, white, muted = c("#f4d873"), c("#eeeeee"), c("#b9b9b9")
        offset = self.layout_offset
        # y is where the capitals start, so that every label stands on the same
        # baseline: "l" and "f" are a pixel taller than the capitals.
        capitals = font.text('H').getbbox()[1]

        def text(value, x, y, color=white, centered=False, max_width=None):
            glyphs = font.text(value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            image.paste(glyphs, (int(x - glyphs.width // 2) if centered else x, y - capitals), glyphs)

        if self.map_enabled:
            self.draw_map(image, draw, font, text)
            self.draw_popup(draw, text)
            return image
        text('Developer Tools', 256, 87 + offset, gold, centered=True)
        if self.page == 'tools' and (self.map_available or not self.level_available):
            self.draw_game_tools(draw, text)
            menu_theme.watermark(image, self.panel_rect)
            return image
        text("Level" if self.level_options else "Screen", 120, 147 + offset)
        if self.level_options:
            text("Screen", 120, 188 + offset)
        for i in self.controls:
            rect = self.control_rect(i)
            draw.rectangle(rect, fill=c("#303030") if i == self.focus else c("#222222"),
                           outline=gold if i == self.focus else c("#626262"))
        for control in ((0, 4) if self.level_options else (0,)):
            left, top, right, _bottom = self.control_rect(control)
            text(self.field_options(control)[self.field_selected_index(control)],
                 left + 10, top + 9, max_width=right - left - 34)
            draw.polygon(((right - 15, top + 12), (right - 7, top + 12),
                          (right - 11, top + 16)), fill=white)
        text("Go to screen", 186, self.control_rect(2)[1] + 11, centered=True, max_width=118)
        checkbox_y = self.control_rect(1)[1] + (8 if self.level_options else 9)
        draw.rectangle((130, checkbox_y, 141, checkbox_y + 11), fill=c("#121212"), outline=muted)
        if self.peaceful:
            draw.line(((132, checkbox_y + 5), (135, checkbox_y + 8),
                       (139, checkbox_y + 2)), fill=gold, width=2)
        text("Peaceful (no guards)", 151, checkbox_y + 1, max_width=231)
        text("Resume", 328, self.control_rect(3)[1] + 11, centered=True)
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
            error_y = (319 if compact else 278) + offset
            line_limit = 2 if compact else 3
            for i, line in enumerate(lines[:line_limit]):
                text(line, 120, error_y + i * 14, c("#ff9b9b"), max_width=272)
        menu_theme.watermark(image, self.panel_rect)
        self.draw_popup(draw, text)
        return image

    def draw_game_tools(self, draw, text):
        gold = c('#f4d873')
        for control in self.controls:
            draw.rectangle(self.control_rect(control),
                           fill=c('#303030') if self.focus == control else c('#222222'),
                           outline=gold if self.focus == control else c('#626262'))
        for control, label in ((4, 'Open map'), (8, 'Cutscene Viewer')):
            if control not in self.controls:
                continue
            left, top, right, bottom = self.control_rect(control)
            cy = (top + bottom) // 2
            text(label, 246, cy - 5, centered=True, max_width=220)
            draw.line(((right - 23, cy - 5), (right - 18, cy),
                       (right - 23, cy + 5)), fill=gold, width=2)
        for control, label, checked in ((1, 'Peaceful', self.peaceful), (11, 'God mode', self.god_mode)):
            if control not in self.controls:
                continue
            left, top, right, _bottom = self.control_rect(control)
            draw.rectangle((left + 10, top + 9, left + 21, top + 20),
                           fill=c('#121212'), outline=c('#b9b9b9'))
            if checked:
                draw.line(((left + 12, top + 14), (left + 15, top + 17), (left + 19, top + 11)),
                          fill=gold, width=2)
            text(label, left + 31, top + 10, max_width=right - left - 39)
        text('Resume', 256, self.control_rect(3)[1] + 10, centered=True)

    def draw_map(self, image, draw, font, text):
        gold, white = c('#f4d873'), c('#eeeeee')
        width = self.map_width
        extra = width - 510
        draw.rectangle((1, 0, width, 383), fill=c('#101010'))
        draw.line((12, 47, width - 10, 47), fill=c('#383838'))
        draw.line((12, 340, width - 10, 340), fill=c('#383838'))
        for control in (7, 5, 0, 6, 1, 2, 3):
            if control not in self.controls and control != 1:
                continue
            rect = self.control_rect(control)
            draw.rectangle(rect, fill=c('#303030') if self.focus == control else c('#222222'),
                           outline=gold if self.focus == control else c('#626262'))
        left, top, right, _bottom = self.control_rect(0)
        text(self.field_options(0)[self.level_index], 250 + extra // 2, top + 8,
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
        text(label, 160, 355, white if destination is not None else c('#777777'),
             centered=True, max_width=256)
        text('Go', 354 + extra, 355, centered=True, max_width=64)
        text('Resume', 450 + extra, 355, centered=True, max_width=88)
        if self.error:
            # Just above the line, on the ground: drawn across it, the line struck it through.
            # The tail of an "f" ends a pixel above the line.
            draw.rectangle((12, 325, width - 10, 339), fill=c('#101010'))
            text(self.error, 12, 326, c('#ff9b9b'), max_width=width - 22)
        tooltip = self.map_tooltip(font)
        if tooltip is not None:
            label, rect = tooltip
            draw.rectangle(rect, fill=c('#181818'), outline=gold)
            text(label, rect[0] + 6, rect[1] + 4, gold)

    def map_tooltip(self, font):
        labels = {5: 'Previous level', 6: 'Next level', 7: 'Developer Tools'}
        if self.dropdown or self.hovered_control not in labels:
            return None
        label = labels[self.hovered_control]
        x1, _y1, _x2, y2 = self.control_rect(self.hovered_control)
        width = font.text(label).width + 12
        x1 = min(x1, self.map_width - 10 - width)
        y1 = y2 + 3 if y2 < 300 else self.control_rect(self.hovered_control)[1] - 22
        return label, (x1, y1, x1 + width, y1 + 18)

    def map_layer(self, font, size=None):
        preview = self.map_preview
        left, top, right, bottom = self.control_rect(4)
        size = size or (right - left, bottom - top)
        # Everything the picture shows; scrolling a list over it changes none of it.
        key = (font, menu_theme.current(), self.screen,
               self.focus == 4 and self.preview_keyboard_selection,
               self.current_level == self.level_number and self.current_screen, self.hovered_screen)
        cached = self.map_layers.get(size)
        if cached is not None and cached[0] is preview and cached[1] == key:
            return cached[2]
        decor = []
        image = self.draw_map_layer(preview, font, size, decor)
        if size not in self.map_layers and len(self.map_layers) >= 2:
            del self.map_layers[next(iter(self.map_layers))]
        self.map_layers[size] = preview, key, image, tuple(decor)
        return image

    def map_layer_entry(self, frame_size):
        """The finished map picture shown in a visible frame of this size, if any."""
        if not self.map_enabled:
            return None
        left, top, right, bottom = self.projected_rect(self.control_rect(4), frame_size)
        return self.map_layers.get((right - left, bottom - top))

    @staticmethod
    def map_layer_damage(before, after):
        """Where two map pictures can differ, or None when it may be anywhere.

        Each picture lists the rectangles its highlights, outlines and tooltip
        cover; everything else is the same plain map when the level, font and
        theme are the same.
        """
        if before is after:
            return ()
        if before is None or after is None or before[0] is not after[0] or before[1][:2] != after[1][:2]:
            return None
        return before[3] + after[3]

    def draw_map_layer(self, preview, font, size, decor=None):
        decor = [] if decor is None else decor
        scale, (ox, oy) = preview.transform(size)
        sx = sy = scale
        gold = c('#f4d873')

        def room_rect(label):
            x1, y1, x2, y2 = preview.rooms[label]
            return (round(x1 * sx + ox), round(y1 * sy + oy),
                    round(x2 * sx + ox) - 1, round(y2 * sy + oy) - 1)

        ground = c('#101010')
        base = self.map_bases.get(size)
        if base is None or base[0] is not preview or base[1] != ground:
            image = preview.detail(size).convert('RGBA')
            if ground != '#101010':
                # The map picture is built (and kept on disk) on neutral grey. Under a
                # theme, stand its rooms on the theme's own ground instead.
                themed = Image.new('RGBA', image.size, ground)
                for label in preview.rooms:
                    x1, y1, x2, y2 = room_rect(label)
                    themed.paste(image.crop((x1, y1, x2 + 1, y2 + 1)), (x1, y1))
                image = themed
            if size not in self.map_bases and len(self.map_bases) >= 2:
                del self.map_bases[next(iter(self.map_bases))]
            base = self.map_bases[size] = preview, ground, image
        image = base[2].copy()
        draw = ImageDraw.Draw(image)

        start_labels = preview.starts | {preview.start}
        markers = [(label, 'Start', (127, 223, 170))
                   for label in sorted(label for label in start_labels if label in preview.rooms)]
        markers += [(label, 'End', (255, 157, 122))
                    for label in sorted(preview.exits) if label in preview.rooms]
        for label in (self.screen if self.focus == 4 and self.preview_keyboard_selection else None,
                      self.current_screen if self.current_level == self.level_number else None,
                      self.hovered_screen):
            if label in preview.rooms:
                x1, y1, x2, y2 = room_rect(label)
                decor.append((x1, y1, x2 + 1, y2 + 1))
        if self.screen in preview.rooms and self.focus == 4 and self.preview_keyboard_selection:
            draw.rectangle(room_rect(self.screen), outline=c('#eeeeee'), width=max(1, round(min(sx, sy))))
        if self.current_level == self.level_number and self.current_screen in preview.rooms:
            draw.rectangle(room_rect(self.current_screen), outline=c('#63c8e5'),
                           width=max(1, round(min(sx, sy))))
        tooltip = None
        if self.hovered_screen in preview.rooms:
            label = self.hovered_screen
            x1, y1, x2, y2 = room_rect(label)
            rect = x1, y1, x2 + 1, y2 + 1
            image.paste(ImageEnhance.Brightness(image.crop(rect)).enhance(1.35), (x1, y1))
            draw.rectangle((x1, y1, x2, y2), outline=gold, width=max(1, round(2 * min(sx, sy))))
            caption = label
            if label in start_labels:
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
        marked = {}  # each marked room's drawn box: only these are blended below

        def mark(label, box):
            old = marked.get(label, box)
            marked[label] = (min(old[0], box[0]), min(old[1], box[1]),
                             max(old[2], box[2]), max(old[3], box[3]))

        for label, caption, color in markers:
            x1, y1, x2, y2 = room_rect(label)
            mark(label, (x1, y1, x2 + 1, y2 + 1))
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
            mark(label, (x1, top, x1 + glyphs.width + pad * 2 + 1, top + glyphs.height + pad * 2 + 1))
            overlay.alpha_composite(glyphs, (x1 + pad, top + pad))
        boxes = [(max(0, x1), max(0, y1), min(size[0], x2), min(size[1], y2))
                 for x1, y1, x2, y2 in marked.values()]
        boxes = [box for box in boxes if box[0] < box[2] and box[1] < box[3]]
        if any(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
               for i, a in enumerate(boxes) for b in boxes[i + 1:]):
            image = Image.alpha_composite(image, overlay)
        else:
            # The overlay is clear everywhere else: blend only the marked rooms.
            for box in boxes:
                image.alpha_composite(overlay, box[:2], box)
        draw = ImageDraw.Draw(image)
        if tooltip is not None:
            tx, ty, width, glyphs = tooltip
            decor.append((tx, ty, tx + width + 1, ty + round(18 * sy) + 1))
            draw.rectangle((tx, ty, tx + width, ty + round(18 * sy)),
                           fill=c('#181818'), outline=gold, width=max(1, round(min(sx, sy))))
            image.paste(glyphs, (tx + round(6 * sx), ty + round(4 * sy)), glyphs)
        return image

    def present_map(self, frame, font):
        if not self.preview_enabled:
            return frame
        def projected(rect):
            return self.projected_rect(rect, frame.size)

        overlay = None
        if self.dropdown:
            overlay_rect = projected(self.popup_rect())
            overlay = frame.crop(overlay_rect)
        elif self.map_tooltip(font) is not None:
            _label, (x1, y1, x2, y2) = self.map_tooltip(font)
            overlay_rect = projected((x1, y1, x2 + 1, y2 + 1))
            overlay = frame.crop(overlay_rect)
        left, top, right, bottom = projected(self.control_rect(4))
        frame.paste(self.map_layer(font, (right - left, bottom - top)), (left, top))
        if overlay is not None:
            frame.paste(overlay, overlay_rect[:2])
        return frame

    def draw_popup(self, draw, text):
        gold, white, muted = c('#f4d873'), c('#eeeeee'), c('#b9b9b9')
        if self.dropdown:
            left, _top, right, bottom = self.control_rect(self.dropdown_control)
            count = self.popup_count
            draw.rectangle((left, bottom, right, bottom + count * self.OPTION_HEIGHT),
                           fill=c("#222222"), outline=gold)
            for i in range(self.popup_start, self.popup_start + count):
                label = self.options[i]
                y = bottom + (i - self.popup_start) * self.OPTION_HEIGHT
                if i == self.option_index:
                    draw.rectangle((left + 1, y + 1, right - 1, y + self.OPTION_HEIGHT - 1),
                                   fill=c("#454545"))
                text(label, left + 10, y + 5, gold if i == self.selected_index else white,
                     max_width=right - left - 20)
            if len(self.options) > count:
                track = count * self.OPTION_HEIGHT - 4
                thumb = max(8, track * count // len(self.options))
                top = bottom + 2 + (track - thumb) * self.popup_start // (len(self.options) - count)
                draw.rectangle((right - 5, bottom + 2, right - 3, bottom + track + 1), fill=c("#454545"))
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
        self.drawn = {}

    # Lines kept drawn: a menu page draws all its labels again for each option the pointer
    # reaches, and drawing one letter by letter took most of the page's time.
    KEPT_LINES = 512

    def text(self, text, color=(255, 255, 85, 255)):
        """The line drawn in ``color`` on a transparent strip as tall as the font. Each call
        gives its own picture, which the caller may change."""
        key = text, color
        drawn = self.drawn.get(key)
        if drawn is None:
            drawn = self.draw_line(text, color)
            if len(self.drawn) >= self.KEPT_LINES:
                del self.drawn[next(iter(self.drawn))]
            self.drawn[key] = drawn
        return drawn.copy()

    def draw_line(self, text, color):
        glyphs = [self.glyphs[code] for code in text.encode("mac_roman")]
        image = Image.new("RGBA", (sum(glyph[2] for glyph in glyphs), self.height))
        x = 0
        for mask, offset, advance in glyphs:
            image.paste(color, (x + offset, 0), mask)
            x += advance
        return image
