"""Tk window controls and modal input for the scene host."""

import functools
import math
import sys
import time
import tkinter as tk
from types import SimpleNamespace
from typing import NamedTuple

import numpy
from PIL import Image, ImageChops, ImageTk

from pop2.app_window import create_root
from pop2.game_menu import GameMenu
from pop2.input_routing import InputRouting
from pop2.game_ui import (DevelopmentMenu, VISIBLE_SIZE, VISIBLE_VIEWPORT, fit_viewport,
                          viewport_point, fit_menu_viewport, menu_viewport_point)
from pop2.preferences import remember
from pop2.screenshots import ScreenshotSettings, save_screenshot
from pop2.tk_photo import put_pixels
from pop2.tk_pointer import refresh_pointer


PAUSE_GAMEPLAY_KEYS = frozenset({
    "Left", "Right", "Up", "Down", "Shift_L", "Shift_R", "Control_L", "Control_R",
})
RESUME_COMMAND_KEYS = frozenset({
    'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Meta_L', 'Meta_R',
    'Super_L', 'Super_R', 'Win_L', 'Win_R',
})
EXTERNAL_CAPTURE_KEYS = frozenset({'F9', 'F10'})
# The page each Alt shortcut opens. Pressed again while its page is on show, the
# shortcut closes the menu, as F1, F2 and F3 close theirs.
SHORTCUT_PAGES = {'confirm_new': 'confirm', 'save': 'saves', 'open': 'saves', 'options': 'options',
                  'controls': 'controls', 'cutscenes': 'cutscenes', 'hall': 'hall', 'about': 'about'}


@functools.lru_cache(maxsize=8)
def nearest_axes(source_size, size):
    """For each column and row of a picture of ``source_size`` enlarged to ``size``
    (Image.resize, NEAREST), the source column and row it shows. Enlarging only a part
    with a source box rounds differently, but these give the whole enlargement's pixels."""
    def axis(count, length):
        ramp = Image.frombytes('I', (count, 1), numpy.arange(count, dtype='<i4').tobytes())
        return numpy.asarray(ramp.resize((length, 1), Image.Resampling.NEAREST)).reshape(-1)

    return axis(source_size[0], size[0]), axis(source_size[1], size[1])


def packed_pixels(image):
    """An RGBA picture's pixels as one 32-bit number each, by rows and columns: compared
    and gathered several times faster than their four channels."""
    return numpy.asarray(image).view(numpy.uint32)[..., 0]


def changed_bands(before, after, gap=8):
    """The boxes (left, top, right, bottom) around what changed between two pictures of
    the same size (arrays, packed or by channel), one for each band of rows that changed,
    bands closer than ``gap`` rows joined: an option the pointer left and the one it
    reached, far apart, are two small boxes rather than one over everything between them."""
    changed = before != after
    if changed.ndim == 3:
        changed = changed.any(axis=2)
    return mask_bands(changed, gap)


def mask_bands(changed, gap=8):
    """changed_bands for a mask of the pixels that changed."""
    rows = numpy.flatnonzero(changed.any(axis=1))
    if not rows.size:
        return []
    breaks = numpy.flatnonzero(numpy.diff(rows) > gap)
    bands = []
    for first, last in zip(numpy.concatenate(([rows[0]], rows[breaks + 1])), numpy.concatenate((rows[breaks], [rows[-1]]))):
        columns = numpy.flatnonzero(changed[first:last + 1].any(axis=0))
        bands.append((int(columns[0]), int(first), int(columns[-1]) + 1, int(last) + 1))
    return bands


def changed_parts(before, after, gap=8):
    """Boxes (left, top, right, bottom) that hold every pixel that differs between two
    pictures of the same size (packed arrays): the bands of changed_bands, each cut into
    its two sides, ``gap`` columns wide, and the bands of rows that change between them.
    An outline that changed colour, as around a save or a picture the focus left or
    reached, is then its four sides rather than all it encloses: at 3440x1440 about a
    fifteenth of the pixels."""
    changed = before != after
    parts = []
    for left, top, right, bottom in mask_bands(changed, gap):
        band = changed[top:bottom, left:right]
        width = right - left
        if width <= 4 * gap or bottom - top <= 4 * gap:
            parts.append((left, top, right, bottom))
            continue
        cut = []
        for start in (0, width - gap):
            side = band[:, start:start + gap]
            rows, columns = numpy.flatnonzero(side.any(axis=1)), numpy.flatnonzero(side.any(axis=0))
            if rows.size:
                cut.append((left + start + int(columns[0]), top + int(rows[0]),
                            left + start + int(columns[-1]) + 1, top + int(rows[-1]) + 1))
        cut += [(left + gap + first, top + upper, left + gap + last, top + lower)
                for first, upper, last, lower in mask_bands(band[:, gap:width - gap], gap)]
        # Pieces that cover most of the band anyway cost more calls than pixels saved.
        area = sum((part[2] - part[0]) * (part[3] - part[1]) for part in cut)
        parts += cut if area * 3 < width * (bottom - top) * 2 else [(left, top, right, bottom)]
    return parts


def page_damage(redrawn, frame):
    """The boxes of ``frame`` (pixels) that differ from what the window showed in the parts
    a page drawn in place over the one shown says it drew again: (box, its pixels before,
    or None to send all of it)."""
    boxes = []
    for box, before in redrawn:
        if before is None:
            boxes.append(box)
            continue
        boxes += [(left + box[0], top + box[1], right + box[0], bottom + box[1]) for left, top, right, bottom
                  in changed_parts(packed_pixels(before), packed_pixels(frame.crop(box)))]
    return boxes


def photo_holder(master, photo):
    """A label never placed, so never shown, that keeps the pixels Tk prepared to show
    ``photo`` while no item shows it: Tk lets them go at its next idle moment otherwise,
    and showing the photo again then prepared all of them again (about 30 ms at 3440x1440).
    Destroy it once the photo is shown again or no longer needed."""
    return tk.Label(master, image=photo)


class SavePageShown(NamedTuple):
    """What a photo kept (spare_photos) shows of a saves page: the picture ``frame`` that
    ``browser`` drew for ``menu`` in place, with what present_viewport remembers of it
    (``state``, ``listing``). Kept by F1's warm-up, and by a saves page left for F1."""
    photo: object
    menu: object
    browser: object
    frame: object
    state: tuple
    listing: tuple


def same_save_page(kept, browser):
    """Whether the browser ``kept`` shows the page that ``browser``, just made, would: the
    same saves (the same ones read), the same game to save and the same state. The game
    to save is compared but for the moment it was captured (created_at, to the second),
    which the page does not show: saving captures it again."""
    def game(slot):
        return {key: value for key, value in slot.document.items() if key != 'created_at'}

    return (len(kept.slots) == len(browser.slots) and all(a is b for a, b in zip(kept.slots, browser.slots))
            and kept == browser and (browser.current is None or game(kept.current) == game(browser.current)))


def put_patch(photo, image, x, y):
    """Write an opaque ``image`` (a picture, or an array of rows of RGB or RGBA bytes, alpha
    ignored) into the Tk ``photo`` at (x, y), by Tk's own function (pop2.tk_photo): about
    five times faster than the data below, at least twice as fast as the copy. Without it,
    copied from another photo, a part makes Tk look over the alpha of all of ``photo``
    (about 2 ms at 3440x1440); given as data with no alpha it spares that, but Tk reads
    such data about twice as slowly, so only the smaller patches go as data."""
    if put_pixels(photo, image, x, y):
        return
    if isinstance(image, numpy.ndarray):
        image = Image.fromarray(image)
    rgb = image if image.mode == 'RGB' else image.convert('RGB')
    if rgb.width * rgb.height * 20 < photo.width() * photo.height():
        photo.tk.call(str(photo), 'put', b'P6 %d %d 255 ' % rgb.size + rgb.tobytes(), '-format', 'ppm',
                      '-to', x, y)
    else:
        patch = ImageTk.PhotoImage(rgb)
        photo.tk.call(str(photo), 'copy', str(patch), '-to', x, y, '-compositingrule', 'set')


def window_is_foreground(root):
    """Native menu/capture activation can clear Tk focus without leaving us."""
    if sys.platform != 'win32':
        return False
    try:
        handle = root.winfo_id()
        if not isinstance(handle, int):
            return False
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        user32.GetAncestor.restype = wintypes.HWND
        return user32.GetAncestor(handle, 2) == user32.GetForegroundWindow()
    except (tk.TclError, OSError):
        return False


def alt_pressed(event, held_keys=()):
    # Tk's Mod1 (0x8) is Num Lock on Windows, but Alt on X11.
    mask = (0x10 | 0x20000) if sys.platform == "win32" else (0x8 | 0x20000)
    return bool(event.state & mask or {"Alt_L", "Alt_R"}.intersection(held_keys))


def centered_window_geometry(root, width, height):
    """The first windowed position, whether shown now or after fullscreen."""
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 2)
    return f"{width}x{height}+{x}+{y}"


def is_resume_key(event, held_keys=()):
    command_keys = RESUME_COMMAND_KEYS
    if (alt_pressed(event, held_keys) or event.state & (0x4 | 0x40)
            or command_keys.intersection(held_keys)):
        return False
    key = event.keysym
    if (key in command_keys or key in {
            "Shift_L", "Shift_R", "Caps_Lock", "Num_Lock", "Scroll_Lock",
            "Pause", "Print", "Sys_Req", "Menu", "Insert", "Delete",
            "Home", "End", "Prior", "Next", "KP_Insert", "KP_Delete",
            "KP_Home", "KP_End", "KP_Prior", "KP_Next", "??", "NoSymbol",
            "VoidSymbol"}
            or key.startswith("XF86") or key.startswith("F") and key[1:].isdigit()):
        return False
    # Windows multimedia events need not carry a reliable Tk keysym/character.
    code = getattr(event, "keycode", None)
    if sys.platform == "win32" and isinstance(code, int) and (
            code in {0x21, 0x22, 0x23, 0x24, 0x2D, 0x2E}
            or 0xA6 <= code <= 0xB7):
        return False
    char = getattr(event, "char", "")
    return (bool(char) and char.isprintable() or len(key) == 1 and key.isprintable()
            or key in {"space", "Return", "Tab", "BackSpace",
                       "Left", "Right", "Up", "Down",
                       "KP_Enter", "KP_Space", "KP_Tab", "KP_Add", "KP_Subtract",
                       "KP_Multiply", "KP_Divide", "KP_Decimal", "KP_Equal"}
            or key.startswith("KP_") and key[3:].isdigit())


