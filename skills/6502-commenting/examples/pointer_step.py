#!/usr/bin/env python3
"""Check a synthetic 16-bit pointer increment using the shared CPU model."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared" / "6502"))
from cpu6502 import Cpu6502Emulator, FU  # noqa: E402

# $8000: LDA $10; CLC; ADC #$28; STA $10; BCC $800B; INC $11; RTS
PROGRAM = bytes.fromhex("a5 10 18 69 28 85 10 90 02 e6 11 60")


def main():
    for initial in (0x2000, 0x20D7, 0x20D8, 0xFFF0):
        cpu = Cpu6502Emulator()
        cpu.inject_bytes(0x8000, PROGRAM)
        cpu.set_le_word(0x10, initial)
        cpu.exit_on_empty_stack = True
        cpu.init_cpu(0x8000, 0, 0x12, 0x34, FU)  # Binary arithmetic: D=0.
        for _ in range(8):
            if not cpu.runcpu():
                break
        else:
            raise AssertionError("synthetic routine did not return within eight instructions")
        result = cpu.get_mem(0x10) | cpu.get_mem(0x11) << 8
        assert result == (initial + 40) & 0xFFFF
        assert (cpu.x, cpu.y) == (0x12, 0x34)
        print(f"${initial:04X} -> ${result:04X}")
    print("Four synthetic cases passed; this is CPU-model evidence, not hardware validation.")


if __name__ == "__main__":
    main()
