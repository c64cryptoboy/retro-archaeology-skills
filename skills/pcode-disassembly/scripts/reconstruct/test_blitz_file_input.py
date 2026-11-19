"""Authored byte controls for literal-file multi-field INPUT in both layouts."""
import unittest

from formats import decode, profile
from symbolic import lift
from test_blitz_name_flags import FAMILIES, fixture


def groups(family, code):
    report = decode(fixture(family, bytes.fromhex(code) + b'\x4f'), family)
    result = lift(family, report)['groups']
    assert [r for g in result for r in g['instructions']] == report['instructions']
    return result


class FileInputTests(unittest.TestCase):
    def test_complete_list_with_middle_field_and_linked_selector(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                result = groups(family, 'b7 48 81 55 a0 00 57 a0 02 51')
                selected, fields = result[1:3]
                self.assertEqual(('inferred', 'INPUT#7, Q9$, Q9%, Q9'), (fields['kind'], fields['text']))
                self.assertEqual(fields['evidenceAddresses'], [r['address'] for g in (selected, fields) for r in g['instructions']])

    def test_control_entry_can_bypass_the_selector_or_an_earlier_field(self):
        for family in FAMILIES:
            main = profile(family)['dispatch']['startupPointerTable'] + 14
            for offset in (1, 2, 3, 4, 6):
                with self.subTest(family=family, offset=offset):
                    # Conditional absolute target inside: B7 48 81 55 A0 02 51.
                    target = main + 4 + offset
                    result = groups(family, f'b1 52 {target >> 8:02x} {target & 255:02x} b7 48 81 55 a0 02 51')
                    final = next(g for g in result if g['instructions'][-1]['mnemonic'] == 'INPUT_FINAL')
                    self.assertEqual(final['kind'], 'partial')
                    self.assertTrue(final['text'].startswith('REM INPUT continuation:'))

    def test_no_new_file_claim_for_other_sequences(self):
        for family in FAMILIES:
            for code in ('b0 48 81 55 a0 02 51',     # zero/keyboard path
                         '82 48 81 55 a0 02 51',     # mutable file expression
                         'b7 42 81 55 a0 02 51',     # output selector
                         'b7 48 81 57 a0 02 51',     # no first-field handler
                         'b7 48 82 55 a0 02 51',     # numeric value, not a destination
                         'b7 48 83 55 a0 02 51',     # FN slot, not a destination
                         'b7 48 81 55 a0 1f 51',     # no such scalar record
                         'a0 02 55 b1 42 b7 48 81 55 a0 02 51',  # stale earlier field
                         'b7 48 81 46 81 55 a0 02 51'):  # intervening GET
                with self.subTest(family=family, code=code):
                    self.assertTrue(groups(family, code)[-2]['text'].startswith('REM INPUT continuation:'))
