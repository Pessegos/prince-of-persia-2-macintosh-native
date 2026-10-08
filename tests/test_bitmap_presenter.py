import json
import os
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.bitmap_presenter import CanvasBitmap


class CanvasBitmapTests(unittest.TestCase):
    def test_reuses_bitmap_and_coalesces_idle_paints(self):
        canvas = Mock()
        frame = Image.new("RGB", (10, 8), "red")
        with patch("pop2.bitmap_presenter.ImageWin.Dib") as dib:
            dib.return_value.size = frame.size
            presenter = CanvasBitmap(canvas)
            presenter.present(frame, (3, 5))
            presenter.present(frame, (4, 6))
            dib.assert_called_once_with("RGB", (10, 8))
            canvas.after_idle.assert_called_once_with(presenter.paint)
            self.assertEqual(dib.return_value.paste.call_count, 2)
            presenter.paint()
            self.assertEqual(dib.return_value.draw.call_args.args[1], (4, 6, 14, 14))
            self.assertIsNone(presenter.after_id)

    def test_resize_replaces_bitmap_and_close_cancels_pending_paint(self):
        canvas = Mock()
        canvas.after_idle.return_value = "paint"
        with patch("pop2.bitmap_presenter.ImageWin.Dib") as dib:
            dib.return_value.size = (10, 8)
            presenter = CanvasBitmap(canvas)
            presenter.present(Image.new("RGB", (10, 8)), (0, 0))
            presenter.present(Image.new("RGB", (20, 16)), (0, 0))
            self.assertEqual(dib.call_count, 2)
            presenter.close()
            canvas.after_cancel.assert_called_once_with("paint")
            self.assertIsNone(presenter.bitmap)
            self.assertIsNone(presenter.after_id)
            presenter.redraw()
            self.assertEqual(canvas.after_idle.call_count, 1)


@unittest.skipUnless(sys.platform == "win32" and not os.environ.get("CI"), "Interactive Windows desktop required")
class CanvasBitmapIntegrationTests(unittest.TestCase):
    def test_fullscreen_pixels_exposure_and_return_to_tk_presentation(self):
        result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
            import ctypes
            import json
            import tkinter as tk
            from PIL import Image, ImageGrab
            from pop2.game_ui import VISIBLE_VIEWPORT, fit_viewport
            from pop2.window_controls import WindowControls

            host = WindowControls()
            host.root = tk.Tk()
            host.root.attributes('-fullscreen', True)
            host.root.attributes('-topmost', True)
            host.canvas = tk.Canvas(host.root, bg='black', highlightthickness=0)
            host.canvas.pack(fill='both', expand=True)
            host.bitmap_presenter = None
            host.canvas.bind('<Expose>', host.expose_viewport)
            host.fullscreen, host.intro = True, object()
            host.native_viewport = Image.new('RGBA', (512, 384), 'blue')
            host.native_viewport.paste('red', (20, 20, 180, 230))
            host.native_viewport.paste('white', (260, 35, 262, 170))
            host.root.update()
            host.root.lift()
            host.root.focus_force()
            host.present_viewport()
            host.root.update()

            def matches():
                size, origin = fit_viewport(host.canvas.winfo_width(), host.canvas.winfo_height())
                x = host.canvas.winfo_rootx() + origin[0]
                y = host.canvas.winfo_rooty() + origin[1]
                ctypes.windll.dwmapi.DwmFlush()
                shot = ImageGrab.grab().crop((x, y, x + size[0], y + size[1]))
                expected = host.native_viewport.crop(VISIBLE_VIEWPORT).convert('RGB').resize(size, Image.Resampling.NEAREST)
                if shot.tobytes() != expected.tobytes():
                    import sys
                    print('mismatch', x, y, size, shot.getpixel((0, 0)), expected.getpixel((0, 0)),
                          shot.getpixel((500, 500)), expected.getpixel((500, 500)), file=sys.stderr)
                return shot.tobytes() == expected.tobytes()

            initial = matches()
            # Force a real WM_PAINT, not just the Python exposure callback.
            redraw = ctypes.windll.user32.RedrawWindow
            redraw.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
            redraw(host.canvas.winfo_id(), None, None, 0x101)
            host.root.update()
            exposed = matches()
            host.root.withdraw()
            host.root.update()
            host.root.deiconify()
            host.root.update()
            restored = matches()
            host.intro = None
            host.present_viewport()
            host.root.update()
            fallback = matches() and host.bitmap_presenter is None and host.image_ref is not None
            host.root.destroy()
            print(json.dumps([initial, exposed, restored, fallback]))
        """)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), [True] * 4, result.stderr)


if __name__ == "__main__":
    unittest.main()
