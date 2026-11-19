"""Authored field/index controls independent of any original program."""
import unittest

from formats import profile
from test_blitz_file_input import groups
from test_blitz_name_flags import FAMILIES


# Bounds 6 and 5; descriptor offsets 9 and 11.  Neither quantity is an index.
DIMS = 'b6 10 01 d5 80 00 09 b5 10 01 56 80 00 0b '
LIST = 'b7 48 82 a4 09 55 b4 a4 0b 51'


class IndexedFileInputTests(unittest.TestCase):
    def test_each_field_has_its_own_index_and_selector_link(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                gs = groups(family, DIMS + LIST + ' 81 46')
                selector, fields, following = gs[-4:-1]
                self.assertEqual((fields['kind'], fields['text']), ('inferred', 'INPUT#7, U%(Q9), V$(4)'))
                self.assertEqual(fields['evidenceAddresses'], [r['address'] for g in (selector, fields) for r in g['instructions']])
                self.assertEqual(following['text'], 'REM current-channel GET: Q9$')
                fields = groups(family, DIMS + 'b7 48 a0 02 55 82 a4 09 57 81 51')[-2]
                self.assertEqual(fields['text'], 'INPUT#7, Q9, U%(Q9), Q9$')

    def test_alternate_entries_do_not_borrow_selector_or_index(self):
        for family in FAMILIES:
            main = profile(family)['dispatch']['startupPointerTable'] + 14
            for offset in (1, 2, 3, 5, 6, 7, 9):
                with self.subTest(family=family, offset=offset):
                    target = main + len(bytes.fromhex(DIMS)) + 4 + offset
                    g = groups(family, DIMS + f'b1 52 {target:04x} ' + LIST)[-2]
                    self.assertTrue(g['text'].startswith('REM INPUT continuation:'))
                    self.assertFalse(any(a < target for a in g['evidenceAddresses']))

    def test_reject_missing_wrong_or_unproved_operands(self):
        for family in FAMILIES:
            for code in (DIMS + 'b7 48 a4 09 55 b4 a4 0b 51',  # missing first index
                         DIMS + 'b7 48 82 a4 09 55 a4 0b 51',  # do not reuse first index
                         DIMS + '82 b7 48 a4 09 55 b4 a4 0b 51',  # index outside list
                         DIMS + LIST.replace('82 a4', '81 a4'),  # string as index
                         DIMS + LIST.replace('82 a4', '83 a4'),  # function slot
                         DIMS + LIST.replace('82 a4', '9e a4'),  # missing slot
                         DIMS + LIST.replace('b7 48', '82 48'),  # computed channel
                         DIMS + LIST.replace('b7 48', 'b0 48'),  # zero channel
                         DIMS + LIST.replace('0b 51', '0d 51'),  # undeclared array
                         DIMS.replace('b5 10 01', 'b5 b2 10 02') + LIST,  # not rank one
                         DIMS + 'b2 10 01 58 80 00 09 ' + LIST):  # ambiguous descriptor
                with self.subTest(family=family, code=code):
                    self.assertTrue(groups(family, code)[-2]['text'].startswith('REM INPUT continuation:'))

    def test_retry_entry_does_not_reuse_pre_begin_index(self):
        for family in FAMILIES:
            # Keyboard form: retry starts after $50.  A producer on the
            # other side of $50 cannot become the first field's subscript.
            g = groups(family, DIMS + '82 50 a4 09 55 b4 a4 0b 51')[-2]
            self.assertEqual((g['kind'], g['text']), ('partial', 'INPUT U%(<?>), V$(4)'))
