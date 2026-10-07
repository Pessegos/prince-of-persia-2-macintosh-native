"""First-run import of user-supplied Macintosh game files."""

from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, ttk

from tools.extract_assets import extract_assets


def import_game(image_path, project, progress=lambda _text: None):
    return extract_assets(image_path, Path(project) / "assets", progress)


class GameSetup:
    def __init__(self, project):
        self.project = Path(project)
        self.completed = False
        self.importing = False
        self.messages = Queue()
        self.root = tk.Tk()
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
        self.import_button.state(["disabled"])
        self.cancel_button.state(["disabled"])
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        Thread(target=self.import_files, args=(image_path,), daemon=True).start()
        self.root.after(50, self.poll_import)

    def import_files(self, image_path):
        try:
            import_game(image_path, self.project,
                        lambda text: self.messages.put(("progress", text)))
        except Exception as error:
            self.messages.put(("error", str(error)))
        else:
            self.messages.put(("complete", ""))

    def poll_import(self):
        while True:
            try:
                kind, text = self.messages.get_nowait()
            except Empty:
                break
            if kind == "progress":
                self.status.set(text)
                continue
            self.importing = False
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
        if not self.importing:
            self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.completed


def setup_game(project):
    return GameSetup(project).run()
