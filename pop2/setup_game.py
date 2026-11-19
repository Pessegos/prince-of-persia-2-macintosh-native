"""First-run import of user-supplied Macintosh game files.

The window says why it opened (a first import, or files this version
prepares differently), offers the image of the last completed import,
lists the import's stages with a progress bar and an estimate of the time
left, and explains in plain words why a chosen file cannot be used.
"""

import math
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Thread
from time import monotonic
import tkinter as tk
from tkinter import filedialog, ttk
import webbrowser

from pop2.app_window import create_root
from pop2.asset_import import STAGES, AssetImport, ImportCancelled, ImportFailed, overall
from pop2.import_advice import ISSUES_URL, describe_missing, os_problem, preflight, problem
from pop2.preferences import load_preferences, remember

IMAGE_TYPES = ("Game images", "*.iso *.hfs *.hfv *.dsk *.img *.dmg")
SUPPORTED = "Supported images: .iso, .hfs, .hfv, .dsk, .img and uncompressed .dmg"
# Problems whose technical detail helps a report (the others say it all).
DETAILED = {'unsupported', 'damaged', 'failed'}
_PREFIXES = ('Asset extraction failed: ', 'This is not a supported Macintosh PoP2 disk image: ')
WRAP = 432
MUTED, RUNNING, DONE, ERROR = '#5f5f5f', '#005fb8', '#107c10', '#a4262c'
MARKS = {'pending': '○', 'running': '●', 'done': '✓'}


def import_game(image_path, project, progress=lambda _text: None, task=None,
                steps=lambda _stage, _done, _total: None):
    return (task or AssetImport(project)).run(image_path, progress, steps)


def import_files(image_path, project, task, messages):
    """Run `task` for the window's import thread, reporting to `messages`."""
    try:
        import_game(image_path, project, lambda text: messages.put(("progress", text)), task=task,
                    steps=lambda stage, done, total: messages.put(('step', (stage, done, total))))
    except ImportCancelled:
        messages.put(('cancelled', ''))
    except ImportFailed as error:
        messages.put(('error', (error.kind, str(error))))
    except OSError as error:
        messages.put(('error', (os_problem(error, image_path), str(error))))
    except Exception as error:
        messages.put(("error", ('failed', str(error))))
    else:
        messages.put(("complete", ""))


def time_left(seconds):
    if seconds < 10:
        return 'a few seconds left'
    if seconds < 90:
        return f'about {5 * math.ceil(seconds / 5)} seconds left'
    return f'about {round(seconds / 60)} minutes left'


def _same_file(first, second):
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


