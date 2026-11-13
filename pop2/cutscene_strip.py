"""A retained Tk viewport: move cached artwork instead of copying its pixels."""

import tkinter as tk
from types import SimpleNamespace

from pop2.menu_theme import c


class CutsceneStrip:
    def __init__(self, scene):
        self.scene = scene
        self.canvas = tk.Canvas(scene.canvas, bg=c('#181818'), borderwidth=0,
                                highlightthickness=0, takefocus=0)
        self.canvas.bindtags(('DevelopmentInput', *self.canvas.bindtags()))
        self.item = self.canvas.create_image(0, 0, anchor='nw', tags='content')
        self.borders = tuple(self.canvas.create_rectangle(0, 0, 0, 0, width=0,
                            fill=c('#c6b58c'), state='hidden', tags='content') for _ in range(4))
        self.border = None
        self.region = None
        self.photo = None
        self.offset = None
        self.shown = False
        for sequence, callback in (
                ('<Button-1>', scene.dev_click), ('<Double-Button-1>', scene.dev_double_click),
                ('<ButtonRelease-1>', scene.dev_release), ('<Motion>', scene.dev_hover),
                ('<B1-Motion>', scene.dev_hover), ('<MouseWheel>', scene.dev_scroll),
                ('<Button-4>', scene.dev_scroll), ('<Button-5>', scene.dev_scroll)):
            self.canvas.bind(sequence, self.forward(callback))
        self.canvas.bind('<Leave>', self.leave)

    def forward(self, callback):
        def dispatch(event):
            values = vars(event).copy()
            values['x'] += self.region[0]
            values['y'] += self.region[1]
            return callback(SimpleNamespace(**values))
        return dispatch

    def leave(self, event):
        # An implicit button grab must continue a drag outside this viewport.
        if not event.state & 0x100:
            return self.scene.dev_pointer_leave(event)

    def show(self, region, photo, offset):
        if photo is not self.photo:
            self.canvas.itemconfigure(self.item, image=photo)
            self.photo = photo
        if offset != self.offset:
            self.canvas.move('content', (self.offset or 0) - offset, 0)
            self.offset = offset
        if region != self.region or not self.shown:
            self.canvas.place(x=region[0], y=region[1], width=region[2] - region[0],
                              height=region[3] - region[1])
            self.region = region
            self.shown = True

    def highlight(self, border):
        if border == self.border:
            return
        self.border = border
        for item, rect in zip(self.borders, border or (None,) * 4):
            self.canvas.itemconfigure(item, state='normal' if rect is not None else 'hidden')
            if rect is not None:
                x1, y1, x2, y2 = rect
                self.canvas.coords(item, x1 - self.offset, y1, x2 - self.offset, y2)

    def hide(self):
        if self.shown:
            self.canvas.place_forget()
            self.shown = False

    def close(self):
        self.canvas.destroy()
