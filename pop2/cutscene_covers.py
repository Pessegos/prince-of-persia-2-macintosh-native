"""Reconstruct the user's chosen covers from their imported game resources.

The rectangles refer to an exact 8x enlargement of the native frame, retaining
the half/one-pixel offsets of the supplied crops. No original artwork is shipped.
"""

from PIL import Image, ImageOps


COVER_SIZE = (1024, 576)
COVER_SHOTS = {
    'opening': (33.5, (512, 552, 3584, 2280)),
    'opening_titles': (8.5, (0, 384, 4096, 2688)),
    'opening_story': (62, (512, 496, 3584, 2224)),
    'voyage': (4.5, (512, 496, 3584, 2224)),
    'discovery': (75, (512, 548, 3584, 2276)),
    'carpet': (14.5, (0, 616, 4096, 2920)),
    'vision': (23, (0, 625, 4080, 2920)),
    'horse': (2, (0, 0, 4080, 2295)),
    'tower': (5, (0, 0, 4080, 2295)),
}


def selected_cover(player, key):
    seconds, crop = COVER_SHOTS[key]
    player.advance(seconds)
    frame = player.frame().convert('RGB')
    frame = frame.resize((frame.width * 8, frame.height * 8), Image.Resampling.NEAREST).crop(crop)
    # Retain the supplied composition and proportions inside the card area.
    picture = ImageOps.contain(frame, COVER_SIZE, method=Image.Resampling.NEAREST)
    result = Image.new('RGB', COVER_SIZE, '#101010')
    result.paste(picture, ((result.width - picture.width) // 2,
                          (result.height - picture.height) // 2))
    return result
