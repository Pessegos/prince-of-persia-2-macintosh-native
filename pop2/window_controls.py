"""Tk window controls and modal input for the scene host."""

import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from pop2.game_menu import GameMenu
from pop2.game_ui import DevelopmentMenu, VISIBLE_SIZE, VISIBLE_VIEWPORT, fit_viewport, viewport_point
from pop2.screenshots import ScreenshotSettings, save_screenshot


def is_resume_key(event, held_keys=()):
    command_keys = {"Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
                    "Super_L", "Super_R", "Win_L", "Win_R"}
    if event.state & (0x4 | 0x8 | 0x40 | 0x20000) or command_keys.intersection(held_keys):
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
        self.screenshot_dialog_active = False
        audio = getattr(self, "audio", None)
        self.sound_enabled = audio.sound_enabled if audio is not None else True
        self.music_enabled = audio.music_enabled if audio is not None else True
        self.root = tk.Tk()
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
        self.root.bind("<Destroy>", self.close_bitmap_presenter, add="+")
        self.root.bind("<KeyPress-Escape>", self.escape_key)
        self.root.bind("<KeyRelease-Escape>", self.escape_release)
        self.root.bind("<Alt-Return>", self.toggle_fullscreen)
        self.root.bind("<F2>", self.open_dev_mode)

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
                self.apply_game_action(self.game_menu.key("Escape"))
            elif self.dev_menu is not None:
                self.apply_dev_action(self.dev_menu.key("Escape"))
            else:
                self.set_paused(not self.paused)
        return "break"

    def escape_release(self, _event=None):
        self.escape_held = False
        return "break"

    def set_paused(self, paused):
        if self.paused == paused:
            return
        now = time.perf_counter()
        self.paused = paused
        audio = getattr(self, "audio", None)
        if audio is not None:
            audio.pause(paused)
        if paused:
            self.pause_started_at = now
            if self.animation_after_id is not None:
                self.root.after_cancel(self.animation_after_id)
                self.animation_after_id = None
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
        self.game_menu = None
        from pop2.playback_navigation import playback_groups

        parts = self.development_parts()
        self.dev_menu = DevelopmentMenu(
            screens, screen_index, self.peaceful,
            sections=tuple(part.label for part in parts), section_groups=playback_groups(parts),
            section_index=self.current_playback_part(), debug_status=self.debug_status,
            level_available=self.level_navigation_available(),
            level_options=level_options, level_index=level_index if level_options else 0,
        )
        if not self.dev_menu.level_available:
            self.dev_menu.change_tab(1)
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
        elif action == "go" and self.level_navigation_available():
            try:
                if self.dev_menu.level_number != self.game.level.number:
                    self.load_level(self.dev_menu.level_number)
                self.jump_to_screen(self.dev_menu.screen)
            except ValueError as exc:
                self.dev_menu.error = str(exc)
                self.render()
                return
            self.close_dev_mode()
        elif action == "peaceful" and self.level_navigation_available():
            self.set_peaceful(self.dev_menu.peaceful)
        elif action in ("seek", "next_part"):
            parts = self.development_parts()
            if not parts:
                return
            index = (self.dev_menu.next_section_index if action == "next_part"
                     else self.dev_menu.section_index)
            self.seek_playback_part(parts[index])
            self.close_dev_mode()
        elif action == "debug_status":
            self.debug_status = self.dev_menu.debug_status
            self.update_status_visibility()
            self.render()
        else:
            self.render()

    def choose_screenshot_folder(self):
        settings = self.screenshot_settings
        menu = self.game_menu
        held_keys = self.window_keys_down.copy()
        self.screenshot_dialog_active = True
        try:
            initial = settings.folder if settings.folder.is_dir() else settings.folder.parent
            folder = filedialog.askdirectory(parent=self.root, title="Screenshot folder",
                                             initialdir=str(initial), mustexist=True)
            if folder:
                from pathlib import Path

                selected = Path(folder).resolve()
                ScreenshotSettings(selected, settings.scale).save()
                settings.folder = selected
                menu.screenshot_folder = str(selected)
                menu.error = menu.screenshot_status = ""
        except (OSError, tk.TclError):
            menu.error = "Could not remember the screenshot folder."
        finally:
            self.screenshot_dialog_active = False
            self.clear_keys(None)
            self.pause_resume_keys.update(held_keys)
            self.render()

    def capture_screenshot(self):
        menu = self.game_menu if self.game_menu is not None and self.game_menu.page == "screenshots" else None
        try:
            viewport = getattr(self, "screenshot_viewport", None)
            if viewport is None:
                raise ValueError("No game frame is available yet")
            path = save_screenshot(viewport, self.screenshot_settings)
        except (OSError, ValueError) as exc:
            message = "Could not save PNG. Check the screenshot folder."
            if menu is not None:
                menu.error = message
                self.render()
            else:
                messagebox.showerror("Screenshot", f"{message}\n\n{exc}", parent=self.root)
            return None
        self.status.set(f"Screenshot saved: {path}")
        if menu is not None:
            menu.error = ""
            menu.screenshot_status = "PNG saved"
            self.render()
        return path

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
            self.game_menu.sound = self.sound_enabled
            self.game_menu.music = self.music_enabled
            self.game_menu.fullscreen = self.fullscreen
            self.game_menu.development = self.development_available()
            self.game_menu.copy_protection = getattr(self, "copy_protection_enabled", True)

    def open_game_menu(self, page="menu"):
        if self.game_menu is not None:
            if self.game_menu.page != "confirm":
                if page == "menu":
                    self.close_game_menu()
                else:
                    self.game_menu.show_page(page)
                    self.pause_resume_keys.update(self.window_keys_down)
                    self.render()
            return
        already_paused = self.paused
        self.game_was_paused = self.dev_was_paused if self.dev_menu is not None else self.paused
        self.dev_menu = None
        self.game_menu = GameMenu(page=page, return_to_menu=page == "menu",
                                  development=self.development_available(),
                                  screenshot_scale=self.screenshot_settings.scale,
                                  screenshot_folder=str(self.screenshot_settings.folder))
        self.set_paused(True)
        self.clear_keys(None)
        self.pause_resume_keys.update(self.window_keys_down)
        self.update_cursor_visibility()
        if already_paused:
            self.render()

    def close_game_menu(self, resume=False):
        if self.game_menu is None:
            return
        self.game_menu = None
        self.clear_keys(None)
        self.update_cursor_visibility()
        self.set_paused(False if resume else self.game_was_paused)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

    def apply_game_action(self, action):
        menu = self.game_menu
        if menu is not None and menu.page == "screenshots" and menu.screenshot_scale != self.screenshot_settings.scale:
            self.screenshot_settings.scale = menu.screenshot_scale
            try:
                self.screenshot_settings.save()
            except OSError:
                menu.error = "Could not remember screenshot settings."
        if action in ("close", "resume"):
            self.close_game_menu(resume=action == "resume")
        elif action in ("confirm_new", "about", "screenshots"):
            self.open_game_menu("confirm" if action == "confirm_new" else action)
        elif action == "screenshot_folder":
            self.choose_screenshot_folder()
        elif action == "screenshot":
            self.capture_screenshot()
        elif action in ("new_game", "restart"):
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
        elif action in ("sound", "music"):
            name = action + "_enabled"
            enabled = not getattr(self, name)
            setattr(self, name, enabled)
            if self.audio is not None:
                getattr(self.audio, "set_" + name)(enabled)
            self.render()
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
        elif action == "development":
            self.open_dev_mode()
        elif action in ("save", "open", "hall"):
            if self.game_menu is None:
                self.open_game_menu()
            self.game_menu.focus = next(i for i, item in enumerate(self.game_menu.items)
                                        if item.action == action)
            self.render()
        else:
            self.render()

    def dev_key_press(self, event):
        alt = event.state & (0x8 | 0x20000) or {"Alt_L", "Alt_R"}.intersection(self.window_keys_down)
        # Closing the host window must bypass intro, pause and menu filters.
        if event.keysym == "F4" and alt:
            self.root.destroy()
            return "break"
        repeated = event.keysym in self.window_keys_down or (
            len(event.keysym) == 1 and event.keysym.swapcase() in self.window_keys_down)
        self.window_keys_down.add(event.keysym)
        if event.keysym == "F8":
            if not repeated and not alt and not event.state & (0x4 | 0x40):
                self.capture_screenshot()
            return "break"
        if event.keysym == "F5" or event.keysym == "F2" and not self.development_available():
            return "break"
        if event.keysym == "F2":
            if not repeated:
                self.open_dev_mode(event)
            return "break"
        if event.keysym in self.pause_resume_keys:
            return "break"
        fullscreen_key = event.keysym == "Return" and event.state & (0x8 | 0x20000)
        if fullscreen_key:
            if repeated:
                return "break"
            self.pause_resume_keys.add(event.keysym)
            return None
        if event.keysym == "F1":
            if not repeated:
                self.open_game_menu()
            return "break"
        command = {"n": "confirm_new", "r": "restart", "t": "sound", "m": "music",
                   "s": "save", "o": "open", "h": "hall", "v": "about"}.get(
                       event.keysym.lower()) if alt and not event.state & (0x4 | 0x40) else None
        if command is not None:
            if not repeated and (self.game_menu is None or self.game_menu.page != "confirm"):
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
            self.apply_game_action(self.game_menu.key(event.keysym, backwards=bool(event.state & 1)))
            if self.game_menu is None or self.game_menu.page != page:
                self.pause_resume_keys.update(self.window_keys_down)
            return "break"
        if self.dev_menu is None:
            challenge = getattr(self, "copy_challenge", None)
            if challenge is not None:
                return "break"
            if self.paused and event.keysym not in ("Escape", "F2") and not fullscreen_key:
                if is_resume_key(event, self.window_keys_down):
                    self.set_paused(False)
                    self.pause_resume_keys.update(self.window_keys_down)
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
                    and event.keysym not in ("F2", "Alt_L", "Alt_R")
                    and not fullscreen_key):
                self.restart_after_death()
                return "break"
            return None
        if event.keysym == "Escape":
            return self.escape_key(event)
        if repeated and event.keysym in ("Return", "KP_Enter", "space"):
            return "break"
        self.apply_dev_action(
            self.dev_menu.key(event.keysym, backwards=bool(event.state & 1))
        )
        if self.dev_menu is None:
            self.pause_resume_keys.add(event.keysym)
        return "break"

    def dev_key_release(self, event):
        self.window_keys_down.discard(event.keysym)
        released = {event.keysym}
        if len(event.keysym) == 1:
            released.add(event.keysym.swapcase())
            self.window_keys_down.discard(event.keysym.swapcase())
        if event.keysym == "F2":
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
                self.apply_dev_action(self.dev_menu.click(*point))
        return "break"

    def dev_release(self, event):
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
            if point is not None and menu.hover(*point):
                self.render()

    def dev_scroll(self, event):
        if self.dev_menu is None or not self.dev_menu.dropdown:
            return None
        point = self.dev_pointer(event)
        if point is not None and self.dev_menu.hit(*point) is not None:
            delta = getattr(event, "delta", 0)
            steps = (-max(1, abs(delta) // 120) if delta > 0 else
                     max(1, abs(delta) // 120) if delta < 0 else
                     -1 if getattr(event, "num", None) == 4 else 1)
            self.dev_menu.scroll(steps)
            self.render()
        return "break"

    def set_peaceful(self, peaceful):
        self.peaceful = peaceful
        if self.dev_menu is not None:
            self.dev_menu.peaceful = peaceful
        self.clear_keys(None)
        if self.combat is not None:
            self.combat.last_guard_at = time.perf_counter()
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
                and getattr(self, "intro", None) is not None
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
        frame = self.native_viewport.crop(VISIBLE_VIEWPORT).resize(size, Image.Resampling.NEAREST)
        self.image_ref = ImageTk.PhotoImage(frame)
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
