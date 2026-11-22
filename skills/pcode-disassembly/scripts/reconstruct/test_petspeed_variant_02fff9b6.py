"""Synthetic exact-profile frontend admission; no private files or runtime bytes.

Only the all-zero runtime digest is mocked for positive pipeline tests.  The
real identity database, profile selection, layout, decoder, and lifter are used.
"""
import contextlib
import unittest
from unittest.mock import patch

from formats import decode, module, profile
import identify as identifier
import reconstruct as reconstruction
from petspeed_listing import serialize
from reading_projection import render_reading


RUNTIME_SHA256 = '02fff9b629da0d6f927549c4c0e7777fc6d31b040ae41c1b9630f114bd4e6af5'
RUNTIME = bytes(0x2800 - 0x0826)
START = 0x3000


def fixture(code):
    p = profile('petspeed')
    base = 0x0801
    raw = bytearray(START + len(code) - base)
    raw[0x0819 - base:0x081C - base] = bytes.fromhex('4c4522')
    for key, value in dict(data=0x2800, arrays=0x2800, initialization=0x2800,
                           codeCursor=START - 1, topCode=START + len(code)).items():
        offset = p['headerWords'][key] - base
        raw[offset:offset + 2] = value.to_bytes(2, 'little')
    raw[START - base:] = code
    return base.to_bytes(2, 'little') + raw


@contextlib.contextmanager
def synthetic_runtime():
    ps = module('petspeed')
    real_sha = ps.sha
    real_identity_sha = identifier.sha
    with patch.object(ps, 'sha', side_effect=lambda data:
                      RUNTIME_SHA256 if data == RUNTIME else real_sha(data)), \
         patch.object(identifier, 'sha', side_effect=lambda data:
                      RUNTIME_SHA256 if data == RUNTIME else real_identity_sha(data)):
        yield


class VariantFrontendTests(unittest.TestCase):
    def test_real_pin_layout_and_binary_only_decode(self):
        prg = fixture(bytes.fromhex('86 af 52 41 c7 f2 00 28 80 0a b4 d8'))
        with synthetic_runtime():
            identity = identifier.identify(prg)
            self.assertEqual(identity['status'], 'identified')
            self.assertEqual(identity['family'], 'petspeed')
            self.assertTrue(identity['matches'][0]['layoutValid'])
            self.assertEqual(identity['matches'][0]['evidence'][0]['sha256'], RUNTIME_SHA256)
            report = decode(prg, 'petspeed')
            result = reconstruction.reconstruct(prg)
            raw_result = reconstruction.reconstruct(prg[2:], raw_base=0x0801)
        self.assertEqual(report['runtimeSha256'], RUNTIME_SHA256)
        self.assertEqual(result['selectedProfile'], 'petspeed-c64-02fff9b6-2245')
        self.assertEqual(result['selectedProfile'], raw_result['selectedProfile'])
        self.assertNotIn('petspeedData', report)
        self.assertNotIn('petspeedCompactStringSlots', report)
        self.assertEqual([r['address'] for g in result['groups'] for r in g['instructions']],
                         [r['address'] for r in report['instructions']])
        self.assertNotIn('readingView', result)
        for exporter in (serialize, render_reading):
            with self.subTest(exporter=exporter.__name__), self.assertRaises(ValueError):
                exporter(result)

    def test_variant_sgn_is_a_barrier_not_ordinary_basic_sgn(self):
        with synthetic_runtime():
            result = reconstruction.reconstruct(fixture(bytes.fromhex('52 01 b4 d8')))
        text = '\n'.join(g['text'] for g in result['groups'])
        self.assertIn('SGN_VARIANT_BC39 semantics not yet modeled', text)
        self.assertNotIn('SGN(', text)
        rows = [r for g in result['groups'] for r in g['instructions']]
        self.assertIn('-32383', next(r for r in rows if r['mnemonic'] == 'SGN_VARIANT_BC39')['comment'])

    def test_matching_identity_does_not_bypass_entry_or_layout(self):
        for address, data in [(0x0819, bytes.fromhex('4c6722')),
                              (0x081C, bytes.fromhex('0027'))]:
            prg = bytearray(fixture(b'\xd8'))
            prg[2 + address - 0x0801:2 + address - 0x0801 + len(data)] = data
            with self.subTest(address=address), synthetic_runtime():
                identity = identifier.identify(bytes(prg))
                self.assertEqual(identity['status'], 'identified')
                self.assertFalse(identity['matches'][0]['layoutValid'])
                with self.assertRaisesRegex(ValueError, 'unsupported object layout'):
                    reconstruction.reconstruct(bytes(prg))

    def test_unknown_selector_truncation_and_target_gate_survive_admission(self):
        for code, error in [('80 11', 'unknown selector'),
                             ('80 0b', 'unknown selector'),
                             ('f2 00', 'truncated instruction'),
                             ('ee 00 28', 'unknown operand length'),
                             ('d1 04 30 f2 00 28', 'not a decoded instruction boundary')]:
            with self.subTest(code=code), synthetic_runtime():
                prg = fixture(bytes.fromhex(code))
                self.assertTrue(identifier.identify(prg)['matches'][0]['layoutValid'])
                with self.assertRaisesRegex(ValueError, error):
                    reconstruction.reconstruct(prg)

    def test_unmocked_and_mutated_runtime_are_unknown(self):
        prg = fixture(b'\xd8')
        self.assertEqual(identifier.identify(prg)['status'], 'unknown')
        changed = bytearray(prg)
        changed[2 + 0x0826 - 0x0801] ^= 1
        with synthetic_runtime():
            self.assertEqual(identifier.identify(bytes(changed))['status'], 'unknown')
            with self.assertRaisesRegex(ValueError, 'compiler family unknown'):
                reconstruction.reconstruct(bytes(changed))


if __name__ == '__main__':
    unittest.main()
