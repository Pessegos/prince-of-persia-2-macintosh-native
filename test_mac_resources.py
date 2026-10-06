import struct
import unittest

from mac_resources import get_resource_fork, parse_resource_fork


def resource_fork():
    payload = struct.pack(">I", 3) + b"abc"
    resource_map = bytearray(55)
    struct.pack_into(">2H", resource_map, 24, 28, 50)
    struct.pack_into(">H4s2H", resource_map, 28, 0, b"TEST", 0, 10)
    struct.pack_into(">hHB3sI", resource_map, 38, -7, 0, 32, bytes(3), 0)
    resource_map[50:] = b"\x04caf\x8e"
    header = struct.pack(">4I", 16, 16 + len(payload), len(payload), len(resource_map))
    return header + payload + resource_map


def hfs_image(wrapper=0):
    image = bytearray(wrapper + 4096)
    header = wrapper + 1024
    image[header : header + 2] = b"BD"
    struct.pack_into(">I", image, header + 20, 512)
    struct.pack_into(">H", image, header + 28, 4)
    struct.pack_into(">I", image, header + 146, 1024)
    struct.pack_into(">2H", image, header + 150, 0, 2)
    catalog = wrapper + 2048
    struct.pack_into(">I", image, catalog + 24, 1)
    struct.pack_into(">H", image, catalog + 32, 512)
    leaf = catalog + 512
    image[leaf + 8] = 0xFF
    struct.pack_into(">H", image, leaf + 10, 1)
    name = b"Prince.rsrc"
    key = bytes((6 + len(name), 0)) + struct.pack(">I", 2) + bytes((len(name),)) + name
    if len(key) % 2:
        key += b"\0"
    file_record = bytearray(102)
    file_record[0] = 2
    file_record[4:8] = b"rsrc"
    struct.pack_into(">I", file_record, 36, 3)
    struct.pack_into(">2H", file_record, 86, 2, 1)
    record = key + file_record
    image[leaf + 14 : leaf + 14 + len(record)] = record
    struct.pack_into(">H", image, leaf + 510, 14)
    struct.pack_into(">H", image, leaf + 508, 14 + len(record))
    image[wrapper + 3072 : wrapper + 3075] = b"abc"
    return image


class ResourceForkTests(unittest.TestCase):
    def test_signed_id_mac_roman_name_attributes_and_data(self):
        resources = parse_resource_fork(resource_fork())
        self.assertEqual(
            resources,
            {"TEST": {-7: {"name": "caf\u00e9", "attrs": 32, "data": b"abc"}}},
        )

    def test_unnamed_resource(self):
        data = bytearray(resource_fork())
        map_offset = struct.unpack_from(">I", data, 4)[0]
        struct.pack_into(">H", data, map_offset + 40, 0xFFFF)
        self.assertIsNone(parse_resource_fork(data)["TEST"][-7]["name"])

    def test_empty_type_list(self):
        data = bytearray(resource_fork())
        map_offset = struct.unpack_from(">I", data, 4)[0]
        struct.pack_into(">H", data, map_offset + 28, 0xFFFF)
        self.assertEqual(parse_resource_fork(data), {})

    def test_truncated_header_map_and_item_are_rejected(self):
        original = resource_fork()
        for data in (b"", original[:15], original[:-1]):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                parse_resource_fork(data)
        data = bytearray(original)
        struct.pack_into(">I", data, 16, 4)
        with self.assertRaises(ValueError):
            parse_resource_fork(data)

    def test_names_cannot_read_beyond_the_resource_map(self):
        data = bytearray(resource_fork())
        map_offset = struct.unpack_from(">I", data, 4)[0]
        data[map_offset + 50] = 255
        with self.assertRaises(ValueError):
            parse_resource_fork(data)


class HfsExtractionTests(unittest.TestCase):
    def test_raw_and_wrapped_images_extract_the_same_resource_bytes(self):
        for wrapper in (0, 84, 512):
            with self.subTest(wrapper=wrapper):
                self.assertEqual(
                    get_resource_fork(hfs_image(wrapper), "Prince.rsrc"), b"abc"
                )

    def test_wrong_name_and_wrong_finder_type_are_not_accepted(self):
        for name, kind in (("missing", "rsrc"), ("Prince.rsrc", "APPL")):
            with (
                self.subTest(name=name, kind=kind),
                self.assertRaises(FileNotFoundError),
            ):
                get_resource_fork(hfs_image(), name, kind)

    def test_cyclic_catalog_is_rejected(self):
        image = hfs_image()
        struct.pack_into(">I", image, 2560, 1)
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            get_resource_fork(image, "missing")

    def test_unavailable_resource_extents_are_not_silently_truncated(self):
        image = hfs_image()
        record = 2560 + 14 + 18
        struct.pack_into(">I", image, record + 36, 513)
        with self.assertRaisesRegex(ValueError, "overflow"):
            get_resource_fork(image, "Prince.rsrc")

    def test_missing_volume_header_and_truncated_catalog_are_rejected(self):
        for image in (bytes(4096), hfs_image()[:2500]):
            with self.subTest(size=len(image)), self.assertRaises(ValueError):
                get_resource_fork(image, "Prince.rsrc")


if __name__ == "__main__":
    unittest.main()