class WindowControls(InputRouting):
    """Window callbacks shared by the rooftop scene and animation preview."""

    def create_window(self, title, scale=2):
        self.screenshot_settings = ScreenshotSettings.load()
        self.screenshot_viewport = None
        self.screenshot_toast = None
        self.screenshot_toast_after_id = None
        self.audio_notice_text = None
        self.audio_notice_after_id = None
        self.screenshot_dialog_active = False
        audio = getattr(self, "audio", None)
        self.sound_enabled = audio.sound_enabled if audio is not None else True
        self.music_enabled = audio.music_enabled if audio is not None else True
        self.root = create_root()
        self.root.title(title)
        self.root.resizable(True, True)
        self.root.minsize(*VISIBLE_SIZE)
        self.canvas = tk.Canvas(
            self.root,
            width=VISIBLE_SIZE[0] * scale,
            height=VISIBLE_SIZE[1] * scale,
            highlightthickness=0,
            bg="#000000",
        )
        self.canvas.pack(fill="both", expand=True)
        self.bitmap_presenter = None
        self.canvas.bind("<Configure>", lambda _event: self.present_viewport())
        self.canvas.bind("<Expose>", self.expose_viewport)
        self.canvas.bind("<Button-1>", self.dev_click)
        self.canvas.bind("<Double-Button-1>", self.dev_double_click)
        self.canvas.bind("<Button-2>", self.dev_click)
        self.canvas.bind("<Button-3>", self.dev_click)
        self.canvas.bind("<ButtonRelease-1>", self.dev_release)
        self.canvas.bind("<Motion>", self.dev_hover)
        self.canvas.bind("<B1-Motion>", self.dev_hover)
        self.canvas.bind("<Leave>", self.dev_pointer_leave)
        self.canvas.bind("<MouseWheel>", self.dev_scroll)
        self.canvas.bind("<Button-4>", self.dev_scroll)
        self.canvas.bind("<Button-5>", self.dev_scroll)
        # Menu input runs before gameplay bindings, without a second window.
        for widget in (self.root, self.canvas):
            widget.bindtags(("DevelopmentInput", *widget.bindtags()))
        self.root.bind_class("DevelopmentInput", "<KeyPress>", self.dev_key_press)
        self.root.bind_class("DevelopmentInput", "<KeyRelease>", self.dev_key_release)
        self.image_ref = None
        self.copy_pointer_held = False
        self.status = tk.StringVar(value="Window escape")
        self.status_label = tk.Label(
            self.root, textvariable=self.status, anchor="w", padx=6
        )
        self.debug_status = False

        for keysym in ("Left", "Right", "Up", "Down", "Shift_L", "Shift_R",
                       "Control_L", "Control_R"):
            for pressed, kind in ((True, "KeyPress"), (False, "KeyRelease")):
                self.root.bind(f"<{kind}-{keysym}>", lambda event, key=keysym, down=pressed:
                               self.run_key_binding(key, down, event))
        self.focus_pause_after_id = None
        self.root.bind("<FocusOut>", self.focus_out)
        self.root.bind("<Destroy>", self.cancel_focus_pause)
        self.root.bind("<Destroy>", self.cancel_audio_notice, add="+")
        self.root.bind("<Destroy>", self.destroy_screenshot_gallery, add="+")
        if hasattr(self, 'destroy_cutscene_viewer'):
            self.root.bind("<Destroy>", self.destroy_cutscene_viewer, add="+")
        self.root.bind("<Destroy>", self.close_bitmap_presenter, add="+")
        self.root.bind("<KeyPress-Escape>", lambda event: self.run_key_binding("Escape", True, event))
        self.root.bind("<KeyRelease-Escape>", lambda event: self.run_key_binding("Escape", False, event))
        self.root.bind("<Alt-Return>", self.toggle_fullscreen)
        self.root.bind("<F2>", self.toggle_screenshot_menu)
        self.root.bind("<F3>", self.open_dev_mode)
        from pop2.window_aspect import constrain_window
        self.window_aspect = constrain_window(
            self.root, self.canvas, self.window_aspect_locked)

    def window_aspect_locked(self):
        gallery = self.active_cutscene_gallery() if hasattr(self, 'active_cutscene_gallery') else None
        return not getattr(self, 'fullscreen', False) and gallery is None

    def focus_out(self, event):
        self.clear_keys(event)
        self.forget_routed_keys()
        self.copy_pointer_held = False
        challenge = getattr(self, "copy_challenge", None)
        if challenge is not None and challenge.focus is not None:
            challenge.focus = None
            self.render()
        if self.focus_pause_after_id is None:
            # Let Tk finish an internal focus transfer before checking its owner.
            self.focus_pause_after_id = self.root.after_idle(self.pause_if_unfocused)

    def pause_if_unfocused(self):
        self.focus_pause_after_id = None
        if getattr(self, "screenshot_dialog_active", False):
            return
        if (getattr(self, "copy_challenge", None) is not None
                and getattr(self, 'cutscene_replay', None) is None
                and getattr(getattr(self, 'game_menu', None), 'page', None) != 'cutscenes'):
            return
        try:
            focused = self.root.focus_get()
        except tk.TclError:
            return
        if focused is None and window_is_foreground(self.root):
            return
        if focused is None or focused.winfo_toplevel() is not self.root:
            menu = getattr(self, 'game_menu', None)
            if menu is not None and menu.page == 'cutscenes':
                menu.cutscene_viewer.drag = None
                menu.cutscene_viewer.dragged = False
                menu.cutscene_viewer.last_clicked = None
            if getattr(self, 'cutscene_replay', None) is not None:
                self.pause_cutscene_replay(True)
            if getattr(self, "game_menu", None) is not None:
                self.game_was_paused = True
            if getattr(self, "dev_menu", None) is not None:
                self.dev_was_paused = True
            self.set_paused(True)

    def cancel_focus_pause(self, event):
        if event.widget is self.root and self.focus_pause_after_id is not None:
            self.root.after_cancel(self.focus_pause_after_id)
            self.focus_pause_after_id = None

    def escape_key(self, _event=None):
        if not self.escape_held:
            self.escape_held = True
            if self.game_menu is not None:
                self.play_menu_sound('click')
                self.apply_game_action(self.game_menu.key("Escape"))
            elif self.dev_menu is not None:
                self.play_menu_sound('click')
                self.apply_dev_action(self.dev_menu.key("Escape"))
            else:
                self.set_paused(not self.paused)
        return "break"

    def escape_release(self, _event=None):
        self.escape_held = False
        return "break"

    def gameplay_controls_available(self):
        return (getattr(self, "game_menu", None) is None
                and getattr(self, "dev_menu", None) is None
                and getattr(self, "intro", None) is None
                and getattr(self, "demo", None) is None
                and getattr(self, "copy_challenge", None) is None
                and not getattr(self, "level_complete", False)
                and getattr(getattr(self, "death", None), "counter", -1) < 0)

    def record_paused_key(self, event, pressed):
        if event.keysym in ("Left", "Right"):
            self.horizontal_key(event, -1 if event.keysym == "Left" else 1, pressed)
        elif event.keysym in PAUSE_GAMEPLAY_KEYS:
            key = event.keysym.lower().split('_')[0]
            key = "ctrl" if key == "control" else key
            if key in ("shift", "ctrl"):
                pair = ("Shift_L", "Shift_R") if key == "shift" else ("Control_L", "Control_R")
                pressed = bool(set(pair).intersection(self.window_keys_down))
            self.set_key_state(key, pressed)

    def restore_held_gameplay_controls(self, keys):
        self.pause_resume_keys.difference_update(keys)
        # Restore modifiers before directions so chords reach the normal
        # controller rather than replaying an old buffered command.
        for key in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Up", "Down", "Left", "Right"):
            if key in keys:
                self.record_paused_key(SimpleNamespace(keysym=key), True)

    def set_paused(self, paused, render=True):
        if self.paused == paused:
            return
        now = time.perf_counter()
        self.paused = paused
        if hasattr(self, 'pause_gate_presentation'):
            self.pause_gate_presentation(paused, now)
        audio = getattr(self, "audio", None)
        if audio is not None:
            audio.pause(paused)
        if paused:
            self.pause_started_at = now
            if self.animation_after_id is not None:
                self.root.after_cancel(self.animation_after_id)
                self.animation_after_id = None
            # Ordinary pause freezes controls as well as animation. Menus and
            # focus loss still explicitly clear input rather than restoring it.
            if not self.gameplay_controls_available():
                self.clear_keys(None)
            self.pause_resume_keys.update(self.window_keys_down)
        else:
            elapsed = now - self.pause_started_at
            if getattr(self, "intro", None) is not None:
                self.last_intro_at = now
            if getattr(self, "demo", None) is not None:
                self.last_demo_at = now
            if getattr(self, 'copy_challenge', None) is not None:
                self.last_copy_at = now
            if self.combat is not None and self.combat.last_guard_at is not None:
                self.combat.last_guard_at += elapsed
            self.pause_started_at = None
            self.next_animation_at = now
            if self.gameplay_controls_available():
                self.resume_pause_controls()
                self.pause_resume_keys.difference_update(PAUSE_GAMEPLAY_KEYS)
                # Keep the normal Up+direction chord window before the next tick.
                self.next_animation_at += self.current_animation_interval_ms() / 1000
            self.schedule_next_animation()
        if render:
            self.render()

    def toggle_fullscreen(self, _event=None, *, windowed_geometry=None, windowed_state=None):
        if not self.fullscreen:
            self.windowed_geometry = windowed_geometry or self.root.geometry()
            self.windowed_state = windowed_state or self.root.state()
            self.status_label.pack_forget()
            self.present_before_fullscreen()
            self.root.attributes("-fullscreen", True)
            self.fullscreen = True
            self.update_cursor_visibility()
        else:
            self.root.attributes("-fullscreen", False)
            self.fullscreen = False
            self.update_cursor_visibility()
            if self.windowed_state == "normal":
                self.root.geometry(self.windowed_geometry)
            self.root.state(self.windowed_state)
            self.update_status_visibility()
        self.root.after_idle(self.present_viewport)
        remember(fullscreen=self.fullscreen)
        return "break"

    def present_before_fullscreen(self):
        """Draw a still picture (paused, a menu) for the fullscreen window before it grows.

        Until the canvas paints again, Windows shows the grown window's old pixels at its
        top-left corner. The running game is painted again within a few milliseconds (by
        CanvasBitmap), but a still picture was drawn anew at the monitor's size first, tens
        of milliseconds at 3440x1440 (twice when paused), so the small picture was seen in
        the corner. Drawn beforehand, the drawing after the resize finds it done and only
        Tk's painting remains."""
        if (sys.platform != 'win32' or getattr(self, 'native_viewport', None) is None
                or not (getattr(self, 'paused', False) or getattr(self, 'game_menu', None) is not None
                        or getattr(self, 'dev_menu', None) is not None
                        or getattr(self, 'copy_challenge', None) is not None)):
            return
        from pop2.display_refresh import window_monitor_size

        size = window_monitor_size(self.root)
        if size is not None:
            self.present_viewport(canvas_size=size)

    def open_dev_mode(self, _event=None):
        if not self.development_available():
            return "break"
        if _event is not None:
            if self.dev_toggle_held:
                return "break"
            self.dev_toggle_held = True
        if self.dev_menu is not None:
            self.close_dev_mode()
            return "break"
        if self.level_map is None:
            return "break"
        if self.game_menu is not None and self.game_menu.page == "confirm":
            return "break"
        already_paused = self.paused
        level_options = self.development_levels() if self.level_navigation_available() else ()
        if level_options:
            level_index = next((i for i, option in enumerate(level_options)
                                if option[0] == self.game.level.number), 0)
            screens = level_options[level_index][2]
            current = self.screen_label(self.room_id)
            screen_index = screens.index(current) if current in screens else 0
        else:
            entries = self.dev_screens()
            if not entries:
                return "break"
            current = self.screen_label(self.room_id)
            screens = tuple(entries)
            screen_index = screens.index(current) if current in entries else 0
        was_paused = self.game_was_paused if self.game_menu is not None else self.paused
        if hasattr(self, 'cancel_cutscene_gallery_tick'):
            self.cancel_cutscene_gallery_tick()
            self.dispose_cutscene_strip()
        self.dispose_screenshot_gallery()
        self.game_menu = None
        self.ui_hover_target = None
        if (self.level_navigation_available() and self.combat is not None
                and not self.combat.player.alive):
            self.remember_development_room()
        self.dev_menu = DevelopmentMenu(
            screens, screen_index, self.peaceful,
            level_available=self.level_navigation_available(),
            level_options=level_options, level_index=level_index if level_options else 0,
            map_provider=self.development_map if level_options else None,
            return_screens=dict(getattr(self, 'development_return_screens', {})),
            current_level=self.game.level.number, current_screen=self.screen_label(self.room_id),
            god_mode=getattr(self, 'god_mode', False),
        )
        if self.dev_menu.map_available:
            self.dev_menu.focus = 4
            self.warm_dev_maps((0, 1, -1))
        self.dev_was_paused = was_paused
        self.set_paused(True)
        self.clear_keys(None)
        self.pause_resume_keys.update(self.window_keys_down)
        self.update_cursor_visibility()
        if already_paused:
            self.render()
        return "break"

    def close_dev_mode(self):
        if self.dev_menu is None:
            return
        self.dev_menu = None
        self.ui_hover_target = None
        self.dev_map_frame = None
        self.warm_dev_maps(())
        self.clear_keys(None)
        self.update_cursor_visibility()
        # Drawn once, below: set_paused drew the game too, then this drew it again (about
        # 30 ms more at 3440x1440 for each closing that resumes the game).
        self.set_paused(self.dev_was_paused, render=False)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

    def apply_dev_action(self, action):
        if self.dev_menu is None:
            return
        if action == "resume":
            self.close_dev_mode()
        elif action == 'cutscenes':
            self.open_cutscene_viewer(developer=True)
        elif action in ('go', 'return_room') and self.level_navigation_available():
            destination = self.dev_menu.return_screen if action == 'return_room' else self.dev_menu.screen
            if destination is None:
                return
            try:
                if self.dev_menu.level_number != self.game.level.number:
                    self.load_level(self.dev_menu.level_number)
                # Scenes played after a warp still count: the player saw them.
                self.jump_to_screen(destination)
            except ValueError as exc:
                self.dev_menu.error = str(exc)
                self.render()
                return
            self.close_dev_mode()
        elif action == "peaceful" and self.level_navigation_available():
            self.set_peaceful(self.dev_menu.peaceful)
        elif action == 'god_mode' and self.level_navigation_available():
            self.set_god_mode(self.dev_menu.god_mode)
        else:
            self.update_cursor_visibility()
            if self.dev_menu.map_enabled and getattr(self, 'screenshot_viewport', None) is not None:
                # F3 froze the world: the map page only redraws the menu over it.
                self.redraw_dev_menu()
                if getattr(self, 'dev_maps_warmed', None) != self.dev_menu.level_index:
                    self.warm_dev_maps((1, -1))
            elif action == 'changed':
                self.redraw_menu()
            else:
                self.render()

    def warm_dev_maps(self, offsets):
        """Load the maps the ◀ ▶ buttons lead to while the player looks at this one.

        One level per idle moment: reading a map and scaling it to the window
        takes 50-100 ms, which is felt when it happens on the click instead.
        """
        pending = getattr(self, 'dev_maps_warm_id', None)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except tk.TclError:
                pass
        self.dev_maps_warm_id = None
        menu = self.dev_menu
        if menu is None or not offsets or menu.map_provider is None or not menu.level_options:
            self.dev_maps_warmed = None
            return
        self.dev_maps_warmed = menu.level_index
        count = len(menu.level_options)
        numbers = list(dict.fromkeys(menu.level_options[(menu.level_index + offset) % count][0]
                                     for offset in offsets))

        def step():
            self.dev_maps_warm_id = None
            if self.dev_menu is not menu or not numbers:
                return
            try:
                atlas = menu.map_provider(numbers.pop(0))
                width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
                if width <= 1 or height <= 1:
                    width, height = VISIBLE_SIZE[0] * 2, VISIBLE_SIZE[1] * 2
                frame, _position = fit_viewport(width, height)
                rect = menu.MAP_CONTROLS[4]
                left, top, right, bottom = menu.projected_rect(rect, frame)
                for size in ((rect[2] - rect[0], rect[3] - rect[1]), (right - left, bottom - top)):
                    atlas.detail(size)
            except Exception:  # noqa: BLE001 - best effort; the click loads it as before
                return
            if numbers:
                self.dev_maps_warm_id = self.root.after(40, step)

        self.dev_maps_warm_id = self.root.after(40, step)

    def choose_screenshot_folder(self):
        if self.game_menu.screenshot_gallery is None:
            self.install_screenshot_gallery()
        self.game_menu.screenshot_gallery.choose_folder()
        self.pause_resume_keys.update(self.window_keys_down)
        self.redraw_screenshot_gallery()
        self.schedule_screenshot_gallery()

    def install_screenshot_gallery(self):
        from pop2.screenshot_gallery import ScreenshotGallery

        self.dispose_screenshot_gallery()
        self.game_menu.screenshot_gallery = ScreenshotGallery(self.screenshot_settings.folder,
            self.screenshot_settings.scale, getattr(self, 'screenshot_include_ui', False))
        self.schedule_screenshot_gallery()

    def dispose_screenshot_gallery(self):
        self.screenshot_scroll_dragging = False
        self.hide_screenshot_held()
        self.hide_screenshot_lava()
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None:
            gallery.close()
            try:
                self.set_window_cursor('')
            except tk.TclError:
                pass
            self.game_menu.screenshot_gallery = None
        pending = getattr(self, 'screenshot_gallery_after_id', None)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except tk.TclError:
                pass
            self.screenshot_gallery_after_id = None

    def destroy_screenshot_gallery(self, event):
        if event.widget is self.root:
            self.dispose_screenshot_gallery()

    def schedule_screenshot_gallery(self):
        menu = getattr(self, 'game_menu', None)
        gallery = getattr(menu, 'screenshot_gallery', None)
        if gallery is None or menu.page != 'screenshots' or getattr(self, 'screenshot_gallery_after_id', None) is not None:
            return
        previous = time.perf_counter()
        def tick():
            nonlocal previous
            self.screenshot_gallery_after_id = None
            if self.game_menu is not menu or menu.page != 'screenshots' or menu.screenshot_gallery is not gallery:
                return
            now = time.perf_counter()
            changed = gallery.poll()
            moving = gallery.animate(now - previous)
            previous = now
            if gallery.burn_cue:
                gallery.burn_cue = False
                self.play_menu_sound('burn')
            if gallery.committed_folder is not None:
                self.screenshot_settings.folder = gallery.committed_folder
                menu.screenshot_folder = str(gallery.committed_folder)
                gallery.committed_folder = None
            if changed or moving:
                self.redraw_screenshot_gallery()
            if gallery.reads.pending or gallery.scrolling or gallery.animation_running or gallery.burn_seconds is not None:
                # Otherwise at the lava's next frame or the burn's (see next_change): ticks of
                # their own caught the burn's steps after 70 or 88 ms, not each after 83.
                wait = None if gallery.scrolling else gallery.next_change()
                if gallery.scrolling:
                    delay = max(1, round(1000 / 120 - (time.perf_counter() - now) * 1000))
                elif gallery.reads.pending and (wait is None or wait > 0.012):
                    delay = 12
                else:
                    delay = max(1, math.ceil((wait - (time.perf_counter() - now)) * 1000))
                self.screenshot_gallery_after_id = self.root.after(delay, tick)
        self.screenshot_gallery_after_id = self.root.after(12, tick)

    def redraw_screenshot_gallery(self):
        if self.game_menu.screenshot_gallery.drag_target is None:
            self.set_window_cursor('')
        # At the game's resolution, drawn over in place: the window draws the page it shows
        # by itself (present_viewport), and a capture with menus draws its own.
        self.native_viewport = self.draw_screenshot_notice(
            self.game_menu.draw(self.screenshot_viewport, self.ui_font, in_place=True))
        self.present_viewport()

    def apply_gallery_action(self, action):
        gallery = self.game_menu.screenshot_gallery
        if action == 'gallery_back':
            self.dispose_screenshot_gallery()
            if self.game_menu.back() == 'close':
                self.close_game_menu()
            else:
                self.render()
            return
        if action == 'gallery_capture':
            self.capture_screenshot(include_ui=gallery.include_ui)
            return
        if action == 'gallery_folder':
            gallery.commit_folder()
        elif action == 'gallery_delete':
            gallery.delete_capture()
        elif action == 'gallery_scale':
            try:
                ScreenshotSettings(self.screenshot_settings.folder, gallery.scale).save()
                self.screenshot_settings.scale = self.game_menu.screenshot_scale = gallery.scale
                gallery.error = ''
            except OSError:
                gallery.scale = self.screenshot_settings.scale
                gallery.error = 'Could not remember PNG size.'
        self.screenshot_include_ui = gallery.include_ui
        self.redraw_screenshot_gallery()
        self.schedule_screenshot_gallery()

    def capture_screenshot(self, *, include_ui=False):
        menu = self.game_menu if self.game_menu is not None and self.game_menu.page == "screenshots" else None
        framed_ui = False
        try:
            viewport = getattr(self, "native_viewport" if include_ui else "screenshot_viewport", None)
            if viewport is None:
                raise ValueError("No game frame is available yet")
            if include_ui and self.game_menu is not None and self.game_menu.page == 'saves':
                scale = self.screenshot_settings.scale
                source = self.screenshot_viewport.resize((512 * scale, 384 * scale), Image.Resampling.NEAREST)
                viewport = self.draw_screenshot_notice(self.game_menu.save_browser.draw(
                    source, self.ui_font, background_key=id(self.screenshot_viewport)))
            elif (include_ui and self.game_menu is not None and self.game_menu.page == 'cutscenes'
                    and getattr(self, 'cutscene_replay', None) is None):
                scale = self.screenshot_settings.scale
                size, _ = fit_menu_viewport(self.canvas.winfo_width(), self.canvas.winfo_height())
                size = round(size[0] * 384 * scale / size[1]), 384 * scale
                viewport = self.cutscene_gallery_frame(size, capture=True)
                framed_ui = True
            elif include_ui and menu is not None and menu.screenshot_gallery is not None:
                scale = self.screenshot_settings.scale
                source = self.screenshot_viewport.resize((512 * scale, 384 * scale), Image.Resampling.NEAREST)
                viewport = self.draw_screenshot_notice(menu.screenshot_gallery.draw(source, self.ui_font))
            elif include_ui and self.dev_menu is not None and self.dev_menu.preview_enabled:
                scale = self.screenshot_settings.scale
                source = viewport.resize((512 * scale, 384 * scale), Image.Resampling.NEAREST)
                visible = source.crop((scale, 0, 511 * scale, 384 * scale))
                source.paste(self.dev_menu.present_map(visible, self.ui_font), (scale, 0))
                viewport = source
            path = (save_screenshot(viewport, self.screenshot_settings, framed_ui=True) if framed_ui
                    else save_screenshot(viewport, self.screenshot_settings))
        except (OSError, ValueError) as exc:
            message = "Could not save PNG. Check the screenshot folder."
            if menu is not None:
                if menu.screenshot_gallery is not None:
                    menu.screenshot_gallery.error = message
                else:
                    menu.error = message
                self.render()
            else:
                self.status.set(str(exc))
                self.show_screenshot_toast(message, error=True)
            return None
        self.status.set(f"Screenshot saved: {path}")
        if menu is not None:
            menu.error = ""
            menu.screenshot_status = "PNG saved"
            if menu.screenshot_gallery is not None:
                menu.screenshot_gallery.error = ''
                menu.screenshot_gallery.status = 'PNG saved'
                menu.screenshot_gallery.refresh(path)
                self.schedule_screenshot_gallery()
        self.show_screenshot_toast(path.name)
        return path

    def show_screenshot_toast(self, filename, *, error=False):
        # The interface font has no underscore: the file's name is shown as the
        # Screenshots page shows it, with spaces ("PoP2 2026-11-17 18.15.37.png").
        self.screenshot_toast = filename if error else f"Saved screenshot as {filename.replace('_', ' ')}"
        after_id = getattr(self, "screenshot_toast_after_id", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self.screenshot_toast_after_id = self.root.after(4000, self.clear_screenshot_toast)
        self.render()

    def clear_screenshot_toast(self):
        self.screenshot_toast = None
        self.screenshot_toast_after_id = None
        self.render()

    def show_audio_notice(self, action, enabled):
        label = {"sound": "Sounds", "music": "Ambient Music", "ambience": "Ambient Effects"}[action]
        message = f"{label} {'On' if enabled else 'Off'}"
        text = self.ui_font.text(message, self.hud_text_color)
        alternate = self.ui_font.text(f"{label} {'Off' if enabled else 'On'}", self.hud_text_color)
        self.audio_notice_text = Image.new("RGBA", (max(text.width, alternate.width), text.height))
        self.audio_notice_text.paste(text, (0, 0))
        after_id = self.audio_notice_after_id
        if after_id is not None:
            self.root.after_cancel(after_id)
        self.audio_notice_after_id = self.root.after(2000, self.clear_audio_notice)
        self.render()

    def show_hud_notice(self, message, seconds=2.5):
        """A short status-strip message, like the sound on/off notice."""
        font = self.ui_font
        message = ''.join(char if (code := char.encode('mac_roman', 'replace')[0]) in font.glyphs
                          and code != 0x2B else ' ' for char in message)
        self.audio_notice_text = font.text(' '.join(message.split()), self.hud_text_color)
        after_id = self.audio_notice_after_id
        if after_id is not None:
            self.root.after_cancel(after_id)
        self.audio_notice_after_id = self.root.after(round(seconds * 1000), self.clear_audio_notice)
        self.render()

    # -- controllers ----------------------------------------------------
    PAD_POLL_MS = 16

    def start_gamepads(self):
        from pop2.gamepad import PadReader, SdlGamepads, gamepads_disabled

        if gamepads_disabled() or getattr(self, 'gamepads', None) is not None:
            return
        self.pad_reader = PadReader()
        self.gamepads = SdlGamepads()
        self.pad_poll_after_id = self.root.after(self.PAD_POLL_MS, self.poll_gamepads)
        self.root.bind('<Destroy>', self.stop_gamepads_on_destroy, add='+')

    def stop_gamepads(self):
        after_id = getattr(self, 'pad_poll_after_id', None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self.pad_poll_after_id = None
        gamepads, self.gamepads = getattr(self, 'gamepads', None), None
        if gamepads is not None:
            gamepads.close()
        self.release_all_pad_inputs()
        self.update_gamepads(())

    def stop_gamepads_on_destroy(self, event):
        if event.widget is self.root and getattr(self, 'gamepads', None) is not None:
            self.pad_poll_after_id = None
            self.gamepads.close()
            self.gamepads = None

    def poll_gamepads(self):
        self.pad_poll_after_id = None
        gamepads = getattr(self, 'gamepads', None)
        if gamepads is None:
            return
        try:
            self.update_gamepads(gamepads.snapshot)
        finally:
            if getattr(self, 'gamepads', None) is not None:
                self.pad_poll_after_id = self.root.after(self.PAD_POLL_MS, self.poll_gamepads)

    def window_has_focus(self):
        if window_is_foreground(self.root):
            return True
        try:
            return self.root.focus_get() is not None
        except (tk.TclError, KeyError):
            return False

    def update_gamepads(self, pads, now=None, foreground=None):
        """One snapshot: connection notices, then button edges as keys."""
        if not getattr(self, 'controller_enabled', True):
            pads = ()
        known = getattr(self, 'pad_known', {})
        current = {pad.instance: pad for pad in pads}
        added = [pad for instance, pad in current.items() if instance not in known]
        removed = [pad for instance, pad in known.items() if instance not in current]
        self.pad_known = current
        if foreground is None:
            foreground = bool(current) and self.window_has_focus()
        reader = getattr(self, 'pad_reader', None)
        if reader is None:
            from pop2.gamepad import PadReader

            reader = self.pad_reader = PadReader()
        before = set(self.key_router.pad_sources())
        self.process_pad_input(reader.inputs(pads), now, foreground)
        if set(self.key_router.pad_sources()) - before:
            self.pad_used = True
        if not (added or removed):
            return
        page = self.controls_page()
        if page is not None:
            page.pads = tuple(current.values())
        if removed and not current:
            if (getattr(self, 'pad_used', False) and not self.paused
                    and self.gameplay_controls_available()):
                self.set_paused(True)
            self.pad_used = False
            self.show_hud_notice('Controller disconnected')
        elif added:
            self.show_hud_notice(f'{added[0].name} connected')
        elif page is not None:
            self.render()

    def clear_audio_notice(self):
        self.audio_notice_text = None
        self.audio_notice_after_id = None
        self.render()

    def cancel_audio_notice(self, event):
        if event.widget is self.root and self.audio_notice_after_id is not None:
            self.root.after_cancel(self.audio_notice_after_id)
            self.audio_notice_after_id = None

    def modal_open(self):
        return (self.dev_menu is not None or self.game_menu is not None
                or getattr(self, "copy_challenge", None) is not None)

    def update_cursor_visibility(self):
        visible = not self.fullscreen or self.modal_open()
        self.set_window_cursor("" if visible else "none")

    def development_available(self):
        return self.level_map is not None and getattr(self, "copy_challenge", None) is None

    def level_navigation_available(self):
        return (self.development_available() and getattr(self, "intro", None) is None
                and getattr(self, "demo", None) is None)

    def update_status_visibility(self):
        if self.debug_status and not self.fullscreen:
            self.status_label.pack(fill="x")
        else:
            self.status_label.pack_forget()

    def refresh_game_menu(self):
        if self.game_menu is not None:
            self.game_menu.save_available = self.can_save_game() if hasattr(self, 'can_save_game') else False
            if self.game_menu.save_browser is not None:
                self.game_menu.save_browser.save_available = self.game_menu.save_available
            self.game_menu.sound = self.sound_enabled
            self.game_menu.music = self.music_enabled
            self.game_menu.cave_ambience = getattr(self, 'cave_ambience_enabled', False)
            self.game_menu.menu_sounds = getattr(self, 'menu_sounds_enabled', True)
            self.game_menu.fullscreen = self.fullscreen
            self.game_menu.copy_protection = getattr(self, "copy_protection_enabled", True)

    def open_game_menu(self, page="menu", render=True):
        # render=False: the caller opens another page at once and draws only that one.
        if self.game_menu is not None:
            if self.game_menu.page != "confirm":
                if page == "menu":
                    if self.game_menu.page in ("screenshots", "saves", 'cutscenes', 'controls', 'options', 'hall'):
                        self.dispose_screenshot_gallery()
                        self.game_menu.show_page("menu")
                        self.pause_resume_keys.update(self.window_keys_down)
                        self.redraw_menu()
                    else:
                        self.close_game_menu()
                else:
                    self.dispose_screenshot_gallery()
                    self.game_menu.show_page(page)
                    if page == "screenshots":
                        self.game_menu.return_to_menu = False
                        self.install_screenshot_gallery()
                    self.pause_resume_keys.update(self.window_keys_down)
                    if render:
                        self.redraw_menu()
            return
        already_paused = self.paused
        self.game_was_paused = self.dev_was_paused if self.dev_menu is not None else self.paused
        self.dev_menu = None
        self.ui_hover_target = None
        self.game_menu = GameMenu(page=page, return_to_menu=page == "menu",
                                  screenshot_scale=self.screenshot_settings.scale,
                                  screenshot_folder=str(self.screenshot_settings.folder))
        if page == 'screenshots':
            self.install_screenshot_gallery()
        if render:
            self.set_paused(True)
        else:
            self.set_paused(True, render=False)
        self.clear_keys(None)
        self.pause_resume_keys.update(self.window_keys_down)
        self.update_cursor_visibility()
        if already_paused and render:
            self.render()
        if page == 'menu' and render:
            from pop2.menu_warmup import schedule_menu_warmup

            schedule_menu_warmup(self)   # the pages F1 leads to, while F1 is shown

    def toggle_screenshot_menu(self, _event=None):
        if self.game_menu is not None and self.game_menu.page == "confirm":
            return "break"
        if self.game_menu is not None and self.game_menu.page == "screenshots":
            self.close_game_menu()
        else:
            self.open_game_menu("screenshots")
        return "break"

    def shortcut_page_shown(self, command):
        """Whether the page the Alt shortcut ``command`` opens is on show (Alt+S the
        saves page saving, Alt+O and Alt+L the same page loading)."""
        menu = getattr(self, 'game_menu', None)
        if menu is None or menu.page != SHORTCUT_PAGES.get(command):
            return False
        if menu.page == 'saves':
            browser = menu.save_browser
            return browser is not None and browser.mode == ('load' if command == 'open' else 'save')
        return True

    def close_shortcut_page(self):
        """The shortcut of the page on show closes the menu, wherever the page was
        opened from, as F2 closes the screenshots page."""
        menu = self.game_menu
        if menu.page == 'hall':
            # Its own Close: after a victory, the presentation waiting for it starts.
            menu.return_to_menu = False
            self.close_hall_of_fame()
        else:
            self.close_game_menu()

    def close_game_menu(self, resume=False):
        if self.game_menu is None:
            return
        if getattr(self, 'menu_warmup_after_id', None) is not None:
            from pop2.menu_warmup import cancel_menu_warmup

            cancel_menu_warmup(self)
        if getattr(self, 'cutscene_replay', None) is not None:
            self.stop_cutscene_replay(render=False)
        if hasattr(self, 'cancel_cutscene_gallery_tick'):
            self.cancel_cutscene_gallery_tick()
            # Here, not left to the next drawing: in fullscreen the running game is drawn by
            # CanvasBitmap, and the strip (a canvas of its own) stayed over it.
            self.release_cutscene_gallery()
        self.dispose_screenshot_gallery()
        self.game_menu = None
        self.save_scroll_dragging = False
        self.ui_hover_target = None
        self.clear_keys(None)
        self.update_cursor_visibility()
        # Drawn once, below (see close_dev_mode).
        self.set_paused(False if resume else self.game_was_paused, render=False)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

    def apply_game_action(self, action, *, preserve_controls=False):
        menu = self.game_menu
        if action == 'cutscenes':
            self.open_cutscene_viewer()
            return
        if action in ('controls', 'controls_back', 'controls_saved', 'controller_toggle'):
            self.apply_controls_action(action)
            return
        if action == 'cutscene_play':
            self.start_cutscene_replay()
            return
        if action == 'cutscene_back':
            self.cancel_cutscene_gallery_tick()
            self.game_menu.show_page('menu')
            self.pause_resume_keys.update(self.window_keys_down)
            self.redraw_menu()
            return
        if menu is not None and menu.page == 'cutscenes' and action == 'changed':
            self.redraw_cutscene_gallery()
            return
        if (menu is not None and menu.page == 'screenshots' and menu.screenshot_gallery is not None
                and (action.startswith('gallery_') or action == 'changed')):
            self.apply_gallery_action(action)
            return
        if menu is not None and menu.page == "screenshots" and menu.screenshot_scale != self.screenshot_settings.scale:
            self.screenshot_settings.scale = menu.screenshot_scale
            try:
                self.screenshot_settings.save()
            except OSError:
                menu.error = "Could not remember screenshot settings."
        if action in ("close", "resume"):
            self.close_game_menu(resume=action == "resume")
        elif action == "quit":
            self.root.destroy()
        elif action in ("confirm_new", "about", "options"):
            self.open_game_menu("confirm" if action == "confirm_new" else action)
        elif action == "menu_sounds":
            self.menu_sounds_enabled = not getattr(self, 'menu_sounds_enabled', True)
            remember(menu_sounds=self.menu_sounds_enabled)
            self.play_menu_sound('click')
            self.render()
        elif action == "screenshot_folder":
            self.choose_screenshot_folder()
        elif action == "screenshot":
            self.capture_screenshot()
        elif action in ("new_game", "restart"):
            held_controls = ((self.window_keys_down - self.pause_resume_keys) & PAUSE_GAMEPLAY_KEYS
                             if action == "restart" and preserve_controls else set())
            self.set_paused(True)
            (getattr(self, "new_game", self.restart_opening) if action == "new_game" else self.restart_level)()
            if self.game_menu is not None:
                self.close_game_menu(resume=True)
            else:
                if self.dev_menu is not None:
                    self.dev_was_paused = False
                    self.close_dev_mode()
                self.set_paused(False)
            self.pause_resume_keys.update(self.window_keys_down)
            self.restore_held_gameplay_controls(held_controls)
        elif action in ("sound", "music"):
            name = action + "_enabled"
            enabled = not getattr(self, name)
            setattr(self, name, enabled)
            if self.audio is not None:
                getattr(self.audio, "set_" + name)(enabled)
            self.show_audio_notice(action, enabled)
        elif action == "ambience":
            self.cave_ambience_enabled = not getattr(self, 'cave_ambience_enabled', False)
            remember(cave_ambience=self.cave_ambience_enabled)
            self.show_audio_notice(action, self.cave_ambience_enabled)
        elif action == "fullscreen":
            self.toggle_fullscreen()
            self.render()
        elif action == "copy_protection":
            self.copy_protection_enabled = not getattr(self, "copy_protection_enabled", True)
            remember(copy_protection=self.copy_protection_enabled)
            if not self.copy_protection_enabled:
                self.copy_challenge = None
                self.copy_pointer_held = False
                self.clear_keys(None)
            self.render()
        elif action in ("save", "open"):
            self.open_save_browser(load=action == 'open')
        elif action == 'save_back':
            if menu.back() == 'close':
                self.close_game_menu()
            else:
                self.redraw_menu()
        elif action in ('slot_save', 'slot_load', 'slot_delete', 'slot_create', 'slot_rename'):
            self.apply_save_action(action)
        elif action == "hall":
            self.open_hall_of_fame()
        elif action == 'hall_saved':
            self.save_hall_of_fame()
        elif action == 'hall_close':
            self.close_hall_of_fame()
        else:
            self.schedule_save_scroll()
            if self.game_menu is not None and self.game_menu.page == 'saves':
                self.redraw_save_menu()
            elif action == 'changed':
                self.redraw_menu()
            else:
                self.render()

    def open_hall_of_fame(self, minutes=None):
        """The menu's Hall of Fame (ShowHallOfFame 2:28c2), or, with the
        minutes left when Jaffar fell, the row to name (HallOfFameDialog)."""
        from pop2.hall_of_fame import HallOfFamePage, load_hall

        if self.game_menu is None or self.game_menu.page != 'hall':
            # Drawn once, below: the page shown before its rows were read was drawn too.
            self.open_game_menu('hall', render=False)
        menu = self.game_menu
        if menu.page != 'hall':
            return
        if minutes is not None:
            menu.return_to_menu = False
        menu.hall_page = HallOfFamePage.after_victory(minutes) if minutes is not None else HallOfFamePage(load_hall())
        self.hall_after_id = None
        self.redraw_menu()

    def save_hall_of_fame(self):
        from pop2.hall_of_fame import save_hall

        menu = self.game_menu
        page = getattr(menu, 'hall_page', None)
        if page is None:
            return
        try:
            save_hall(page.table())
        except OSError:
            self.status.set('Could not save the Hall of Fame')
        self.render()
        # 2:1fa4-1fd8: the named table stays up for 900 ticks or a click.
        def close():
            self.hall_after_id = None
            if self.game_menu is menu and menu.hall_page is page:
                self.close_hall_of_fame()
        self.hall_after_id = self.root.after(15000, close)

    def close_hall_of_fame(self):
        menu = self.game_menu
        pending = getattr(self, 'hall_after_id', None)
        if pending is not None:
            self.root.after_cancel(pending)
            self.hall_after_id = None
        if menu is None:
            return
        victory = getattr(menu.hall_page, 'position', None) is not None
        menu.hall_page = None
        if victory or menu.back() == 'close':
            # After a victory the presentation, already waiting, starts now.
            self.close_game_menu(resume=victory)
        else:
            self.redraw_menu()

    def gamepads_available(self):
        gamepads = getattr(self, 'gamepads', None)
        return gamepads is not None and gamepads.error is None

    def open_controls_page(self):
        from pop2.controls_page import ControlsPage

        if self.game_menu is None:
            self.open_game_menu('controls', render=False)   # drawn once, below
        elif self.game_menu.page != 'controls':
            self.dispose_screenshot_gallery()
            self.game_menu.show_page('controls')
            self.pause_resume_keys.update(self.window_keys_down)
        menu = self.game_menu
        if menu is None:
            return
        menu.controls_page = ControlsPage(
            self.keyboard_bindings, self.controller_bindings,
            pads=tuple(getattr(self, 'pad_known', {}).values()),
            controller_enabled=getattr(self, 'controller_enabled', True),
            controller_available=self.gamepads_available(),
            return_to_menu=menu.return_to_menu)
        menu.controls_page.input_device = getattr(self, 'last_input_device', 'keyboard')
        menu.controls_page.refresh_locks()
        self.watch_lock_lights()
        self.redraw_menu()

    LOCK_POLL_MS = 150

    def watch_lock_lights(self):
        """While the Controls page is open, its keyboard's lock lights
        follow the real ones, even when they change outside the game."""
        after_id = getattr(self, 'lock_poll_after_id', None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self.lock_poll_after_id = None
        page = self.controls_page()
        if page is None:
            return
        if page.refresh_locks() and page.device == 'keyboard' and page.view == 'overview':
            self.render()
        self.lock_poll_after_id = self.root.after(self.LOCK_POLL_MS, self.watch_lock_lights)

    def apply_controls_action(self, action):
        menu = self.game_menu
        page = getattr(menu, 'controls_page', None)
        if action == 'controls':
            self.open_controls_page()
            return
        if page is None:
            return
        if action == 'controls_back':
            if menu.back() == 'close':
                self.close_game_menu()
                return
            menu.focus = next(index for index, item in enumerate(menu.items) if item.action == 'controls')
            menu.controls_page = None
        elif action == 'controls_saved':
            remember(keyboard_bindings=self.keyboard_bindings.to_saved(),
                     controller_bindings=self.controller_bindings.to_saved())
        elif action == 'controller_toggle':
            self.controller_enabled = page.controller_enabled
            remember(controller_enabled=self.controller_enabled)
            if not self.controller_enabled:
                self.release_all_pad_inputs()
        self.redraw_menu()   # the game stays as it was under the menu

    def redraw_save_menu(self):
        self.refresh_game_menu()
        # Drawn over in place, as redraw_screenshot_gallery draws its page.
        self.native_viewport = self.draw_screenshot_notice(
            self.game_menu.draw(self.screenshot_viewport, self.ui_font, in_place=True))
        self.present_viewport()

    def open_save_browser(self, load=False):
        direct = self.game_menu is None
        if self.game_menu is None:
            self.open_game_menu(render=False)
        parent = self.game_menu.return_to_menu if self.game_menu.page == 'saves' else self.game_menu.page == 'menu'
        self.dispose_screenshot_gallery()
        self.game_menu.show_page('saves')
        self.game_menu.return_to_menu = parent and not direct
        browser = self.new_save_browser(load)
        # The page a kept photo shows already, when it is this one (SavePageShown): it then
        # opens on that photo, drawn and written already. Writing all of it into the photo
        # took about 25 ms at 3440x1440, drawing it 15.
        self.game_menu.save_browser = next(
            (shown.browser for _, _, shown in self.spare_photos().values()
             if isinstance(shown, SavePageShown) and shown.menu is self.game_menu
             and same_save_page(shown.browser, browser)), browser)
        self.pause_resume_keys.update(self.window_keys_down)
        # From F1 the game is not drawn again under the page (as a page reached from F1).
        self.redraw_menu()

    def new_save_browser(self, load):
        """The saves page's browser as it opens now, saving or loading (``load``)."""
        from pop2.save_slots import SAVE_DIRECTORY, SaveBrowser, SaveSlot, list_slots

        try:
            slots = list_slots(SAVE_DIRECTORY)
        except OSError:
            slots = tuple()
        if load:
            selected = max((i for i, slot in enumerate(slots) if slot.exists and not slot.error),
                           key=lambda i: slots[i].modified, default=0)
        else:
            selected = 0
        active_path = getattr(self, 'active_save_path', None)
        active_index = next((i for i, slot in enumerate(slots)
                             if slot.path == active_path and not slot.error), None)
        if active_index is not None:
            selected = active_index
        current = None
        if self.can_save_game():
            from pop2.save_game import capture

            document = capture(self.game)
            progress = document['resume']
            current = SaveSlot(SAVE_DIRECTORY, 'New save', level=self.game.level.number,
                               resume='Checkpoint' if progress['checkpoint'] else 'Level start',
                               capacity=progress['max_life'], document=document)
        browser = SaveBrowser(slots, 'load' if load else 'save', selected,
                              focus=100 + selected if load or active_index is not None else 29,
                              save_available=self.can_save_game(), current=current, active_path=active_path,
                              preview_provider=self.save_slot_preview, ground_cache=self.save_page_grounds())
        browser.ensure_visible(immediate=True)
        return browser

    def apply_save_action(self, action):
        from pop2.save_slots import SAVE_DIRECTORY, list_slots
        from pop2.save_game import read_document, save_name, write_save
        from uuid import uuid4

        browser = self.game_menu.save_browser
        if action == 'slot_save' and not browser.entry.exists:
            browser.edit_name('create')
            self.render()
            return
        if action in ('slot_load', 'slot_delete', 'slot_rename') and not browser.entry.exists:
            return
        path = browser.entry.path
        try:
            if action == 'slot_load':
                self.load_game_from(path)
                self.close_game_menu(resume=True)
                return
            if action == 'slot_delete':
                path.unlink()
                if path == getattr(self, 'active_save_path', None):
                    self.active_save_path = None
                browser.status = 'Save deleted'
            elif action == 'slot_rename':
                document = read_document(path)
                document['name'] = save_name(browser.draft)
                write_save(path, document)
                browser.status = 'Save renamed'
            else:
                if action == 'slot_create':
                    path = SAVE_DIRECTORY / (uuid4().hex + '.pop2save')
                self.save_game_to(path, save_name(browser.draft) if action == 'slot_create' else browser.entry.name)
                browser.status = 'Game saved'
            browser.slots = list_slots(SAVE_DIRECTORY)
            browser.active_path = getattr(self, 'active_save_path', None)
            browser.selected = next((i for i, slot in enumerate(browser.slots) if slot.path == path),
                                    max(0, min(browser.selected, len(browser.items) - 1)))
            browser.ensure_visible(immediate=True)
            browser.error = ''
            browser.editing = None
        except (OSError, ValueError) as error:
            browser.error = 'Could not ' + action[5:] + ' this save.'
            self.status.set(str(error))
        browser.confirmation = None
        browser.focus = 32 if browser.editing else 27
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

    def play_menu_sound(self, kind):
        audio = getattr(self, 'audio', None)
        # Menu sounds have their own switch on the Options page, apart from the game's sounds.
        if audio is not None and getattr(self, 'menu_sounds_enabled', True):
            audio.play_ui(kind)

    def menu_sound_target(self, menu, point=None):
        page = getattr(menu, 'controls_page', None) if menu.page == 'controls' else None
        if page is not None:
            index = page.focus if point is None else page.hit(*point)
            if index is None:
                return None
            return id(menu), menu.page, page.view, page.device, page.listening, index
        viewer = getattr(menu, 'cutscene_viewer', None) if menu.page == 'cutscenes' else None
        if viewer is not None:
            index = viewer.focus if point is None else viewer.hit(*point)
            if (index is None or index in (0, 1) and not viewer.unlocked
                    or index == 3 and viewer.scroll_target == 0
                    or index == 4 and viewer.scroll_target == viewer.max_scroll):
                return None
            return id(menu), menu.page, viewer.index, index
        gallery = getattr(menu, 'screenshot_gallery', None) if menu.page == 'screenshots' else None
        if gallery is not None:
            index = gallery.focus if point is None else gallery.hit(*point)
            if index is None or index == 13 and gallery.entry is None:
                return None
            return id(menu), menu.page, gallery.choosing, gallery.deleting, index
        browser = getattr(menu, 'save_browser', None) if menu.page == 'saves' else None
        index = ((browser.focus if browser is not None else menu.option_index if menu.dropdown else menu.focus)
                 if point is None else menu.hit(*point))
        if index is None:
            return None
        context = id(menu), menu.page, menu.dropdown
        if browser is not None:
            if index == 29 and not browser.save_available:
                return None
            if index >= 100 and (index >= 100 + len(browser.items)
                                 or not browser.items[index - 100].exists and not browser.save_available):
                return None
            if index == 27 and not browser.primary_enabled or index == 26 and not browser.entry.exists:
                return None
            return (*context, browser.selected, browser.confirmation, browser.editing, index)
        if menu.dropdown:
            return (*context, 'option', getattr(menu, 'dropdown_control', 0), index)
        if isinstance(menu, GameMenu) and menu.page == 'menu' and not menu.items[index].enabled:
            return None
        if isinstance(menu, DevelopmentMenu) and index not in menu.controls:
            return None
        if isinstance(menu, DevelopmentMenu) and menu.map_enabled and index == 4:
            room = menu.screen if point is None else menu.map_hit(*point)
            return (*context, 'room', menu.level_number, room) if room is not None else None
        return (*context, 'control', index)

    def menu_key_action(self, menu, event):
        fields = ('page', 'focus', 'dropdown', 'option_index', 'level_index', 'screen_index',
                  'screenshot_scale')
        def state():
            browser = getattr(menu, 'save_browser', None)
            viewer = getattr(menu, 'cutscene_viewer', None) if menu.page == 'cutscenes' else None
            page = getattr(menu, 'controls_page', None) if menu.page == 'controls' else None
            return tuple(getattr(menu, name, None) for name in fields) + (
                (browser.selected, browser.focus, browser.mode, browser.confirmation) if browser else ()) + (
                (viewer.index, viewer.focus) if viewer else ()) + (
                (page.focus, page.view, page.device, page.listening) if page else ())

        before = state()
        if event.keysym in ('Return', 'KP_Enter', 'space') and self.menu_sound_target(menu) is not None:
            self.play_menu_sound('click')
        if isinstance(menu, GameMenu):
            action = menu.key(event.keysym, backwards=bool(event.state & 1),
                              char=getattr(event, 'char', ''), control=bool(event.state & 4))
        else:
            action = menu.key(event.keysym, backwards=bool(event.state & 1))
        if (event.keysym in ('Up', 'Down', 'Left', 'Right', 'Tab')
                and before != state()
                and self.menu_sound_target(menu) is not None):
            self.play_menu_sound('hover')
        return action

    def key_press_unrouted(self, event):
        alt = alt_pressed(event, self.window_keys_down)
        # Closing the host window must bypass intro, pause and menu filters.
        if event.keysym == "F4" and alt:
            self.root.destroy()
            return "break"
        if event.keysym in EXTERNAL_CAPTURE_KEYS:
            # Windows Tk binds F10 to WinMenuKey even without a menu bar.
            # Stop that local menu action, not the OS/recorder's global hotkey.
            return "break"
        repeated = event.keysym in self.window_keys_down or (
            len(event.keysym) == 1 and event.keysym.swapcase() in self.window_keys_down)
        self.window_keys_down.add(event.keysym)
        if event.keysym == "F8":
            if not repeated and not alt and not event.state & (0x4 | 0x40):
                if event.state & 0x1:
                    self.capture_screenshot(include_ui=True)
                else:
                    self.capture_screenshot()
            return "break"
        if (getattr(self, 'cutscene_replay', None) is not None
                and self.cutscene_replay_key(event, repeated, alt)):
            return 'break'
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if self.game_menu is not None and self.game_menu.page == 'screenshots' and gallery is not None and gallery.choosing:
            if repeated and event.keysym in ('Return', 'KP_Enter', 'space') and gallery.focus != 40:
                return 'break'
            if repeated and event.keysym in ('Return', 'KP_Enter'):
                return 'break'
            if gallery.commit_key is not None:
                return 'break'
            if event.keysym == 'F2' and not repeated:
                self.toggle_screenshot_menu(event)
                return 'break'
            if alt:
                return 'break'
            key, control = event.keysym.lower(), bool(event.state & 4)
            if gallery.focus == 40 and control and key in ('c', 'x', 'v'):
                start, end = sorted((gallery.caret, gallery.anchor))
                try:
                    if key == 'v':
                        gallery.edit_text('', self.root.clipboard_get())
                    elif start != end:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(gallery.draft[start:end])
                        if key == 'x':
                            gallery.edit_text('Delete')
                except tk.TclError:
                    pass
                action = 'changed'
            else:
                action = self.game_menu.key(event.keysym, bool(event.state & 1),
                                            getattr(event, 'char', ''), control)
            self.apply_game_action(action)
            if event.keysym == 'Escape':
                self.pause_resume_keys.add('Escape')
            return 'break'
        hall = getattr(self.game_menu, 'hall_page', None) if self.game_menu is not None else None
        if hall is not None and self.game_menu.page == 'hall' and (hall.editing or hall.confirming):
            # Typing the name: letters are text, not commands (GetHallOfFameName 2:2220).
            if alt or repeated and event.keysym in ('Return', 'KP_Enter', 'space'):
                return 'break'
            control = bool(event.state & 4)
            if event.keysym in ('Return', 'KP_Enter', 'space', 'Escape'):
                self.play_menu_sound('click')
            self.apply_game_action(self.game_menu.key(
                event.keysym, bool(event.state & 1), getattr(event, 'char', ''), control))
            if event.keysym == 'Escape':
                self.pause_resume_keys.add('Escape')
            return 'break'
        if (self.game_menu is not None and self.game_menu.page == 'saves'
                and self.game_menu.save_browser.editing):
            browser = self.game_menu.save_browser
            if alt:
                return 'break'
            char = getattr(event, 'char', '')
            control = bool(event.state & 4)
            key = event.keysym.lower()
            if control and key in ('c', 'x', 'v'):
                start, end = sorted((browser.anchor, browser.caret))
                try:
                    if key == 'v':
                        browser.edit_text('', self.root.clipboard_get())
                    elif start != end:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(browser.draft[start:end])
                        if key == 'x':
                            browser.edit_text('Delete')
                except tk.TclError:
                    pass
                action = 'changed'
            else:
                action = self.game_menu.key(event.keysym, bool(event.state & 1),
                                            '' if control else char, control)
            self.apply_game_action(action)
            return 'break'
        if event.keysym == "F2":
            if not repeated:
                self.toggle_screenshot_menu(event)
                self.play_menu_sound('click')
            return "break"
        if event.keysym == "F5" or event.keysym == "F3" and not self.development_available():
            return "break"
        if event.keysym == "F3":
            if not repeated:
                self.open_dev_mode(event)
                self.play_menu_sound('click')
            return "break"
        if (self.paused and self.gameplay_controls_available()
                and event.keysym in PAUSE_GAMEPLAY_KEYS
                and (repeated or not is_resume_key(event, self.window_keys_down))):
            self.record_paused_key(event, True)
        if event.keysym in self.pause_resume_keys:
            return "break"
        fullscreen_key = event.keysym == "Return" and alt
        if fullscreen_key:
            if repeated:
                return "break"
            self.pause_resume_keys.add(event.keysym)
            return None
        if event.keysym == "F1":
            if not repeated:
                self.open_game_menu()
                self.play_menu_sound('click')
            return "break"
        if (event.keysym.lower() == 't' and alt and event.state & 0x1
                and not event.state & (0x4 | 0x40)):
            if (not repeated and getattr(self, 'god_mode', False) and not self.paused
                    and self.game_menu is None and self.dev_menu is None
                    and self.gameplay_controls_available()):
                self.god_mode_add_health()
            return 'break'
        command = {"n": "confirm_new", "r": "restart", "t": "sound", "m": "music",
                   "a": "ambience", "s": "save", "o": "open", "l": "open", "h": "hall", "v": "about",
                   "c": "cutscenes", "k": "controls", "p": "options", "q": "quit"}.get(
                       event.keysym.lower()) if alt and not event.state & (0x4 | 0x40) else None
        if command is not None:
            confirming_save = (self.game_menu is not None and self.game_menu.page == 'saves'
                               and self.game_menu.save_browser.confirmation is not None)
            if not repeated and not confirming_save and self.shortcut_page_shown(command):
                self.close_shortcut_page()
                self.pause_resume_keys.add(event.keysym)
            elif not repeated and not confirming_save and (self.game_menu is None or self.game_menu.page != "confirm"):
                if command == "restart" and self.gameplay_controls_available():
                    self.apply_game_action(command, preserve_controls=True)
                else:
                    self.apply_game_action(command)
                self.pause_resume_keys.add(event.keysym)
            return "break"
        if self.game_menu is not None:
            if event.keysym == "Escape":
                return self.escape_key(event)
            if alt or event.state & (0x4 | 0x40):
                return "break"
            if repeated and event.keysym in ("Return", "KP_Enter", "space"):
                return "break"
            page = self.game_menu.page
            self.apply_game_action(self.menu_key_action(self.game_menu, event))
            if self.game_menu is None or self.game_menu.page != page:
                self.pause_resume_keys.update(self.window_keys_down)
            return "break"
        if self.dev_menu is None:
            challenge = getattr(self, "copy_challenge", None)
            if challenge is not None:
                if not repeated or event.keysym in ('Left', 'Right', 'Up', 'Down'):
                    self.copy_challenge_key(challenge, event.keysym)
                return "break"
            if self.paused and event.keysym not in ("Escape", "F2", "F3") and not fullscreen_key:
                if is_resume_key(event, self.window_keys_down):
                    self.set_paused(False)
                    gameplay = self.gameplay_controls_available()
                    self.pause_resume_keys.update(
                        self.window_keys_down - PAUSE_GAMEPLAY_KEYS if gameplay else self.window_keys_down)
                    if gameplay and event.keysym in PAUSE_GAMEPLAY_KEYS:
                        return None
                return "break"
            if getattr(self, "intro", None) is not None:
                if event.keysym == "Escape":
                    return None
                if (not repeated and not alt and not event.state & (0x4 | 0x40)
                        and (event.keysym == "space" or (getattr(self, "attract_stage", None) == "credits"
                             and is_resume_key(event, self.window_keys_down)))):
                    self.finish_intro()
                return "break"
            if getattr(self, "demo", None) is not None:
                if event.keysym == "Escape":
                    return None
                if not repeated and not alt and is_resume_key(event, self.window_keys_down):
                    self.finish_intro()
                return "break"
            if (not self.paused and self.death.counter >= 0
                    and event.keysym not in ("F2", "F3", "Alt_L", "Alt_R")
                    and not fullscreen_key):
                if not repeated and (event.keysym == 'Escape'
                                     or is_resume_key(event, self.window_keys_down)):
                    self.restart_after_death(preserve_controls=True)
                return "break"
            if (event.keysym == 'space' and not alt and not event.state & (0x4 | 0x40)
                    and self.gameplay_controls_available()
                    and (show_time := getattr(self, 'show_remaining_time', None)) is not None):
                if not repeated:
                    show_time()
                return 'break'
            minute_delta = (1 if event.keysym in ('plus', 'KP_Add')
                            or getattr(event, 'char', '') == '+' else
                            -1 if event.keysym in ('minus', 'KP_Subtract')
                            or getattr(event, 'char', '') == '-' else None)
            if (minute_delta is not None and getattr(self, 'god_mode', False)
                    and not alt and not event.state & (0x4 | 0x40)
                    and self.gameplay_controls_available() and self.combat is not None
                    and self.combat.player.alive):
                # Let Tk's ordinary held-key repeat adjust the clock rapidly.
                self.god_mode_adjust_minutes(minute_delta)
                return 'break'
            if (event.keysym.lower() == 'k' and getattr(self, 'god_mode', False)
                    and not self.paused and self.gameplay_controls_available()
                    and self.combat is not None and self.combat.player.alive
                    and not alt and not event.state & (0x1 | 0x4 | 0x40)):
                if not repeated:
                    self.combat.kill_room_enemies(self.room_id)
                    self.render()
                return 'break'
            return None
        if event.keysym == "Escape":
            return self.escape_key(event)
        if repeated and event.keysym in ("Return", "KP_Enter", "space"):
            return "break"
        self.apply_dev_action(self.menu_key_action(self.dev_menu, event))
        if self.dev_menu is None:
            self.pause_resume_keys.add(event.keysym)
        return "break"

    def key_release_unrouted(self, event):
        if event.keysym in EXTERNAL_CAPTURE_KEYS:
            return "break"
        self.window_keys_down.discard(event.keysym)
        released = {event.keysym}
        if len(event.keysym) == 1:
            released.add(event.keysym.swapcase())
            self.window_keys_down.discard(event.keysym.swapcase())
        if self.paused and self.gameplay_controls_available() and event.keysym in PAUSE_GAMEPLAY_KEYS:
            self.record_paused_key(event, False)
            self.pause_resume_keys.difference_update(released)
            return "break"
        if event.keysym == "F3":
            self.dev_toggle_held = False
        elif event.keysym == "Escape":
            self.escape_release(event)
        if released.intersection(self.pause_resume_keys):
            self.pause_resume_keys.difference_update(released)
            return "break"
        if self.modal_open():
            return "break"
        if getattr(self, "intro", None) is not None or getattr(self, "demo", None) is not None:
            return "break"
        return None

    def copy_challenge_key(self, challenge, key):
        """Port extension: arrows/Enter (and a controller) pick a symbol too."""
        if self.paused or not getattr(challenge, 'input_ready', True):
            return
        if key in ('Left', 'Right', 'Up', 'Down'):
            if challenge.focus is None:
                challenge.focus = 0
            else:
                column, row = challenge.focus % 5, challenge.focus // 5
                column = (column + {'Left': -1, 'Right': 1}.get(key, 0)) % 5
                row = (row + {'Up': -1, 'Down': 1}.get(key, 0)) % 2
                challenge.focus = row * 5 + column
            self.render()
        elif key in ('Return', 'KP_Enter', 'space') and challenge.focus is not None:
            challenge.choose(challenge.focus)
            self.last_copy_at = time.perf_counter()
            self.resolve_copy_challenge()
            self.render()

    def dev_pointer(self, event):
        if hasattr(self, 'active_cutscene_gallery') and self.active_cutscene_gallery() is not None:
            return menu_viewport_point(
                event.x, event.y, self.canvas.winfo_width(), self.canvas.winfo_height())
        menu = getattr(self, 'game_menu', None)
        page = getattr(menu, 'page', None)
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        wide = (menu.save_browser if page == 'saves' else
                getattr(menu, 'screenshot_gallery', None) if page == 'screenshots' else None)
        if wide is not None:
            spread, shift = wide.wide_layout(width, height)
            if spread:   # the wide page uses the whole window; its panel starts `shift` units in
                point = menu_viewport_point(event.x, event.y, width, height)
                return None if point is None else (point[0] - shift, point[1])
        return viewport_point(
            event.x, event.y, self.canvas.winfo_width(), self.canvas.winfo_height()
        )

    def dev_click(self, event):
        if getattr(self, 'cutscene_replay', None) is not None:
            # One click on a card starts its film. The second press of a
            # double click made out of habit must not pause it at once.
            fresh = time.perf_counter() - self.cutscene_replay.started_at < 0.5
            if getattr(event, 'num', 1) == 1 and not fresh:
                point = self.dev_pointer(event)
                if point is not None:
                    self.pause_cutscene_replay(not self.cutscene_replay.paused)
            return 'break'
        if not self.modal_open():
            return "break" if self.paused else None
        if getattr(event, "num", 1) != 1:
            return "break"
        point = self.dev_pointer(event)
        if point is not None:
            if self.game_menu is not None:
                if (self.game_menu.page == 'cutscenes'
                        and self.game_menu.cutscene_viewer.begin_drag(*point)):
                    return 'break'
                gallery = self.game_menu.screenshot_gallery if self.game_menu.page == 'screenshots' else None
                if gallery is not None:
                    gallery.begin_drag(*point)
                self.save_scroll_dragging = (self.game_menu.page == 'saves'
                    and self.game_menu.save_browser.hit(*point) == 24)
                self.screenshot_scroll_dragging = (self.game_menu.page == 'screenshots'
                    and self.game_menu.screenshot_gallery is not None
                    and self.game_menu.screenshot_gallery.hit(*point) == 14)
                if self.menu_sound_target(self.game_menu, point) is not None:
                    self.play_menu_sound('click')
                self.apply_game_action(self.game_menu.click(*point))
                self.pause_resume_keys.update(self.window_keys_down)
            elif getattr(self, "copy_challenge", None) is not None:
                if not self.paused and getattr(self.copy_challenge, 'input_ready', True):
                    # The original tracks GetMouse while StillDown is true.
                    self.copy_pointer_held = True
                    focus = self.copy_challenge.hit(*point)
                    if self.copy_challenge.focus != focus:
                        self.copy_challenge.focus = focus
                        self.render()
            else:
                if self.menu_sound_target(self.dev_menu, point) is not None:
                    self.play_menu_sound('click')
                self.apply_dev_action(self.dev_menu.click(*point))
        return "break"

    def dev_double_click(self, event):
        viewer = self.active_cutscene_gallery() if hasattr(self, 'active_cutscene_gallery') else None
        if viewer is None:
            return self.dev_click(event)
        point = self.dev_pointer(event)
        if point is not None:
            action = viewer.double_click(*point)
            if action == 'cutscene_play':
                self.play_menu_sound('click')
            self.apply_game_action(action)
            self.pause_resume_keys.update(self.window_keys_down)
        return 'break'

    def dev_release(self, event):
        viewer = self.active_cutscene_gallery() if hasattr(self, 'active_cutscene_gallery') else None
        if viewer is not None and viewer.drag is not None and getattr(event, 'num', 1) == 1:
            point = self.dev_pointer(event)
            action = viewer.end_drag(*(point if point is not None else (-1, -1)))
            if action == 'cutscene_play':
                self.play_menu_sound('click')
            self.apply_game_action(action)
            self.set_window_cursor('')
            return 'break'
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None and gallery.drag_target is not None and getattr(event, 'num', 1) == 1:
            point = self.dev_pointer(event)
            self.apply_game_action(gallery.release_drag(*(point if point is not None else (-1, -1))))
            self.set_window_cursor('')
            return 'break'
        if getattr(self, 'screenshot_scroll_dragging', False):
            self.screenshot_scroll_dragging = False
            return 'break'
        if getattr(self, 'save_scroll_dragging', False):
            self.save_scroll_dragging = False
            return 'break'
        challenge = getattr(self, "copy_challenge", None)
        if challenge is None:
            self.copy_pointer_held = False
            return None
        if getattr(event, "num", 1) != 1:
            return "break"
        if not self.copy_pointer_held:
            return "break"
        self.copy_pointer_held = False
        point = self.dev_pointer(event)
        symbol = challenge.hit(*point) if point is not None else None
        if not self.paused and symbol is not None and getattr(challenge, 'input_ready', True):
            challenge.choose(symbol)
            self.last_copy_at = time.perf_counter()
            self.resolve_copy_challenge()
            self.render()
        elif challenge.focus is not None:
            challenge.focus = None
            self.render()
        return "break"

    def dev_hover(self, event):
        viewer = self.active_cutscene_gallery() if hasattr(self, 'active_cutscene_gallery') else None
        if viewer is not None and viewer.drag is not None:
            point = self.dev_pointer(event)
            if point is not None and viewer.move_drag(point[0]):
                self.set_window_cursor('fleur')
                self.redraw_cutscene_gallery()
            return 'break'
        if getattr(self, 'cutscene_replay', None) is not None:
            return 'break'
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None and gallery.drag_target is not None:
            point = self.dev_pointer(event)
            before = gallery.dragging, gallery.hovered
            if gallery.move_drag(*(point if point is not None else (-1, -1))):
                self.set_window_cursor('hand2' if gallery.hovered == 13 else 'fleur')
                # A step that only carries the picture moves its own canvas item;
                # starting, or reaching or leaving the delete button, redraws the page.
                if before != (True, gallery.hovered) or not self.move_screenshot_held(gallery):
                    self.redraw_screenshot_gallery()
                self.schedule_screenshot_gallery()
            return 'break'
        if getattr(self, 'screenshot_scroll_dragging', False) and self.game_menu is not None:
            gallery = self.game_menu.screenshot_gallery
            point = self.dev_pointer(event)
            if gallery is not None and point is not None and not gallery.choosing and not gallery.deleting:
                gallery.scroll_target = max(0, min(gallery.max_scroll, gallery.max_scroll *
                    (point[1] - gallery.LIST[1]) / (gallery.LIST[3] - gallery.LIST[1])))
                self.redraw_screenshot_gallery()
                self.schedule_screenshot_gallery()
            return 'break'
        if (getattr(self, 'save_scroll_dragging', False) and self.game_menu is not None
                and self.game_menu.page == 'saves'):
            point = self.dev_pointer(event)
            if point is not None:
                browser = self.game_menu.save_browser
                browser.scroll_target = max(0, min(browser.max_scroll, browser.max_scroll *
                    (point[1] - browser.LIST[1]) / (browser.LIST[3] - browser.LIST[1])))
                self.schedule_save_scroll()
            return 'break'
        challenge = getattr(self, "copy_challenge", None)
        if challenge is not None and not (self.game_menu is not None and self.game_menu.page == 'cutscenes'):
            if not self.copy_pointer_held or self.paused:
                return
            point = self.dev_pointer(event)
            focus = challenge.hit(*point) if point is not None else None
            if challenge.focus != focus:
                challenge.focus = focus
                self.render()
            return
        menu = self.game_menu or self.dev_menu
        if menu is not None:
            point = self.dev_pointer(event)
            target = self.menu_sound_target(menu, point if point is not None else (-1, -1))
            if target is not None and target != getattr(self, 'ui_hover_target', None):
                self.play_menu_sound('hover')
            self.ui_hover_target = target
            if menu.hover(*(point if point is not None else (-1, -1))):
                if menu is self.dev_menu:
                    self.redraw_dev_menu()
                elif menu.page == 'saves':
                    self.redraw_save_menu()
                elif menu.page == 'screenshots' and menu.screenshot_gallery is not None:
                    self.redraw_screenshot_gallery()
                elif menu.page == 'cutscenes':
                    self.redraw_cutscene_gallery()
                else:
                    self.redraw_menu()
            if menu is self.game_menu and menu.page == 'cutscenes':
                self.set_window_cursor('hand2' if target is not None else '')
            if menu is self.dev_menu:
                hovered = menu.hovered_screen if menu.map_enabled else None
                self.set_window_cursor('hand2' if hovered is not None and not menu.dropdown else '')
            elif menu.page == 'saves':
                self.set_window_cursor('hand2' if menu.save_browser.hovered == 25 else '')

    def set_window_cursor(self, cursor):
        """Show the pointer as ``cursor`` over the window ('' the arrow, 'none' hidden).
        It is the toplevel's cursor, which the canvas and the windows over it show, having
        none of their own: configuring the canvas, even with the cursor it had, made Tk
        paint all of it again, about 8 ms at 3440x1440 (at times 30-70) for each option
        the pointer reached or left where the cursor changes."""
        root = self.root
        if str(root.cget('cursor')) != cursor:
            root.configure(cursor=cursor)
            refresh_pointer(root)   # on the screen now, not when the pointer next moves

    def screenshot_gallery_placement(self, gallery, width, height):
        """Where the screenshots page goes in a window: the game's picture (size, position),
        then the page's, which is wider in a wide window."""
        size, position = fit_viewport(width, height)
        if gallery.wide_layout(width, height)[0]:
            # The wide page fills the window; the game's picture stays centred behind it.
            return size, position, *fit_menu_viewport(width, height)
        return size, position, size, position

    def show_screenshot_held(self, gallery, size, position):
        """Show the picture being dragged in a canvas item of its own over the page,
        or take it away when nothing is dragged."""
        held = gallery.held_overlay(size) if gallery is not None else None
        if held is None:
            self.hide_screenshot_held()
            return
        picture, (x, y) = held
        place = float(position[0] + x), float(position[1] + y)
        shown = getattr(self, 'screenshot_held', None)
        if shown is None or shown[2] is not picture:
            photo = ImageTk.PhotoImage(picture, master=self.canvas)
            if shown is None:
                item = self.canvas.create_image(*place, image=photo, anchor='nw')
            else:
                item = shown[0]
                self.canvas.itemconfigure(item, image=photo)
            self.screenshot_held = item, photo, picture
        item = self.screenshot_held[0]
        if tuple(self.canvas.coords(item)) != place:
            self.canvas.coords(item, *place)

    def hide_screenshot_held(self):
        shown = getattr(self, 'screenshot_held', None)
        self.screenshot_held = None
        if shown is not None:
            try:
                self.canvas.delete(shown[0])
            except tk.TclError:
                pass

    @staticmethod
    def screenshot_lava_region(gallery, size):
        """The delete button, its hover label and where a dropped picture falls into the
        lava and burns, in the pixels of the page's picture."""
        delete = gallery.DELETE
        fall = (delete[0] - 8, delete[1] - 48, delete[2] + 8, delete[3] + 2)
        rects = [gallery.pixel_rect(rect, size) for rect in (delete, gallery.hint_rect, fall)]
        return (max(0, min(rect[0] for rect in rects)), max(0, min(rect[1] for rect in rects)),
                min(size[0], max(rect[2] for rect in rects) + 1), min(size[1], max(rect[3] for rect in rects) + 1))

    def show_screenshot_lava(self, frame, region, position, refresh):
        """Show the page's delete button and its label in a small canvas item of their own,
        just over the page. The lava changes twelve times a second and the label comes and
        goes with the pointer: each copy into the page's photo made Tk look over all of
        that photo again (2 ms at 3440x1440); in this one it looks over only these pixels.
        ``refresh`` is true to show all of the region again, or the boxes of the page that
        changed in it."""
        shown = getattr(self, 'screenshot_lava', None)
        if region[0] >= region[2] or region[1] >= region[3]:
            self.hide_screenshot_lava()
            return
        place = float(position[0] + region[0]), float(position[1] + region[1])
        if shown is None or shown[2] != region:
            photo = ImageTk.PhotoImage(frame.crop(region).convert('RGB'), master=self.canvas)
            if shown is None:
                item = self.canvas.create_image(*place, image=photo, anchor='nw')
                self.canvas.tag_raise(item, self.canvas.find_all()[0])   # under the held picture
            else:
                item = shown[0]
                self.canvas.itemconfigure(item, image=photo)
            self.screenshot_lava = item, photo, region
        elif refresh:
            for box in ([region] if refresh is True else refresh):
                box = (max(box[0], region[0]), max(box[1], region[1]), min(box[2], region[2]), min(box[3], region[3]))
                if box[0] < box[2] and box[1] < box[3]:
                    put_patch(shown[1], frame.crop(box), box[0] - region[0], box[1] - region[1])
        item = self.screenshot_lava[0]
        if tuple(self.canvas.coords(item)) != place:
            self.canvas.coords(item, *place)

    def hide_screenshot_lava(self):
        shown = getattr(self, 'screenshot_lava', None)
        self.screenshot_lava = None
        if shown is not None:
            try:
                self.canvas.delete(shown[0])
            except tk.TclError:
                pass

    def move_screenshot_held(self, gallery):
        """Carry the dragged picture to the pointer without redrawing the page under it;
        false when the page on screen is not the one it was shown over."""
        presented = getattr(self, 'screenshot_gallery_frame', None)
        if presented is None or presented[0] is not gallery or getattr(self, 'screenshot_held', None) is None:
            return False
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width <= 1 or height <= 1:
            width, height = VISIBLE_SIZE[0] * 2, VISIBLE_SIZE[1] * 2
        size, position = self.screenshot_gallery_placement(gallery, width, height)[2:]
        if (size, position) != presented[5]:
            return False
        self.show_screenshot_held(gallery, size, position)
        return True

    def redraw_dev_menu(self):
        # F3 pauses the world; pointer changes only need the frozen picture under the menu.
        underlay = self.kept_menu_underlay()
        self.native_viewport = self.draw_screenshot_notice(
            self.dev_menu.draw(self.screenshot_viewport if underlay is None else underlay, self.ui_font))
        self.present_viewport()

    def kept_menu_underlay(self):
        """The game's picture under the open menu as the last render() drew it, while it still
        holds: the game is paused, so its world has not moved, and no other picture was shown
        since. Unlike the captures' picture (screenshot_viewport), it has no prompt to restart."""
        kept = getattr(self, 'menu_underlay', None)
        if (kept is None or not getattr(self, 'paused', False) or kept[1] is not self.screenshot_viewport
                or (getattr(self, 'dev_menu', None) is None and getattr(self, 'game_menu', None) is None)
                or getattr(self, 'cutscene_replay', None) is not None):
            return None
        return kept[0]

    def redraw_menu(self):
        """Show again a menu of which only the focus or the page changed (the pointer or the
        keys moved over it, a page led to another): over the game's picture kept under it.
        Drawing the game again took 2-4 ms of each step, whatever the window's size."""
        underlay = self.kept_menu_underlay()
        if underlay is None:
            self.render()
            return
        self.native_viewport = self.draw_menus(underlay)
        self.present_viewport()

    def dev_pointer_leave(self, _event):
        viewer = self.active_cutscene_gallery() if hasattr(self, 'active_cutscene_gallery') else None
        if viewer is not None:
            viewer.drag = None
            viewer.dragged = False
            viewer.last_clicked = None
            viewer.hovered = None
            self.set_window_cursor('')
            self.redraw_cutscene_gallery()
        self.ui_hover_target = None
        if self.game_menu is not None and self.game_menu.page == 'saves':
            if self.game_menu.hover(-1, -1):
                self.redraw_save_menu()
            self.set_window_cursor('')
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None and gallery.drag_target is not None:
            gallery.cancel_drag()
            self.set_window_cursor('')
            self.redraw_screenshot_gallery()
        menu = self.dev_menu
        if menu is not None and menu.preview_enabled:
            if menu.hover(-1, -1):
                self.redraw_dev_menu()
            self.set_window_cursor('')

    def dev_scroll(self, event):
        menu = getattr(self, 'game_menu', None)
        if menu is not None and menu.page == 'menu':
            point = self.dev_pointer(event)
            if point is not None and DevelopmentMenu.contains(menu.PANEL, *point):
                delta = getattr(event, 'delta', 0)
                steps = -delta / 120 if delta else -1 if getattr(event, 'num', None) == 4 else 1
                if menu.wheel(steps):
                    self.redraw_menu()
            return 'break'
        if menu is not None and menu.page == 'cutscenes':
            if getattr(self, 'cutscene_replay', None) is None:
                delta = getattr(event, 'delta', 0)
                steps = -delta / 120 if delta else (-1 if getattr(event, 'num', None) == 4 else 1)
                menu.cutscene_viewer.wheel(steps)
                self.redraw_cutscene_gallery()
            return 'break'
        if menu is not None and menu.page == 'screenshots' and menu.screenshot_gallery is not None:
            gallery = menu.screenshot_gallery
            point = self.dev_pointer(event)
            rect = gallery.FOLDER_LIST if gallery.choosing else gallery.LIST
            if point is not None and gallery.contains(rect, *point):
                delta = getattr(event, 'delta', 0)
                steps = -delta / 120 if delta else -1 if getattr(event, 'num', None) == 4 else 1
                gallery.wheel(steps)
                self.redraw_screenshot_gallery()
                self.schedule_screenshot_gallery()
            return 'break'
        if getattr(self, 'game_menu', None) is not None and self.game_menu.page == 'saves':
            browser = self.game_menu.save_browser
            point = self.dev_pointer(event)
            if point is not None and browser.contains(browser.LIST, *point):
                delta = getattr(event, 'delta', 0)
                steps = -delta / 120 if delta else -1 if getattr(event, 'num', None) == 4 else 1
                if browser.wheel(steps):
                    self.schedule_save_scroll()
            return 'break'
        if self.dev_menu is None:
            return None
        if not self.dev_menu.dropdown:
            return None
        point = self.dev_pointer(event)
        if point is not None and self.dev_menu.hit(*point) is not None:
            delta = getattr(event, "delta", 0)
            if delta:
                # A touchpad sends many small deltas: one row per whole notch (120).
                rest = getattr(self, 'dev_wheel_rest', 0)
                rest = (rest if rest * delta <= 0 else 0) - delta
                steps = int(rest / 120)
                self.dev_wheel_rest = rest - steps * 120
            else:
                steps = -1 if getattr(event, "num", None) == 4 else 1
            previous = self.dev_menu.option_index
            if steps and self.dev_menu.scroll(steps, point):
                if self.dev_menu.option_index != previous:
                    self.play_menu_sound('hover')
                # F3 froze the world: only the list's rows change.
                self.redraw_dev_menu()
        return "break"

    def schedule_save_scroll(self):
        menu = getattr(self, 'game_menu', None)
        pending = getattr(self, 'save_scroll_after_id', None)
        if pending is not None and getattr(self, 'save_scroll_menu', None) is not menu:
            self.root.after_cancel(pending)
            self.save_scroll_after_id = None
        if (menu is None or menu.page != 'saves'
                or menu.save_browser.editing or menu.save_browser.confirmation
                or abs(menu.save_browser.scroll - menu.save_browser.scroll_target) < 0.1
                or getattr(self, 'save_scroll_after_id', None) is not None):
            return
        browser = menu.save_browser
        self.save_scroll_menu = menu
        previous = time.perf_counter()

        def animate():
            nonlocal previous
            self.save_scroll_after_id = None
            if self.game_menu is not menu or menu.page != 'saves' or menu.save_browser is not browser:
                return
            now = time.perf_counter()
            moving = browser.animate(now - previous)
            previous = now
            self.redraw_save_menu()
            if moving:
                delay = max(1, round(1000 / 120 - (time.perf_counter() - now) * 1000))
                self.save_scroll_after_id = self.root.after(delay, animate)

        self.save_scroll_after_id = self.root.after(8, animate)

    def set_peaceful(self, peaceful):
        self.peaceful = peaceful
        if self.dev_menu is not None:
            self.dev_menu.peaceful = peaceful
        self.clear_keys(None)
        if self.combat is not None:
            self.combat.last_guard_at = time.perf_counter()
        self.render()

    def set_god_mode(self, enabled):
        self.god_mode = bool(enabled)
        if self.dev_menu is not None:
            self.dev_menu.god_mode = self.god_mode
        if self.combat is not None:
            self.combat.god_mode = self.god_mode
        self.render()

    @staticmethod
    def dev_map_damage(menu, previous, native, entry, size):
        """Regions of the enlarged map page that may differ from the shown frame.

        Outside the map the frame is the native menu enlarged, so a small native
        comparison finds the change; inside it the HD map picture names its own
        highlights. Anything unknown compares the whole frame.
        """
        whole = [(0, 0, *size)]
        if len(previous) < 5 or previous[3].size != native.size or not menu.map_enabled:
            return whole
        layer = DevelopmentMenu.map_layer_damage(previous[4], entry)
        if layer is None:
            return whole
        rects = []
        changed = ImageChops.difference(previous[3], native).getbbox()
        if changed is not None:
            rects.append(menu.projected_rect(changed, size))
        if layer:
            left, top, _right, _bottom = menu.projected_rect(menu.control_rect(4), size)
            rects += [(x1 + left, y1 + top, x2 + left, y2 + top) for x1, y1, x2, y2 in layer]
        pad = max(2, round(size[1] / 384))  # nearest-neighbour edges of a native pixel
        rects = [(max(0, x1 - pad), max(0, y1 - pad), min(size[0], x2 + pad), min(size[1], y2 + pad))
                 for x1, y1, x2, y2 in rects]
        return [rect for rect in rects if rect[0] < rect[2] and rect[1] < rect[3]]

    def present_viewport(self, canvas_size=None):
        """Show the picture in the window. ``canvas_size``: drawn for a canvas of that
        size instead of the canvas's own (see present_before_fullscreen)."""
        if self.native_viewport is None:
            return
        width, height = canvas_size or (self.canvas.winfo_width(), self.canvas.winfo_height())
        if width <= 1 or height <= 1:
            width, height = VISIBLE_SIZE[0] * 2, VISIBLE_SIZE[1] * 2
        size, position = fit_viewport(width, height)
        # Kept only while the window shows menus drawn at the game's resolution (see patch_native_menu).
        native_menu, self.native_menu_frame = getattr(self, 'native_menu_frame', None), None
        # What the photo shown holds, should another take its place (show_photo keeps it).
        self.leaving_menu_frame = native_menu
        saves = getattr(self, 'save_menu_frame', None)
        if native_menu is None and saves is not None and saves[2] is getattr(self, 'image_ref', None):
            self.leaving_menu_frame = SavePageShown(saves[2], saves[0], saves[5], saves[1], saves[3], saves[4])
        if (sys.platform == "win32" and getattr(self, "fullscreen", False)
                and not getattr(self, "paused", False)
                and getattr(self, "game_menu", None) is None
                and getattr(self, "dev_menu", None) is None
                and getattr(self, "copy_challenge", None) is None):
            from pop2.bitmap_presenter import CanvasBitmap

            if getattr(self, "bitmap_presenter", None) is None:
                self.bitmap_presenter = CanvasBitmap(self.canvas)
                # The game's own picture needs no photo. The one shown last, of the game's size
                # (a menu's, or the paused game's), is kept with the pixels Tk prepared for it
                # and what it shows: the next menu over the game writes into it only what
                # changed. A new photo took about 22 ms at 3440x1440, writing all of one 15.
                photo = getattr(self, 'image_ref', None)
                if (photo is not None and getattr(self, 'image_ref_size', None) == size
                        and self.canvas.find_all()):
                    self.keep_photo(photo, size, native_menu if native_menu is not None
                                    and native_menu[0] is photo else None)
                self.drop_spare_photos(keep=size)
                for item in self.canvas.find_all():
                    self.canvas.itemconfigure(item, image="")
                self.image_ref = None
            frame = self.native_viewport.crop(VISIBLE_VIEWPORT).convert("RGB").resize(size, Image.Resampling.NEAREST)
            self.bitmap_presenter.present(frame, position)
            return
        if getattr(self, "bitmap_presenter", None) is not None:
            self.bitmap_presenter.close()
            self.bitmap_presenter = None
        if (hasattr(self, 'present_cutscene_gallery')
                and self.present_cutscene_gallery(*fit_menu_viewport(width, height))):
            return
        game_menu = getattr(self, 'game_menu', None)
        gallery = getattr(game_menu, 'screenshot_gallery', None) if getattr(game_menu, 'page', None) == 'screenshots' else None
        if gallery is not None:
            fitted, origin, size, position = self.screenshot_gallery_placement(gallery, width, height)
            spread, shift = gallery.wide_layout(width, height)
            cached = getattr(self, 'screenshot_gallery_source', None)
            if cached is None or cached[0] is not self.screenshot_viewport or cached[1] != size:
                source = self.menu_backdrop(fitted, origin, size, position)
                self.screenshot_gallery_source = self.screenshot_viewport, size, source
            else:
                source = cached[2]
            # A dragged picture is shown over the page by itself (show_screenshot_held). The page
            # stays RGBA: Tk is given only the parts that changed, their alpha ignored. It is
            # drawn in place: the page shown, drawn over again where it changed.
            page = gallery.draw(source, self.ui_font, visible=True, held_picture=False, in_place=True)
            redrawn = gallery.redrawn
            frame = self.draw_screenshot_notice(page, visible=True, uniform=bool(spread), inset=shift)
            previous = getattr(self, 'screenshot_gallery_frame', None)
            state = id(self.screenshot_viewport), id(self.ui_font), gallery.surface_state, gallery.overlay_active
            lava = self.screenshot_lava_region(gallery, size)
            refresh_lava = True
            if previous is not None and previous[0] is gallery and previous[1].size == size and previous[2] is self.image_ref:
                refresh_lava = False
                dialog = gallery.dialog_rect
                if previous[1] is frame:
                    # The page shown was drawn over again: it changed only in the parts it
                    # lists, compared with the pixels they had, and only where they differ.
                    damages = (page_damage(redrawn, frame) if redrawn is not None and previous[3] == state
                               else [(0, 0, *frame.size)])
                elif previous[3] == state and dialog is None:
                    # Only the thumbnail strip, the animated delete button, its hover label, the
                    # controls lit by the focus and a held or burning picture (where it was and
                    # where it is) can change.
                    damages = []
                    regions = [(*region[:2], region[2] + 1, region[3] + 1)
                               for region in (gallery.pixel_rect(rect, size) for rect in
                                              (gallery.LIST, gallery.DELETE, gallery.hint_rect, *gallery.lit_rects))]
                    regions += [rect for rect in (previous[4], gallery.held_rect) if rect is not None]
                    for index, region in enumerate(regions):
                        region = (max(0, region[0]), max(0, region[1]),
                                  min(frame.width, region[2]), min(frame.height, region[3]))
                        if region[0] >= region[2] or region[1] >= region[3]:
                            continue
                        if index == 0 and previous[6] == gallery.list_drawn:
                            continue   # drawn from the same thumbnails, scroll and selection
                        cells = gallery.list_changes(previous[6]) if index == 0 and not gallery.scrolling else None
                        if cells is not None:
                            # Only the focus moved in the list: compare the cells it left and reached.
                            for cell in cells:
                                cell = gallery.pixel_rect(cell, size)
                                cell = (max(region[0], cell[0]), max(region[1], cell[1]),
                                        min(region[2], cell[2] + 1), min(region[3], cell[3] + 1))
                                if cell[0] >= cell[2] or cell[1] >= cell[3]:
                                    continue
                                local = ImageChops.difference(previous[1].crop(cell),
                                                              frame.crop(cell)).getbbox(alpha_only=False)
                                if local:
                                    damages.append((local[0] + cell[0], local[1] + cell[1],
                                                    local[2] + cell[0], local[3] + cell[1]))
                            continue
                        if index == 0 and gallery.scrolling:
                            # A moving list changes all over: send it without comparing.
                            local = (0, 0, min(region[2], frame.width) - region[0],
                                     min(region[3], frame.height) - region[1])
                        else:
                            # alpha_only: the page is opaque, so a difference's alpha is zero everywhere.
                            local = ImageChops.difference(previous[1].crop(region),
                                                          frame.crop(region)).getbbox(alpha_only=False)
                        if local:
                            damages.append((local[0] + region[0], local[1] + region[1],
                                            local[2] + region[0], local[3] + region[1]))
                elif previous[3] == state and previous[7] is not None and previous[7] == gallery.modal_drawn:
                    # The dialog is drawn again over the same darkened page: only it can change.
                    region = gallery.pixel_rect((dialog[0] - 2, dialog[1] - 2, dialog[2] + 2, dialog[3] + 2), size)
                    region = (max(0, region[0]), max(0, region[1]), min(frame.width, region[2] + 1),
                              min(frame.height, region[3] + 1))
                    local = ImageChops.difference(previous[1].crop(region), frame.crop(region)).getbbox(alpha_only=False)
                    damages = [(local[0] + region[0], local[1] + region[1], local[2] + region[0],
                                local[3] + region[1])] if local else []
                elif (previous[7] is None) != (dialog is None):
                    # A dialog opening or closing darkens or lightens all of the page: no need to compare.
                    damages = [(0, 0, *frame.size)]
                else:
                    damage = ImageChops.difference(previous[1], frame).getbbox(alpha_only=False)
                    damages = [damage] if damage else []
                if damages and (damages[0][2] - damages[0][0]) * (damages[0][3] - damages[0][1]) * 3 >= frame.width * frame.height * 2:
                    # Most of the page: put it into the photo directly. A patch of it would be copied
                    # in twice, and Tk prepares the shown photo's pixels each time (32 ms in all
                    # at 3440x1440, instead of 48).
                    self.image_ref.paste(frame)
                    damages, refresh_lava = [], True
                lava_damages = []
                for damage in damages:
                    if damage[0] < lava[2] and lava[0] < damage[2] and damage[1] < lava[3] and lava[1] < damage[3]:
                        lava_damages.append(damage)
                        if (lava[0] <= damage[0] and lava[1] <= damage[1] and damage[2] <= lava[2]
                                and damage[3] <= lava[3] and getattr(self, 'screenshot_lava', None) is not None):
                            continue   # only the lava's own item shows it
                    put_patch(self.image_ref, frame.crop(damage), *damage[:2])
                refresh_lava = refresh_lava or lava_damages
                self.keep_photo_at(position)
            else:
                self.show_photo(frame.convert('RGB'), position)
            self.screenshot_gallery_frame = (gallery, frame, self.image_ref, state, gallery.held_rect, (size, position),
                                             gallery.list_drawn, gallery.modal_drawn)
            self.show_screenshot_lava(frame, lava, position, refresh_lava)
            self.show_screenshot_held(gallery, size, position)
            return
        self.hide_screenshot_held()
        self.hide_screenshot_lava()
        self.screenshot_gallery_frame = self.screenshot_gallery_source = None
        if getattr(game_menu, 'page', None) == 'saves':
            browser = game_menu.save_browser
            size, position, source, page, frame, state, listing = self.save_page_frame(browser, width, height)
            redrawn = browser.redrawn
            modal = browser.editing or browser.confirmation
            previous = getattr(self, 'save_menu_frame', None)
            if previous is None or previous[2] is not self.image_ref:
                # The page opens on a photo kept that shows it already (by F1's warm-up).
                previous = self.save_photo_back(game_menu, browser, frame, state, position) or previous
            if (previous is not None and previous[0] is game_menu and previous[1].size == frame.size
                    and previous[2] is self.image_ref):
                damages = []
                if previous[1] is page and redrawn is not None:
                    # The page shown was drawn over again: it changed only in the parts it
                    # lists, compared with the pixels they had, and only where they differ.
                    damages = page_damage(redrawn, frame)
                shown = previous[1] is frame and redrawn is not None
                rects = [] if shown else [(0, 0, *frame.size)]
                if not shown and bool(previous[3][9] or previous[3][10]) != bool(modal):
                    # A dialog opening or closing darkens or lightens all of the page: sent
                    # whole, without comparing it (about 20 ms at 3440x1440) or cutting it.
                    rects = []
                    self.image_ref.paste(frame)
                elif not shown and previous[3] == state:
                    # Only what the pointer or the keys light up: the dialog, or the tabs, the
                    # footer and the list (compared alone, not the whole window). A list that did
                    # not scroll changed only in the rows the focus left and reached.
                    parts = [browser.DIALOG] if modal else [*browser.TABS, *browser.footer_rects]
                    if not modal and previous[4][2:] != listing[2:]:
                        parts.append(browser.NAME_AREA)
                    if not modal and previous[4][1] != browser.scroll:
                        parts.append(browser.LIST)
                    elif not modal:
                        listed = browser.LIST
                        for focus in {previous[4][0], browser.focus} if previous[4][0] != browser.focus else ():
                            if isinstance(focus, int) and focus >= 100:
                                row = browser.row_rect(focus - 100)
                                parts.append((row[0], max(listed[1], row[1]), row[2], min(listed[3], row[3])))
                    rects = [browser.pixel_rect((*rect[:2], rect[2] + 1, rect[3] + 1), size) for rect in parts
                             if rect[1] < rect[3]]
                for rect in rects:
                    rect = (max(0, rect[0]), max(0, rect[1]), min(frame.width, rect[2]), min(frame.height, rect[3]))
                    if rect[0] >= rect[2] or rect[1] >= rect[3]:
                        continue
                    # alpha_only: the page is opaque, so a difference's alpha is zero everywhere.
                    damage = ImageChops.difference(previous[1].crop(rect), frame.crop(rect)).getbbox(alpha_only=False)
                    if damage is not None:
                        damages.append((damage[0] + rect[0], damage[1] + rect[1],
                                        damage[2] + rect[0], damage[3] + rect[1]))
                for damage in damages:
                    put_patch(self.image_ref, frame.crop(damage), *damage[:2])
                self.save_menu_frame = (game_menu, frame, self.image_ref, state, listing, browser)
                self.keep_photo_at(position)
                return
        else:
            self.save_menu_frame = None
            if game_menu is None:
                self.save_menu_source = self.save_grounds = None   # kept while the menu is open
            menu = getattr(self, 'dev_menu', None)
            source = self.native_viewport.crop(VISIBLE_VIEWPORT)
            if menu is not None and menu.preview_enabled:
                source = source.convert('RGB')  # cheaper here than on the enlarged frame
            elif (game_menu is not None or menu is not None or getattr(self, 'copy_challenge', None) is not None
                  or getattr(self, 'paused', False)):
                # A still picture: drawn again, only what changed is sent (a paused game too).
                if native_menu is None:
                    # Back from a wide page: the menu's own photo, as it was under that page.
                    native_menu = self.menu_photo_back(size, position)
                if self.patch_native_menu(native_menu, source, size, position):
                    return
                native_menu = source   # remembered below, with the photo made from it
            frame = source.resize(size, Image.Resampling.NEAREST)
        menu = getattr(self, 'dev_menu', None)
        if menu is not None and menu.preview_enabled:
            # RGB: an RGBA difference's bounding box would only see alpha.
            native = self.native_viewport.convert('RGB')
            frame = menu.present_map(frame, self.ui_font)
            if frame.mode != 'RGB':
                frame = frame.convert('RGB')
            entry = menu.map_layer_entry(frame.size)
            previous = getattr(self, 'dev_map_frame', None)
            if (previous is not None and previous[0] is menu and previous[1].size == frame.size
                    and previous[2] is self.image_ref):
                # Upload only changed rooms/labels instead of a full 1440p Tk photo.
                shown = previous[1]
                for rect in self.dev_map_damage(menu, previous, native, entry, frame.size):
                    damage = ImageChops.difference(shown.crop(rect), frame.crop(rect)).getbbox()
                    if damage is None:
                        continue
                    damage = (damage[0] + rect[0], damage[1] + rect[1],
                              damage[2] + rect[0], damage[3] + rect[1])
                    patch = frame.crop(damage)
                    # The remembered frame stays exactly what the window shows.
                    shown.paste(patch, damage[:2])
                    put_patch(self.image_ref, patch, *damage[:2])
                self.dev_map_frame = (menu, shown, self.image_ref, native, entry)
                self.keep_photo_at(position)
                return
        else:
            self.dev_map_frame = None
        self.show_photo(frame, position)
        if native_menu is source:
            self.native_menu_frame = self.image_ref, source, size, None
        if getattr(game_menu, 'page', None) == 'saves':
            self.save_menu_frame = (game_menu, frame, self.image_ref, state, listing, browser)
        if menu is not None and menu.preview_enabled:
            self.dev_map_frame = (menu, frame, self.image_ref, native, entry)

    def spare_photos(self):
        """The photos kept, by size, while the window shows another, each with the label
        that keeps Tk's pixels prepared for the display and what it shows: a menu drawn at
        the game's resolution (as native_menu_frame), or None."""
        spares = getattr(self, 'kept_photos', None)
        if spares is None:
            spares = self.kept_photos = {}
        return spares

    def drop_spare_photos(self, keep=None):
        """Let go of the photos kept, but for the one of the size ``keep``."""
        spares = self.spare_photos()
        for size in [size for size in spares if size != keep]:
            spares.pop(size)[1].destroy()

    def keep_photo(self, photo, size, shown=None):
        """Keep the window's photo of ``size``, about to give way to another, with Tk's pixels
        prepared for it; ``shown`` is what it shows (see spare_photos). One of each size is
        kept, two sizes at most."""
        spares = self.spare_photos()
        previous = spares.pop(size, None)
        if previous is not None:
            previous[1].destroy()
        spares[size] = photo, photo_holder(self.canvas, photo), shown
        while len(spares) > 2:
            spares.pop(next(iter(spares)))[1].destroy()

    def place_photo(self, photo, size, position):
        """Show ``photo``, of ``size``, at ``position``; the photo it replaces is kept
        (keep_photo)."""
        items = self.canvas.find_all()
        old = (getattr(self, 'image_ref', None), getattr(self, 'image_ref_size', None)) if items else (None, None)
        if items:
            self.canvas.itemconfigure(items[0], image=photo)
            self.canvas.coords(items[0], *position)
        else:
            self.canvas.create_image(*position, image=photo, anchor='nw')
        self.image_ref, self.image_ref_size = photo, size
        if old[0] is not None and old[0] is not photo and old[1] is not None:
            leaving = getattr(self, 'leaving_menu_frame', None)
            self.keep_photo(*old, leaving if leaving is not None and leaving[0] is old[0] else None)

    def show_photo(self, frame, position, hidden=None):
        """Show all of ``frame`` as the window's photo at ``position``; but for ``hidden``, a
        box of it that a widget over the window hides (the Cutscene Viewer's shelf), which is
        not written, and in a new photo stays blank: Tk prepares only the pixels written for
        the display (about 5 ns each), and the photo is shown before they are.

        Tk prepares a photo's pixels for the display again for each new photo shown, about
        7 ms more than writing them into one it shows at 1920x1440, 12 at 3440x1440. The
        photo shown before is kept, prepared (keep_photo), and takes the next picture of its
        size: a wide page (saves, screenshots, the Cutscene Viewer) and F1 under it each keep
        theirs, and the running game in a window has two in turn."""
        spare = self.spare_photos().pop(frame.size, None)
        photo, holder = spare[:2] if spare is not None else (None, None)
        if hidden is None:
            if photo is None:
                photo = ImageTk.PhotoImage(frame)
            else:
                photo.paste(frame)
            self.place_photo(photo, frame.size, position)
        else:
            if photo is None:
                photo = ImageTk.PhotoImage('RGB', frame.size)
            self.place_photo(photo, frame.size, position)
            left, top, right, bottom = hidden
            width, height = frame.size
            for box in ((0, 0, width, top), (0, bottom, width, height), (0, top, left, bottom),
                        (right, top, width, bottom)):
                if box[0] < box[2] and box[1] < box[3]:
                    put_patch(photo, frame.crop(box), *box[:2])
        if holder is not None:
            holder.destroy()   # the window's own item keeps the pixels prepared now
        if getattr(self, 'game_menu', None) is None and getattr(self, 'dev_menu', None) is None:
            self.drop_spare_photos(keep=frame.size)   # the running game needs no other size

    def menu_photo_back(self, size, position):
        """Show again the kept photo of ``size`` of a menu drawn at the game's resolution, as
        it was when a wide page took its place: what it shows (native_menu_frame), for only
        what changed since to be written into it, or None when no such photo is kept.
        Writing all of it, in a new photo, took about 35 ms at 3440x1440."""
        spares = self.spare_photos()
        spare = spares.get(size)
        if spare is None or spare[2] is None or isinstance(spare[2], SavePageShown) or not self.canvas.find_all():
            return None
        photo, holder, shown = spares.pop(size)
        self.place_photo(photo, size, position)
        holder.destroy()
        return shown

    def save_page_source(self, width, height):
        """The picture the saves page is drawn over in a window of this size: (the game's
        picture's size, the page's size, its place, the picture). It is kept while the menu
        is open: the saves pages it opens, and F1's warm-up, draw over the same one."""
        from pop2.save_slots import SaveBrowser

        size, position = fit_viewport(width, height)
        fitted, origin = size, position
        if SaveBrowser.wide_layout(width, height)[0]:
            # The wide page fills the window; the game's picture stays centred behind it.
            size, position = fit_menu_viewport(width, height)
        kept = getattr(self, 'save_menu_source', None)
        if kept is None or kept[0] is not self.screenshot_viewport or kept[1] != size:
            kept = self.save_menu_source = (self.screenshot_viewport, size,
                                            self.menu_backdrop(fitted, origin, size, position))
        return fitted, size, position, kept[2]

    def save_page_grounds(self):
        """The saves pages' grounds over the picture under the menu (SaveBrowser.ground_cache),
        kept while the menu is open and shows that picture."""
        kept = getattr(self, 'save_grounds', None)
        if kept is None or kept[0] is not self.screenshot_viewport:
            kept = self.save_grounds = self.screenshot_viewport, {}
        return kept[1]

    def save_page_frame(self, browser, width, height):
        """The saves page that ``browser`` draws in place for a window of this size, as
        present_viewport shows it: (its size, its place, the picture it is drawn over, the
        page, the picture shown, what is remembered of it: its state, and what the pointer
        and the keys light up)."""
        fitted, size, position, source = self.save_page_source(width, height)
        # The page stays RGBA: Tk is given only the parts that changed, their alpha ignored.
        # Drawn in place: the page shown, drawn over again where the focus or the scroll moved.
        page = browser.draw(source, self.ui_font, visible=True, background_key=id(self.screenshot_viewport),
                            in_place=True)
        frame = self.draw_screenshot_notice(page, visible=True, uniform=size != fitted)
        state = (id(self.screenshot_viewport), id(self.ui_font), browser.mode, browser.selected,
                 id(browser.slots), id(browser.current), browser.error, browser.status,
                 browser.save_available, browser.editing, browser.confirmation,
                 getattr(self, 'screenshot_toast', None), browser.active_path)
        # The Rename highlight and its tip change only the name's part (NAME_AREA).
        listing = browser.focus, browser.scroll, browser.focus == 25, browser.hovered == 25
        return size, position, source, page, frame, state, listing

    def prepare_save_page(self, width, height):
        """The saves page that F1's Save game opens now (Load game, when the game cannot be
        saved), drawn in place over this pause's picture, with what present_viewport
        remembers of it: a SavePageShown without its photo, for prepare_page_photo. None
        while a capture's toast is shown over the pages."""
        if self.game_menu is None or getattr(self, 'screenshot_toast', None) is not None:
            return None
        browser = self.new_save_browser(not self.can_save_game())
        _, _, _, page, frame, state, listing = self.save_page_frame(browser, width, height)
        return SavePageShown(None, self.game_menu, browser, frame, state, listing) if frame is page else None

    def save_photo_back(self, menu, browser, frame, state, position):
        """Show the kept photo of the saves page ``frame``, as ``browser`` drew it in place
        for ``menu`` with the same ``state`` (SavePageShown): what present_viewport remembers
        of it (save_menu_frame), for only what changed since to be written into it; or None
        when no such photo is kept."""
        spares = self.spare_photos()
        spare = spares.get(frame.size)
        shown = spare[2] if spare is not None else None
        if (not isinstance(shown, SavePageShown) or shown.menu is not menu or shown.browser is not browser
                or shown.frame is not frame or shown.state != state or not self.canvas.find_all()):
            return None
        spares.pop(frame.size)
        self.place_photo(spare[0], frame.size, position)
        spare[1].destroy()
        return menu, frame, spare[0], state, shown.listing, browser

    def prepare_page_photo(self, picture, shown=None):
        """Keep a photo of ``picture``'s size, the pixels Tk prepares for the window
        already made, for the next page of that size (a wide page opened from F1: the
        saves, the screenshots, the Cutscene Viewer), which then only writes into it
        (show_photo): its first opening made a new photo, about 12 ms more at 3440x1440.

        ``shown``: ``picture`` is that saves page (SavePageShown, prepare_save_page), which
        is written into the photo and opens on it as it is. A photo of that size kept
        already takes it, unless it shows a menu shown again from it (menu_photo_back)."""
        spares = self.spare_photos()
        spare = spares.get(picture.size)
        if not self.canvas.find_all() or spare is not None and (
                shown is None or spare[2] is not None and not isinstance(spare[2], SavePageShown)):
            return
        if spare is None and shown is None:
            self.keep_photo(ImageTk.PhotoImage(picture), picture.size)
            return
        if spare is None:
            # Blank, shown to Tk by its holder first: Tk prepares its pixels once, as they are written.
            self.keep_photo(ImageTk.PhotoImage('RGB', picture.size), picture.size)
            spare = spares[picture.size]
        put_patch(spare[0], picture, 0, 0)
        spares[picture.size] = spare[0], spare[1], shown._replace(photo=spare[0])

    def patch_native_menu(self, previous, source, size, position):
        """Show again a menu drawn at the game's resolution (the game menu, its options
        and controls, the tools): only the pixels that changed go into the window's photo,
        enlarged as the whole page is. A new photo of the whole window for each option the
        pointer passed, which Tk then painted again in full, took about 30 ms at 3440x1440."""
        if (previous is None or previous[0] is not self.image_ref or previous[2] != size
                or previous[1].size != source.size or 'RGBA' != previous[1].mode or 'RGBA' != source.mode):
            return False
        # The shown page's packed pixels, kept once they were needed: compared as one number
        # each, the whole page takes a fifth of the time of finding its changed box.
        before = packed_pixels(previous[1]) if previous[3] is None else previous[3]
        pixels = packed_pixels(source)
        bands = changed_bands(before, pixels)
        if bands:
            columns, rows = nearest_axes(source.size, size)
            for left, top, right, bottom in bands:
                # The window's columns and rows that show the changed ones.
                left, right = (int(edge) for edge in numpy.searchsorted(columns, (left, right)))
                top, bottom = (int(edge) for edge in numpy.searchsorted(rows, (top, bottom)))
                # Gathered from the changed pixels alone, columns first: the rows are then
                # whole copies (a third of the time of gathering the rows of the page's width).
                shown_columns, shown_rows = columns[left:right], rows[top:bottom]
                part = pixels[shown_rows[0]:shown_rows[-1] + 1, shown_columns[0]:shown_columns[-1] + 1]
                part = part.take(shown_columns - shown_columns[0], 1).take(shown_rows - shown_rows[0], 0)
                put_patch(self.image_ref, part.view(numpy.uint8).reshape(*part.shape, 4), left, top)
        self.native_menu_frame = self.image_ref, source, size, pixels
        self.keep_photo_at(position)
        return True

    def keep_photo_at(self, position):
        """Place the window's photo, whose pixels were patched, at ``position``. Even the same
        coordinates make Tk paint all of it again (about 6 ms at 3440x1440), so it moves
        only when its place changed."""
        item = self.canvas.find_all()[0]
        if tuple(self.canvas.coords(item)) != tuple(map(float, position)):
            self.canvas.coords(item, *position)

    def menu_backdrop(self, fitted, origin, size, position):
        """The game's picture behind a menu page drawn at the window's resolution.

        A wide page (``size`` differs from the ``fitted`` 4:3 picture) covers
        the whole window; the picture then stays where the game shows it.
        """
        source = self.screenshot_viewport.crop(VISIBLE_VIEWPORT).resize(fitted, Image.Resampling.NEAREST)
        if size != fitted:
            picture, source = source, Image.new('RGBA', size, '#080808')
            source.paste(picture, (origin[0] - position[0], origin[1] - position[1]))
        return source

    def expose_viewport(self, _event=None):
        if self.bitmap_presenter is not None:
            self.bitmap_presenter.redraw()

    def close_bitmap_presenter(self, event):
        if event.widget is self.root and self.bitmap_presenter is not None:
            self.bitmap_presenter.close()
            self.bitmap_presenter = None

    def run(self):
        self.root.mainloop()
