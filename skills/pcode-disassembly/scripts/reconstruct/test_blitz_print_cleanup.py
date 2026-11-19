"""Authored byte controls for the selected-output cleanup tail in both layouts."""
import unittest

from formats import profile
from test_blitz_file_input import groups
from test_blitz_name_flags import FAMILIES


CLEANUP = 'REM restore default I/O channels (no newline)'


class PrintCleanupTests(unittest.TestCase):
    def test_cleanup_after_effectful_output(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                result = groups(family, 'b3 48 b7 42 b1 27 3c 45 b2 3e 81 46')
                rnd = result[3]['instructions'][-1]['address']
                temp = f'T_{rnd:04X}'
                self.assertEqual([g['text'] for g in result[1:-1]], [
                    'REM SELECT_INPUT_CHANNEL 3', 'REM SELECT_OUTPUT_CHANNEL 7',
                    temp + ' = RND(1)', 'PRINT#7,  ' + temp + ';', CLEANUP, 'PRINT 2', 'GET Q9$',
                ])
                self.assertEqual([r['bytes'] for r in result[5]['instructions']], ['45'])

    def test_alternate_entry_at_cleanup_does_not_require_selection(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                main = profile(family)['dispatch']['startupPointerTable'] + 14
                target = main + 6
                result = groups(family, f'b1 52 {target:04x} b7 42 45 b4 3e')
                self.assertEqual(result[1]['text'], f'IF 1 THEN GOTO L_{target:04X}')
                self.assertEqual(result[3]['evidenceAddresses'], [target])
                self.assertEqual((result[3]['text'], result[3]['kind']), (CLEANUP, 'structural'))
                self.assertEqual(result[4]['text'], 'PRINT 4')

    def test_true_newlines_remain_prints(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                result = groups(family, 'b7 42 3f b4 43 b5 3e')
                self.assertEqual([g['text'].strip() for g in result[2:-1]],
                                 ['PRINT#7,', 'PRINT#7,  4', 'PRINT 5'])
