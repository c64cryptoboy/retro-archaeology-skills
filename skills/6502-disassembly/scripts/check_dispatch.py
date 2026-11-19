"""Exercise only the authored bytes below, using shared/6502/cpu6502.py."""
import unittest

from cpu6502 import Cpu6502Emulator, MEM_USAGE_READ


# One entry ($3600); no calls, interrupts, mappings, or external writers.
CODE = bytes.fromhex("E0 03 90 03 4C 20 36 BD 40 36 85 F8 BD 50 36 85 F9 6C F8 00")
LO, HI = 0x3640, 0x3650
REGIONS = {
    LO: bytes.fromhex("74 20 74 B6"),
    HI: bytes.fromhex("37 36 37 38"),
    0x3620: b"\x60", 0x3774: b"\x60", 0x38B6: b"\x60",
}


def observe(code, x, y):
    cpu = Cpu6502Emulator()
    for addr, data in {0x3600: code, **REGIONS}.items():
        cpu.memory[addr:addr + len(data)] = data
    cpu.pc, cpu.x, cpu.y = 0x3600, x, y
    for _ in range(7):
        pc = cpu.pc
        if pc not in (0x3600, 0x3602, 0x3604, 0x3607, 0x360A, 0x360C, 0x360F, 0x3611):
            raise AssertionError(f"unexpected instruction address ${pc:04X}")
        cpu.runcpu()
        if pc in (0x3604, 0x3611):  # direct or indirect JMP, now at destination
            reads = {base + i for base in (LO, HI) for i in range(4)
                     if cpu.mem_usage[base + i] & MEM_USAGE_READ}
            return pc, cpu.pc, reads
    raise AssertionError("did not transfer within seven instructions")


class DispatchTest(unittest.TestCase):
    def test_guard_and_case_map(self):
        for x in range(256):
            with self.subTest(x=x):
                if x < 3:
                    expected = (0x3611, (0x3774, 0x3620, 0x3774)[x], {LO + x, HI + x})
                else:
                    expected = (0x3604, 0x3620, set())
                self.assertEqual(observe(CODE, x, 0), expected)

    def test_wrong_register_invalidates_bound(self):
        wrong = b"\xC0" + CODE[1:]  # CPY #3 instead of CPX #3
        self.assertEqual(observe(wrong, 3, 0), (0x3611, 0x38B6, {LO + 3, HI + 3}))
        self.assertEqual(observe(wrong, 0, 3), (0x3604, 0x3620, set()))


if __name__ == "__main__":
    unittest.main()
