"""The exact reserved DIM descriptor is not a normal BASIC variable name."""
import unittest

from formats import decode
from symbolic import lift
from test_blitz_name_flags import FAMILIES, fixture


class ReservedArrayTests(unittest.TestCase):
    def test_reserved_and_source_array_keep_distinct_bounds_and_ownership(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                code = bytes.fromhex('b2 10 01 da aa 00 00 b4 10 01 d5 80 00 07 4f')
                report = decode(fixture(family, code), family)
                groups = lift(family, report)['groups']
                reserved, normal = groups[1:3]
                self.assertEqual(reserved['kind'], 'structural')
                self.assertEqual(reserved['text'], 'REM allocate reserved integer array Z*%, upper bound 2')
                self.assertEqual(normal['text'], 'DIM U%(4)')
                self.assertEqual([r for g in groups for r in g['instructions']], report['instructions'])

    def test_nearby_descriptors_not_given_internal_role(self):
        for family in FAMILIES:
            for operand in ('01 da aa 01 00','01 da aa 00 07','01 da b0 00 00','02 da aa 00 00'):
                with self.subTest(family=family, operand=operand):
                    code = bytes.fromhex('b1 b2 10 '+operand+' 4f')
                    report = decode(fixture(family, code), family)
                    dim = next(r for r in report['instructions'] if r['mnemonic'] == 'DIM_INTERNAL')
                    self.assertNotIn('reservedArray',dim)
