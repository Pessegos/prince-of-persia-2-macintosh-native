from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache
import struct

from PIL import Image, ImageChops, ImageDraw, ImageFont

from animation_data import parse_frame_records, shape_id_for_action
from mac_resources import parse_resource_fork
from terrain import LevelMap, character_column, character_row, floor_contact_x


PROJECT_DIR = Path(__file__).resolve().parent
ASSET_DIR = PROJECT_DIR / "assets"
OUTPUT_DIR = PROJECT_DIR / "rendered"
TILE_WIDTH = 51
TILE_HEIGHT = 120
ROOM_WIDTH = TILE_WIDTH * 10
# Original DATA/A5:b4b2 contains row bottoms 125, 245, 365; b014 clips at 365.
SCENERY_Y_OFFSET = 5
ROOM_HEIGHT = TILE_HEIGHT * 3 + SCENERY_Y_OFFSET
VIEWPORT_WIDTH = 512
VIEWPORT_HEIGHT = 384
ROOM_ORIGIN_X = (VIEWPORT_WIDTH - ROOM_WIDTH) // 2
# CODE:4, 0x31fa places the Prince at row * 120 + 106 (not the scenery anchor).
OPENING_FLOOR_Y = TILE_HEIGHT + 106

# DrawRoofBackWall (CODE:23, 0x0090) uses DATA/A5:cc4a before the wall SHAP.
ROOF_BACKGROUND_FILL = (
    0, 0, 0, 0, 0, 3, 2, 0, 0, 1, 0, 0, 2, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0,
    2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 3, 2, 0, 3, 2,
)
# DrawRoofGlass (0x0c84), DATA/A5:cd00 and cd1e.
ROOF_GLASS_FRAMES = (8, 4, 3, 2, 1, 5, 6, 7, 6, 5, 0, 1, 2, 3)
ROOF_GLASS_OFFSETS = (
    (19, -15), (19, -15), (14, -13), (10, -14), (10, -16),
    (19, -15), (19, -16), (19, -16), (11, -18),
)
# DrawRoofDecoration 23:018e, expanded DATA/A5 cca8 and ccea.
# (SHAP index, X, bottom-Y offset, native drawing pass).
ROOF_DECORATIONS = (
    (59, 47, -56, 1), (60, 0, 0, 5), (61, 48, -7, 5),
    (62, 0, -42, 5), (63, 35, -88, 1), (64, 47, -85, 1),
    (65, 45, -18, 1), (66, 46, -12, 1), (67, 46, -21, 1),
    (68, 48, 0, 1), (121, 38, -88, 5),
)
# ComputeHalfRect 3:3694-36f0, DATA b4ba: QuickDraw top/left/bottom/right
# for poses 135-144, translated by the drawn cell's 51x120 origin.
CLIMB_FOREGROUND_RECTS = (
    (109, 0, 120, 26), (109, 0, 120, 25), (109, 0, 120, 26),
    (109, 0, 120, 31), (109, 0, 120, 24), (109, 0, 120, 25),
    (109, 0, 120, 30), (112, 0, 120, 22), (112, 0, 120, 20),
    (112, 0, 120, 20),
)


def add_alpha(mask, alpha, x, y):
    rect = (x, y, x + alpha.width, y + alpha.height)
    mask.paste(ImageChops.lighter(mask.crop(rect), alpha), (x, y))


@dataclass(frozen=True)
class RoofForeground:
    row: int
    column: int
    kind: int
    x: int
    y: int
    alpha: Image.Image
    decoration: bool = False


def actor_foreground_column(state, record, bounds=None):
    # IndexChar 4:4558 / GetCharEdges 4:5e10: mode 1 indexes the drawn
    # rectangle; other modes index the supporting foot. 5:48b0 subtracts 4
    # from native X (scene X + 207) before its signed division by 51.
    if state.animation_state == 1 and bounds is not None:
        native_left = bounds[0] + 207
        numerator = native_left - 4
        quotient = abs(numerator) // TILE_WIDTH * (-1 if numerator < 0 else 1)
        column = max(0, quotient - 4 - int(native_left < 0))
    else:
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
    if 135 <= state.action < 149 or state.animation_state in (2, 3, 4, 6):
        column += -1 if state.facing else 1
    return column


