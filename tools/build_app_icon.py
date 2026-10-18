"""Build the pixel-art Windows icon without implicit smoothing by Tk."""

from pathlib import Path

from PIL import Image


ICON_DIR = Path(__file__).resolve().parent.parent / "pop2" / "icons"
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def build_icon(source=ICON_DIR / "prince.png", output=ICON_DIR / "prince.ico"):
    with Image.open(source) as image:
        frames = [image.convert("RGBA").resize((size, size), Image.Resampling.NEAREST)
                  for size in ICON_SIZES]
    # Tk 8.6 does not reliably select native-sized frames in a PNG-backed ICO.
    frames[-1].save(output, format="ICO", bitmap_format="bmp",
                    sizes=[frame.size for frame in frames], append_images=frames[:-1])
    return Path(output)


if __name__ == "__main__":
    print(build_icon())
