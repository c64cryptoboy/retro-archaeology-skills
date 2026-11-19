"""Synthetic typed names through the BLITZ and Austro-Speed object decoders."""
import unittest

from formats import decode, profile
from symbolic import lift


FAMILIES = ('blitz', 'austrospeed')


def fixture(family, code):
    base = 0x0801
    table = profile(family)['dispatch']['startupPointerTable']
    init = table + 12
    main = init + 2
    # Same two significant characters, four distinct name-byte flags.
    records = b''.join(bytes([first, second]) + bytes(5) for first, second in
                       [(0xD1, 0xB9), (0x51, 0xB9), (0x51, 0x39), (0xD1, 0x39)])
    vt = main + len(code)
    end = vt + len(records)
    pointers = b''.join(n.to_bytes(2, 'little') for n in (vt, end, end, init, init + 1, main))
    return base.to_bytes(2, 'little') + bytes(table - base) + pointers + b'\x16\xff' + code + records


class NameFlagTests(unittest.TestCase):
    def test_same_stem_scalar_slots_and_inline_dim_names(self):
        # Q9%=6 : Q9$="W" : Q9=Q9% : DIM U%(2) : DIM U$(3) : END
        code = bytes.fromhex('b6 c0 e9 57 c1 80 c2 b2 10 01 d5 80 00 07 b3 10 01 55 80 00 09 4f')
        for family in FAMILIES:
            with self.subTest(family=family):
                report = decode(fixture(family, code), family)
                self.assertEqual([r['name'] for r in report['scalarRecords']], ['Q9%', 'Q9$', 'Q9', 'FN Q9'])
                groups = lift(family, report)['groups']
                self.assertEqual([g['text'] for g in groups[1:]],
                                 ['Q9% = 6', 'Q9$ = "W"', 'Q9 = Q9%', 'DIM U%(2)', 'DIM U$(3)', 'END'])
                self.assertEqual([i for g in groups for i in g['instructions']], report['instructions'])

    def test_entry_at_typed_store_does_not_recover_skipped_value(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                main = profile(family)['dispatch']['startupPointerTable'] + 14
                code = b'\x19' + (main + 4).to_bytes(2, 'big') + bytes.fromhex('b6 c0 4f')
                report = decode(fixture(family, code), family)
                groups = lift(family, report)['groups']
                store = next(g for g in groups if g['instructions'][0]['address'] == main + 4)
                self.assertEqual(store['text'], 'Q9% = <?>')
                self.assertNotIn(main + 3, store['evidenceAddresses'])
