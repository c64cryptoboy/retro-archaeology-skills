"""Synthetic admission/grammar tests; no runtime or private specimen bundled.

Positive selection tests mock only the digest of the all-zero runtime.  Real
hashing remains active for the base-profile pin and all other byte sequences.
These tests establish static decoding/refusal, not native execution.
"""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import petspeed as ps
from test_petspeed_region import fixture, RUNTIME, START
import variant_02fff9b6 as variant
import variant_2267


BASE = json.loads(Path(__file__).with_name('petspeed_profile.json').read_text())
PROFILE = variant.build_profile(BASE)
ADDED = {'86', 'AF', 'C7', 'F2'}


class VariantTests(unittest.TestCase):
    def one(self, data, profile=PROFILE):
        return ps.decode_one(data, START, START, START + len(data), profile)

    def selected(self, prg, digest=variant.RUNTIME_SHA256):
        real_sha = ps.sha
        with patch.object(ps, 'sha', side_effect=lambda data:
                          digest if data == RUNTIME else real_sha(data)):
            selected = ps.select_profile(prg, BASE)
            return selected, ps.disassemble(prg, selected)

    def test_exact_small_delta_and_deep_copy(self):
        original = copy.deepcopy(BASE)
        p = variant.build_profile(BASE)
        self.assertEqual(p['runtimeSha256'], variant.RUNTIME_SHA256)
        self.assertEqual(set(p['opcodes']) - set(BASE['opcodes']), ADDED)
        self.assertEqual(p['entryBytes'], '4c4522')
        self.assertEqual(p['headerWords'], BASE['headerWords'])
        for opcode, spec in BASE['opcodes'].items():
            if opcode not in ('80', 'B4'):
                self.assertEqual(p['opcodes'][opcode], spec)
        self.assertEqual(set(p['opcodes']['80']['selectors']) -
                         set(BASE['opcodes']['80']['selectors']), {'0A'})
        for key, spec in BASE['opcodes']['80']['selectors'].items():
            self.assertEqual(p['opcodes']['80']['selectors'][key], spec)
        self.assertEqual(p['families'], BASE['families'])
        self.assertEqual(p['modifierTables'], BASE['modifierTables'])
        p['opcodes']['80']['selectors']['01']['comment'] = 'changed'
        p['families'][0]['comment'] = 'changed'
        p['modifierTables'].clear()
        self.assertEqual(BASE, original)
        self.assertEqual(variant.build_profile(BASE), PROFILE)

    def test_future_base_expansions_or_entry_changes_require_review(self):
        mutations = [lambda p: p.update(entryBytes='4c6722'),
                     lambda p: p.update(runtimeSha256=variant.RUNTIME_SHA256),
                     lambda p: p['headerWords'].update(data=0x081D),
                     lambda p: p['opcodes'].update(EE={'operand': 'u16le'}),
                     lambda p: p['opcodes']['80']['selectors'].update(
                         {'0B': {'mnemonic': 'TIME_ARG', 'operand': 'none'}}),
                     lambda p: p['modifierTables']['input-store'].update(
                         {'44': {'mnemonicSuffix': '_NEW'}})]
        for mutate in mutations:
            p = copy.deepcopy(BASE)
            mutate(p)
            with self.subTest(mutation=p), self.assertRaisesRegex(ValueError, 'reviewed canonical base'):
                variant.build_profile(p)

    def test_new_forms_and_native_sign_contract(self):
        for code, mnemonic, size in [('86', 'POWER_REVERSED', 1),
                                      ('af', 'OPEN_SECONDARY', 1),
                                      ('c7', 'CHR_STRING', 1),
                                      ('f2 34 12', 'LOAD_STRING_ELEMENT_AT', 3),
                                      ('80 0a', 'STATUS_ARG', 2),
                                      ('b4', 'SGN_VARIANT_BC39', 1)]:
            with self.subTest(code=code):
                row = self.one(bytes.fromhex(code))
                self.assertEqual((row['mnemonic'], row['size'], row['control']),
                                 (mnemonic, size, 'fallthrough'))
        self.assertEqual(self.one(bytes.fromhex('f2 34 12'))['operands'], {'value': 0x1234})
        self.assertEqual(self.one(bytes.fromhex('80 0a'))['operands'], {'selector': 10})
        self.assertIn('-32383', self.one(b'\xb4')['comment'])
        self.assertEqual(self.one(b'\xb4', BASE)['mnemonic'], 'SGN')
        self.assertEqual(self.one(b'\xb4', variant_2267.build_profile(BASE))['mnemonic'], 'SGN')

    def test_only_one_selector_changes_and_no_cross_runtime_backport(self):
        other = variant_2267.build_profile(BASE)
        for selector in range(256):
            data = bytes([0x80, selector])
            if f'{selector:02X}' not in PROFILE['opcodes']['80']['selectors']:
                with self.subTest(selector=selector), self.assertRaisesRegex(ps.DecodeError, 'unknown selector'):
                    self.one(data)
            elif selector != 10:
                self.assertEqual(self.one(data), self.one(data, BASE))
        for p in (BASE, other):
            with self.assertRaisesRegex(ps.DecodeError, 'unknown selector'):
                self.one(bytes.fromhex('80 0a'), p)
        for opcode in ('A1', 'A8', 'ED', 'EE', 'EF', 'F1', 'F4'):
            with self.subTest(opcode=opcode), self.assertRaisesRegex(ps.DecodeError, 'unknown operand length'):
                self.one(bytes.fromhex(opcode + ' 00 30'))

    def test_truncated_forms_and_unknowns_still_refuse(self):
        for data, message in [(b'\x80', 'truncated instruction'),
                              (b'\xf2', 'truncated instruction'),
                              (b'\xf2\x34', 'truncated instruction'),
                              (b'\x80\x11', 'unknown selector'),
                              (b'\x80\x12', 'unknown selector'),
                              (b'\x48', 'unknown operand length')]:
            with self.subTest(data=data), self.assertRaisesRegex(ps.DecodeError, message):
                self.one(data)

    def test_selection_partition_and_target_boundary_gates(self):
        code = bytes.fromhex('86 af c7 f2 00 28 80 0a b4 d8')
        selected, report = self.selected(fixture(code))
        self.assertEqual(selected, PROFILE)
        self.assertTrue(report['completeCodeDecode'])
        self.assertEqual(report['decodedBytes'], len(code))
        # Target $3003 is the start of F2, not either of its address bytes.
        for target, complete in [(START + 3, True), (START + 4, False), (0x2800, False)]:
            code = b'\xd1' + target.to_bytes(2, 'little') + bytes.fromhex('f2 00 28 d8')
            _, report = self.selected(fixture(code))
            self.assertEqual(report['completeCodeDecode'], complete)
            if not complete:
                self.assertIn('not a decoded instruction boundary', report['error'])
        # Classic selection must not borrow STATUS_ARG or the variant SGN.
        classic, report = self.selected(fixture(b'\xb4\x80\x0a'), BASE['runtimeSha256'])
        self.assertEqual(classic['opcodes']['B4']['mnemonic'], 'SGN')
        self.assertIn('unknown selector', report['error'])

    def test_no_unmocked_fingerprint_or_stub_layout_bypass(self):
        prg = fixture(b'\xd8')
        self.assertIs(ps.select_profile(prg, BASE), BASE)
        with self.assertRaisesRegex(ps.DecodeError, 'runtime fingerprint'):
            ps.disassemble(prg, PROFILE)
        for address, data, message in [(0x0819, bytes.fromhex('4c6722'), 'entry stub'),
                                       (0x081C, b'\x00\x27', 'region ordering'),
                                       (0x0826, b'\x01', 'runtime fingerprint')]:
            damaged = bytearray(prg)
            damaged[2 + address - 0x0801:2 + address - 0x0801 + len(data)] = data
            with self.subTest(address=address), self.assertRaisesRegex(ps.DecodeError, message):
                self.selected(bytes(damaged))
        wrong_load = b'\x00\x08' + prg[2:]
        self.assertIs(ps.select_profile(wrong_load, BASE), BASE)
        with self.assertRaisesRegex(ps.DecodeError, 'load address'):
            ps.disassemble(wrong_load, PROFILE)
        with self.assertRaisesRegex(ps.DecodeError, 'truncated/out-of-image'):
            ps.disassemble(prg[:20], PROFILE)


if __name__ == '__main__':
    unittest.main()
