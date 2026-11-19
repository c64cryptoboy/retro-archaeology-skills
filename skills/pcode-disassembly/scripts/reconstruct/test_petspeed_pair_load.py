"""Synthetic byte streams, not BASIC-source or historical execution oracles."""
import importlib
import unittest

from formats import module, profile
from symbolic import lift


PS = module('petspeed')
ALT = importlib.import_module(PS.__name__ + '.variant_2267').build_profile(profile('petspeed'))


def read_groups(hexbytes, fingerprint=ALT['runtimeSha256']):
    data = bytes.fromhex(hexbytes)
    pc, rows = 0x3200, []
    while pc < 0x3200 + len(data):
        r = PS.decode_one(data, 0x3200, pc, 0x3200 + len(data), ALT)
        rows.append(r)
        pc += r['size']
    return lift('petspeed', dict(instructions=rows, runtimeSha256=fingerprint, loadedRegions=[
        dict(name='variable region', start=0x2800, end=0x2840),
        dict(name='array region', start=0x2900, end=0x2980)]))['groups']


class PairLoadTests(unittest.TestCase):
    def test_order_and_aliased_store(self):
        # D is both an index and the destination.  Use its old value, never a
        # value predicted from a previous store, and don't exchange FAC/ARG.
        prior, g = read_groups('52 19 64 fc 30 29 24 01 a1 64')
        self.assertEqual(prior['text'], 'V_2820 = 25')
        self.assertEqual((g['kind'], g['text']), ('inferred', 'V_2820 = PAIR_LOAD_2930(V_2820, V_2808)'))
        self.assertEqual(g['evidenceAddresses'], [0x3203, 0x3206, 0x3207, 0x3208, 0x3209])
        self.assertIn('live descriptor', ' '.join(g['warnings']))

    def test_two_loads_of_same_slot(self):
        g, = read_groups('fc 03 29 26 06 a1 61')
        self.assertEqual(g['text'], 'V_2808 = PAIR_LOAD_2903(V_2830, V_2830)')

    def test_no_deferred_or_reordered_read(self):
        for code in ('fc 30 29 01 24 a1 64', 'fc 30 29 24 01 a1 f5 24 f7 82 64',
                     'fc 30 29 24 01 a1 8a 64', 'fc 30 29 24 01 a8 64'):
            self.assertFalse(any(' = PAIR_LOAD_' in g['text'] for g in read_groups(code)))

    def test_no_interior_entry(self):
        # Jump to each producer after ARRAY_BASE, A1, or the consuming store.
        for target in (6, 7, 8, 9):
            gs = read_groups(f'd1 {target:02x} 32 fc 30 29 24 01 a1 64')
            self.assertFalse(any(' = PAIR_LOAD_' in g['text'] for g in gs))

    def test_refuse_wrong_region_and_fingerprint(self):
        for code in ('fc 02 29 24 01 a1 64', 'fc 80 29 24 01 a1 64',
                     'fc 52 00 24 01 a1 64', 'fc 30 29 2f 01 a1 64',
                     'fc 30 29 24 01 a1 6f'):
            self.assertFalse(any(' = PAIR_LOAD_' in g['text'] for g in read_groups(code)))
        for fingerprint in (None, profile('petspeed')['runtimeSha256']):
            gs = read_groups('fc 30 29 24 01 a1 64', fingerprint)
            self.assertFalse(any(' = PAIR_LOAD_' in g['text'] for g in gs))
