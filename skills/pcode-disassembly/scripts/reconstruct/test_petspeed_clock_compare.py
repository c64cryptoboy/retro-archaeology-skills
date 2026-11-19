"""An inline string survives this clock handler; a general FAC value does not."""
import importlib
import unittest

from formats import module, profile
from symbolic import lift


PS = module('petspeed')
ALT = importlib.import_module(PS.__name__ + '.variant_2267').build_profile(profile('petspeed'))


def groups(code, fingerprint=ALT['runtimeSha256'], split=None):
    raw = bytes.fromhex(code)
    origin = pc = 0x3200
    rows = []
    while pc < origin + len(raw):
        r = PS.decode_one(raw, origin, pc, origin + len(raw), ALT)
        if split is not None and pc >= origin + split:
            r['region'] = 'other'
        rows.append(r)
        pc += r['size']
    result = lift('petspeed', dict(instructions=rows, runtimeSha256=fingerprint))['groups']
    assert [r for g in result for r in g['instructions']] == rows
    return result


class ClockCompareTests(unittest.TestCase):
    def test_sample_then_compare_in_native_order(self):
        first, test, second, empty = groups('46 02 36 31 80 0d 99 60 46 00 80 0d 99 61')
        self.assertEqual([g['text'] for g in (first, test, second, empty)],
                         ['T_3204$ = TI$', 'V_2800 = (T_3204$ < "61")',
                          'T_320A$ = TI$', 'V_2808 = (T_320A$ < "")'])
        self.assertEqual(test['evidenceAddresses'], [0x3200, 0x3204, 0x3206, 0x3207])
        self.assertIn('normal return', ' '.join(first['warnings']))

    def test_stack_is_not_forwarded_and_arg_is_not_reused(self):
        result = groups('52 07 f5 46 01 30 80 0d 99 f7 8d 60')
        self.assertEqual(result[-1]['text'], 'V_2800 = ((T_3206$ < "0") AND <?>)')
        self.assertEqual(result[-1]['kind'], 'partial')
        stale = groups('46 01 30 80 0d 99 82 60')
        self.assertIn('<?>', stale[-1]['text'])
        self.assertEqual(stale[-1]['text'].count('T_3203$'), 1)

    def test_refuse_unproved_inputs_and_other_consumers(self):
        for code in ('52 09 80 0d 99 60', '24 80 0d 99 60',
                     '46 01 30 8a 80 0d 99 60', '46 01 30 80 0d 82 60',
                     '46 01 30 80 0d 9e 99 60'):
            with self.subTest(code=code):
                result = groups(code)
                self.assertTrue(any(g['kind'] == 'unresolved' and 'TIME_STRING_ARG' in g['text']
                                    for g in result))
                self.assertFalse(any(' = TI$' in g['text'] for g in result))

    def test_identity_and_entry_refusals(self):
        code = '46 01 30 80 0d 99 60'
        variants = [groups(code, fp) for fp in (None, profile('petspeed')['runtimeSha256'])]
        variants += [groups(code, split=off) for off in (3, 5)]
        variants += [groups(f'd1 {lo:02x} 32 ' + code) for lo in (6, 8)]
        for result in variants:
            self.assertFalse(any(' = TI$' in g['text'] for g in result))
            self.assertTrue(any('TIME_STRING_ARG_CLOBBER_FAC_TYPE semantics not yet modeled' in g['text']
                                for g in result))
