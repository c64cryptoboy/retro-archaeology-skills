"""Authored byte corridors and independent rank/stride fixtures; no runtime required."""
import unittest

from formats import module, profile
from symbolic import lift

FLOAT = '2e 80 92 1a 7f 3b 10 2e 80 92 1a 80 3e 15'
WORD = 'a5 52 1a 7f 3b 10 a5 52 1a 80 3e 15'


def corridor(body, *, skip=None, prefix='7c 00', tail='73', layout=True, change=None):
    body = bytes.fromhex(body)
    pre = bytes.fromhex(prefix)
    target = len(pre) + 2 + len(body) if skip is None else skip
    raw = pre + (target.to_bytes(2, 'little') if pre.startswith(b'\x7c') else b'') + body + bytes.fromhex(tail)
    decoder, p = module('basic64'), profile('basic64')
    rows = []
    pc = 0
    while pc < len(raw):
        r = decoder.decode_one(raw, 0, pc, len(raw), p)
        # Provide descriptor facts separately, as the full image decoder does.
        if r['opcode'] in (0x3b, 0x3d, 0x3e):
            integer = r['opcode'] == 0x3b
            r['operands'].update(arrayBase=0xb100 if integer else 0xb104,
                                 extentsReversed=[2], elementSize=2 if integer else 3)
        rows.append(r)
        pc += r['size']
    if change:
        change(rows)
    report = {'instructions': rows}
    if layout:
        report['layout'] = dict(loadedEnd=0x3000, stringTop=0x9000, memoryTop=0xff00)
    gs = lift('basic64', report)['groups']
    assert [r for g in gs for r in g['instructions']] == rows
    return [g for g in gs if g['text'].startswith('INPUT AR_')]


class IndexedInputTests(unittest.TestCase):
    def test_index_sampled_twice_with_store_between_not_before_prompt(self):
        for body, slot, addresses in [(FLOAT, 'V_9280', [0,4,7,8,9,11,14,15,16]),
                                      (WORD, 'V_0352', [0,4,6,7,8,10,12,13,14])]:
            with self.subTest(slot=slot):
                g, = corridor(body)
                self.assertEqual(g['text'], f'INPUT AR_B100%({slot}), AR_B104$({slot})')
                self.assertEqual(g['evidenceAddresses'], addresses)
                self.assertEqual([r['address'] for r in g['instructions']], addresses)
                self.assertEqual(g['instructions'][0]['operands']['target'], addresses[-1]+2)
                self.assertEqual(g['kind'], 'inferred')
                self.assertIn('bad numeric delimiter', g['warnings'][0])
                self.assertIn('bounds-check and store before sampling', g['warnings'][1])
                self.assertEqual(any('not BASIC INT()' in w for w in g['warnings']), body == FLOAT)
        g, = corridor(WORD.replace('52 1a 80', '58 1a 80'))
        self.assertEqual(g['text'], 'INPUT AR_B100%(V_0352), AR_B104$(V_0358)')

    def test_refuse_alias_or_unproved_storage(self):
        def alter(which, **operands):
            return lambda rows: rows[which]['operands'].update(operands)
        for modify in (alter(4, arrayBase=0x927d),  # final array byte aliases first subscript byte
                       alter(8, arrayBase=0xb103),  # one-byte overlap of destination spans
                       alter(5, value=0x9284),      # partially overlapping scalar names
                       alter(1, value=0x9ffc),      # five-byte load crosses into BASIC ROM
                       alter(4, extentsReversed=[2, 2]), alter(8, elementSize=2),
                       alter(4, value=252), alter(8, arrayBase=0x8fff)):
            with self.subTest(modify=modify):
                self.assertFalse(corridor(FLOAT, change=modify))
        self.assertFalse(corridor(WORD, layout=False))

    def test_refuse_other_control_entry_or_broken_interval(self):
        for offset in (4,6,7,8,10,12,13,14):
            for entry in (0x8a, 0x9f):
                with self.subTest(entry=entry, offset=offset):
                    self.assertFalse(corridor(WORD, tail=f'73 {entry:02x} {offset:02x} 00'))
        self.assertTrue(corridor(WORD, tail='73 8a 00 00'))  # entry at prompt
        self.assertFalse(corridor(WORD, skip=14))
        self.assertFalse(corridor(WORD, tail=''))
        self.assertFalse(corridor(WORD, change=lambda rows: rows[5].update(region='other')))
        self.assertFalse(corridor(WORD, change=lambda rows: rows[8].update(size=3)))

    def test_refuse_other_fields_effects_and_sources(self):
        for body in (WORD.replace('1a 7f', '1a 7e'), WORD.replace('80 3e', '80 3d'),
                     WORD.replace('80 3e', '7a 3e'), WORD.replace('52 1a 80', '52 84 1a 80'),
                     WORD.replace('a5 52', '1e 52'), WORD.replace('1a 80', '80 1a')):
            with self.subTest(body=body):
                self.assertFalse(corridor(body))
        self.assertFalse(corridor(WORD, prefix='7c 01 51'))
        for prefix in ('7b', '7d'):  # DATA and explicit file are not ambient prompt sources.
            self.assertFalse(corridor(WORD, prefix=prefix))
