"""Source-free byte controls for BLITZ/Austro field-list joins."""
import unittest
from test_blitz_leaf_fn import fixture, output


class InputEntryTests(unittest.TestCase):
    def test_branch_to_second_destination_must_not_inherit_first(self):
        fields=bytes.fromhex('50 a0 00 55 a0 02 51 4f')
        for family in ('blitz','austrospeed'):
            with self.subTest(family=family):
                start=next(r['skipTarget'] for r in fixture(family)['instructions'] if r['mnemonic']=='DEF_FN')
                _,linear=output(fixture(family,continuation=fields),family)
                self.assertIn('X, Y',linear)
                branch=bytes.fromhex('b1 52')+(start+8).to_bytes(2,'big')
                joined,_=output(fixture(family,continuation=branch+fields),family)
                final=next(g for g in joined['groups'] if any(r['mnemonic']=='INPUT_FINAL' for r in g['instructions']))
                self.assertEqual((final['kind'],final['text']),('partial','REM INPUT continuation: Y'))
                self.assertTrue(any('Earlier field list is unknown' in w for w in final['warnings']))
