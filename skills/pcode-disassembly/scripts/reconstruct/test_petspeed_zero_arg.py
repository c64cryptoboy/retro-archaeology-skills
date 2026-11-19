"""The admitted $AB constant writes ARG only; do not preserve it across unknown entries."""
import unittest

from symbolic import lift


def listing(rows, extra=()):
    instructions = [dict(address=0x2000+i, bytes=f'{byte:02x}', size=1,
                         mnemonic=name, operands={}, grammar='none')
                    for i, (byte, name) in enumerate(rows)]
    return [group['text'] for group in lift('petspeed', {
        'instructions': instructions + list(extra), 'typedDataRecords': []})['groups']]


class ZeroArgTests(unittest.TestCase):
    compare_and_print = [(0x94, 'EQUAL'), (0xCF, 'PRINT_NUMBER')]

    def test_overwrites_arg_not_fac(self):
        lines = listing([(0x8A, 'ONE_FAC'), (0x97, 'ONE_ARG'), (0xAB, 'ZERO_ARG')] + self.compare_and_print)
        self.assertEqual(lines, ['PRINT (0 = 1);'])
        self.assertEqual(listing([(0xAB, 'ZERO_ARG')] + self.compare_and_print), ['PRINT (0 = <?>);'])

    def test_bypass_does_not_supply_either_register(self):
        jump = dict(address=0x2004, mnemonic='GOTO', grammar='u16le', bytes='d1 02 20', size=3,
                    operands={'target': 0x2002})
        lines = listing([(0x8A, 'ONE_FAC'), (0xAB, 'ZERO_ARG')] + self.compare_and_print, [jump])
        self.assertIn('PRINT (<?> = <?>);', lines)
        self.assertNotIn('PRINT (0 = 1);', lines)
