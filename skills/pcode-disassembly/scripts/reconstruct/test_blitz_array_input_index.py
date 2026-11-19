"""Source-free controls: declaration arity, selector, and element index are distinct."""
import unittest

from formats import profile
from test_blitz_file_input import groups
from test_blitz_name_flags import FAMILIES


# Upper bound 6, rank 1, and descriptor offset 9; none is the index.
DIM = 'b6 10 01 55 80 00 09 '


class ArrayInputIndexTests(unittest.TestCase):
    def test_get_needs_a_separate_subscript_even_after_a_selector(self):
        for family in FAMILIES:
            for code, expected in [('a4 09 46', 'GET U$(<?>)'),
                                   ('b7 48 a4 09 46', 'GET#7, U$(<?>)'),
                                   ('82 b7 48 a4 09 46', 'GET#7, U$(Q9)'),
                                   ('b4 a4 09 46', 'GET U$(4)')]:
                with self.subTest(family=family, code=code):
                    g = groups(family, DIM + code)[-2]
                    self.assertEqual(g['text'], expected)
                    unknown = '<?>' in expected
                    self.assertEqual(g['kind'], 'partial' if unknown else 'inferred')
                    self.assertEqual(any('no reaching subscript' in w for w in g['warnings']), unknown)

    def test_branch_can_skip_an_adjacent_valid_index(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                main = profile(family)['dispatch']['startupPointerTable'] + 14
                target = main + len(bytes.fromhex(DIM)) + 5
                g = groups(family, DIM + f'b1 52 {target:04x} 82 a4 09 46')[-2]
                self.assertEqual((g['kind'], g['text']), ('partial', 'REM current-channel GET: U$(<?>)'))
                self.assertNotIn(target - 1, g['evidenceAddresses'])

    def test_retry_starts_after_input_begin_not_at_previous_index(self):
        # Numeric U% permits the input parser's retry.  Only the producer on
        # the retry side of $50 is also evaluated on a repeated attempt.
        for family in FAMILIES:
            for operands, expected in [('82 50', '<?>'), ('50 82', 'Q9')]:
                with self.subTest(family=family, operands=operands):
                    g = groups(family, 'b6 10 01 d5 80 00 09 ' + operands + ' a4 09 53')[-2]
                    self.assertEqual(g['text'], 'INPUT U%(' + expected + ')')
                    self.assertEqual(g['kind'], 'partial' if expected == '<?>' else 'inferred')
