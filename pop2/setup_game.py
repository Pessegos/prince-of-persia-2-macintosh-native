"""First-run import of user-supplied Macintosh game files."""

from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from time import monotonic
import tkinter as tk
from tkinter import filedialog, ttk

from pop2.app_window import create_root
from pop2.asset_import import AssetImport, ImportCancelled


def import_game(image_path, project, progress=lambda _text: None, task=None):
    return (task or AssetImport(project)).run(image_path, progress)


class GameSetup:
    def __init__(self, project):
        self.project = Path(project)
        self.completed = False
        self.importing = False
        self.closing = False
        self.task = None
        self.started_at = None
        self.messages = Queue()
        self.root = create_root()
        self.root.title("Prince of Persia 2 - Game Files")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        panel = ttk.Frame(self.root, padding=24)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Original game files required", font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            panel,
            text="Macintosh Prince of Persia 2 disk image (.hfs, .hfv, .dsk or .img)",
            wraplength=400,
        ).pack(anchor="w", pady=(12, 18))
        self.status = tk.StringVar()
        self.status_label = ttk.Label(panel, textvariable=self.status, wraplength=400)
        self.status_label.pack(anchor="w", fill="x", pady=(0, 18))
        self.progressbar = ttk.Progressbar(panel, mode='indeterminate')
        self.progressbar.pack(fill='x', pady=(0, 8))
        self.elapsed = tk.StringVar()
        ttk.Label(panel, textvariable=self.elapsed).pack(anchor='w', pady=(0, 12))
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x")
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.close)
        self.cancel_button.pack(side="right")
        self.import_button = ttk.Button(buttons, text="Choose disk image...", command=self.choose)
        self.import_button.pack(side="left")
        self.import_button.focus_set()
        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.bind("<Return>", self.activate)

        self.root.update_idletasks()
        width, height = max(448, self.root.winfo_reqwidth()), self.root.winfo_reqheight()
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def choose(self):
        image_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select the Macintosh Prince of Persia 2 disk image",
            filetypes=(
                ("Macintosh disk images", "*.hfs *.hfv *.dsk *.img"),
                ("All files", "*.*"),
            ),
        )
        if not image_path:
            return
        self.status.set("Importing game files...")
        self.importing = True
        self.closing = False
        self.task = AssetImport(self.project)
        self.started_at = monotonic()
        self.elapsed.set('00:00')
        self.progressbar.start(20)
        self.import_button.state(["disabled"])
        self.root.update_idletasks()
        Thread(target=self.import_files, args=(image_path,), daemon=True).start()
        self.root.after(50, self.poll_import)

    def import_files(self, image_path):
        try:
            import_game(image_path, self.project,
                        lambda text: self.messages.put(("progress", text)), task=self.task)
        except ImportCancelled:
            self.messages.put(('cancelled', ''))
        except Exception as error:
            self.messages.put(("error", str(error)))
        else:
            self.messages.put(("complete", ""))

    def poll_import(self):
        if self.started_at is not None:
            minutes, seconds = divmod(int(monotonic() - self.started_at), 60)
            self.elapsed.set(f'{minutes:02}:{seconds:02}')
        while True:
            try:
                kind, text = self.messages.get_nowait()
            except Empty:
                break
            if kind == "progress":
                if not self.closing:
                    self.status.set(text)
                continue
            self.importing = False
            self.progressbar.stop()
            if self.closing or kind == 'cancelled':
                self.close()
                return
            if kind == "error":
                self.status.set(text)
                self.import_button.state(["!disabled"])
                self.cancel_button.state(["!disabled"])
                self.root.configure(cursor="")
                self.root.geometry("")
            else:
                self.completed = True
                self.close()
            return
        self.root.after(50, self.poll_import)

    def activate(self, _event):
        if self.root.focus_get() == self.cancel_button:
            self.close()
        elif not self.import_button.instate(["disabled"]):
            self.choose()

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


def setup_game(project):
    return GameSetup(project).run()
