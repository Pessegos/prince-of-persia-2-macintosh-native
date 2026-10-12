"""Original CUST scenery for the desert shore and stone chamber."""

from dataclasses import dataclass
import struct

from PIL import Image

from pop2.render_opening import (
    OpeningRoom, ROOM_HEIGHT, ROOM_WIDTH, decode_ctbl, decode_shap,
)


@dataclass(frozen=True)
class BeachScene:
    room: OpeningRoom
    planks: tuple

    @classmethod
    def read(cls, resources, room_id):
        data = resources["CUST"][4000 + room_id * 25]["data"]
        if len(data) < 30:
            raise ValueError("Truncated custom beach scene")
        kind, first_shape = struct.unpack_from(">2H", data)
        count = struct.unpack_from(">H", data, 28)[0]
        if kind != 8 or len(data) != 30 + count * 32:
            raise ValueError("Unsupported custom beach scene")
        palette = decode_ctbl(resources["CTBL"][3500]["data"])
        background = Image.new("RGBA", (ROOM_WIDTH, ROOM_HEIGHT), (0, 0, 0, 255))
        planks = []
        for offset in range(30, len(data), 32):
            index, bottom, x, draw_pass, flags = struct.unpack_from(">5h", data, offset)
            if flags not in (0, 16):
                raise ValueError("Unsupported beach drawing flags")
            sprite = decode_shap(resources["SHAP"][first_shape + index]["data"], palette)
            position = x, bottom - sprite.height
            if draw_pass == 0:
                background.paste(sprite, position, sprite)
            elif draw_pass == 11:
                planks.append((sprite, position))
            else:
                raise ValueError("Unsupported beach drawing pass")
        if len(planks) != 3:
            raise ValueError("Missing beach plank animation")
        empty = Image.new("RGBA", background.size)
        masks = {row: Image.new("L", background.size) for row in range(-1, 5)}
        return cls(OpeningRoom(background, empty, masks, (), (), room_id, 1), tuple(planks))

    def draw(self, frame, frame_number):
        # Anim/DrawDsrtPlanks 18:0808-08b4: six steps, two per image.
        sprite, position = self.planks[(frame_number % 6) // 2]
        frame.paste(sprite, position, sprite)
        return frame


@dataclass(frozen=True)
class DesertScene:
    room: OpeningRoom
    records: tuple
    shapes: dict
    kind: int
    first_shape: int

    @classmethod
    def read(cls, resources, room_id):
        data = resources['CUST'][4000 + room_id * 25]['data']
        kind, first_shape = struct.unpack_from('>2H', data)
        count = struct.unpack_from('>H', data, 28)[0]
        if kind not in (6, 7, 8) or len(data) != 30 + count * 32:
            raise ValueError('Unsupported desert custom room')
        records = tuple(struct.iter_unpack('>16h', data[30:]))
        palette = decode_ctbl(resources['CTBL'][1000 if kind == 6 else 3500]['data'])
        if kind == 6:
            # Index 247 is the unpainted entrance under the movable exit.
            palette[247] = (0, 0, 0, 255)
        shapes = {first_shape + record[0]: decode_shap(
            resources['SHAP'][first_shape + record[0]]['data'], palette) for record in records}
        if kind == 6:
            for index in range(16, 25):
                shapes[first_shape + index] = decode_shap(resources['SHAP'][first_shape + index]['data'], palette)
        background = Image.new('RGBA', (ROOM_WIDTH, ROOM_HEIGHT), (0, 0, 0, 255))
        foreground = Image.new('RGBA', background.size)
        for record in records:
            index, bottom, x, draw_pass = record[:4]
            if draw_pass in (0, 1):
                sprite = shapes[first_shape + index]
                layer = foreground if draw_pass == 1 else background
                layer.paste(sprite, (x, bottom - sprite.height), sprite)
        masks = {row: foreground.getchannel('A') for row in range(-1, 5)}
        room = OpeningRoom(background, foreground, masks, (), (), room_id, 1)
        return cls(room, records, shapes, kind, first_shape)

    def draw(self, frame, frame_number, state, front=False):
        first = self.first_shape

        def shape(index, bottom, x):
            sprite = self.shapes[first + index]
            frame.paste(sprite, (x, bottom - sprite.height), sprite)

        if self.kind in (7, 8):
            if not front:
                record = self.records[(2 if self.kind == 7 else 1) + frame_number % 6 // 2]
                shape(record[0], record[1], record[2])
            return frame
        if state is None:
            return frame
        if front:
            return frame
        else:
            # DrawDsrtExit (18:074c) moves CUST X, leaving Y and the
            # foreground cliff fixed. Both moving pieces use background pass 11.
            door, symbol = self.records[2], self.records[16]
            shape(door[0], door[1], door[2] - state.gate * 3)
            shape(16 + state.symbol, symbol[1], symbol[2] - state.gate * 3)
            for index, stone in enumerate(state.stones):
                if stone.phase:
                    record = self.records[stone.phase + 2]
                    shape(record[0], 240 + record[1], (index + 2) * 51 + record[2])
                if index == state.marked_stone and stone.phase >= 9:
                    mark = self.records[17 if stone.phase == 9 else 18]
                    bottom = (mark[1] if stone.phase == 9
                              else max(-6, (12 - stone.phase) * 2 - 6))
                    shape((22 if stone.phase == 9 else 19) + state.symbol,
                          240 + bottom, (index + 2) * 51 + mark[2])
        return frame
