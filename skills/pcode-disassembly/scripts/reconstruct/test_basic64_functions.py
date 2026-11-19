"""Authored BASIC-64 byte fragments: decoded and lifted, never executed."""
import unittest
from formats import module, profile
from symbolic import lift


def word(v):
    return v.to_bytes(2, 'little')


def definition(body, *, desc=0x9000, skip=None, tail=b'\x95'):
    body = bytes.fromhex(body)
    return b'\x72' + word(desc) + word(5 + len(body) if skip is None else skip) + body + tail


def read_groups(raw):
    m, p = module('basic64'), profile('basic64')
    rows = []; pc = 0
    while pc < len(raw):
        row = m.decode_one(raw, 0, pc, len(raw), p)
        rows.append(row); pc += row['size']
    groups = lift('basic64', {'instructions': rows, 'layout': {
        'loadedEnd': 0x2000, 'stringTop': 0x8000, 'memoryTop': 0xA000}})['groups']
    assert [r for g in groups for r in g['instructions']] == rows
    return groups


class Basic64Functions(unittest.TestCase):
    def test_complete_leafs_keep_separate_body_label_and_evidence(self):
        for body, expr in [('26 02 90 94', 'V_9002'),
                           ('27 02 90 26 02 90 54 94', '(V_9002 * V_9002)'),
                           ('26 02 90 25 fe ff 6d 94', '(-2 - V_9002)'),
                           ('27 02 90 32 80 00 00 00 00 53 94', '(V_9002 + 0.5)')]:
            with self.subTest(body=body):
                d, b, stop = read_groups(definition(body))
                self.assertEqual((d['text'], d['kind']), ('DEF FN F_36864(V_9002) = ' + expr, 'inferred'))
                self.assertEqual((b['text'], b['kind']), ('RETURN FN F_36864 = ' + expr, 'structural'))
                self.assertEqual(d['evidenceAddresses'], [r['address'] for r in d['instructions'] + b['instructions']])
                self.assertEqual(b['evidenceAddresses'], d['evidenceAddresses'])
                self.assertEqual(b['instructions'][0]['address'], 5)
                self.assertIn(f'skips to L_{stop["instructions"][0]["address"]:04X}', d['warnings'][0])
                self.assertIn('not the previous argument bytes', b['warnings'][0])

    def test_refuse_foreign_load_stack_effect_missing_argument_or_return(self):
        for body in ['27 03 90 22 05 54 94', '26 02 90 93 07 90 94', '26 02 90 2b 2c 94',
                     '26 02 90 28 22 90 94', '24 01 22 05 53 94', '27 02 90 54 94', '26 02 90 95']:
            with self.subTest(body=body):
                groups = read_groups(definition(body))
                self.assertTrue(groups[0]['text'].startswith('REM DEFINE_FUNCTION '))
                self.assertFalse(any(g['text'].startswith('RETURN FN F_') for g in groups))

    def test_refuse_targets_skip_and_overlapping_descriptors(self):
        body = '27 02 90 26 02 90 54 94'
        for fragment in [*(definition(body, tail=b'\x8a' + word(t)) for t in (5, 8, 11, 12)),
                         definition(body, tail=b'\x90\x01' + word(5)), definition(body, skip=12),
                         definition('26 fc 9f 94', desc=0x9FFA), definition('26 02 70 94', desc=0x7000),
                         *(definition(body, tail=b'\x72' + word(a) + word(22) + bytes.fromhex('26 02 90 94 95'))
                           for a in (0x8FFA, 0x9000, 0x9006))]:
            with self.subTest(raw=fragment.hex()):
                self.assertTrue(read_groups(fragment)[0]['text'].startswith('REM DEFINE_FUNCTION '))

    def test_use_descriptor_at_call_not_a_static_inlined_expression(self):
        groups = read_groups(definition('26 02 90 94', tail=bytes.fromhex('22 07 93 00 90 28 22 90')))
        call = groups[2]
        self.assertEqual(call['text'], 'V_9022 = FN F_36864(7)')
        self.assertIn('descriptor selects the body at runtime', call['warnings'][0])
        self.assertEqual(call['evidenceAddresses'], [9, 11, 14])
        self.assertEqual(len(groups), 3)
        self.assertEqual(read_groups(bytes.fromhex('26 33 90 93 00 90 28 22 90'))[0]['text'],
                         'V_9022 = FN F_36864(V_9033)')

    def test_refuse_call_store_foreign_entry_overlap_or_wrong_consumer(self):
        for raw in ['22 07 93 00 90 28 22 90 8a 05 00', '22 07 93 00 90 28 22 90 8a 02 00',
                    '22 07 93 00 90 28 03 90', '22 07 93 00 90 28 fd 9f',
                    '22 07 93 fa 9f 28 22 90', '26 20 d0 93 00 90 28 22 90',
                    '22 07 93 00 90 2b 2c 28 22 90', '22 07 93 00 90 94']:
            with self.subTest(raw=raw):
                groups = read_groups(bytes.fromhex(raw))
                self.assertFalse(any(g['text'].startswith('V_') and ' = FN ' in g['text'] for g in groups))
                self.assertTrue(any(' = FN ' in g['text'] and g['text'].startswith('T_') for g in groups))