@dataclass(frozen=True)
class RoofLedge:
    row: int
    x: int
    y: int
    alpha: Image.Image

    def add_to(self, mask, width):
        alpha = self.alpha.crop((0, 0, width, self.alpha.height))
        add_alpha(mask, alpha, self.x, self.y)

    def behind_actor(self, state, bounds):
        # DrawRoofFloor 23:0614-06c6 tests the ledge rectangle against the
        # character rectangle during climbing/falling and these hang poses.
        if state is None or bounds is None or state.sequence_id == 68:
            return False
        if state.animation_state not in (3, 4, 6) and state.action not in (91, 80, 81, 136):
            return False
        left, top, right, bottom = bounds
        return (left < self.x + self.alpha.width and right >= self.x
                and top < self.y + self.alpha.height and bottom >= self.y)


def roof_ledge_width(room_id, row, actor_row, actor_bottom):
    # DrawRoofFloor, CODE:23 0x04c4-0x0546. Only this strip is foreground;
    # the rest of the sloping side remains scenery behind the character.
    if room_id == 3:
        return 20
    if room_id in (0, 2):
        return 19
    if room_id in (9, 10) and (row != actor_row or actor_bottom > row * TILE_HEIGHT + 109):
        return 17
    return 22


@dataclass(frozen=True)
class OpeningRoom:
    background: Image.Image
    foreground: Image.Image
    actor_occlusion: dict[int, Image.Image]
    ledges: tuple[RoofLedge, ...]
    pieces: tuple[RoofForeground, ...]
    room_id: int

    def flattened(self):
        return Image.alpha_composite(self.background, self.foreground)

    def actor_mask(self, row, bottom=None, state=None, bounds=None, record=None):
        if (state is not None and getattr(state, "actor_type", None) == 2
                and getattr(state, "level_kind", None) == 5
                and state.animation_state == 9 and self.room_id not in (15, 18)):
            # ClipChar 4:4210-422c skips ordinary roof clipping for tumbles.
            return Image.new("L", (ROOM_WIDTH, ROOM_HEIGHT), 0)
        row = max(-1, min(4, row))
        if state is None and (bottom is None or self.room_id not in (9, 10)):
            return self.actor_occlusion[row]
        if bottom is None:
            bottom = bounds[3] if bounds is not None else row * TILE_HEIGHT + 106
        mask = Image.new("L", (ROOM_WIDTH, ROOM_HEIGHT), 0)
        column = (actor_foreground_column(state, record, bounds)
                  if state is not None and record is not None else None)
        indexed_row = row
        if state is not None and state.animation_state == 1 and bounds is not None:
            indexed_row = character_row(bounds[3])
            if indexed_row == -1:
                indexed_row = 3
        climbing = state is not None and 135 <= state.action < 149
        hanging = state is not None and (state.action in (80, 81) or 87 <= state.action < 100)
        airborne = (state is not None and state.animation_state in (3, 4)
                    and not climbing and not hanging)
        # SEQS:10 advances the physical floor at pose 141, while the drawn
        # body still overlaps the lower row. Keep the climbed roof's near
        # face/ledge in front until the climb clears it, not its entire side.
        roof_row = row - int(climbing and state.action < 141 or hanging)
        for piece in self.pieces:
            # Full foreground SHAPs can overlap a body outside the two indexed
            # cells. Climbing keeps its separate partial-redraw exception.
            indexed = column is None or piece.column in (column - 1, column)
            overlaps = (bounds is not None and bounds[0] < piece.x + piece.alpha.width
                        and bounds[2] >= piece.x and bounds[1] < piece.y + piece.alpha.height
                        and bounds[3] >= piece.y)
            # Fall physics advances the supporting row before the sprite
            # clears the upper facade. Keep intersecting near-face SHAPs in
            # front throughout the fall, not only once Catch selects pose 80.
            # Sloping sides are RoofLedges and retain their own back/strip rule.
            airborne_foreground = airborne and overlaps
            # Catching the left edge faces the flat near facade, not the
            # shaded side. Keep its complete foreground through SEQS:10's
            # row change; DrawHalf alone exposes hands/feet at poses 141-148.
            near_facade_climb = column is not None and climbing and state.facing and overlaps
            climbed_roof = ((piece.kind == 1 or piece.decoration) and piece.row == roof_row
                            and (climbing and (indexed or state.action < 141 and overlaps)
                                 or near_facade_climb
                                 or hanging and overlaps))
            if piece.row < row and not (climbed_roof or airborne_foreground):
                continue
            if (column is None or indexed and piece.row >= indexed_row or climbed_roof or airborne_foreground
                    or piece.kind == 20 or piece.decoration or piece.kind == 1 and not climbing):
                # Foreground wall SHAPs remain in front across the whole
                # actor rectangle, including a right-facing catch. Their
                # shaded side is background, not part of this alpha mask.
                add_alpha(mask, piece.alpha, piece.x, piece.y)
            elif piece.kind == 1 and piece.row == row and 135 <= state.action < 145:
                top, left, bottom_edge, right = CLIMB_FOREGROUND_RECTS[state.action - 135]
                rect = (piece.column * TILE_WIDTH + left, row * TILE_HEIGHT + top,
                        piece.column * TILE_WIDTH + right, row * TILE_HEIGHT + bottom_edge)
                alpha = piece.alpha.crop((rect[0] - piece.x, rect[1] - piece.y,
                                          rect[2] - piece.x, rect[3] - piece.y))
                add_alpha(mask, alpha, rect[0], rect[1])
        for ledge in self.ledges:
            if ledge.row >= roof_row and not ledge.behind_actor(state, bounds):
                width = roof_ledge_width(self.room_id, ledge.row, row, bottom)
                ledge.add_to(mask, width)
        return mask


