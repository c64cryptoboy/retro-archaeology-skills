"""Synthetic profile/grammar tests; no runtime, title, ROM, or fixture assets.

Most grammar tests call decode_one on synthetic p-code.  Full-pipeline tests use
an explicitly test-only all-zero runtime fingerprint, never an admission bypass
in build_profile.  Real-image/native comparisons remain private evidence.
"""
import copy
import json
from pathlib import Path
import unittest

import petspeed as ps
import variant_2267 as variant


BASE = json.loads(Path(__file__).with_name('petspeed_profile.json').read_text())
PROFILE = variant.build_profile(BASE)
START = 0x281B


def synthetic_prg(code):
    base = 0x0801
    raw = bytearray(START + len(code) - base)
    raw[0x819-base:0x81c-base] = bytes.fromhex(PROFILE['entryBytes'])
    for key, value in dict(data=0x2810, arrays=0x2811, initialization=0x2812,
                           codeCursor=START-1, topCode=START+len(code)).items():
        at = PROFILE['headerWords'][key] - base
        raw[at:at+2] = value.to_bytes(2, 'little')
    raw[START-base:] = code
    synthetic_profile = copy.deepcopy(PROFILE)
    synthetic_profile['runtimeSha256'] = ps.sha(raw[0x826-base:0x2800-base])
    return base.to_bytes(2, 'little') + raw, synthetic_profile


