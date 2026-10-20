"""In-game commands and confirmation pages, drawn at the native resolution."""

from dataclasses import dataclass

from PIL import Image, ImageDraw

from pop2.game_ui import DevelopmentMenu, VISIBLE_SIZE, centered_panel


@dataclass(frozen=True)
class MenuItem:
    action: str
    label: str
    shortcut: str
    enabled: bool = True
    checked: bool | None = None


@dataclass
class GameMenu:
    sound: bool = True
    music: bool = True
    fullscreen: bool = False
    focus: int = 0
    page: str = "menu"
    return_to_menu: bool = True
    copy_protection: bool = True
    screenshot_scale: int = 3
    screenshot_folder: str = ""
    screenshot_status: str = ""
    error: str = ""
    dropdown: bool = False
    option_index: int = 0
    save_available: bool = True
    save_browser: object = None
    screenshot_gallery: object = None

    PANEL = centered_panel(384, 284)
    DIALOG = centered_panel(352, 166)
    ABOUT_DIALOG = centered_panel(352, 184)
    BUTTONS = ((100, DIALOG[1] + 120, 242, DIALOG[1] + 150),
               (254, DIALOG[1] + 120, 412, DIALOG[1] + 150))
    ABOUT_BUTTON = (190, ABOUT_DIALOG[1] + 120, 322, ABOUT_DIALOG[1] + 150)
    ROW_TOP = PANEL[1] + 36
    ROW_HEIGHT = 22
    SCREENSHOT_PANEL = centered_panel(352, 230)
    CAPTURE_CONTROLS = ((212, SCREENSHOT_PANEL[1] + 44, 412, SCREENSHOT_PANEL[1] + 72),
                        (100, SCREENSHOT_PANEL[1] + 88, 412, SCREENSHOT_PANEL[1] + 116),
                        (100, SCREENSHOT_PANEL[1] + 158, 250, SCREENSHOT_PANEL[1] + 190),
                        (264, SCREENSHOT_PANEL[1] + 158, 412, SCREENSHOT_PANEL[1] + 190))
    CAPTURE_SIZES = tuple(f"{scale}x ({VISIBLE_SIZE[0] * scale} x {VISIBLE_SIZE[1] * scale})"
                          for scale in range(1, 5))

    @property
    def items(self):
        return (
            MenuItem("resume", "Resume", "F1"),
            MenuItem("confirm_new", "New game", "Alt+N"),
            MenuItem("restart", "Restart level", "Alt+R"),
            MenuItem("save", "Save game", "Alt+S", self.save_available),
            MenuItem("open", "Load game", "Alt+O"),
            MenuItem("sound", "Sound", "Alt+T", checked=self.sound),
            MenuItem("music", "Ambient music", "Alt+M", checked=self.music),
            MenuItem("hall", "Hall of Fame", "Alt+H", False),
            MenuItem("about", "About", "Alt+V"),
            MenuItem("fullscreen", "Fullscreen", "Alt+Enter", checked=self.fullscreen),
            MenuItem("copy_protection", "Copy protection", "", checked=self.copy_protection),
        )

    def show_page(self, page):
        self.return_to_menu = self.page == "menu"
        self.page = page
        self.focus = 0
        self.dropdown = False
        self.error = self.screenshot_status = ""

    def back(self):
        if not self.return_to_menu:
            return "close"
        self.page = "menu"
        self.focus = 0
        self.dropdown = False
        return "changed"

    def activate(self):
        if self.page == 'screenshots' and self.screenshot_gallery is not None:
            return self.screenshot_gallery.activate()
        if self.page == 'saves':
            return self.save_browser.activate()
        if self.page == "screenshots":
            if self.focus == 0:
                self.dropdown = True
                self.option_index = self.screenshot_scale - 1
                return "changed"
            return self.back() if self.focus == 3 else {1: "screenshot_folder", 2: "screenshot"}[self.focus]
        if self.page == "confirm":
            return "new_game" if self.focus == 1 else self.back()
        if self.page == "about":
            return self.back()
        item = self.items[self.focus]
        return item.action if item.enabled else "changed"

    def key(self, key, backwards=False, char='', control=False):
        if self.page == 'screenshots' and self.screenshot_gallery is not None:
            return self.screenshot_gallery.key(key, backwards, char, control)
        if self.page == 'saves':
            return self.save_browser.key(key, backwards, char, control)
        if self.page == "screenshots":
            if key == "Escape":
                if self.dropdown:
                    self.dropdown = False
                    return "changed"
                return self.back()
            if key == "Tab":
                self.dropdown = False
                self.focus = (self.focus + (-1 if backwards else 1)) % 4
                return "changed"
            if self.dropdown:
                if key in ("Up", "Down", "Left", "Right"):
                    self.option_index = (self.option_index + (-1 if key in ("Up", "Left") else 1)) % 4
                elif key in ("Return", "KP_Enter", "space"):
                    self.screenshot_scale = self.option_index + 1
                    self.dropdown = False
            elif key in ("Up", "Down"):
                delta = -1 if key == "Up" else 1
                self.focus = (self.focus + delta) % 4
            elif key in ("Left", "Right") and self.focus == 0:
                self.screenshot_scale = (self.screenshot_scale - 1 + (-1 if key == "Left" else 1)) % 4 + 1
            elif key in ("Left", "Right") and self.focus in (2, 3):
                self.focus = 2 if key == "Left" else 3
            elif key in ("Return", "KP_Enter", "space"):
                return self.activate()
            return "changed"
        if key == "Escape":
            return "close" if self.page == "menu" else self.back()
        if key in ("Return", "KP_Enter", "space"):
            return self.activate()
        if self.page == "menu":
            if key in ("Up", "Down", "Tab"):
                delta = -1 if key == "Up" or key == "Tab" and backwards else 1
                self.focus = (self.focus + delta) % len(self.items)
        elif self.page == "confirm":
            if key in ("Left", "Right"):
                self.focus = 0 if key == "Left" else 1
            elif key in ("Up", "Down", "Tab"):
                self.focus = 1 - self.focus
        return "changed"

    def row_rect(self, index):
        top = self.ROW_TOP + index * self.ROW_HEIGHT
        return (80, top, 432, top + self.ROW_HEIGHT - 2)

    def hit(self, x, y):
        if self.page == 'screenshots' and self.screenshot_gallery is not None:
            return self.screenshot_gallery.hit(x, y)
        if self.page == 'saves':
            return self.save_browser.hit(x, y)
        if self.page == "screenshots":
            if self.dropdown:
                left, _top, right, bottom = self.CAPTURE_CONTROLS[0]
                if left <= x < right and bottom <= y < bottom + 4 * self.ROW_HEIGHT:
                    return int((y - bottom) // self.ROW_HEIGHT)
                return None
            return next((i for i, rect in enumerate(self.CAPTURE_CONTROLS)
                         if DevelopmentMenu.contains(rect, x, y)), None)
        rects = ([self.row_rect(i) for i in range(len(self.items))]
                 if self.page == "menu" else self.BUTTONS if self.page == "confirm"
                 else (self.ABOUT_BUTTON,))
        return next((i for i, rect in enumerate(rects)
                     if DevelopmentMenu.contains(rect, x, y)), None)

    def hover(self, x, y):
        if self.page == 'screenshots' and self.screenshot_gallery is not None:
            return self.screenshot_gallery.hover(x, y)
        if self.page == 'saves':
            return self.save_browser.hover(x, y)
        index = self.hit(x, y)
        field = "option_index" if self.page == "screenshots" and self.dropdown else "focus"
        if index is None or index == getattr(self, field):
            return False
        setattr(self, field, index)
        return True

    def click(self, x, y):
        if self.page == 'screenshots' and self.screenshot_gallery is not None:
            return self.screenshot_gallery.click(x, y)
        if self.page == 'saves':
            return self.save_browser.click(x, y)
        index = self.hit(x, y)
        if self.page == "screenshots" and self.dropdown:
            if index is not None:
                self.screenshot_scale = index + 1
            self.dropdown = False
            return "changed"
        if index is None:
            return "changed"
        self.focus = index
        return self.activate()

    def draw(self, viewport, font):
        if self.page == 'screenshots' and self.screenshot_gallery is not None:
            return self.screenshot_gallery.draw(viewport, font)
        if self.page == 'saves':
            return self.save_browser.draw(viewport, font)
        image = Image.alpha_composite(viewport, Image.new("RGBA", viewport.size, (0, 0, 0, 100)))
        draw = ImageDraw.Draw(image)
        gold, white, muted = "#f4d873", "#eeeeee", "#999999"

        def text(value, x, y, color=white, align="left", max_width=None):
            glyphs = font.text(value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            ink = glyphs.getbbox()
            if align == "center":
                x -= glyphs.width // 2
            elif align == "right":
                x -= glyphs.width
            image.paste(glyphs, (x, y - (ink[1] if ink else 0)), glyphs)

        def button(rect, label, selected):
            draw.rectangle(rect, fill="#303030" if selected else "#222222",
                           outline=gold if selected else "#626262")
            text(label, (rect[0] + rect[2]) // 2, rect[1] + 10, align="center",
                 max_width=rect[2] - rect[0] - 12)

        panel = self.SCREENSHOT_PANEL if self.page == "screenshots" else self.PANEL if self.page == "menu" else (
            self.ABOUT_DIALOG if self.page == "about" else self.DIALOG)
        draw.rectangle(panel,
                       fill="#181818", outline="#858585")
        panel_top = panel[1]
        if self.page == "screenshots":
            text("Screenshots", 256, panel_top + 18, gold, "center")
            text("PNG size", 100, panel_top + 52)
            left, top, right, bottom = self.CAPTURE_CONTROLS[0]
            draw.rectangle((left, top, right, bottom), fill="#303030" if self.focus == 0 else "#222222",
                           outline=gold if self.focus == 0 else "#626262")
            text(self.CAPTURE_SIZES[self.screenshot_scale - 1], left + 10, top + 9, max_width=right - left - 34)
            draw.polygon(((right - 15, top + 12), (right - 7, top + 12),
                          (right - 11, top + 16)), fill=white)
            button(self.CAPTURE_CONTROLS[1], "Choose folder...", self.focus == 1)
            encoded = self.screenshot_folder.replace("\\", "/").encode("mac_roman", errors="replace")
            encoded = bytes(code if code in font.glyphs else 63 for code in encoded)
            widths = [font.glyphs[code][2] for code in encoded]
            width, start = sum(widths), 0
            if width > 312:
                limit = 312 - font.text("...").width
                while width > limit and start < len(widths):
                    width -= widths[start]
                    start += 1
            text(("..." if start else "") + encoded[start:].decode("mac_roman"), 100, panel_top + 126, muted)
            button(self.CAPTURE_CONTROLS[2], "Save PNG", self.focus == 2)
            button(self.CAPTURE_CONTROLS[3], "Back" if self.return_to_menu else "Close", self.focus == 3)
            if self.error or self.screenshot_status:
                text(self.error or self.screenshot_status, 100, panel_top + 202,
                     "#ff9b9b" if self.error else gold, max_width=312)
            if self.dropdown:
                left, _top, right, bottom = self.CAPTURE_CONTROLS[0]
                draw.rectangle((left, bottom, right, bottom + 4 * self.ROW_HEIGHT),
                               fill="#222222", outline=gold)
                for index, label in enumerate(self.CAPTURE_SIZES):
                    y = bottom + index * self.ROW_HEIGHT
                    if index == self.option_index:
                        draw.rectangle((left + 1, y + 1, right - 1, y + self.ROW_HEIGHT - 1), fill="#454545")
                    text(label, left + 8, y + 6,
                         gold if index == self.screenshot_scale - 1 else white, max_width=right - left - 16)
        elif self.page == "confirm":
            text("New game?", 256, panel_top + 20, gold, "center")
            text("Restart the game?", 256, panel_top + 57, align="center")
            text("Unsaved progress will be lost.", 256, panel_top + 79, muted, "center", 312)
            for i, (rect, label) in enumerate(zip(self.BUTTONS, ("Cancel", "New game"))):
                button(rect, label, i == self.focus)
        elif self.page == "about":
            text("Prince of Persia 2", 256, panel_top + 20, gold, "center", 312)
            text("Macintosh Native", 256, panel_top + 46, align="center")
            text("Work in progress", 256, panel_top + 78, muted, "center")
            button(self.ABOUT_BUTTON, "Back" if self.return_to_menu else "Close", True)
            text("by Pessegos", 420, panel_top + 162, muted, "right")
        else:
            text("Game Menu", 256, panel_top + 14, gold, "center")
            for i, item in enumerate(self.items):
                rect = self.row_rect(i)
                selected = i == self.focus
                draw.rectangle(rect, fill="#303030" if selected else "#222222",
                               outline=gold if selected else "#404040")
                color = white if item.enabled else muted
                x, y = rect[0] + 10, rect[1] + 5
                if item.checked is not None:
                    draw.rectangle((x, y, x + 10, y + 10), fill="#121212", outline=muted)
                    if item.checked:
                        draw.line(((x + 2, y + 5), (x + 4, y + 8), (x + 8, y + 2)),
                                  fill=gold, width=2)
                    x += 20
                text(item.label, x, y, color, max_width=204)
                # The game's NFNT replaces '+' with a trademark glyph.
                text(item.shortcut.replace("+", "-"), rect[2] - 10, y, color, "right", 100)
            if not self.items[self.focus].enabled:
                text("Save unavailable right now" if self.items[self.focus].action == 'save'
                     else "Not implemented yet", 256, panel[3] + 5, muted, "center")
        return image
