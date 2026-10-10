"""The custom beach scene at the level-two entrance."""

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
        return cls(OpeningRoom(background, empty, masks, (), (), room_id), tuple(planks))

    def draw(self, frame, frame_number):
        # Anim/DrawDsrtPlanks 18:0808-08b4: six steps, two per image.
        sprite, position = self.planks[(frame_number % 6) // 2]
        frame.paste(sprite, position, sprite)
        return frame
