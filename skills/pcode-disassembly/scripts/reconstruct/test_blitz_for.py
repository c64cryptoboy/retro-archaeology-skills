"""Literal counter initialization on two independently profiled VM contracts."""
import unittest
from test_blitz_leaf_fn import fixture, output


class LiteralForTests(unittest.TestCase):
    def test_first_target_and_all_rows_stay_at_the_header(self):
        for family in ('blitz', 'austrospeed'):
            report = fixture(family, continuation=bytes.fromhex('b2 c0 b4 a0 00 11 4f'))
            result, _ = output(report, family)
            header = next(g for g in result['groups'] if g['text'] == 'FOR X = 2 TO 4')
            rows = report['instructions'][-6:-1]
            self.assertEqual(header['instructions'], rows)
            self.assertEqual(header['evidenceAddresses'], [r['address'] for r in rows])
            definition = next(r for r in report['instructions'] if r['mnemonic'] == 'DEF_FN')
            self.assertEqual(rows[0]['address'], definition['skipTarget'])

    def test_interior_entry_counter_dependency_other_slot_or_intervening_effect_refuses(self):
        for code, branch_into_limit in [('b2 c0 b4 a0 00 11 4f', True), ('b2 c0 80 a0 00 11 4f', False),
                                        ('b2 c0 b4 a0 02 11 4f', False), ('b2 c0 49 b4 a0 00 11 4f', False),
                                        ('b2 c0 b4 b1 a0 00 12 4f', False)]:
            with self.subTest(code=code):
                report = fixture(continuation=bytes.fromhex(code))
                if branch_into_limit:
                    # Inject an alternate incoming edge to the limit, bypassing the store.
                    report['instructions'][0]['targets'] = [report['instructions'][-4]['address']]
                _, text = output(report)
                self.assertIn('X = 2\n', text)
                self.assertIn(' STEP ', text)
