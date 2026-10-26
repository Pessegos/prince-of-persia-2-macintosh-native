"""Tk window controls and modal input for the scene host."""

import sys
import time
import tkinter as tk
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageTk

from pop2.app_window import create_root
from pop2.game_menu import GameMenu
from pop2.game_ui import DevelopmentMenu, VISIBLE_SIZE, VISIBLE_VIEWPORT, fit_viewport, viewport_point
from pop2.screenshots import ScreenshotSettings, save_screenshot


PAUSE_GAMEPLAY_KEYS = frozenset({
    "Left", "Right", "Up", "Down", "Shift_L", "Shift_R", "Control_L", "Control_R",
})
RESUME_COMMAND_KEYS = frozenset({
    'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Meta_L', 'Meta_R',
    'Super_L', 'Super_R', 'Win_L', 'Win_R',
})
EXTERNAL_CAPTURE_KEYS = frozenset({'F9', 'F10'})


def alt_pressed(event, held_keys=()):
    # Tk's Mod1 (0x8) is Num Lock on Windows, but Alt on X11.
    mask = (0x10 | 0x20000) if sys.platform == "win32" else (0x8 | 0x20000)
    return bool(event.state & mask or {"Alt_L", "Alt_R"}.intersection(held_keys))


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


class WindowControls:
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

        self.root.bind(
            "<KeyPress-Left>", lambda event: self.horizontal_key(event, -1, True)
        )
        self.root.bind(
            "<KeyRelease-Left>", lambda event: self.horizontal_key(event, -1, False)
        )
        self.root.bind(
            "<KeyPress-Right>", lambda event: self.horizontal_key(event, 1, True)
        )
        self.root.bind(
            "<KeyRelease-Right>", lambda event: self.horizontal_key(event, 1, False)
        )
        self.root.bind("<KeyPress-Up>", self.up_key)
        self.root.bind(
            "<KeyRelease-Up>", lambda _event: self.set_key_state("up", False)
        )
        self.root.bind(
            "<KeyPress-Down>", lambda _event: self.set_key_state("down", True)
        )
        self.root.bind(
            "<KeyRelease-Down>", lambda _event: self.set_key_state("down", False)
        )
        self.root.bind(
            "<KeyPress-Shift_L>", lambda _event: self.set_key_state("shift", True)
        )
        self.root.bind(
            "<KeyRelease-Shift_L>", lambda _event: self.set_key_state("shift", False)
        )
        self.root.bind(
            "<KeyPress-Shift_R>", lambda _event: self.set_key_state("shift", True)
        )
        self.root.bind(
            "<KeyRelease-Shift_R>", lambda _event: self.set_key_state("shift", False)
        )
        self.root.bind(
            "<KeyPress-Control_L>", lambda _event: self.set_key_state("ctrl", True)
        )
        self.root.bind(
            "<KeyRelease-Control_L>", lambda _event: self.set_key_state("ctrl", False)
        )
        self.root.bind(
            "<KeyPress-Control_R>", lambda _event: self.set_key_state("ctrl", True)
        )
        self.root.bind(
            "<KeyRelease-Control_R>", lambda _event: self.set_key_state("ctrl", False)
        )
        self.focus_pause_after_id = None
        self.root.bind("<FocusOut>", self.focus_out)
        self.root.bind("<Destroy>", self.cancel_focus_pause)
        self.root.bind("<Destroy>", self.cancel_audio_notice, add="+")
        self.root.bind("<Destroy>", self.destroy_screenshot_gallery, add="+")
        self.root.bind("<Destroy>", self.close_bitmap_presenter, add="+")
        self.root.bind("<KeyPress-Escape>", self.escape_key)
        self.root.bind("<KeyRelease-Escape>", self.escape_release)
        self.root.bind("<Alt-Return>", self.toggle_fullscreen)
        self.root.bind("<F2>", self.toggle_screenshot_menu)
        self.root.bind("<F3>", self.open_dev_mode)
        from pop2.window_aspect import constrain_window
        self.window_aspect = constrain_window(
            self.root, self.canvas, lambda: not getattr(self, 'fullscreen', False))

    def focus_out(self, event):
        self.clear_keys(event)
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
        if getattr(self, "copy_challenge", None) is not None:
            return
        try:
            focused = self.root.focus_get()
        except tk.TclError:
            return
        if focused is None or focused.winfo_toplevel() is not self.root:
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

    def set_paused(self, paused):
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
        self.render()

    def toggle_fullscreen(self, _event=None):
        if not self.fullscreen:
            self.windowed_geometry = self.root.geometry()
            self.windowed_state = self.root.state()
            self.status_label.pack_forget()
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
        return "break"

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
        self.dispose_screenshot_gallery()
        self.game_menu = None
        from pop2.playback_navigation import playback_groups

        self.ui_hover_target = None
        parts = self.development_parts()
        if not hasattr(self, 'development_gallery_pages'):
            self.development_gallery_pages = {}
        if (self.level_navigation_available() and self.combat is not None
                and not self.combat.player.alive):
            self.remember_development_room()
        self.dev_menu = DevelopmentMenu(
            screens, screen_index, self.peaceful,
            sections=tuple(part.label for part in parts), section_groups=playback_groups(parts),
            section_index=self.current_playback_part(), debug_status=self.debug_status,
            level_available=self.level_navigation_available(),
            level_options=level_options, level_index=level_index if level_options else 0,
            map_provider=self.development_map if level_options else None,
            return_screens=dict(getattr(self, 'development_return_screens', {})),
            playback_provider=self.development_playback_preview if parts else None,
            gallery_pages=self.development_gallery_pages,
            current_section=(self.current_playback_part() if self.attract_stage is not None
                             or self.game.level.number == 2 else None),
            current_level=self.game.level.number, current_screen=self.screen_label(self.room_id),
            god_mode=getattr(self, 'god_mode', False),
        )
        if self.dev_menu.map_available:
            self.dev_menu.focus = 4
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
        self.clear_keys(None)
        self.update_cursor_visibility()
        self.set_paused(self.dev_was_paused)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

    def apply_dev_action(self, action):
        if self.dev_menu is None:
            return
        if action == "resume":
            self.close_dev_mode()
        elif action in ('go', 'return_room') and self.level_navigation_available():
            destination = self.dev_menu.return_screen if action == 'return_room' else self.dev_menu.screen
            if destination is None:
                return
            try:
                if self.dev_menu.level_number != self.game.level.number:
                    self.load_level(self.dev_menu.level_number)
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
        elif action in ("seek", "next_part"):
            parts = self.development_parts()
            if not parts:
                return
            index = (self.dev_menu.next_section_index if action == "next_part"
                     else self.dev_menu.section_index)
            self.seek_playback_part(parts[index])
            self.dev_was_paused = False
            self.close_dev_mode()
        elif action == "debug_status":
            self.debug_status = self.dev_menu.debug_status
            self.update_status_visibility()
            self.render()
        else:
            self.update_cursor_visibility()
            self.render()

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
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None:
            gallery.close()
            try:
                self.canvas.configure(cursor='')
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
            if gallery.committed_folder is not None:
                self.screenshot_settings.folder = gallery.committed_folder
                menu.screenshot_folder = str(gallery.committed_folder)
                gallery.committed_folder = None
            if changed or moving:
                self.redraw_screenshot_gallery()
            if gallery.reads.pending or gallery.scrolling or gallery.animation_running or gallery.burn_seconds is not None:
                if gallery.scrolling or gallery.burn_seconds is not None:
                    fps = 120 if gallery.scrolling else 60
                    delay = max(1, round(1000 / fps - (time.perf_counter() - now) * 1000))
                elif gallery.reads.pending:
                    delay = 12
                else:
                    delay = max(1, round((1 - (gallery.icon_seconds * 12) % 1) * 1000 / 12))
                self.screenshot_gallery_after_id = self.root.after(delay, tick)
        self.screenshot_gallery_after_id = self.root.after(12, tick)

    def redraw_screenshot_gallery(self):
        if self.game_menu.screenshot_gallery.drag_target is None and self.canvas.cget('cursor'):
            self.canvas.configure(cursor='')
        self.native_viewport = self.draw_screenshot_notice(
            self.game_menu.draw(self.screenshot_viewport, self.ui_font))
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
        try:
            viewport = getattr(self, "native_viewport" if include_ui else "screenshot_viewport", None)
            if viewport is None:
                raise ValueError("No game frame is available yet")
            if include_ui and self.game_menu is not None and self.game_menu.page == 'saves':
                scale = self.screenshot_settings.scale
                source = self.screenshot_viewport.resize((512 * scale, 384 * scale), Image.Resampling.NEAREST)
                viewport = self.draw_screenshot_notice(self.game_menu.save_browser.draw(
                    source, self.ui_font, background_key=id(self.screenshot_viewport)))
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
            path = save_screenshot(viewport, self.screenshot_settings)
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
        self.screenshot_toast = filename if error else f"Saved screenshot as {filename}"
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
        label = "Sounds" if action == "sound" else "Ambient Music"
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
        self.canvas.configure(cursor="" if visible else "none")

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
            self.game_menu.fullscreen = self.fullscreen
            self.game_menu.copy_protection = getattr(self, "copy_protection_enabled", True)

    def open_game_menu(self, page="menu"):
        if self.game_menu is not None:
            if self.game_menu.page != "confirm":
                if page == "menu":
                    if self.game_menu.page in ("screenshots", "saves"):
                        self.dispose_screenshot_gallery()
                        self.game_menu.show_page("menu")
                        self.pause_resume_keys.update(self.window_keys_down)
                        self.render()
                    else:
                        self.close_game_menu()
                else:
                    self.dispose_screenshot_gallery()
                    self.game_menu.show_page(page)
                    if page == "screenshots":
                        self.game_menu.return_to_menu = False
                        self.install_screenshot_gallery()
                    self.pause_resume_keys.update(self.window_keys_down)
                    self.render()
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
        self.set_paused(True)
        self.clear_keys(None)
        self.pause_resume_keys.update(self.window_keys_down)
        self.update_cursor_visibility()
        if already_paused:
            self.render()

    def toggle_screenshot_menu(self, _event=None):
        if self.game_menu is not None and self.game_menu.page == "confirm":
            return "break"
        if self.game_menu is not None and self.game_menu.page == "screenshots":
            self.close_game_menu()
        else:
            self.open_game_menu("screenshots")
        return "break"

    def close_game_menu(self, resume=False):
        if self.game_menu is None:
            return
        self.dispose_screenshot_gallery()
        self.game_menu = None
        self.save_scroll_dragging = False
        self.ui_hover_target = None
        self.clear_keys(None)
        self.update_cursor_visibility()
        self.set_paused(False if resume else self.game_was_paused)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

    def apply_game_action(self, action, *, preserve_controls=False):
        menu = self.game_menu
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
        elif action in ("confirm_new", "about"):
            self.open_game_menu("confirm" if action == "confirm_new" else action)
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
        elif action == "fullscreen":
            self.toggle_fullscreen()
            self.render()
        elif action == "copy_protection":
            self.copy_protection_enabled = not getattr(self, "copy_protection_enabled", True)
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
                self.render()
        elif action in ('slot_save', 'slot_load', 'slot_delete', 'slot_create', 'slot_rename'):
            self.apply_save_action(action)
        elif action == "hall":
            if self.game_menu is None:
                self.open_game_menu()
            self.game_menu.focus = next(i for i, item in enumerate(self.game_menu.items)
                                        if item.action == action)
            self.render()
        else:
            self.schedule_save_scroll()
            if self.game_menu is not None and self.game_menu.page == 'saves':
                self.redraw_save_menu()
            else:
                self.render()

    def redraw_save_menu(self):
        self.refresh_game_menu()
        self.native_viewport = self.draw_screenshot_notice(
            self.game_menu.draw(self.screenshot_viewport, self.ui_font))
        self.present_viewport()

    def open_save_browser(self, load=False):
        from pop2.save_slots import SAVE_DIRECTORY, SaveBrowser, SaveSlot, list_slots

        direct = self.game_menu is None
        if self.game_menu is None:
            self.open_game_menu()
        parent = self.game_menu.return_to_menu if self.game_menu.page == 'saves' else self.game_menu.page == 'menu'
        self.dispose_screenshot_gallery()
        self.game_menu.show_page('saves')
        self.game_menu.return_to_menu = parent and not direct
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
        self.game_menu.save_browser = SaveBrowser(slots, 'load' if load else 'save', selected,
                                                  focus=100 + selected if load or active_index is not None else 29,
                                                  save_available=self.can_save_game(), current=current,
                                                  active_path=active_path,
                                                  preview_provider=self.save_slot_preview)
        self.game_menu.save_browser.ensure_visible(immediate=True)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

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
        if audio is not None and getattr(self, 'sound_enabled', True):
            audio.play_ui(kind)

    def menu_sound_target(self, menu, point=None):
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
        if isinstance(menu, DevelopmentMenu) and menu.preview_enabled and index == 4:
            if menu.map_enabled:
                room = menu.screen if point is None else menu.map_hit(*point)
                return (*context, 'room', menu.level_number, room) if room is not None else None
            part = menu.section_index if point is None else menu.gallery_hit(*point)
            return (*context, 'part', part) if part is not None else None
        return (*context, 'control', index)

    def menu_key_action(self, menu, event):
        fields = ('page', 'focus', 'dropdown', 'option_index', 'level_index', 'screen_index',
                  'section_index', 'gallery_page', 'screenshot_scale')
        def state():
            browser = getattr(menu, 'save_browser', None)
            return tuple(getattr(menu, name, None) for name in fields) + (
                (browser.selected, browser.focus, browser.mode, browser.confirmation) if browser else ())

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

    def dev_key_press(self, event):
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
        command = {"n": "confirm_new", "r": "restart", "t": "sound", "m": "music",
                   "s": "save", "o": "open", "l": "open", "h": "hall", "v": "about"}.get(
                       event.keysym.lower()) if alt and not event.state & (0x4 | 0x40) else None
        if command is not None:
            confirming_save = (self.game_menu is not None and self.game_menu.page == 'saves'
                               and self.game_menu.save_browser.confirmation is not None)
            if not repeated and not confirming_save and (self.game_menu is None or self.game_menu.page != "confirm"):
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
            if (event.keysym.lower() == 'k' and getattr(self, 'god_mode', False)
                    and not self.paused and self.gameplay_controls_available()
                    and self.combat is not None and self.combat.player.alive
                    and not alt and not event.state & (0x4 | 0x40)):
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

    def dev_key_release(self, event):
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

    def dev_pointer(self, event):
        return viewport_point(
            event.x, event.y, self.canvas.winfo_width(), self.canvas.winfo_height()
        )

    def dev_click(self, event):
        if not self.modal_open():
            return "break" if self.paused else None
        if getattr(event, "num", 1) != 1:
            return "break"
        point = self.dev_pointer(event)
        if point is not None:
            if self.game_menu is not None:
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

    def dev_release(self, event):
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None and gallery.drag_target is not None and getattr(event, 'num', 1) == 1:
            point = self.dev_pointer(event)
            self.apply_game_action(gallery.release_drag(*(point if point is not None else (-1, -1))))
            self.canvas.configure(cursor='')
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
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None and gallery.drag_target is not None:
            point = self.dev_pointer(event)
            if gallery.move_drag(*(point if point is not None else (-1, -1))):
                self.canvas.configure(cursor='hand2' if gallery.hovered == 13 else 'fleur')
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
        if challenge is not None:
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
                else:
                    self.render()
            if menu is self.dev_menu:
                hovered = menu.hovered_screen if menu.map_enabled else menu.hovered_part
                cursor = 'hand2' if menu.preview_enabled and hovered is not None and not menu.dropdown else ''
                if self.canvas.cget('cursor') != cursor:
                    self.canvas.configure(cursor=cursor)
            elif menu.page == 'saves':
                cursor = 'hand2' if menu.save_browser.hovered == 25 else ''
                if self.canvas.cget('cursor') != cursor:
                    self.canvas.configure(cursor=cursor)

    def redraw_dev_menu(self):
        # F3 pauses the world; pointer changes only need the frozen clean viewport.
        self.native_viewport = self.draw_screenshot_notice(
            self.dev_menu.draw(self.screenshot_viewport, self.ui_font))
        self.present_viewport()

    def dev_pointer_leave(self, _event):
        self.ui_hover_target = None
        if self.game_menu is not None and self.game_menu.page == 'saves':
            if self.game_menu.hover(-1, -1):
                self.redraw_save_menu()
            self.canvas.configure(cursor='')
        gallery = getattr(getattr(self, 'game_menu', None), 'screenshot_gallery', None)
        if gallery is not None and gallery.drag_target is not None:
            gallery.cancel_drag()
            self.canvas.configure(cursor='')
            self.redraw_screenshot_gallery()
        menu = self.dev_menu
        if menu is not None and menu.preview_enabled:
            if menu.hover(-1, -1):
                self.redraw_dev_menu()
            self.canvas.configure(cursor='')

    def dev_scroll(self, event):
        menu = getattr(self, 'game_menu', None)
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
        if self.dev_menu.gallery_enabled and not self.dev_menu.dropdown:
            point = self.dev_pointer(event)
            if (point is not None and self.dev_menu.hit(*point) == 4
                    and self.dev_menu.gallery_count > 1):
                delta = getattr(event, 'delta', 0)
                self.dev_menu.turn_gallery_page(-1 if delta > 0 or getattr(event, 'num', None) == 4 else 1)
                self.play_menu_sound('click')
                self.redraw_dev_menu()
            return 'break'
        if not self.dev_menu.dropdown:
            return None
        point = self.dev_pointer(event)
        if point is not None and self.dev_menu.hit(*point) is not None:
            delta = getattr(event, "delta", 0)
            steps = (-max(1, abs(delta) // 120) if delta > 0 else
                     max(1, abs(delta) // 120) if delta < 0 else
                     -1 if getattr(event, "num", None) == 4 else 1)
            previous = self.dev_menu.option_index
            self.dev_menu.scroll(steps)
            if self.dev_menu.option_index != previous:
                self.play_menu_sound('hover')
            self.render()
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

    def present_viewport(self):
        if self.native_viewport is None:
            return
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1 or height <= 1:
            width, height = VISIBLE_SIZE[0] * 2, VISIBLE_SIZE[1] * 2
        size, position = fit_viewport(width, height)
        if (sys.platform == "win32" and getattr(self, "fullscreen", False)
                and not getattr(self, "paused", False)
                and getattr(self, "game_menu", None) is None
                and getattr(self, "dev_menu", None) is None
                and getattr(self, "copy_challenge", None) is None):
            from pop2.bitmap_presenter import CanvasBitmap

            if getattr(self, "bitmap_presenter", None) is None:
                self.bitmap_presenter = CanvasBitmap(self.canvas)
                for item in self.canvas.find_all():
                    self.canvas.itemconfigure(item, image="")
                self.image_ref = None
            frame = self.native_viewport.crop(VISIBLE_VIEWPORT).convert("RGB").resize(size, Image.Resampling.NEAREST)
            self.bitmap_presenter.present(frame, position)
            return
        if getattr(self, "bitmap_presenter", None) is not None:
            self.bitmap_presenter.close()
            self.bitmap_presenter = None
        game_menu = getattr(self, 'game_menu', None)
        gallery = getattr(game_menu, 'screenshot_gallery', None) if getattr(game_menu, 'page', None) == 'screenshots' else None
        if gallery is not None:
            cached = getattr(self, 'screenshot_gallery_source', None)
            if cached is None or cached[0] is not self.screenshot_viewport or cached[1] != size:
                source = self.screenshot_viewport.crop(VISIBLE_VIEWPORT).resize(size, Image.Resampling.NEAREST)
                self.screenshot_gallery_source = self.screenshot_viewport, size, source
            else:
                source = cached[2]
            frame = self.draw_screenshot_notice(gallery.draw(source, self.ui_font, visible=True), visible=True).convert('RGB')
            previous = getattr(self, 'screenshot_gallery_frame', None)
            state = id(self.screenshot_viewport), id(self.ui_font), gallery.surface_state, gallery.overlay_active
            if previous is not None and previous[0] is gallery and previous[1].size == size and previous[2] is self.image_ref:
                if previous[3] == state and not (gallery.choosing or gallery.deleting or gallery.overlay_active):
                    # Only the thumbnail strip and animated delete button can change.
                    damages = []
                    for left, top, right, bottom in (gallery.LIST, gallery.DELETE):
                        region = (round((left - 1) * size[0] / 510), round(top * size[1] / 384),
                                  round((right - 1) * size[0] / 510) + 1, round(bottom * size[1] / 384) + 1)
                        local = ImageChops.difference(previous[1].crop(region), frame.crop(region)).getbbox()
                        if local:
                            damages.append((local[0] + region[0], local[1] + region[1],
                                            local[2] + region[0], local[3] + region[1]))
                else:
                    damage = ImageChops.difference(previous[1], frame).getbbox()
                    damages = [damage] if damage else []
                for damage in damages:
                    patch = ImageTk.PhotoImage(frame.crop(damage))
                    self.image_ref.tk.call(str(self.image_ref), 'copy', str(patch), '-to', damage[0], damage[1])
                self.canvas.coords(self.canvas.find_all()[0], *position)
            else:
                self.image_ref = ImageTk.PhotoImage(frame)
                if self.canvas.find_all():
                    self.canvas.itemconfigure(self.canvas.find_all()[0], image=self.image_ref)
                    self.canvas.coords(self.canvas.find_all()[0], *position)
                else:
                    self.canvas.create_image(*position, image=self.image_ref, anchor='nw')
            self.screenshot_gallery_frame = gallery, frame, self.image_ref, state
            return
        self.screenshot_gallery_frame = self.screenshot_gallery_source = None
        if getattr(game_menu, 'page', None) == 'saves':
            source_cache = getattr(self, 'save_menu_source', None)
            if source_cache is None or source_cache[0] is not self.screenshot_viewport or source_cache[1] != size:
                source = self.screenshot_viewport.crop(VISIBLE_VIEWPORT).resize(size, Image.Resampling.NEAREST)
                self.save_menu_source = (self.screenshot_viewport, size, source)
            else:
                source = source_cache[2]
            browser = game_menu.save_browser
            frame = self.draw_screenshot_notice(
                browser.draw(source, self.ui_font, visible=True,
                                            background_key=id(self.screenshot_viewport)), visible=True).convert('RGB')
            state = (id(self.screenshot_viewport), id(self.ui_font), browser.mode, browser.selected,
                     id(browser.slots), id(browser.current), browser.error, browser.status,
                     browser.save_available, browser.editing, browser.confirmation,
                     None if browser.editing or browser.confirmation else browser.focus,
                     getattr(self, 'screenshot_toast', None), browser.active_path, browser.hovered == 25)
            previous = getattr(self, 'save_menu_frame', None)
            if (previous is not None and previous[0] is game_menu and previous[1].size == frame.size
                    and previous[2] is self.image_ref):
                rect = (0, 0, *frame.size)
                if previous[3] == state:
                    native = (80, 121, 433, 271) if browser.editing or browser.confirmation else browser.LIST
                    rect = (round((native[0] - 1) * size[0] / 510), round(native[1] * size[1] / 384),
                            round((native[2] - 1) * size[0] / 510), round(native[3] * size[1] / 384))
                damage = ImageChops.difference(previous[1].crop(rect), frame.crop(rect)).getbbox()
                if damage is not None:
                    damage = (damage[0] + rect[0], damage[1] + rect[1],
                              damage[2] + rect[0], damage[3] + rect[1])
                    patch = ImageTk.PhotoImage(frame.crop(damage))
                    self.image_ref.tk.call(str(self.image_ref), 'copy', str(patch), '-to', damage[0], damage[1])
                self.save_menu_frame = (game_menu, frame, self.image_ref, state)
                self.canvas.coords(self.canvas.find_all()[0], *position)
                return
        else:
            self.save_menu_frame = None
            self.save_menu_source = None
            frame = self.native_viewport.crop(VISIBLE_VIEWPORT).resize(size, Image.Resampling.NEAREST)
        menu = getattr(self, 'dev_menu', None)
        if menu is not None and menu.preview_enabled:
            frame = menu.present_map(frame, self.ui_font).convert('RGB')
            previous = getattr(self, 'dev_map_frame', None)
            if (previous is not None and previous[0] is menu and previous[1].size == frame.size
                    and previous[2] is self.image_ref):
                # Upload only changed rooms/labels instead of a full 1440p Tk photo.
                damage = ImageChops.difference(previous[1], frame).getbbox()
                if damage is not None:
                    patch = ImageTk.PhotoImage(frame.crop(damage))
                    self.image_ref.tk.call(str(self.image_ref), 'copy', str(patch),
                                           '-to', damage[0], damage[1])
                self.dev_map_frame = (menu, frame, self.image_ref)
                self.canvas.coords(self.canvas.find_all()[0], *position)
                return
        else:
            self.dev_map_frame = None
        self.image_ref = ImageTk.PhotoImage(frame)
        if getattr(game_menu, 'page', None) == 'saves':
            self.save_menu_frame = (game_menu, frame, self.image_ref, state)
        if menu is not None and menu.preview_enabled:
            self.dev_map_frame = (menu, frame, self.image_ref)
        if self.canvas.find_all():
            self.canvas.itemconfigure(self.canvas.find_all()[0], image=self.image_ref)
            self.canvas.coords(self.canvas.find_all()[0], *position)
        else:
            self.canvas.create_image(*position, image=self.image_ref, anchor="nw")

    def expose_viewport(self, _event=None):
        if self.bitmap_presenter is not None:
            self.bitmap_presenter.redraw()

    def close_bitmap_presenter(self, event):
        if event.widget is self.root and self.bitmap_presenter is not None:
            self.bitmap_presenter.close()
            self.bitmap_presenter = None

    def run(self):
        self.root.mainloop()
