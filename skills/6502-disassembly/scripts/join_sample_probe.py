#!/usr/bin/env python3
"""Authored 6502 control-flow example, not a binary analyzer or a C64 device model.

Run with Python from anywhere in the skills distribution.  Both test programs
have the same branch target and byte layout; only the carry-set arm changes.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'shared' / '6502'))
from cpu6502 import Cpu6502Emulator, FC, FU

ENTRY, JOIN, END = 0x2000, 0x2008, 0x200A
PORT = 0x4000  # Synthetic changing input, not an assertion about the C64 map.
LOAD_PORT = bytes.fromhex('AD 00 40')


class SampleCpu(Cpu6502Emulator):
    def __init__(self):
        super().__init__()
        self.samples = []

    def get_mem(self, loc):
        if loc == PORT:
            value = 0x31 + len(self.samples)
            self.samples.append(value)
            return value
        return super().get_mem(loc)


def run(arm, carry, entry=ENTRY):
    # LDA port; BCC join; {INX:NOP:NOP or LDA port}; join: STA $20
    code = LOAD_PORT + bytes.fromhex('90 03') + arm + bytes.fromhex('85 20')
    cpu = SampleCpu()
    cpu.memory[ENTRY:END] = code
    cpu.init_cpu(entry, newa=0x99, flags=FU | (FC if carry else 0))
    for _ in range(8):
        if cpu.pc == END:
            return cpu.memory[0x20], cpu.samples, cpu.x
        if not ENTRY <= cpu.pc < END:
            break
        cpu.runcpu()
    raise RuntimeError(f'example did not reach ${END:04X}')


class SampleJoinTests(unittest.TestCase):
    def test_both_arms_preserve_one_prebranch_definition(self):
        preserve = bytes.fromhex('E8 EA EA')
        self.assertEqual(run(preserve, False), (0x31, [0x31], 0))
        self.assertEqual(run(preserve, True), (0x31, [0x31], 1))

    def test_same_address_read_again_is_not_the_same_sample(self):
        self.assertEqual(run(LOAD_PORT, False), (0x31, [0x31], 0))
        self.assertEqual(run(LOAD_PORT, True), (0x32, [0x31, 0x32], 0))

    def test_an_extra_entry_can_bypass_the_definition(self):
        self.assertEqual(run(bytes.fromhex('E8 EA EA'), False, JOIN),
                         (0x99, [], 0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
