"""Portable ZERO_ARG grammar/refusal controls; synthetic bytes only, no CPU execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import petspeed as ps

HERE = Path(__file__).resolve().parent
PROFILE = json.loads((HERE / 'petspeed_profile.json').read_text())
START = 0x281B
# Frozen public grammar before AB, normalized to avoid JSON whitespace dependence.
PRE_AB_SHA256 = '73b3e6f738a1a17dfb852b4eafbeb6c3447e6c06ddd53a4c10aaf3e115fbaaa8'


def pre_ab_profile():
    profile = deepcopy(PROFILE)
    del profile['opcodes']['AB']
    return profile


def fixture(code, profile=PROFILE, start=START):
    profile = deepcopy(profile)
    base = profile['loadAddress']
    raw = bytearray(start + len(code) - base)
    entry = bytes.fromhex(profile['entryBytes'])
    offset = profile['entryAddress'] - base
    raw[offset:offset + len(entry)] = entry
    for key, value in dict(data=0x2810, arrays=0x2811, initialization=0x2812,
                           codeCursor=start - 1, topCode=start + len(code)).items():
        offset = profile['headerWords'][key] - base
        raw[offset:offset + 2] = value.to_bytes(2, 'little')
    raw[start - base:] = code
    # Only synthetic zero-filled runtimes are repinned; the installed profile
    # retains its exact real-runtime fingerprint and is never modified here.
    profile['runtimeSha256'] = ps.sha(raw[profile['runtimeStart'] - base:profile['runtimeEnd'] - base])
    return base.to_bytes(2, 'little') + raw, profile


def decode(code, profile=PROFILE, start=START):
    blob, synthetic_profile = fixture(code, profile, start)
    return ps.disassemble(blob, synthetic_profile)


class ZeroArgTests(unittest.TestCase):
    def test_profile_adds_only_ab_to_frozen_public_grammar(self):
        self.assertEqual(Path(ps.__file__).resolve(), HERE / 'petspeed.py')
        self.assertEqual(ps.sha(json.dumps(pre_ab_profile(), sort_keys=True).encode()), PRE_AB_SHA256)
        entry = PROFILE['opcodes']['AB']
        self.assertEqual((entry['mnemonic'], entry['operand'], entry['control']),
                         ('ZERO_ARG', 'none', 'fallthrough'))
        self.assertEqual(set(entry), {'mnemonic', 'operand', 'control', 'comment', 'evidence'})
        self.assertEqual((PROFILE['runtimeStart'], PROFILE['runtimeEnd']), (0x0826, 0x2800))
        self.assertEqual(PROFILE['runtimeSha256'],
                         'cee17449b6e9700af4642546477c06dbb42413888fa5e594ebded33014c5dbaf')

    def test_pre_ab_synthetic_profile_preserves_historical_refusal(self):
        result = decode(b'\xab\xd3', pre_ab_profile())
        self.assertFalse(result['completeCodeDecode'])
        self.assertEqual(result['decodedBytes'], 0)
        self.assertIn('unknown operand length for opcode $AB', result['error'])

    def test_ab_at_end_needs_no_operand_and_falls_through(self):
        result = decode(b'\xab')
        self.assertTrue(result['completeCodeDecode'])
        self.assertEqual(result['decodedBytes'], 1)
        row = result['instructions'][0]
        self.assertEqual((row['size'], row['operands'], row['mnemonic'], row['control']),
                         (1, {}, 'ZERO_ARG', 'fallthrough'))

    def test_following_opcode_is_not_consumed(self):
        result = decode(b'\xab\x52\x9a\xd3')
        self.assertTrue(result['completeCodeDecode'])
        self.assertEqual([i['size'] for i in result['instructions']], [1, 2, 1])
        self.assertEqual(result['instructions'][1]['operands']['value'], 0x9a)
        self.assertEqual(result['instructions'][1]['address'], START + 1)

    def test_page_boundary_following_opcode(self):
        result = decode(b'\xab\xd3', start=0x28ff)
        self.assertTrue(result['completeCodeDecode'])
        self.assertEqual([i['address'] for i in result['instructions']], [0x28ff, 0x2900])

    def test_repeated_ab_instructions_remain_separate(self):
        result = decode(b'\xab\xab\xab\xd3')
        self.assertTrue(result['completeCodeDecode'])
        self.assertEqual([i['address'] for i in result['instructions']], list(range(START, START + 4)))

    def test_ab_inside_known_operand_not_reinterpreted(self):
        result = decode(b'\x52\xab\x46\x01\xab\xd3')
        self.assertTrue(result['completeCodeDecode'])
        self.assertNotIn('ZERO_ARG', [i['mnemonic'] for i in result['instructions']])
        self.assertEqual(result['instructions'][0]['operands']['value'], 0xab)
        self.assertEqual(result['instructions'][1]['operands']['stringHex'], 'ab')

    def test_truncated_following_instruction_still_refuses(self):
        for code in (b'\xab\x52', b'\xab\x40\x01', b'\xab\x46\x02A'):
            with self.subTest(code=code.hex()):
                result = decode(code)
                self.assertFalse(result['completeCodeDecode'])
                self.assertEqual(result['decodedBytes'], 1)
                self.assertIn('truncated instruction', result['error'])

    def test_unknown_following_ab_stops_without_resynchronization(self):
        result = decode(b'\xab\xf1\xd3')
        self.assertFalse(result['completeCodeDecode'])
        self.assertEqual(result['decodedBytes'], 1)
        self.assertEqual(len(result['instructions']), 1)
        self.assertIn('unknown operand length for opcode $F1', result['error'])

    def test_unrelated_unknown_widths_not_admitted(self):
        for opcode in (0xc7, 0xf4):
            with self.subTest(opcode=opcode):
                result = decode(bytes([0xab, opcode, 0xd3]))
                self.assertFalse(result['completeCodeDecode'])
                self.assertEqual(result['decodedBytes'], 1)
                self.assertIn(f'opcode ${opcode:02X}', result['error'])

    def test_unknown_selector_after_ab_remains_refusal(self):
        result = decode(b'\xab\x80\xff\xd3')
        self.assertFalse(result['completeCodeDecode'])
        self.assertEqual(result['decodedBytes'], 1)
        self.assertIn('unknown selector $FF', result['error'])

    def test_branch_to_ab_and_after_ab_are_valid_boundaries(self):
        for destination in (START, START + 1):
            with self.subTest(destination=destination):
                result = decode(b'\xab\xd3\xd1' + destination.to_bytes(2, 'little'))
                self.assertTrue(result['completeCodeDecode'])

    def test_branch_inside_following_operand_refuses(self):
        result = decode(b'\xab\x52\x01\xd1' + (START + 2).to_bytes(2, 'little'))
        self.assertFalse(result['completeCodeDecode'])
        self.assertIn('not a decoded instruction boundary', result['error'])

    def test_wrong_runtime_still_refuses(self):
        blob, profile = fixture(b'\xab\xd3')
        bad = bytearray(blob)
        bad[0x1408 - profile['loadAddress'] + 2] ^= 1
        with self.assertRaisesRegex(ps.DecodeError, 'runtime fingerprint'):
            ps.disassemble(bytes(bad), profile)

    def test_synthetic_decode_and_render_are_deterministic(self):
        first = decode(b'\xab\x8a\x82\xd3')
        again = decode(b'\xab\x8a\x82\xd3')
        self.assertEqual(first, again)
        self.assertEqual(ps.render(first), ps.render(again))
        self.assertEqual(first['source'], {})
        self.assertIsNone(first['lineMap'])

    def test_runtime_dependencies_and_span_edges_remain_fingerprinted(self):
        blob, profile = fixture(b'\xab\xd3')
        # Synthetic runtime mutations at the span edges, dispatch word, fetch,
        # handler entry and handler tail; not commercial runtime byte fixtures.
        for address in (0x0826, 0x087c, 0x0926, 0x1408, 0x1413, 0x27ff):
            with self.subTest(address=address):
                bad = bytearray(blob)
                bad[2 + address - profile['loadAddress']] ^= 1
                with self.assertRaisesRegex(ps.DecodeError, 'runtime fingerprint'):
                    ps.disassemble(bytes(bad), profile)

    def test_unknown_before_ab_is_not_skipped(self):
        result = decode(b'\xf1\xab\xd3')
        self.assertFalse(result['completeCodeDecode'])
        self.assertEqual(result['instructions'], [])
        self.assertEqual(result['decodedBytes'], 0)
        self.assertIn('unknown operand length for opcode $F1', result['error'])

    def test_target_before_main_or_at_exclusive_end_refuses(self):
        for destination in (START - 1, START + 4):
            with self.subTest(destination=destination):
                result = decode(b'\xab\xd1' + destination.to_bytes(2, 'little'))
                self.assertFalse(result['completeCodeDecode'])
                self.assertEqual(result['decodedBytes'], 4)
                self.assertEqual([i['address'] for i in result['instructions']], [START, START + 1])
                self.assertIn('not a decoded instruction boundary', result['error'])


if __name__ == '__main__':
    unittest.main()
