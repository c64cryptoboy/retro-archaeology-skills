"""Synthetic semantic-record checks; no runtime/profile admission or target bytes."""
import unittest

from symbolic import lift


def row(mnemonic, **operands):
    return {'mnemonic': mnemonic, 'bytes': '00', 'size': 1,
            'grammar': 'none', 'operands': operands}


def program(*rows, family='petspeed'):
    return lift(family, {'instructions': [
        {'address': 0x1000 + i, **record} for i, record in enumerate(rows)
    ]})


def text(result):
    return '\n'.join(group['text'] for group in result['groups'])


def store():
    return row('STORE_FAC_VAR', variable=0x2800)


class PETSpeedTimeArgTests(unittest.TestCase):
    def test_preserves_fac_and_subtract_orientation(self):
        result = program(row('LOAD_FAC_VAR', variable=0x2810), row('TIME_ARG'),
                         row('SUBTRACT'), store())
        self.assertEqual(text(result),
                         'T_1001 = TI\nV_2800 = (T_1001 - V_2810)')
        self.assertEqual(result['groups'][-1]['evidenceAddresses'],
                         [0x1000, 0x1001, 0x1002, 0x1003])
        self.assertIn('Runtime system-variable representation may differ from stock BASIC.',
                      result['groups'][-1]['warnings'])
        self.assertEqual([r['address'] for g in result['groups'] for r in g['instructions']],
                         list(range(0x1000, 0x1004)))

    def test_replaces_stale_arg_without_replacing_fac(self):
        result = program(row('CONST_U8_ARG', value=99),
                         row('CONST_U8_FAC', value=7), row('TIME_ARG'),
                         row('SUBTRACT'), store())
        self.assertEqual(text(result), 'T_1002 = TI\nV_2800 = (T_1002 - 7)')

    def test_missing_fac_is_not_invented(self):
        result = program(row('TIME_ARG'), row('SUBTRACT'), store())
        self.assertEqual(text(result), 'T_1000 = TI\nV_2800 = (T_1000 - <?>)')
        self.assertEqual(result['groups'][-1]['kind'], 'partial')

    def test_clock_samples_remain_distinct_and_ordered(self):
        result = program(row('TIME_FAC'), row('TIME_ARG'), row('SUBTRACT'), store())
        self.assertEqual(text(result),
                         'T_1000 = TI\nT_1001 = TI\nV_2800 = (T_1001 - T_1000)')
        self.assertEqual(text(result).count(' = TI'), 2)

    def test_join_does_not_reuse_predecessor_values(self):
        result = program(row('CONST_U8_FAC', value=7), row('TIME_ARG'),
                         row('SUBTRACT'), store(), row('GOTO', target=0x1002))
        self.assertIn('V_2800 = (<?> - <?>)', text(result))
        self.assertNotIn('V_2800 = (T_1001 - 7)', text(result))
        self.assertEqual(text(result).count(' = TI'), 1)

    def test_unknown_effect_still_discards_clock_value(self):
        result = program(row('CONST_U8_FAC', value=7), row('TIME_ARG'),
                         row('UNMODELED_EFFECT'), row('SUBTRACT'), store())
        self.assertIn('UNMODELED_EFFECT semantics not yet modeled', text(result))
        self.assertIn('V_2800 = (<?> - <?>)', text(result))

    def test_region_boundary_still_discards_values(self):
        subtract = {**row('SUBTRACT'), 'region': 'other'}
        assignment = {**store(), 'region': 'other'}
        result = program(row('CONST_U8_FAC', value=7), row('TIME_ARG'),
                         subtract, assignment)
        self.assertIn('V_2800 = (<?> - <?>)', text(result))

    def test_string_type_clobber_form_remains_unresolved(self):
        result = program(row('CONST_U8_FAC', value=7), row('TIME_ARG'),
                         row('TIME_STRING_ARG_FAC_TYPE_CLOBBER'), store())
        self.assertIn('TIME_STRING_ARG_FAC_TYPE_CLOBBER semantics not yet modeled', text(result))
        self.assertIn('V_2800 = <?>', text(result))
        self.assertNotIn('TI$', text(result))

    def test_rule_does_not_leak_to_other_families(self):
        for family in ('blitz', 'basic64', 'dtl'):
            with self.subTest(family=family):
                result = program(row('TIME_ARG'), family=family)
                self.assertIn('TIME_ARG semantics not yet modeled', text(result))
                self.assertNotIn(' = TI', text(result))


if __name__ == '__main__':
    unittest.main()
