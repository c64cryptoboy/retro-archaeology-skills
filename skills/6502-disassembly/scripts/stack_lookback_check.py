"""Run only the seven authored instructions below.  Supply the public shared/6502 directory on PYTHONPATH."""

from cpu6502 import Cpu6502Emulator


class DataReads(Cpu6502Emulator):
    def __init__(self):
        super().__init__()
        self.data_reads = []

    def get_mem(self, loc):
        if loc < 0x0300:  # All test data is here; code and its operands are at $4000.
            self.data_reads.append(loc)
        return super().get_mem(loc)


def observe(s):
    cpu = DataReads()
    code = bytes.fromhex("48 A9 C7 48 BA BD 02 01 68 68")
    cpu.inject_bytes(0x4000, code)
    cpu.inject_bytes(0x0200, [0xD0, 0xD1])
    cpu.init_cpu(0x4000, newa=0x35)
    cpu.sp = s
    values = []
    for step in range(7):
        cpu.runcpu()
        if step >= 4:  # indexed load, first pull, second pull
            values.append(cpu.a)
    writes = [(addr, new) for addr, old, new in cpu.write_trace]
    return writes, cpu.x, cpu.data_reads, values, cpu.sp, cpu.pc


def main():
    # Literal hand ledger, independent of CPU helper formulas.
    for s, first, second, x, indexed, peek in (
        (0x00, 0x0100, 0x01FF, 0xFE, 0x0200, 0xD0),
        (0x01, 0x0101, 0x0100, 0xFF, 0x0201, 0xD1),
        (0x02, 0x0102, 0x0101, 0x00, 0x0102, 0x35),
    ):
        expected = ([(first, 0x35), (second, 0xC7)], x, [indexed, second, first],
                    [peek, 0xC7, 0x35], s, 0x400A)
        actual = observe(s)
        if actual != expected:
            raise SystemExit(f"initial S=${s:02X}: expected {expected}, got {actual}")
        print(f"S=${s:02X}: pushes ${first:04X},${second:04X}; "
              f"X=${x:02X}; indexed ${indexed:04X} -> ${peek:02X}; pulls $C7,$35")


if __name__ == "__main__":
    main()
