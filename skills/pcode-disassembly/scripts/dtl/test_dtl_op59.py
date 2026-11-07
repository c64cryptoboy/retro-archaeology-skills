"""Native-backed OP_59 grammar controls, using synthetic bytes only."""
import json
from pathlib import Path
import unittest

from dtl import Decoder, DecodeError
from test_dtl import fixture
from test_dtl_omnibus import PROFILE, sample


class Op59Tests(unittest.TestCase):
    def test_explicit_profile_only_and_scope(self):
        default = json.loads(Path(__file__).with_name('dtl64_profile.json').read_text())
        self.assertEqual(sum(s['grammar'] is not None for s in default['opcodes'].values()), 79)
        self.assertEqual(sum(s['grammar'] is not None for s in PROFILE['opcodes'].values()), 83)
        spec = PROFILE['opcodes']['59']
        self.assertEqual(spec['handler'], 0xB6CE)
        self.assertEqual(spec['mnemonic'], 'OP_59')
        self.assertEqual(spec['grammar'], 'counted_bytes')
        self.assertEqual(spec['maxCount'], 253)
        raw, p = fixture(b'\x59\x00')
        with self.assertRaisesRegex(DecodeError, 'unknown operand grammar'):
            Decoder(raw, p).decode()

    def test_exact_width_payload_and_successor(self):
        for payload in (b'', b'V', b'FILE-NAME', bytes(range(253))):
            with self.subTest(count=len(payload)):
                raw, p = sample(b'\x59' + bytes([len(payload)]) + payload + b'\x81')
                d = Decoder(raw, p)
                r, following = d.decode()['instructions'][-2:]
                self.assertEqual(r['address'], d.main)
                self.assertEqual(r['length'], len(payload) + 2)
                self.assertEqual(r['operands']['bytes'], payload.hex())
                self.assertEqual(r['targets'], [])
                self.assertEqual(following['address'], d.main + len(payload) + 2)
                self.assertEqual(following['opcode'], 0x81)
                self.assertEqual(d.decode(), Decoder(raw, p).decode())

    def test_truncated_count_and_payload(self):
        for code in (b'\x59', b'\x59\x01', b'\x59\x03AB'):
            raw, p = sample(code)
            with self.subTest(code=code), self.assertRaisesRegex(DecodeError, 'truncated'):
                Decoder(raw, p).decode()

    def test_native_width_overflow_refused(self):
        for count in (254, 255):
            raw, p = sample(b'\x59' + bytes([count]) + bytes(count))
            with self.subTest(count=count), self.assertRaisesRegex(DecodeError, 'overflowing'):
                Decoder(raw, p).decode()

    def test_remaining_unknowns_refused(self):
        for opcode in (0x4b, 0x56, 0xff):
            raw, p = sample(bytes([opcode, 0]))
            with self.subTest(opcode=opcode), self.assertRaisesRegex(DecodeError, 'unknown operand grammar'):
                Decoder(raw, p).decode()

    def test_target_into_owned_count_or_payload_refused(self):
        for displacement in (3, 4, 5):
            raw, p = sample(bytes([0x4f, displacement, 0x59, 2, 0x81, 0x81, 0x81]))
            with self.subTest(displacement=displacement), self.assertRaisesRegex(DecodeError, 'boundary'):
                Decoder(raw, p).decode()
        raw, p = sample(bytes([0x4f, 6, 0x59, 2, 0x81, 0x81, 0x81]))
        self.assertEqual(Decoder(raw, p).decode()['instructions'][3]['targets'], [0x893])

    def test_identity_and_external_layout_gates(self):
        raw, p = sample(b'\x59\x00')
        bad = bytearray(raw)
        bad[2] ^= 1
        with self.assertRaisesRegex(DecodeError, 'bootstrap'):
            Decoder(bad, p)
        bad = bytearray(raw)
        bad[-16:-14] = b'\0\0'
        with self.assertRaisesRegex(DecodeError, 'regions'):
            Decoder(bad, p)


if __name__ == '__main__':
    unittest.main()
