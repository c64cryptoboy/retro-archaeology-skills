"""A lost BASIC-64 input route is not an explicit logical-file selection."""
import unittest
from test_basic64_addresses import groups


class InputRouteTests(unittest.TestCase):
    def test_entry_can_bypass_selector(self):
        g = groups('8a 06 00 1e 09 7d 7a 73')[-2]
        self.assertEqual((g['text'], g['kind']), ('REM current-channel GET: T_0006$', 'partial'))
        self.assertEqual(groups('1e 09 7d 7a 73')[-2]['text'], 'GET#9, T_0003$')
        self.assertEqual(groups('7d 7a 73')[-2]['text'], 'GET#<?>, T_0001$')

    def test_lost_route_does_not_prove_file_or_keyboard(self):
        fields = [g['text'] for g in groups('7a 7c 00 08 00 80 aa fe 73')]
        self.assertIn('REM current-channel INPUT FIELD -> T_0005$', fields)
        for expected in ('GET T_0000$', 'REM current-channel GET: T_0001$'):
            self.assertIn(expected, [g['text'] for g in groups('7a 7a 73')])
        self.assertEqual(groups('7b 80 ab 3f 73')[1]['text'], 'READ V_033F')
