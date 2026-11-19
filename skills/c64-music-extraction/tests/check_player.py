"""Run the *shipped bytes*, independently of sidfile.py. Requires py65 1.2.0.

A small NMOS 6502 call harness, not a SID, CIA, or full 6510 machine emulator.
The oracle below is only for the known original Glass Steps example.
"""
import unittest
from pathlib import Path

from py65.devices.mpu6502 import MPU

DEMO = Path(__file__).resolve().parents[1] / 'examples/glass-steps.sid'


class Bus(bytearray):
    def __setitem__(self, address, value):
        if isinstance(address, int):
            self.writes.append((address, value))
        super().__setitem__(address, value)


def trace(wire):
    # Extract the entries and data directly using published header offsets.
    word = lambda i: int.from_bytes(wire[i:i + 2], 'big')
    off, init, play = word(6), word(10), word(12)
    load = int.from_bytes(wire[off:off + 2], 'little')
    payload = wire[off + 2:]
    mem = Bus(0x10000)
    mem.writes = []
    mem[load:load + len(payload)] = payload
    m = MPU(memory=mem, pc=init)
    m.a = 0  # first subtune

    def call(entry):
        mem[1] = 0x37  # mapping contract only; py65 does not implement banks
        m.pc = entry
        previous_sp = m.sp
        m.stPushWord(0x02ff)  # RTS to $0300
        mem.writes.clear()
        for _ in range(256):
            m.step()
            if m.pc == 0x0300 and m.sp == previous_sp:
                break
        else:
            raise ValueError('routine did not return with a balanced stack')
        sid = []
        for a, v in mem.writes:
            if 0xd400 <= a <= 0xd418:
                sid.append((a, v))
            elif not (load <= a < load + len(payload) or 0x100 <= a < 0x200):
                raise ValueError('unexpected write outside the player and SID')
        return sid

    init_writes = call(init)
    frames = [call(play) for _ in range(121)]  # two loops plus next attack
    return init_writes, frames


class Performance(unittest.TestCase):
    def check_phrase(self, data):
        init, frames = trace(data)
        self.assertEqual(init, [(a, 0) for a in range(0xd418, 0xd3ff, -1)] +
                         [(0xd405, 0x08), (0xd406, 0xa3), (0xd418, 15)])
        keys = (67, 70, 65, 74)  # G4, B-flat4, F4, D5
        for i, writes in enumerate(frames):
            expected = []
            if i % 15 == 0:
                hz = 440 * 2 ** ((keys[i // 15 % 4] - 69) / 12)
                word = round(hz * 2**24 / 1022727)
                expected = [(0xd400, word & 255), (0xd401, word >> 8), (0xd404, 0x21)]
            elif i % 15 == 11:
                expected = [(0xd404, 0x20)]
            self.assertEqual(writes, expected, f'SID writes in frame {i}')

    def test_compiled_driver(self):
        self.check_phrase(DEMO.read_bytes())

    def test_missing_gate_is_detected(self):
        data = DEMO.read_bytes()
        pattern = bytes.fromhex('a9 21 8d 04 d4')
        self.assertEqual(data.count(pattern), 1)
        broken = data.replace(pattern, b'\xa9\x20' + pattern[2:])
        with self.assertRaisesRegex(AssertionError, 'SID writes in frame 0'):
            self.check_phrase(broken)


if __name__ == '__main__':
    unittest.main()
