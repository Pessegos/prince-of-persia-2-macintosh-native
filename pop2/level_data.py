"""Level identity and start metadata decoded from the original LEVL resource."""

from dataclasses import dataclass
import struct

from pop2.rebirth import level_checkpoints
from pop2.terrain import LevelMap, TILE_WIDTH


@dataclass(frozen=True)
class LevelDefinition:
    number: int
    data: bytes
    kind: int
    start_room: int
    start_tile: int
    facing: int
    opponent_type: int
    checkpoints: tuple

    @classmethod
    def read(cls, prince, number):
        if type(number) is not int or number < 1:
            raise ValueError("Level number must be a positive integer")
        resource_id = 1999 + number
        try:
            data = prince["LEVL"][resource_id]["data"]
        except KeyError as error:
            raise ValueError(f"Missing LEVL:{resource_id} for level {number}") from error
        return cls.decode(number, data)

    @classmethod
    def decode(cls, number, data):
        if type(number) is not int or number < 1:
            raise ValueError("Level number must be a positive integer")
        if len(data) < 0x39ae:
            raise ValueError("Truncated LEVL resource")
        kind = struct.unpack_from(">H", data, 0x2186)[0]
        native_number = struct.unpack_from(">H", data, 0x218a)[0]
        room, tile, facing = struct.unpack_from(">3H", data, 0x2198)
        opponent_type = struct.unpack_from(">h", data, 0x21a4)[0]
        if native_number != number:
            raise ValueError(f"LEVL identifies level {native_number}, not {number}")
        if not 1 <= kind <= 6 or not 1 <= room <= 32 or not 0 <= tile < 30:
            raise ValueError("Invalid LEVL environment or start position")
        if facing not in (0, 65535):
            raise ValueError("Invalid LEVL start facing")
        if any(link > 32 for link in struct.unpack_from(">128H", data, 0x2080)):
            raise ValueError("Invalid LEVL room link")
        # SetKidDefaults 2:5d46 complements LEVL's facing word before storing it.
        return cls(number, bytes(data), kind, room - 1, tile, int(facing != 0),
                   opponent_type, level_checkpoints(data))

    @property
    def resource_id(self):
        return 1999 + self.number

    @property
    def window_escape(self):
        return self.kind == 5 and self.start_room == 3

    @property
    def start_row(self):
        # The window starts above its landing floor; OpeningEscape retains
        # the absolute initial Y while terrain tracks that lower floor.
        return 1 if self.window_escape else self.start_tile // 10

    @property
    def start_x(self):
        return self.start_tile % 10 * TILE_WIDTH + 22

    @property
    def entry_sequence(self):
        # SetKidDefaults 2:5d98-5dca. Other environments have separate branches.
        if self.window_escape:
            return 4
        if self.kind == 1:
            return 124
        raise ValueError(f"Level {self.number} entry controller is not implemented")

    def right_platform_edge(self):
        terrain = LevelMap(self.data)
        supported = []
        for column in range(self.start_tile % 10, 10):
            if terrain.tile(self.start_room, column, self.start_row).kind != 1:
                break
            supported.append(column)
        return (supported[-1] + 1) * TILE_WIDTH if supported else 10 * TILE_WIDTH - 1
