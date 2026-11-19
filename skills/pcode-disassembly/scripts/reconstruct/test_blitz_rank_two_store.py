"""Authored source-free p-code: the last two literals are not index and rank."""
import unittest

from formats import profile
from test_blitz_file_input import groups


DIM = 'b7 b5 10 02 55 32 00 09 '  # DIM U2(7, 5), descriptor offset 9
STORE = 'b3 b4 a6 63 e4 09'


def last_store(code, family='blitz'):
    return next(g for g in reversed(groups(family, code))
                if g['instructions'][-1]['mnemonic'] == 'STORE_ARRAY')


class RankTwoStoreTests(unittest.TestCase):
    def test_distinct_axes_value_and_descriptor(self):
        g = last_store(DIM + STORE)
        self.assertEqual((g['kind'], g['text'], g['warnings']), ('inferred', 'U2(3, 4) = 99', []))
        self.assertEqual(g['evidenceAddresses'], [r['address'] for r in g['instructions']])
        self.assertEqual(last_store(DIM + '82 b1 08 b4 a6 63 e4 09')['text'], 'U2((Q9 - 1), 4) = 99')

    def test_other_ranks_descriptors_and_families_do_not_gain_two_axes(self):
        for code in (STORE, DIM + DIM + STORE, DIM.replace('02 55', '03 55') + STORE,
                     DIM.replace('32 00', '32 01') + STORE, DIM + STORE.replace('e4 09', 'e4 0b'),
                     DIM.replace('55 32', '55 b2') + STORE, DIM.replace('55 32', '00 55') + STORE,
                     DIM + '81 b4 a6 63 e4 09', DIM + 'b4 a6 63 e4 09',
                     DIM + 'b1 07 b4 a6 63 e4 09'):
            with self.subTest(code=code):
                self.assertNotIn('U2(', last_store(code)['text'])
        self.assertTrue(last_store(DIM + STORE, 'austrospeed')['text'].startswith('ELEM_'))

    def test_branch_bypassing_first_subscript_cannot_supply_it(self):
        main = profile('blitz')['dispatch']['startupPointerTable'] + 14
        target = main + len(bytes.fromhex(DIM)) + 4 + 1
        g = last_store(DIM + f'b1 52 {target:04x} ' + STORE)
        self.assertNotIn('U2(', g['text'])
        self.assertNotIn(target - 1, g['evidenceAddresses'])
