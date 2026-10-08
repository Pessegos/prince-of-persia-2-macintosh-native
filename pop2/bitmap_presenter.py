"""Opaque Windows bitmap presentation for high-refresh fullscreen scenes."""

from PIL import ImageWin


class CanvasBitmap:
    def __init__(self, canvas):
        self.canvas = canvas
        self.bitmap = None
        self.position = (0, 0)
        self.after_id = None

    def present(self, frame, position):
        if self.bitmap is None or self.bitmap.size != frame.size:
            self.bitmap = ImageWin.Dib("RGB", frame.size)
        self.bitmap.paste(frame)
        self.position = position
        self.redraw()

    def redraw(self):
        if self.bitmap is not None and self.after_id is None:
            # Paint after Tk clears exposed/resized canvas areas, without a
            # nested event loop or an extra full-resolution Tk photo upload.
            self.after_id = self.canvas.after_idle(self.paint)

    def paint(self):
        self.after_id = None
        x, y = self.position
        width, height = self.bitmap.size
        self.bitmap.draw(ImageWin.HWND(self.canvas.winfo_id()), (x, y, x + width, y + height))

    def close(self):
        if self.after_id is not None:
            self.canvas.after_cancel(self.after_id)
            self.after_id = None
        self.bitmap = None
