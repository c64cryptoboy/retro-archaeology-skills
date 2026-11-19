"""BASIC-64 loop headers from authored, non-executed instruction fragments."""
import unittest
from test_basic64_addresses import groups


class Basic64ForTests(unittest.TestCase):
    def test_literal_headers_keep_rows_and_first_entry(self):
        for code, expected in [
            ('22 02 28 40 42 22 09 2b 74 40 42', 'FOR V_4240 = 2 TO 9'),
            ('23 f9 ff 28 40 42 22 05 2b 23 fd ff 76 40 42', 'FOR V_4240 = -7 TO 5 STEP -3'),
            ('1e 08 a7 42 1e 0c 75 42 03', 'FOR V_0342 = 8 TO 12'),
        ]:
            with self.subTest(code=code):
                jump, header = groups('8a 03 00 ' + code)
                self.assertEqual(jump['text'], 'GOTO L_0003')
                self.assertEqual(header['text'], expected)
                self.assertEqual(header['kind'], 'inferred')
                self.assertEqual(header['instructions'][0]['address'], 3)
                self.assertEqual(header['evidenceAddresses'], [r['address'] for r in header['instructions']])

    def test_explicit_entries_do_not_swallow_labels_or_bypass_store(self):
        code = '22 02 28 40 42 22 09 2b 23 fd ff 76 40 42'
        # Incoming GOTO to store, bound, push, explicit step, or setup.
        for address in (5, 8, 10, 11, 14):
            with self.subTest(address=address):
                result = groups(f'8a {address:02x} 00 ' + code)
                self.assertIn(address, [g['instructions'][0]['address'] for g in result])
                self.assertFalse(any(g['text'].startswith('FOR V_4240 = 2 TO') for g in result))

    def test_dependent_bound_wrong_pointer_intervening_effect_or_stack_shape(self):
        for code in [
            '22 02 28 40 42 26 40 42 2b 74 40 42',  # bound reads the initialized counter
            '1e 02 a7 42 1e 09 75 42 04',           # same low byte, different page
            '22 02 28 40 42 95 22 09 2b 74 40 42',  # STOP between store and bound
            '22 02 28 40 42 22 09 74 40 42',        # FAC alone does not supply the limit
            '22 02 28 40 42 22 09 2b 26 40 42 76 40 42',  # nonliteral step
        ]:
            with self.subTest(code=code):
                result = groups(code)
                self.assertIn(' = 2', result[0]['text'])
                self.assertIn('Initial assignment shown separately.', result[-1]['warnings'])
