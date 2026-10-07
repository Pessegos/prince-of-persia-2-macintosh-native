"""Readers for the game's Mohawk archives and uncompressed Mac sound resources."""

from dataclasses import dataclass
import io
import struct
import wave

from pop2.mac_resources import _span, _u16, _u32


def mohawk_resources(data):
    if data[:4] != b"MHWK" or data[8:12] != b"RSRC":
        raise ValueError("Not a Mohawk resource archive")
    directory = _u32(data, 20)
    file_table = directory + _u16(data, 24)
    files = []
    for index in range(_u32(data, file_table)):
        entry = file_table + 4 + index * 10
        offset = _u32(data, entry)
        size = _u16(data, entry + 4) | (_span(data, entry + 6, 1)[0] << 16)
        files.append(_span(data, offset, size))
    result = {}
    for index in range(_u16(data, directory + 2)):
        entry = directory + 4 + index * 8
        kind = _span(data, entry, 4).decode("ascii")
        table = directory + _u16(data, entry + 4)
        for number in range(_u16(data, table)):
            item = table + 2 + number * 4
            resource_id = struct.unpack(">h", _span(data, item, 2))[0]
            file_index = _u16(data, item + 2)
            if not 1 <= file_index <= len(files):
                raise ValueError("Invalid Mohawk file index")
            chunk = files[file_index - 1]
            expected = b"WAVE" if kind == "snd " else kind.encode("ascii")
            if chunk[:4] != b"MHWK" or chunk[8:12] != expected:
                raise ValueError("Invalid Mohawk resource chunk")
            payload = _span(chunk, 12, _u32(chunk, 4) - 4)
            if resource_id in result.setdefault(kind, {}):
                raise ValueError("Duplicate Mohawk resource")
            result[kind][resource_id] = payload
    return result


@dataclass(frozen=True)
class Sample:
    pcm: bytes
    rate: int
    channels: int = 1
    width: int = 1
    base_note: int = 60
    loop_start: int = 0
    loop_end: int = 0

    def wav(self, sustain=False):
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setparams((self.channels, self.width, self.rate, 0, "NONE", ""))
            writer.writeframes(self.pcm)
        data = output.getvalue()
        if sustain and self.loop_end > self.loop_start:
            # smssynth uses byte offsets for this sampler chunk.
            fields = (0, 0, round(1e9 / self.rate), self.base_note, 0, 0, 0, 1, 24,
                      0, 0, self.loop_start * self.width, self.loop_end * self.width, 0, 0)
            chunk = b"smpl" + struct.pack("<I15I", 60, *fields)
            data = data[:36] + chunk + data[36:]
            data = data[:4] + struct.pack("<I", len(data) - 8) + data[8:]
        return data


def standard_sound(data):
    kind = _u16(data, 0)
    if kind not in (1, 2):
        raise ValueError("Unsupported Mac sound format")
    count_at = 4 + _u16(data, 2) * 6 if kind == 1 else 4
    for index in range(_u16(data, count_at)):
        command = count_at + 2 + index * 8
        if _u16(data, command) & 0x7fff not in (80, 81):
            continue
        header = _u32(data, command + 4)
        length = _u32(data, header + 4)
        rate = round(_u32(data, header + 8) / 65536)
        encoding, note = _span(data, header + 20, 2)
        start, end = _u32(data, header + 12), _u32(data, header + 16)
        if encoding != 0 or not rate or not 0 <= start <= end <= length:
            raise ValueError("Unsupported Mac sample header")
        return Sample(_span(data, header + 22, length), rate, base_note=note,
                      loop_start=start, loop_end=end)
    raise ValueError("Mac sound has no sample buffer")


def digitized_sound(data):
    cursor = 0
    while cursor < len(data):
        tag = _span(data, cursor, 4)
        size = _u32(data, cursor + 4)
        body = _span(data, cursor + 8, size)
        cursor += 8 + size
        if tag != b"Data":
            continue
        rate = round(_u32(body, 0) / 65536)
        frames = _u16(body, 4)
        bits, channels = _span(body, 6, 2)
        if not rate or bits != 8 or channels not in (1, 2):
            raise ValueError("Unsupported Mohawk PCM format")
        return Sample(_span(body, 20, frames * channels), rate, channels)
    raise ValueError("Mohawk sound has no PCM data")
