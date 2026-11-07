#!/usr/bin/env python3
"""Focused, bounded tests for the standalone 6502 CPU core.

These tests deliberately exercise only pure CPU/RAM behavior. They do not boot a
C64, model a raster, poll hardware registers, or run an unbounded machine loop.
"""

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import cpu6502  # noqa: E402


class StandaloneCpuTests(unittest.TestCase):
    def run_program(self, program, *, pc=0x8000, a=0, x=0, y=0,
                    flags=cpu6502.FU, max_instructions=1000):
        cpu = cpu6502.Cpu6502Emulator()
        cpu.inject_bytes(pc, program)
        cpu.exit_on_empty_stack = True
        cpu.init_cpu(pc, a, x, y, flags)

        executed = 0
        while True:
            self.assertLess(executed, max_instructions, "instruction limit exceeded")
            running = cpu.runcpu()
            executed += 1
            if not running:
                return cpu, executed

    def test_binary_adc_and_flags(self):
        cpu, executed = self.run_program([
            0xA9, 0x7F,       # LDA #$7F
            0x18,             # CLC
            0x69, 0x01,       # ADC #$01
            0x60,             # RTS
        ])
        self.assertEqual(executed, 4)
        self.assertEqual(cpu.a, 0x80)
        self.assertTrue(cpu.flags & cpu6502.FN)
        self.assertTrue(cpu.flags & cpu6502.FV)
        self.assertFalse(cpu.flags & cpu6502.FC)
        self.assertFalse(cpu.flags & cpu6502.FZ)
        self.assertEqual(cpu.cpucycles, 12)

    def test_loop_and_memory_result(self):
        cpu, executed = self.run_program([
            0xA2, 0x05,       # LDX #5
            0xA9, 0x00,       # LDA #0
            0x18,             # CLC
            0x69, 0x03,       # loop: ADC #3
            0xCA,             # DEX
            0xD0, 0xFB,       # BNE loop
            0x8D, 0x00, 0x20, # STA $2000
            0x60,             # RTS
        ])
        self.assertEqual(executed, 20)
        self.assertEqual(cpu.get_mem(0x2000), 15)
        self.assertEqual(cpu.x, 0)

    def test_jsr_rts_and_outer_empty_stack_exit(self):
        # JSR $8007; STA $2000; RTS; subroutine: LDA #$42; RTS
        cpu, executed = self.run_program([
            0x20, 0x07, 0x80,
            0x8D, 0x00, 0x20,
            0x60,
            0xA9, 0x42,
            0x60,
        ])
        self.assertEqual(executed, 5)
        self.assertEqual(cpu.a, 0x42)
        self.assertEqual(cpu.get_mem(0x2000), 0x42)
        self.assertEqual(cpu.sp, 0xFF)

    def test_memory_and_word_validation_raise_exceptions(self):
        cpu = cpu6502.Cpu6502Emulator()
        with self.assertRaises(cpu6502.Cpu6502ValueError):
            cpu.set_mem(0x2000, 256)
        with self.assertRaises(cpu6502.Cpu6502ValueError):
            cpu.set_le_word(0x2000, 65536)

    def test_unimplemented_opcode_has_standalone_exception(self):
        cpu = cpu6502.Cpu6502Emulator()
        cpu.inject_bytes(0x8000, [0x03])
        cpu.init_cpu(0x8000)
        with self.assertRaises(cpu6502.Cpu6502NotImplemented):
            cpu.runcpu()

    def test_hexdump_is_dependency_free_text(self):
        dump = cpu6502.hexdump([0x41, 0x00, 0x7F], 0x1000)
        self.assertIn("0000001000", dump)
        self.assertIn("41 00 7F", dump)
        self.assertIn("A..", dump)


if __name__ == "__main__":
    unittest.main()
