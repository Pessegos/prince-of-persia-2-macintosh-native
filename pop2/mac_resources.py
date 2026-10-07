"""Read classic Macintosh resource forks and HFS catalog extents."""

import struct


def _span(data, offset, length):
    if offset < 0 or length < 0 or offset + length > len(data):
        raise ValueError("Truncated Macintosh resource or disk image")
    return data[offset : offset + length]


def _u16(data, offset):
    return struct.unpack(">H", _span(data, offset, 2))[0]


def _u32(data, offset):
    return struct.unpack(">I", _span(data, offset, 4))[0]


def parse_resource_fork(data):
    data_offset, map_offset, data_length, map_length = struct.unpack(
        ">4I", _span(data, 0, 16)
    )
    payload = _span(data, data_offset, data_length)
    resource_map = _span(data, map_offset, map_length)
    type_base = _u16(resource_map, 24)
    name_base = _u16(resource_map, 26)
    # The count fields store count - 1; 0xffff denotes an empty list.
    type_count = (_u16(resource_map, type_base) + 1) & 0xFFFF
    resources = {}
    for index in range(type_count):
        entry = type_base + 2 + index * 8
        kind = _span(resource_map, entry, 4).decode("mac_roman")
        count = (_u16(resource_map, entry + 4) + 1) & 0xFFFF
        references = type_base + _u16(resource_map, entry + 6)
        for number in range(count):
            reference = _span(resource_map, references + number * 12, 12)
            resource_id, name_offset = struct.unpack_from(">hH", reference)
            offset = int.from_bytes(reference[5:8], "big")
            item_length = _u32(payload, offset)
            item = _span(payload, offset + 4, item_length)
            name = None
            if name_offset != 0xFFFF:
                name_start = name_base + name_offset
                name_length = _span(resource_map, name_start, 1)[0]
                name = _span(resource_map, name_start + 1, name_length).decode(
                    "mac_roman"
                )
            resources.setdefault(kind, {})[resource_id] = {
                "name": name,
                "attrs": reference[4],
                "data": item,
            }
    return resources


def _volume_header(image):
    if image[1024:1026] == b"BD":
        return 1024
    # Raw HFS images can have a wrapper before the volume's first sector.
    position = image.find(b"BD", 1024, 1024 * 1024)
    while position >= 0:
        if position + 162 <= len(image):
            block_size = _u32(image, position + 20)
            if block_size and block_size % 512 == 0:
                return position
        position = image.find(b"BD", position + 1, 1024 * 1024)
    raise ValueError("HFS volume header not found")


def _read_extents(image, allocation_start, block_size, extents, length):
    output = bytearray()
    for start, count in extents:
        if count:
            size = min(count * block_size, length - len(output))
            output.extend(_span(image, allocation_start + start * block_size, size))
        if len(output) == length:
            return bytes(output)
    raise ValueError("HFS extents overflow is not supported by this extractor")


def _extents(data, offset):
    return [
        struct.unpack(">2H", _span(data, offset + index * 4, 4)) for index in range(3)
    ]


def get_resource_fork(image, file_name, file_type="rsrc"):
    return _get_fork(image, file_name, file_type, resource=True)


def get_data_fork(image, file_name, file_type=None):
    return _get_fork(image, file_name, file_type, resource=False)


def _get_fork(image, file_name, file_type, resource):
    header = _volume_header(image)
    allocation_start = header - 1024 + _u16(image, header + 28) * 512
    block_size = _u32(image, header + 20)
    if not block_size or block_size % 512:
        raise ValueError("Invalid HFS allocation block size")
    catalog = _read_extents(
        image,
        allocation_start,
        block_size,
        _extents(image, header + 150),
        _u32(image, header + 146),
    )
    node_size = _u16(catalog, 14 + 18)
    if node_size < 256 or node_size & (node_size - 1):
        raise ValueError("Invalid HFS catalog node size")
    node_id = _u32(catalog, 14 + 10)
    visited = set()
    while node_id:
        if node_id in visited:
            raise ValueError("Cyclic HFS catalog leaf chain")
        visited.add(node_id)
        node = _span(catalog, node_id * node_size, node_size)
        next_node = _u32(node, 0)
        if node[8] == 0xFF:
            count = _u16(node, 10)
            if 14 + (count + 1) * 2 > node_size:
                raise ValueError("Invalid HFS catalog record count")
            offsets = [
                _u16(node, node_size - (index + 1) * 2) for index in range(count + 1)
            ]
            for index in range(count):
                start, end = offsets[index : index + 2]
                if not 14 <= start <= end <= node_size - (count + 1) * 2:
                    raise ValueError("Invalid HFS catalog record offsets")
                record = _span(node, start, end - start)
                name_length = _span(record, 6, 1)[0]
                name = _span(record, 7, name_length).decode("mac_roman")
                key_length = _span(record, 0, 1)[0]
                file_data = record[(key_length + 2) & ~1 :]
                if (
                    name != file_name
                    or not file_data
                    or file_data[0] != 2
                    or (file_type is not None
                        and _span(file_data, 4, 4).decode("mac_roman") != file_type)
                ):
                    continue
                return _read_extents(
                    image,
                    allocation_start,
                    block_size,
                    _extents(file_data, 86 if resource else 74),
                    _u32(file_data, 36 if resource else 26),
                )
        node_id = next_node
    raise FileNotFoundError(f"{file_name!r} ({file_type}) not found in the HFS catalog")
