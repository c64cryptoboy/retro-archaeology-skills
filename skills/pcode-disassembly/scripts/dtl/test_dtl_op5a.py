"""Additive OP_5A grammar tests. Synthetic bytes, not compiler/runtime evidence."""
import copy
import json
from pathlib import Path
import unittest
from dtl import Decoder, DecodeError
from test_dtl import fixture

HERE = Path(__file__).resolve().parent
PROFILE = json.loads((HERE / 'dtl64_profile-omnibus.json').read_text())
DEFAULT = json.loads((HERE / 'dtl64_profile.json').read_text())
# Explicit missing-grammar negative, not a replacement for the private frozen baseline.
NO_OP5A = copy.deepcopy(PROFILE)
NO_OP5A['opcodes']['5A'] = copy.deepcopy(DEFAULT['opcodes']['5A'])


def sample(code, init=None):
    raw, p = fixture(code, **({} if init is None else {'init': init}))
    p['opcodes'] = copy.deepcopy(PROFILE['opcodes'])
    return raw, p


class Op5aTests(unittest.TestCase):
    def test_explicit_profile_scope(self):
        self.assertEqual(sum(s['grammar'] is not None for s in DEFAULT['opcodes'].values()), 79)
        self.assertIsNone(DEFAULT['opcodes']['5A']['grammar'])
        self.assertEqual(PROFILE['opcodes']['5A']['grammar'], 'counted_bytes')
        self.assertEqual(PROFILE['opcodes']['5A']['confidence'], 'confirmed-structure')
        self.assertEqual(sum(s['grammar'] is not None for s in PROFILE['opcodes'].values()), 83)
        self.assertEqual(PROFILE['opcodes']['5A']['handler'], 0xB6CE)
        self.assertEqual(PROFILE['opcodes']['5A']['mnemonic'], 'OP_5A')
        self.assertEqual(PROFILE['opcodes']['5A']['maxCount'], 253)

    def test_every_nonwrapping_count_ownership_and_successor(self):
        for count in range(254):
            payload = bytes(range(count))
            raw, p = sample(b'\x5a' + bytes([count]) + payload + b'\x81')
            d = Decoder(raw, p)
            with self.subTest(count=count):
                r, following = d.decode()['instructions'][-2:]
                self.assertEqual(r['address'], d.main)
                self.assertEqual(r['bytes'], (b'\x5a' + bytes([count]) + payload).hex())
                self.assertEqual(r['length'], count + 2)
                self.assertEqual(r['operands']['count'], count)
                self.assertEqual(r['operands']['bytes'], payload.hex())
                self.assertEqual(r['targets'], [])
                self.assertEqual(following['address'], d.main + count + 2)
                self.assertEqual(following['opcode'], 0x81)

    def test_truncated_count_or_payload(self):
        for code in (b'\x5a', b'\x5a\x01', b'\x5a\x03AB'):
            raw, p = sample(code)
            with self.subTest(code=code), self.assertRaisesRegex(DecodeError, 'truncated'):
                Decoder(raw, p).decode()

    def test_wrapping_counts_refused_even_with_complete_payload(self):
        for count in (254, 255):
            raw, p = sample(b'\x5a' + bytes([count]) + bytes(count))
            with self.subTest(count=count), self.assertRaisesRegex(DecodeError, 'overflowing'):
                Decoder(raw, p).decode()

    def test_default_and_missing_grammar_refuse(self):
        for profile in (DEFAULT, NO_OP5A):
            raw, p = fixture(b'\x5a\x00')
            p['opcodes'] = copy.deepcopy(profile['opcodes'])
            with self.assertRaisesRegex(DecodeError, 'unknown operand grammar'):
                Decoder(raw, p).decode()

    def test_remaining_unknowns_refused(self):
        for op in (0x4b, 0x56, 0xff):
            raw, p = sample(bytes([op, 0]))
            with self.subTest(op=op), self.assertRaisesRegex(DecodeError, 'unknown operand grammar'):
                Decoder(raw, p).decode()

    def test_interior_targets_refuse_and_normal_successor_accepts(self):
        for offset in (3, 4, 5):
            raw, p = sample(bytes([0x4f, offset, 0x5a, 2, 0x81, 0x81, 0x81]))
            with self.subTest(offset=offset), self.assertRaisesRegex(DecodeError, 'boundary'):
                Decoder(raw, p).decode()
        raw, p = sample(bytes([0x4f, 6, 0x5a, 2, 0x81, 0x81, 0x81]))
        d = Decoder(raw, p)
        self.assertEqual(d.decode()['instructions'][3]['targets'], [d.main + 6])

    def test_identity_layout_and_region_boundary_gates(self):
        raw, p = sample(b'\x5a\x00')
        bad = bytearray(raw); bad[2] ^= 1
        with self.assertRaisesRegex(DecodeError, 'bootstrap'):
            Decoder(bad, p)
        bad = bytearray(raw); bad[-16:-14] = b'\0\0'
        with self.assertRaisesRegex(DecodeError, 'regions'):
            Decoder(bad, p)
        raw, p = sample(b'\x81', init=b'\x5a\x02X')
        with self.assertRaisesRegex(DecodeError, 'truncated'):
            Decoder(raw, p).decode()

    def test_byte_identical_deterministic_replay(self):
        raw, p = sample(b'\x5a\x06\0\xff:ABC\x81')
        a = json.dumps(Decoder(raw, p).decode(), sort_keys=True)
        b = json.dumps(Decoder(raw, p).decode(), sort_keys=True)
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
