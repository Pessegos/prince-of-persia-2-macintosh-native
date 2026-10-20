"""Native bitmap labels with composed accents and Unicode filename fallback."""

from functools import lru_cache
import math
import unicodedata

from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=12)
def fallback_font(height, east_asian=False, emoji=False):
    names = (('seguiemj.ttf',) if emoji else ()) + (
        ('msyh.ttc', 'YuGothR.ttc') if east_asian else ()) + (
        'segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf')
    for name in names:
        try:
            return ImageFont.truetype(name, height)
        except OSError:
            continue
    return ImageFont.load_default()


def native_character(font, char):
    try:
        encoded = char.encode('mac_roman')
        return len(encoded) == 1 and encoded[0] in font.glyphs
    except UnicodeEncodeError:
        return False


def label_text(font, value, color):
    value = unicodedata.normalize('NFC', str(value))
    if all(native_character(font, char) for char in value):
        return font.text(value, color)
    height = getattr(font, 'height', 16)
    marks = {'\u0300', '\u0301', '\u0302', '\u0303', '\u0308', '\u030a', '\u030c', '\u0327'}
    glyphs = []
    for char in value:
        parts = unicodedata.normalize('NFD', char)
        composed = (len(parts) > 1 and native_character(font, parts[0])
                    and all(mark in marks for mark in parts[1:]))
        if native_character(font, char) or composed:
            raw = font.text(parts[0] if composed else char, color)
            glyph = Image.new('RGBA', (max(1, raw.width), height + 6))
            glyph.paste(raw, (0, 3))
            if composed:
                ink = raw.getbbox()
                if ink:
                    center = (ink[0] + ink[2]) // 2
                    top = max(0, ink[1] - 1)
                    draw = ImageDraw.Draw(glyph)
                    for mark in parts[1:]:
                        if mark == '\u0327':
                            y = ink[3] + 3
                            draw.line(((center + 1, y), (center + 2, y + 1),
                                       (center + 1, y + 3), (center - 1, y + 3)), fill=color)
                        elif mark == '\u0303':
                            draw.line(((center - 3, top + 1), (center - 2, top), (center, top),
                                       (center + 1, top + 1), (center + 3, top + 1)), fill=color)
                        elif mark == '\u0308':
                            draw.rectangle((center - 3, top, center - 2, top + 1), fill=color)
                            draw.rectangle((center + 1, top, center + 2, top + 1), fill=color)
                        elif mark == '\u030a':
                            draw.ellipse((center - 2, top, center + 1, top + 2), outline=color)
                        else:
                            points = {'\u0300': ((center - 1, top), (center + 1, top + 2)),
                                      '\u0301': ((center + 1, top), (center - 1, top + 2)),
                                      '\u0302': ((center - 3, top + 2), (center, top), (center + 2, top + 2)),
                                      '\u030c': ((center - 3, top), (center, top + 2), (center + 2, top))}[mark]
                            draw.line(points, fill=color, width=2)
        else:
            face = fallback_font(height, ord(char) >= 0x2e80, ord(char) >= 0x1f000)
            glyph = Image.new('RGBA', (max(1, math.ceil(face.getlength(char))) + 2, height + 6))
            ImageDraw.Draw(glyph).text((1, getattr(font, 'ascent', height - 3) + 3), char,
                                      font=face, fill=color, anchor='ls')
        glyphs.append(glyph)
    image = Image.new('RGBA', (sum(glyph.width for glyph in glyphs), height + 6))
    x = 0
    for glyph in glyphs:
        image.paste(glyph, (x, 0))
        x += glyph.width
    return image
