"""Authored BASIC-64 output sequences.  Decode only; no runtime required."""
import unittest

from test_basic64_addresses import groups


class PrintLineTests(unittest.TestCase):
    def test_order_and_owned_bytes(self):
        code = '37 03 3b 22 0d 83 26 ff 80 82 1e 0c 85 a5 80 81 1e 03 86 a9 ee 83 84'
        line, = groups(code)
        self.assertEqual(line['text'], 'PRINT ";"+CHR$(34)+CHR$(13); V_80FF; TAB(12); V_0380; SPC(3); V_03EE')
        rows = line['instructions']
        self.assertEqual(' '.join(r['bytes'] for r in rows), code)
        self.assertEqual(line['evidenceAddresses'], [0, 5, 6, 9, 10, 12, 13, 15, 16, 18, 19, 21, 22])
        self.assertEqual((line['kind'], line['warnings']), ('inferred', []))

    def test_known_entry_may_start_but_not_be_hidden(self):
        corridor = ' 37 01 58 83 1e 04 85 84'
        jump, line = groups('8a 03 00' + corridor)
        self.assertEqual((jump['text'], line['text']), ('GOTO L_0003', 'PRINT "X"; TAB(4)'))
        self.assertEqual(line['kind'], 'partial')
        self.assertIn('current output channel is unknown', line['warnings'][0])
        _, prefix, suffix = groups('8a 07 00' + corridor)
        self.assertEqual((prefix['text'], suffix['text']), ('PRINT "X";', 'PRINT TAB(4)'))
        for entry in ('8a 0a 00', '9f 0a 00'):  # target only the newline
            with self.subTest(entry=entry):
                result = groups(entry + corridor)
                self.assertEqual([g['text'] for g in result[1:]], ['PRINT "X";', 'PRINT TAB(4);', 'PRINT'])

    def test_missing_newline_extra_newline_and_spacing_boundary(self):
        for code, expected in [
            ('37 00 83 1e 04 85', ['PRINT "";', 'PRINT TAB(4);']),
            ('37 00 83 84 84', ['PRINT ""', 'PRINT']),
            ('37 01 21 83 87 84', ['PRINT "!";', 'PRINT ,', 'PRINT']),
            ('37 01 21 83 1e 09 a7 42 84', ['PRINT "!";', 'V_0342 = 9', 'PRINT']),
        ]:
            with self.subTest(code=code):
                self.assertEqual([g['text'] for g in groups(code)], expected)

    def test_explicit_selection_is_not_ambient_output(self):
        for select, file in [('1e 09 71', '9'), ('a5 87 71', '<?>')]:
            with self.subTest(select=select):
                _, item, newline, _, ambient = groups(select + ' 37 01 46 83 84 0f 37 01 52 83 84')
                self.assertEqual(item['text'], f'PRINT#{file},  "F";')
                self.assertEqual(newline['text'], f'PRINT#{file}, ')
                self.assertEqual(ambient['text'], 'PRINT "R"')
