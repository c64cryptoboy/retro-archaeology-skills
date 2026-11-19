"""Independent header layout, strict-profile rejections, and reversible I/O."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sidfile import Tune, read_psid, write_psid


class Header(unittest.TestCase):
    def test_handbuilt_wire_image(self):
        # Do NOT import the writer's struct or tables.  Two RTS at $3412/$3413.
        for prefix in (True, False):
            t = Tune(b'\x60\x60', 0x3412, 0x3412, 0x3413, 'PAL', 'cia1a',
                     '6581', 'É' * 32, 'B', '€', prefix)
            h = bytearray(124)
            h[:8] = b'PSID\x00\x02\x00\x7c'
            h[8:10] = b'\x00\x00' if prefix else b'\x34\x12'
            h[10:22] = bytes.fromhex('34 12 34 13 00 01 00 01 00 00 00 01')
            h[22:54] = b'\xc9' * 32
            h[54] = ord('B')
            h[86] = 0x80
            h[119] = 0x14  # PAL (01), 6581 (01), clean native C64 data
            wire = bytes(h) + (b'\x12\x34' if prefix else b'') + b'\x60\x60'
            with self.subTest(prefix=prefix):
                self.assertEqual(read_psid(wire), t)
                self.assertEqual(write_psid(t), wire)

    def test_packaged_tune(self):
        wire = (ROOT / 'examples/glass-steps.sid').read_bytes()
        self.assertEqual(wire[:22], bytes.fromhex('50 53 49 44 00 02 00 7c 00 00 10 00 10 03 00 01 00 01 00 00 00 00'))
        self.assertEqual(wire[118:126], bytes.fromhex('00 28 00 00 00 00 00 10'))
        t = read_psid(wire)
        self.assertEqual((t.clock, t.model, t.rate, t.name), ('NTSC', '8580', 'vbi', 'Glass Steps'))
        self.assertEqual(t.payload, wire[126:])
        self.assertEqual(write_psid(t), wire)

    def test_decline_outside_profile(self):
        wire = (ROOT / 'examples/glass-steps.sid').read_bytes()
        for why, offset, patch in [
            ('RSID', 0, b'RSID'), ('v3', 5, b'\x03'), ('v1 offset', 7, b'\x76'),
            ('implicit init', 10, bytes(2)), ('IRQ-only play', 12, bytes(2)),
            ('external play', 12, b'\xe0\x00'), ('two subtunes', 15, b'\x02'),
            ('bad start song', 17, b'\x02'), ('surplus speed bits', 21, b'\x02'),
            ('MUS', 119, b'\x29'), ('PlaySID-specific', 119, b'\x2a'),
            ('unspecified clock', 119, b'\x20'), ('either clock', 119, b'\x2c'),
            ('reserved flag', 118, b'\x80'), ('relocation range', 120, b'\x40\x01'),
            ('second SID field', 122, b'\x42'), ('third SID field', 123, b'\x44'),
            ('crosses BASIC ROM', 124, b'\xfe\x9f'), ('dirty text padding', 52, b'!'),
        ]:
            with self.subTest(why=why), self.assertRaises(ValueError):
                read_psid(wire[:offset] + patch + wire[offset + len(patch):])
        for cut in (0, 123, 124, 125, 126):
            with self.subTest(cut=cut), self.assertRaises(ValueError):
                read_psid(wire[:cut])

    def test_reject_invalid_author_input(self):
        t = read_psid((ROOT / 'examples/glass-steps.sid').read_bytes())
        for changes in ({'name': 'A' * 33}, {'released': 'bad\0tail'}, {'payload': b''},
                        {'load': -1}, {'play': 0}, {'clock': 'guess'}, {'rate': '50Hz'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                write_psid(replace(t, **changes))


if __name__ == '__main__':
    unittest.main()
