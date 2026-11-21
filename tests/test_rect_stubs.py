"""The native probes' SectRect/UnionRect stand-ins accept dst == a source."""

import random
import struct
import unittest

try:
    from unicorn import UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, Uc
    from unicorn.m68k_const import UC_CPU_M68K_M68000, UC_M68K_REG_A7, UC_M68K_REG_D3
except ImportError:  # pragma: no cover - optional research dependency
    Uc = None


@unittest.skipIf(Uc is None, 'unicorn required')
class RectStubTests(unittest.TestCase):
    def test_sect_and_union_rect_allow_the_destination_to_alias_a_source(self):
        # QuickDraw lets dst be either source: SectRect(r, clip, clip) at
        # 3:28c2-28d8 and (fullclip, r, r) at 4:5dc6. The old stubs wrote dst
        # while still reading the aliased source, so the gate peel's clip
        # lost the cell rows.
        from tools.extract_caverns import SECT_RECT, SECT_RECT_CODE, UNION_RECT, UNION_RECT_CODE

        cpu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        cpu.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        cpu.mem_map(0, 0x100000)
        cpu.mem_write(SECT_RECT, SECT_RECT_CODE)
        cpu.mem_write(UNION_RECT, UNION_RECT_CODE)
        rng = random.Random(1)
        for case in range(600):
            first = [rng.randint(-50, 400) for _ in range(4)]
            second = [rng.randint(-50, 400) for _ in range(4)]
            source1, source2 = 0x1000, 0x1010
            destination = (0x1020, source2, source1)[case % 3]
            cpu.mem_write(source1, struct.pack('>4h', *first))
            cpu.mem_write(source2, struct.pack('>4h', *second))
            sect = case % 2 == 0
            sp = 0x8000
            cpu.mem_write(sp, struct.pack('>IIIIH', 0x5000, destination, source2, source1, 0xffff))
            cpu.reg_write(UC_M68K_REG_A7, sp)
            cpu.reg_write(UC_M68K_REG_D3, 0x1234)
            cpu.emu_start(SECT_RECT if sect else UNION_RECT, 0x5000, count=1000)
            result = list(struct.unpack('>4h', cpu.mem_read(destination, 8)))
            with self.subTest(case=case):
                if sect:
                    expected = [max(first[0], second[0]), max(first[1], second[1]),
                                min(first[2], second[2]), min(first[3], second[3])]
                    nonempty = expected[0] < expected[2] and expected[1] < expected[3]
                    self.assertEqual(result, expected if nonempty else [0, 0, 0, 0])
                    self.assertEqual(cpu.mem_read(sp + 16, 1)[0], int(nonempty))
                else:
                    self.assertEqual(result, [min(first[0], second[0]), min(first[1], second[1]),
                                              max(first[2], second[2]), max(first[3], second[3])])
                self.assertEqual(cpu.reg_read(UC_M68K_REG_A7), sp + 16)
                self.assertEqual(cpu.reg_read(UC_M68K_REG_D3), 0x1234)


if __name__ == '__main__':
    unittest.main()
