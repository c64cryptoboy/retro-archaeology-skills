"""Execute the shipped Two Hops bytes.  Requires py65; no assembler at test time."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from py65.devices.mpu6502 import MPU
from sidfile import read_psid, write_psid

WIRE = Path(__file__).with_name('two-hops.sid').read_bytes()
DIRTY = (0x24, 0x74)


class Bus(bytearray):
    def __setitem__(self, address, value):
        if isinstance(address, int):
            self.writes.append((address, value))
        super().__setitem__(address, value)


class Packed(unittest.TestCase):
    def test_declarations(self):
        self.assertEqual(WIRE[120:124], bytes.fromhex('25 4f 00 00'))
        tune = read_psid(WIRE, dirty_pages=DIRTY)
        self.assertEqual(write_psid(tune, dirty_pages=DIRTY), WIRE)
        with self.assertRaises(ValueError):  # clean-only reader remains the default
            read_psid(WIRE)
        for fields in ('24 50', '25 50', '10 01', '25 01', '00 00', 'ff 00'):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                read_psid(WIRE[:120] + bytes.fromhex(fields) + WIRE[122:], dirty_pages=DIRTY)

    def check_performance(self, wire):
        # Independent of the candidate reader: explicit load, no PRG prefix.
        self.assertEqual(wire[:22], bytes.fromhex(
            '50 53 49 44 00 02 00 7c 10 00 10 00 10 03 00 01 00 01 00 00 00 00'))
        self.assertEqual(wire[118:124], bytes.fromhex('00 28 25 4f 00 00'))
        raw = wire[124:]
        self.assertEqual(len(raw), 31 + 73 + 4)
        mem = Bus(b'\xcc' * 65536)
        mem.writes = []
        mem[1] = 0x37  # mapping contract, not emulated 6510 banking
        mem[0x1000:0x106c] = raw
        cpu = MPU(memory=mem)
        host = wire[120] << 8  # put the actual JSR in the declared free run

        def call(entry):
            mem[host:host + 3] = bytes((0x20, entry & 255, entry >> 8))
            cpu.pc = host
            cpu.sp = 0xff
            mem.writes.clear()
            for _ in range(1024):
                cpu.step()
                if cpu.pc == host + 3:
                    break
            else:
                self.fail('entry did not return to host')
            self.assertEqual(cpu.sp, 0xff)
            stack = [(a, v) for a, v in mem.writes if a >> 8 == 1]
            self.assertEqual(stack, [(0x1ff, host >> 8), (0x1fe, 2)])
            sid = [(a, v) for a, v in mem.writes if 0xd400 <= a <= 0xd418]
            ram = [(a, v) for a, v in mem.writes if a >> 8 != 1 and not 0xd400 <= a <= 0xd418]
            return ram, sid

        moves = [(0x2400 + i, raw[31 + i]) for i in reversed(range(73))]
        moves += [(0x7400 + i, raw[104 + i]) for i in reversed(range(4))]
        init_sid = [(a, 0) for a in reversed(range(0xd400, 0xd419))]
        init_sid += [(0xd406, 0x92), (0xd418, 15)]
        for poison in (0xcc, 0x55):
            # No image reload.  Second init must repair both damaged copies.
            mem[0x2400:0x2449] = bytes([poison]) * 73
            mem[0x7400:0x7404] = bytes([poison]) * 4
            cpu.a = 0
            self.assertEqual(call(0x1000), (moves + [(0x2448, 0)], init_sid))
            for field in range(65):  # two full loops and the next attack
                ram, sid = call(0x1003)
                self.assertEqual(ram, [(0x2448, (field + 1) % 32)])
                expected = []
                if field % 8 == 0:
                    expected = [(0xd401, (14, 17, 21, 16)[field // 8 % 4]), (0xd404, 0x11)]
                elif field % 8 == 6:
                    expected = [(0xd404, 0x10)]
                self.assertEqual(sid, expected, f'SID writes in field {field}')

    def test_performance(self):
        self.check_performance(WIRE)

    def test_changed_pitch(self):
        with self.assertRaisesRegex(AssertionError, 'SID writes in field 24'):
            self.check_performance(WIRE[:-1] + b'\x11')


if __name__ == '__main__':
    unittest.main()