def open_file(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class GameSetup:
    def __init__(self, project, missing=()):
        self.project = Path(project)
        self.log = self.project / 'rendered' / 'setup.log'
        missing = list(missing)
        assets = self.project / 'assets'
        # Files from an earlier import: this version needs some of them again.
        self.refresh = bool(missing) and assets.is_dir() and any(
            path.is_file() for path in assets.iterdir())
        self.summary = describe_missing(missing) if self.refresh else ''
        self.completed = False
        self.importing = False
        self.closing = False
        self.task = None
        self.started_at = None
        self.image = None
        self.offered = None
        self.stages = {}
        self.drawn = {}
        self.shown_progress = 0.0
        self.messages = Queue()
        remembered = load_preferences().game_image
        self.remembered = Path(remembered) if remembered and Path(remembered).is_file() else None

        self.root = create_root()
        self.root.title("Prince of Persia 2 - Game Files")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(self.root)
        style.configure('Title.TLabel', font=('Segoe UI', 12, 'bold'))
        style.configure('Muted.TLabel', foreground=MUTED)
        style.configure('Name.TLabel', font=('Segoe UI', 9, 'bold'))
        style.configure('Problem.TLabel', font=('Segoe UI', 10, 'bold'), foreground=ERROR)
        for state, colour in (('pending', MUTED), ('running', RUNNING), ('done', DONE)):
            style.configure(f'{state.title()}.TLabel', foreground=colour)

        panel = ttk.Frame(self.root, padding=24)
        panel.pack(fill="both", expand=True)
        # Keeps the window one width whatever it shows.
        ttk.Frame(panel, width=WRAP, height=1).pack()
        self.heading = tk.StringVar()
        ttk.Label(panel, textvariable=self.heading, style='Title.TLabel', wraplength=WRAP).pack(anchor="w")
        self.intro = tk.StringVar()
        self.intro_label = ttk.Label(panel, textvariable=self.intro, wraplength=WRAP, justify='left')

        self.offer_frame = ttk.Frame(panel)
        self.offer_caption = tk.StringVar()
        ttk.Label(self.offer_frame, textvariable=self.offer_caption).pack(anchor='w')
        self.offer_name = tk.StringVar()
        ttk.Label(self.offer_frame, textvariable=self.offer_name, style='Name.TLabel',
                  wraplength=WRAP).pack(anchor='w', pady=(2, 0))
        self.offer_folder = tk.StringVar()
        ttk.Label(self.offer_frame, textvariable=self.offer_folder, style='Muted.TLabel',
                  wraplength=WRAP).pack(anchor='w')
        self.types_label = ttk.Label(panel, text=SUPPORTED, style='Muted.TLabel', wraplength=WRAP)

        self.progress_frame = ttk.Frame(panel)
        self.progress_frame.columnconfigure(1, weight=1)
        self.rows = {}
        for row, (key, label, _weight) in enumerate(STAGES):
            mark = ttk.Label(self.progress_frame, width=2)
            mark.grid(row=row, column=0, sticky='w')
            name = ttk.Label(self.progress_frame, text=label)
            name.grid(row=row, column=1, sticky='w', pady=1)
            detail = ttk.Label(self.progress_frame, style='Muted.TLabel')
            detail.grid(row=row, column=2, sticky='e')
            self.rows[key] = (mark, name, detail)
        self.progressbar = ttk.Progressbar(self.progress_frame, mode='determinate', maximum=100)
        self.progressbar.grid(row=len(STAGES), column=0, columnspan=3, sticky='ew', pady=(12, 6))
        self.status = tk.StringVar()
        ttk.Label(self.progress_frame, textvariable=self.status, style='Muted.TLabel',
                  wraplength=WRAP).grid(row=len(STAGES) + 1, column=0, columnspan=3, sticky='w')
        self.elapsed = tk.StringVar()
        ttk.Label(self.progress_frame, textvariable=self.elapsed, style='Muted.TLabel').grid(
            row=len(STAGES) + 2, column=0, columnspan=3, sticky='w')

        self.problem_frame = ttk.Frame(panel)
        self.problem_title = tk.StringVar()
        ttk.Label(self.problem_frame, textvariable=self.problem_title, style='Problem.TLabel',
                  wraplength=WRAP).pack(anchor='w')
        self.problem_advice = tk.StringVar()
        ttk.Label(self.problem_frame, textvariable=self.problem_advice, wraplength=WRAP,
                  justify='left').pack(anchor='w', pady=(4, 0))
        self.problem_detail = tk.StringVar()
        self.detail_label = ttk.Label(self.problem_frame, textvariable=self.problem_detail,
                                      style='Muted.TLabel', wraplength=WRAP, justify='left')
        self.help_buttons = ttk.Frame(self.problem_frame)
        self.log_button = ttk.Button(self.help_buttons, text='Open the import log',
                                     command=lambda: self.open_log())
        self.report_button = ttk.Button(self.help_buttons, text='Report a problem',
                                        command=lambda: webbrowser.open(ISSUES_URL))

        buttons = ttk.Frame(panel)
        buttons.pack(side='bottom', fill="x", pady=(20, 0))
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=lambda: self.close())
        self.cancel_button.pack(side="right")
        self.same_button = ttk.Button(buttons, command=lambda: self.use_offered())
        self.import_button = ttk.Button(buttons, command=lambda: self.choose())
        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.bind("<Return>", self.activate)

        self.sections = (self.intro_label, self.offer_frame, self.types_label, self.progress_frame,
                         self.problem_frame)
        self.offer(self.remembered, 'Last time you used:', 'Use this image')
        self.show_ready()

        self.root.update_idletasks()
        width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 3)
        self.root.geometry(f"+{x}+{y}")

    # The window's states.

    def ready_heading(self):
        return ('Your game files need refreshing' if self.refresh
                else 'Choose your original game image')

    def show(self, *sections):
        for section in self.sections:
            section.pack_forget()
        for section in sections:
            section.pack(anchor='w', fill='x', pady=(14 if section is not self.intro_label else 10, 0))

    def show_ready(self):
        self.heading.set(self.ready_heading())
        if self.refresh:
            parts = f' for {self.summary}' if self.summary else ''
            self.intro.set(f'This version of the port needs newly prepared files{parts}. '
                           'Choose your game image again to prepare them. Your saved games and '
                           'settings are kept.')
        else:
            self.intro.set('Select a disk image of Prince of Persia 2 for Macintosh. Its pictures, '
                           'music and scenes are prepared once; this usually takes under a minute.')
        self.show(self.intro_label, *((self.offer_frame,) if self.offered else ()), self.types_label)
        self.enable_choices()

    def offer(self, image, caption='', label=''):
        """Offer `image` (or nothing) to import again with the same_button."""
        self.offered = Path(image) if image is not None else None
        self.same_button.pack_forget()
        self.import_button.pack_forget()
        if self.offered is None:
            self.import_button.configure(text='Choose game image...')
            self.import_button.pack(side='left')
            return
        self.offer_caption.set(caption)
        self.offer_name.set(self.offered.name)
        self.offer_folder.set(str(self.offered.parent))
        self.same_button.configure(text=label)
        self.import_button.configure(text='Choose another image...')
        self.same_button.pack(side='left')
        self.import_button.pack(side='left', padx=(8, 0))

    def default_button(self):
        return self.same_button if self.offered is not None else self.import_button

    def enable_choices(self):
        for button in (self.same_button, self.import_button, self.cancel_button):
            button.state(['!disabled'])
        self.default_button().focus_set()

    def show_importing(self):
        self.heading.set('Preparing your game files')
        self.intro.set(f'From {Path(self.image).name}. Cancel stops the import without changing '
                       'anything.')
        self.show(self.intro_label, self.progress_frame)
        self.same_button.state(['disabled'])
        self.import_button.state(['disabled'])
        # Not on a disabled button, nor on Cancel where Enter would stop the import.
        self.root.focus_set()
        self.update_progress()

    def show_problem(self, kind, image=None, detail='', ran=False):
        advice = problem(kind)
        # Also kept for diagnostics (packaged_app.smoke_import reports it).
        self.status.set(detail or advice.title)
        self.heading.set(self.ready_heading())
        self.problem_title.set(advice.title)
        self.problem_advice.set(advice.advice)
        text = detail.splitlines()[0] if detail else ''
        for prefix in _PREFIXES:
            text = text.removeprefix(prefix)
        self.problem_detail.set(text if kind in DETAILED else '')
        self.detail_label.pack_forget()
        self.help_buttons.pack_forget()
        self.log_button.pack_forget()
        self.report_button.pack_forget()
        if self.problem_detail.get():
            self.detail_label.pack(anchor='w', pady=(6, 0))
        if ran and self.log.is_file():
            self.log_button.pack(side='left', padx=(0, 8))
        if kind == 'failed':
            self.report_button.pack(side='left')
        if ran and self.log.is_file() or kind == 'failed':
            self.help_buttons.pack(anchor='w', pady=(10, 0))
        if advice.retry and image is not None:
            self.offer(image, 'Selected image:', 'Try again')
        elif self.remembered is not None and (image is None or not _same_file(image, self.remembered)):
            self.offer(self.remembered, 'Last time you used:', 'Use this image')
        else:
            self.offer(None)
        self.show(self.problem_frame, *((self.offer_frame,) if self.offered else ()), self.types_label)
        self.enable_choices()
        self.root.configure(cursor="")

    # Choosing and importing an image.

    def choose(self):
        # The picker opens beside the image offered or used last time.
        known = self.offered or self.remembered
        image_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select your Macintosh Prince of Persia 2 game image",
            filetypes=(IMAGE_TYPES, ("All files", "*.*")),
            **({'initialdir': str(known.parent)} if known is not None else {}),
        )
        if not image_path:
            return
        self.start(image_path)

    def use_offered(self):
        if self.offered is not None:
            self.start(self.offered)

    def start(self, image_path):
        kind = preflight(image_path, self.project)
        if kind:
            self.show_problem(kind, image_path)
            return
        self.image = image_path
        self.importing = True
        self.closing = False
        self.task = AssetImport(self.project)
        self.started_at = monotonic()
        self.stages = {'image': (0, 1)}
        self.drawn = {}
        self.shown_progress = 0.0
        self.status.set("Importing game files...")
        self.elapsed.set('0:00 elapsed')
        self.show_importing()
        self.root.update_idletasks()
        # The thread holds no Tk object: one freed there would end the process
        # (Tcl_AsyncDelete), even by a garbage collection it happens to run.
        Thread(target=import_files, args=(image_path, self.project, self.task, self.messages),
               daemon=True).start()
        self.root.after(50, self.poll_import)

    def overall(self):
        """The import's progress, 0-100, from its stages' shares."""
        return overall(self.stages)

    def stage_state(self, key):
        if key not in self.stages:
            return 'pending'
        done, total = self.stages[key]
        return 'done' if total and done >= total else 'running'

    def update_progress(self):
        # Only what changed is redrawn: the window shares the processor
        # with every recovery worker.
        for key, (mark, name, detail) in self.rows.items():
            state = self.stage_state(key)
            done, total = self.stages.get(key, (0, 0))
            percent = 100 * done // total if total > 1 else 0
            shown = (state, f'{percent}%' if state == 'running' and percent else '')
            if self.drawn.get(key) != shown:
                self.drawn[key] = shown
                mark.configure(text=MARKS[state], style=f'{state.title()}.TLabel')
                name.configure(style='Muted.TLabel' if state == 'pending' else 'TLabel')
                detail.configure(text=shown[1])
        target = self.overall()
        # Glide toward the reported progress instead of jumping.
        value = min(target, self.shown_progress + max(0.4, (target - self.shown_progress) / 4))
        if value != self.shown_progress or not self.drawn.get('bar'):
            self.shown_progress = value
            self.drawn['bar'] = True
            self.progressbar.configure(value=value)
        if self.started_at is not None:
            seconds = monotonic() - self.started_at
            text = f'{int(seconds) // 60}:{int(seconds) % 60:02} elapsed'
            share = target / 100
            if 0.08 <= share < 1 and seconds >= 4:
                text += ' · ' + time_left(seconds * (1 - share) / share)
            if text != self.elapsed.get():
                self.elapsed.set(text)

    def poll_import(self):
        while True:
            try:
                kind, text = self.messages.get_nowait()
            except Empty:
                break
            if kind == "progress":
                if not self.closing:
                    self.status.set(text)
                continue
            if kind == 'step':
                stage, done, total = text
                self.stages[stage] = (done, total)
                continue
            self.importing = False
            if self.closing or kind == 'cancelled':
                self.close()
                return
            if kind == "error":
                problem_kind, detail = text
                self.show_problem(problem_kind, self.image, detail, ran=True)
            else:
                remember(game_image=str(Path(self.image).resolve()))
                self.completed = True
                self.close()
            return
        if not self.closing:
            self.update_progress()
        self.root.after(50, self.poll_import)

    def open_log(self):
        if self.log.is_file():
            open_file(self.log)

    def activate(self, _event):
        focus = self.root.focus_get()
        if focus == self.cancel_button:
            self.close()
            return
        if self.importing:
            return
        if focus in (self.same_button, self.import_button, self.log_button, self.report_button):
            if not focus.instate(['disabled']):
                focus.invoke()
            return
        default = self.default_button()
        if not default.instate(["disabled"]):
            default.invoke()

    def close(self):
        if self.importing:
            self.closing = True
            self.status.set('Canceling import...')
            self.cancel_button.state(['disabled'])
            self.task.cancel()
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.completed


def setup_game(project, missing=()):
    return GameSetup(project, missing).run()
