"""Shared application identity for the game and first-run importer."""

from pathlib import Path
import sys
import tkinter as tk


ICON_DIR = Path(__file__).resolve().parent / "icons"
APP_ID = "Pessegos.PrinceOfPersia2.MacintoshNative"


def create_root():
    if sys.platform == "win32":
        import ctypes

        # Give the taskbar a game identity instead of grouping it with Python.
        set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        set_app_id(APP_ID)

    root = tk.Tk()
    if sys.platform == "win32":
        icon = str(ICON_DIR / "prince.ico")
        root.iconbitmap(bitmap=icon, default=icon)
    else:
        source = tk.PhotoImage(master=root, file=str(ICON_DIR / "prince.png"))
        root._app_icon_images = tuple(source.subsample(scale) for scale in (8, 16))
        root.iconphoto(True, *root._app_icon_images)
    return root