def character_sprite_top(bottom_y, height):
    # AddMid (CODE:3, 0x0302-0x030c) treats character bottom Y as inclusive.
    return bottom_y - height + 1


def u16(data, offset):
    return struct.unpack_from(">H", data, offset)[0]


def s16(data, offset):
    return struct.unpack_from(">h", data, offset)[0]


def load_resource_file(name):
    return parse_resource_fork((ASSET_DIR / name).read_bytes())


def decode_ctbl(data):
    count = u16(data, 0)
    colors = {}
    for i in range(count):
        offset = 2 + i * 4
        red, green, blue, index = data[offset:offset + 4]
        colors[index] = (red, green, blue, 255)
    return colors


def decompress_rows(data, height, row_bytes):
    output = bytearray()
    offset = 0
    for _ in range(height):
        encoded_size = u16(data, offset)
        offset += 2
        end = offset + encoded_size
        row = bytearray()
        while offset < end:
            token = data[offset]
            offset += 1
            if token & 0x80:
                count = (token & 0x7F) + 1
                row.extend([data[offset]] * count)
                offset += 1
            else:
                count = token + 1
                row.extend(data[offset:offset + count])
                offset += count
        if len(row) != row_bytes:
            raise ValueError(f"SHAP row decoded to {len(row)} bytes, expected {row_bytes}")
        output.extend(row)
    return bytes(output)


