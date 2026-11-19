"""Synthetic instruction streams for the detailed reading; no runtime assets."""
import importlib
import unittest

from formats import module, profile
from symbolic import lift


PS = module('petspeed')
ALT = importlib.import_module(PS.__name__ + '.variant_2267').build_profile(profile('petspeed'))
START = 0x3200


def groups(hexbytes, fingerprint=ALT['runtimeSha256']):
    raw = bytes.fromhex(hexbytes)
    rows = []
    pos = START
    while pos < START + len(raw):
        row = PS.decode_one(raw, START, pos, START + len(raw), ALT)
        rows.append(row)
        pos += row['size']
    return lift('petspeed', {'instructions': rows, 'runtimeSha256': fingerprint,
                             'loadedRegions': [{'name': 'array region', 'start': 0x2900,
                                                'end': 0x2A00}]})['groups']


class AbsoluteWordTests(unittest.TestCase):
    def test_signed_fac_not_arg_at_little_endian_address(self):
        g, = groups('40 cc fe 55 11 f4 04 29')
        self.assertEqual((g['kind'], g['text']), ('inferred', 'STORE I16BE AT $2904 FROM -308'))

    def test_floating_conversion_not_verbatim_copy(self):
        g, = groups('43 81 c0 00 00 00 00 f4 04 29')
        self.assertIn('1.5', g['text'])
        self.assertIn('range', ' '.join(g['warnings']))

    def test_string_tag_bypasses_numeric_conversion(self):
        g, = groups('46 01 51 f4 04 29')
        self.assertEqual(g['kind'], 'partial')
        self.assertIn('raw bytes', ' '.join(g['warnings']))
        self.assertNotIn('I16BE', g['text'])

    def test_branch_bypassing_fac_producer(self):
        # GOTO the store, not the preceding -308 producer.
        g = groups('d1 06 32 40 cc fe f4 04 29')[-1]
        self.assertEqual(g['kind'], 'partial')
        self.assertNotIn('-308', g['text'])

    def test_overwrites_prepared_pointer_and_kills_fac_fact(self):
        result = groups('fc 80 29 8a a3 52 07 f4 04 29 f9')
        self.assertIn('T_INDEX_', result[0]['text'])
        self.assertEqual(result[-2]['text'], 'STORE I16BE AT $2904 FROM 7')
        self.assertEqual((result[-1]['text'], result[-1]['kind']), ('<?> = <?>', 'partial'))

    def test_not_ordinary_word_or_wrong_runtime(self):
        for operand in ('ff 29', '3d 00', '00 d0', 'ff ff'):
            self.assertEqual(groups('8a f4 ' + operand)[-1]['kind'], 'unresolved')
        for fingerprint in (None, profile('petspeed')['runtimeSha256']):
            self.assertEqual(groups('8a f4 04 29', fingerprint)[-1]['kind'], 'unresolved')
