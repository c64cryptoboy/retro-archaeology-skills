"""Synthetic ownership tests for separately native-expanded operand contracts."""
import hashlib
import json
from pathlib import Path
import unittest
import basic64

ROOT=Path(__file__).resolve().parent
P=json.loads((ROOT/'basic64_profile-extended.json').read_text())


class ExtendedTests(unittest.TestCase):
    def test_base_profile_preserved(self):
        raw=(ROOT/'basic64_profile.json').read_bytes();old=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),P['baseProfileSha256'])
        self.assertEqual(len(old['opcodes']),156);self.assertEqual(len(P['opcodes']),168)
        for k,v in old['opcodes'].items():self.assertEqual(v,P['opcodes'][k])
    def test_absolute_integer_and_string_addresses(self):
        for op in (0x12,0x13,0x14,0x34,0x35,0x36):
            with self.subTest(op=op):
                raw=bytes([op,0x34,0x12,0x73]);r=basic64.decode_one(raw,0x2000,0x2000,0x2004,P)
                self.assertEqual(r['size'],3);self.assertEqual(r['operands']['value'],0x1234)
                self.assertEqual(basic64.decode_one(raw,0x2000,0x2003,0x2004,P)['mnemonic'],'END')
    def test_absolute_operands_do_not_swallow_missing_byte(self):
        for op in (0x12,0x13,0x14,0x34,0x35,0x36):
            with self.assertRaises(basic64.DecodeError):basic64.decode_one(bytes([op,0x34]),0x2000,0x2000,0x2002,P)
    def test_fixed_helpers_do_not_consume_pointer_bytes(self):
        for op in (0x11,0x1b,0x31,0x66,0xa2):
            r=basic64.decode_one(bytes([op,0x73]),0x2000,0x2000,0x2002,P)
            self.assertEqual(r['size'],1);self.assertEqual(r['operands'],{})
    def test_string_argument_slot_is_one_byte(self):
        r=basic64.decode_one(bytes([0x9a,0xfe,0x73]),0x2000,0x2000,0x2003,P)
        self.assertEqual(r['size'],2);self.assertEqual(r['operands']['value'],254)
    def test_unmodeled_bootstrap_native_transitions_remain_refused(self):
        for op in (0x98,0x9c,0x9d,0x9e):
            with self.assertRaises(basic64.DecodeError):basic64.decode_one(bytes([op,0x73]),0x2000,0x2000,0x2002,P)


if __name__=='__main__':unittest.main()