def decode_shap(data, palette):
    flags, row_stride, width, height = struct.unpack_from(">HhhH", data, 0)
    compression = (flags & 0x0F00) >> 8
    pixels = data[12:]

    if compression & 0x01:
        pixels = decompress_rows(pixels, height, width)
    elif compression == 0:
        if len(pixels) != row_stride * height:
            raise ValueError("Uncompressed SHAP data does not match its row stride")
        pixels = b"".join(
            pixels[row * row_stride:row * row_stride + width]
            for row in range(height)
        )
    else:
        raise ValueError(f"Unsupported SHAP compression flags: {flags:#06x}")

    if len(pixels) != width * height:
        raise ValueError(f"SHAP data size {len(pixels)} does not match {width}x{height}")

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    image.putdata([palette.get(index, (255, 0, 255, 255)) if index else (0, 0, 0, 0) for index in pixels])
    return image


def load_shapes(resources, ctbl_id_for_shape):
    palettes = {rid: decode_ctbl(item["data"]) for rid, item in resources["CTBL"].items()}
    shapes = {}
    for shape_id, item in resources.get("SHAP", {}).items():
        palette_id = ctbl_id_for_shape(shape_id)
        if palette_id in palettes:
            try:
                shapes[shape_id] = decode_shap(item["data"], palettes[palette_id])
            except ValueError:
                pass
    return shapes


