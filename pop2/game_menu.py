"""In-game commands and confirmation pages, drawn at the native resolution."""

from dataclasses import dataclass

from PIL import Image, ImageDraw

from pop2.game_ui import DevelopmentMenu


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
    development: bool = True
    focus: int = 0
    page: str = "menu"
    return_to_menu: bool = True

    PANEL = (64, 28, 448, 356)
    DIALOG = (80, 108, 432, 274)
    ABOUT_DIALOG = (80, 108, 432, 292)
    BUTTONS = ((100, 228, 242, 258), (254, 228, 412, 258))
    ROW_TOP = 64
    ROW_HEIGHT = 22

    @property
    def items(self):
        return (
            MenuItem("resume", "Resume", "F1"),
            MenuItem("confirm_new", "New game", "Alt+N"),
            MenuItem("restart", "Restart level", "Alt+R"),
            MenuItem("save", "Save game", "Alt+S", False),
            MenuItem("open", "Open game", "Alt+O", False),
            MenuItem("sound", "Sound", "Alt+T", checked=self.sound),
            MenuItem("music", "Ambient music", "Alt+M", checked=self.music),
            MenuItem("end", "End game", "Alt+E", False),
            MenuItem("hall", "Hall of Fame", "Alt+H", False),
            MenuItem("about", "About", "Alt+V"),
            MenuItem("fullscreen", "Fullscreen", "Alt+Enter", checked=self.fullscreen),
            MenuItem("development", "Dev Mode", "F2", self.development),
        )

    def show_page(self, page):
        self.return_to_menu = self.page == "menu"
        self.page = page
        self.focus = 0

    def back(self):
        if not self.return_to_menu:
            return "close"
        self.page = "menu"
        self.focus = 0
        return "changed"

    def activate(self):
        if self.page == "confirm":
            return "new_game" if self.focus == 1 else self.back()
        if self.page == "about":
            return self.back()
        item = self.items[self.focus]
        return item.action if item.enabled else "changed"

    def key(self, key, backwards=False):
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
        rects = ([self.row_rect(i) for i in range(len(self.items))]
                 if self.page == "menu" else self.BUTTONS if self.page == "confirm"
                 else ((190, 228, 322, 258),))
        return next((i for i, rect in enumerate(rects)
                     if DevelopmentMenu.contains(rect, x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        if index is None or index == self.focus:
            return False
        self.focus = index
        return True

    def click(self, x, y):
        index = self.hit(x, y)
        if index is None:
            return "changed"
        self.focus = index
        return self.activate()

    def draw(self, viewport, font):
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

        panel = self.PANEL if self.page == "menu" else (
            self.ABOUT_DIALOG if self.page == "about" else self.DIALOG)
        draw.rectangle(panel,
                       fill="#181818", outline="#858585")
        if self.page == "confirm":
            text("New game?", 256, 128, gold, "center")
            text("Restart the game?", 256, 165, align="center")
            text("Unsaved progress will be lost.", 256, 187, muted, "center", 312)
            for i, (rect, label) in enumerate(zip(self.BUTTONS, ("Cancel", "New game"))):
                button(rect, label, i == self.focus)
        elif self.page == "about":
            text("Prince of Persia 2", 256, 128, gold, "center", 312)
            text("Macintosh Native", 256, 154, align="center")
            text("Work in progress", 256, 186, muted, "center")
            button((190, 228, 322, 258), "Back" if self.return_to_menu else "Close", True)
            text("by Pessegos", 420, 270, muted, "right")
        else:
            text("Game", 256, 42, gold, "center")
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
                text("Not implemented yet", 256, 339, muted, "center")
        return image
