"""Classic whole-object selection and boundaries, using the interval suite's synthetic PRG."""
import unittest

import petspeed as ps
from test_petspeed_region import PROFILE, START, fixture, synthetic_runtime


class ClassicWholeTests(unittest.TestCase):
    def whole(self, code):
        prg = fixture(bytes.fromhex(code))
        with synthetic_runtime():
            return ps.disassemble(prg, ps.select_profile(prg, PROFILE))

    def test_only_reviewed_rules_and_no_change_to_explicit_base(self):
        prg = fixture(b'\xc7')
        with synthetic_runtime():
            p = ps.select_profile(prg, PROFILE)
            self.assertEqual(set(p['opcodes']) - set(PROFILE['opcodes']), {'C7', 'EE', 'F1', 'F4'})
            self.assertEqual({k: v for k, v in p['opcodes'].items() if k not in ('C7', 'EE', 'F1', 'F4')}, PROFILE['opcodes'])
            self.assertEqual(dict(p, id=PROFILE['id'], opcodes=PROFILE['opcodes']), PROFILE)
            self.assertNotIn('C7', PROFILE['opcodes'])
            self.assertIn('unknown operand length for opcode $C7', ps.disassemble(prg, PROFILE)['error'])
            self.assertNotIn('EE', PROFILE['opcodes'])
            self.assertIn('unknown operand length for opcode $EE',
                          ps.disassemble(fixture(bytes.fromhex('ee d3 d8')), PROFILE)['error'])
            self.assertNotIn('F1', PROFILE['opcodes'])
            self.assertIn('unknown operand length for opcode $F1',
                          ps.disassemble(fixture(bytes.fromhex('f1 d3 d8')), PROFILE)['error'])
            self.assertNotIn('F4', PROFILE['opcodes'])
            self.assertIn('unknown operand length for opcode $F4',
                          ps.disassemble(fixture(bytes.fromhex('f4 11 22')), PROFILE)['error'])
            with self.assertRaisesRegex(ps.DecodeError, 'requires the reviewed base'):
                ps.select_profile(prg, dict(PROFILE, variableStride=7))

    def test_target_is_opcode_not_c7_valued_operand(self):
        r = self.whole('d1 05 30 52 c7 c7')
        self.assertTrue(r['completeCodeDecode'], r['error'])
        jump, literal, char = r['instructions']
        self.assertEqual((jump['operands']['target'], literal['operands']['value']), (START + 5, 199))
        self.assertEqual((char['address'], char['bytes'], char['size'], char['mnemonic'],
                          char['control'], char['operands']),
                         (START + 5, 'c7', 1, 'CHR_STRING', 'fallthrough', {}))
        bad = self.whole('d1 04 30 52 c7 c7')
        self.assertFalse(bad['completeCodeDecode'])
        self.assertIn('$3004 is not a decoded instruction boundary', bad['error'])

    def test_next_unknown_or_truncated_instruction_still_stops_partition(self):
        for code, error in [('52 41 c7 f4 d3', 'truncated instruction'),
                            ('52 41 c7 f1 d3', 'truncated instruction'),
                            ('52 41 c7 ee d3', 'truncated instruction'),
                            ('52 41 c7 48 d3', 'unknown operand length for opcode $48'),
                            ('52 41 c7 52', 'truncated instruction')]:
            with self.subTest(code=code):
                result = self.whole(code)
                self.assertFalse(result['completeCodeDecode'])
                self.assertIn(error, result['error'])
                self.assertEqual(result['decodedBytes'], 3)
                self.assertEqual([r['address'] for r in result['instructions']], [START, START + 2])

    def test_word_load_uses_address_not_target_or_immediate(self):
        r = self.whole('d1 06 30 f1 d3 80 d8')
        self.assertTrue(r['completeCodeDecode'], r['error'])
        _, load, successor = r['instructions']
        self.assertEqual((load['bytes'], load['mnemonic'], load['size'], load['operands'],
                          load['control'], successor['address']),
                         ('f1 d3 80', 'LOAD_INTEGER_WORD_ABS', 3, {'value': 0x80d3},
                          'fallthrough', START + 6))
        self.assertIn('from two bytes at $80D3', load['comment'])
        for dest in (4, 5):
            bad = self.whole(f'd1 {dest:02x} 30 f1 d3 80 d8')
            self.assertIn('not a decoded instruction boundary', bad['error'])

    def test_arg_word_load_owns_both_address_bytes(self):
        result = self.whole('d1 06 30 ee f1 d8 d8')
        self.assertTrue(result['completeCodeDecode'], result['error'])
        _, load, successor = result['instructions']
        self.assertEqual((load['address'], load['mnemonic'], load['bytes'], load['size'],
                          load['operands'], load['control'], successor['address']),
                         (START + 3, 'LOAD_INTEGER_WORD_ARG_ABS', 'ee f1 d8', 3,
                          {'value': 0xd8f1}, 'fallthrough', START + 6))
        self.assertIn('integer ARG from two bytes at $D8F1', load['comment'])
        for dest in (4, 5):
            bad = self.whole(f'd1 {dest:02x} 30 ee f1 d8 d8')
            self.assertFalse(bad['completeCodeDecode'])
            self.assertIn('not a decoded instruction boundary', bad['error'])

    def test_word_store_has_data_address_not_control_target(self):
        result = self.whole('d1 06 30 f4 d3 f1 d8')
        self.assertTrue(result['completeCodeDecode'], result['error'])
        _, store, successor = result['instructions']
        self.assertEqual((store['address'], store['bytes'], store['size'], store['mnemonic'],
                          store['operands'], store['control'], successor['address']),
                         (START + 3, 'f4 d3 f1', 3, 'STORE_NUMERIC_WORD_ABS',
                          {'value': 0xf1d3}, 'fallthrough', START + 6))
        self.assertIn('$F1D3', store['comment'])
        for dest in (4, 5):
            bad = self.whole(f'd1 {dest:02x} 30 f4 d3 f1 d8')
            self.assertFalse(bad['completeCodeDecode'])
            self.assertIn('not a decoded instruction boundary', bad['error'])

    def test_whole_selection_cannot_override_stub_hash_or_extent(self):
        original = fixture(b'\xc7')
        for address, value, error in [(0x081A, 0x67, 'entry stub'),
                                      (0x1E9E, 0xEA, 'runtime fingerprint'),
                                      (PROFILE['headerWords']['topCode'] + 1, 0x40, 'region ordering')]:
            bad = bytearray(original)
            bad[2 + address - 0x0801] = value
            with self.subTest(address=address), synthetic_runtime(), self.assertRaisesRegex(ps.DecodeError, error):
                ps.disassemble(bytes(bad), ps.select_profile(bytes(bad), PROFILE))
