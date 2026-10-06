from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class FrameRecord:
    action: int
    shape_index: int
    afrm_index: int
    offset_x: int
    offset_y: int
    aux: int


def parse_frame_records(data):
    if len(data) % 10:
        raise ValueError("FRAM resource length is not a multiple of 10 bytes")
    return tuple(
        FrameRecord(i, *struct.unpack_from(">5h", data, i * 10))
        for i in range(len(data) // 10)
    )


def shape_id_for_action(records, first_shape_id, action):
    if not 0 <= action < len(records):
        raise IndexError(f"FRAM action {action} is out of range")
    shape_index = records[action].shape_index
    return None if shape_index < 0 else first_shape_id + shape_index


def parse_aframe_records(data):
    if len(data) % 8:
        raise ValueError("AFRM resource length is not a multiple of 8 bytes")
    return tuple(
        struct.unpack_from(">4h", data, i)
        for i in range(0, len(data), 8)
    )


def sequence_words(data):
    if len(data) % 2:
        raise ValueError("SEQS resource length is not a multiple of 2 bytes")
    return tuple(struct.unpack_from(">h", data, i)[0] for i in range(0, len(data), 2))
