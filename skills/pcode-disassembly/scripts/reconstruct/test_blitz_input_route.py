"""A lost input route is not an executed file selector."""
import unittest

from formats import profile
from test_blitz_file_input import groups
from test_blitz_name_flags import FAMILIES


class InputRouteTests(unittest.TestCase):
    def test_join_before_input_and_get(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                main = profile(family)['dispatch']['startupPointerTable'] + 14
                # One incoming edge skips the selector.  $50 saves a retry PC only.
                code = f'b1 52 {main+6:04x} b4 48 50 81 55 a0 02 51 81 46'
                result = groups(family, code)
                self.assertEqual([(g['kind'], g['text']) for g in result[-3:-1]], [
                    ('partial', 'REM current-channel INPUT: Q9$, Q9'),
                    ('partial', 'REM current-channel GET: Q9$'),
                ])

    def test_executed_selectors_remain_distinct(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                result = groups(family, 'b4 48 81 46 82 48 81 46')
                self.assertEqual([g['text'] for g in result if g['text'].startswith('GET')],
                                 ['GET#4, Q9$', 'GET#<?>, Q9$'])

    def test_single_field_does_not_prove_keyboard_after_join(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                main = profile(family)['dispatch']['startupPointerTable'] + 14
                field = groups(family, f'b1 52 {main+6:04x} b4 48 50 a0 02 53')[-2]
                self.assertEqual((field['kind'], field['text']), ('partial', 'REM current-channel INPUT: Q9'))