class ProfileTests(unittest.TestCase):
    def one(self, code):
        return ps.decode_one(code, START, START, START+len(code), PROFILE)

    def decode(self, code):
        prg, profile = synthetic_prg(code)
        return ps.disassemble(prg, profile)

    def test_exact_metadata_and_pure_independent_build(self):
        original = copy.deepcopy(BASE)
        p = variant.build_profile(BASE)
        self.assertEqual(BASE, original)
        self.assertEqual(p['runtimeSha256'], variant.RUNTIME_SHA256)
        self.assertEqual(p['entryBytes'], '4c6722')
        for key in ('headerWords', 'runtimeStart', 'runtimeEnd', 'loadAddress'):
            self.assertEqual(p[key], BASE[key])
        p['opcodes']['80']['selectors']['0D']['comment'] = 'changed'
        p['families'][0]['comment'] = 'changed'
        p['modifierTables']['input-store']['41']['commentSuffix'] = 'changed'
        self.assertEqual(BASE, original)
        self.assertNotEqual(variant.build_profile(BASE), p)

    def test_other_base_and_unreviewed_expansion_refused(self):
        for field, value in [('runtimeSha256', '0'*64), ('entryBytes', '4c6722'),
                             ('schema', 'other'), ('variableStride', 7)]:
            p = copy.deepcopy(BASE)
            p[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                variant.build_profile(p)
        for section, key, value in [('headerWords', 'data', 0x081D),
                                    ('opcodes', 'FD', dict(operand='u16le'))]:
            p = copy.deepcopy(BASE)
            p[section][key] = value
            with self.subTest(section=section), self.assertRaises(ValueError):
                variant.build_profile(p)
        p = copy.deepcopy(BASE)
        p['modifierTables']['string-input-store']['42'] = dict(mnemonicSuffix='_WRONG')
        with self.assertRaises(ValueError):
            variant.build_profile(p)
        p = copy.deepcopy(BASE)
        p['families'][0]['last'] = 30
        with self.assertRaises(ValueError):
            variant.build_profile(p)
        for selector in (False, True):
            p = copy.deepcopy(BASE)
            table = p['opcodes']['80']['selectors'] if selector else p['opcodes']
            table['EE' if selector else 'AD'] = dict(operand='none')
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                variant.build_profile(p)

    def test_extended_stride_seven_unsigned_all_indices(self):
        for opcode in (0xFD, 0xFE, 0xFF):
            for index in range(256):
                with self.subTest(opcode=opcode, index=index):
                    item = self.one(bytes((opcode, index)))
                    self.assertEqual(item['size'], 2)
                    self.assertEqual(item['operands'], dict(value=index, slot=32+index,
                                                           variable=0x2900+7*index))
                    self.assertNotIn('target', item['operands'])
            with self.assertRaises(ps.DecodeError):
                self.one(bytes((opcode,)))
        compact = self.decode(bytes((0x00, 0x1F, 0x20, 0x3F, 0x60, 0x7F)))
        self.assertTrue(compact['completeCodeDecode'])
        self.assertEqual([i['operands']['variable'] for i in compact['instructions']],
                         [0x2800, 0x28F8]*3)

    def test_direct_addresses_are_little_endian_data_not_targets(self):
        for opcode in (0xED, 0xEE, 0xEF, 0xF0, 0xF1, 0xF2, 0xF3, 0xF4):
            with self.subTest(opcode=opcode):
                code = bytes((opcode, 0x34, 0x12))
                item = self.one(code)
                self.assertEqual(item['size'], 3)
                self.assertEqual(item['operands'], dict(value=0x1234))
                self.assertEqual(item['control'], 'fallthrough')
                for size in (1, 2):
                    with self.assertRaises(ps.DecodeError):
                        self.one(code[:size])
                self.assertTrue(self.decode(code+b'\xd3')['completeCodeDecode'])

    def test_new_no_payload_and_secondary_forms(self):
        expected = {0x86: 'POWER_REVERSED', 0xA1: 'ARRAY_PAIR_LOAD_FAC',
                    0xA8: 'ARRAY_PAIR_DEST', 0xAF: 'OPEN_SECONDARY', 0xC7: 'CHR_STRING'}
        for opcode, mnemonic in expected.items():
            with self.subTest(opcode=opcode):
                item = self.one(bytes((opcode,)))
                self.assertEqual((item['size'], item['mnemonic']), (1, mnemonic))
        for selector, mnemonic in [(0x0B, 'TIME_ARG'),
                                   (0x0D, 'TIME_STRING_ARG_CLOBBER_FAC_TYPE')]:
            item = self.one(bytes((0x80, selector)))
            self.assertEqual((item['size'], item['mnemonic']), (2, mnemonic))
        with self.assertRaises(ps.DecodeError):
            self.one(b'\x80')

    def test_contextual_modifiers_numeric_and_string_split(self):
        for opcode in (0xD6, 0xD9, 0xDA, 0xDB):
            for modifier in (0x41, 0x42):
                item = self.one(bytes((opcode, modifier)))
                self.assertEqual(item['size'], 2)
                self.assertIn('_STORE_', item['mnemonic'])
        for opcode in (0xD7, 0xDC):
            self.assertEqual(self.one(bytes((opcode, 0x41)))['size'], 2)
            self.assertEqual(self.one(bytes((opcode, 0x42)))['size'], 1)
            self.assertFalse(self.decode(bytes((opcode, 0x42, 0xD3)))['completeCodeDecode'])
        for opcode in (0x41, 0x42):
            with self.assertRaises(ps.DecodeError):
                self.one(bytes((opcode,)))
        for opcode in (0xD6, 0xD7):
            item = self.one(bytes((opcode, 0x41)))
            self.assertIn('EMPTY_SKIP', item['mnemonic'])
            self.assertIn('parsed-field path', item['comment'])
            # Empty-input runtime skip is not a guessed linear inline payload.
            self.assertEqual(self.one(bytes((opcode, 0xFF, 0xFF)))['size'], 1)

    def test_explicit_float_mantissa_not_restored_hidden_bit(self):
        for opcode in (0x43, 0x4C):
            for payload, expected in [(bytes((129, 0, 0, 0, 1, 0)), (1, 2**31)),
                                      (bytes((129, 128, 0, 0, 0, 128)), (-1, 1)),
                                      (bytes((0, 255, 255, 255, 255, 0)), (0, 1))]:
                item = self.one(bytes((opcode,))+payload)
                self.assertEqual(item['size'], 7)
                self.assertEqual((item['operands']['numerator'], item['operands']['denominator']), expected)

    def test_semantic_qualifications_not_false_typed_shortcuts(self):
        self.assertIn('$11 unchanged', self.one(b'\xef\x34\x12')['comment'])
        self.assertIn('$10 unchanged', self.one(b'\xf4\x34\x12')['comment'])
        self.assertIn('zero exponent loads following integer', self.one(b'\xed\x34\x12')['comment'])
        self.assertIn('FAC type $10 := FF', self.one(b'\x80\x0d')['comment'])
        self.assertIn('scaling carry', self.one(b'\xa1')['comment'])
        self.assertIn('$11 := 1', self.one(b'\xab')['comment'])
        self.assertNotIn('$B6', self.one(b'\xab')['comment'])

    def test_unknowns_still_refuse_without_resynchronization(self):
        for code in (b'\xad\xd3', b'\xb2\xd3', b'\xf6\xd3',
                     b'\x80\x00\xd3', b'\x80\x04\xd3', b'\x80\x07\xd3'):
            r = self.decode(code)
            self.assertFalse(r['completeCodeDecode'])
            self.assertEqual(r['decodedBytes'], 0)
            self.assertFalse(r['instructions'])
            self.assertIn('unknown', r['error'])

    def test_normal_disassemble_pipeline_and_strict_identity_gates(self):
        code = bytes.fromhex('a1 a8 ed 34 12 ee 34 12 ef 34 12 f1 34 12 f2 34 12 '
                             'f4 34 12 fd ff fe 80 ff 00 80 0b 80 0d d3')
        prg, synthetic_profile = synthetic_prg(code)
        result = ps.disassemble(prg, synthetic_profile)
        self.assertTrue(result['completeCodeDecode'], result['error'])
        self.assertEqual(result['decodedBytes'], len(code))
        self.assertEqual(sum(i['size'] for i in result['instructions']), len(code))
        self.assertEqual(result['instructions'][-1]['address'], START+len(code)-1)
        # Real built profile must reject our asset-free, all-zero runtime.
        with self.assertRaises(ps.DecodeError):
            ps.disassemble(prg, PROFILE)
        for address in (0x819, 0x926):
            bad = bytearray(prg)
            bad[address-0x801+2] ^= 1
            with self.subTest(address=address), self.assertRaises(ps.DecodeError):
                ps.disassemble(bytes(bad), synthetic_profile)
        for bad in (prg[:-1], prg[:2]+prg[3:]):
            with self.assertRaises(ps.DecodeError):
                ps.disassemble(bad, synthetic_profile)
        self.assertFalse(self.decode(b'\xd1\xff\xff')['completeCodeDecode'])
        self.assertFalse(self.decode(b'\xd1\x1c\x28')['completeCodeDecode'])


if __name__ == '__main__':
    unittest.main()
