"""Independently authored scalar DATA fragments and layout, never executed."""
import unittest

from formats import module, profile
from symbolic import lift


RAM = dict(loadedEnd=0x2800, stringTop=0x9080, memoryTop=0xb000)


def numeric(code, layout=RAM, change=None):
    raw = bytes.fromhex(code)
    decoder, p = module('basic64'), profile('basic64')
    rows = []
    pc = 0
    while pc < len(raw):
        r = decoder.decode_one(raw, 0, pc, len(raw), p)
        rows.append(r)
        pc += r['size']
    if change:
        change(rows)
    gs = lift('basic64', {'instructions': rows, 'layout': layout})['groups']
    assert [r for g in gs for r in g['instructions']] == rows
    return [g for g in gs if g['text'].startswith('READ V_') and g['instructions'][0]['opcode'] != 0x80]


class NumericDataTests(unittest.TestCase):
    def test_order_width_selector_and_repeated_destination(self):
        gs = numeric('7b 7e 28 fb 9f 7f a7 fa 7f a7 fa 7e 28 80 90 73')
        self.assertEqual([g['text'] for g in gs], ['READ V_9FFB', 'READ V_03FA', 'READ V_03FA', 'READ V_9080'])
        for g, at, size, action in zip(gs, (1,5,8,11), (4,3,3,4), ('pack FAC', 'signed word', 'signed word', 'pack FAC')):
            self.assertEqual(g['kind'], 'inferred')
            self.assertEqual(g['evidenceAddresses'], [0, at, at+1])
            self.assertEqual(sum(r['size'] for r in g['instructions']), size)
            self.assertIn(action, g['warnings'][0])
            self.assertIn('not evidence of original READ syntax', g['warnings'][0])

    def test_storage_bounds_and_overlaps(self):
        for store in ('7e 28 10 00', '7e 28 40 00', '7e 28 fc 9f', '7e 28 7f 90',
                      '7e 28 fd ff', '7f a7 3b', '7f a7 fb', '7f a7 ff'):
            with self.subTest(store=store):
                self.assertFalse(numeric('7b ' + store + ' 7f a7 62 73'))
        self.assertFalse(numeric('7b 7e 28 84 90 73', layout=None))
        self.assertFalse(numeric('7b 7e 28 84 90 73', layout=dict(RAM, memoryTop=0x9088)))
        self.assertFalse(numeric('7b 7e 28 84 90 73', layout=dict(RAM, loadedEnd=0x9081)))
        for a, b in [('7f a7 62', '7f a7 61'), ('7e 28 90 90', '7e 28 94 90')]:
            self.assertEqual(len(numeric(f'7b {a} {b} 7f a7 90 73')), 1)
        self.assertFalse(numeric('7b 80 ab 53 7f a7 55 73'))  # Descriptor bookkeeping.

    def test_sources_consumers_and_interruptions(self):
        for code in ('7f a7 55 73', '7d 7f a7 55 73', '7b 7d 7e 28 80 90 73',
                     '7b 7c 00 08 00 7f a7 55 73', '7b 92 7f a7 55 73',
                     '7b 96 7f a7 55 73', '7b 7a a7 55 73', '7b 7e a7 55 73',
                     '7b 7f 28 80 90 73', '7b 7e 84 28 80 90 73', '7b 7f 3b 10 73'):
            with self.subTest(code=code):
                self.assertFalse(numeric(code))
        g, = numeric('7b 7d 7f a7 55 7b 7f a7 3c 73')
        self.assertEqual((g['text'], g['evidenceAddresses']), ('READ V_033C', [5, 6, 7]))

    def test_foreign_entry_or_discontinuity(self):
        body = '7b 7e 28 81 90 7f a7 53 73'
        for op in ('8a', '9f'):
            for offset, count in ((0,2), (1,0), (2,0), (5,1), (6,1)):
                with self.subTest(op=op, offset=offset):
                    self.assertEqual(len(numeric(f'{body} {op} {offset:02x} 00')), count)
        for change in (lambda rs: rs[2].update(region='other'), lambda rs: rs[0].update(size=2)):
            self.assertFalse(numeric(body, change=change))