def make_kid_contact_sheet():
    resources = load_resource_file("Kid.rsrc")
    shape_ids = sorted(resources.get("SHAP", {}))
    palette_ids = sorted(resources.get("CTBL", {}))
    if not shape_ids or not palette_ids:
        raise ValueError("Kid.rsrc has no SHAP or CTBL resources")

    font = ImageFont.load_default()
    cell_width, cell_height, columns = 90, 74, 16
    rows = (len(shape_ids) + columns - 1) // columns

    preview_palettes = [palette_id for palette_id in (25001, 2000) if palette_id in resources["CTBL"]]
    for palette_id in preview_palettes:
        palette_data = resources["CTBL"].get(palette_id)
        if palette_data is None:
            continue
        palette = decode_ctbl(palette_data["data"])
        sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (34, 36, 40))
        draw = ImageDraw.Draw(sheet)
        for index, shape_id in enumerate(shape_ids):
            try:
                sprite = decode_shap(resources["SHAP"][shape_id]["data"], palette)
            except ValueError:
                continue
            x = (index % columns) * cell_width
            y = (index // columns) * cell_height
            sheet.paste(sprite, (x + (cell_width - sprite.width) // 2, y + 3), sprite)
            draw.text((x + 2, y + 57), str(shape_id), fill=(230, 230, 230), font=font)
        path = OUTPUT_DIR / f"kid_sprites_ctbl_{palette_id}.png"
        sheet.save(path)
        print(f"Wrote {path.name}: {len(shape_ids)} SHAP frames, CTBL {palette_id}")

    palette = decode_ctbl(resources["CTBL"][25001]["data"])
    focus_ids = [shape_id for shape_id in range(25002, 25082) if shape_id in resources["SHAP"]]
    columns, cell_width, cell_height = 10, 92, 100
    rows = (len(focus_ids) + columns - 1) // columns
    focus = Image.new("RGB", (columns * cell_width, rows * cell_height), (34, 36, 40))
    draw = ImageDraw.Draw(focus)
    font = ImageFont.load_default()
    for index, shape_id in enumerate(focus_ids):
        sprite = decode_shap(resources["SHAP"][shape_id]["data"], palette)
        sprite = sprite.resize((sprite.width * 2, sprite.height * 2), Image.Resampling.NEAREST)
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        focus.paste(sprite, (x + (cell_width - sprite.width) // 2, y + 2), sprite)
        draw.text((x + 2, y + 77), str(shape_id), fill=(235, 235, 235), font=font)
    focus.save(OUTPUT_DIR / "kid_sprites_focus.png")


@lru_cache(maxsize=1)
def rooftop_scene_data():
    level_resources = load_resource_file("Prince.rsrc")
    level = level_resources["LEVL"][2000]["data"]
    level_map = LevelMap(level)
    level_kind = u16(level, 0x2186)
    if level_kind != 5:
        raise ValueError(f"Expected Rooftops level kind 5, got {level_kind}")

    rooftop_resources = load_resource_file("Rooftops.rsrc")
    shapes = load_shapes(rooftop_resources, lambda shape_id: 3500 if shape_id <= 3608 else 3501)
    piece_data = rooftop_resources["PIEC"][3500]["data"]
    pieces = [struct.unpack_from(">10h", piece_data, offset) for offset in range(0, len(piece_data), 20)]
    return level_map, shapes, pieces


def build_opening_room(include_curtain=True, room_id=None):
    # Decode the read-only level atlas once, not during every screen cut.
    level_map, shapes, pieces = rooftop_scene_data()
    if room_id is None:
        room_id = level_map.start_room

    layers = [Image.new("RGBA", (ROOM_WIDTH, ROOM_HEIGHT), (0, 0, 0, 0)) for _ in range(4)]
    ledges = []
    foreground_pieces = []

    def tile_info(x, y):
        tile = level_map.tile(room_id, x, y)
        return tile.kind, tile.foreground, tile.background

    def draw_shape(layer_index, shape_id, tile_x, tile_y, dx=0, dy=0, ledge=False,
                   decoration=False):
        shape = shapes.get(shape_id)
        if shape is None:
            raise ValueError(f"Missing/unsupported rooftop SHAP:{shape_id}")
        anchor_x = tile_x * TILE_WIDTH + dx
        anchor_y = (tile_y + 1) * TILE_HEIGHT + SCENERY_Y_OFFSET + dy
        layers[layer_index].paste(shape, (anchor_x, anchor_y - shape.height), shape)
        if layer_index == 3:
            if ledge:
                ledges.append(RoofLedge(tile_y, anchor_x, anchor_y - shape.height,
                                        shape.getchannel("A")))
            else:
                foreground_pieces.append(RoofForeground(tile_y, tile_x, tile_info(tile_x, tile_y)[0],
                                                       anchor_x, anchor_y - shape.height,
                                                       shape.getchannel("A"), decoration))

    def draw_background(tile_x, tile_y, background):
        background_type = background & 0x3F
        if background_type:
            piece = pieces[0x24]
            fill = ROOF_BACKGROUND_FILL[background_type]
            if fill:
                draw_shape(0, 3500 + fill, tile_x, tile_y, piece[2], piece[3])
            draw_shape(0, 3500 + background_type, tile_x, tile_y, piece[2], piece[3])

    def draw_room_tile(tile_x, tile_y):
        tile_type, foreground, background = tile_info(tile_x, tile_y)
        if tile_type in (0x00, 0x31):
            draw_background(tile_x, tile_y, background)
            if tile_type == 0x31 and include_curtain:
                glass_frame = ROOF_GLASS_FRAMES[foreground] if foreground < 14 else 8
                dx, dy = ROOF_GLASS_OFFSETS[glass_frame]
                draw_shape(1, 3500 + 0x58 + glass_frame, tile_x, tile_y, dx, dy)
        elif tile_type == 0x01:
            piece = pieces[0x01]
            draw_background(tile_x, tile_y, background)
            draw_shape(3, 3500 + (foreground & 0x000F) + 0x33, tile_x, tile_y, piece[8], piece[9])
            if tile_x < 9 and tile_info(tile_x + 1, tile_y)[0] in (0x00, 0x09, 0x1B, 0x2F, 0x31):
                draw_shape(3, 3500 + min((foreground & 0x000F) + 0x2F, 0x32),
                           tile_x + 1, tile_y, 0, piece[6], ledge=True)
        elif tile_type == 0x14:
            if room_id != 0x0E:
                piece = pieces[0x24]
                draw_shape(3, 3500 + (foreground & 0x001F) + 0x45, tile_x, tile_y,
                           piece[8], piece[9])
        else:
            raise ValueError(f"Opening room has unimplemented tile type {tile_type:#x}")
        decoration_id = (foreground >> 8) & 15
        if decoration_id:
            if decoration_id > len(ROOF_DECORATIONS):
                raise ValueError(f"Unimplemented rooftop decoration {decoration_id}")
            shape, dx, dy, draw_pass = ROOF_DECORATIONS[decoration_id - 1]
            draw_shape(3 if draw_pass == 1 else 1, 3500 + shape, tile_x, tile_y,
                       dx, dy, decoration=True)

    # Neighbor rows can overlap the top/bottom five pixels of the room clip.
    for tile_y in range(3, -2, -1):
        for tile_x in range(-1, 10):
            if level_map.tile(room_id, tile_x, tile_y).room is None:
                # The physics sentinel (wall 20) has no scenery. Where there
                # is no upper room, extend the top row's background pattern
                # through the five-pixel viewport margin, without foreground.
                if tile_y == -1 and 0 <= tile_x < 10:
                    bg_type = tile_info(tile_x, 0)[2] & 0x3f
                    if bg_type:
                        strip = shapes[3500 + bg_type].crop(
                            (0, 0, TILE_WIDTH, SCENERY_Y_OFFSET))
                        layers[0].paste(strip, (tile_x * TILE_WIDTH, 0), strip)
                continue
            draw_room_tile(tile_x, tile_y)

    background = Image.new("RGBA", (ROOM_WIDTH, ROOM_HEIGHT), (0, 0, 0, 255))
    for layer in layers[:3]:
        background = Image.alpha_composite(background, layer)
    # Keep the floor ownership of foreground pieces. The native rooftop draw
    # passes distinguish a ledge in back (23:05a2) from the actor's foreground;
    # one flattened overlay incorrectly cuts a lower-floor falling sprite.
    occlusion = {}
    for row in range(-1, 5):
        mask = Image.new("L", (ROOM_WIDTH, ROOM_HEIGHT), 0)
        for piece in foreground_pieces:
            if piece.row >= row:
                add_alpha(mask, piece.alpha, piece.x, piece.y)
        for ledge in ledges:
            if ledge.row >= row:
                width = roof_ledge_width(room_id, ledge.row, ledge.row,
                                        ledge.row * TILE_HEIGHT + 106)
                ledge.add_to(mask, width)
        occlusion[row] = mask
    return OpeningRoom(background, layers[3], occlusion,
                       tuple(ledges), tuple(foreground_pieces), room_id)


def make_opening_room():
    room_image = build_opening_room().flattened()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "opening_room.png"
    room_image.save(path)
    print(f"Wrote {path.name}: Level 1 opening room, {ROOM_WIDTH}x{ROOM_HEIGHT}")
    return room_image


def make_scene_preview(room):
    level_resources = load_resource_file("Prince.rsrc")
    level = level_resources["LEVL"][2000]["data"]
    start_tile = u16(level, 0x219A)
    player_x = (start_tile % 10) * TILE_WIDTH + 14

    kid = load_resource_file("Kid.rsrc")
    palette = decode_ctbl(kid["CTBL"][25001]["data"])
    first_shape_id, _shape_count = struct.unpack_from(">HH", kid["SHPL"][25001]["data"], 0)
    frames = parse_frame_records(kid["FRAM"][25001]["data"])
    player_shape_id = shape_id_for_action(frames, first_shape_id, action=15)
    player = decode_shap(kid["SHAP"][player_shape_id]["data"], palette)
    scene = room.background.copy()
    record = frames[15]
    player_y = character_sprite_top(OPENING_FLOOR_Y + record.offset_y, player.height)
    scene.paste(player, (player_x - record.offset_x, player_y), player)
    scene = Image.alpha_composite(scene, room.foreground)
    path = OUTPUT_DIR / "opening_scene_preview.png"
    scene.save(path)
    print(f"Wrote {path.name}: authentic opening room with the initial Prince sprite")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    room = build_opening_room()
    room.flattened().save(OUTPUT_DIR / "opening_room.png")
    make_scene_preview(room)
    make_kid_contact_sheet()


if __name__ == "__main__":
    main()
